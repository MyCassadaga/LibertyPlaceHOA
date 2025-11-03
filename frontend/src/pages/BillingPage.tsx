import React, { useEffect, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import { fetchBillingSummary, fetchInvoices, fetchMyOwnerRecord, fetchOwners } from '../services/api';
import { BillingSummary, Invoice, Owner } from '../types';
import { userHasAnyRole } from '../utils/roles';

const BillingPage: React.FC = () => {
  const { user } = useAuth();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [summary, setSummary] = useState<BillingSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [ownerAddresses, setOwnerAddresses] = useState<Record<number, string>>({});

  useEffect(() => {
    const load = async () => {
      if (!user) return;
      setLoading(true);
      try {
        const invoiceData = await fetchInvoices();
        setInvoices(invoiceData);

        const addressMap: Record<number, string> = {};
        if (userHasAnyRole(user, ['BOARD', 'TREASURER', 'SYSADMIN'])) {
          const [summaryData, owners] = await Promise.all([
            fetchBillingSummary(),
            fetchOwners(),
          ]);
          setSummary(summaryData);
          owners.forEach((owner: Owner) => {
            if (owner.property_address) {
              addressMap[owner.id] = owner.property_address;
            }
          });
        } else {
          setSummary(null);
          try {
            const myOwner = await fetchMyOwnerRecord();
            if (myOwner.property_address) {
              addressMap[myOwner.id] = myOwner.property_address;
            }
          } catch (error) {
            // ignore if homeowner record not available
          }
        }
        setOwnerAddresses(addressMap);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [user]);

  if (!user) return null;

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
              <p className="text-lg font-semibold text-primary-600">${Number(summary.total_balance).toFixed(2)}</p>
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
      <div className="rounded border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Invoice</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Property</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Amount</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Due</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {invoices.map((invoice) => (
              <tr key={invoice.id}>
                <td className="px-3 py-2">#{invoice.id}</td>
                <td className="px-3 py-2">{ownerAddresses[invoice.owner_id] ?? `Owner #${invoice.owner_id}`}</td>
                <td className="px-3 py-2">${Number(invoice.amount).toFixed(2)}</td>
                <td className="px-3 py-2">{new Date(invoice.due_date).toLocaleDateString()}</td>
                <td className="px-3 py-2">{invoice.status}</td>
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
