import React, { useCallback, useEffect, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import Badge from '../components/Badge';
import FilePreview from '../components/FilePreview';
import Timeline, { TimelineEvent } from '../components/Timeline';
import { Appeal, Violation, ViolationStatus } from '../types';
import { formatUserRoles, userHasAnyRole, userHasRole } from '../utils/roles';
import { useResidentsQuery } from '../features/owners/hooks';
import {
  useCreateViolationMutation,
  useFineSchedulesQuery,
  useSubmitAppealMutation,
  useTransitionViolationMutation,
  useViolationNoticesQuery,
  useViolationsQuery,
} from '../features/violations/hooks';

const STATUS_LABELS: Record<ViolationStatus, string> = {
  NEW: 'New',
  UNDER_REVIEW: 'Under Review',
  WARNING_SENT: 'Warning Sent',
  HEARING: 'Hearing Scheduled',
  FINE_ACTIVE: 'Fine Active',
  RESOLVED: 'Resolved',
  ARCHIVED: 'Archived',
};

const STATUS_BADGE: Record<ViolationStatus, string> = {
  NEW: 'bg-slate-200 text-slate-700',
  UNDER_REVIEW: 'bg-blue-100 text-blue-700',
  WARNING_SENT: 'bg-amber-100 text-amber-700',
  HEARING: 'bg-indigo-100 text-indigo-700',
  FINE_ACTIVE: 'bg-rose-100 text-rose-700',
  RESOLVED: 'bg-green-100 text-green-700',
  ARCHIVED: 'bg-gray-200 text-gray-600',
};

const ALLOWED_TRANSITIONS: Record<ViolationStatus, ViolationStatus[]> = {
  NEW: ['UNDER_REVIEW', 'ARCHIVED'],
  UNDER_REVIEW: ['WARNING_SENT', 'FINE_ACTIVE', 'ARCHIVED'],
  WARNING_SENT: ['HEARING', 'FINE_ACTIVE', 'RESOLVED'],
  HEARING: ['FINE_ACTIVE', 'RESOLVED'],
  FINE_ACTIVE: ['RESOLVED'],
  RESOLVED: ['ARCHIVED'],
  ARCHIVED: [],
};

const ViolationsPage: React.FC = () => {
  const { user } = useAuth();
  const isHomeowner = userHasRole(user, 'HOMEOWNER');
  const manageRoles = ['BOARD', 'SYSADMIN', 'SECRETARY', 'TREASURER', 'ATTORNEY'];
  const canManage = userHasAnyRole(user, manageRoles);
  const isHomeownerOnly = isHomeowner && !canManage;

  const [selectedViolationId, setSelectedViolationId] = useState<number | null>(null);
  const [appealText, setAppealText] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [createForm, setCreateForm] = useState({
    target: '',
    category: '',
    description: '',
    location: '',
    fine_schedule_id: '',
    due_date: '',
  });
  const [creating, setCreating] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState<boolean>(canManage);
  const [transitionStatus, setTransitionStatus] = useState<string>('');
  const [transitionNote, setTransitionNote] = useState('');
  const [transitionHearingDate, setTransitionHearingDate] = useState('');
  const [transitionFineAmount, setTransitionFineAmount] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const violationsFilters = useMemo(() => {
    if (isHomeownerOnly) {
      return { mine: true };
    }
    if (statusFilter !== 'ALL') {
      return { status: statusFilter };
    }
    return {};
  }, [isHomeownerOnly, statusFilter]);

  const violationsQuery = useViolationsQuery(violationsFilters);
  const violations = useMemo(() => violationsQuery.data ?? [], [violationsQuery.data]);
  const selectedViolation = useMemo(
    () => (selectedViolationId ? violations.find((item) => item.id === selectedViolationId) ?? null : null),
    [selectedViolationId, violations],
  );

  const fineSchedulesQuery = useFineSchedulesQuery(canManage);
  const fineSchedules = useMemo(() => fineSchedulesQuery.data ?? [], [fineSchedulesQuery.data]);
  const residentsQuery = useResidentsQuery();
  const residents = useMemo(() => residentsQuery.data ?? [], [residentsQuery.data]);
  const noticesQuery = useViolationNoticesQuery(selectedViolation?.id ?? null);
  const notices = useMemo(() => noticesQuery.data ?? [], [noticesQuery.data]);

  const createViolationMutation = useCreateViolationMutation();
  const transitionMutation = useTransitionViolationMutation();
  const submitAppealMutation = useSubmitAppealMutation();

  const loading = violationsQuery.isLoading;
  const violationsError = violationsQuery.isError ? 'Unable to load violations.' : null;
  const noticesLoading = noticesQuery.isLoading;
  const combinedError = error ?? violationsError;
  const logError = useCallback((message: string, err: unknown) => {
    console.error(message, err);
  }, []);

  const residentOptions = useMemo(() => {
    if (!canManage) return [];
    const options: { value: string; label: string }[] = [];
    residents.forEach((resident) => {
      const { owner, user } = resident;
      if (owner?.is_archived) {
        return;
      }
      if (owner) {
        const propertyLabel = owner.property_address
          ? owner.property_address
          : `Owner #${owner.id}`;
        const ownerLabel = `${propertyLabel} • ${owner.primary_name}`;
        if (user) {
          options.push({
            value: `owner:${owner.id}`,
            label: `${ownerLabel} — ${user.email} [${formatUserRoles(user)}]`,
          });
        } else {
          options.push({
            value: `owner:${owner.id}`,
            label: `${ownerLabel} — Owner record (no linked login)`,
          });
        }
      } else if (user) {
        const displayName = user.full_name && user.full_name.trim().length > 0 ? user.full_name : user.email;
        options.push({
          value: `user:${user.id}`,
          label: `Account — ${displayName} [${formatUserRoles(user)}]`,
        });
      }
    });
    return options.sort((a, b) => a.label.localeCompare(b.label));
  }, [residents, canManage]);

  useEffect(() => {
    if (canManage && !createForm.target && residentOptions.length > 0) {
      setCreateForm((prev) => ({ ...prev, target: residentOptions[0].value }));
    }
  }, [residentOptions, createForm.target, canManage]);

  useEffect(() => {
    if (canManage && fineSchedules.length > 0 && !createForm.fine_schedule_id) {
      setCreateForm((prev) => ({
        ...prev,
        fine_schedule_id: prev.fine_schedule_id || String(fineSchedules[0].id),
      }));
    }
  }, [canManage, fineSchedules, createForm.fine_schedule_id]);

  useEffect(() => {
    if (!canManage) {
      setShowCreateForm(false);
    }
  }, [canManage]);

  useEffect(() => {
    if (!selectedViolationId && violations.length > 0) {
      setSelectedViolationId(violations[0].id);
      return;
    }
    if (selectedViolationId) {
      const exists = violations.some((violation) => violation.id === selectedViolationId);
      if (!exists) {
        setSelectedViolationId(violations[0]?.id ?? null);
      }
    }
  }, [violations, selectedViolationId]);

  const handleSelectViolation = (violation: Violation) => {
    setSelectedViolationId(violation.id);
    setTransitionStatus('');
    setTransitionNote('');
    setTransitionHearingDate('');
    setTransitionFineAmount('');
    setAppealText('');
  };

  const violationTimeline = useMemo<TimelineEvent[]>(() => {
    if (!selectedViolation) return [];
    const events: TimelineEvent[] = [];
    const push = (timestamp?: string | null, label?: string, description?: string, meta?: string) => {
      if (!timestamp || !label) return;
      events.push({ timestamp, label, description, meta });
    };

    push(selectedViolation.opened_at, 'Violation created', selectedViolation.description ?? undefined);
    push(selectedViolation.due_date, 'Due date set');
    push(selectedViolation.hearing_date, 'Hearing scheduled', undefined, selectedViolation.location ?? undefined);

  notices.forEach((notice) => {
      const templateLabel =
        STATUS_LABELS[notice.template_key as ViolationStatus] ?? notice.template_key;
      push(
        notice.created_at,
        `Notice sent (${templateLabel})`,
        notice.subject,
        notice.template_key,
      );
    });

    selectedViolation.appeals.forEach((appeal) => {
      push(appeal.submitted_at, 'Appeal submitted', appeal.reason, `Status: ${appeal.status}`);
      if (appeal.decided_at) {
        push(appeal.decided_at, 'Appeal decided', appeal.decision_notes ?? undefined);
      }
    });

    if (selectedViolation.updated_at && selectedViolation.updated_at !== selectedViolation.opened_at) {
      push(selectedViolation.updated_at, `Status updated (${STATUS_LABELS[selectedViolation.status] ?? selectedViolation.status})`, selectedViolation.resolution_notes ?? undefined);
    }

    return events.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  }, [selectedViolation, notices]);

  const handleCreateViolation = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canManage) return;
    setCreating(true);
    setError(null);
    setSuccess(null);
    try {
      const selection = createForm.target;
      let ownerId: number | undefined;
      let userId: number | undefined;

      if (selection.startsWith('owner:')) {
        const parsed = Number(selection.split(':')[1]);
        if (!Number.isNaN(parsed)) {
          ownerId = parsed;
        }
      } else if (selection.startsWith('user:')) {
        const parsed = Number(selection.split(':')[1]);
        if (!Number.isNaN(parsed)) {
          userId = parsed;
        }
      }

      if (!ownerId && !userId) {
        setError('Select an owner or account before creating a violation.');
        setCreating(false);
        return;
      }

      await createViolationMutation.mutateAsync({
        owner_id: ownerId,
        user_id: userId,
        category: createForm.category,
        description: createForm.description,
        location: createForm.location || undefined,
        due_date: createForm.due_date || undefined,
        fine_schedule_id: createForm.fine_schedule_id ? Number(createForm.fine_schedule_id) : undefined,
      });
      setCreateForm({
        target: '',
        category: '',
        description: '',
        location: '',
        fine_schedule_id: fineSchedules.length > 0 ? String(fineSchedules[0].id) : '',
        due_date: '',
      });
      setSuccess('Violation created.');
    } catch (err) {
      logError('Unable to create violation.', err);
      setError('Unable to create violation. Ensure required fields are completed.');
    } finally {
      setCreating(false);
    }
  };

  const handleTransition = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedViolation || !transitionStatus) {
      return;
    }
    try {
      await transitionMutation.mutateAsync({
        violationId: selectedViolation.id,
        payload: {
          target_status: transitionStatus,
          note: transitionNote || undefined,
          hearing_date: transitionHearingDate || undefined,
          fine_amount: transitionFineAmount || undefined,
        },
      });
      setSuccess('Status updated.');
    } catch (err) {
      logError('Unable to update violation status.', err);
      setError('Unable to update status. Check required fields for the transition.');
    }
  };

  const handleAppealSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedViolation || !appealText.trim()) return;
    try {
      await submitAppealMutation.mutateAsync({ violationId: selectedViolation.id, message: appealText.trim() });
      setAppealText('');
      setSuccess('Appeal submitted.');
    } catch (err) {
      logError('Unable to submit appeal.', err);
      setError('Unable to submit appeal.');
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-primary-600">Covenant Violations</h2>
          <p className="text-sm text-slate-500">
            Track compliance actions, notices, hearings, and appeals.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {canManage && (
            <button
              type="button"
              className="rounded bg-primary-600 px-3 py-2 text-sm font-semibold text-white hover:bg-primary-500"
              onClick={() => setShowCreateForm((prev) => !prev)}
            >
              {showCreateForm ? 'Hide Report Form' : 'Report Violation'}
            </button>
          )}
          <div className="flex items-center gap-2">
            <label className="text-sm text-slate-600" htmlFor="status-filter">
              Filter
            </label>
            <select
              id="status-filter"
              className="rounded border border-slate-300 px-3 py-1 text-sm"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
            >
              <option value="ALL">All</option>
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </header>

      {combinedError && <p className="text-sm text-red-600">{combinedError}</p>}
      {success && <p className="text-sm text-green-600">{success}</p>}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded border border-slate-200">
          <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
            <h3 className="text-sm font-semibold text-slate-600">Violations</h3>
          </div>
          <div className="max-h-[480px] overflow-y-auto">
            {loading ? (
              <p className="p-4 text-sm text-slate-500">Loading violations…</p>
            ) : violations.length === 0 ? (
              <p className="p-4 text-sm text-slate-500">No violations found for the selected filter.</p>
            ) : (
              <ul className="divide-y divide-slate-200">
                {violations.map((violation) => (
                  <li
                    key={violation.id}
                    className={`cursor-pointer px-4 py-3 hover:bg-primary-50 ${
                      selectedViolation?.id === violation.id ? 'bg-primary-50' : ''
                    }`}
                    onClick={() => handleSelectViolation(violation)}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-semibold text-slate-700">
                          {violation.owner.property_address || `Owner #${violation.owner.id}`} • {violation.category}
                        </p>
                        <p className="text-xs text-slate-500">
                          Opened {new Date(violation.opened_at).toLocaleDateString()}
                        </p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_BADGE[violation.status]}`}>
                        {STATUS_LABELS[violation.status]}
                      </span>
                    </div>
                    {violation.description && (
                      <p className="mt-2 line-clamp-2 text-sm text-slate-600">{violation.description}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <div className="space-y-6">
          {canManage && !showCreateForm && (
            <section className="rounded border border-dashed border-slate-300 bg-slate-50/60 p-4 text-sm text-slate-600">
              Use <span className="font-semibold">Report Violation</span> to log a new case. You can still browse existing violations on the left.
            </section>
          )}

          {canManage && showCreateForm && (
            <section className="rounded border border-slate-200 p-4">
              <h3 className="mb-3 text-sm font-semibold text-slate-600">Create Violation</h3>
              {fineSchedulesQuery.isError && (
                <p className="text-sm text-red-600">Unable to load fine schedules.</p>
              )}
              {residentsQuery.isError && (
                <p className="text-sm text-red-600">Unable to load resident roster.</p>
              )}
              <form className="space-y-3" onSubmit={handleCreateViolation}>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-600" htmlFor="violation-target">
                    Owner / Account
                  </label>
                  <select
                    id="violation-target"
                    className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                    required
                    value={createForm.target}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, target: event.target.value }))}
                    disabled={residentOptions.length === 0}
                  >
                    {residentOptions.length === 0 && <option value="">No residents available</option>}
                    {residentOptions.length > 0 && <option value="">Select owner or account…</option>}
                    {residentOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  <p className="mt-1 text-xs text-slate-500">
                    Accounts without owner records will be assigned an owner automatically.
                  </p>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-600" htmlFor="category">
                    Category
                  </label>
                  <input
                    id="category"
                    className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                    required
                    value={createForm.category}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, category: event.target.value }))}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-600" htmlFor="description">
                    Description
                  </label>
                  <textarea
                    id="description"
                    className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                    rows={3}
                    value={createForm.description}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, description: event.target.value }))}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-xs font-semibold text-slate-600" htmlFor="location">
                      Location
                    </label>
                    <input
                      id="location"
                      className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                      value={createForm.location}
                      onChange={(event) => setCreateForm((prev) => ({ ...prev, location: event.target.value }))}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-semibold text-slate-600" htmlFor="due_date">
                      Due Date
                    </label>
                    <input
                      id="due_date"
                      type="date"
                      className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                      value={createForm.due_date}
                      onChange={(event) => setCreateForm((prev) => ({ ...prev, due_date: event.target.value }))}
                    />
                  </div>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-600" htmlFor="fine_schedule_id">
                    Fine Schedule
                  </label>
                  <select
                    id="fine_schedule_id"
                    className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                    value={createForm.fine_schedule_id}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, fine_schedule_id: event.target.value }))}
                  >
                    <option value="">None</option>
                    {fineSchedules.map((schedule) => (
                      <option key={schedule.id} value={schedule.id}>
                        {schedule.name}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  type="submit"
                  className="rounded bg-primary-600 px-3 py-2 text-sm font-semibold text-white hover:bg-primary-500 disabled:opacity-60"
                  disabled={creating}
                >
                  {creating ? 'Creating…' : 'Create Violation'}
                </button>
              </form>
            </section>
          )}

          {selectedViolation ? (
            <section className="rounded border border-slate-200 p-4">
              <header className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-slate-600">
                    Violation #{selectedViolation.id} • {selectedViolation.owner.property_address || `Owner #${selectedViolation.owner.id}`}
                  </h3>
                  <p className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <span>
                      {new Date(selectedViolation.opened_at).toLocaleString()} • Reported by{' '}
                      {selectedViolation.owner.primary_name}
                    </span>
                    {selectedViolation.owner.is_archived && <Badge tone="warning">Owner Archived</Badge>}
                  </p>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_BADGE[selectedViolation.status]}`}>
                  {STATUS_LABELS[selectedViolation.status]}
                </span>
              </header>

              {selectedViolation.description && (
                <p className="mt-3 whitespace-pre-wrap text-sm text-slate-700">{selectedViolation.description}</p>
              )}
              {selectedViolation.location && (
                <p className="mt-2 text-xs text-slate-500">Location: {selectedViolation.location}</p>
              )}
              {selectedViolation.due_date && (
                <p className="mt-1 text-xs text-amber-600">Due by: {new Date(selectedViolation.due_date).toLocaleDateString()}</p>
              )}
              {selectedViolation.hearing_date && (
                <p className="mt-1 text-xs text-indigo-600">
                  Hearing: {new Date(selectedViolation.hearing_date).toLocaleDateString()}
                </p>
              )}
              {selectedViolation.fine_amount && (
                <p className="mt-1 text-xs text-rose-600">Fine: ${Number(selectedViolation.fine_amount).toFixed(2)}</p>
              )}

              <section className="mt-4">
                <h4 className="text-xs font-semibold uppercase text-slate-500">Timeline</h4>
                <div className="mt-2">
                  <Timeline events={violationTimeline} />
                </div>
              </section>

              {canManage && ALLOWED_TRANSITIONS[selectedViolation.status].length > 0 && (
                <form className="mt-4 space-y-3 rounded border border-slate-200 p-3" onSubmit={handleTransition}>
                  <h4 className="text-xs font-semibold text-slate-600">Transition Status</h4>
                  <div>
                    <label className="mb-1 block text-xs text-slate-500" htmlFor="transition-status">
                      Next Status
                    </label>
                    <select
                      id="transition-status"
                      className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                      value={transitionStatus}
                      onChange={(event) => setTransitionStatus(event.target.value)}
                      required
                    >
                      <option value="">Select status…</option>
                      {ALLOWED_TRANSITIONS[selectedViolation.status].map((status) => (
                        <option key={status} value={status}>
                          {STATUS_LABELS[status]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-slate-500" htmlFor="transition-note">
                      Note (optional)
                    </label>
                    <textarea
                      id="transition-note"
                      rows={2}
                      className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                      value={transitionNote}
                      onChange={(event) => setTransitionNote(event.target.value)}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1 block text-xs text-slate-500" htmlFor="transition-hearing">
                        Hearing Date
                      </label>
                      <input
                        id="transition-hearing"
                        type="date"
                        className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                        value={transitionHearingDate}
                        onChange={(event) => setTransitionHearingDate(event.target.value)}
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs text-slate-500" htmlFor="transition-fine">
                        Fine Amount
                      </label>
                      <input
                        id="transition-fine"
                        type="number"
                        min="0"
                        step="0.01"
                        className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                        value={transitionFineAmount}
                        onChange={(event) => setTransitionFineAmount(event.target.value)}
                      />
                    </div>
                  </div>
                  <button
                    type="submit"
                    className="rounded bg-primary-600 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-white hover:bg-primary-500"
                  >
                    Update Status
                  </button>
                </form>
              )}

              <section className="mt-4">
                <h4 className="text-xs font-semibold uppercase text-slate-500">Notices</h4>
                {noticesQuery.isError ? (
                  <p className="text-xs text-red-600">Unable to load notices.</p>
                ) : noticesLoading ? (
                  <p className="text-xs text-slate-500">Loading notices…</p>
                ) : notices.length === 0 ? (
                  <p className="text-xs text-slate-500">No notices recorded.</p>
                ) : (
                  <div className="mt-2 space-y-3">
                    {notices.map((notice) =>
                      notice.pdf_path ? (
                        <FilePreview
                          key={notice.id}
                          name={notice.subject}
                          storedPath={notice.pdf_path}
                          uploadedAt={notice.created_at}
                          contentType="application/pdf"
                        />
                      ) : (
                        <div key={notice.id} className="rounded border border-slate-200 p-3 text-xs">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="font-semibold text-slate-600">{notice.subject}</span>
                            <span className="text-slate-500">
                              {new Date(notice.created_at).toLocaleDateString()} ({notice.template_key})
                            </span>
                          </div>
                          <p className="mt-1 whitespace-pre-wrap text-slate-600">{notice.body}</p>
                        </div>
                      ),
                    )}
                  </div>
                )}
              </section>

              {selectedViolation.appeals.length > 0 && (
                <section className="mt-4">
                  <h4 className="text-xs font-semibold uppercase text-slate-500">Appeals</h4>
                  <ul className="mt-2 space-y-2 text-xs">
                    {selectedViolation.appeals.map((appeal: Appeal) => (
                      <li key={appeal.id} className="rounded border border-slate-200 p-2">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-slate-600">{appeal.status}</span>
                          <span className="text-slate-500">
                            {new Date(appeal.submitted_at).toLocaleDateString()}
                          </span>
                        </div>
                        <p className="mt-1 whitespace-pre-wrap text-slate-600">{appeal.reason}</p>
                        {appeal.decision_notes && (
                          <p className="mt-1 whitespace-pre-wrap text-slate-500">
                            Decision: {appeal.decision_notes}
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {isHomeowner && (
                <form className="mt-4 space-y-3 rounded border border-slate-200 p-3" onSubmit={handleAppealSubmit}>
                  <h4 className="text-xs font-semibold text-slate-600">Submit Appeal</h4>
                  <textarea
                    className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                    rows={3}
                    placeholder="Enter your appeal details…"
                    value={appealText}
                    onChange={(event) => setAppealText(event.target.value)}
                  />
                  <button
                    type="submit"
                    className="rounded bg-primary-600 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-white hover:bg-primary-500 disabled:opacity-60"
                    disabled={!appealText.trim()}
                  >
                    Submit Appeal
                  </button>
                </form>
              )}
            </section>
          ) : (
            <section className="rounded border border-dashed border-slate-200 p-4 text-sm text-slate-500">
              Select a violation to see details, notices, and appeals.
            </section>
          )}
        </div>
      </div>
    </div>
  );
};

export default ViolationsPage;
