import React, { useMemo } from 'react';
import { NavLink, Outlet } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import { userHasAnyRole, userHasRole } from '../utils/roles';
import NavBar from './NavBar';

interface NavItem {
  label: string;
  to: string;
  roles?: string[];
}

const Layout: React.FC = () => {
  const { user } = useAuth();

  const navItems = useMemo<NavItem[]>(() => {
    if (!user) return [];
    const entries = new Map<string, NavItem>();
    const addItem = (label: string, to: string) => {
      if (!entries.has(to)) {
        entries.set(to, { label, to });
      }
    };

    addItem('Dashboard', '/dashboard');
    addItem('Billing', '/billing');
    addItem('Account', '/owner-profile');

    if (userHasRole(user, 'HOMEOWNER')) {
      addItem('Violations', '/violations');
      addItem('ARC Requests', '/arc');
    }
    if (userHasAnyRole(user, ['BOARD', 'TREASURER', 'SYSADMIN', 'SECRETARY'])) {
      addItem('Owners', '/owners');
    }
    if (userHasAnyRole(user, ['BOARD', 'TREASURER', 'SYSADMIN', 'ATTORNEY'])) {
      addItem('Contracts', '/contracts');
    }
    if (userHasAnyRole(user, ['BOARD', 'SECRETARY', 'SYSADMIN'])) {
      addItem('Comms', '/communications');
    }
    if (userHasAnyRole(user, ['BOARD', 'TREASURER', 'SYSADMIN', 'SECRETARY', 'ATTORNEY'])) {
      addItem('Violations', '/violations');
    }
    if (userHasAnyRole(user, ['ARC', 'BOARD', 'SYSADMIN', 'SECRETARY'])) {
      addItem('ARC Requests', '/arc');
    }
    if (userHasAnyRole(user, ['BOARD', 'TREASURER', 'SYSADMIN'])) {
      addItem('Reconciliation', '/reconciliation');
    }
    if (userHasAnyRole(user, ['BOARD', 'SYSADMIN'])) {
      addItem('Reports', '/reports');
    }
    if (userHasRole(user, 'SYSADMIN')) {
      addItem('Admin', '/admin');
    }

    return Array.from(entries.values());
  }, [user]);

  return (
    <div className="min-h-screen bg-slate-100">
      <NavBar />
      <div className="mx-auto flex max-w-6xl gap-6 px-4 py-6">
        <aside className="w-48">
          <nav className="space-y-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `block rounded px-3 py-2 text-sm font-medium ${
                    isActive ? 'bg-primary-600 text-white' : 'text-slate-600 hover:bg-primary-50'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="flex-1 rounded bg-white p-6 shadow">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
