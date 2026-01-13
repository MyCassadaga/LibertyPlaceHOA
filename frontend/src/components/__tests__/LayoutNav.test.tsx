import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import Layout from '../Layout';

const mockUser = {
  id: 7,
  email: 'admin@example.com',
  full_name: 'Admin User',
  role: null,
  primary_role: null,
  roles: [{ id: 1, name: 'SYSADMIN' }],
  created_at: '2024-01-01T00:00:00Z',
  is_active: true,
  two_factor_enabled: false,
};

const mockLogout = vi.fn();

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: mockUser,
    token: 'token',
    loading: false,
    login: vi.fn(),
    logout: mockLogout,
    refresh: vi.fn(),
  }),
}));

vi.mock('../../hooks/useNotifications', () => ({
  useNotifications: () => ({
    notifications: [],
    unreadCount: 0,
    loading: false,
    markAsRead: vi.fn(),
    markAllAsRead: vi.fn(),
    connectionState: 'idle',
  }),
}));

const renderLayoutAt = (initialEntry: string) =>
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route path="admin/workflows" element={<div>Admin workflows</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );

describe('Layout navigation', () => {
  it('marks only the exact matching admin workflow route as active', () => {
    renderLayoutAt('/admin/workflows');

    const workflowsLink = screen.getByRole('link', { name: 'Workflows' });
    expect(workflowsLink).toHaveClass('bg-primary-600');

    const adminLinks = [
      screen.getByRole('link', { name: 'Audit Log' }),
      screen.getByRole('link', { name: 'Templates' }),
    ];

    adminLinks.forEach((link) => {
      expect(link).not.toHaveClass('bg-primary-600');
    });

    const activeLinks = screen
      .getAllByRole('link')
      .filter((link) => link.className.includes('bg-primary-600'));
    expect(activeLinks).toEqual([workflowsLink]);
  });

  it('renders admin links alphabetically', () => {
    renderLayoutAt('/admin/workflows');

    const primaryNav = screen.getAllByRole('navigation', { name: 'Primary' })[0];
    const adminHeader = within(primaryNav).getAllByText('Admin')[0];
    const adminSection = adminHeader?.parentElement;
    if (!adminSection) {
      throw new Error('Admin section missing');
    }
    const links = within(adminSection).getAllByRole('link');
    const labels = links.map((link) => link.textContent);

    expect(labels).toEqual(['Audit Log', 'Templates', 'Workflows']);
  });
});
