import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import Badge from '../components/Badge';
import FilePreview from '../components/FilePreview';
import Timeline, { TimelineEvent } from '../components/Timeline';
import { ARCCondition, ARCAttachment, ARCRequest, ARCStatus } from '../types';
import {
  useArcRequestsQuery,
  useCreateArcRequestMutation,
  useAddArcConditionMutation,
  useArcReviewersQuery,
  useReopenArcRequestMutation,
  useSubmitArcReviewMutation,
  useTransitionArcRequestMutation,
  useUploadArcAttachmentMutation,
} from '../features/arc/hooks';
import { useMyLinkedOwnersQuery, useOwnersQuery } from '../features/billing/hooks';
import { userHasAnyRole, userHasRole } from '../utils/roles';

const STATUS_LABELS: Record<ARCStatus, string> = {
  DRAFT: 'Draft',
  SUBMITTED: 'Submitted',
  IN_REVIEW: 'In Review',
  PASSED: 'Passed',
  FAILED: 'Failed',
  REVIEW_COMPLETE: 'Review Complete',
  ARCHIVED: 'Archived',
};

const STATUS_BADGE: Record<ARCStatus, string> = {
  DRAFT: 'bg-slate-200 text-slate-700',
  SUBMITTED: 'bg-blue-100 text-blue-700',
  IN_REVIEW: 'bg-indigo-100 text-indigo-700',
  PASSED: 'bg-emerald-100 text-emerald-700',
  FAILED: 'bg-rose-100 text-rose-700',
  REVIEW_COMPLETE: 'bg-teal-100 text-teal-700',
  ARCHIVED: 'bg-gray-200 text-gray-600',
};

const TRANSITIONS: Record<ARCStatus, ARCStatus[]> = {
  DRAFT: ['SUBMITTED'],
  SUBMITTED: ['IN_REVIEW'],
  IN_REVIEW: [],
  PASSED: ['ARCHIVED'],
  FAILED: ['ARCHIVED'],
  REVIEW_COMPLETE: ['ARCHIVED'],
  ARCHIVED: [],
};

