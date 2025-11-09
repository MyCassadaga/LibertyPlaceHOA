import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useNotifications } from '../hooks/useNotifications';

const formatTimestamp = (isoString: string): string => {
  try {
    return new Date(isoString).toLocaleString();
  } catch (error) {
    return isoString;
  }
};

const NotificationsMenu: React.FC = () => {
  const { notifications, unreadCount, loading, markAsRead, markAllAsRead } = useNotifications();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      if (!open) return;
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => {
      document.removeEventListener('mousedown', handleClick);
    };
  }, [open]);

  const sortedNotifications = useMemo(() => {
    const copy = [...notifications];
    copy.sort((a, b) => (a.created_at > b.created_at ? -1 : a.created_at < b.created_at ? 1 : 0));
    return copy.slice(0, 15);
  }, [notifications]);

  const handleToggle = () => {
    setOpen((prev) => !prev);
  };

  const handleNotificationClick = async (notificationId: number, linkUrl?: string | null) => {
    await markAsRead(notificationId);
    if (linkUrl) {
      navigate(linkUrl);
      setOpen(false);
    }
  };

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={handleToggle}
        className="relative rounded border border-primary-600 px-3 py-1 text-primary-600 hover:bg-primary-50"
      >
        Notifications
        {unreadCount > 0 && (
          <span className="ml-2 rounded-full bg-primary-600 px-2 py-0.5 text-xs font-semibold text-white">
            {unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-2 w-80 rounded border border-slate-200 bg-white shadow-lg">
          <header className="flex items-center justify-between border-b border-slate-200 px-3 py-2">
            <p className="text-sm font-semibold text-slate-600">Alerts &amp; Updates</p>
            <button
              type="button"
              onClick={() => markAllAsRead()}
              className="text-xs text-primary-600 hover:underline disabled:opacity-50"
              disabled={unreadCount === 0}
            >
              Mark all as read
            </button>
          </header>
          <div className="max-h-80 overflow-y-auto">
            {loading ? (
              <p className="px-4 py-3 text-sm text-slate-500">Loading notifications…</p>
            ) : sortedNotifications.length === 0 ? (
              <p className="px-4 py-3 text-sm text-slate-500">You&apos;re all caught up.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {sortedNotifications.map((notification) => (
                  <li
                    key={notification.id}
                    className={`px-4 py-3 text-sm ${notification.read_at ? 'bg-white' : 'bg-primary-50'}`}
                  >
                    <button
                      type="button"
                      onClick={() => handleNotificationClick(notification.id, notification.link_url)}
                      className="block text-left"
                    >
                      <p className="font-semibold text-slate-700">{notification.title}</p>
                      <p className="mt-1 text-xs text-slate-600">{notification.message}</p>
                      <p className="mt-2 text-[10px] uppercase tracking-wide text-slate-400">
                        {formatTimestamp(notification.created_at)}
                      </p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <footer className="border-t border-slate-200 px-3 py-2 text-right text-xs text-slate-500">
            Showing {sortedNotifications.length} recent
          </footer>
        </div>
      )}
    </div>
  );
};

export default NotificationsMenu;
