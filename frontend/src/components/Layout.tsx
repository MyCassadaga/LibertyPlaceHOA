import React, { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';

import NavBar from './NavBar';

const Layout: React.FC = () => {
  const [isNavOpen, setIsNavOpen] = useState(false);

  const handleNavToggle = () => setIsNavOpen((prev) => !prev);
  const closeNav = () => setIsNavOpen(false);

  const renderLink = (to: string, label: string, index: number) => (
    <NavLink
      key={`${to}-${index}`}
      to={to}
      className={({ isActive }) =>
        `block rounded px-3 py-2 text-sm font-medium ${
          isActive ? 'bg-primary-600 text-white' : 'text-slate-600 hover:bg-primary-50'
        } transition-colors duration-150`
      }
      onClick={closeNav}
    >
      {label}
    </NavLink>
  );

  const homeownerLinks = [
    { label: 'Account', to: '/owner-profile' },
    { label: 'Billing', to: '/billing' },
    { label: 'Documents', to: '/documents' },
    { label: 'Meetings', to: '/meetings' },
    { label: 'Violations', to: '/violations' },
    { label: 'Elections', to: '/elections' },
    { label: 'ARC', to: '/arc' },
    { label: 'ARC Requests', to: '/arc' },
  ];

  const boardLinks = [
    { label: 'Announcements', to: '/communications' },
    { label: 'Contracts', to: '/contracts' },
    { label: 'Owners', to: '/owners' },
    { label: 'Budget', to: '/budget' },
    { label: 'Reconciliation', to: '/reconciliation' },
    { label: 'Reports', to: '/reports' },
    { label: 'Paperwork', to: '/board/paperwork' },
    { label: 'Templates', to: '/templates' },
  ];

  return (
    <div className="min-h-screen bg-slate-100">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-4 focus:py-2 focus:shadow"
      >
        Skip to main content
      </a>
      <NavBar onMenuToggle={handleNavToggle} isMenuOpen={isNavOpen} />
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-4 sm:px-5 sm:py-6 lg:flex-row lg:px-6">
        <div
          className={`fixed inset-0 z-30 bg-slate-900/40 transition-opacity duration-200 lg:hidden ${
            isNavOpen ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0'
          }`}
          aria-hidden="true"
          onClick={closeNav}
        />
        <aside
          className={`fixed left-0 top-0 z-40 h-full w-full max-w-xs transform overflow-y-auto border-r border-slate-200 bg-white p-4 shadow-lg transition-transform duration-200 lg:static lg:h-auto lg:w-56 lg:translate-x-0 lg:rounded lg:border lg:bg-white lg:shadow ${
            isNavOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
          aria-label="Primary navigation"
        >
          <nav className="space-y-4" aria-label="Primary">
            <div className="flex items-center justify-between lg:hidden">
              <p className="text-sm font-semibold text-slate-700">Navigation</p>
              <button
                type="button"
                className="text-xs font-semibold text-slate-500 hover:text-slate-700"
                onClick={closeNav}
              >
                Close
              </button>
            </div>

            {renderLink('/dashboard', 'Dashboard', 0)}
            {renderLink('/notifications', 'Notifications', 1)}

            <div>
              <p className="px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Homeowner</p>
              <div className="mt-1 space-y-1">
                {homeownerLinks.map((item, index) => renderLink(item.to, item.label, index))}
              </div>
            </div>

            <div>
              <p className="px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Board</p>
              <div className="mt-1 space-y-1">
                {boardLinks.map((item, index) => renderLink(item.to, item.label, index))}
              </div>
            </div>

            <div>
              <p className="px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Admin</p>
              <div className="mt-1 space-y-1">
                {renderLink('/admin', 'Admin', 999)}
                {renderLink('/audit-log', 'Audit Log', 1000)}
              </div>
            </div>
          </nav>
        </aside>
        <main id="main-content" role="main" className="min-w-0 flex-1 rounded bg-white p-4 shadow sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
