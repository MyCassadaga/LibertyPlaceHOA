import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { API_BASE_URL, fetchNotifications, markAllNotificationsRead, markNotificationRead } from '../services/api';
import { Notification } from '../types';
import { useAuth } from './useAuth';
import type { AxiosError } from 'axios';

type NotificationsContextValue = {
  notifications: Notification[];
  unreadCount: number;
  loading: boolean;
  markAsRead: (notificationId: number) => Promise<void>;
  markAllAsRead: () => Promise<void>;
  refresh: () => Promise<void>;
};

const NotificationsContext = createContext<NotificationsContextValue | undefined>(undefined);

const buildWebSocketUrl = (token: string): string => {
  const base = API_BASE_URL.replace(/\/+$/, '');
  const wsBase = base.startsWith('https://')
    ? base.replace('https://', 'wss://')
    : base.startsWith('http://')
    ? base.replace('http://', 'ws://')
    : base;
  return `${wsBase}/notifications/ws?token=${encodeURIComponent(token)}`;
};

export const NotificationsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { token, loading: authLoading, refresh: refreshAuth } = useAuth();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<number | null>(null);
  const refreshingSocketRef = useRef(false);

  const clearSocket = useCallback(() => {
    if (reconnectTimeout.current !== null) {
      window.clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const applyNotificationUpdate = useCallback((incoming: Notification) => {
    setNotifications((prev) => {
      const filtered = prev.filter((item) => item.id !== incoming.id);
      const next = [incoming, ...filtered];
      next.sort((a, b) => (a.created_at > b.created_at ? -1 : a.created_at < b.created_at ? 1 : 0));
      return next;
    });
  }, []);

  const connectWebSocket = useCallback(() => {
    if (!token) {
      return;
    }
    clearSocket();
    const socket = new WebSocket(buildWebSocketUrl(token));
    wsRef.current = socket;

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        switch (payload.type) {
          case 'notification.created':
            if (payload.notification) {
              applyNotificationUpdate(payload.notification as Notification);
            }
            break;
          case 'notification.read':
            setNotifications((prev) =>
              prev.map((item) =>
                item.id === payload.id ? { ...item, read_at: payload.read_at ?? new Date().toISOString() } : item,
              ),
            );
            break;
          case 'notification.bulk_read':
            if (Array.isArray(payload.ids)) {
              setNotifications((prev) =>
                prev.map((item) =>
                  payload.ids.includes(item.id)
                    ? { ...item, read_at: payload.read_at ?? new Date().toISOString() }
                    : item,
                ),
              );
            }
            break;
          default:
            break;
        }
      } catch (error) {
        console.warn('Failed to parse notification payload', error);
      }
    };

    socket.onclose = (event) => {
      wsRef.current = null;
      if (!token) {
        return;
      }
      const unauthorizedCodes = new Set([1008, 4401, 4403]);
      const unauthorized = unauthorizedCodes.has(event.code) || event.code === 1006;
      if (unauthorized) {
        if (!refreshingSocketRef.current) {
          refreshingSocketRef.current = true;
          refreshAuth()
            .catch((error) => {
              console.error('Unable to refresh auth for notifications socket', error);
            })
            .finally(() => {
              refreshingSocketRef.current = false;
            });
        }
        return;
      }
      reconnectTimeout.current = window.setTimeout(() => {
        connectWebSocket();
      }, 2000);
    };

    socket.onerror = () => {
      socket.close();
    };
  }, [applyNotificationUpdate, clearSocket, refreshAuth, token]);

  const refresh = useCallback(async () => {
    if (!token) {
      setNotifications([]);
      return;
    }
    setLoading(true);
    try {
      const data = await fetchNotifications({ includeRead: true, limit: 100 });
      data.sort((a, b) => (a.created_at > b.created_at ? -1 : a.created_at < b.created_at ? 1 : 0));
      setNotifications(data);
    } catch (error) {
      const axiosError = error as AxiosError;
      if (axiosError?.response?.status === 401) {
        try {
          await refreshAuth();
        } catch (refreshError) {
          console.error('Unable to refresh auth while loading notifications', refreshError);
        }
      } else {
        console.error('Unable to load notifications', error);
      }
    } finally {
      setLoading(false);
    }
  }, [token, refreshAuth]);

  useEffect(() => {
    if (authLoading) {
      return;
    }
    if (!token) {
      clearSocket();
      setNotifications([]);
      setLoading(false);
      return;
    }
    void refresh();
    connectWebSocket();
    return () => {
      clearSocket();
    };
  }, [authLoading, token, refresh, connectWebSocket, clearSocket]);

  const markAsRead = useCallback(
    async (notificationId: number) => {
      try {
        const updated = await markNotificationRead(notificationId);
        applyNotificationUpdate(updated);
      } catch (error) {
        console.error('Unable to mark notification as read', error);
      }
    },
    [applyNotificationUpdate],
  );

  const markAllAsReadFn = useCallback(async () => {
    try {
      const response = await markAllNotificationsRead();
      if (response.updated > 0) {
        const timestamp = new Date().toISOString();
        setNotifications((prev) => prev.map((item) => ({ ...item, read_at: timestamp })));
      }
    } catch (error) {
      console.error('Unable to mark all notifications as read', error);
    }
  }, []);

  const unreadCount = useMemo(() => notifications.filter((item) => !item.read_at).length, [notifications]);

  const value = useMemo<NotificationsContextValue>(
    () => ({
      notifications,
      unreadCount,
      loading,
      markAsRead,
      markAllAsRead: markAllAsReadFn,
      refresh,
    }),
    [notifications, unreadCount, loading, markAsRead, markAllAsReadFn, refresh],
  );

  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>;
};

export const useNotifications = (): NotificationsContextValue => {
  const ctx = useContext(NotificationsContext);
  if (!ctx) {
    throw new Error('useNotifications must be used within a NotificationsProvider');
  }
  return ctx;
};
