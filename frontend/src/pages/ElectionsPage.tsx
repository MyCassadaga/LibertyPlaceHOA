import React, { useCallback, useEffect, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import {
  addElectionCandidate,
  createElection,
  deleteElectionCandidate,
  fetchElectionBallots,
  fetchElectionDetail,
  fetchElections,
  fetchOwners,
  generateElectionBallots,
  submitElectionVote,
  updateElection,
} from '../services/api';
import {
  ElectionAdminBallot,
  ElectionCandidate,
  ElectionDetail,
  ElectionListItem,
  ElectionStatus,
  Owner,
} from '../types';
import { formatUserRoles, userHasAnyRole } from '../utils/roles';

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

  const [elections, setElections] = useState<ElectionListItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ElectionDetail | null>(null);
  const [ballots, setBallots] = useState<ElectionAdminBallot[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

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
  const [owners, setOwners] = useState<Owner[]>([]);
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

  const refreshElectionList = useCallback(async (preferredId?: number | null) => {
    const data = await fetchElections();
    setElections(data);
    setSelectedId((current) => {
      if (preferredId != null) {
        return preferredId;
      }
      if (current != null && data.some((item) => item.id === current)) {
        return current;
      }
      return data.length > 0 ? data[0].id : null;
    });
  }, []);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        await refreshElectionList();
      } catch (err) {
        setError('Unable to load elections.');
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [refreshElectionList]);

  useEffect(() => {
    if (selectedId == null) {
      setDetail(null);
      setBallots([]);
      setStatusForm({ status: 'DRAFT', opens_at: '', closes_at: '' });
      return;
    }

    const loadDetail = async () => {
      setError(null);
      try {
        const data = await fetchElectionDetail(selectedId);
        setDetail(data);
        setStatusForm({
          status: data.status,
          opens_at: data.opens_at ? data.opens_at.slice(0, 16) : '',
          closes_at: data.closes_at ? data.closes_at.slice(0, 16) : '',
        });
        if (isManager) {
          const ballotData = await fetchElectionBallots(selectedId);
          setBallots(ballotData);
        } else {
          setBallots([]);
        }
      } catch (err) {
        setError('Unable to load election details.');
      }
    };

    void loadDetail();
  }, [selectedId, isManager]);

  useEffect(() => {
    setVoteCandidateId(null);
    setWriteInValue('');
    setVoteError(null);
    setVoteFeedback(null);
  }, [detail?.id]);

  const upcomingElections = useMemo(
    () => elections.filter((election) => ['DRAFT', 'SCHEDULED', 'OPEN'].includes(election.status)),
    [elections],
  );

  const closedElections = useMemo(
    () => elections.filter((election) => ['CLOSED', 'ARCHIVED'].includes(election.status)),
    [elections],
  );
  const myStatus = detail?.my_status ?? null;
  const canVoteInPortal = Boolean(detail && detail.status === 'OPEN' && myStatus && !myStatus.has_voted);
  const alreadyVoted = Boolean(myStatus?.has_voted);

  const handleUpdateStatus = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!detail) return;
    setError(null);
    try {
      const updated = await updateElection(detail.id, {
        status: statusForm.status,
        opens_at: statusForm.opens_at || undefined,
        closes_at: statusForm.closes_at || undefined,
      });
      setDetail(updated);
      setStatus('Election updated.');
      await refreshElectionList(updated.id);
    } catch (err) {
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
      const created = await createElection(payload);
      setStatus('Election created.');
      setCreateForm({ title: '', description: '', opens_at: '', closes_at: '' });
      await refreshElectionList(created.id);
    } catch (err) {
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
      const candidate = await addElectionCandidate(detail.id, {
        display_name: displayName,
        statement: candidateForm.statement.trim() || undefined,
        owner_id: ownerId,
      });
      setDetail({
        ...detail,
        candidates: [...detail.candidates, candidate],
      });
      setCandidateForm({ display_name: '', statement: '', owner_id: '' });
      setStatus('Candidate added.');
    } catch (err) {
      setError('Unable to add candidate.');
    }
  };

  const handleDeleteCandidate = async (candidate: ElectionCandidate) => {
    if (!detail) return;
    const confirm = window.confirm(`Remove candidate ${candidate.display_name}?`);
    if (!confirm) return;
    try {
      await deleteElectionCandidate(detail.id, candidate.id);
      setDetail({
        ...detail,
        candidates: detail.candidates.filter((item) => item.id !== candidate.id),
      });
      setStatus('Candidate removed.');
    } catch (err) {
      setError('Unable to remove candidate.');
    }
  };

  const handleGenerateBallots = async () => {
    if (!detail) return;
    setError(null);
    try {
      const data = await generateElectionBallots(detail.id);
      setBallots(data);
      setStatus('Ballots generated.');
    } catch (err) {
      setError('Unable to generate ballots.');
    }
  };

  useEffect(() => {
    if (!isManager) return;
    const loadOwners = async () => {
      try {
        const data = await fetchOwners();
        setOwners(data);
      } catch (err) {
        console.warn('Unable to load owners for candidate selection');
      }
    };
    void loadOwners();
  }, [isManager]);

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
      await submitElectionVote(detail.id, {
        candidate_id: voteCandidateId ?? undefined,
        write_in: trimmedWriteIn || undefined,
      });
      setVoteFeedback('Thanks for casting your ballot.');
      setStatus('Vote recorded.');
      await refreshElectionList(detail.id);
      const updated = await fetchElectionDetail(detail.id);
      setDetail(updated);
    } catch (err) {
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

      {error && <p className="text-sm text-red-600">{error}</p>}
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
                    onClick={() => setSelectedId(election.id)}
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
                    onClick={() => setSelectedId(election.id)}
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

                {isManager && (
                  <form className="mt-3 grid gap-2" onSubmit={handleAddCandidate}>
                    <h5 className="text-xs font-semibold uppercase text-slate-500">Add Candidate</h5>
                    <select
                      className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                      value={candidateForm.owner_id}
                      onChange={handleOwnerChange}
                    >
                      <option value="">Select owner…</option>
                      {owners.map((owner) => (
                        <option key={owner.id} value={owner.id}>
                          {owner.property_address} • {owner.primary_name}
                        </option>
                      ))}
                    </select>
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
                  {ballots.length === 0 ? (
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
