import axios, { AxiosError } from 'axios';
import React, { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import {
  createContract,
  fetchContracts,
  getContractAttachmentDownloadUrl,
  updateContract,
  uploadContractAttachment,
} from '../services/api';
import {
  useContractsQuery,
  useCreateVendorPaymentMutation,
  useMarkVendorPaymentPaidMutation,
  useSendVendorPaymentMutation,
  useVendorPaymentsQuery,
} from '../features/billing/hooks';
import { userHasAnyRole } from '../utils/roles';
import { ApiErrorPayload } from '../lib/api/client';
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
  const [contractForm, setContractForm] = useState({
    vendorName: '',
    serviceType: '',
    contactEmail: '',
    startDate: '',
    endDate: '',
    autoRenew: false,
    terminationNoticeDeadline: '',
    value: '',
    notes: '',
  });
  const [editingContractId, setEditingContractId] = useState<number | null>(null);
  const [attachmentFile, setAttachmentFile] = useState<File | null>(null);
  const [contractBusy, setContractBusy] = useState(false);
  const [contractStatus, setContractStatus] = useState<string | null>(null);
  const [contractError, setContractError] = useState<string | null>(null);
  const [vendorBusy, setVendorBusy] = useState(false);
  const [vendorStatus, setVendorStatus] = useState<string | null>(null);
  const [vendorError, setVendorError] = useState<string | null>(null);

  const getApiErrorMessage = (error: unknown, fallback: string) => {
    if (!axios.isAxiosError(error)) {
      return fallback;
    }
    const responseError = error as AxiosError<ApiErrorPayload>;
    const detail = responseError.response?.data?.detail;
    if (!detail) {
      return fallback;
    }
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (item && typeof item === 'object' && 'msg' in item) {
            return String(item.msg);
          }
          return String(item);
        })
        .filter(Boolean);
      return messages.length > 0 ? messages.join(' ') : fallback;
    }
    if (typeof detail === 'string') {
      return detail;
    }
    return fallback;
  };

  const managerRoles = useMemo(() => ['BOARD', 'TREASURER', 'SYSADMIN'], []);
  const editorRoles = useMemo(() => ['TREASURER', 'SYSADMIN'], []);
  const isManager = useMemo(() => userHasAnyRole(user, managerRoles), [user, managerRoles]);
  const canEditContracts = useMemo(() => userHasAnyRole(user, editorRoles), [user, editorRoles]);

  const contractsQuery = useContractsQuery(isManager);
  const vendorPaymentsQuery = useVendorPaymentsQuery(isManager);
  const createVendorPayment = useCreateVendorPaymentMutation();
  const sendVendorPaymentMutation = useSendVendorPaymentMutation();
  const markVendorPaymentPaidMutation = useMarkVendorPaymentPaidMutation();

  const vendorPayments = vendorPaymentsQuery.data ?? [];
  const isCheckPayment = vendorForm.paymentMethod === 'CHECK';

  const resetContractForm = () => {
    setContractForm({
      vendorName: '',
      serviceType: '',
      contactEmail: '',
      startDate: '',
      endDate: '',
      autoRenew: false,
      terminationNoticeDeadline: '',
      value: '',
      notes: '',
    });
    setEditingContractId(null);
    setAttachmentFile(null);
  };

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

  const handleContractFormChange = (field: keyof typeof contractForm, value: string | boolean) => {
    setContractForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleEditContract = (contract: Contract) => {
    setContractForm({
      vendorName: contract.vendor_name,
      serviceType: contract.service_type ?? '',
      contactEmail: contract.contact_email ?? '',
      startDate: contract.start_date ?? '',
      endDate: contract.end_date ?? '',
      autoRenew: contract.auto_renew,
      terminationNoticeDeadline: contract.termination_notice_deadline ?? '',
      value: contract.value ?? '',
      notes: contract.notes ?? '',
    });
    setEditingContractId(contract.id);
    setAttachmentFile(null);
    setContractStatus(null);
    setContractError(null);
  };

  const handleSaveContract = async (event: React.FormEvent) => {
    event.preventDefault();
    setContractBusy(true);
    setContractStatus(null);
    setContractError(null);
    try {
      const payload = {
        vendor_name: contractForm.vendorName.trim(),
        service_type: contractForm.serviceType.trim() || null,
        contact_email: contractForm.contactEmail.trim() || null,
        start_date: contractForm.startDate,
        end_date: contractForm.endDate || null,
        auto_renew: contractForm.autoRenew,
        termination_notice_deadline: contractForm.terminationNoticeDeadline || null,
        value: contractForm.value || null,
        notes: contractForm.notes.trim() || null,
      };

      let saved: Contract;
      if (editingContractId) {
        saved = await updateContract(editingContractId, payload);
      } else {
        saved = await createContract(payload);
      }

      let uploadFailed = false;
      if (attachmentFile) {
        try {
          saved = await uploadContractAttachment(saved.id, attachmentFile);
        } catch (error) {
          uploadFailed = true;
          setContractError(getApiErrorMessage(error, 'Contract saved, but unable to upload the attachment.'));
        }
      }

      try {
        await contractsQuery.refetch();
      } catch (error) {
        setContractError(getApiErrorMessage(error, 'Contract saved, but unable to refresh the list.'));
        uploadFailed = true;
      }

      if (!uploadFailed) {
        setContractStatus(editingContractId ? 'Contract updated.' : 'Contract created.');
        resetContractForm();
      }
    } catch (error) {
      setContractError(getApiErrorMessage(error, 'Unable to save contract.'));
    } finally {
      setContractBusy(false);
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
                <th className="px-3 py-2 text-left font-medium text-slate-600">Value</th>
                <th className="px-3 py-2 text-left font-medium text-slate-600">Attachment</th>
                {canEditContracts && <th className="px-3 py-2 text-right font-medium text-slate-600">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {contracts.map((contract) => (
                <tr key={contract.id}>
                  <td className="px-3 py-2">
                    <p className="font-semibold text-slate-700">{contract.vendor_name}</p>
                    {contract.notes && <p className="text-xs text-slate-500">{contract.notes}</p>}
                  </td>
                  <td className="px-3 py-2">{contract.service_type ?? '—'}</td>
                  <td className="px-3 py-2">{new Date(contract.start_date).toLocaleDateString()}</td>
                  <td className="px-3 py-2">
                    {contract.end_date ? new Date(contract.end_date).toLocaleDateString() : 'Open'}
                  </td>
                  <td className="px-3 py-2">{contract.auto_renew ? 'Yes' : 'No'}</td>
                  <td className="px-3 py-2">{contract.value ? formatCurrency(contract.value) : '—'}</td>
                  <td className="px-3 py-2">
                    {contract.attachment_download_url ? (
                      <a
                        className="text-xs font-semibold text-primary-600 hover:text-primary-500"
                        href={contract.attachment_download_url || getContractAttachmentDownloadUrl(contract.id)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Download PDF
                      </a>
                    ) : (
                      <span className="text-xs text-slate-400">No file</span>
                    )}
                  </td>
                  {canEditContracts && (
                    <td className="px-3 py-2 text-right">
                      <button
                        type="button"
                        className="rounded border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                        onClick={() => handleEditContract(contract)}
                      >
                        Edit
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          {contracts.length === 0 && !loading && (
            <p className="px-3 py-4 text-sm text-slate-500">No contracts recorded yet.</p>
          )}
        </div>
        {!canEditContracts && (
          <p className="text-sm text-slate-500">
            You have read-only access to contracts. Contact a treasurer or sysadmin to make changes.
          </p>
        )}
      </div>

      {canEditContracts && (
        <section className="rounded border border-slate-200 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-slate-700">
                {editingContractId ? 'Edit contract' : 'Add contract'}
              </h3>
              <p className="text-sm text-slate-500">Upload contract PDFs and track renewal dates.</p>
            </div>
            {contractStatus && <span className="text-xs text-emerald-600">{contractStatus}</span>}
          </div>
          {contractError && <p className="mt-2 text-sm text-red-600">{contractError}</p>}
          <form className="mt-4 grid gap-3 md:grid-cols-3" onSubmit={handleSaveContract}>
            <label className="text-sm">
              <span className="text-xs uppercase text-slate-500">Vendor</span>
              <input
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={contractForm.vendorName}
                onChange={(event) => handleContractFormChange('vendorName', event.target.value)}
                placeholder="ACME Landscaping"
                required
              />
            </label>
            <label className="text-sm">
              <span className="text-xs uppercase text-slate-500">Service</span>
              <input
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={contractForm.serviceType}
                onChange={(event) => handleContractFormChange('serviceType', event.target.value)}
                placeholder="Landscaping"
              />
            </label>
            <label className="text-sm">
              <span className="text-xs uppercase text-slate-500">Contact email</span>
              <input
                type="email"
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={contractForm.contactEmail}
                onChange={(event) => handleContractFormChange('contactEmail', event.target.value)}
                placeholder="vendor@example.com"
              />
            </label>
            <label className="text-sm">
              <span className="text-xs uppercase text-slate-500">Value</span>
              <input
                type="number"
                step="0.01"
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={contractForm.value}
                onChange={(event) => handleContractFormChange('value', event.target.value)}
                placeholder="0.00"
              />
            </label>
            <label className="text-sm">
              <span className="text-xs uppercase text-slate-500">Start date</span>
              <input
                type="date"
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={contractForm.startDate}
                onChange={(event) => handleContractFormChange('startDate', event.target.value)}
                required
              />
            </label>
            <label className="text-sm">
              <span className="text-xs uppercase text-slate-500">End date</span>
              <input
                type="date"
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={contractForm.endDate}
                onChange={(event) => handleContractFormChange('endDate', event.target.value)}
              />
            </label>
            <label className="text-sm">
              <span className="text-xs uppercase text-slate-500">Notice deadline</span>
              <input
                type="date"
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={contractForm.terminationNoticeDeadline}
                onChange={(event) => handleContractFormChange('terminationNoticeDeadline', event.target.value)}
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300 text-primary-600"
                checked={contractForm.autoRenew}
                onChange={(event) => handleContractFormChange('autoRenew', event.target.checked)}
              />
              <span className="text-xs uppercase text-slate-500">Auto renew</span>
            </label>
            <label className="text-sm md:col-span-2">
              <span className="text-xs uppercase text-slate-500">Attachment (PDF)</span>
              <input
                type="file"
                accept="application/pdf"
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-xs"
                onChange={(event) => setAttachmentFile(event.target.files?.[0] ?? null)}
              />
              {editingContractId && (
                <p className="mt-1 text-xs text-slate-400">Uploading a file replaces the existing attachment.</p>
              )}
            </label>
            <label className="text-sm md:col-span-3">
              <span className="text-xs uppercase text-slate-500">Notes</span>
              <textarea
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                rows={3}
                value={contractForm.notes}
                onChange={(event) => handleContractFormChange('notes', event.target.value)}
                placeholder="Renewal notes or contact details"
              />
            </label>
            <div className="flex flex-wrap items-center gap-3 md:col-span-3">
              <button
                type="submit"
                className="rounded bg-primary-600 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white hover:bg-primary-500 disabled:opacity-60"
                disabled={contractBusy}
              >
                {contractBusy ? 'Saving…' : editingContractId ? 'Save changes' : 'Create contract'}
              </button>
              {editingContractId && (
                <button
                  type="button"
                  className="rounded border border-slate-300 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-slate-600 hover:bg-slate-50"
                  onClick={resetContractForm}
                >
                  Cancel
                </button>
              )}
            </div>
          </form>
        </section>
      )}

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
