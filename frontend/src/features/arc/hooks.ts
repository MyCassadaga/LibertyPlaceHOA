import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  addARCCondition,
  createARCRequest,
  fetchARCReviewers,
  fetchARCRequests,
  reopenARCRequest,
  submitARCReview,
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

export const useArcReviewersQuery = (enabled: boolean) =>
  useQuery({
    queryKey: queryKeys.arcReviewers,
    queryFn: fetchARCReviewers,
    enabled,
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

export const useReopenArcRequestMutation = () => {
  const invalidate = useInvalidateArcRequests();
  return useMutation({
    mutationFn: ({ requestId }: { requestId: number }) => reopenARCRequest(requestId),
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

export const useSubmitArcReviewMutation = () => {
  const invalidate = useInvalidateArcRequests();
  return useMutation({
    mutationFn: ({
      requestId,
      payload,
    }: {
      requestId: number;
      payload: Parameters<typeof submitARCReview>[1];
    }) => submitARCReview(requestId, payload),
    onSuccess: invalidate,
  });
};
