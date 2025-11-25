import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  addARCCondition,
  createARCInspection,
  createARCRequest,
  fetchARCRequests,
  resolveARCCondition,
  transitionARCRequest,
  uploadARCAttachment,
} from '../../services/api';
import { queryKeys } from '../../lib/api/queryKeys';
import type { ARCRequest } from '../../types';

const arcRequestsKey = (status?: string) =>
  status ? [...queryKeys.arcRequests, status] : [...queryKeys.arcRequests, 'ALL'];

export const useArcRequestsQuery = (status?: string) =>
  useQuery<ARCRequest[]>({
    queryKey: arcRequestsKey(status),
    queryFn: () => fetchARCRequests(status),
  });

const useInvalidateArcRequests = () => {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.arcRequests });
};

export const useCreateArcRequestMutation = () => {
  const invalidate = useInvalidateArcRequests();
  return useMutation({
    mutationFn: createARCRequest,
    onSuccess: invalidate,
  });
};

export const useTransitionArcRequestMutation = () => {
  const invalidate = useInvalidateArcRequests();
  return useMutation({
    mutationFn: ({
      requestId,
      payload,
    }: {
      requestId: number;
      payload: Parameters<typeof transitionARCRequest>[1];
    }) => transitionARCRequest(requestId, payload),
    onSuccess: invalidate,
  });
};

export const useUploadArcAttachmentMutation = () => {
  const invalidate = useInvalidateArcRequests();
  return useMutation({
    mutationFn: ({ requestId, file }: { requestId: number; file: File }) =>
      uploadARCAttachment(requestId, file),
    onSuccess: invalidate,
  });
};

export const useAddArcConditionMutation = () => {
  const invalidate = useInvalidateArcRequests();
  return useMutation({
    mutationFn: ({
      requestId,
      payload,
    }: {
      requestId: number;
      payload: Parameters<typeof addARCCondition>[1];
    }) => addARCCondition(requestId, payload),
    onSuccess: invalidate,
  });
};

export const useResolveArcConditionMutation = () => {
  const invalidate = useInvalidateArcRequests();
  return useMutation({
    mutationFn: ({
      requestId,
      conditionId,
      status,
    }: {
      requestId: number;
      conditionId: number;
      status: 'OPEN' | 'RESOLVED';
    }) => resolveARCCondition(requestId, conditionId, status),
    onSuccess: invalidate,
  });
};

export const useCreateArcInspectionMutation = () => {
  const invalidate = useInvalidateArcRequests();
  return useMutation({
    mutationFn: ({
      requestId,
      payload,
    }: {
      requestId: number;
      payload: Parameters<typeof createARCInspection>[1];
    }) => createARCInspection(requestId, payload),
    onSuccess: invalidate,
  });
};
