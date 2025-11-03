import React, { useEffect, useMemo, useRef, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import {
  addARCCondition,
  createARCInspection,
  createARCRequest,
  fetchARCRequests,
  fetchOwners,
  resolveARCCondition,
  transitionARCRequest,
  uploadARCAttachment,
} from '../services/api';
import {
  ARCCondition,
  ARCInspection,
  ARCAttachment,
  ARCRequest,
  ARCStatus,
  Owner,
} from '../types';

const STATUS_LABELS: Record<ARCStatus, string> = {
  DRAFT: 'Draft',
  SUBMITTED: 'Submitted',
  IN_REVIEW: 'In Review',
  REVISION_REQUESTED: 'Revision Requested',
  APPROVED: 'Approved',
  APPROVED_WITH_CONDITIONS: 'Approved w/ Conditions',
  DENIED: 'Denied',
  COMPLETED: 'Completed',
  ARCHIVED: 'Archived',
};

const STATUS_BADGE: Record<ARCStatus, string> = {
  DRAFT: 'bg-slate-200 text-slate-700',
  SUBMITTED: 'bg-blue-100 text-blue-700',
  IN_REVIEW: 'bg-indigo-100 text-indigo-700',
  REVISION_REQUESTED: 'bg-amber-100 text-amber-700',
  APPROVED: 'bg-green-100 text-green-700',
  APPROVED_WITH_CONDITIONS: 'bg-emerald-100 text-emerald-700',
  DENIED: 'bg-rose-100 text-rose-700',
  COMPLETED: 'bg-teal-100 text-teal-700',
  ARCHIVED: 'bg-gray-200 text-gray-600',
};

const TRANSITIONS: Record<ARCStatus, ARCStatus[]> = {
  DRAFT: ['SUBMITTED', 'ARCHIVED'],
  SUBMITTED: ['IN_REVIEW', 'ARCHIVED'],
  IN_REVIEW: ['REVISION_REQUESTED', 'APPROVED', 'APPROVED_WITH_CONDITIONS', 'DENIED'],
  REVISION_REQUESTED: ['SUBMITTED', 'ARCHIVED'],
  APPROVED: ['COMPLETED', 'ARCHIVED'],
  APPROVED_WITH_CONDITIONS: ['COMPLETED', 'ARCHIVED'],
  DENIED: ['ARCHIVED'],
  COMPLETED: ['ARCHIVED'],
  ARCHIVED: [],
};

const ARCPage: React.FC = () => {
  const { user } = useAuth();
  const [requests, setRequests] = useState<ARCRequest[]>([]);
  const [selected, setSelected] = useState<ARCRequest | null>(null);
  const [owners, setOwners] = useState<Owner[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ title: '', project_type: '', description: '', owner_id: '' });
  const [transitionStatus, setTransitionStatus] = useState('');
  const [transitionNotes, setTransitionNotes] = useState('');
  const [reviewerId, setReviewerId] = useState('');
  const [inspectionDate, setInspectionDate] = useState('');
  const [inspectionNotes, setInspectionNotes] = useState('');
  const [inspectionResult, setInspectionResult] = useState('');
  const [commentText, setCommentText] = useState('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const isHomeowner = user?.role.name === 'HOMEOWNER';
  const canReview = ['ARC', 'BOARD', 'SYSADMIN', 'SECRETARY'].includes(user?.role.name ?? '');

  const loadRequests = async () => {
    try {
      setLoading(true);
      const data = await fetchARCRequests(statusFilter !== 'ALL' ? statusFilter : undefined);
      setRequests(data);
      if (selected) {
        const refreshed = data.find((item) => item.id === selected.id);
        setSelected(refreshed ?? null);
      }
    } catch (err) {
      setError('Unable to load ARC requests.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadRequests();
  }, [statusFilter]);

  useEffect(() => {
    const init = async () => {
      if (canReview) {
        try {
          const ownerList = await fetchOwners();
          setOwners(ownerList);
        } catch (err) {
          setError('Unable to load owners.');
        }
      }
    };
    void init();
  }, [canReview]);

  const filteredRequests = useMemo(() => {
    if (statusFilter === 'ALL') return requests;
    return requests.filter((req) => req.status === statusFilter);
  }, [requests, statusFilter]);

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    setCreating(true);
    setError(null);
    try {
      await createARCRequest({
        title: form.title,
        project_type: form.project_type || undefined,
        description: form.description || undefined,
        owner_id: canReview && form.owner_id ? Number(form.owner_id) : undefined,
      });
      setSuccess('ARC request created.');
      setForm({ title: '', project_type: '', description: '', owner_id: '' });
      await loadRequests();
    } catch (err) {
      setError('Unable to create request.');
    } finally {
      setCreating(false);
    }
  };

  const handleSelect = (request: ARCRequest) => {
    setSelected(request);
    setTransitionStatus('');
    setTransitionNotes('');
    setReviewerId(request.reviewer_user_id ? String(request.reviewer_user_id) : '');
    setInspectionDate('');
    setInspectionNotes('');
    setInspectionResult('');
    setCommentText('');
  };

  const handleTransition = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected || !transitionStatus) return;
    setError(null);
    try {
      await transitionARCRequest(selected.id, {
        target_status: transitionStatus,
        reviewer_user_id: reviewerId ? Number(reviewerId) : undefined,
        notes: transitionNotes || undefined,
      });
      setSuccess('Status updated.');
      await loadRequests();
      const refreshed = requests.find((item) => item.id === selected.id);
      if (refreshed) handleSelect(refreshed);
    } catch (err) {
      setError('Unable to update status. Check permissions and required fields.');
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!selected || !event.target.files || event.target.files.length === 0) return;
    const file = event.target.files[0];
    try {
      await uploadARCAttachment(selected.id, file);
      setSuccess('Attachment uploaded.');
      if (fileInputRef.current) fileInputRef.current.value = '';
      await loadRequests();
      const refreshed = requests.find((item) => item.id === selected.id);
      if (refreshed) handleSelect(refreshed);
    } catch (err) {
      setError('Unable to upload attachment.');
    }
  };

  const handleCommentSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected || !commentText.trim()) return;
    try {
      await addARCCondition(selected.id, { text: commentText.trim(), condition_type: 'COMMENT' });
      setCommentText('');
      setSuccess('Comment added.');
      await loadRequests();
      const refreshed = requests.find((item) => item.id === selected.id);
      if (refreshed) handleSelect(refreshed);
    } catch (err) {
      setError('Unable to add comment.');
    }
  };

  const handleConditionToggle = async (condition: ARCCondition) => {
    if (!selected) return;
    try {
      await resolveARCCondition(selected.id, condition.id, condition.status === 'OPEN' ? 'RESOLVED' : 'OPEN');
      setSuccess('Condition updated.');
      await loadRequests();
      const refreshed = requests.find((item) => item.id === selected.id);
      if (refreshed) handleSelect(refreshed);
    } catch (err) {
      setError('Unable to update condition.');
    }
  };

  const handleInspectionCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    try {
      await createARCInspection(selected.id, {
        scheduled_date: inspectionDate || undefined,
        result: inspectionResult || undefined,
        notes: inspectionNotes || undefined,
      });
      setInspectionDate('');
      setInspectionNotes('');
      setInspectionResult('');
      setSuccess('Inspection recorded.');
      await loadRequests();
      const refreshed = requests.find((item) => item.id === selected.id);
      if (refreshed) handleSelect(refreshed);
    } catch (err) {
      setError('Unable to add inspection.');
    }
  };

  const allowedTransitions = useMemo(() => {
    if (!selected) return [];
    const list = TRANSITIONS[selected.status] || [];
    if (isHomeowner) {
      return list.filter((status) => ['SUBMITTED', 'ARCHIVED'].includes(status));
    }
    return list;
  }, [selected, isHomeowner]);

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-primary-600">ARC Requests</h2>
          <p className="text-sm text-slate-500">Submit architectural changes and track review status.</p>
        </div>
        <div>
          <label className="mr-2 text-sm text-slate-600" htmlFor="status-filter">
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
      </header>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {success && <p className="text-sm text-green-600">{success}</p>}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded border border-slate-200">
          <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
            <h3 className="text-sm font-semibold text-slate-600">Requests</h3>
          </div>
          <div className="max-h-[480px] overflow-y-auto">
            {loading ? (
              <p className="p-4 text-sm text-slate-500">Loading ARC requests…</p>
            ) : filteredRequests.length === 0 ? (
              <p className="p-4 text-sm text-slate-500">No records for the selected filter.</p>
            ) : (
              <ul className="divide-y divide-slate-200">
                {filteredRequests.map((request) => (
                  <li
                    key={request.id}
                    className={`cursor-pointer px-4 py-3 hover:bg-primary-50 ${
                      selected?.id === request.id ? 'bg-primary-50' : ''
                    }`}
                    onClick={() => handleSelect(request)}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-semibold text-slate-700">{request.title}</p>
                        <p className="text-xs text-slate-500">
                          {request.project_type || 'General'} • {new Date(request.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_BADGE[request.status]}`}>
                        {STATUS_LABELS[request.status]}
                      </span>
                    </div>
                    {request.description && (
                      <p className="mt-2 line-clamp-2 text-sm text-slate-600">{request.description}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <div className="space-y-6">
          <section className="rounded border border-slate-200 p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-600">
              {isHomeowner ? 'New ARC Request' : 'Submit on behalf of owner'}
            </h3>
            <form className="space-y-3" onSubmit={handleCreate}>
              {canReview && (
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-600" htmlFor="owner-select">
                    Owner
                  </label>
                  <select
                    id="owner-select"
                    className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                    value={form.owner_id}
                    onChange={(event) => setForm((prev) => ({ ...prev, owner_id: event.target.value }))}
                    required
                  >
                    <option value="">Select owner…</option>
                    {owners.map((owner) => (
                      <option key={owner.id} value={owner.id}>
                        {owner.property_address || `Owner #${owner.id}`} • {owner.primary_name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-600" htmlFor="request-title">
                  Project Title
                </label>
                <input
                  id="request-title"
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                  value={form.title}
                  onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-600" htmlFor="request-type">
                  Project Type
                </label>
                <input
                  id="request-type"
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                  value={form.project_type}
                  onChange={(event) => setForm((prev) => ({ ...prev, project_type: event.target.value }))}
                  placeholder="Fencing, landscaping, exterior paint…"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-600" htmlFor="request-description">
                  Description
                </label>
                <textarea
                  id="request-description"
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                  rows={3}
                  value={form.description}
                  onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
                  placeholder="Describe your project…"
                />
              </div>
              <button
                type="submit"
                className="rounded bg-primary-600 px-3 py-2 text-sm font-semibold text-white hover:bg-primary-500 disabled:opacity-60"
                disabled={creating}
              >
                {creating ? 'Submitting…' : 'Create Request'}
              </button>
            </form>
          </section>

          {selected ? (
            <section className="rounded border border-slate-200 p-4">
              <header className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-slate-600">{selected.title}</h3>
                  <p className="text-xs text-slate-500">
                    {selected.owner.property_address || `Owner #${selected.owner.id}`} • Created {new Date(selected.created_at).toLocaleDateString()}
                  </p>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_BADGE[selected.status]}`}>
                  {STATUS_LABELS[selected.status]}
                </span>
              </header>

              {selected.description && (
                <p className="mt-3 whitespace-pre-wrap text-sm text-slate-700">{selected.description}</p>
              )}
              {selected.project_type && (
                <p className="mt-2 text-xs text-slate-500">Project Type: {selected.project_type}</p>
              )}
              {selected.decision_notes && (
                <p className="mt-2 whitespace-pre-wrap text-xs text-slate-600">Decision Notes: {selected.decision_notes}</p>
              )}

              {allowedTransitions.length > 0 && (
                <form className="mt-4 space-y-3 rounded border border-slate-200 p-3" onSubmit={handleTransition}>
                  <h4 className="text-xs font-semibold uppercase text-slate-500">Transition</h4>
                  <div>
                    <label className="mb-1 block text-xs text-slate-500" htmlFor="arc-next-status">
                      Next Status
                    </label>
                    <select
                      id="arc-next-status"
                      className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                      value={transitionStatus}
                      onChange={(event) => setTransitionStatus(event.target.value)}
                      required
                    >
                      <option value="">Select status…</option>
                      {allowedTransitions.map((status) => (
                        <option key={status} value={status}>
                          {STATUS_LABELS[status]}
                        </option>
                      ))}
                    </select>
                  </div>
                  {canReview && (
                    <div>
                      <label className="mb-1 block text-xs text-slate-500" htmlFor="arc-reviewer">
                        Reviewer (optional)
                      </label>
                      <input
                        id="arc-reviewer"
                        className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                        value={reviewerId}
                        onChange={(event) => setReviewerId(event.target.value)}
                        placeholder="User ID"
                      />
                    </div>
                  )}
                  <div>
                    <label className="mb-1 block text-xs text-slate-500" htmlFor="arc-notes">
                      Notes
                    </label>
                    <textarea
                      id="arc-notes"
                      rows={2}
                      className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                      value={transitionNotes}
                      onChange={(event) => setTransitionNotes(event.target.value)}
                    />
                  </div>
                  <button
                    type="submit"
                    className="rounded bg-primary-600 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-white hover:bg-primary-500"
                  >
                    Apply Transition
                  </button>
                </form>
              )}

              <section className="mt-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-semibold uppercase text-slate-500">Attachments</h4>
                  <input
                    ref={fileInputRef}
                    type="file"
                    className="text-xs"
                    onChange={handleFileUpload}
                  />
                </div>
                {selected.attachments.length === 0 ? (
                  <p className="mt-2 text-xs text-slate-500">No files uploaded.</p>
                ) : (
                  <ul className="mt-2 space-y-2 text-xs">
                    {selected.attachments.map((attachment: ARCAttachment) => (
                      <li key={attachment.id} className="rounded border border-slate-200 p-2">
                        <span className="font-semibold text-slate-600">{attachment.original_filename}</span>
                        <span className="ml-2 text-slate-500">
                          {new Date(attachment.uploaded_at).toLocaleString()}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="mt-4">
                <h4 className="text-xs font-semibold uppercase text-slate-500">Comments & Conditions</h4>
                {selected.conditions.length === 0 ? (
                  <p className="mt-2 text-xs text-slate-500">No comments yet.</p>
                ) : (
                  <ul className="mt-2 space-y-2 text-xs">
                    {selected.conditions.map((condition: ARCCondition) => (
                      <li key={condition.id} className="rounded border border-slate-200 p-2">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-slate-600">{condition.condition_type}</span>
                          <span className="text-slate-500">
                            {new Date(condition.created_at).toLocaleString()}
                          </span>
                        </div>
                        <p className="mt-1 whitespace-pre-wrap text-slate-600">{condition.text}</p>
                        <div className="mt-1 flex items-center justify-between text-[10px] uppercase tracking-wide">
                          <span
                            className={
                              condition.status === 'RESOLVED'
                                ? 'text-green-600'
                                : 'text-amber-600'
                            }
                          >
                            {condition.status}
                          </span>
                          {canReview && (
                            <button
                              type="button"
                              className="rounded border border-slate-300 px-2 py-1"
                              onClick={() => handleConditionToggle(condition)}
                            >
                              {condition.status === 'OPEN' ? 'Mark Resolved' : 'Reopen'}
                            </button>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
                <form className="mt-3 flex gap-2" onSubmit={handleCommentSubmit}>
                  <input
                    className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm"
                    placeholder="Add comment..."
                    value={commentText}
                    onChange={(event) => setCommentText(event.target.value)}
                  />
                  <button
                    type="submit"
                    className="rounded bg-primary-600 px-3 py-2 text-xs font-semibold text-white hover:bg-primary-500 disabled:opacity-60"
                    disabled={!commentText.trim()}
                  >
                    Post
                  </button>
                </form>
              </section>

              {canReview && (
                <section className="mt-4 rounded border border-slate-200 p-3">
                  <h4 className="text-xs font-semibold uppercase text-slate-500">Inspections</h4>
                  {selected.inspections.length === 0 ? (
                    <p className="mt-2 text-xs text-slate-500">No inspections recorded.</p>
                  ) : (
                    <ul className="mt-2 space-y-2 text-xs">
                      {selected.inspections.map((inspection: ARCInspection) => (
                        <li key={inspection.id} className="rounded border border-slate-200 p-2">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-slate-600">
                              {inspection.result ?? 'Scheduled'}
                            </span>
                            <span className="text-slate-500">
                              {inspection.scheduled_date
                                ? new Date(inspection.scheduled_date).toLocaleDateString()
                                : 'Pending'}
                            </span>
                          </div>
                          {inspection.notes && (
                            <p className="mt-1 whitespace-pre-wrap text-slate-600">{inspection.notes}</p>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                  <form className="mt-3 grid gap-2 sm:grid-cols-2" onSubmit={handleInspectionCreate}>
                    <div className="sm:col-span-1">
                      <label className="mb-1 block text-xs text-slate-500" htmlFor="inspection-date">
                        Scheduled Date
                      </label>
                      <input
                        id="inspection-date"
                        type="date"
                        className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                        value={inspectionDate}
                        onChange={(event) => setInspectionDate(event.target.value)}
                      />
                    </div>
                    <div className="sm:col-span-1">
                      <label className="mb-1 block text-xs text-slate-500" htmlFor="inspection-result">
                        Result
                      </label>
                      <input
                        id="inspection-result"
                        className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                        value={inspectionResult}
                        onChange={(event) => setInspectionResult(event.target.value)}
                        placeholder="Passed / Failed / N/A"
                      />
                    </div>
                    <div className="sm:col-span-2">
                      <label className="mb-1 block text-xs text-slate-500" htmlFor="inspection-notes">
                        Notes
                      </label>
                      <textarea
                        id="inspection-notes"
                        className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                        rows={2}
                        value={inspectionNotes}
                        onChange={(event) => setInspectionNotes(event.target.value)}
                        placeholder="Enter inspection notes..."
                      />
                    </div>
                    <div className="sm:col-span-2 flex justify-end">
                      <button
                        type="submit"
                        className="rounded bg-primary-600 px-3 py-2 text-xs font-semibold text-white hover:bg-primary-500"
                      >
                        Record Inspection
                      </button>
                    </div>
                  </form>
                </section>
              )}
            </section>
          ) : (
            <section className="rounded border border-dashed border-slate-200 p-4 text-sm text-slate-500">
              Select an ARC request to view details, attachments, comments, and inspections.
            </section>
          )}
        </div>
      </div>
    </div>
  );
};

export default ARCPage;
