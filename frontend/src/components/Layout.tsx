import React, { useMemo } from 'react';
import { NavLink, Outlet } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import { userHasAnyRole, userHasRole } from '../utils/roles';
import NavBar from './NavBar';

const boardRoles = ['BOARD', 'TREASURER', 'SECRETARY', 'SYSADMIN', 'ATTORNEY'];

const Layout: React.FC = () => {
  const { user } = useAuth();

  const { isHomeowner, isBoard, isSysAdmin, isAuditor } = useMemo(() => {
    if (!user) {
      return { isHomeowner: false, isBoard: false, isSysAdmin: false, isAuditor: false };
    }
    return {
      isHomeowner: userHasRole(user, 'HOMEOWNER'),
      isBoard: userHasAnyRole(user, boardRoles),
      isSysAdmin: userHasRole(user, 'SYSADMIN'),
      isAuditor: userHasRole(user, 'AUDITOR'),
    };
  }, [user]);

  const renderLink = (to: string, label: string, index: number) => (
    <NavLink
      key={`${to}-${index}`}
      to={to}
      className={({ isActive }) =>
        `block rounded px-3 py-2 text-sm font-medium ${
          isActive ? 'bg-primary-600 text-white' : 'text-slate-600 hover:bg-primary-50'
        }`
      }
    >
      {label}
    </NavLink>
  );

  const homeownerLinks = useMemo(() => {
    if (!user || !isHomeowner) return [];
    const items: { label: string; to: string; roles?: string[] }[] = [
      { label: 'Account', to: '/owner-profile' },
      { label: 'ARC Requests', to: '/arc' },
      { label: 'Budget', to: '/budget' },
      { label: 'Billing', to: '/billing' },
      { label: 'Documents', to: '/documents' },
      { label: 'Elections', to: '/elections' },
      { label: 'Meetings', to: '/meetings' },
      { label: 'Violations', to: '/violations' },
    ];
    return items
      .filter((item) => (item.roles ? userHasAnyRole(user, item.roles) : true))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [isHomeowner, user]);

  const homeownerRoutes = useMemo(() => new Set(homeownerLinks.map((item) => item.to)), [homeownerLinks]);

  const boardLinks = useMemo(() => {
    if (!user || !isBoard) return [];
    const items: { label: string; to: string; roles?: string[] }[] = [
      { label: 'Budget', to: '/budget' },
      { label: 'Paperwork', to: '/board/paperwork' },
      { label: 'Comms', to: '/communications', roles: ['BOARD', 'SECRETARY', 'SYSADMIN'] },
      { label: 'Contracts', to: '/contracts', roles: ['BOARD', 'TREASURER', 'SYSADMIN', 'ATTORNEY'] },
      { label: 'Owners', to: '/owners', roles: ['BOARD', 'TREASURER', 'SYSADMIN', 'SECRETARY'] },
      { label: 'Reports', to: '/reports', roles: ['BOARD', 'SYSADMIN'] },
      { label: 'Reconciliation', to: '/reconciliation', roles: ['BOARD', 'TREASURER', 'SYSADMIN'] },
    ];
    return items
      .filter(
        (item) =>
          (!item.roles || userHasAnyRole(user, item.roles)) &&
          !(isHomeowner && homeownerRoutes.has(item.to)),
      )
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [homeownerRoutes, isBoard, isHomeowner, user]);

  return (
    <div className="min-h-screen bg-slate-100">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-4 focus:py-2 focus:shadow"
      >
        Skip to main content
      </a>
      <NavBar />
      <div className="mx-auto flex max-w-6xl gap-6 px-4 py-6">
        <aside className="w-52">
          <nav className="space-y-4" aria-label="Primary">
            {renderLink('/dashboard', 'Dashboard', 0)}
            {renderLink('/notifications', 'Notifications', 1)}

            {isHomeowner && homeownerLinks.length > 0 && (
              <div>
                <p className="px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Homeowner</p>
                <div className="mt-1 space-y-1">
                  {homeownerLinks.map((item, index) => renderLink(item.to, item.label, index))}
                </div>
              </div>
            )}

            {isBoard && boardLinks.length > 0 && (
              <div>
                <p className="px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Board</p>
                <div className="mt-1 space-y-1">
                  {boardLinks.map((item, index) => renderLink(item.to, item.label, index))}
                </div>
              </div>
            )}

            {(isSysAdmin || isAuditor) && (
              <div>
                <p className="px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Admin</p>
                <div className="mt-1 space-y-1">
                  {isSysAdmin && renderLink('/admin', 'Admin', 999)}
                  {renderLink('/audit-log', 'Audit Log', 1000)}
                </div>
              </div>
            )}
          </nav>
        </aside>
        <main id="main-content" role="main" className="flex-1 rounded bg-white p-6 shadow">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
