import React, { useCallback, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import { getPaperworkPrintUrl, getPaperworkDownloadUrl } from '../services/api';
import { userHasAnyRole } from '../utils/roles';
import {
  useClaimPaperworkMutation,
  useDispatchPaperworkMutation,
  useMailPaperworkMutation,
  usePaperworkFeaturesQuery,
  usePaperworkQuery,
} from '../features/paperwork/hooks';

const BOARD_ROLES = ['BOARD', 'TREASURER', 'SECRETARY', 'SYSADMIN'];
const STATUS_TABS = ['PENDING', 'CLAIMED', 'MAILED'] as const;
const DELIVERY_METHODS = ['STANDARD_MAIL', 'CERTIFIED_MAIL'] as const;

type StatusFilter = typeof STATUS_TABS[number];
type DeliveryMethod = typeof DELIVERY_METHODS[number];
type DeliverySelectionState = Record<number, DeliveryMethod>;

const DELIVERY_METHOD_LABELS: Record<DeliveryMethod, string> = {
  STANDARD_MAIL: 'Standard mail (Click2Mail)',
  CERTIFIED_MAIL: 'Certified mail',
};

const PaperworkPage: React.FC = () => {
  const { user } = useAuth();
  const canManage = useMemo(() => userHasAnyRole(user, BOARD_ROLES), [user]);
  const [status, setStatus] = useState<StatusFilter>('PENDING');
  const [requiredOnly, setRequiredOnly] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [dispatchingId, setDispatchingId] = useState<number | null>(null);
  const [deliverySelections, setDeliverySelections] = useState<DeliverySelectionState>({});
  const logError = useCallback((message: string, err: unknown) => {
    console.error(message, err);
  }, []);
  const paperworkQuery = usePaperworkQuery(status, requiredOnly);
  const paperworkFeaturesQuery = usePaperworkFeaturesQuery();
  const items = useMemo(() => paperworkQuery.data ?? [], [paperworkQuery.data]);
  const loading = paperworkQuery.isLoading;
  const queryError = paperworkQuery.isError ? 'Unable to load paperwork.' : null;
  const click2mailEnabled = Boolean(paperworkFeaturesQuery.data?.click2mail_enabled);
  const certifiedMailEnabled = Boolean(paperworkFeaturesQuery.data?.certified_mail_enabled);
  const effectiveError = actionError ?? queryError;
  const claimMutation = useClaimPaperworkMutation();
  const mailMutation = useMailPaperworkMutation();
  const dispatchMutation = useDispatchPaperworkMutation();
  const deliveryOptions = useMemo(
    () =>
      DELIVERY_METHODS.filter((method) => {
        if (method === 'STANDARD_MAIL') return click2mailEnabled;
        if (method === 'CERTIFIED_MAIL') return certifiedMailEnabled;
        return false;
      }),
    [certifiedMailEnabled, click2mailEnabled],
  );

  const handleClaim = async (paperworkId: number) => {
    try {
      setActionError(null);
      await claimMutation.mutateAsync(paperworkId);
    } catch (err) {
      logError('Unable to claim item.', err);
      setActionError('Unable to claim item.');
    }
  };

  const handleMail = async (paperworkId: number) => {
    try {
      setActionError(null);
      await mailMutation.mutateAsync(paperworkId);
    } catch (err) {
      logError('Unable to mark mailed.', err);
      setActionError('Unable to mark mailed.');
    }
  };

  const handleDispatch = async (paperworkId: number, deliveryMethod: DeliveryMethod) => {
    setDispatchingId(paperworkId);
    setActionError(null);
    try {
      await dispatchMutation.mutateAsync({ paperworkId, delivery_method: deliveryMethod });
    } catch (err) {
      logError('Unable to dispatch paperwork.', err);
      setActionError('Unable to dispatch paperwork.');
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

  const getSelectedDeliveryMethod = (paperworkId: number): DeliveryMethod => {
    if (deliverySelections[paperworkId]) {
      return deliverySelections[paperworkId];
    }
    return deliveryOptions[0] ?? 'STANDARD_MAIL';
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-primary-600">USPS Mailings</h2>
          <p className="text-sm text-slate-500">
            Manage USPS mailings, draft packets, and board-required paper workflows.
          </p>
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

      <section className="rounded border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
        <h3 className="text-sm font-semibold text-slate-700">USPS Workflow (Draft)</h3>
        <p className="mt-2 text-xs text-slate-500">
          Draft USPS packets are automatically created for new homeowners. This workflow is intentionally stubby so we
          can return later to configure USPS integration, template selection, and certified mail handling.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-500">Packet template (stub)</label>
            <input
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              placeholder="USPS Welcome Packet Template"
              disabled
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-500">USPS submission (stub)</label>
            <button
              type="button"
              className="w-full rounded border border-slate-300 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-400"
              disabled
            >
              Submit to USPS (coming soon)
            </button>
          </div>
        </div>
      </section>

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

      {effectiveError && <p className="text-sm text-red-600">{effectiveError}</p>}
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
                            {item.status === 'PENDING' && 'Pending'}
                            {item.status === 'CLAIMED' && (
                              <span>
                                Claimed by {item.claimed_by?.full_name || 'board member'}{' '}
                                {item.claimed_at ? `on ${new Date(item.claimed_at).toLocaleDateString()}` : ''}
                              </span>
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
                            {canManage && item.status === 'PENDING' && deliveryOptions.length > 0 && (
                              <select
                                className="rounded border border-slate-300 px-2 py-1 text-slate-600"
                                value={getSelectedDeliveryMethod(item.id)}
                                onChange={(event) =>
                                  setDeliverySelections((prev) => ({
                                    ...prev,
                                    [item.id]: event.target.value as DeliveryMethod,
                                  }))
                                }
                              >
                                {deliveryOptions.map((method) => (
                                  <option key={method} value={method}>
                                    {DELIVERY_METHOD_LABELS[method]}
                                  </option>
                                ))}
                              </select>
                            )}
                            {canManage && item.status === 'PENDING' && deliveryOptions.length > 0 && (
                              <button
                                type="button"
                                className="rounded border border-amber-500 px-3 py-1 text-amber-700 hover:bg-amber-50 disabled:opacity-60"
                                disabled={dispatchingId === item.id}
                                onClick={() => handleDispatch(item.id, getSelectedDeliveryMethod(item.id))}
                              >
                                {dispatchingId === item.id
                                  ? 'Sending…'
                                  : `Send ${DELIVERY_METHOD_LABELS[getSelectedDeliveryMethod(item.id)]}`}
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
                        {item.delivery_method && DELIVERY_METHOD_LABELS[item.delivery_method as DeliveryMethod]
                          ? DELIVERY_METHOD_LABELS[item.delivery_method as DeliveryMethod]
                          : 'Manual mail'}
                        {item.delivery_status ? ` • ${item.delivery_status}` : ''}
                      </span>
                      {item.tracking_number && <span className="text-xs text-slate-500">Tracking: {item.tracking_number}</span>}
                      <span className="text-xs text-slate-500">
                        {item.mailed_at ? new Date(item.mailed_at).toLocaleString() : '—'}
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
