import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  archiveOwner,
  fetchOwnerById,
  fetchResidents,
  linkUserToOwner,
  restoreOwner,
  unlinkUserFromOwner,
  updateOwner,
} from '../../services/api';
import { OwnerUpdatePayload, Resident } from '../../types';

const residentsKey = ['owners', 'residents'];
const ownerDetailKey = (ownerId: number) => ['owners', ownerId];

export const useResidentsQuery = () =>
  useQuery<Resident[]>({
    queryKey: residentsKey,
    queryFn: () => fetchResidents({ includeArchived: true }),
  });

export const useOwnerDetailQuery = (ownerId: number | null) =>
  useQuery({
    queryKey: ownerId ? ownerDetailKey(ownerId) : ['owners', 'detail', 'noop'],
    queryFn: () => fetchOwnerById(ownerId!),
    enabled: ownerId != null,
  });

export const useOwnerUpdateMutation = (ownerId: number | null) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: OwnerUpdatePayload) => updateOwner(ownerId!, payload),
    onSuccess: async () => {
      if (ownerId != null) {
        await queryClient.invalidateQueries({ queryKey: ownerDetailKey(ownerId) });
      }
      await queryClient.invalidateQueries({ queryKey: residentsKey });
    },
  });
};

export const useArchiveOwnerMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ownerId, reason }: { ownerId: number; reason?: string }) => archiveOwner(ownerId, { reason }),
    onSuccess: async (_, variables) => {
      await queryClient.invalidateQueries({ queryKey: residentsKey });
      await queryClient.invalidateQueries({ queryKey: ownerDetailKey(variables.ownerId) });
    },
  });
};

export const useRestoreOwnerMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ownerId, reactivate }: { ownerId: number; reactivate: boolean }) =>
      restoreOwner(ownerId, { reactivate_user: reactivate }),
    onSuccess: async (_, variables) => {
      await queryClient.invalidateQueries({ queryKey: residentsKey });
      await queryClient.invalidateQueries({ queryKey: ownerDetailKey(variables.ownerId) });
    },
  });
};

export const useLinkUserMutation = (ownerId: number | null) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: number) => linkUserToOwner(ownerId!, { user_id: userId }),
    onSuccess: async () => {
      if (ownerId != null) {
        await queryClient.invalidateQueries({ queryKey: ownerDetailKey(ownerId) });
      }
      await queryClient.invalidateQueries({ queryKey: residentsKey });
    },
  });
};

export const useUnlinkUserMutation = (ownerId: number | null) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: number) => unlinkUserFromOwner(ownerId!, userId),
    onSuccess: async () => {
      if (ownerId != null) {
        await queryClient.invalidateQueries({ queryKey: ownerDetailKey(ownerId) });
      }
      await queryClient.invalidateQueries({ queryKey: residentsKey });
    },
  });
};
