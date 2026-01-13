import React, { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';

import NavBar from './NavBar';
import { useAuth } from '../hooks/useAuth';
import { userHasAnyRole } from '../utils/roles';

const Layout: React.FC = () => {
  const [isNavOpen, setIsNavOpen] = useState(false);
  const { user } = useAuth();

  const handleNavToggle = () => setIsNavOpen((prev) => !prev);
  const closeNav = () => setIsNavOpen(false);

  const renderLink = (
    to: string,
    label: string,
    index: number,
    options?: { end?: boolean },
  ) => (
    <NavLink
      key={`${to}-${index}`}
      to={to}
      end={options?.end ?? true}
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

  const renderExternalLink = (href: string, label: string, index: number) => (
    <a
      key={`${href}-${index}`}
      href={href}
      className="block rounded px-3 py-2 text-sm font-medium text-slate-600 transition-colors duration-150 hover:bg-primary-50"
      target="_blank"
      rel="noreferrer"
      onClick={closeNav}
    >
      {label}
    </a>
  );

  const homeownerLinks = [
    { label: 'Account', to: '/owner-profile' },
    { label: 'ARC Requests', to: '/arc' },
    { label: 'Billing', to: '/billing' },
    { label: 'Documents', to: '/documents' },
    { label: 'Elections', to: '/elections' },
    { label: 'Facebook', href: 'https://www.facebook.com/groups/456044389610375' },
    { label: 'Meetings', to: '/meetings' },
    { label: 'Violations', to: '/violations' },
  ];

  const boardLinks = [
    { label: 'Announcements', to: '/communications' },
    { label: 'Budget', to: '/budget' },
    { label: 'Contracts', to: '/contracts' },
    { label: 'Owners', to: '/owners' },
    { label: 'Reconciliation', to: '/reconciliation' },
    { label: 'Reports', to: '/reports' },
    { label: 'USPS', to: '/board/paperwork' },
  ];

  const canViewBoard = userHasAnyRole(user, [
    'BOARD',
    'TREASURER',
    'SECRETARY',
    'ATTORNEY',
    'SYSADMIN',
  ]);
  const canViewAdmin = userHasAnyRole(user, ['SYSADMIN', 'AUDITOR']);
  const canViewAdminPortal = userHasAnyRole(user, ['SYSADMIN']);
  const canViewAuditLog = userHasAnyRole(user, ['SYSADMIN', 'AUDITOR']);
  const canViewTemplates = userHasAnyRole(user, ['SYSADMIN']);
  const canViewLegal = userHasAnyRole(user, ['LEGAL', 'SYSADMIN']);
  const adminNavItems = [
    { label: 'Audit Log', to: '/audit-log', isVisible: canViewAuditLog },
    { label: 'Templates', to: '/templates', isVisible: canViewTemplates },
    { label: 'Workflows', to: '/admin/workflows', isVisible: canViewAdminPortal },
  ];
  const boardNavItems = (() => {
    const items = [...boardLinks];

    if (canViewLegal) {
      items.push({ label: 'Legal', to: '/legal' });
    }

    return items.sort((a, b) => a.label.localeCompare(b.label));
  })();

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
                {homeownerLinks.map((item, index) =>
                  'href' in item
                    ? renderExternalLink(item.href, item.label, index)
                    : renderLink(item.to, item.label, index),
                )}
              </div>
            </div>

            {canViewBoard && (
              <div>
                <p className="px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Board</p>
                <div className="mt-1 space-y-1">
                  {boardNavItems.map((item, index) => renderLink(item.to, item.label, index))}
                </div>
              </div>
            )}

            {canViewLegal && !canViewBoard && (
              <div>
                <p className="px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Legal</p>
                <div className="mt-1 space-y-1">
                  {renderLink('/legal', 'Legal', 903)}
                </div>
              </div>
            )}

            {canViewAdmin && (
              <div>
                <p className="px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Admin</p>
                <div className="mt-1 space-y-1">
                  {adminNavItems
                    .filter((item) => item.isVisible)
                    .map((item, index) => renderLink(item.to, item.label, index))}
                </div>
              </div>
            )}
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
