import React, { useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { ElectionCandidate } from '../types';
import { usePublicElectionQuery, usePublicVoteMutation } from '../features/elections/hooks';

const PublicVotePage: React.FC = () => {
  const { electionId } = useParams<{ electionId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') ?? '';
  const numericElectionId = useMemo(() => (electionId ? Number(electionId) : null), [electionId]);

  const publicElectionQuery = usePublicElectionQuery(numericElectionId, token || null);
  const election = publicElectionQuery.data ?? null;
  const [selectedCandidate, setSelectedCandidate] = useState<number | null>(null);
  const [writeIn, setWriteIn] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const submitMutation = usePublicVoteMutation();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!numericElectionId || !token || !election) {
      setError('Missing election token.');
      return;
    }
    const trimmedWriteIn = writeIn.trim();
    if (selectedCandidate == null && !trimmedWriteIn) {
      setError('Select a candidate or enter a write-in.');
      return;
    }
    setError(null);
    setStatus(null);
    try {
      await submitMutation.mutateAsync({
        electionId: numericElectionId,
        payload: {
          token,
          candidate_id: selectedCandidate ?? undefined,
          write_in: trimmedWriteIn || undefined,
        },
      });
      setStatus('Thank you! Your vote has been recorded.');
      await publicElectionQuery.refetch();
      setSelectedCandidate(null);
      setWriteIn('');
    } catch (err) {
      console.error('Unable to record public vote.', err);
      setError('Unable to record vote. The ballot may already be used or the election may be closed.');
    }
  };

  const handleCandidateChange = (candidate: ElectionCandidate) => {
    setSelectedCandidate(candidate.id);
    setWriteIn('');
  };

  const handleWriteInFocus = () => {
    setSelectedCandidate(null);
  };

  if (!token) {
    return (
      <div className="p-6 text-sm text-red-600">
        Invalid ballot link. Please use the ballot URL that was distributed for this election.
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
      <div className="w-full max-w-2xl rounded bg-white p-6 shadow">
        <button
          type="button"
          onClick={() => navigate('/')}
          className="text-xs text-slate-500 hover:text-slate-700"
        >
          ← Return to portal
        </button>
        <h1 className="mt-2 text-2xl font-semibold text-primary-600">{election?.title ?? 'Election'}</h1>
        {election?.description && (
          <p className="mt-2 text-sm text-slate-600 whitespace-pre-wrap">{election.description}</p>
        )}

        {publicElectionQuery.isLoading && <p className="mt-4 text-sm text-slate-500">Loading ballot…</p>}
        {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
        {status && <p className="mt-4 text-sm text-green-600">{status}</p>}

        {election && !publicElectionQuery.isLoading && !election.has_voted && (
          <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
            <fieldset className="space-y-3">
              <legend className="text-sm font-semibold text-slate-600">Select a candidate</legend>
              {election.candidates.map((candidate) => (
                <label key={candidate.id} className="flex items-start gap-2 rounded border border-slate-200 px-3 py-2">
                  <input
                    type="radio"
                    name="candidate"
                    className="mt-1"
                    checked={selectedCandidate === candidate.id}
                    onChange={() => handleCandidateChange(candidate)}
                  />
                  <div>
                    <span className="text-sm font-semibold text-slate-700">{candidate.display_name}</span>
                    {candidate.statement && (
                      <p className="text-xs text-slate-500 whitespace-pre-wrap">{candidate.statement}</p>
                    )}
                  </div>
                </label>
              ))}
              <div className="rounded border border-slate-200 px-3 py-2">
                <label className="text-sm font-semibold text-slate-600" htmlFor="write-in">
                  Write-in option
                </label>
                <input
                  id="write-in"
                  className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
                  placeholder="Enter a write-in candidate"
                  value={writeIn}
                  onFocus={handleWriteInFocus}
                  onChange={(event) => setWriteIn(event.target.value)}
                />
              </div>
            </fieldset>
            <button
              type="submit"
              className="w-full rounded bg-primary-600 px-3 py-2 text-sm font-semibold text-white hover:bg-primary-500 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={submitMutation.isPending}
            >
              {submitMutation.isPending ? 'Submitting…' : 'Submit Vote'}
            </button>
          </form>
        )}

        {election?.has_voted && (
          <div className="mt-4 rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            This ballot token has already been used. Thank you for participating!
          </div>
        )}
      </div>
    </div>
  );
};

export default PublicVotePage;
