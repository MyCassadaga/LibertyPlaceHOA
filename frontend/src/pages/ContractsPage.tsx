import React, { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import { fetchContracts } from '../services/api';
import {
  useContractsQuery,
  useCreateVendorPaymentMutation,
  useMarkVendorPaymentPaidMutation,
  useSendVendorPaymentMutation,
  useVendorPaymentsQuery,
} from '../features/billing/hooks';
import { userHasAnyRole } from '../utils/roles';
import { Contract } from '../types';

const ContractsPage: React.FC = () => {
  const { user } = useAuth();
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [loading, setLoading] = useState(true);
  const [vendorForm, setVendorForm] = useState<{
    contractId: string;
    vendorName: string;
    amount: string;
    paymentMethod: 'ACH' | 'CHECK' | 'WIRE' | 'CARD' | 'CASH' | 'OTHER';
    checkNumber: string;
    notes: string;
  }>({
    contractId: '',
    vendorName: '',
    amount: '',
    paymentMethod: 'ACH',
    checkNumber: '',
    notes: '',
  });
  const [vendorBusy, setVendorBusy] = useState(false);
  const [vendorStatus, setVendorStatus] = useState<string | null>(null);
  const [vendorError, setVendorError] = useState<string | null>(null);

  const managerRoles = useMemo(() => ['BOARD', 'TREASURER', 'SYSADMIN'], []);
  const isManager = useMemo(() => userHasAnyRole(user, managerRoles), [user, managerRoles]);

  const contractsQuery = useContractsQuery(isManager);
  const vendorPaymentsQuery = useVendorPaymentsQuery(isManager);
  const createVendorPayment = useCreateVendorPaymentMutation();
  const sendVendorPaymentMutation = useSendVendorPaymentMutation();
  const markVendorPaymentPaidMutation = useMarkVendorPaymentPaidMutation();

  const vendorPayments = vendorPaymentsQuery.data ?? [];
  const isCheckPayment = vendorForm.paymentMethod === 'CHECK';

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await fetchContracts();
        setContracts(data);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  useEffect(() => {
    if (contractsQuery.data) {
      setContracts(contractsQuery.data);
    }
  }, [contractsQuery.data]);

  const formatCurrency = (value: string | number) => {
    const parsedRaw = typeof value === 'string' ? Number(value) : value;
    const parsed = Number.isFinite(parsedRaw) ? parsedRaw : 0;
    return parsed.toLocaleString(undefined, { style: 'currency', currency: 'USD' });
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
      if (field === 'paymentMethod') {
        return {
          ...prev,
          paymentMethod: value as typeof prev.paymentMethod,
          checkNumber: value === 'CHECK' ? prev.checkNumber : '',
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
        payment_method: 'ACH' | 'CHECK' | 'WIRE' | 'CARD' | 'CASH' | 'OTHER';
        check_number?: string;
        notes?: string;
      } = {
        amount: vendorForm.amount,
        payment_method: vendorForm.paymentMethod,
      };
      if (vendorForm.contractId) {
        payload.contract_id = Number(vendorForm.contractId);
      }
      if (vendorForm.vendorName.trim()) {
        payload.vendor_name = vendorForm.vendorName.trim();
      }
      if (vendorForm.checkNumber.trim()) {
        payload.check_number = vendorForm.checkNumber.trim();
      }
      if (vendorForm.notes.trim()) {
        payload.notes = vendorForm.notes.trim();
      }
      const record = await createVendorPayment.mutateAsync(payload);
      setVendorStatus(`Drafted payment for ${record.vendor_name}.`);
      setVendorForm({ contractId: '', vendorName: '', amount: '', paymentMethod: 'ACH', checkNumber: '', notes: '' });
      await vendorPaymentsQuery.refetch();
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
      await sendVendorPaymentMutation.mutateAsync(paymentId);
      setVendorStatus('Vendor payment submitted for processing.');
      await vendorPaymentsQuery.refetch();
    } catch {
      setVendorError('Unable to submit vendor payment.');
    }
  };

  const handleMarkVendorPaid = async (paymentId: number) => {
    setVendorStatus(null);
    setVendorError(null);
    try {
      await markVendorPaymentPaidMutation.mutateAsync(paymentId);
      setVendorStatus('Vendor payment marked as paid.');
      await vendorPaymentsQuery.refetch();
    } catch {
      setVendorError('Unable to update vendor payment.');
    }
  };

  if (!user) return null;

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold text-slate-700">Vendor Contracts</h2>
        {loading && <p className="text-sm text-slate-500">Loading contracts…</p>}
        <div className="overflow-x-auto rounded border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-slate-600">Vendor</th>
                <th className="px-3 py-2 text-left font-medium text-slate-600">Service</th>
                <th className="px-3 py-2 text-left font-medium text-slate-600">Start</th>
                <th className="px-3 py-2 text-left font-medium text-slate-600">End</th>
                <th className="px-3 py-2 text-left font-medium text-slate-600">Auto Renew</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {contracts.map((contract) => (
                <tr key={contract.id}>
                  <td className="px-3 py-2">
                    <p className="font-semibold text-slate-700">{contract.vendor_name}</p>
                    {contract.memo && <p className="text-xs text-slate-500">{contract.memo}</p>}
                  </td>
                  <td className="px-3 py-2">{contract.service_type ?? '—'}</td>
                  <td className="px-3 py-2">{new Date(contract.start_date).toLocaleDateString()}</td>
                  <td className="px-3 py-2">
                    {contract.end_date ? new Date(contract.end_date).toLocaleDateString() : 'Open'}
                  </td>
                  <td className="px-3 py-2">{contract.auto_renew ? 'Yes' : 'No'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {contracts.length === 0 && !loading && (
            <p className="px-3 py-4 text-sm text-slate-500">No contracts recorded yet.</p>
          )}
        </div>
      </div>

      {isManager && (
        <section className="rounded border border-slate-200 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-slate-700">Vendor Payments</h3>
              <p className="text-sm text-slate-500">Draft payouts for contract vendors and track their status.</p>
            </div>
            {vendorStatus && <span className="text-xs text-emerald-600">{vendorStatus}</span>}
          </div>
          {vendorError && <p className="mt-2 text-sm text-red-600">{vendorError}</p>}
          {vendorPaymentsQuery.isError && (
            <p className="mt-2 text-sm text-red-600">Unable to load vendor payments.</p>
          )}
          <form className="mt-3 grid gap-3 md:grid-cols-6" onSubmit={handleCreateVendorPayment}>
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
              <span className="text-xs uppercase text-slate-500">Payment method</span>
              <select
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={vendorForm.paymentMethod}
                onChange={(event) => handleVendorFormChange('paymentMethod', event.target.value)}
              >
                <option value="ACH">ACH</option>
                <option value="CHECK">Check</option>
                <option value="WIRE">Wire</option>
                <option value="CARD">Card</option>
                <option value="CASH">Cash</option>
                <option value="OTHER">Other</option>
              </select>
            </label>
            <label className="text-sm">
              <span className="text-xs uppercase text-slate-500">Check #</span>
              <input
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={vendorForm.checkNumber}
                onChange={(event) => handleVendorFormChange('checkNumber', event.target.value)}
                placeholder={isCheckPayment ? '100245' : 'N/A'}
                disabled={!isCheckPayment}
                required={isCheckPayment}
              />
            </label>
            <label className="text-sm md:col-span-3">
              <span className="text-xs uppercase text-slate-500">Notes</span>
              <textarea
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={vendorForm.notes}
                onChange={(event) => handleVendorFormChange('notes', event.target.value)}
                placeholder="Invoice #, scope of work, or internal notes"
                rows={2}
              />
            </label>
            <div className="md:col-span-6">
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
            {vendorPaymentsQuery.isLoading ? (
              <p className="text-sm text-slate-500">Loading vendor payments…</p>
            ) : (
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Vendor</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Amount</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Method</th>
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
                        {payment.notes && <p className="text-xs text-slate-500">{payment.notes}</p>}
                      </td>
                      <td className="px-3 py-2">{formatCurrency(payment.amount)}</td>
                      <td className="px-3 py-2 text-xs text-slate-500">
                        <p className="uppercase">{payment.payment_method}</p>
                        {payment.check_number && <p className="text-slate-400">Check #{payment.check_number}</p>}
                      </td>
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
                      <td colSpan={6} className="px-3 py-4 text-center text-sm text-slate-500">
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
    </div>
  );
};

export default ContractsPage;
