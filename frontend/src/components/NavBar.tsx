import React from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import { formatUserRoles } from '../utils/roles';
import NotificationsMenu from './NotificationsMenu';

const NavBar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="bg-white shadow">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link to="/dashboard" className="text-lg font-semibold text-primary-600">
          Liberty Place HOA
        </Link>
        {user && (
          <nav className="flex items-center gap-4 text-sm">
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
