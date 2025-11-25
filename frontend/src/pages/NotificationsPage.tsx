import React, { useMemo, useState } from 'react';

import {
  useMarkAllNotificationsReadMutation,
  useMarkNotificationReadMutation,
  useNotificationsListQuery,
} from '../features/notifications/hooks';
import { Notification } from '../types';

const LEVEL_BADGE: Record<string, string> = {
  INFO: 'bg-slate-100 text-slate-700',
  SUCCESS: 'bg-emerald-100 text-emerald-700',
  WARNING: 'bg-amber-100 text-amber-700',
  DANGER: 'bg-rose-100 text-rose-700',
};

const formatTimestamp = (iso: string) => {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
};

const NotificationsPage: React.FC = () => {
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);
  const [levelFilter, setLevelFilter] = useState<string>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');

  const queryOptions = useMemo(
    () => ({
      includeRead: !showUnreadOnly,
      limit: 100,
      levels: levelFilter === 'ALL' ? undefined : [levelFilter],
      categories: categoryFilter === 'ALL' ? undefined : [categoryFilter],
    }),
    [showUnreadOnly, levelFilter, categoryFilter],
  );

  const notificationsQuery = useNotificationsListQuery(queryOptions);
  const notifications = useMemo<Notification[]>(
    () => notificationsQuery.data ?? [],
    [notificationsQuery.data],
  );
  const markOneMutation = useMarkNotificationReadMutation();
  const markAllMutation = useMarkAllNotificationsReadMutation();
  const unreadCount = useMemo(() => notifications.filter((item) => !item.read_at).length, [notifications]);

  const handleMarkRead = async (notification: Notification) => {
    if (notification.read_at) {
      return;
    }
    try {
      await markOneMutation.mutateAsync(notification.id);
    } catch (err) {
      console.error('Unable to mark notification as read', err);
    }
  };

  const handleMarkAll = async () => {
    if (unreadCount === 0) {
      return;
    }
    try {
      await markAllMutation.mutateAsync();
    } catch (err) {
      console.error('Unable to mark all notifications as read', err);
    }
  };

  const categories = useMemo(() => {
    const set = new Set<string>();
    notifications.forEach((notification) => {
      if (notification.category) {
        set.add(notification.category);
      }
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [notifications]);

  const availableLevels = ['INFO', 'SUCCESS', 'WARNING', 'DANGER'];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-primary-600">Notifications</h2>
          <p className="text-sm text-slate-500">All alerts delivered to your account.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={showUnreadOnly}
              onChange={(event) => setShowUnreadOnly(event.target.checked)}
            />
            Show unread only
          </label>
          <label className="flex items-center gap-2">
            <span className="text-xs uppercase text-slate-500">Level</span>
            <select
              className="rounded border border-slate-300 px-2 py-1 text-xs"
              value={levelFilter}
              onChange={(event) => setLevelFilter(event.target.value)}
            >
              <option value="ALL">All</option>
              {availableLevels.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2">
            <span className="text-xs uppercase text-slate-500">Category</span>
            <select
              className="rounded border border-slate-300 px-2 py-1 text-xs"
              value={categoryFilter}
              onChange={(event) => setCategoryFilter(event.target.value)}
            >
              <option value="ALL">All</option>
              {categories.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="rounded border border-slate-300 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={handleMarkAll}
            disabled={unreadCount === 0 || markAllMutation.isPending}
          >
            {markAllMutation.isPending ? 'Marking…' : 'Mark all read'}
          </button>
        </div>
      </header>

      {notificationsQuery.isLoading ? (
        <p className="text-sm text-slate-500">Loading notifications…</p>
      ) : notifications.length === 0 ? (
        <p className="text-sm text-slate-500">
          {showUnreadOnly ? 'No unread notifications.' : 'No notifications match the selected filters.'}
        </p>
      ) : (
        <ul className="space-y-3">
          {notifications.map((notification) => {
            const badgeTone = LEVEL_BADGE[notification.level ?? 'INFO'] ?? LEVEL_BADGE.INFO;
            return (
              <li
                key={notification.id}
                className={`rounded border ${
                  notification.read_at ? 'border-slate-200 bg-white' : 'border-primary-200 bg-primary-50'
                } p-4`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className={`rounded px-2 py-1 text-xs font-semibold ${badgeTone}`}>
                      {notification.level ?? 'INFO'}
                    </span>
                    <p className="text-sm font-semibold text-slate-700">{notification.title}</p>
                  </div>
                  <p className="text-xs text-slate-500">{formatTimestamp(notification.created_at)}</p>
                </div>
                {notification.message && (
                  <p className="mt-2 text-sm text-slate-600">{notification.message}</p>
                )}
                <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500">
                  {notification.category && <span>Category: {notification.category}</span>}
                  {notification.link_url && (
                    <a
                      className="text-primary-600 hover:underline"
                      href={notification.link_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      View details
                    </a>
                  )}
                  {!notification.read_at && (
                    <button
                      type="button"
                      className="rounded border border-slate-300 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                      onClick={() => void handleMarkRead(notification)}
                      disabled={markOneMutation.isPending}
                    >
                      Mark read
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};

export default NotificationsPage;
