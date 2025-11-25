import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  sendNotificationBroadcast,
} from '../../services/api';
import { queryKeys } from '../../lib/api/queryKeys';
import type { Notification } from '../../types';

type NotificationsListQueryOptions = {
  includeRead: boolean;
  limit?: number;
  levels?: string[];
  categories?: string[];
};

export const useNotificationsListQuery = (options: NotificationsListQueryOptions) => {
  const normalizedLevels =
    options.levels?.filter(Boolean).map((level) => level.trim().toLowerCase()) ?? undefined;
  const normalizedCategories =
    options.categories?.filter(Boolean).map((category) => category.trim().toLowerCase()) ?? undefined;

  return useQuery<Notification[]>({
    queryKey: [
      queryKeys.notifications,
      options.includeRead,
      options.limit ?? 100,
      normalizedLevels?.join('|') ?? null,
      normalizedCategories?.join('|') ?? null,
    ],
    queryFn: () =>
      fetchNotifications({
        includeRead: options.includeRead,
        limit: options.limit,
        levels: normalizedLevels,
        categories: normalizedCategories,
      }),
  });
};

const useInvalidateNotifications = () => {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.notifications });
};

export const useMarkNotificationReadMutation = () => {
  const invalidate = useInvalidateNotifications();
  return useMutation({
    mutationFn: (notificationId: number) => markNotificationRead(notificationId),
    onSuccess: invalidate,
  });
};

export const useMarkAllNotificationsReadMutation = () => {
  const invalidate = useInvalidateNotifications();
  return useMutation({
    mutationFn: () => markAllNotificationsRead(),
    onSuccess: invalidate,
  });
};

export const useNotificationBroadcastMutation = () =>
  useMutation({
    mutationFn: sendNotificationBroadcast,
  });
