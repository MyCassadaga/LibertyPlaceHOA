import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  fetchRoles,
  fetchUsers,
  fetchLoginBackground,
  registerUser,
  updateUserRoles,
  uploadLoginBackground,
  RegisterUserPayload,
} from '../../services/api';
import { queryKeys } from '../../lib/api/queryKeys';
import type { RoleOption, User } from '../../types';

export const useRolesQuery = () =>
  useQuery<RoleOption[]>({
    queryKey: queryKeys.roles,
    queryFn: fetchRoles,
  });

export const useUsersQuery = () =>
  useQuery<User[]>({
    queryKey: queryKeys.adminUsers,
    queryFn: fetchUsers,
  });

export const useLoginBackgroundQuery = () =>
  useQuery({
    queryKey: queryKeys.loginBackground,
    queryFn: fetchLoginBackground,
  });

const useInvalidateUsers = () => {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.adminUsers });
};

export const useRegisterUserMutation = () => {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: (payload: RegisterUserPayload) => registerUser(payload),
    onSuccess: invalidate,
  });
};

export const useUpdateUserRolesMutation = () => {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: ({ userId, roleIds }: { userId: number; roleIds: number[] }) =>
      updateUserRoles(userId, roleIds),
    onSuccess: invalidate,
  });
};

export const useUploadLoginBackgroundMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadLoginBackground(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.loginBackground });
    },
  });
};