const ARCPage: React.FC = () => {
  const { user } = useAuth();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const isHomeowner = useMemo(() => userHasRole(user, 'HOMEOWNER'), [user]);
  const canReview = useMemo(() => userHasAnyRole(user, ['ARC', 'BOARD']), [user]);
  const canViewStaff = useMemo(
    () => userHasAnyRole(user, ['ARC', 'BOARD', 'SYSADMIN', 'SECRETARY', 'TREASURER']),
    [user],
  );
  const canViewQueue = useMemo(
    () => userHasAnyRole(user, ['BOARD', 'SYSADMIN', 'SECRETARY', 'TREASURER']),
    [user],
  );
  const arcRequestsQuery = useArcRequestsQuery(statusFilter !== 'ALL' ? statusFilter : undefined);
  const requests = useMemo(() => arcRequestsQuery.data ?? [], [arcRequestsQuery.data]);
  const sortedRequests = useMemo(() => {
    const items = [...requests];
    items.sort((a, b) => {
      const aTime = new Date(a.created_at).getTime();
      const bTime = new Date(b.created_at).getTime();
      if (aTime !== bTime) {
        return bTime - aTime;
      }
      return b.id - a.id;
    });
    return items;
  }, [requests]);
  const loading = arcRequestsQuery.isLoading;
  const requestsError = arcRequestsQuery.isError ? 'Unable to load ARC requests.' : null;
  const createRequestMutation = useCreateArcRequestMutation();
  const transitionMutation = useTransitionArcRequestMutation();
  const reopenMutation = useReopenArcRequestMutation();
  const uploadAttachmentMutation = useUploadArcAttachmentMutation();
  const addConditionMutation = useAddArcConditionMutation();
  const submitReviewMutation = useSubmitArcReviewMutation();
  const reviewersQuery = useArcReviewersQuery(canReview);
  const ownersQuery = useOwnersQuery(canViewStaff);
  const linkedOwnersQuery = useMyLinkedOwnersQuery(isHomeowner && !canViewStaff);
  const owners = useMemo(() => ownersQuery.data ?? [], [ownersQuery.data]);
  const linkedOwners = useMemo(() => linkedOwnersQuery.data ?? [], [linkedOwnersQuery.data]);
  const ownersError = ownersQuery.isError && canViewStaff ? 'Unable to load owners.' : null;
  const linkedOwnersError =
    linkedOwnersQuery.isError && isHomeowner && !canViewStaff ? 'Unable to load linked owners.' : null;
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ title: '', project_type: '', description: '', owner_id: '' });
  const [transitionStatus, setTransitionStatus] = useState('');
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewDecision, setReviewDecision] = useState('');
  const [reviewOpen, setReviewOpen] = useState(false);
  const [commentText, setCommentText] = useState('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const combinedError = error ?? requestsError ?? ownersError ?? linkedOwnersError;

  const reportError = useCallback((message: string, err: unknown) => {
    console.error(message, err);
    setError(message);
  }, []);

  const selected = useMemo(() => {
    if (selectedId == null) return null;
    return sortedRequests.find((req) => req.id === selectedId) ?? null;
  }, [sortedRequests, selectedId]);

  const handleSelect = useCallback(
    (request: ARCRequest) => {
      setSelectedId(request.id);
      setTransitionStatus('');
      setReviewNotes('');
      setReviewDecision('');
      setReviewOpen(false);
      setCommentText('');
    },
    [],
  );

  useEffect(() => {
    if (!sortedRequests.length) {
      setSelectedId(null);
      return;
    }
    if (selectedId == null) {
      handleSelect(sortedRequests[0]);
      return;
    }
    if (!sortedRequests.some((request) => request.id === selectedId)) {
      handleSelect(sortedRequests[0]);
    }
  }, [sortedRequests, selectedId, handleSelect]);

  useEffect(() => {
    if (!isHomeowner || canViewStaff || linkedOwners.length === 0) return;
    if (form.owner_id) return;
    setForm((prev) => ({ ...prev, owner_id: String(linkedOwners[0].id) }));
  }, [isHomeowner, canViewStaff, linkedOwners, form.owner_id]);

  const filteredRequests = useMemo(() => {
    if (statusFilter === 'ALL') return sortedRequests;
    return sortedRequests.filter((req) => req.status === statusFilter);
  }, [sortedRequests, statusFilter]);

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const created = await createRequestMutation.mutateAsync({
        title: form.title,
        project_type: form.project_type || undefined,
        description: form.description || undefined,
        owner_id:
          (canViewStaff || (isHomeowner && !canViewStaff)) && form.owner_id ? Number(form.owner_id) : undefined,
      });
      setSuccess('ARC request created.');
      setSelectedId(created.id);
      setForm({ title: '', project_type: '', description: '', owner_id: '' });
    } catch (err) {
      reportError('Unable to create request.', err);
    } finally {
      setCreating(false);
    }
  };

  const handleTransition = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected || !transitionStatus) return;
    setError(null);
    try {
      await transitionMutation.mutateAsync({
        requestId: selected.id,
        payload: { target_status: transitionStatus },
      });
      setSuccess('Status updated.');
      setTransitionStatus('');
    } catch (err) {
      reportError('Unable to update status. Check permissions and required fields.', err);
    }
  };

  const handleSubmitDraft = async () => {
    if (!selected) return;
    setError(null);
    try {
      await transitionMutation.mutateAsync({
        requestId: selected.id,
        payload: { target_status: 'SUBMITTED' },
      });
      setSuccess('Request submitted.');
    } catch (err) {
      reportError('Unable to submit request.', err);
    }
  };

  const handleReviewRequest = async () => {
    if (!selected) return;
    setError(null);
    try {
      if (selected.status === 'SUBMITTED') {
        await transitionMutation.mutateAsync({
          requestId: selected.id,
          payload: { target_status: 'IN_REVIEW' },
        });
        setSuccess('Request marked as in review.');
      }
      setReviewOpen(true);
    } catch (err) {
      reportError('Unable to start review.', err);
    }
  };

  const handleReopen = async () => {
    if (!selected) return;
    setError(null);
    try {
      const reopened = await reopenMutation.mutateAsync({ requestId: selected.id });
      setSuccess('ARC request reopened.');
      setSelectedId(reopened.id);
    } catch (err) {
      reportError('Unable to reopen request.', err);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!selected || !event.target.files || event.target.files.length === 0) return;
    const file = event.target.files[0];
    try {
      await uploadAttachmentMutation.mutateAsync({ requestId: selected.id, file });
      setSuccess('Attachment uploaded.');
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      reportError('Unable to upload attachment.', err);
    }
  };

  const handleCommentSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected || !commentText.trim()) return;
    try {
      await addConditionMutation.mutateAsync({
        requestId: selected.id,
        payload: { text: commentText.trim(), condition_type: 'COMMENT' },
      });
      setCommentText('');
      setSuccess('Comment added.');
    } catch (err) {
      reportError('Unable to add comment.', err);
    }
  };

  const handleReviewSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected || !reviewDecision) return;
    try {
      await submitReviewMutation.mutateAsync({
        requestId: selected.id,
        payload: {
          decision: reviewDecision,
          notes: reviewNotes || undefined,
        },
      });
      setSuccess('Review submitted.');
      setReviewOpen(false);
    } catch (err) {
      reportError('Unable to submit review.', err);
    }
  };

  const allowedTransitions = useMemo(() => {
    if (!selected) return [];
    if (selected.status === 'DRAFT') return [];
    if (!canReview) return [];
    if (selected.status === 'SUBMITTED') return [];
    if (['IN_REVIEW', 'PASSED', 'FAILED'].includes(selected.status)) return [];
    return TRANSITIONS[selected.status] || [];
  }, [selected, canReview]);
  const conditions = useMemo(() => selected?.conditions ?? [], [selected]);
  const reviews = useMemo(() => selected?.reviews ?? [], [selected]);
  const reviewers = useMemo(() => reviewersQuery.data ?? [], [reviewersQuery.data]);
  const currentReview = useMemo(() => {
    if (!selected || !user) return null;
    return reviews.find((review) => review.reviewer_user_id === user.id) ?? null;
  }, [reviews, selected, user]);

  const canReopenRequest = useMemo(() => {
    if (!selected || !canReview) return false;
    return [
      'APPROVED',
      'APPROVED_WITH_CONDITIONS',
      'DENIED',
      'COMPLETED',
      'ARCHIVED',
      'PASSED',
      'FAILED',
    ].includes(selected.status);
  }, [selected, canReview]);
  const canSubmitDraft = useMemo(
    () => !!selected && selected.status === 'DRAFT' && (isHomeowner || canReview || canViewStaff),
    [selected, isHomeowner, canReview, canViewStaff],
  );
  const canReviewRequest = useMemo(() => {
    if (!selected || !canReview) return false;
    if (['SUBMITTED', 'IN_REVIEW'].includes(selected.status)) {
      return currentReview === null;
    }
    return false;
  }, [selected, canReview, currentReview]);
  const canComment = useMemo(() => isHomeowner || canReview, [isHomeowner, canReview]);
  const showReviewerNotes = useMemo(() => {
    if (!selected) return false;
    if (reviewOpen) return true;
    if (currentReview) return true;
    if (reviews.length > 0) return true;
    return ['PASSED', 'FAILED'].includes(selected.status);
  }, [selected, reviewOpen, currentReview, reviews.length]);

  useEffect(() => {
    if (!selected) return;
    setReviewDecision(currentReview?.decision ?? '');
    setReviewNotes(currentReview?.notes ?? '');
  }, [selected, currentReview]);

  const timelineEvents = useMemo<TimelineEvent[]>(() => {
    if (!selected) return [];
    const events: TimelineEvent[] = [];
    const push = (timestamp?: string | null, label?: string, description?: string, meta?: string) => {
      if (!timestamp || !label) return;
      events.push({ timestamp, label, description, meta });
    };

    push(selected.created_at, 'Request created', selected.description ?? undefined);
    push(selected.submitted_at, 'Submitted for review');
    push(selected.final_decision_at, 'Decision finalized', selected.decision_notes ?? undefined);
    push(selected.archived_at, 'Request archived');

    conditions.forEach((condition) => {
      push(
        condition.created_at,
        condition.condition_type === 'REQUIREMENT' ? 'Requirement added' : 'Comment added',
        condition.text,
      );
    });

    reviews.forEach((review) => {
      const meta = review.reviewer_name ? `Reviewer: ${review.reviewer_name}` : undefined;
      push(
        review.submitted_at,
        `Review submitted (${review.decision})`,
        review.notes ?? undefined,
        meta,
      );
    });

    if (selected.updated_at && selected.updated_at !== selected.created_at) {
      push(selected.updated_at, 'Last updated');
    }

    return events.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  }, [conditions, reviews, selected]);

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

      {combinedError && <p className="text-sm text-red-600">{combinedError}</p>}
      {success && <p className="text-sm text-green-600">{success}</p>}

      <div className="space-y-6">
        <section className="rounded border border-slate-200 p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-600">Submit an ARC Request</h3>
          <form className="space-y-3" onSubmit={handleCreate}>
            {(canViewStaff || (isHomeowner && !canViewStaff)) && (
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-600" htmlFor="owner-select">
                  {canViewStaff ? 'Owner' : 'Address'}
                </label>
                <select
                  id="owner-select"
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                  value={form.owner_id}
                  onChange={(event) => setForm((prev) => ({ ...prev, owner_id: event.target.value }))}
                  required
                >
                  <option value="">
                    {canViewStaff ? 'Select owner…' : linkedOwners.length > 0 ? 'Select address…' : 'Loading addresses…'}
                  </option>
                  {(canViewStaff ? owners : linkedOwners).map((owner) => (
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

        {canViewQueue && (
          <section className="rounded border border-slate-200">
            <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
              <h3 className="text-sm font-semibold text-slate-600">Request Queue</h3>
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
                        <span
                          className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_BADGE[request.status]}`}
                        >
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
        )}

        {selected ? (
          <section className="rounded border border-slate-200 p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-600">Review Request</h3>
            <header className="flex items-center justify-between gap-3">
              <div>
                <h4 className="text-sm font-semibold text-slate-600">{selected.title}</h4>
                <p className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <span>
                    {selected.owner.property_address || `Owner #${selected.owner.id}`} • Created{' '}
                    {new Date(selected.created_at).toLocaleDateString()}
                  </span>
                  {selected.owner.is_archived && <Badge tone="warning">Owner Archived</Badge>}
                  {selected.owner.is_rental && <Badge tone="info">Rental</Badge>}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {canReopenRequest && (
                  <button
                    type="button"
                    className="rounded border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                    onClick={handleReopen}
                    disabled={reopenMutation.isLoading}
                  >
                    {reopenMutation.isLoading ? 'Reopening…' : 'Reopen Request'}
                  </button>
                )}
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_BADGE[selected.status]}`}>
                  {STATUS_LABELS[selected.status]}
                </span>
              </div>
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
            {selected.reviewer_name && (
              <p className="mt-2 text-xs text-slate-500">Reviewer: {selected.reviewer_name}</p>
            )}

              <section className="mt-4">
                <h4 className="text-xs font-semibold uppercase text-slate-500">Timeline</h4>
                <div className="mt-2">
                  <Timeline events={timelineEvents} />
                </div>
              </section>

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
                  <div className="mt-2 space-y-3">
                    {selected.attachments.map((attachment: ARCAttachment) => (
                      <FilePreview
                        key={attachment.id}
                        name={attachment.original_filename}
                        storedPath={attachment.stored_filename}
                        uploadedAt={attachment.uploaded_at}
                        contentType={attachment.content_type}
                        sizeBytes={attachment.file_size}
                      />
                    ))}
                  </div>
                )}
              </section>

              <section className="mt-4">
                <h4 className="text-xs font-semibold uppercase text-slate-500">Comments & Conditions</h4>
                {conditions.length === 0 ? (
                  <p className="mt-2 text-xs text-slate-500">No comments yet.</p>
                ) : (
                  <ul className="mt-2 space-y-2 text-xs">
                    {conditions.map((condition: ARCCondition) => (
                      <li key={condition.id} className="rounded border border-slate-200 p-2">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-slate-600">{condition.condition_type}</span>
                          <span className="text-slate-500">
                            {new Date(condition.created_at).toLocaleString()}
                          </span>
                        </div>
                        <p className="mt-1 whitespace-pre-wrap text-slate-600">{condition.text}</p>
                      </li>
                    ))}
                  </ul>
                )}
                {canComment && (
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
                )}
                {canSubmitDraft && (
                  <div className="mt-3 flex justify-end">
                    <button
                      type="button"
                      className="rounded bg-primary-600 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white hover:bg-primary-500"
                      onClick={handleSubmitDraft}
                    >
                      Submit request
                    </button>
                  </div>
                )}
              </section>

              {showReviewerNotes && (
                <section className="mt-4 rounded border border-slate-200 p-3">
                  <h4 className="text-xs font-semibold uppercase text-slate-500">Reviewer Notes</h4>
                  {reviewers.length > 0 && (
                    <p className="mt-2 text-xs text-slate-500">
                      Eligible reviewers: {reviewers.map((reviewer) => reviewer.full_name || reviewer.email).join(', ')}
                    </p>
                  )}
                  {reviews.length === 0 ? (
                    <p className="mt-2 text-xs text-slate-500">No reviewer notes recorded.</p>
                  ) : (
                    <ul className="mt-2 space-y-2 text-xs">
                      {reviews.map((review) => (
                        <li key={review.id} className="rounded border border-slate-200 p-2">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-slate-600">
                              {review.decision === 'PASS' ? 'Pass' : 'Fail'}
                            </span>
                            <span className="text-slate-500">
                              {review.reviewer_name || 'Reviewer'} •{' '}
                              {new Date(review.submitted_at).toLocaleDateString()}
                            </span>
                          </div>
                          {review.notes && (
                            <p className="mt-1 whitespace-pre-wrap text-slate-600">{review.notes}</p>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                  {canReview &&
                    ['IN_REVIEW', 'SUBMITTED'].includes(selected.status) &&
                    (reviewOpen || currentReview) && (
                    <form className="mt-3 grid gap-2 sm:grid-cols-2" onSubmit={handleReviewSubmit}>
                      <div className="sm:col-span-1">
                        <label className="mb-1 block text-xs text-slate-500" htmlFor="review-decision">
                          Decision
                        </label>
                        <select
                          id="review-decision"
                          className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                          value={reviewDecision}
                          onChange={(event) => setReviewDecision(event.target.value)}
                          required
                        >
                          <option value="">Select decision…</option>
                          <option value="PASS">Pass</option>
                          <option value="FAIL">Fail</option>
                        </select>
                      </div>
                      <div className="sm:col-span-2">
                        <label className="mb-1 block text-xs text-slate-500" htmlFor="review-notes">
                          Notes
                        </label>
                        <textarea
                          id="review-notes"
                          className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                          rows={2}
                          value={reviewNotes}
                          onChange={(event) => setReviewNotes(event.target.value)}
                          placeholder="Provide reviewer notes..."
                        />
                      </div>
                      <div className="sm:col-span-2 flex justify-end">
                        <button
                          type="submit"
                          className="rounded bg-primary-600 px-3 py-2 text-xs font-semibold text-white hover:bg-primary-500 disabled:opacity-60"
                          disabled={!reviewDecision}
                        >
                          Submit
                        </button>
                      </div>
                    </form>
                  )}
                </section>
              )}

              {canReviewRequest && (
                <div className="mt-4 flex justify-end">
                  <button
                    type="button"
                    className="rounded bg-primary-600 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white hover:bg-primary-500 disabled:opacity-60"
                    onClick={handleReviewRequest}
                    disabled={transitionMutation.isLoading}
                  >
                    {transitionMutation.isLoading ? 'Starting review…' : 'Review'}
                  </button>
                </div>
              )}
          </section>
        ) : (
          <section className="rounded border border-dashed border-slate-200 p-4 text-sm text-slate-500">
            Select an ARC request to view details, attachments, comments, and reviewer notes.
          </section>
        )}
      </div>
    </div>
  );
};

export default ARCPage;
