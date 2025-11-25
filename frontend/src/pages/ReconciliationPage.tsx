import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import {
  fetchReconciliations,
  fetchReconciliationById,
  fetchBankTransactions,
  uploadBankStatement,
} from '../services/api';
import { BankTransaction, Reconciliation } from '../types';
import { userHasAnyRole } from '../utils/roles';

const statusBadge: Record<string, string> = {
  MATCHED: 'bg-green-100 text-green-700',
  UNMATCHED: 'bg-rose-100 text-rose-700',
  PENDING: 'bg-slate-200 text-slate-600',
};

const ReconciliationPage: React.FC = () => {
  const { user } = useAuth();
  const [reconciliations, setReconciliations] = useState<Reconciliation[]>([]);
  const [selected, setSelected] = useState<Reconciliation | null>(null);
  const [transactions, setTransactions] = useState<BankTransaction[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [statementDate, setStatementDate] = useState('');
  const [note, setNote] = useState('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const isAuthorized = !!user && userHasAnyRole(user, ['BOARD', 'TREASURER', 'SYSADMIN']);
  const logError = useCallback((message: string, err: unknown) => {
    console.error(message, err);
  }, []);

  const loadReconciliations = useCallback(async () => {
    try {
      const data = await fetchReconciliations();
      setReconciliations(data);
      setSelected((current) => {
        if (!current) {
          return current;
        }
        return data.find((item) => item.id === current.id) ?? current;
      });
    } catch (err) {
      logError('Unable to load reconciliations.', err);
      setError('Unable to load reconciliations.');
    }
  }, [logError]);

  const loadTransactions = useCallback(async (status?: string) => {
    try {
      setLoading(true);
      const data = await fetchBankTransactions(status && status !== 'ALL' ? status : undefined);
      setTransactions(data);
    } catch (err) {
      logError('Unable to load transactions.', err);
      setError('Unable to load transactions.');
    } finally {
      setLoading(false);
    }
  }, [logError]);

  useEffect(() => {
    if (!isAuthorized) return;
    void loadReconciliations();
  }, [isAuthorized, loadReconciliations]);

  useEffect(() => {
    if (!isAuthorized) return;
    void loadTransactions(statusFilter !== 'ALL' ? statusFilter : undefined);
  }, [statusFilter, isAuthorized, loadTransactions]);

  const handleSelect = async (reconciliation: Reconciliation) => {
    try {
      const detail = await fetchReconciliationById(reconciliation.id);
      setSelected(detail);
    } catch (err) {
      logError('Unable to load reconciliation detail.', err);
      setError('Unable to load reconciliation detail.');
    }
  };

  const filteredTransactions = useMemo(() => {
    if (statusFilter === 'ALL') return transactions;
    return transactions.filter((tx) => tx.status === statusFilter);
  }, [transactions, statusFilter]);

  const handleUpload = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!fileInputRef.current || !fileInputRef.current.files || fileInputRef.current.files.length === 0) {
      setError('Select a CSV file to upload.');
      return;
    }
    const file = fileInputRef.current.files[0];
    setUploading(true);
    setSuccess(null);
    setError(null);
    try {
      const result = await uploadBankStatement(file, statementDate || undefined, note || undefined);
      setSuccess('Bank statement imported successfully.');
      await loadReconciliations();
      await loadTransactions(statusFilter !== 'ALL' ? statusFilter : undefined);
      setSelected(result.reconciliation);
      if (fileInputRef.current) fileInputRef.current.value = '';
      setStatementDate('');
      setNote('');
    } catch (err) {
      logError('Unable to import bank statement.', err);
      setError('Unable to import statement. Ensure the CSV has date, description, amount columns.');
    } finally {
      setUploading(false);
    }
  };

  if (!isAuthorized) {
    return <p className="text-sm text-red-600">You do not have access to bank reconciliation reports.</p>;
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-primary-600">Bank Reconciliation</h2>
          <p className="text-sm text-slate-500">
            Upload statement CSVs, review matched items, and track outstanding transactions.
          </p>
        </div>
        <div>
          <label className="mr-2 text-sm text-slate-600" htmlFor="status-filter">Filter</label>
          <select
            id="status-filter"
            className="rounded border border-slate-300 px-3 py-1 text-sm"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="ALL">All</option>
            <option value="MATCHED">Matched</option>
            <option value="UNMATCHED">Unmatched</option>
            <option value="PENDING">Pending</option>
          </select>
        </div>
      </header>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {success && <p className="text-sm text-green-600">{success}</p>}

      <section className="rounded border border-slate-200 p-4">
        <h3 className="text-sm font-semibold text-slate-600">Import Statement</h3>
        <form className="mt-3 grid gap-3 md:grid-cols-4" onSubmit={handleUpload}>
          <div className="md:col-span-2">
            <label className="mb-1 block text-xs text-slate-500" htmlFor="bank-file">CSV File</label>
            <input
              ref={fileInputRef}
              id="bank-file"
              type="file"
              accept=".csv"
              className="w-full text-sm"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500" htmlFor="statement-date">Statement Date</label>
            <input
              id="statement-date"
              type="date"
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              value={statementDate}
              onChange={(event) => setStatementDate(event.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500" htmlFor="statement-note">Note</label>
            <input
              id="statement-note"
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Optional"
            />
          </div>
          <div className="md:col-span-4 flex justify-end">
            <button
              type="submit"
              className="rounded bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-500 disabled:opacity-60"
              disabled={uploading}
            >
              {uploading ? 'Uploading…' : 'Upload & Match'}
            </button>
          </div>
        </form>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded border border-slate-200">
          <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
            <h3 className="text-sm font-semibold text-slate-600">Reconciliations</h3>
          </div>
          <div className="max-h-[420px] overflow-y-auto">
            {reconciliations.length === 0 ? (
              <p className="p-4 text-sm text-slate-500">No reconciliations yet. Upload a statement to begin.</p>
            ) : (
              <ul className="divide-y divide-slate-200">
                {reconciliations.map((rec) => (
                  <li
                    key={rec.id}
                    className={`cursor-pointer px-4 py-3 hover:bg-primary-50 ${selected?.id === rec.id ? 'bg-primary-50' : ''}`}
                    onClick={() => void handleSelect(rec)}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-semibold text-slate-700">
                          Statement {rec.statement_date ? new Date(rec.statement_date).toLocaleDateString() : 'N/A'}
                        </p>
                        <p className="text-xs text-slate-500">
                          Created {new Date(rec.created_at).toLocaleString()} • {rec.matched_transactions}/{rec.total_transactions} matched
                        </p>
                      </div>
                      <span className="text-xs text-slate-500">
                        Unmatched ${Number(rec.unmatched_amount).toFixed(2)}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="rounded border border-slate-200 p-4">
          <h3 className="text-sm font-semibold text-slate-600">Transactions ({filteredTransactions.length})</h3>
          {loading ? (
            <p className="mt-3 text-sm text-slate-500">Loading transactions…</p>
          ) : filteredTransactions.length === 0 ? (
            <p className="mt-3 text-sm text-slate-500">No transactions for this filter. Try another status.</p>
          ) : (
            <div className="mt-3 max-h-[360px] overflow-y-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Date</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Description</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Amount</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-slate-500">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredTransactions.map((tx) => (
                    <tr key={tx.id} className="hover:bg-primary-50/60">
                      <td className="px-3 py-2 text-xs text-slate-500">
                        {tx.transaction_date ? new Date(tx.transaction_date).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-3 py-2">
                        <p className="text-sm text-slate-700">{tx.description ?? '—'}</p>
                        {tx.reference && <p className="text-xs text-slate-500">Ref: {tx.reference}</p>}
                      </td>
                      <td className="px-3 py-2 font-semibold text-slate-700">
                        ${Number(tx.amount).toFixed(2)}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`rounded-full px-2 py-1 text-xs font-semibold ${statusBadge[tx.status] ?? 'bg-slate-200 text-slate-600'}`}
                        >
                          {tx.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {selected && (
        <section className="rounded border border-slate-200 p-4">
          <h3 className="text-sm font-semibold text-slate-600">Reconciliation Detail</h3>
          <p className="mt-1 text-xs text-slate-500">
            Statement date: {selected.statement_date ? new Date(selected.statement_date).toLocaleDateString() : 'N/A'} •
            Matched {selected.matched_transactions}/{selected.total_transactions} • Unmatched ${Number(selected.unmatched_amount).toFixed(2)}
          </p>
          <div className="mt-3 max-h-[300px] overflow-y-auto">
            <table className="min-w-full divide-y divide-slate-200 text-xs">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold text-slate-500">Date</th>
                  <th className="px-3 py-2 text-left font-semibold text-slate-500">Description</th>
                  <th className="px-3 py-2 text-left font-semibold text-slate-500">Amount</th>
                  <th className="px-3 py-2 text-left font-semibold text-slate-500">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {selected.transactions.map((tx) => (
                  <tr key={tx.id}>
                    <td className="px-3 py-2">{tx.transaction_date ? new Date(tx.transaction_date).toLocaleDateString() : '—'}</td>
                    <td className="px-3 py-2">
                      <p className="text-slate-700">{tx.description ?? '—'}</p>
                      {tx.reference && <p className="text-[10px] text-slate-500">Ref: {tx.reference}</p>}
                    </td>
                    <td className="px-3 py-2 font-semibold">${Number(tx.amount).toFixed(2)}</td>
                    <td className="px-3 py-2">
                      <span className={`rounded-full px-2 py-1 font-semibold ${statusBadge[tx.status] ?? 'bg-slate-200 text-slate-600'}`}>
                        {tx.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
};

export default ReconciliationPage;
