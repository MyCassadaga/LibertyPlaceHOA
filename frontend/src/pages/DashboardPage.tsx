import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { useAuth } from '../hooks/useAuth';
import { fetchBillingSummary, fetchDashboardReminders, fetchInvoices } from '../services/api';
import { BillingSummary, ElectionListItem, Invoice, Reminder } from '../types';
import { queryKeys } from '../lib/api/queryKeys';
import { formatUserRoles, userHasAnyRole, userHasRole } from '../utils/roles';
import FullPageSpinner from '../components/feedback/FullPageSpinner';
import { useElectionsQuery } from '../features/elections/hooks';

const DashboardPage: React.FC = () => {
  const { user } = useAuth();

  const isBoardUser = useMemo(
    () => !!user && userHasAnyRole(user, ['BOARD', 'TREASURER', 'SYSADMIN', 'SECRETARY']),
    [user],
  );

  const invoicesQuery = useQuery<Invoice[]>({
    queryKey: queryKeys.invoices,
    queryFn: fetchInvoices,
    enabled: !!user && userHasRole(user, 'HOMEOWNER'),
  });

  const summaryQuery = useQuery<BillingSummary>({
    queryKey: queryKeys.billingSummary,
    queryFn: fetchBillingSummary,
    enabled: isBoardUser,
  });

  const remindersQuery = useQuery<Reminder[]>({
    queryKey: queryKeys.contractReminders,
    queryFn: fetchDashboardReminders,
    enabled: isBoardUser,
  });

  const electionsQuery = useElectionsQuery({ enabled: isBoardUser });

  const upcomingElections = useMemo<ElectionListItem[]>(() => {
    if (!electionsQuery.data) {
      return [];
    }
    return electionsQuery.data.filter((election) => ['OPEN', 'SCHEDULED', 'DRAFT'].includes(election.status));
  }, [electionsQuery.data]);

  const openElectionCount = useMemo(() => {
    if (!electionsQuery.data) return 0;
    return electionsQuery.data.filter((election) => election.status === 'OPEN').length;
  }, [electionsQuery.data]);

  const remindersTimestamp = remindersQuery.dataUpdatedAt || null;

  const loading = invoicesQuery.isLoading || summaryQuery.isLoading || remindersQuery.isLoading;

  if (!user) {
    return null;
  }

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-xl font-semibold text-primary-600">Welcome back, {user.full_name || user.email}</h2>
        <p className="text-sm text-slate-500">Roles: {formatUserRoles(user)}</p>
      </header>

      {loading && <FullPageSpinner label="Loading dashboard…" className="min-h-[120px]" />}

      {isBoardUser && (
        <section className="rounded border border-slate-200 p-4">
          <h3 className="mb-3 text-lg font-semibold text-slate-700">Contract Renewal Reminders</h3>
          {remindersQuery.isError && <p className="text-sm text-red-600">Unable to load renewal reminders.</p>}
          {!remindersQuery.isError && (remindersQuery.data ?? []).length === 0 && (
            <p className="text-sm text-slate-500">No contract renewals require attention in the next 30 days.</p>
          )}
          {(remindersQuery.data ?? []).length > 0 && (
            <ul className="space-y-3 text-sm">
              {remindersQuery.data?.map((reminder) => {
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
                  dueDate != null && remindersTimestamp
                    ? Math.max(0, Math.ceil((dueDate.getTime() - remindersTimestamp) / (1000 * 60 * 60 * 24)))
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

      {isBoardUser && (
        <section className="rounded border border-slate-200 p-4">
          <h3 className="mb-3 text-lg font-semibold text-slate-700">Election Snapshot</h3>
          {electionsQuery.isError && <p className="text-sm text-red-600">Unable to load elections.</p>}
          {!electionsQuery.isError && electionsQuery.isLoading && (
            <p className="text-sm text-slate-500">Loading election data…</p>
          )}
          {!electionsQuery.isError && !electionsQuery.isLoading && (
            <>
              <div className="mb-4 grid gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-xs uppercase text-slate-500">Open Elections</p>
                  <p className="text-2xl font-semibold text-primary-600">{openElectionCount}</p>
                </div>
                <div>
                  <p className="text-xs uppercase text-slate-500">Ballots Issued</p>
                  <p className="text-2xl font-semibold text-primary-600">
                    {upcomingElections.reduce((sum, election) => sum + election.ballot_count, 0)}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase text-slate-500">Votes Recorded</p>
                  <p className="text-2xl font-semibold text-primary-600">
                    {upcomingElections.reduce((sum, election) => sum + election.votes_cast, 0)}
                  </p>
                </div>
              </div>
              {upcomingElections.length === 0 ? (
                <p className="text-sm text-slate-500">No active or scheduled elections.</p>
              ) : (
                <ul className="space-y-3 text-sm">
                  {upcomingElections.slice(0, 3).map((election) => (
                    <li key={election.id} className="rounded border border-slate-200 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <p className="font-semibold text-slate-700">{election.title}</p>
                          <p className="text-xs uppercase text-slate-400">{election.status}</p>
                        </div>
                        <span className="text-xs text-slate-500">
                          Opens {election.opens_at ? new Date(election.opens_at).toLocaleDateString() : 'TBD'}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-slate-500">
                        Votes: {election.votes_cast} / {election.ballot_count} ballots issued
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>
      )}

      {summaryQuery.data && (
        <section className="rounded border border-slate-200 p-4">
          <h3 className="mb-3 text-lg font-semibold text-slate-700">Accounts Receivable</h3>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <dt className="text-xs uppercase text-slate-500">Total Balance</dt>
              <dd className="text-lg font-semibold text-primary-600">
                ${Number(summaryQuery.data.total_balance).toFixed(2)}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-slate-500">Open Invoices</dt>
              <dd className="text-lg font-semibold">{summaryQuery.data.open_invoices}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-slate-500">Homeowners</dt>
              <dd className="text-lg font-semibold">{summaryQuery.data.owner_count}</dd>
            </div>
          </dl>
        </section>
      )}

      {userHasRole(user, 'HOMEOWNER') && (
        <section className="rounded border border-slate-200 p-4">
          <h3 className="mb-3 text-lg font-semibold text-slate-700">Your Invoices</h3>
          {(invoicesQuery.data ?? []).length === 0 ? (
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
                {invoicesQuery.data?.map((invoice) => (
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
