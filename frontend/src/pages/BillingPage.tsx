import React, { useCallback, useEffect, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import {
  API_BASE_URL,
  cancelAutopay,
  contactOverdueOwner,
  createPaymentSession,
  createVendorPaymentRequest,
  fetchAutopayEnrollment,
  fetchBillingSummary,
  fetchContracts,
  fetchInvoices,
  fetchMyOwnerRecord,
  fetchOverdueAccounts,
  fetchOwners,
  fetchVendorPayments,
  forwardOverdueToAttorney,
  markVendorPaymentPaid,
  sendVendorPayment,
  upsertAutopayEnrollment,
} from '../services/api';
import {
  AutopayEnrollment,
  AutopayAmountType,
  BillingSummary,
  Contract,
  Invoice,
  OverdueAccount,
  Owner,
  VendorPayment,
} from '../types';
import { userHasAnyRole } from '../utils/roles';

type ActionMode = 'contact' | 'forward';

interface ActionPanelState {
  mode: ActionMode;
  account: OverdueAccount;
}

const BillingPage: React.FC = () => {
  const { user } = useAuth();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [summary, setSummary] = useState<BillingSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [ownerAddresses, setOwnerAddresses] = useState<Record<number, string>>({});
  const [payingInvoiceId, setPayingInvoiceId] = useState<number | null>(null);
  const [paymentError, setPaymentError] = useState<string | null>(null);
  const [overdueAccounts, setOverdueAccounts] = useState<OverdueAccount[]>([]);
  const [overdueLoading, setOverdueLoading] = useState(false);
  const [overdueError, setOverdueError] = useState<string | null>(null);
  const [actionPanel, setActionPanel] = useState<ActionPanelState | null>(null);
  const [actionMessage, setActionMessage] = useState('');
  const [actionBusy, setActionBusy] = useState(false);
  const [actionStatus, setActionStatus] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionLink, setActionLink] = useState<string | null>(null);
  const [autopay, setAutopay] = useState<AutopayEnrollment | null>(null);
  const [autopayLoading, setAutopayLoading] = useState(false);
  const [autopaySaving, setAutopaySaving] = useState(false);
  const [autopayError, setAutopayError] = useState<string | null>(null);
  const [autopayForm, setAutopayForm] = useState<{ payment_day: number; amount_type: AutopayAmountType; fixed_amount: string }>({
    payment_day: 1,
    amount_type: 'STATEMENT_BALANCE',
    fixed_amount: '',
  });
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [vendorPayments, setVendorPayments] = useState<VendorPayment[]>([]);
  const [vendorForm, setVendorForm] = useState<{ contractId: string; vendorName: string; amount: string; memo: string }>({
    contractId: '',
    vendorName: '',
    amount: '',
    memo: '',
  });
  const [vendorBusy, setVendorBusy] = useState(false);
  const [vendorStatus, setVendorStatus] = useState<string | null>(null);
  const [vendorError, setVendorError] = useState<string | null>(null);
  const [vendorLoading, setVendorLoading] = useState(false);

  const boardBillingRoles = useMemo(() => ['BOARD', 'TREASURER', 'SYSADMIN'], []);
  const isBoardBillingUser = useMemo(() => userHasAnyRole(user, boardBillingRoles), [user, boardBillingRoles]);
  const isHomeownerUser = useMemo(() => userHasAnyRole(user, ['HOMEOWNER']), [user]);

  const formatCurrency = useCallback((value: string | number) => {
    const parsedRaw = typeof value === 'string' ? Number(value) : value;
    const parsed = Number.isFinite(parsedRaw) ? parsedRaw : 0;
    return parsed.toLocaleString(undefined, { style: 'currency', currency: 'USD' });
  }, []);

  const toAbsoluteUrl = useCallback((url: string) => {
    if (!url) return '';
    const base = API_BASE_URL.replace(/\/$/, '');
    const normalized = url.startsWith('/') ? url : `/${url}`;
    return `${base}${normalized}`;
  }, []);

  const refreshOverdue = useCallback(async () => {
    if (!isBoardBillingUser) {
      setOverdueAccounts([]);
      setOverdueLoading(false);
      return;
    }
    setOverdueLoading(true);
    setOverdueError(null);
    try {
      const data = await fetchOverdueAccounts();
      setOverdueAccounts(data);
    } catch {
      setOverdueError('Unable to load overdue accounts.');
    } finally {
      setOverdueLoading(false);
    }
  }, [isBoardBillingUser]);

  const refreshVendorPayments = useCallback(async () => {
    if (!isBoardBillingUser) {
      setVendorPayments([]);
      setVendorLoading(false);
      return;
    }
    setVendorLoading(true);
    setVendorError(null);
    try {
      const data = await fetchVendorPayments();
      setVendorPayments(data);
    } catch {
      setVendorError('Unable to load vendor payments.');
    } finally {
      setVendorLoading(false);
    }
  }, [isBoardBillingUser]);

  const loadAutopay = useCallback(async () => {
    if (!isHomeownerUser) {
      setAutopay(null);
      setAutopayLoading(false);
      return;
    }
    setAutopayLoading(true);
    setAutopayError(null);
    try {
      const data = await fetchAutopayEnrollment();
      setAutopay(data);
    } catch {
      setAutopay(null);
      setAutopayError('Unable to load autopay status.');
    } finally {
      setAutopayLoading(false);
    }
  }, [isHomeownerUser]);

  useEffect(() => {
    if (!isBoardBillingUser) {
      setActionPanel(null);
      setActionMessage('');
      setActionStatus(null);
      setActionError(null);
      setActionLink(null);
    }
  }, [isBoardBillingUser]);

  useEffect(() => {
    const load = async () => {
      if (!user) return;
      setLoading(true);
      try {
        const invoiceData = await fetchInvoices();
        setInvoices(invoiceData);

        const addressMap: Record<number, string> = {};
        if (isBoardBillingUser) {
          try {
            const [summaryData, owners, contractRows] = await Promise.all([
              fetchBillingSummary(),
              fetchOwners(),
              fetchContracts(),
            ]);
            setSummary(summaryData);
            setContracts(contractRows);
            owners.forEach((owner: Owner) => {
              if (owner.property_address) {
                addressMap[owner.id] = owner.property_address;
              }
            });
          } catch {
            setSummary(null);
            setContracts([]);
          }
          await refreshOverdue();
          await refreshVendorPayments();
        } else {
          setSummary(null);
          setContracts([]);
          setOverdueAccounts([]);
          setOverdueError(null);
          setVendorPayments([]);
          setVendorError(null);
          try {
            const myOwner = await fetchMyOwnerRecord();
            if (myOwner.property_address) {
              addressMap[myOwner.id] = myOwner.property_address;
            }
          } catch {
            // ignore if homeowner record not available
          }
        }
        setOwnerAddresses(addressMap);
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [user, isBoardBillingUser, refreshOverdue, refreshVendorPayments]);

  useEffect(() => {
    void loadAutopay();
  }, [loadAutopay]);

  useEffect(() => {
    if (!autopay) {
      setAutopayForm({ payment_day: 1, amount_type: 'STATEMENT_BALANCE', fixed_amount: '' });
      return;
    }
    setAutopayForm({
      payment_day: autopay.payment_day ?? 1,
      amount_type: (autopay.amount_type ?? 'STATEMENT_BALANCE') as AutopayAmountType,
      fixed_amount: autopay.fixed_amount ?? '',
    });
  }, [autopay]);

  const handlePayInvoice = async (invoiceId: number) => {
    setPaymentError(null);
    setPayingInvoiceId(invoiceId);
    try {
      const { checkoutUrl } = await createPaymentSession(invoiceId);
      window.location.href = checkoutUrl;
    } catch (err) {
      setPaymentError('Unable to start payment session. Please try again.');
    } finally {
      setPayingInvoiceId(null);
    }
  };

  const handleAutopaySubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setAutopayError(null);
    setAutopaySaving(true);
    try {
      const payload = {
        payment_day: autopayForm.payment_day,
        amount_type: autopayForm.amount_type,
        fixed_amount: autopayForm.amount_type === 'FIXED' ? autopayForm.fixed_amount || '0' : undefined,
      };
      const result = await upsertAutopayEnrollment(payload);
      setAutopay(result);
      setStatusMessage('Autopay preferences saved.');
    } catch {
      setAutopayError('Unable to save autopay preferences.');
    } finally {
      setAutopaySaving(false);
    }
  };

  const handleAutopayCancel = async () => {
    if (!window.confirm('Cancel autopay enrollment?')) return;
    try {
      const result = await cancelAutopay();
      setAutopay(result);
      setStatusMessage('Autopay canceled.');
    } catch {
      setAutopayError('Unable to cancel autopay at this time.');
    }
  };

  const handleVendorFormChange = (field: keyof typeof vendorForm, value: string) => {
    setVendorForm((prev) => {
      if (field === 'contractId') {
        const selected = contracts.find((contract) => contract.id === Number(value));
        return {
          ...prev,
          contractId: value,
          vendorName: selected ? selected.vendor_name : prev.vendorName,
        };
      }
      return { ...prev, [field]: value };
    });
  };

  const handleCreateVendorPayment = async (event: React.FormEvent) => {
    event.preventDefault();
    setVendorBusy(true);
    setVendorStatus(null);
    setVendorError(null);
    try {
      const payload: {
        contract_id?: number | null;
        vendor_name?: string;
        amount: string;
        memo?: string;
      } = {
        amount: vendorForm.amount,
      };
      if (vendorForm.contractId) {
        payload.contract_id = Number(vendorForm.contractId);
      }
      if (vendorForm.vendorName.trim()) {
        payload.vendor_name = vendorForm.vendorName.trim();
      }
      if (vendorForm.memo.trim()) {
        payload.memo = vendorForm.memo.trim();
      }
      const record = await createVendorPaymentRequest(payload);
      setVendorStatus(`Drafted payment for ${record.vendor_name}.`);
      setVendorForm({ contractId: '', vendorName: '', amount: '', memo: '' });
      await refreshVendorPayments();
    } catch {
      setVendorError('Unable to create vendor payment.');
    } finally {
      setVendorBusy(false);
    }
  };

  const handleSendVendorPayment = async (paymentId: number) => {
    setVendorStatus(null);
    setVendorError(null);
    try {
      await sendVendorPayment(paymentId);
      setVendorStatus('Vendor payment submitted to Stripe (stub).');
      await refreshVendorPayments();
    } catch {
      setVendorError('Unable to submit vendor payment.');
    }
  };

  const handleMarkVendorPaid = async (paymentId: number) => {
    setVendorStatus(null);
    setVendorError(null);
    try {
      await markVendorPaymentPaid(paymentId);
      setVendorStatus('Vendor payment marked as paid.');
      await refreshVendorPayments();
    } catch {
      setVendorError('Unable to update vendor payment.');
    }
  };

  if (!user) return null;

  const describeMonths = (months: number) => {
    if (months <= 0) return '<1 month';
    return `${months} month${months === 1 ? '' : 's'}`;
  };

  const getLongestDaysOverdue = (account: OverdueAccount) =>
    account.invoices.reduce((max, invoice) => Math.max(max, invoice.days_overdue), 0);

  const formatReminderDate = (value?: string | null) => {
    if (!value) return 'Never';
    return new Date(value).toLocaleDateString();
  };

  const handleOpenContact = (account: OverdueAccount) => {
    const defaultMessage = `Hello ${account.owner_name}, your HOA account for ${
      account.property_address ?? 'your property'
    } is ${describeMonths(account.max_months_overdue)} past due with a balance of ${formatCurrency(
      account.total_due,
    )}. Please log in to the portal or contact the board within 10 days to avoid legal escalation.`;
    setActionPanel({ mode: 'contact', account });
    setActionMessage(defaultMessage);
    setActionStatus(null);
    setActionError(null);
    setActionLink(null);
  };

  const handleOpenForward = (account: OverdueAccount) => {
    const longestDays = getLongestDaysOverdue(account);
    const defaultNotes = `${account.owner_name} is ${describeMonths(account.max_months_overdue)} past due (${longestDays} days) with ${formatCurrency(
      account.total_due,
    )} outstanding.`;
    setActionPanel({ mode: 'forward', account });
    setActionMessage(defaultNotes);
    setActionStatus(null);
    setActionError(null);
    setActionLink(null);
  };

  const handleClosePanel = () => {
    setActionPanel(null);
    setActionMessage('');
    setActionStatus(null);
    setActionError(null);
    setActionLink(null);
  };

  const handleSubmitAction = async () => {
    if (!actionPanel) return;
    setActionBusy(true);
    setActionError(null);
    setActionStatus(null);
    setActionLink(null);
    try {
      const payload = actionMessage.trim() || undefined;
      if (actionPanel.mode === 'contact') {
        await contactOverdueOwner(actionPanel.account.owner_id, payload);
        setActionStatus('Message sent to linked homeowner accounts.');
      } else {
        const response = await forwardOverdueToAttorney(actionPanel.account.owner_id, payload);
        const absolute = toAbsoluteUrl(response.notice_url);
        setActionStatus('Attorney packet generated.');
        setActionLink(absolute);
      }
      await refreshOverdue();
    } catch {
      setActionError('Unable to complete the request. Please try again.');
    } finally {
      setActionBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-slate-700">Billing & Assessments</h2>
      </div>
      {loading && <p className="text-sm text-slate-500">Loading billing data…</p>}
      {summary && (
        <div className="rounded border border-slate-200 p-4">
          <h3 className="mb-2 text-lg font-semibold text-slate-700">Summary</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 text-sm">
            <div>
              <p className="text-slate-500">Total Balance</p>
              <p className="text-lg font-semibold text-primary-600">{formatCurrency(summary.total_balance)}</p>
            </div>
            <div>
              <p className="text-slate-500">Open invoices</p>
              <p className="text-lg font-semibold">{summary.open_invoices}</p>
            </div>
            <div>
              <p className="text-slate-500">Homeowners</p>
              <p className="text-lg font-semibold">{summary.owner_count}</p>
            </div>
          </div>
        </div>
      )}
      {isHomeownerUser && (
        <section className="rounded border border-slate-200 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-slate-700">Autopay Enrollment</h3>
              <p className="text-sm text-slate-500">Enroll once; Stripe will process charges once credentials are live.</p>
            </div>
            {autopay && (
              <span className="rounded-full border border-slate-200 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
                {autopay.status.replace(/_/g, ' ')}
              </span>
            )}
          </div>
          {autopayError && <p className="mt-2 text-sm text-red-600">{autopayError}</p>}
          {autopayLoading ? (
            <p className="mt-3 text-sm text-slate-500">Loading autopay status…</p>
          ) : (
            <form className="mt-4 grid gap-3 md:grid-cols-3" onSubmit={handleAutopaySubmit}>
              <label className="text-sm">
                <span className="text-xs uppercase text-slate-500">Draft day</span>
                <input
                  type="number"
                  min={1}
                  max={28}
                  className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                  value={autopayForm.payment_day}
                  onChange={(event) =>
                    setAutopayForm((prev) => ({ ...prev, payment_day: Number(event.target.value) }))
                  }
                />
              </label>
              <label className="text-sm">
                <span className="text-xs uppercase text-slate-500">Amount type</span>
                <select
                  className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                  value={autopayForm.amount_type}
                  onChange={(event) =>
                    setAutopayForm((prev) => ({ ...prev, amount_type: event.target.value as AutopayAmountType }))
                  }
                >
                  <option value="STATEMENT_BALANCE">Statement balance</option>
                  <option value="FIXED">Fixed amount</option>
                </select>
              </label>
              <label className="text-sm">
                <span className="text-xs uppercase text-slate-500">Fixed amount</span>
                <input
                  type="number"
                  step="0.01"
                  className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                  value={autopayForm.fixed_amount}
                  onChange={(event) => setAutopayForm((prev) => ({ ...prev, fixed_amount: event.target.value }))}
                  disabled={autopayForm.amount_type !== 'FIXED'}
                  placeholder="$0.00"
                />
              </label>
              <div className="text-sm md:col-span-3">
                <button
                  type="submit"
                  className="rounded bg-primary-600 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white hover:bg-primary-500 disabled:opacity-60"
                  disabled={autopaySaving}
                >
                  {autopaySaving ? 'Saving…' : 'Save Autopay'}
                </button>
                {autopay && autopay.status !== 'NOT_ENROLLED' && (
                  <button
                    type="button"
                    className="ml-3 rounded border border-slate-300 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-600 hover:bg-slate-50"
                    onClick={handleAutopayCancel}
                  >
                    Cancel Autopay
                  </button>
                )}
              </div>
            </form>
          )}
          {autopay && autopay.status !== 'NOT_ENROLLED' && autopay.provider_setup_required && (
            <p className="mt-3 text-xs text-amber-600">
              Enrollment saved — Stripe setup intents will appear automatically once real credentials are configured.
            </p>
          )}
        </section>
      )}
      {isBoardBillingUser && (
        <div className="rounded border border-slate-200 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-slate-700">Overdue Accounts</h3>
              <p className="text-sm text-slate-500">
                Longest aging and escalation tools for board / finance roles.
              </p>
            </div>
            <button
              type="button"
              className="rounded border border-slate-300 px-3 py-1 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-60"
              onClick={() => {
                void refreshOverdue();
              }}
              disabled={overdueLoading}
            >
              {overdueLoading ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>
          {overdueError && <p className="mt-3 text-sm text-red-600">{overdueError}</p>}
          {overdueAccounts.length > 0 ? (
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium text-slate-600">Owner</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-600">Property</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-600">Balance</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-600">Longest Aging</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-600">Last Reminder</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-600">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {overdueAccounts.map((account) => (
                    <tr key={account.owner_id}>
                      <td className="px-3 py-3">
                        <p className="font-medium text-slate-700">{account.owner_name}</p>
                        <p className="text-xs text-slate-500">
                          {account.primary_email ?? 'No email on file'}
                        </p>
                        {account.primary_phone && (
                          <p className="text-xs text-slate-500">{account.primary_phone}</p>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        <p>{account.property_address ?? 'Pending address'}</p>
                        <ul className="mt-1 space-y-1 text-xs text-slate-500">
                          {account.invoices.map((invoice) => (
                            <li key={invoice.id}>
                              #{invoice.id} · due {new Date(invoice.due_date).toLocaleDateString()} ·{' '}
                              {invoice.days_overdue}d overdue
                            </li>
                          ))}
                        </ul>
                      </td>
                      <td className="px-3 py-3 font-semibold text-slate-700">
                        {formatCurrency(account.total_due)}
                      </td>
                      <td className="px-3 py-3">
                        <p className="font-medium text-slate-700">
                          {describeMonths(account.max_months_overdue)}
                        </p>
                        <p className="text-xs text-slate-500">
                          {getLongestDaysOverdue(account)} day(s) overdue
                        </p>
                      </td>
                      <td className="px-3 py-3 text-sm text-slate-600">{formatReminderDate(account.last_reminder_sent_at)}</td>
                      <td className="px-3 py-3 space-y-2">
                        <button
                          type="button"
                          className="block w-full rounded bg-primary-50 px-3 py-1 text-xs font-semibold text-primary-700 hover:bg-primary-100"
                          onClick={() => handleOpenContact(account)}
                        >
                          Contact
                        </button>
                        <button
                          type="button"
                          className="block w-full rounded bg-rose-600 px-3 py-1 text-xs font-semibold text-white hover:bg-rose-500"
                          onClick={() => handleOpenForward(account)}
                        >
                          Forward to Attorney
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : overdueLoading ? (
            <p className="mt-4 text-sm text-slate-500">Loading overdue accounts…</p>
          ) : (
            <p className="mt-4 text-sm text-slate-500">All homeowner assessments are current.</p>
          )}

          {actionPanel && (
            <div className="mt-5 rounded border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-slate-700">
                    {actionPanel.mode === 'contact' ? 'Contact owner' : 'Generate attorney packet'}
                  </p>
                  <p className="text-xs text-slate-500">
                    {actionPanel.account.owner_name} · {actionPanel.account.property_address ?? 'Pending address'}
                  </p>
                </div>
                <button
                  type="button"
                  className="text-xs font-semibold text-slate-500 hover:text-slate-700"
                  onClick={handleClosePanel}
                >
                  Close
                </button>
              </div>
              <textarea
                className="mt-3 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
                rows={4}
                value={actionMessage}
                onChange={(event) => setActionMessage(event.target.value)}
                placeholder={actionPanel.mode === 'contact' ? 'Enter message to homeowner' : 'Optional notes for attorney packet'}
              />
              {actionError && <p className="mt-2 text-sm text-red-600">{actionError}</p>}
              {actionStatus && (
                <p className="mt-2 text-sm text-green-600">
                  {actionStatus}{' '}
                  {actionLink && (
                    <a
                      href={actionLink}
                      target="_blank"
                      rel="noreferrer"
                      className="underline"
                    >
                      View packet
                    </a>
                  )}
                </p>
              )}
              <div className="mt-3">
                <button
                  type="button"
                  className="rounded bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-500 disabled:opacity-60"
                  onClick={handleSubmitAction}
                  disabled={actionBusy}
                >
                  {actionBusy
                    ? 'Working…'
                    : actionPanel.mode === 'contact'
                    ? 'Send portal message'
                    : 'Generate packet'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      {isBoardBillingUser && (
        <section className="rounded border border-slate-200 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-slate-700">Vendor Payments</h3>
              <p className="text-sm text-slate-500">Draft payouts for contract vendors and track their status.</p>
            </div>
            {vendorStatus && <span className="text-xs text-emerald-600">{vendorStatus}</span>}
          </div>
          {vendorError && <p className="mt-2 text-sm text-red-600">{vendorError}</p>}
          <form className="mt-3 grid gap-3 md:grid-cols-4" onSubmit={handleCreateVendorPayment}>
            <label className="text-sm">
              <span className="text-xs uppercase text-slate-500">Contract</span>
              <select
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={vendorForm.contractId}
                onChange={(event) => handleVendorFormChange('contractId', event.target.value)}
              >
                <option value="">Select contract…</option>
                {contracts.map((contract) => (
                  <option key={contract.id} value={contract.id}>
                    {contract.vendor_name} ({contract.service_type ?? 'General'})
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="text-xs uppercase text-slate-500">Vendor</span>
              <input
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={vendorForm.vendorName}
                onChange={(event) => handleVendorFormChange('vendorName', event.target.value)}
                placeholder="ACME Landscaping"
                required={!vendorForm.contractId}
              />
            </label>
            <label className="text-sm">
              <span className="text-xs uppercase text-slate-500">Amount</span>
              <input
                type="number"
                step="0.01"
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={vendorForm.amount}
                onChange={(event) => handleVendorFormChange('amount', event.target.value)}
                required
              />
            </label>
            <label className="text-sm">
              <span className="text-xs uppercase text-slate-500">Memo</span>
              <input
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={vendorForm.memo}
                onChange={(event) => handleVendorFormChange('memo', event.target.value)}
                placeholder="Monthly retainer"
              />
            </label>
            <div className="md:col-span-4">
              <button
                type="submit"
                className="rounded bg-primary-600 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white hover:bg-primary-500 disabled:opacity-60"
                disabled={vendorBusy}
              >
                {vendorBusy ? 'Creating…' : 'Create payment request'}
              </button>
            </div>
          </form>
          <div className="mt-4 overflow-x-auto">
            {vendorLoading ? (
              <p className="text-sm text-slate-500">Loading vendor payments…</p>
            ) : (
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Vendor</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Amount</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Status</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Requested</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {vendorPayments.map((payment) => (
                    <tr key={payment.id}>
                      <td className="px-3 py-2">
                        <p className="font-semibold text-slate-700">{payment.vendor_name}</p>
                        {payment.memo && <p className="text-xs text-slate-500">{payment.memo}</p>}
                      </td>
                      <td className="px-3 py-2">{formatCurrency(payment.amount)}</td>
                      <td className="px-3 py-2 text-xs uppercase text-slate-500">{payment.status}</td>
                      <td className="px-3 py-2 text-xs text-slate-500">
                        {new Date(payment.requested_at).toLocaleDateString()}
                      </td>
                      <td className="px-3 py-2 space-x-2 text-right text-xs">
                        {['PENDING', 'FAILED'].includes(payment.status) && (
                          <button
                            type="button"
                            className="rounded bg-emerald-600 px-3 py-2 font-semibold text-white hover:bg-emerald-500"
                            onClick={() => handleSendVendorPayment(payment.id)}
                          >
                            Send via Stripe
                          </button>
                        )}
                        {payment.status === 'SUBMITTED' && (
                          <button
                            type="button"
                            className="rounded border border-slate-300 px-3 py-2 font-semibold text-slate-600 hover:bg-slate-50"
                            onClick={() => handleMarkVendorPaid(payment.id)}
                          >
                            Mark paid
                          </button>
                        )}
                        {payment.status === 'PAID' && (
                          <span className="text-slate-500">
                            Paid {payment.paid_at ? new Date(payment.paid_at).toLocaleDateString() : ''}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {!vendorPayments.length && (
                    <tr>
                      <td colSpan={5} className="px-3 py-4 text-center text-sm text-slate-500">
                        No vendor payouts yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
        </section>
      )}
      <div className="rounded border border-slate-200">
        {paymentError && <p className="px-3 pt-3 text-sm text-red-600">{paymentError}</p>}
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Invoice</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Property</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Amount</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Due</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Status</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {invoices.map((invoice) => (
              <tr key={invoice.id}>
                <td className="px-3 py-2">#{invoice.id}</td>
                <td className="px-3 py-2">{ownerAddresses[invoice.owner_id] ?? `Owner #${invoice.owner_id}`}</td>
                <td className="px-3 py-2">{formatCurrency(invoice.amount)}</td>
                <td className="px-3 py-2">{new Date(invoice.due_date).toLocaleDateString()}</td>
                <td className="px-3 py-2">{invoice.status}</td>
                <td className="px-3 py-2">
                  {invoice.status !== 'PAID' ? (
                    <button
                      type="button"
                      onClick={() => handlePayInvoice(invoice.id)}
                      className="rounded bg-primary-600 px-3 py-1 text-xs font-semibold text-white hover:bg-primary-500 disabled:opacity-60"
                      disabled={payingInvoiceId === invoice.id}
                    >
                      {payingInvoiceId === invoice.id ? 'Starting…' : 'Pay'}
                    </button>
                  ) : (
                    <span className="text-xs text-slate-400">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {invoices.length === 0 && !loading && (
          <p className="px-3 py-4 text-sm text-slate-500">No invoices available.</p>
        )}
      </div>
    </div>
  );
};

export default BillingPage;
