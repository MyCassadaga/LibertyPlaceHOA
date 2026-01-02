import React, { useCallback, useEffect, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import { createPaymentSession } from '../services/api';
import {
  useAutopayCancelMutation,
  useAutopayQuery,
  useAutopayUpsertMutation,
  useBillingSummaryQuery,
  useContactOverdueMutation,
  useForwardToAttorneyMutation,
  useInvoicesQuery,
  useMyOwnerQuery,
  useOverdueAccountsQuery,
  useOwnersQuery,
} from '../features/billing/hooks';
import { API_BASE_URL } from '../lib/api/client';
import { AutopayAmountType, OverdueAccount } from '../types';
import { userHasAnyRole } from '../utils/roles';

type ActionMode = 'contact' | 'forward';

interface ActionPanelState {
  mode: ActionMode;
  account: OverdueAccount;
}

const BillingPage: React.FC = () => {
  const { user } = useAuth();
  const [payingInvoiceId, setPayingInvoiceId] = useState<number | null>(null);
  const [paymentError, setPaymentError] = useState<string | null>(null);
  const [actionPanel, setActionPanel] = useState<ActionPanelState | null>(null);
  const [actionMessage, setActionMessage] = useState('');
  const [actionBusy, setActionBusy] = useState(false);
  const [actionStatus, setActionStatus] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionLink, setActionLink] = useState<string | null>(null);
  const [autopayError, setAutopayError] = useState<string | null>(null);
  const [autopayStatus, setAutopayStatus] = useState<string | null>(null);
  const [autopayForm, setAutopayForm] = useState<{ payment_day: number; amount_type: AutopayAmountType; fixed_amount: string }>({
    payment_day: 1,
    amount_type: 'STATEMENT_BALANCE',
    fixed_amount: '',
  });

  const boardBillingRoles = useMemo(() => ['BOARD', 'TREASURER', 'SYSADMIN'], []);
  const elevatedSummaryRoles = useMemo(
    () => ['BOARD', 'TREASURER', 'SECRETARY', 'SYSADMIN', 'AUDITOR', 'ATTORNEY'],
    [],
  );
  const isBoardBillingUser = useMemo(() => userHasAnyRole(user, boardBillingRoles), [user, boardBillingRoles]);
  const canViewHomeownerCount = useMemo(
    () => userHasAnyRole(user, elevatedSummaryRoles),
    [user, elevatedSummaryRoles],
  );
  const isHomeownerUser = useMemo(() => userHasAnyRole(user, ['HOMEOWNER']), [user]);

  const invoicesQuery = useInvoicesQuery(!!user && isHomeownerUser);
  const summaryQuery = useBillingSummaryQuery(isBoardBillingUser);
  const ownersQuery = useOwnersQuery(isBoardBillingUser);
  const myOwnerQuery = useMyOwnerQuery(!!user && isHomeownerUser);
  const overdueQuery = useOverdueAccountsQuery(isBoardBillingUser);
  const autopayQuery = useAutopayQuery(!!user && isHomeownerUser);

  const autopayUpsert = useAutopayUpsertMutation();
  const autopayCancel = useAutopayCancelMutation();
  const contactOverdueMutation = useContactOverdueMutation();
  const forwardToAttorneyMutation = useForwardToAttorneyMutation();

  const invoices = invoicesQuery.data ?? [];
  const summary = summaryQuery.data ?? null;
  const overdueAccounts = overdueQuery.data ?? [];
  const autopay = autopayQuery.data ?? null;

  const ownerAddresses = useMemo(() => {
    const map: Record<number, string> = {};
    ownersQuery.data?.forEach((owner) => {
      if (owner.property_address) {
        map[owner.id] = owner.property_address;
      }
    });
    if (myOwnerQuery.data?.property_address) {
      map[myOwnerQuery.data.id] = myOwnerQuery.data.property_address;
    }
    return map;
  }, [ownersQuery.data, myOwnerQuery.data]);

  const pageLoading =
    invoicesQuery.isLoading ||
    summaryQuery.isLoading || ownersQuery.isLoading || overdueQuery.isLoading || myOwnerQuery.isLoading || autopayQuery.isLoading;

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

  const refreshOverdue = overdueQuery.refetch;
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

  const handlePayInvoice = async (invoiceId: number) => {
    setPaymentError(null);
    setPayingInvoiceId(invoiceId);
    try {
      const { checkoutUrl } = await createPaymentSession(invoiceId);
      window.location.href = checkoutUrl;
    } catch (err) {
      console.error('Unable to start payment session.', err);
      setPaymentError('Unable to start payment session. Please try again.');
    } finally {
      setPayingInvoiceId(null);
    }
  };

  const handleAutopaySubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setAutopayError(null);
    setAutopayStatus(null);
    try {
      const payload = {
        payment_day: autopayForm.payment_day,
        amount_type: autopayForm.amount_type,
        fixed_amount: autopayForm.amount_type === 'FIXED' ? autopayForm.fixed_amount || '0' : undefined,
      };
      await autopayUpsert.mutateAsync(payload);
      setAutopayStatus('Autopay preferences saved.');
    } catch {
      setAutopayError('Unable to save autopay preferences.');
    }
  };

  const handleAutopayCancel = async () => {
    if (!window.confirm('Cancel autopay enrollment?')) return;
    try {
      await autopayCancel.mutateAsync();
      setAutopayStatus('Autopay canceled.');
    } catch {
      setAutopayError('Unable to cancel autopay at this time.');
    }
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
        await contactOverdueMutation.mutateAsync({ ownerId: actionPanel.account.owner_id, message: payload });
        setActionStatus('Message sent to linked homeowner accounts.');
      } else {
        const response = await forwardToAttorneyMutation.mutateAsync({
          ownerId: actionPanel.account.owner_id,
          notes: payload,
        });
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
      {isBoardBillingUser && (
        <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <p className="font-semibold">Vendor payments moved</p>
          <p className="mt-1">
            Draft and track vendor payouts on the <span className="font-semibold">Contracts</span> page now. This Billing page
            focuses on homeowner assessments, overdue accounts, and autopay.
          </p>
        </div>
      )}
      {pageLoading && <p className="text-sm text-slate-500">Loading billing data…</p>}
      {summary && (
        <div className="rounded border border-slate-200 p-4">
          <h3 className="mb-2 text-lg font-semibold text-slate-700">Summary</h3>
          <div className={`grid grid-cols-1 gap-4 text-sm ${canViewHomeownerCount ? 'sm:grid-cols-3' : 'sm:grid-cols-2'}`}>
            <div>
              <p className="text-slate-500">Total Balance</p>
              <p className="text-lg font-semibold text-primary-600">{formatCurrency(summary.total_balance)}</p>
            </div>
            <div>
              <p className="text-slate-500">Open invoices</p>
              <p className="text-lg font-semibold">{summary.open_invoices}</p>
            </div>
            {canViewHomeownerCount && (
              <div>
                <p className="text-slate-500">Homeowners</p>
                <p className="text-lg font-semibold">{summary.owner_count}</p>
              </div>
            )}
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
          {autopayStatus && <p className="mt-2 text-sm text-emerald-600">{autopayStatus}</p>}
          {autopayQuery.isError && <p className="mt-2 text-sm text-red-600">Unable to load autopay status.</p>}
          {autopayError && <p className="mt-2 text-sm text-red-600">{autopayError}</p>}
          {autopayQuery.isLoading ? (
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
                  disabled={autopayUpsert.isLoading}
                >
                  {autopayUpsert.isLoading ? 'Saving…' : 'Save Autopay'}
                </button>
                {autopay && autopay.status !== 'NOT_ENROLLED' && (
                  <button
                    type="button"
                    className="ml-3 rounded border border-slate-300 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-600 hover:bg-slate-50 disabled:opacity-60"
                    onClick={handleAutopayCancel}
                    disabled={autopayCancel.isLoading}
                  >
                    {autopayCancel.isLoading ? 'Cancelling…' : 'Cancel Autopay'}
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
              disabled={overdueQuery.isFetching}
            >
              {overdueQuery.isFetching ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>
          {overdueQuery.isError && <p className="mt-3 text-sm text-red-600">Unable to load overdue accounts.</p>}
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
          ) : overdueQuery.isLoading ? (
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
      <div className="rounded border border-slate-200">
        {paymentError && <p className="px-3 pt-3 text-sm text-red-600">{paymentError}</p>}
        <div className="overflow-x-auto">
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
        </div>
        {invoices.length === 0 && !pageLoading && (
          <p className="px-3 py-4 text-sm text-slate-500">No invoices available.</p>
        )}
      </div>
    </div>
  );
};

export default BillingPage;
