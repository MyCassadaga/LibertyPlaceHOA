import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  addElectionCandidate,
  createElection,
  deleteElectionCandidate,
  downloadElectionResultsCsv,
  fetchElectionBallots,
  fetchElectionDetail,
  fetchElectionStats,
  fetchElections,
  fetchPublicElection,
  generateElectionBallots,
  submitElectionVote,
  submitPublicVote,
  updateElection,
} from '../../services/api';
import { queryKeys } from '../../lib/api/queryKeys';
import type {
  ElectionAdminBallot,
  ElectionDetail,
  ElectionListItem,
  ElectionPublicDetail,
  ElectionStats,
} from '../../types';

const electionDetailKey = (electionId: number) => [...queryKeys.electionDetail, electionId] as const;
const electionBallotsKey = (electionId: number) => [...queryKeys.electionBallots, electionId] as const;
const electionStatsKey = (electionId: number) => [...queryKeys.electionStats, electionId] as const;

export const useElectionsQuery = (options?: { enabled?: boolean }) =>
  useQuery<ElectionListItem[]>({
    queryKey: queryKeys.elections,
    queryFn: () => fetchElections(),
    enabled: options?.enabled ?? true,
  });

export const useElectionDetailQuery = (electionId: number | null) =>
  useQuery<ElectionDetail>({
    queryKey: electionId != null ? electionDetailKey(electionId) : ['elections', 'detail', 'noop'],
    queryFn: () => fetchElectionDetail(electionId!),
    enabled: electionId != null,
  });

export const useElectionBallotsQuery = (electionId: number | null, enabled: boolean) =>
  useQuery<ElectionAdminBallot[]>({
    queryKey: electionId != null ? electionBallotsKey(electionId) : ['elections', 'ballots', 'noop'],
    queryFn: () => fetchElectionBallots(electionId!),
    enabled: enabled && electionId != null,
  });

export const useElectionStatsQuery = (electionId: number | null, enabled: boolean) =>
  useQuery<ElectionStats>({
    queryKey: electionId != null ? electionStatsKey(electionId) : ['elections', 'stats', 'noop'],
    queryFn: () => fetchElectionStats(electionId!),
    enabled: enabled && electionId != null,
  });

export const useCreateElectionMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createElection,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.elections });
      queryClient.invalidateQueries({ queryKey: electionDetailKey(data.id) });
    },
  });
};

export const useUpdateElectionMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      electionId,
      payload,
    }: {
      electionId: number;
      payload: Parameters<typeof updateElection>[1];
    }) => updateElection(electionId, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.elections });
      queryClient.invalidateQueries({ queryKey: electionDetailKey(variables.electionId) });
    },
  });
};

export const useAddCandidateMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      electionId,
      payload,
    }: {
      electionId: number;
      payload: Parameters<typeof addElectionCandidate>[1];
    }) => addElectionCandidate(electionId, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: electionDetailKey(variables.electionId) });
    },
  });
};

export const useDeleteCandidateMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ electionId, candidateId }: { electionId: number; candidateId: number }) =>
      deleteElectionCandidate(electionId, candidateId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: electionDetailKey(variables.electionId) });
    },
  });
};

export const useGenerateBallotsMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (electionId: number) => generateElectionBallots(electionId),
    onSuccess: (data, electionId) => {
      queryClient.setQueryData(electionBallotsKey(electionId), data);
    },
  });
};

export const useSubmitElectionVoteMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      electionId,
      payload,
    }: {
      electionId: number;
      payload: Parameters<typeof submitElectionVote>[1];
    }) => submitElectionVote(electionId, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.elections });
      queryClient.invalidateQueries({ queryKey: electionDetailKey(variables.electionId) });
    },
  });
};

export const usePublicVoteMutation = () =>
  useMutation({
    mutationFn: ({
      electionId,
      payload,
    }: {
      electionId: number;
      payload: Parameters<typeof submitPublicVote>[1] & { token: string };
    }) => submitPublicVote(electionId, payload),
  });
export const usePublicElectionQuery = (electionId: number | null, token: string | null) =>
  useQuery<ElectionPublicDetail>({
    queryKey: electionId != null ? [...queryKeys.electionPublic, electionId, token] : ['elections', 'public', 'noop'],
    queryFn: () => fetchPublicElection(electionId!, token!),
    enabled: Boolean(electionId && token),
  });

export const useElectionResultsExportMutation = () =>
  useMutation({
    mutationFn: (electionId: number) => downloadElectionResultsCsv(electionId),
  });
