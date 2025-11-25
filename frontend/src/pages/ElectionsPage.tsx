import React, { useCallback, useEffect, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import { ElectionCandidate, ElectionStatus } from '../types';
import { formatUserRoles, userHasAnyRole } from '../utils/roles';
import { useOwnersQuery } from '../features/billing/hooks';
import {
  useAddCandidateMutation,
  useCreateElectionMutation,
  useDeleteCandidateMutation,
  useElectionBallotsQuery,
  useElectionDetailQuery,
  useElectionResultsExportMutation,
  useElectionStatsQuery,
  useElectionsQuery,
  useGenerateBallotsMutation,
  useSubmitElectionVoteMutation,
  useUpdateElectionMutation,
} from '../features/elections/hooks';

const MANAGER_ROLES = ['BOARD', 'SYSADMIN', 'SECRETARY', 'TREASURER', 'ATTORNEY'];

const statusBadge: Record<ElectionStatus, string> = {
  DRAFT: 'bg-slate-200 text-slate-700',
  SCHEDULED: 'bg-blue-100 text-blue-700',
  OPEN: 'bg-emerald-100 text-emerald-700',
  CLOSED: 'bg-slate-300 text-slate-700',
  ARCHIVED: 'bg-gray-200 text-gray-600',
};

const ElectionsPage: React.FC = () => {
  const { user } = useAuth();
  const isManager = userHasAnyRole(user, MANAGER_ROLES);
  const electionsQuery = useElectionsQuery();
  const elections = useMemo(() => electionsQuery.data ?? [], [electionsQuery.data]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const detailQuery = useElectionDetailQuery(selectedId);
  const detail = detailQuery.data ?? null;
  const ballotsQuery = useElectionBallotsQuery(selectedId, isManager);
  const ballots = useMemo(() => ballotsQuery.data ?? [], [ballotsQuery.data]);
  const statsQuery = useElectionStatsQuery(selectedId, isManager);
  const stats = statsQuery.data ?? null;
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const electionsError = electionsQuery.isError ? 'Unable to load elections.' : null;
  const detailError = selectedId != null && detailQuery.isError ? 'Unable to load election details.' : null;
  const ballotsError = isManager && ballotsQuery.isError ? 'Unable to load ballots.' : null;
  const statsError = isManager && statsQuery.isError ? 'Unable to load election stats.' : null;
  const ownersLoading = isManager && ownersQuery.isLoading;
  const ownersError = isManager && ownersQuery.isError ? 'Unable to load owners.' : null;
  const loading = electionsQuery.isLoading || (selectedId != null && detailQuery.isLoading);
  const combinedError = error ?? detailError ?? electionsError ?? ownersError ?? ballotsError ?? statsError;

  const [createForm, setCreateForm] = useState({
    title: '',
    description: '',
    opens_at: '',
    closes_at: '',
  });

  const [candidateForm, setCandidateForm] = useState({
    display_name: '',
    statement: '',
    owner_id: '',
  });
  const ownersQuery = useOwnersQuery(isManager);
  const owners = useMemo(() => ownersQuery.data ?? [], [ownersQuery.data]);
  const createElectionMutation = useCreateElectionMutation();
  const updateElectionMutation = useUpdateElectionMutation();
  const addCandidateMutation = useAddCandidateMutation();
  const deleteCandidateMutation = useDeleteCandidateMutation();
  const generateBallotsMutation = useGenerateBallotsMutation();
  const submitVoteMutation = useSubmitElectionVoteMutation();
  const exportResultsMutation = useElectionResultsExportMutation();
  const [statusForm, setStatusForm] = useState({
    status: 'DRAFT',
    opens_at: '',
    closes_at: '',
  });
  const [voteCandidateId, setVoteCandidateId] = useState<number | null>(null);
  const [writeInValue, setWriteInValue] = useState('');
  const [voteError, setVoteError] = useState<string | null>(null);
  const [voteFeedback, setVoteFeedback] = useState<string | null>(null);
  const [voteSubmitting, setVoteSubmitting] = useState(false);
  const logError = useCallback((message: string, err: unknown) => {
    console.error(message, err);
  }, []);

  useEffect(() => {
    if (elections.length === 0) {
      setSelectedId(null);
      return;
    }
    setSelectedId((current) => {
      if (current && elections.some((item) => item.id === current)) {
        return current;
      }
      return elections[0].id;
    });
  }, [elections]);

  useEffect(() => {
    if (!detail) {
      setStatusForm({ status: 'DRAFT', opens_at: '', closes_at: '' });
      return;
    }
    setStatusForm({
      status: detail.status,
      opens_at: detail.opens_at ? detail.opens_at.slice(0, 16) : '',
      closes_at: detail.closes_at ? detail.closes_at.slice(0, 16) : '',
    });
  }, [detail]);

  useEffect(() => {
    setVoteCandidateId(null);
    setWriteInValue('');
    setVoteError(null);
    setVoteFeedback(null);
  }, [detail?.id]);

  const handleSelectElection = useCallback((electionId: number) => {
    setStatus(null);
    setError(null);
    setSelectedId(electionId);
  }, []);

  const upcomingElections = useMemo(
    () => elections.filter((election) => ['DRAFT', 'SCHEDULED', 'OPEN'].includes(election.status)),
    [elections],
  );

  const closedElections = useMemo(
    () => elections.filter((election) => ['CLOSED', 'ARCHIVED'].includes(election.status)),
    [elections],
  );
  const myStatus = detail?.my_status ?? null;
  const alreadyVoted = Boolean(myStatus?.has_voted);
  const writeInResult = useMemo(() => {
    if (!detail) return null;
    return detail.results.find(
      (item) => item.candidate_id == null && (item.candidate_name ?? '').toLowerCase().includes('write'),
    );
  }, [detail]);

  const statsLoading = isManager && statsQuery.isLoading;
  const showStatsPanel = isManager && selectedId != null;

  const handleUpdateStatus = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!detail) return;
    setError(null);
    try {
      const updated = await updateElectionMutation.mutateAsync({
        electionId: detail.id,
        payload: {
        status: statusForm.status,
        opens_at: statusForm.opens_at || undefined,
        closes_at: statusForm.closes_at || undefined,
        },
      });
      setStatus('Election updated.');
      setStatusForm({
        status: updated.status,
        opens_at: updated.opens_at ? updated.opens_at.slice(0, 16) : '',
        closes_at: updated.closes_at ? updated.closes_at.slice(0, 16) : '',
      });
      await electionsQuery.refetch();
    } catch (err) {
      logError('Unable to update election.', err);
      setError('Unable to update election.');
    }
  };

  const handleCreateElection = async (event: React.FormEvent) => {
    event.preventDefault();
    setStatus(null);
    setError(null);
    if (!createForm.title.trim()) {
      setError('Title is required.');
      return;
    }
    try {
      const payload = {
        title: createForm.title.trim(),
        description: createForm.description.trim() || undefined,
        opens_at: createForm.opens_at || undefined,
        closes_at: createForm.closes_at || undefined,
      };
      const created = await createElectionMutation.mutateAsync(payload);
      setStatus('Election created.');
      setCreateForm({ title: '', description: '', opens_at: '', closes_at: '' });
      setSelectedId(created.id);
      await electionsQuery.refetch();
    } catch (err) {
      logError('Unable to create election.', err);
      setError('Unable to create election.');
    }
  };

  const handleAddCandidate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!detail) {
      return;
    }
    const ownerId = candidateForm.owner_id ? Number(candidateForm.owner_id) : undefined;
    const selectedOwner = ownerId ? owners.find((owner) => owner.id === ownerId) : undefined;
    const displayName = candidateForm.display_name.trim() || selectedOwner?.primary_name || '';
    if (!displayName) {
      setError('Candidate name is required.');
      return;
    }
    setError(null);
    try {
      await addCandidateMutation.mutateAsync({
        electionId: detail.id,
        payload: {
          display_name: displayName,
          statement: candidateForm.statement.trim() || undefined,
          owner_id: ownerId,
        },
      });
      setCandidateForm({ display_name: '', statement: '', owner_id: '' });
      setStatus('Candidate added.');
    } catch (err) {
      logError('Unable to add candidate.', err);
      setError('Unable to add candidate.');
    }
  };

  const handleDeleteCandidate = async (candidate: ElectionCandidate) => {
    if (!detail) return;
    const confirm = window.confirm(`Remove candidate ${candidate.display_name}?`);
    if (!confirm) return;
    try {
      await deleteCandidateMutation.mutateAsync({ electionId: detail.id, candidateId: candidate.id });
      setStatus('Candidate removed.');
    } catch (err) {
      logError('Unable to remove candidate.', err);
      setError('Unable to remove candidate.');
    }
  };

  const handleGenerateBallots = async () => {
    if (!detail) return;
    setError(null);
    try {
      await generateBallotsMutation.mutateAsync(detail.id);
      setStatus('Ballots generated.');
    } catch (err) {
      logError('Unable to generate ballots.', err);
      setError('Unable to generate ballots.');
    }
  };

  const handleExportResults = async () => {
    if (!selectedId) return;
    setError(null);
    try {
      const blob = await exportResultsMutation.mutateAsync(selectedId);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `election-${selectedId}-results.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setStatus('Election results exported.');
    } catch (err) {
      logError('Unable to export election results.', err);
      setError('Unable to export election results.');
    }
  };

  const handleOwnerChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const value = event.target.value;
    const owner = value ? owners.find((item) => item.id === Number(value)) : undefined;
    setCandidateForm((prev) => ({
      ...prev,
      owner_id: value,
      display_name: owner ? owner.primary_name : prev.display_name,
    }));
  };

  const handleSubmitVote = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!detail) return;
    const trimmedWriteIn = writeInValue.trim();
    if (voteCandidateId == null && !trimmedWriteIn) {
      setVoteError('Please select a candidate or enter a write-in.');
      return;
    }
    setVoteSubmitting(true);
    setVoteError(null);
    setVoteFeedback(null);
    try {
      await submitVoteMutation.mutateAsync({
        electionId: detail.id,
        payload: {
          candidate_id: voteCandidateId ?? undefined,
          write_in: trimmedWriteIn || undefined,
        },
      });
      setVoteFeedback('Thanks for casting your ballot.');
      setStatus('Vote recorded.');
      setVoteCandidateId(null);
      setWriteInValue('');
      await Promise.all([electionsQuery.refetch(), detailQuery.refetch()]);
    } catch (err) {
      logError('Unable to record your vote.', err);
      setVoteError('Unable to record your vote. Please try again.');
    } finally {
      setVoteSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-primary-600">Elections & Voting</h2>
          <p className="text-sm text-slate-500">
            Manage community elections, candidates, and ballot issuance.
          </p>
        </div>
        <div className="text-xs text-slate-500">{user ? `Roles: ${formatUserRoles(user)}` : ''}</div>
      </header>

      {combinedError && <p className="text-sm text-red-600">{combinedError}</p>}
      {status && <p className="text-sm text-green-600">{status}</p>}
      {loading && <p className="text-sm text-slate-500">Loading elections…</p>}

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          <div className="rounded border border-slate-200">
            <div className="border-b border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
              Upcoming Elections
            </div>
            {upcomingElections.length === 0 ? (
              <p className="px-3 py-4 text-sm text-slate-500">No scheduled elections.</p>
            ) : (
              <ul className="divide-y divide-slate-200">
                {upcomingElections.map((election) => (
                  <li
                    key={election.id}
                    className={`cursor-pointer px-3 py-3 hover:bg-primary-50 ${selectedId === election.id ? 'bg-primary-50' : ''}`}
                    onClick={() => handleSelectElection(election.id)}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-semibold text-slate-700">{election.title}</p>
                        <p className="text-xs text-slate-500">
                          Opens {election.opens_at ? new Date(election.opens_at).toLocaleString() : 'TBD'}
                        </p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusBadge[election.status]}`}>
                        {election.status}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded border border-slate-200">
            <div className="border-b border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
              Results & Archived
            </div>
            {closedElections.length === 0 ? (
              <p className="px-3 py-4 text-sm text-slate-500">No completed elections yet.</p>
            ) : (
              <ul className="divide-y divide-slate-200">
                {closedElections.map((election) => (
                  <li
                    key={election.id}
                    className={`cursor-pointer px-3 py-3 hover:bg-primary-50 ${selectedId === election.id ? 'bg-primary-50' : ''}`}
                    onClick={() => handleSelectElection(election.id)}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-semibold text-slate-700">{election.title}</p>
                        <p className="text-xs text-slate-500">
                          Votes cast: {election.votes_cast} / {election.ballot_count}
                        </p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusBadge[election.status]}`}>
                        {election.status}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="space-y-4">
          {isManager && (
            <section className="rounded border border-slate-200 p-4">
              <h3 className="mb-3 text-sm font-semibold text-slate-600">Create Election</h3>
              <form className="grid gap-2" onSubmit={handleCreateElection}>
                <label className="text-sm">
                  <span className="mb-1 block text-slate-600">Title</span>
                  <input
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={createForm.title}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, title: event.target.value }))}
                    required
                  />
                </label>
                <label className="text-sm">
                  <span className="mb-1 block text-slate-600">Description</span>
                  <textarea
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    rows={2}
                    value={createForm.description}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, description: event.target.value }))}
                  />
                </label>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <label className="text-sm">
                    <span className="mb-1 block text-slate-600">Opens</span>
                    <input
                      type="datetime-local"
                      className="w-full rounded border border-slate-300 px-3 py-2"
                      value={createForm.opens_at}
                      onChange={(event) => setCreateForm((prev) => ({ ...prev, opens_at: event.target.value }))}
                    />
                  </label>
                  <label className="text-sm">
                    <span className="mb-1 block text-slate-600">Closes</span>
                    <input
                      type="datetime-local"
                      className="w-full rounded border border-slate-300 px-3 py-2"
                      value={createForm.closes_at}
                      onChange={(event) => setCreateForm((prev) => ({ ...prev, closes_at: event.target.value }))}
                    />
                  </label>
                </div>
                <button
                  type="submit"
                  className="mt-2 w-full rounded bg-primary-600 px-3 py-2 text-sm font-semibold text-white hover:bg-primary-500"
                >
                  Create Election
                </button>
              </form>
            </section>
          )}

          {detail ? (
            <section className="rounded border border-slate-200 p-4">
              <header className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-slate-600">{detail.title}</h3>
                  <p className="text-xs text-slate-500">
                    Status: {detail.status} • Votes: {detail.votes_cast} / {detail.ballot_count}
                  </p>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusBadge[detail.status]}`}>
                  {detail.status}
                </span>
              </header>

              {showStatsPanel && (
                <section className="mt-4 rounded border border-primary-100 bg-primary-50/60 p-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-semibold uppercase text-primary-700">Turnout Snapshot</h4>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        className="rounded border border-primary-300 px-3 py-1 text-xs font-semibold text-primary-700 hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
                        onClick={() => statsQuery.refetch()}
                        disabled={statsLoading}
                      >
                        {statsLoading ? 'Refreshing…' : 'Refresh stats'}
                      </button>
                      <button
                        type="button"
                        className="rounded border border-primary-300 px-3 py-1 text-xs font-semibold text-primary-700 hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
                        onClick={handleExportResults}
                        disabled={exportResultsMutation.isPending || !stats || statsLoading}
                      >
                        {exportResultsMutation.isPending ? 'Exporting…' : 'Download CSV'}
                      </button>
                    </div>
                  </div>
                  {statsLoading ? (
                    <p className="mt-3 text-xs text-primary-700">Calculating turnout…</p>
                  ) : stats ? (
                    <>
                      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        {[
                          { label: 'Turnout', value: `${stats.turnout_percent.toFixed(1)}%` },
                          { label: 'Votes cast', value: `${stats.votes_cast} / ${stats.ballot_count}` },
                          { label: 'Abstentions', value: String(stats.abstentions) },
                          { label: 'Write-ins', value: String(stats.write_in_count) },
                        ].map((card) => (
                          <div key={card.label} className="rounded border border-primary-200 bg-white/90 p-3">
                            <p className="text-[11px] uppercase text-primary-500">{card.label}</p>
                            <p className="text-lg font-semibold text-primary-700">{card.value}</p>
                          </div>
                        ))}
                      </div>
                      <div className="mt-4 space-y-2 rounded border border-primary-200 bg-white/90 p-3">
                        <p className="text-[11px] uppercase text-primary-500">Vote share</p>
                        <div className="space-y-2">
                          {(stats.results || []).map((result) => {
                            const total = stats.votes_cast || 1;
                            const percent = Math.min(100, Math.max(0, (result.vote_count / total) * 100));
                            return (
                              <div key={`${result.candidate_id ?? 'write-in'}-${result.candidate_name ?? 'write-in'}`}>
                                <div className="flex items-center justify-between text-xs text-primary-700">
                                  <span className="font-semibold">
                                    {result.candidate_name || 'Write-in'}
                                  </span>
                                  <span className="tabular-nums">{percent.toFixed(1)}%</span>
                                </div>
                                <div className="mt-1 h-2 overflow-hidden rounded bg-primary-100">
                                  <div
                                    className="h-full bg-primary-500 transition-all"
                                    style={{ width: `${percent}%` }}
                                  />
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                      <p className="mt-3 text-[11px] uppercase text-primary-500">
                        Snapshot refreshes automatically as ballots are issued and votes recorded.
                      </p>
                    </>
                  ) : (
                    <p className="mt-3 text-xs text-primary-700">No turnout metrics yet.</p>
                  )}
                </section>
              )}

              {detail.description && (
                <p className="mt-3 whitespace-pre-wrap text-sm text-slate-700">{detail.description}</p>
              )}

              <section className="mt-4">
                <h4 className="text-xs font-semibold uppercase text-slate-500">Candidates</h4>
                {detail.candidates.length === 0 ? (
                  <p className="mt-2 text-xs text-slate-500">No candidates registered.</p>
                ) : (
                  <ul className="mt-2 space-y-2 text-sm">
                    {detail.candidates.map((candidate) => {
                      const result = detail.results.find((item) => item.candidate_id === candidate.id);
                      return (
                        <li key={candidate.id} className="rounded border border-slate-200 p-2">
                          <div className="flex items-center justify-between">
                            <div>
                              <span className="font-semibold text-slate-700">{candidate.display_name}</span>
                              {candidate.statement && (
                                <p className="mt-1 text-xs text-slate-500">{candidate.statement}</p>
                              )}
                            </div>
                            {typeof result?.vote_count === 'number' && (
                              <span className="text-xs font-semibold text-slate-600">
                                {result.vote_count} vote{result.vote_count === 1 ? '' : 's'}
                              </span>
                            )}
                          </div>
                          {isManager && (
                            <button
                              type="button"
                              className="mt-2 rounded border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-100"
                              onClick={() => handleDeleteCandidate(candidate)}
                            >
                              Remove
                            </button>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}

                {writeInResult && (
                  <p className="mt-3 text-xs text-slate-500">
                    Write-in ballots recorded:{' '}
                    <span className="font-semibold text-slate-700">{writeInResult.vote_count}</span>
                  </p>
                )}

                {isManager && (
                  <form className="mt-3 grid gap-2" onSubmit={handleAddCandidate}>
                    <h5 className="text-xs font-semibold uppercase text-slate-500">Add Candidate</h5>
                    <select
                      className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                      value={candidateForm.owner_id}
                      onChange={handleOwnerChange}
                      disabled={ownersLoading}
                    >
                      <option value="">{ownersLoading ? 'Loading owners…' : 'Select owner…'}</option>
                      {owners.map((owner) => (
                        <option key={owner.id} value={owner.id}>
                          {owner.property_address} • {owner.primary_name}
                        </option>
                      ))}
                    </select>
                    {ownersError && <p className="text-xs text-red-600">{ownersError}</p>}
                    <input
                      className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                      placeholder="Custom candidate name"
                      value={candidateForm.display_name}
                      onChange={(event) => setCandidateForm((prev) => ({ ...prev, display_name: event.target.value }))}
                    />
                    <textarea
                      className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                      rows={2}
                      placeholder="Statement (optional)"
                      value={candidateForm.statement}
                      onChange={(event) => setCandidateForm((prev) => ({ ...prev, statement: event.target.value }))}
                    />
                    <button
                      type="submit"
                      className="rounded bg-primary-600 px-3 py-2 text-xs font-semibold text-white hover:bg-primary-500"
                    >
                      Add Candidate
                    </button>
                  </form>
                )}
              </section>

              {isManager && (
                <section className="mt-4 rounded border border-slate-200 p-3">
                  <h4 className="text-xs font-semibold uppercase text-slate-500">Timeline & Status</h4>
                  <form className="mt-2 grid gap-2 sm:grid-cols-3" onSubmit={handleUpdateStatus}>
                    <label className="text-xs">
                      <span className="mb-1 block text-slate-600">Status</span>
                      <select
                        className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                        value={statusForm.status}
                        onChange={(event) => setStatusForm((prev) => ({ ...prev, status: event.target.value }))}
                      >
                        <option value="DRAFT">Draft</option>
                        <option value="SCHEDULED">Scheduled</option>
                        <option value="OPEN">Open</option>
                        <option value="CLOSED">Closed</option>
                        <option value="ARCHIVED">Archived</option>
                      </select>
                    </label>
                    <label className="text-xs">
                      <span className="mb-1 block text-slate-600">Opens</span>
                      <input
                        type="datetime-local"
                        className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                        value={statusForm.opens_at}
                        onChange={(event) => setStatusForm((prev) => ({ ...prev, opens_at: event.target.value }))}
                      />
                    </label>
                    <label className="text-xs">
                      <span className="mb-1 block text-slate-600">Closes</span>
                      <input
                        type="datetime-local"
                        className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                        value={statusForm.closes_at}
                        onChange={(event) => setStatusForm((prev) => ({ ...prev, closes_at: event.target.value }))}
                      />
                    </label>
                    <div className="sm:col-span-3 flex justify-end">
                      <button
                        type="submit"
                        className="rounded bg-primary-600 px-3 py-2 text-xs font-semibold text-white hover:bg-primary-500"
                      >
                        Save Status
                      </button>
                    </div>
                  </form>
                </section>
              )}

              {isManager && (
                <section className="mt-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-semibold uppercase text-slate-500">Ballots</h4>
                    <button
                      type="button"
                      className="rounded bg-primary-600 px-3 py-2 text-xs font-semibold text-white hover:bg-primary-500"
                      onClick={handleGenerateBallots}
                    >
                      Generate / Refresh Ballots
                    </button>
                  </div>
                  {ballotsQuery.isLoading ? (
                    <p className="mt-2 text-xs text-slate-500">Loading ballots…</p>
                  ) : ballots.length === 0 ? (
                    <p className="mt-2 text-xs text-slate-500">No ballots have been issued yet.</p>
                  ) : (
                    <div className="mt-2 overflow-x-auto">
                      <table className="min-w-full divide-y divide-slate-200 text-xs">
                        <thead className="bg-slate-50">
                          <tr>
                            <th className="px-2 py-1 text-left font-semibold text-slate-600">Owner</th>
                            <th className="px-2 py-1 text-left font-semibold text-slate-600">Token</th>
                            <th className="px-2 py-1 text-left font-semibold text-slate-600">Issued</th>
                            <th className="px-2 py-1 text-left font-semibold text-slate-600">Voted</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {ballots.map((ballot) => (
                            <tr key={ballot.id}>
                              <td className="px-2 py-1">{ballot.owner_name ?? `Owner #${ballot.owner_id}`}</td>
                              <td className="px-2 py-1 font-mono text-xs">{ballot.token}</td>
                              <td className="px-2 py-1">{new Date(ballot.issued_at).toLocaleString()}</td>
                              <td className="px-2 py-1">
                                {ballot.voted_at ? new Date(ballot.voted_at).toLocaleString() : 'Not yet'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              )}

              {myStatus ? (
                <section className="mt-4 rounded border border-emerald-200 bg-emerald-50 p-3">
                  <h4 className="text-xs font-semibold uppercase text-emerald-700">Portal Voting</h4>
                  {detail.status !== 'OPEN' && (
                    <p className="mt-2 text-sm text-emerald-900">
                      This election is not currently open. You will be able to vote here once it opens.
                    </p>
                  )}
                  {detail.status === 'OPEN' && alreadyVoted && (
                    <p className="mt-2 text-sm text-emerald-900">
                      Thanks for voting! Your ballot was recorded{' '}
                      {myStatus.voted_at ? new Date(myStatus.voted_at).toLocaleString() : 'recently'}.
                    </p>
                  )}
                  {detail.status === 'OPEN' && !alreadyVoted && (
                    <form className="mt-3 space-y-3 text-sm text-emerald-900" onSubmit={handleSubmitVote}>
                      <p>Select a candidate below or enter a write-in.</p>
                      <div className="space-y-2 rounded border border-emerald-200 bg-white p-3">
                        {detail.candidates.length === 0 ? (
                          <p className="text-xs text-emerald-600">No candidates available.</p>
                        ) : (
                          detail.candidates.map((candidate) => (
                            <label key={candidate.id} className="flex cursor-pointer items-start gap-3 text-sm">
                              <input
                                type="radio"
                                name="candidate"
                                className="mt-1"
                                value={candidate.id}
                                checked={voteCandidateId === candidate.id}
                                onChange={() => setVoteCandidateId(candidate.id)}
                              />
                              <span>
                                <span className="font-semibold">{candidate.display_name}</span>
                                {candidate.statement && (
                                  <span className="block text-xs text-emerald-700">{candidate.statement}</span>
                                )}
                              </span>
                            </label>
                          ))
                        )}
                      </div>
                      <div>
                        <label className="block text-xs font-semibold uppercase text-emerald-700">
                          Write-in candidate (optional)
                        </label>
                        <input
                          className="mt-1 w-full rounded border border-emerald-300 px-3 py-2 text-sm text-slate-800"
                          placeholder="Name for write-in ballot"
                          value={writeInValue}
                          onChange={(event) => setWriteInValue(event.target.value)}
                        />
                      </div>
                      {voteError && <p className="text-xs text-red-700">{voteError}</p>}
                      {voteFeedback && <p className="text-xs text-emerald-700">{voteFeedback}</p>}
                      <button
                        type="submit"
                        className="rounded bg-emerald-600 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white hover:bg-emerald-500 disabled:opacity-60"
                        disabled={voteSubmitting}
                      >
                        {voteSubmitting ? 'Submitting…' : 'Cast Vote'}
                      </button>
                    </form>
                  )}
                </section>
              ) : (
                !isManager && (
                  <section className="mt-4 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                    We could not find an active homeowner profile linked to your login. Contact an administrator if you
                    need help accessing your ballot.
                  </section>
                )
              )}
            </section>
          ) : (
            <section className="rounded border border-dashed border-slate-300 p-4 text-sm text-slate-500">
              Select an election to view details and results.
            </section>
          )}
        </div>
      </section>
    </div>
  );
};

export default ElectionsPage;
