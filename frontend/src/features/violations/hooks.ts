import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createViolation,
  fetchFineSchedules,
  fetchViolationNotices,
  fetchViolations,
  submitAppeal,
  transitionViolation,
} from '../../services/api';
import type { FineSchedule, Violation, ViolationNotice } from '../../types';

const violationsKey = (filters: Record<string, unknown>) => ['violations', filters] as const;
const fineSchedulesKey = ['violations', 'fine-schedules'] as const;
const noticesKey = (violationId: number) => ['violations', 'notices', violationId] as const;

export const useViolationsQuery = (filters: Record<string, unknown>) =>
  useQuery<Violation[]>({
    queryKey: violationsKey(filters),
    queryFn: () => fetchViolations(filters),
  });

export const useFineSchedulesQuery = (enabled: boolean) =>
  useQuery<FineSchedule[]>({
    queryKey: fineSchedulesKey,
    queryFn: fetchFineSchedules,
    enabled,
  });

export const useViolationNoticesQuery = (violationId: number | null) =>
  useQuery<ViolationNotice[]>({
    queryKey: violationId ? noticesKey(violationId) : ['violations', 'notices', 'noop'],
    queryFn: () => fetchViolationNotices(violationId!),
    enabled: violationId != null,
  });

export const useCreateViolationMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createViolation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['violations'] });
    },
  });
};

export const useTransitionViolationMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      violationId,
      payload,
    }: {
      violationId: number;
      payload: { status: string; note?: string; hearing_date?: string; fine_amount?: string };
    }) => transitionViolation(violationId, payload),
    onSuccess: async (_, { violationId }) => {
      await queryClient.invalidateQueries({ queryKey: ['violations'] });
      await queryClient.invalidateQueries({ queryKey: noticesKey(violationId) });
    },
  });
};

export const useSubmitAppealMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ violationId, message }: { violationId: number; message: string }) =>
      submitAppeal(violationId, message),
    onSuccess: async (_, { violationId }) => {
      await queryClient.invalidateQueries({ queryKey: ['violations'] });
      await queryClient.invalidateQueries({ queryKey: noticesKey(violationId) });
    },
  });
};
