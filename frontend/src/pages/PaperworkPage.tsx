import React, { useCallback, useEffect, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import {
  claimPaperworkItem,
  fetchPaperwork,
  fetchPaperworkFeatures,
  getPaperworkPrintUrl,
  getPaperworkDownloadUrl,
  mailPaperworkItem,
  sendPaperworkViaClick2Mail,
} from '../services/api';
import { PaperworkItem } from '../types';
import { userHasAnyRole } from '../utils/roles';

const BOARD_ROLES = ['BOARD', 'TREASURER', 'SECRETARY', 'SYSADMIN'];
const STATUS_TABS = ['PENDING', 'CLAIMED', 'MAILED'] as const;

type StatusFilter = typeof STATUS_TABS[number];

const PaperworkPage: React.FC = () => {
  const { user } = useAuth();
  const canManage = useMemo(() => userHasAnyRole(user, BOARD_ROLES), [user]);
  const [items, setItems] = useState<PaperworkItem[]>([]);
  const [status, setStatus] = useState<StatusFilter>('PENDING');
  const [requiredOnly, setRequiredOnly] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [click2mailEnabled, setClick2mailEnabled] = useState(false);
  const [dispatchingId, setDispatchingId] = useState<number | null>(null);

  const loadPaperwork = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPaperwork({ status, requiredOnly });
      setItems(data);
    } catch (err) {
      setError('Unable to load paperwork.');
    } finally {
      setLoading(false);
    }
  }, [status, requiredOnly]);

  useEffect(() => {
    void loadPaperwork();
  }, [loadPaperwork]);

  useEffect(() => {
    const loadFeatures = async () => {
      try {
        const data = await fetchPaperworkFeatures();
        setClick2mailEnabled(Boolean(data.click2mail_enabled));
      } catch {
        setClick2mailEnabled(false);
      }
    };
    void loadFeatures();
  }, []);

  const handleClaim = async (paperworkId: number) => {
    try {
      await claimPaperworkItem(paperworkId);
      await loadPaperwork();
    } catch (err) {
      setError('Unable to claim item.');
    }
  };

  const handleMail = async (paperworkId: number) => {
    try {
      await mailPaperworkItem(paperworkId);
      await loadPaperwork();
    } catch (err) {
      setError('Unable to mark mailed.');
    }
  };

  const handleSendClick2Mail = async (paperworkId: number) => {
    setDispatchingId(paperworkId);
    setError(null);
    try {
      await sendPaperworkViaClick2Mail(paperworkId);
      await loadPaperwork();
    } catch (err) {
      setError('Unable to send via Click2Mail.');
    } finally {
      setDispatchingId(null);
    }
  };

  const handlePrint = (paperworkId: number) => {
    const url = getPaperworkPrintUrl(paperworkId);
    window.open(url, '_blank');
  };

  const groupedItems = useMemo(() => {
    if (status !== 'MAILED') {
      return {
        required: items.filter((item) => item.required),
        optional: items.filter((item) => !item.required),
      };
    }
    return { required: items, optional: [] };
  }, [items, status]);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-primary-600">Paperwork Queue</h2>
          <p className="text-sm text-slate-500">Track physical mailings and keep the board in sync.</p>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={requiredOnly}
              onChange={(event) => setRequiredOnly(event.target.checked)}
            />
            Required only
          </label>
        </div>
      </header>

      <div className="flex gap-3 text-sm">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            className={`rounded-full px-4 py-2 ${
              status === tab ? 'bg-primary-600 text-white' : 'bg-slate-200 text-slate-600'
            }`}
            onClick={() => setStatus(tab)}
          >
            {tab === 'MAILED' ? 'History' : tab}
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {loading && <p className="text-sm text-slate-500">Loading paperwork…</p>}

      {status !== 'MAILED' && (
        <section className="space-y-6">
          {['required', 'optional'].map((groupKey) => {
            const groupItems = groupedItems[groupKey as 'required' | 'optional'];
            if (requiredOnly && groupKey === 'optional') {
              return null;
            }
            if (groupItems.length === 0) {
              return null;
            }
            return (
              <div key={groupKey}>
                <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-600">
                  <span>{groupKey === 'required' ? 'Required Mailings' : 'Optional Mailings'}</span>
                  {groupKey === 'required' && <span className="rounded bg-rose-100 px-2 py-0.5 text-xs text-rose-700">Priority</span>}
                </div>
                <div className="overflow-x-auto rounded border border-slate-200">
                  <table className="min-w-full divide-y divide-slate-200 text-sm">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="px-3 py-2 text-left font-semibold text-slate-500">Owner</th>
                        <th className="px-3 py-2 text-left font-semibold text-slate-500">Notice</th>
                        <th className="px-3 py-2 text-left font-semibold text-slate-500">Status</th>
                        <th className="px-3 py-2 text-left font-semibold text-slate-500">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {groupItems.map((item) => (
                        <tr key={item.id}>
                          <td className="px-3 py-3">
                            <p className="font-semibold text-slate-700">{item.owner_name}</p>
                            <p className="text-xs text-slate-500">{item.owner_address}</p>
                          </td>
                          <td className="px-3 py-3">
                            <p className="font-semibold text-slate-700">{item.subject}</p>
                            <p className="text-xs text-slate-500">{item.notice_type_code}</p>
                          </td>
                          <td className="px-3 py-3 text-sm text-slate-600">
                            {item.delivery_provider === 'CLICK2MAIL' ? (
                              <span>
                                Sent via Click2Mail{' '}
                                {item.provider_status ? (
                                  <span className="text-xs text-slate-500">({item.provider_status})</span>
                                ) : null}
                              </span>
                            ) : (
                              <>
                                {item.status === 'PENDING' && 'Pending'}
                                {item.status === 'CLAIMED' && (
                                  <span>
                                    Claimed by {item.claimed_by?.full_name || 'board member'}{' '}
                                    {item.claimed_at ? `on ${new Date(item.claimed_at).toLocaleDateString()}` : ''}
                                  </span>
                                )}
                              </>
                            )}
                          </td>
                          <td className="px-3 py-3 space-x-2 text-right text-xs">
                            <button
                              type="button"
                              className="rounded border border-slate-300 px-3 py-1 text-slate-600 hover:bg-slate-50"
                              onClick={() => handlePrint(item.id)}
                            >
                              Print
                            </button>
                            {item.pdf_available && (
                              <button
                                type="button"
                                className="rounded border border-slate-300 px-3 py-1 text-slate-600 hover:bg-slate-50"
                                onClick={() => window.open(getPaperworkDownloadUrl(item.id), '_blank')}
                              >
                                PDF
                              </button>
                            )}
                            {canManage && click2mailEnabled && item.status === 'PENDING' && item.delivery_provider !== 'CLICK2MAIL' && (
                              <button
                                type="button"
                                className="rounded border border-amber-500 px-3 py-1 text-amber-700 hover:bg-amber-50 disabled:opacity-60"
                                disabled={dispatchingId === item.id}
                                onClick={() => handleSendClick2Mail(item.id)}
                              >
                                {dispatchingId === item.id ? 'Sending…' : 'Send via Click2Mail'}
                              </button>
                            )}
                            {item.status === 'PENDING' && canManage && (
                              <button
                                type="button"
                                className="rounded bg-primary-600 px-3 py-1 text-white hover:bg-primary-500"
                                onClick={() => handleClaim(item.id)}
                              >
                                Claim
                              </button>
                            )}
                            {item.status === 'CLAIMED' && canManage && (
                              <button
                                type="button"
                                className="rounded bg-emerald-600 px-3 py-1 text-white hover:bg-emerald-500"
                                onClick={() => handleMail(item.id)}
                              >
                                Mark Mailed
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })}
        </section>
      )}

      {status === 'MAILED' && (
        <section className="rounded border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-3 py-2 text-left font-semibold text-slate-500">Owner</th>
                <th className="px-3 py-2 text-left font-semibold text-slate-500">Notice</th>
                <th className="px-3 py-2 text-left font-semibold text-slate-500">Mailed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((item) => (
                <tr key={item.id}>
                  <td className="px-3 py-2">
                    <p className="font-semibold text-slate-700">{item.owner_name}</p>
                    <p className="text-xs text-slate-500">{item.owner_address}</p>
                  </td>
                  <td className="px-3 py-2">
                    <p className="font-semibold text-slate-700">{item.subject}</p>
                    <p className="text-xs text-slate-500">{item.notice_type_code}</p>
                  </td>
                  <td className="px-3 py-2 text-sm text-slate-600">
                    <div className="flex flex-col gap-1">
                      <span>
                        {item.delivery_provider === 'CLICK2MAIL'
                          ? `Click2Mail ${item.provider_status ? `• ${item.provider_status}` : ''}`
                          : item.mailed_at
                            ? new Date(item.mailed_at).toLocaleString()
                            : '—'}
                      </span>
                      {item.pdf_available && (
                        <button
                          type="button"
                          className="w-fit rounded border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
                          onClick={() => window.open(getPaperworkDownloadUrl(item.id), '_blank')}
                        >
                          Download PDF
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
};

export default PaperworkPage;
