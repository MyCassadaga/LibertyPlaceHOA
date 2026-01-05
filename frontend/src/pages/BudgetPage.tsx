import React, { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import { BudgetAttachment, BudgetSummary, Contract, ReservePlanItem } from '../types';
import { userHasAnyRole, userHasRole } from '../utils/roles';
import {
  useBudgetAttachmentMutation,
  useBudgetDetailQuery,
  useBudgetLineItemMutation,
  useBudgetStatusMutation,
  useBudgetsQuery,
  useReserveItemMutation,
  useCreateBudgetMutation,
  useUpdateBudgetMutation,
} from '../features/budgets/hooks';
import { useContractsQuery } from '../features/billing/hooks';

const editorRoles = ['BOARD', 'TREASURER', 'SYSADMIN'];

const BUDGET_CATEGORIES = [
  'Accounting Services',
  'Contracts',
  'Insurance',
  'Licenses and Permits',
  'Property Taxes',
  'Reimbursables',
  'Reserve Contribution',
  'Reserve Study',
  'Website Costs',
];

const emptyLineForm = {
  label: '',
  category: '',
  amount: '',
  sort_order: 0,
};

const emptyReserveForm = {
  name: '',
  target_year: new Date().getFullYear(),
  estimated_cost: '',
  inflation_rate: 0,
  current_funding: '',
  notes: '',
};

const BudgetPage: React.FC = () => {
  const { user } = useAuth();
  const canEdit = useMemo(() => userHasAnyRole(user, editorRoles), [user]);
  const isBoardMember = useMemo(() => !!user && userHasRole(user, 'BOARD'), [user]);
  const isSysAdmin = useMemo(() => !!user && userHasRole(user, 'SYSADMIN'), [user]);
  const isTreasurer = useMemo(() => !!user && userHasRole(user, 'TREASURER'), [user]);
  const canForceLock = useMemo(() => isSysAdmin || isTreasurer, [isSysAdmin, isTreasurer]);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const budgetsQuery = useBudgetsQuery();
  const contractsQuery = useContractsQuery(canEdit);
  const contracts = useMemo<Contract[]>(() => contractsQuery.data ?? [], [contractsQuery.data]);
  const budgets = useMemo<BudgetSummary[]>(() => budgetsQuery.data ?? [], [budgetsQuery.data]);
  const detailQuery = useBudgetDetailQuery(selectedId);
  const detail = detailQuery.data ?? null;
  const budgetsError = budgetsQuery.isError ? 'Unable to load budgets.' : null;
  const detailError = selectedId != null && detailQuery.isError ? 'Unable to load budget details.' : null;
  const combinedError = error ?? detailError ?? budgetsError;
  const loading = budgetsQuery.isLoading || (selectedId != null && detailQuery.isLoading);

  const [newBudgetYear, setNewBudgetYear] = useState<number>(new Date().getFullYear());
  const [newBudgetHomes, setNewBudgetHomes] = useState<number>(0);

  const [lineForm, setLineForm] = useState<typeof emptyLineForm>(emptyLineForm);
  const [editingLineId, setEditingLineId] = useState<number | null>(null);
  const [contractSelection, setContractSelection] = useState('');
  const [contractAmount, setContractAmount] = useState('');

  const [reserveForm, setReserveForm] = useState<typeof emptyReserveForm>(emptyReserveForm);
  const [editingReserveId, setEditingReserveId] = useState<number | null>(null);

  const [attachmentUploading, setAttachmentUploading] = useState(false);
  const [metaForm, setMetaForm] = useState<{ home_count: number; notes: string }>({
    home_count: 0,
    notes: '',
  });

  const categoryOptions = useMemo(() => {
    const options = [...BUDGET_CATEGORIES];
    if (lineForm.category && !options.includes(lineForm.category)) {
      options.push(lineForm.category);
    }
    return options;
  }, [lineForm.category]);

  const formatCurrency = (value: string | number) => {
    const num = typeof value === 'string' ? Number(value) : value;
    return num.toLocaleString(undefined, { style: 'currency', currency: 'USD' });
  };

  const createBudgetMutation = useCreateBudgetMutation();
  const updateBudgetMutation = useUpdateBudgetMutation();
  const approveMutation = useBudgetStatusMutation('approve');
  const withdrawMutation = useBudgetStatusMutation('withdraw');
  const lockMutation = useBudgetStatusMutation('lock');
  const unlockMutation = useBudgetStatusMutation('unlock');
  const lineAddMutation = useBudgetLineItemMutation('add');
  const lineUpdateMutation = useBudgetLineItemMutation('update');
  const lineDeleteMutation = useBudgetLineItemMutation('delete');
  const reserveAddMutation = useReserveItemMutation('add');
  const reserveUpdateMutation = useReserveItemMutation('update');
  const reserveDeleteMutation = useReserveItemMutation('delete');
  const uploadAttachmentMutation = useBudgetAttachmentMutation('upload');
  const deleteAttachmentMutation = useBudgetAttachmentMutation('delete');

  useEffect(() => {
    if (!budgets.length) {
      setSelectedId(null);
      return;
    }
    setSelectedId((current) => {
      if (current && budgets.some((budget) => budget.id === current)) {
        return current;
      }
      return budgets[0].id;
    });
  }, [budgets]);

  useEffect(() => {
    if (detail) {
      setMetaForm({
        home_count: detail.home_count ?? 0,
        notes: detail.notes ?? '',
      });
    } else {
      setMetaForm({ home_count: 0, notes: '' });
    }
  }, [detail]);

  const handleCreateBudget = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canEdit) return;
    try {
      const data = await createBudgetMutation.mutateAsync({ year: newBudgetYear, home_count: newBudgetHomes });
      setStatusMessage('Budget created.');
      setSelectedId(data.id);
      await budgetsQuery.refetch();
    } catch (err) {
      console.error('Unable to create budget.', err);
      setError('Unable to create budget.');
    }
  };

  const handleBudgetMetaUpdate = async () => {
    if (!detail || !canEdit) return;
    try {
      await updateBudgetMutation.mutateAsync({
        budgetId: detail.id,
        payload: { home_count: metaForm.home_count, notes: metaForm.notes || undefined },
      });
      setStatusMessage('Budget updated.');
      await detailQuery.refetch();
    } catch (err) {
      console.error('Unable to update budget.', err);
      setError('Unable to update budget.');
    }
  };

  const handleApproveBudget = async () => {
    if (!detail) return;
    try {
      await approveMutation.mutateAsync(detail.id);
      setStatusMessage('Approval recorded.');
      await detailQuery.refetch();
    } catch (err) {
      console.error('Unable to record approval.', err);
      setError('Unable to record approval.');
    }
  };

  const handleWithdrawApproval = async () => {
    if (!detail) return;
    try {
      await withdrawMutation.mutateAsync(detail.id);
      setStatusMessage('Approval withdrawn.');
      await detailQuery.refetch();
    } catch (err) {
      console.error('Unable to withdraw approval.', err);
      setError('Unable to withdraw approval.');
    }
  };

  const handleUnlockBudget = async () => {
    if (!detail) return;
    if (!window.confirm('Unlock this budget for edits?')) return;
    try {
      await unlockMutation.mutateAsync(detail.id);
      setStatusMessage('Budget unlocked.');
      await detailQuery.refetch();
    } catch (err) {
      console.error('Unable to unlock budget.', err);
      setError('Unable to unlock budget.');
    }
  };

  const handleForceLock = async () => {
    if (!detail) return;
    if (!window.confirm('Lock and approve this budget immediately?')) return;
    try {
      await lockMutation.mutateAsync(detail.id);
      setStatusMessage('Budget locked.');
      await detailQuery.refetch();
    } catch (err) {
      console.error('Unable to lock budget.', err);
      setError('Unable to lock budget.');
    }
  };

  const handleLineSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!detail || !canEdit) return;
    try {
      if (editingLineId) {
        await lineUpdateMutation.mutateAsync({
          budgetId: detail.id,
          lineItemId: editingLineId,
          payload: {
            label: lineForm.label,
            category: lineForm.category,
            amount: lineForm.amount,
            sort_order: lineForm.sort_order,
          },
        });
        setStatusMessage('Line item updated.');
      } else {
        await lineAddMutation.mutateAsync({ budgetId: detail.id, payload: { ...lineForm, is_reserve: false } });
        setStatusMessage('Line item added.');
      }
      setLineForm(emptyLineForm);
      setEditingLineId(null);
      await detailQuery.refetch();
    } catch (err) {
      console.error('Unable to save line item.', err);
      setError('Unable to save line item.');
    }
  };

  const selectedContract = useMemo(
    () => contracts.find((contract) => contract.id === Number(contractSelection)) ?? null,
    [contracts, contractSelection],
  );

  const handleAddContractLine = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!detail || !canEdit || !selectedContract) return;
    const amountValue = contractAmount || selectedContract.value || '';
    if (!amountValue) {
      setError('Enter a contract value before adding it to the budget.');
      return;
    }
    try {
      await lineAddMutation.mutateAsync({
        budgetId: detail.id,
        payload: {
          label: selectedContract.vendor_name,
          category: 'Contracts',
          amount: amountValue,
          sort_order: 0,
          is_reserve: false,
        },
      });
      setStatusMessage('Contract added to line items.');
      setContractSelection('');
      setContractAmount('');
      await detailQuery.refetch();
    } catch (err) {
      console.error('Unable to add contract line item.', err);
      setError('Unable to add contract line item.');
    }
  };

  const handleReserveSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!detail || !canEdit) return;
    try {
      if (editingReserveId) {
        await reserveUpdateMutation.mutateAsync({
          budgetId: detail.id,
          reserveId: editingReserveId,
          payload: {
            name: reserveForm.name,
            target_year: reserveForm.target_year,
            estimated_cost: reserveForm.estimated_cost,
            inflation_rate: reserveForm.inflation_rate,
            current_funding: reserveForm.current_funding,
            notes: reserveForm.notes,
          },
        });
        setStatusMessage('Reserve item updated.');
      } else {
        await reserveAddMutation.mutateAsync({ budgetId: detail.id, payload: reserveForm });
        setStatusMessage('Reserve item added.');
      }
      setReserveForm(emptyReserveForm);
      setEditingReserveId(null);
      await detailQuery.refetch();
    } catch (err) {
      console.error('Unable to save reserve item.', err);
      setError('Unable to save reserve item.');
    }
  };

  const handleDeleteLine = async (itemId: number) => {
    if (!detail || !canEdit) return;
    if (!window.confirm('Remove this line item?')) return;
    try {
      await lineDeleteMutation.mutateAsync({ budgetId: detail.id, lineItemId: itemId });
      await detailQuery.refetch();
    } catch (err) {
      console.error('Unable to delete line item.', err);
      setError('Unable to delete line item.');
    }
  };

  const handleDeleteReserve = async (itemId: number) => {
    if (!detail || !canEdit) return;
    if (!window.confirm('Remove this reserve item?')) return;
    try {
      await reserveDeleteMutation.mutateAsync({ budgetId: detail.id, reserveId: itemId });
      await detailQuery.refetch();
    } catch (err) {
      console.error('Unable to delete reserve item.', err);
      setError('Unable to delete reserve item.');
    }
  };

  const handleAttachmentUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!detail || !canEdit || !event.target.files?.length) return;
    try {
      setAttachmentUploading(true);
      await uploadAttachmentMutation.mutateAsync({ budgetId: detail.id, file: event.target.files[0] });
      await detailQuery.refetch();
    } catch (err) {
      console.error('Unable to upload attachment.', err);
      setError('Unable to upload attachment.');
    } finally {
      setAttachmentUploading(false);
      event.target.value = '';
    }
  };

  const handleDeleteAttachment = async (attachment: BudgetAttachment) => {
    if (!canEdit || !detail) return;
    if (!window.confirm('Delete this attachment?')) return;
    try {
      await deleteAttachmentMutation.mutateAsync({ budgetId: detail.id, attachmentId: attachment.id });
      await detailQuery.refetch();
    } catch (err) {
      console.error('Unable to delete attachment.', err);
      setError('Unable to delete attachment.');
    }
  };

  const reserveFutureCost = (item: ReservePlanItem) => {
    if (!detail) return 0;
    const years = Math.max(item.target_year - detail.year, 0);
    const base = Number(item.estimated_cost);
    const rate = item.inflation_rate || 0;
    const projected = base * Math.pow(1 + rate, years);
    return projected;
  };

  const reserveAnnualContribution = (item: ReservePlanItem) => {
    if (!detail) return 0;
    const yearsRemaining = Math.max(item.target_year - detail.year, 1);
    const projected = reserveFutureCost(item);
    const remaining = Math.max(projected - Number(item.current_funding), 0);
    return remaining / yearsRemaining;
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-primary-600">Budget & Reserves</h2>
          <p className="text-sm text-slate-500">Annual budget planning and reserve projections.</p>
        </div>
        {statusMessage && <p className="text-sm text-emerald-600">{statusMessage}</p>}
      </header>

      {combinedError && <p className="text-sm text-red-600">{combinedError}</p>}
      {loading && <p className="text-sm text-slate-500">Loading budget data…</p>}

      <section className="grid gap-6 md:grid-cols-[260px,1fr]">
        <aside className="space-y-4">
          <div className="rounded border border-slate-200">
            <div className="border-b border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
              Budgets
            </div>
            <ul className="divide-y divide-slate-200">
              {budgets.map((budget) => (
                <li
                  key={budget.id}
                  className={`cursor-pointer px-3 py-2 text-sm hover:bg-primary-50 ${selectedId === budget.id ? 'bg-primary-50' : ''}`}
                  onClick={() => setSelectedId(budget.id)}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-700">{budget.year}</span>
                    <span className="text-xs uppercase text-slate-500">{budget.status}</span>
                  </div>
                  <p className="text-xs text-slate-500">{formatCurrency(budget.total_annual)}</p>
                </li>
              ))}
            </ul>
          </div>

          {canEdit && (
            <form className="rounded border border-slate-200 p-4 text-sm" onSubmit={handleCreateBudget}>
              <h3 className="mb-2 font-semibold text-slate-600">New Budget</h3>
              <label className="mb-2 block">
                <span className="text-xs text-slate-500">Year</span>
                <input
                  type="number"
                  className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
                  value={newBudgetYear}
                  onChange={(event) => setNewBudgetYear(Number(event.target.value))}
                  required
                />
              </label>
              <label className="mb-3 block">
                <span className="text-xs text-slate-500">Homes</span>
                <input
                  type="number"
                  className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
                  value={newBudgetHomes}
                  onChange={(event) => setNewBudgetHomes(Number(event.target.value))}
                />
              </label>
              <button
                type="submit"
                className="w-full rounded bg-primary-600 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-white hover:bg-primary-500"
              >
                Create
              </button>
            </form>
          )}
        </aside>

        <div className="space-y-4">
          {loading && <p className="text-sm text-slate-500">Loading budget…</p>}
          {detail ? (
            <div className="space-y-4">
              <div className="rounded border border-slate-200 p-4">
                <div className="flex flex-col gap-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h3 className="text-lg font-semibold text-slate-700">{detail.year} Budget</h3>
                      <p className="text-xs uppercase text-slate-500">Status: {detail.status}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {isBoardMember && detail.status !== 'APPROVED' && (
                        detail.user_has_approved ? (
                          <button
                            type="button"
                            className="rounded border border-slate-300 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-600 hover:bg-slate-50"
                            onClick={handleWithdrawApproval}
                          >
                            Withdraw approval
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="rounded bg-emerald-600 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white hover:bg-emerald-500"
                            onClick={handleApproveBudget}
                          >
                            Approve budget
                          </button>
                        )
                      )}
                      {canForceLock && detail.status !== 'APPROVED' && (
                        <button
                          type="button"
                          className="rounded border border-slate-300 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-600 hover:bg-slate-50"
                          onClick={handleForceLock}
                        >
                          Force lock
                        </button>
                      )}
                      {canForceLock && detail.status === 'APPROVED' && (
                        <button
                          type="button"
                          className="rounded border border-rose-200 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-rose-600 hover:bg-rose-50"
                          onClick={handleUnlockBudget}
                        >
                          Unlock
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
                    <span className="font-semibold">
                      Approvals: {detail.approval_count}/{detail.required_approvals || detail.approval_count || 0}
                    </span>
                    {detail.required_approvals > 0 && detail.status !== 'APPROVED' && (
                      <span className="text-xs text-slate-500">
                        {Math.max(detail.required_approvals - detail.approval_count, 0)} more approval(s) needed
                      </span>
                    )}
                    {detail.status === 'APPROVED' && (
                      <span className="text-xs text-emerald-600">
                        Homeowners have been notified of the new quarterly assessment.
                      </span>
                    )}
                  </div>
                  {detail.approvals.length > 0 && (
                    <div className="mt-2 rounded border border-slate-100 bg-slate-50 p-3 text-xs text-slate-600">
                      <p className="mb-1 font-semibold text-slate-700">Recorded approvals</p>
                      <ul className="space-y-1">
                        {detail.approvals.map((approval) => (
                          <li key={approval.user_id} className="flex items-center justify-between">
                            <span>{approval.full_name || approval.email || 'Board member'}</span>
                            <span className="text-slate-500">{approval.approved_at ? new Date(approval.approved_at).toLocaleString() : ''}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
                <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="rounded border border-slate-100 p-3 text-sm">
                    <p className="text-xs text-slate-500">Operations</p>
                    <p className="text-lg font-semibold text-primary-600">{formatCurrency(detail.operations_total)}</p>
                  </div>
                  <div className="rounded border border-slate-100 p-3 text-sm">
                    <p className="text-xs text-slate-500">Reserves</p>
                    <p className="text-lg font-semibold text-primary-600">{formatCurrency(detail.reserves_total)}</p>
                  </div>
                  <div className="rounded border border-slate-100 p-3 text-sm">
                    <p className="text-xs text-slate-500">Annual Total</p>
                    <p className="text-lg font-semibold text-primary-600">{formatCurrency(detail.total_annual)}</p>
                  </div>
                  <div className="rounded border border-slate-100 p-3 text-sm">
                    <p className="text-xs text-slate-500">Quarterly Assessment</p>
                    <p className="text-lg font-semibold text-primary-600">{formatCurrency(detail.assessment_per_quarter)}</p>
                  </div>
                </div>
                {canEdit && (
                  <div className="mt-4 space-y-3 text-sm">
                    <label className="block">
                      <span className="text-xs text-slate-500">Home count</span>
                      <input
                        type="number"
                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                        value={metaForm.home_count}
                        onChange={(event) =>
                          setMetaForm((prev) => ({ ...prev, home_count: Number(event.target.value) }))
                        }
                      />
                    </label>
                    <label className="block">
                      <span className="text-xs text-slate-500">Notes</span>
                      <textarea
                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                        rows={3}
                        value={metaForm.notes}
                        onChange={(event) => setMetaForm((prev) => ({ ...prev, notes: event.target.value }))}
                      />
                    </label>
                    <button
                      type="button"
                      className="rounded border border-slate-300 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-600 hover:bg-slate-50"
                      onClick={handleBudgetMetaUpdate}
                    >
                      Save meta
                    </button>
                  </div>
                )}
              </div>

              <section className="rounded border border-slate-200 p-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-semibold text-slate-600">Line Items</h4>
                </div>
                <div className="mt-3 overflow-x-auto">
                  <table className="min-w-full divide-y divide-slate-200 text-sm">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Label</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Category</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Amount</th>
                        {canEdit && <th className="px-3 py-2" />}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {detail.line_items.map((item) => (
                        <tr key={item.id}>
                          <td className="px-3 py-2">{item.label}</td>
                          <td className="px-3 py-2">{item.category ?? '—'}</td>
                          <td className="px-3 py-2">{formatCurrency(item.amount)}</td>
                          {canEdit && (
                            <td className="px-3 py-2 space-x-2 text-right text-xs">
                              <button
                                type="button"
                                className="text-primary-600"
                                onClick={() => {
                                  setEditingLineId(item.id);
                                  setLineForm({
                                    label: item.label,
                                    category: item.category ?? '',
                                    amount: item.amount,
                                    sort_order: item.sort_order,
                                  });
                                }}
                              >
                                Edit
                              </button>
                              <button
                                type="button"
                                className="text-rose-600"
                                onClick={() => handleDeleteLine(item.id)}
                              >
                                Delete
                              </button>
                            </td>
                          )}
                        </tr>
                      ))}
                      {detail.reserve_items.map((item) => (
                        <tr key={`reserve-${item.id}`} className="bg-primary-50/40">
                          <td className="px-3 py-2 font-semibold text-primary-700">
                            Reserve: {item.name}
                          </td>
                          <td className="px-3 py-2 text-xs text-primary-600">Reserve contribution</td>
                          <td className="px-3 py-2 font-semibold text-primary-700">
                            {formatCurrency(reserveAnnualContribution(item))}
                          </td>
                          {canEdit && <td className="px-3 py-2" />}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {canEdit && detail.status !== 'APPROVED' && contracts.length > 0 && (
                  <form className="mt-4 grid gap-3 rounded border border-dashed border-slate-200 p-3 md:grid-cols-3" onSubmit={handleAddContractLine}>
                    <div className="md:col-span-2">
                      <label className="text-xs text-slate-500">Add contract to line items</label>
                      <select
                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
                        value={contractSelection}
                        onChange={(event) => {
                          const value = event.target.value;
                          setContractSelection(value);
                          const chosen = contracts.find((contract) => contract.id === Number(value));
                          setContractAmount(chosen?.value ? String(chosen.value) : '');
                        }}
                      >
                        <option value="">Select contract…</option>
                        {contracts.map((contract) => (
                          <option key={contract.id} value={contract.id}>
                            {contract.vendor_name} {contract.service_type ? `• ${contract.service_type}` : ''}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-slate-500">Annual value</label>
                      <input
                        type="number"
                        step="0.01"
                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
                        value={contractAmount}
                        onChange={(event) => setContractAmount(event.target.value)}
                        placeholder="0.00"
                      />
                    </div>
                    <div className="md:col-span-3 flex justify-end">
                      <button
                        type="submit"
                        className="rounded bg-primary-600 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white hover:bg-primary-500 disabled:opacity-60"
                        disabled={!contractSelection}
                      >
                        Add contract line
                      </button>
                    </div>
                  </form>
                )}

                {canEdit && detail.status !== 'APPROVED' && (
                  <form className="mt-4 grid gap-3 md:grid-cols-2" onSubmit={handleLineSubmit}>
                    <label className="text-sm">
                      <span className="text-xs text-slate-500">Label</span>
                      <input
                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                        value={lineForm.label}
                        onChange={(event) => setLineForm((prev) => ({ ...prev, label: event.target.value }))}
                        required
                      />
                    </label>
                    <label className="text-sm">
                      <span className="text-xs text-slate-500">Category</span>
                      <select
                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                        value={lineForm.category}
                        onChange={(event) => setLineForm((prev) => ({ ...prev, category: event.target.value }))}
                      >
                        <option value="">Select category…</option>
                        {categoryOptions.map((category) => (
                          <option key={category} value={category}>
                            {category}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="text-sm">
                      <span className="text-xs text-slate-500">Amount</span>
                      <input
                        type="number"
                        step="0.01"
                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                        value={lineForm.amount}
                        onChange={(event) => setLineForm((prev) => ({ ...prev, amount: event.target.value }))}
                        required
                      />
                    </label>
                    <div className="md:col-span-2 flex gap-2">
                      <button
                        type="submit"
                        className="rounded bg-primary-600 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white hover:bg-primary-500"
                      >
                        {editingLineId ? 'Update line' : 'Add line'}
                      </button>
                      {editingLineId && (
                        <button
                          type="button"
                          className="rounded border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-600"
                          onClick={() => {
                            setEditingLineId(null);
                            setLineForm(emptyLineForm);
                          }}
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </form>
                )}
              </section>

              <section className="rounded border border-slate-200 p-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-semibold text-slate-600">Reserve Plan</h4>
                </div>
                <div className="mt-3 overflow-x-auto">
                  <table className="min-w-full divide-y divide-slate-200 text-sm">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Item</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Target Year</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Est. Cost</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Inflation %</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Projected Cost</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Annual Contribution</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Current Funding</th>
                        {canEdit && <th className="px-3 py-2" />}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {detail.reserve_items.map((item) => (
                        <tr key={item.id}>
                          <td className="px-3 py-2">
                            <p className="font-semibold text-slate-700">{item.name}</p>
                            {item.notes && <p className="text-xs text-slate-500">{item.notes}</p>}
                          </td>
                          <td className="px-3 py-2">{item.target_year}</td>
                          <td className="px-3 py-2">{formatCurrency(item.estimated_cost)}</td>
                          <td className="px-3 py-2">{(item.inflation_rate * 100).toFixed(1)}%</td>
                          <td className="px-3 py-2">{formatCurrency(reserveFutureCost(item))}</td>
                          <td className="px-3 py-2">{formatCurrency(reserveAnnualContribution(item))}</td>
                          <td className="px-3 py-2">{formatCurrency(item.current_funding)}</td>
                          {canEdit && (
                            <td className="px-3 py-2 space-x-2 text-right text-xs">
                              <button
                                type="button"
                                className="text-primary-600"
                                onClick={() => {
                                  setEditingReserveId(item.id);
                                  setReserveForm({
                                    name: item.name,
                                    target_year: item.target_year,
                                    estimated_cost: item.estimated_cost,
                                    inflation_rate: item.inflation_rate,
                                    current_funding: item.current_funding,
                                    notes: item.notes ?? '',
                                  });
                                }}
                              >
                                Edit
                              </button>
                              <button
                                type="button"
                                className="text-rose-600"
                                onClick={() => handleDeleteReserve(item.id)}
                              >
                                Delete
                              </button>
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {canEdit && detail.status !== 'APPROVED' && (
                  <form className="mt-4 grid gap-3 md:grid-cols-2" onSubmit={handleReserveSubmit}>
                    <label className="text-sm">
                      <span className="text-xs text-slate-500">Name</span>
                      <input
                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                        value={reserveForm.name}
                        onChange={(event) => setReserveForm((prev) => ({ ...prev, name: event.target.value }))}
                        required
                      />
                    </label>
                    <label className="text-sm">
                      <span className="text-xs text-slate-500">Target Year</span>
                      <input
                        type="number"
                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                        value={reserveForm.target_year}
                        onChange={(event) => setReserveForm((prev) => ({ ...prev, target_year: Number(event.target.value) }))}
                        required
                      />
                    </label>
                    <label className="text-sm">
                      <span className="text-xs text-slate-500">Estimated Cost</span>
                      <input
                        type="number"
                        step="0.01"
                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                        value={reserveForm.estimated_cost}
                        onChange={(event) => setReserveForm((prev) => ({ ...prev, estimated_cost: event.target.value }))}
                        required
                      />
                    </label>
                    <label className="text-sm">
                      <span className="text-xs text-slate-500">Inflation Rate</span>
                      <input
                        type="number"
                        step="0.01"
                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                        value={reserveForm.inflation_rate}
                        onChange={(event) => setReserveForm((prev) => ({ ...prev, inflation_rate: Number(event.target.value) }))}
                      />
                    </label>
                    <label className="text-sm">
                      <span className="text-xs text-slate-500">Current Funding</span>
                      <input
                        type="number"
                        step="0.01"
                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                        value={reserveForm.current_funding}
                        onChange={(event) => setReserveForm((prev) => ({ ...prev, current_funding: event.target.value }))}
                      />
                    </label>
                    <label className="text-sm md:col-span-2">
                      <span className="text-xs text-slate-500">Notes</span>
                      <textarea
                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                        rows={2}
                        value={reserveForm.notes}
                        onChange={(event) => setReserveForm((prev) => ({ ...prev, notes: event.target.value }))}
                      />
                    </label>
                    <div className="md:col-span-2 flex gap-2">
                      <button
                        type="submit"
                        className="rounded bg-primary-600 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white hover:bg-primary-500"
                      >
                        {editingReserveId ? 'Update reserve' : 'Add reserve'}
                      </button>
                      {editingReserveId && (
                        <button
                          type="button"
                          className="rounded border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-600"
                          onClick={() => {
                            setEditingReserveId(null);
                            setReserveForm(emptyReserveForm);
                          }}
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </form>
                )}
              </section>

              <section className="rounded border border-slate-200 p-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-semibold text-slate-600">Reserve Study & Documents</h4>
                  {canEdit && detail.status !== 'APPROVED' && (
                    <label className="text-xs font-semibold text-primary-600">
                      {attachmentUploading ? 'Uploading…' : 'Upload PDF'}
                      <input type="file" className="hidden" onChange={handleAttachmentUpload} disabled={attachmentUploading} />
                    </label>
                  )}
                </div>
                {detail.attachments.length === 0 ? (
                  <p className="mt-2 text-sm text-slate-500">No attachments available.</p>
                ) : (
                  <ul className="mt-3 space-y-2 text-sm">
                    {detail.attachments.map((attachment) => (
                      <li key={attachment.id} className="flex items-center justify-between rounded border border-slate-200 px-3 py-2">
                        <div>
                          <a
                            href={attachment.stored_path}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-semibold text-primary-600"
                          >
                            {attachment.file_name}
                          </a>
                          <p className="text-xs text-slate-500">
                            Uploaded {new Date(attachment.uploaded_at).toLocaleString()}
                          </p>
                        </div>
                        {canEdit && detail.status !== 'APPROVED' && (
                          <button
                            type="button"
                            className="text-xs text-rose-600"
                            onClick={() => handleDeleteAttachment(attachment)}
                          >
                            Delete
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          ) : (
            <div className="rounded border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
              Select a budget to view details.
            </div>
          )}
        </div>
      </section>
    </div>
  );
};

export default BudgetPage;
