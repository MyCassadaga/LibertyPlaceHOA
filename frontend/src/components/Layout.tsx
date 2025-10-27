import React, { useMemo } from 'react';
import { NavLink, Outlet } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
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
    const base: NavItem[] = [
      { label: 'Dashboard', to: '/dashboard' },
      { label: 'Billing', to: '/billing' },
    ];
    if (user.role.name === 'HOMEOWNER') {
      base.push({ label: 'Owner Profile', to: '/owner-profile' });
    }
    if (["BOARD", "TREASURER", "SYSADMIN", "SECRETARY"].includes(user.role.name)) {
      base.push({ label: 'Owners', to: '/owners' });
    }
    if (["BOARD", "TREASURER", "SYSADMIN", "ATTORNEY"].includes(user.role.name)) {
      base.push({ label: 'Contracts', to: '/contracts' });
    }
    if (["BOARD", "SECRETARY", "SYSADMIN"].includes(user.role.name)) {
      base.push({ label: 'Comms', to: '/communications' });
    }
    return base;
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
