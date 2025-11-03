import React, { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import { fetchBillingSummary, fetchDashboardReminders, fetchInvoices } from '../services/api';
import { BillingSummary, Invoice, Reminder } from '../types';
import { formatUserRoles, userHasAnyRole, userHasRole } from '../utils/roles';

const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [summary, setSummary] = useState<BillingSummary | null>(null);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [remindersError, setRemindersError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      if (!user) return;
      setLoading(true);
      try {
        if (userHasRole(user, 'HOMEOWNER')) {
          const data = await fetchInvoices();
          setInvoices(data);
        }
        if (userHasAnyRole(user, ['BOARD', 'TREASURER', 'SYSADMIN', 'SECRETARY'])) {
          try {
            const data = await fetchBillingSummary();
            setSummary(data);
          } catch (err) {
            setSummary(null);
          }
          try {
            const reminderData = await fetchDashboardReminders();
            setReminders(reminderData);
            setRemindersError(null);
          } catch (err) {
            setReminders([]);
            setRemindersError('Unable to load renewal reminders.');
          }
        }
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [user]);

  const isBoardUser = useMemo(() => !!user && userHasAnyRole(user, ['BOARD', 'TREASURER', 'SYSADMIN', 'SECRETARY']), [user]);

  if (!user) {
    return null;
  }

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-xl font-semibold text-primary-600">Welcome back, {user.full_name || user.email}</h2>
        <p className="text-sm text-slate-500">Roles: {formatUserRoles(user)}</p>
      </header>

      {loading && <p className="text-sm text-slate-500">Loading dashboard data…</p>}

      {isBoardUser && (
        <section className="rounded border border-slate-200 p-4">
          <h3 className="mb-3 text-lg font-semibold text-slate-700">Contract Renewal Reminders</h3>
          {remindersError && <p className="text-sm text-red-600">{remindersError}</p>}
          {!remindersError && reminders.length === 0 && (
            <p className="text-sm text-slate-500">No contract renewals require attention in the next 30 days.</p>
          )}
          {reminders.length > 0 && (
            <ul className="space-y-3 text-sm">
              {reminders.map((reminder) => {
                const dueDate = reminder.due_date ? new Date(reminder.due_date) : null;
                const vendorName =
                  reminder.context && typeof reminder.context['vendor_name'] === 'string'
                    ? (reminder.context['vendor_name'] as string)
                    : undefined;
                const serviceType =
                  reminder.context && typeof reminder.context['service_type'] === 'string'
                    ? (reminder.context['service_type'] as string)
                    : undefined;
                const formattedDue = dueDate ? dueDate.toLocaleDateString() : 'No deadline';
                const daysRemaining =
                  dueDate != null
                    ? Math.max(0, Math.ceil((dueDate.getTime() - Date.now()) / (1000 * 60 * 60 * 24)))
                    : null;
                return (
                  <li key={reminder.id} className="rounded border border-slate-200 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h4 className="font-semibold text-slate-700">
                        {reminder.title}
                        {serviceType ? <span className="ml-2 text-xs uppercase text-slate-400">{serviceType}</span> : null}
                      </h4>
                      <span className="text-xs font-medium text-primary-600">
                        Due: {formattedDue}
                        {daysRemaining != null ? ` • ${daysRemaining} day${daysRemaining === 1 ? '' : 's'} remaining` : ''}
                      </span>
                    </div>
                    {reminder.description && (
                      <p className="mt-2 whitespace-pre-wrap text-slate-600">{reminder.description}</p>
                    )}
                    <p className="mt-2 text-xs text-slate-500">
                      Vendor: {vendorName ?? 'Unknown'} • Created on {new Date(reminder.created_at).toLocaleString()}
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}

      {summary && (
        <section className="rounded border border-slate-200 p-4">
          <h3 className="mb-3 text-lg font-semibold text-slate-700">Accounts Receivable</h3>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <dt className="text-xs uppercase text-slate-500">Total Balance</dt>
              <dd className="text-lg font-semibold text-primary-600">${Number(summary.total_balance).toFixed(2)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-slate-500">Open Invoices</dt>
              <dd className="text-lg font-semibold">{summary.open_invoices}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-slate-500">Homeowners</dt>
              <dd className="text-lg font-semibold">{summary.owner_count}</dd>
            </div>
          </dl>
        </section>
      )}

      {userHasRole(user, 'HOMEOWNER') && (
        <section className="rounded border border-slate-200 p-4">
          <h3 className="mb-3 text-lg font-semibold text-slate-700">Your Invoices</h3>
          {invoices.length === 0 ? (
            <p className="text-sm text-slate-500">No invoices at this time.</p>
          ) : (
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Invoice</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Amount</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Due Date</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {invoices.map((invoice) => (
                  <tr key={invoice.id}>
                    <td className="px-3 py-2">#{invoice.id}</td>
                    <td className="px-3 py-2">${Number(invoice.amount).toFixed(2)}</td>
                    <td className="px-3 py-2">{new Date(invoice.due_date).toLocaleDateString()}</td>
                    <td className="px-3 py-2">{invoice.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </div>
  );
};

export default DashboardPage;
