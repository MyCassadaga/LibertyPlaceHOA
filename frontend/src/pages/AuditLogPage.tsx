import React, { useState } from 'react';

import { AuditLogEntry } from '../types';
import { useAuditLogsQuery } from '../features/audit/hooks';

const AuditLogPage: React.FC = () => {
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);
  const logsQuery = useAuditLogsQuery(limit, offset);
  const logs: AuditLogEntry[] = logsQuery.data?.items ?? [];
  const total = logsQuery.data?.total ?? 0;
  const loading = logsQuery.isLoading;
  const error = logsQuery.isError ? 'Unable to load audit log.' : null;

  const nextDisabled = offset + limit >= total;
  const prevDisabled = offset === 0;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-primary-600">Audit Log</h2>
          <p className="text-sm text-slate-500">Every action recorded for oversight.</p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <label>
            <span className="mr-2 text-xs uppercase text-slate-500">Rows</span>
            <select
              className="rounded border border-slate-300 px-2 py-1"
              value={limit}
              onChange={(event) => {
                setOffset(0);
                setLimit(Number(event.target.value));
              }}
            >
              {[25, 50, 100, 200].map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="rounded border border-slate-300 px-3 py-1 text-slate-600 hover:bg-slate-50"
            onClick={() => logsQuery.refetch()}
            disabled={logsQuery.isFetching}
          >
            {logsQuery.isFetching ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </header>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {loading && <p className="text-sm text-slate-500">Loading entries…</p>}

      <div className="overflow-x-auto rounded border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-3 py-2 text-left font-semibold text-slate-600">Timestamp</th>
              <th className="px-3 py-2 text-left font-semibold text-slate-600">User</th>
              <th className="px-3 py-2 text-left font-semibold text-slate-600">Action</th>
              <th className="px-3 py-2 text-left font-semibold text-slate-600">Target</th>
              <th className="px-3 py-2 text-left font-semibold text-slate-600">Result</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {logs.map((entry) => (
              <tr key={entry.id}>
                <td className="px-3 py-2 text-xs text-slate-500">
                  {new Date(entry.timestamp).toLocaleString()}
                </td>
                <td className="px-3 py-2">
                  {entry.actor.full_name || entry.actor.email || 'System'}
                  {entry.actor.email && entry.actor.full_name ? (
                    <p className="text-xs text-slate-500">{entry.actor.email}</p>
                  ) : null}
                </td>
                <td className="px-3 py-2 font-semibold text-slate-700">{entry.action}</td>
                <td className="px-3 py-2 text-xs text-slate-500">
                  {entry.target_entity_type || '—'} {entry.target_entity_id || ''}
                </td>
                <td className="px-3 py-2 text-xs text-slate-500">
                  {entry.after ?? entry.before ?? '—'}
                </td>
              </tr>
            ))}
            {!logs.length && !loading && (
              <tr>
                <td colSpan={5} className="px-3 py-4 text-center text-sm text-slate-500">
                  No log entries yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-500">
          Showing {offset + 1} - {Math.min(offset + limit, total)} of {total}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded border border-slate-300 px-3 py-1 text-slate-600 disabled:opacity-50"
            disabled={prevDisabled}
            onClick={() => setOffset(Math.max(offset - limit, 0))}
          >
            Previous
          </button>
          <button
            type="button"
            className="rounded border border-slate-300 px-3 py-1 text-slate-600 disabled:opacity-50"
            disabled={nextDisabled}
            onClick={() => setOffset(offset + limit)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};

export default AuditLogPage;
