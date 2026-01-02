import React, { useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import {
  downloadARAgingReport,
  downloadCashFlowReport,
  downloadViolationsSummaryReport,
  downloadArcSlaReport,
} from '../services/api';
import SortableTable, { SortableColumn } from '../components/SortableTable';
import { downloadCsvFromData, CsvColumn } from '../utils/csv';
import type { ARCStatus, ViolationStatus } from '../types';
import {
  useArcRequestsQuery,
  useInvoicesQuery,
  useReconciliationsQuery,
  useViolationsQuery,
} from '../features/reports/hooks';

const downloadFile = async (fetcher: () => Promise<Blob>, filename: string, setStatus: (value: string | null) => void, setError: (value: string | null) => void) => {
  try {
    setStatus('Preparing download…');
    setError(null);
    const data = await fetcher();
    const url = URL.createObjectURL(data);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setStatus('Download started.');
  } catch (err) {
    console.error('Unable to download report', err);
    setStatus(null);
    setError('Unable to download report.');
  }
};

const ARC_STATUS_LABELS: Record<ARCStatus, string> = {
  DRAFT: 'Draft',
  SUBMITTED: 'Submitted',
  IN_REVIEW: 'In Review',
  REVIEW_COMPLETE: 'Review Complete',
  ARCHIVED: 'Archived',
};

const VIOLATION_STATUS_LABELS: Record<ViolationStatus, string> = {
  NEW: 'New',
  UNDER_REVIEW: 'Under Review',
  WARNING_SENT: 'Warning Sent',
  HEARING: 'Hearing Scheduled',
  FINE_ACTIVE: 'Fine Active',
  RESOLVED: 'Resolved',
  ARCHIVED: 'Archived',
};

type AgingRow = {
  invoiceId: number;
  ownerId: number;
  ownerLabel: string;
  lot?: string | null;
  amount: number;
  dueDate?: string | null;
  status: string;
  daysPastDue: number | null;
};

type CashFlowRow = {
  statementDate?: string | null;
  matchedAmount: number;
  unmatchedAmount: number;
  matchedTransactions: number;
  unmatchedTransactions: number;
  totalTransactions: number;
};

type ViolationSummaryRow = {
  status: string;
  category: string;
  count: number;
};

type ArcRow = {
  title: string;
  status: ARCStatus;
  createdAt: string;
  submittedAt?: string | null;
  finalDecisionAt?: string | null;
  completedAt?: string | null;
  daysToDecision: number | null;
  daysToCompletion: number | null;
};

const ReportsPage: React.FC = () => {
  const { user } = useAuth();
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const invoicesQuery = useInvoicesQuery();
  const reconciliationsQuery = useReconciliationsQuery();
  const violationsQuery = useViolationsQuery();
  const arcRequestsQuery = useArcRequestsQuery();

  const invoicesSnapshot = invoicesQuery.dataUpdatedAt || null;

  const agingRows = useMemo<AgingRow[]>(() => {
    const msPerDay = 1000 * 60 * 60 * 24;
    return (invoicesQuery.data ?? []).map((invoice) => {
      const dueDateValue = invoice.due_date ? new Date(invoice.due_date).getTime() : null;
      const diff =
        dueDateValue && invoicesSnapshot
          ? Math.floor((invoicesSnapshot - dueDateValue) / msPerDay)
          : null;
      const ownerLabel = invoice.lot ?? `Owner #${String(invoice.owner_id).padStart(3, '0')}`;
      return {
        invoiceId: invoice.id,
        ownerId: invoice.owner_id,
        ownerLabel,
        lot: invoice.lot ?? null,
        amount: Number.parseFloat(invoice.amount) || 0,
        dueDate: invoice.due_date ?? null,
        status: invoice.status,
        daysPastDue: diff,
      };
    });
  }, [invoicesQuery.data, invoicesSnapshot]);

  const cashFlowRows = useMemo<CashFlowRow[]>(() => {
    return (reconciliationsQuery.data ?? []).map((recon) => ({
      statementDate: recon.statement_date ?? null,
      matchedAmount: Number.parseFloat(recon.matched_amount) || 0,
      unmatchedAmount: Number.parseFloat(recon.unmatched_amount) || 0,
      matchedTransactions: recon.matched_transactions,
      unmatchedTransactions: recon.unmatched_transactions,
      totalTransactions: recon.total_transactions,
    }));
  }, [reconciliationsQuery.data]);

  const violationSummaryRows = useMemo<ViolationSummaryRow[]>(() => {
    const map = new Map<string, ViolationSummaryRow>();
    (violationsQuery.data ?? []).forEach((violation) => {
      const key = `${violation.status}|${violation.category ?? 'General'}`;
      if (!map.has(key)) {
        map.set(key, {
          status: violation.status,
          category: violation.category ?? 'General',
          count: 0,
        });
      }
      const entry = map.get(key)!;
      entry.count += 1;
    });
    return Array.from(map.values());
  }, [violationsQuery.data]);

  const arcRows = useMemo<ArcRow[]>(() => {
    const differenceInDays = (start?: string | null, end?: string | null): number | null => {
      if (!start || !end) return null;
      const startDate = new Date(start).getTime();
      const endDate = new Date(end).getTime();
      if (Number.isNaN(startDate) || Number.isNaN(endDate)) return null;
      return Math.max(0, Math.round((endDate - startDate) / (1000 * 60 * 60 * 24)));
    };
    return (arcRequestsQuery.data ?? []).map((request) => ({
      title: request.title,
      status: request.status,
      createdAt: request.created_at,
      submittedAt: request.submitted_at ?? null,
      finalDecisionAt: request.final_decision_at ?? null,
      completedAt: request.completed_at ?? null,
      daysToDecision: differenceInDays(request.submitted_at, request.final_decision_at),
      daysToCompletion: differenceInDays(request.submitted_at ?? request.created_at, request.completed_at),
    }));
  }, [arcRequestsQuery.data]);

  const agingColumns = useMemo<SortableColumn<AgingRow>[]>(() => [
    {
      header: 'Invoice #',
      accessor: (row) => `#${String(row.invoiceId).padStart(4, '0')}`,
      sortValue: (row) => row.invoiceId,
    },
    {
      header: 'Owner / Lot',
      accessor: (row) => row.ownerLabel,
      sortValue: (row) => row.ownerLabel,
    },
    {
      header: 'Amount',
      accessor: (row) => `$${row.amount.toFixed(2)}`,
      sortValue: (row) => row.amount,
      align: 'right',
    },
    {
      header: 'Due Date',
      accessor: (row) => (row.dueDate ? new Date(row.dueDate).toLocaleDateString() : '—'),
      sortValue: (row) => (row.dueDate ? new Date(row.dueDate) : null),
    },
    {
      header: 'Days Past Due',
      accessor: (row) => {
        if (row.daysPastDue === null) return '—';
        if (row.daysPastDue === 0) return 'Due today';
        if (row.daysPastDue > 0) return `${row.daysPastDue} day(s) overdue`;
        return `Due in ${Math.abs(row.daysPastDue)} day(s)`;
      },
      sortValue: (row) => row.daysPastDue ?? Number.NEGATIVE_INFINITY,
    },
    {
      header: 'Status',
      accessor: (row) => row.status,
      sortValue: (row) => row.status,
    },
  ], []);

  const cashFlowColumns = useMemo<SortableColumn<CashFlowRow>[]>(() => [
    {
      header: 'Statement Date',
      accessor: (row) => (row.statementDate ? new Date(row.statementDate).toLocaleDateString() : '—'),
      sortValue: (row) => (row.statementDate ? new Date(row.statementDate) : null),
    },
    {
      header: 'Total Transactions',
      accessor: (row) => row.totalTransactions,
      sortValue: (row) => row.totalTransactions,
      align: 'right',
    },
    {
      header: 'Matched',
      accessor: (row) => row.matchedTransactions,
      sortValue: (row) => row.matchedTransactions,
      align: 'right',
    },
    {
      header: 'Unmatched',
      accessor: (row) => row.unmatchedTransactions,
      sortValue: (row) => row.unmatchedTransactions,
      align: 'right',
    },
    {
      header: 'Matched Amount',
      accessor: (row) => `$${row.matchedAmount.toFixed(2)}`,
      sortValue: (row) => row.matchedAmount,
      align: 'right',
    },
    {
      header: 'Unmatched Amount',
      accessor: (row) => `$${row.unmatchedAmount.toFixed(2)}`,
      sortValue: (row) => row.unmatchedAmount,
      align: 'right',
    },
  ], []);

  const violationColumns = useMemo<SortableColumn<ViolationSummaryRow>[]>(() => [
    {
      header: 'Status',
      accessor: (row) => VIOLATION_STATUS_LABELS[row.status as ViolationStatus] ?? row.status,
      sortValue: (row) => row.status,
    },
    {
      header: 'Category',
      accessor: (row) => row.category,
      sortValue: (row) => row.category,
    },
    {
      header: 'Count',
      accessor: (row) => row.count,
      sortValue: (row) => row.count,
      align: 'right',
    },
  ], []);

  const arcColumns = useMemo<SortableColumn<ArcRow>[]>(() => [
    {
      header: 'Request',
      accessor: (row) => row.title,
      sortValue: (row) => row.title,
    },
    {
      header: 'Status',
      accessor: (row) => ARC_STATUS_LABELS[row.status] ?? row.status,
      sortValue: (row) => row.status,
    },
    {
      header: 'Created',
      accessor: (row) => new Date(row.createdAt).toLocaleDateString(),
      sortValue: (row) => new Date(row.createdAt),
    },
    {
      header: 'Submitted',
      accessor: (row) => (row.submittedAt ? new Date(row.submittedAt).toLocaleDateString() : '—'),
      sortValue: (row) => (row.submittedAt ? new Date(row.submittedAt) : null),
    },
    {
      header: 'Days to Decision',
      accessor: (row) => (row.daysToDecision !== null ? `${row.daysToDecision} day(s)` : '—'),
      sortValue: (row) => row.daysToDecision ?? Number.MAX_SAFE_INTEGER,
      align: 'right',
    },
    {
      header: 'Days to Completion',
      accessor: (row) => (row.daysToCompletion !== null ? `${row.daysToCompletion} day(s)` : '—'),
      sortValue: (row) => row.daysToCompletion ?? Number.MAX_SAFE_INTEGER,
      align: 'right',
    },
  ], []);

  const exportAgingCsv = () => {
    const columns: CsvColumn<AgingRow>[] = [
      { header: 'Invoice #', accessor: (row) => `#${String(row.invoiceId).padStart(4, '0')}` },
      { header: 'Owner / Lot', accessor: (row) => row.ownerLabel },
      { header: 'Amount', accessor: (row) => row.amount.toFixed(2) },
      { header: 'Due Date', accessor: (row) => (row.dueDate ? new Date(row.dueDate).toLocaleDateString() : '') },
      {
        header: 'Days Past Due',
        accessor: (row) => (row.daysPastDue ?? ''),
      },
      { header: 'Status', accessor: (row) => row.status },
    ];
    downloadCsvFromData('ar-aging-view.csv', agingRows, columns);
  };

  const exportCashFlowCsv = () => {
    const columns: CsvColumn<CashFlowRow>[] = [
      { header: 'Statement Date', accessor: (row) => (row.statementDate ? new Date(row.statementDate).toLocaleDateString() : '') },
      { header: 'Total Transactions', accessor: (row) => row.totalTransactions },
      { header: 'Matched Transactions', accessor: (row) => row.matchedTransactions },
      { header: 'Unmatched Transactions', accessor: (row) => row.unmatchedTransactions },
      { header: 'Matched Amount', accessor: (row) => row.matchedAmount.toFixed(2) },
      { header: 'Unmatched Amount', accessor: (row) => row.unmatchedAmount.toFixed(2) },
    ];
    downloadCsvFromData('cash-flow-view.csv', cashFlowRows, columns);
  };

  const exportViolationsCsv = () => {
    const columns: CsvColumn<ViolationSummaryRow>[] = [
      { header: 'Status', accessor: (row) => VIOLATION_STATUS_LABELS[row.status as ViolationStatus] ?? row.status },
      { header: 'Category', accessor: (row) => row.category },
      { header: 'Count', accessor: (row) => row.count },
    ];
    downloadCsvFromData('violations-summary-view.csv', violationSummaryRows, columns);
  };

  const exportArcCsv = () => {
    const columns: CsvColumn<ArcRow>[] = [
      { header: 'Title', accessor: (row) => row.title },
      { header: 'Status', accessor: (row) => ARC_STATUS_LABELS[row.status] ?? row.status },
      { header: 'Created', accessor: (row) => new Date(row.createdAt).toLocaleDateString() },
      { header: 'Submitted', accessor: (row) => (row.submittedAt ? new Date(row.submittedAt).toLocaleDateString() : '') },
      { header: 'Days to Decision', accessor: (row) => (row.daysToDecision ?? '') },
      { header: 'Days to Completion', accessor: (row) => (row.daysToCompletion ?? '') },
    ];
    downloadCsvFromData('arc-sla-view.csv', arcRows, columns);
  };

  const loading =
    invoicesQuery.isLoading || reconciliationsQuery.isLoading || violationsQuery.isLoading || arcRequestsQuery.isLoading;
  const baseError =
    invoicesQuery.isError || reconciliationsQuery.isError || violationsQuery.isError || arcRequestsQuery.isError
      ? 'Unable to load report data.'
      : null;
  const effectiveError = error ?? baseError;

  if (!user) {
    return null;
  }

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-xl font-semibold text-primary-600">Reports & Analytics</h2>
        <p className="text-sm text-slate-500">
          Explore key financial and operational metrics. Export the tables below or download raw CSVs from the API.
        </p>
      </header>

      {status && <p className="text-sm text-green-600">{status}</p>}
      {effectiveError && <p className="text-sm text-red-600">{effectiveError}</p>}
      {loading && <p className="text-sm text-slate-500">Loading report data…</p>}

      <section className="space-y-3 rounded border border-slate-200 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold text-slate-700">Accounts Receivable Aging</h3>
            <p className="text-sm text-slate-500">Outstanding invoices with due dates and aging details.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              className="rounded border border-primary-600 px-3 py-2 text-sm font-semibold text-primary-600 hover:bg-primary-50"
              onClick={exportAgingCsv}
              type="button"
            >
              Export Table CSV
            </button>
            <button
              className="rounded bg-primary-600 px-3 py-2 text-sm font-semibold text-white hover:bg-primary-500"
              onClick={() => downloadFile(downloadARAgingReport, 'ar-aging.csv', setStatus, setError)}
              type="button"
            >
              Download Raw CSV
            </button>
          </div>
        </div>
        <SortableTable data={agingRows} columns={agingColumns} emptyMessage="No invoices available." />
      </section>

      <section className="space-y-3 rounded border border-slate-200 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold text-slate-700">Cash Flow Summary</h3>
            <p className="text-sm text-slate-500">Reconciliation snapshots with matched and unmatched balances.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              className="rounded border border-primary-600 px-3 py-2 text-sm font-semibold text-primary-600 hover:bg-primary-50"
              onClick={exportCashFlowCsv}
              type="button"
            >
              Export Table CSV
            </button>
            <button
              className="rounded bg-primary-600 px-3 py-2 text-sm font-semibold text-white hover:bg-primary-500"
              onClick={() => downloadFile(downloadCashFlowReport, 'cash-flow.csv', setStatus, setError)}
              type="button"
            >
              Download Raw CSV
            </button>
          </div>
        </div>
        <SortableTable data={cashFlowRows} columns={cashFlowColumns} emptyMessage="No reconciliation data available." />
      </section>

      <section className="space-y-3 rounded border border-slate-200 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold text-slate-700">Violations Summary</h3>
            <p className="text-sm text-slate-500">Counts by status and category for covenant enforcement.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              className="rounded border border-primary-600 px-3 py-2 text-sm font-semibold text-primary-600 hover:bg-primary-50"
              onClick={exportViolationsCsv}
              type="button"
            >
              Export Table CSV
            </button>
            <button
              className="rounded bg-primary-600 px-3 py-2 text-sm font-semibold text-white hover:bg-primary-500"
              onClick={() => downloadFile(downloadViolationsSummaryReport, 'violations-summary.csv', setStatus, setError)}
              type="button"
            >
              Download Raw CSV
            </button>
          </div>
        </div>
        <SortableTable
          data={violationSummaryRows}
          columns={violationColumns}
          emptyMessage="No violation activity recorded."
        />
      </section>

      <section className="space-y-3 rounded border border-slate-200 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold text-slate-700">ARC SLA Metrics</h3>
            <p className="text-sm text-slate-500">Turnaround times for ARC requests from submission to decision.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              className="rounded border border-primary-600 px-3 py-2 text-sm font-semibold text-primary-600 hover:bg-primary-50"
              onClick={exportArcCsv}
              type="button"
            >
              Export Table CSV
            </button>
            <button
              className="rounded bg-primary-600 px-3 py-2 text-sm font-semibold text-white hover:bg-primary-500"
              onClick={() => downloadFile(downloadArcSlaReport, 'arc-sla.csv', setStatus, setError)}
              type="button"
            >
              Download Raw CSV
            </button>
          </div>
        </div>
        <SortableTable data={arcRows} columns={arcColumns} emptyMessage="No ARC requests submitted." />
      </section>
    </div>
  );
};

export default ReportsPage;
