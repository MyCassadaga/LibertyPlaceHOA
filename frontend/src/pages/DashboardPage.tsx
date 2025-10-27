import React, { useEffect, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import { fetchBillingSummary, fetchInvoices } from '../services/api';
import { BillingSummary, Invoice } from '../types';

const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [summary, setSummary] = useState<BillingSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      if (!user) return;
      setLoading(true);
      try {
        if (user.role.name === 'HOMEOWNER') {
          const data = await fetchInvoices();
          setInvoices(data);
        }
        if (["BOARD", "TREASURER"].includes(user.role.name)) {
          const data = await fetchBillingSummary();
          setSummary(data);
        }
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [user]);

  if (!user) {
    return null;
  }

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-xl font-semibold text-primary-600">Welcome back, {user.full_name || user.email}</h2>
        <p className="text-sm text-slate-500">Role: {user.role.name}</p>
      </header>

      {loading && <p className="text-sm text-slate-500">Loading dashboard data…</p>}

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

      {user.role.name === 'HOMEOWNER' && (
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
