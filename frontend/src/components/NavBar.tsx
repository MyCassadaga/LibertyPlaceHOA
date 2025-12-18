import React from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import { formatUserRoles } from '../utils/roles';
import NotificationsMenu from './NotificationsMenu';

interface NavBarProps {
  onMenuToggle?: () => void;
  isMenuOpen?: boolean;
}

const NavBar: React.FC<NavBarProps> = ({ onMenuToggle, isMenuOpen = false }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="bg-white shadow">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center justify-between gap-3">
          {user && onMenuToggle && (
            <button
              type="button"
              onClick={onMenuToggle}
              className="rounded border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50 sm:hidden"
              aria-label="Toggle navigation"
              aria-expanded={isMenuOpen}
            >
              Menu
            </button>
          )}
          <Link to="/dashboard" className="text-lg font-semibold text-primary-600">
            Liberty Place HOA
          </Link>
        </div>
        {user && (
          <nav className="flex flex-wrap items-center gap-3 text-sm sm:justify-end">
            <NotificationsMenu />
            <span className="rounded-full bg-primary-50 px-3 py-1 text-primary-600">
              {formatUserRoles(user)}
            </span>
            <button
              onClick={handleLogout}
              className="rounded border border-primary-600 px-3 py-1 text-primary-600 hover:bg-primary-50"
            >
              Logout
            </button>
          </nav>
        )}
      </div>
    </header>
  );
};

export default NavBar;
