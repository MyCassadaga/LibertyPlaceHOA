import React, { useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import {
  downloadARAgingReport,
  downloadCashFlowReport,
  downloadViolationsSummaryReport,
  downloadArcSlaReport,
} from '../services/api';

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
    setStatus(null);
    setError('Unable to download report.');
  }
};

const ReportsPage: React.FC = () => {
  const { user } = useAuth();
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!user) {
    return null;
  }

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-xl font-semibold text-primary-600">Reports & Analytics</h2>
        <p className="text-sm text-slate-500">
          Download CSV reports for financials, violations, and ARC service levels. Access is restricted to board and
          treasurer roles.
        </p>
      </header>

      {status && <p className="text-sm text-green-600">{status}</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      <section className="grid gap-4 md:grid-cols-2">
        <article className="rounded border border-slate-200 p-4">
          <h3 className="font-semibold text-slate-700">Accounts Receivable Aging</h3>
          <p className="mt-1 text-sm text-slate-500">
            Export open invoices by owner, aging bucket, and balance.
          </p>
          <button
            className="mt-3 rounded bg-primary-600 px-3 py-2 text-sm font-semibold text-white hover:bg-primary-500"
            onClick={() => downloadFile(downloadARAgingReport, 'ar-aging.csv', setStatus, setError)}
          >
            Download AR Aging CSV
          </button>
        </article>

        <article className="rounded border border-slate-200 p-4">
          <h3 className="font-semibold text-slate-700">Cash Flow Summary</h3>
          <p className="mt-1 text-sm text-slate-500">
            Monthly net cash flow derived from ledger entries.
          </p>
          <button
            className="mt-3 rounded bg-primary-600 px-3 py-2 text-sm font-semibold text-white hover:bg-primary-500"
            onClick={() => downloadFile(downloadCashFlowReport, 'cash-flow.csv', setStatus, setError)}
          >
            Download Cash Flow CSV
          </button>
        </article>

        <article className="rounded border border-slate-200 p-4">
          <h3 className="font-semibold text-slate-700">Violations Summary</h3>
          <p className="mt-1 text-sm text-slate-500">
            Counts by status and category for covenant compliance actions.
          </p>
          <button
            className="mt-3 rounded bg-primary-600 px-3 py-2 text-sm font-semibold text-white hover:bg-primary-500"
            onClick={() => downloadFile(downloadViolationsSummaryReport, 'violations-summary.csv', setStatus, setError)}
          >
            Download Violations Summary CSV
          </button>
        </article>

        <article className="rounded border border-slate-200 p-4">
          <h3 className="font-semibold text-slate-700">ARC SLA Metrics</h3>
          <p className="mt-1 text-sm text-slate-500">
            Average review and completion times plus revision counts for ARC workflows.
          </p>
          <button
            className="mt-3 rounded bg-primary-600 px-3 py-2 text-sm font-semibold text-white hover:bg-primary-500"
            onClick={() => downloadFile(downloadArcSlaReport, 'arc-sla.csv', setStatus, setError)}
          >
            Download ARC SLA CSV
          </button>
        </article>
      </section>
    </div>
  );
};

export default ReportsPage;
