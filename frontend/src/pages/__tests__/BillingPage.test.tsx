import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import BillingPage from '../BillingPage';

type MockUser = { primary_role?: { name: string }; roles?: { name: string }[] };
type MockInvoice = { id: number; owner_id: number; amount: string; due_date: string; status: string };
type MockOwner = { id: number; property_address?: string | null };

const noopMutation = { mutateAsync: vi.fn(), isLoading: false };

let mockUser: MockUser | null = null;
let mockInvoices: MockInvoice[] = [];
let mockOwner: MockOwner | null = null;

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ user: mockUser }),
}));

vi.mock('../../features/billing/hooks', () => ({
  useInvoicesQuery: () => ({
    data: mockInvoices,
    isLoading: false,
    isError: false,
  }),
  useOwnersQuery: () => ({
    data: [],
    isLoading: false,
    isError: false,
  }),
  useMyOwnerQuery: () => ({
    data: mockOwner,
    isLoading: false,
    isError: false,
  }),
  useOverdueAccountsQuery: () => ({
    data: [],
    isLoading: false,
    isError: false,
    isFetching: false,
    refetch: vi.fn(),
  }),
  useAutopayQuery: () => ({
    data: null,
    isLoading: false,
    isError: false,
  }),
  useAutopayUpsertMutation: () => noopMutation,
  useAutopayCancelMutation: () => noopMutation,
  useContactOverdueMutation: () => noopMutation,
  useForwardToAttorneyMutation: () => noopMutation,
}));

describe('BillingPage', () => {
  it('shows only the logged-in owner invoices for board members', () => {
    mockUser = { primary_role: { name: 'BOARD' }, roles: [{ name: 'BOARD' }, { name: 'HOMEOWNER' }] };
    mockOwner = { id: 1, property_address: '123 Main Street' };
    mockInvoices = [
      { id: 101, owner_id: 1, amount: '125.00', due_date: '2024-06-10', status: 'OPEN' },
      { id: 202, owner_id: 2, amount: '200.00', due_date: '2024-07-01', status: 'OPEN' },
    ];

    render(<BillingPage />);

    expect(screen.getByText('#101')).toBeInTheDocument();
    expect(screen.queryByText('#202')).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Pay' })).toHaveLength(1);

    const openInvoicesSection = screen.getByText('Open invoices').parentElement;
    expect(openInvoicesSection).toHaveTextContent('1');
  });
});
