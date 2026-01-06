import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ARCPage from '../ARCPage';

let mockUser: { primary_role?: { name: string }; roles?: { name: string }[] } | null = null;
let mockRequests: any[] = [];
let mockLinkedOwners: any[] = [];

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ user: mockUser }),
}));

vi.mock('../../features/arc/hooks', () => ({
  useArcRequestsQuery: () => ({
    data: mockRequests,
    isLoading: false,
    isError: false,
  }),
  useCreateArcRequestMutation: () => ({ mutateAsync: vi.fn(), isLoading: false }),
  useTransitionArcRequestMutation: () => ({ mutateAsync: vi.fn(), isLoading: false }),
  useReopenArcRequestMutation: () => ({ mutateAsync: vi.fn(), isLoading: false }),
  useUploadArcAttachmentMutation: () => ({ mutateAsync: vi.fn(), isLoading: false }),
  useAddArcConditionMutation: () => ({ mutateAsync: vi.fn(), isLoading: false }),
  useResolveArcConditionMutation: () => ({ mutateAsync: vi.fn(), isLoading: false }),
  useCreateArcInspectionMutation: () => ({ mutateAsync: vi.fn(), isLoading: false }),
}));

vi.mock('../../features/billing/hooks', () => ({
  useOwnersQuery: () => ({ data: [], isError: false }),
  useMyLinkedOwnersQuery: () => ({ data: mockLinkedOwners, isError: false }),
}));

vi.mock('../../components/Timeline', () => ({
  default: () => <div data-testid="timeline" />,
}));

vi.mock('../../components/FilePreview', () => ({
  default: () => <div data-testid="file-preview" />,
}));

const buildRequest = (id: number, title: string, projectType: string, createdAt: string) => ({
  id,
  owner_id: 1,
  submitted_by_user_id: 1,
  reviewer_user_id: null,
  reviewer_name: null,
  title,
  project_type: projectType,
  description: `Description for ${title}`,
  status: 'SUBMITTED',
  submitted_at: createdAt,
  decision_notes: null,
  final_decision_at: null,
  final_decision_by_user_id: null,
  revision_requested_at: null,
  completed_at: null,
  archived_at: null,
  created_at: createdAt,
  updated_at: createdAt,
  owner: {
    id: 1,
    primary_name: 'Owner Name',
    property_address: '123 Main Street',
    is_archived: false,
    is_rental: false,
  },
  attachments: [],
  conditions: [],
  inspections: [],
});

describe('ARCPage', () => {
  beforeEach(() => {
    mockRequests = [];
    mockLinkedOwners = [];
    mockUser = null;
  });

  it('hides the request queue for homeowners and defaults to the most recent request', () => {
    mockUser = { primary_role: { name: 'HOMEOWNER' }, roles: [{ name: 'HOMEOWNER' }] };
    mockRequests = [
      buildRequest(2, 'Latest Request', 'Deck', '2024-06-10T12:00:00Z'),
      buildRequest(1, 'Older Request', 'Fence', '2024-05-01T12:00:00Z'),
    ];
    mockLinkedOwners = [
      { id: 1, property_address: '123 Main Street', primary_name: 'Owner Name' },
    ];

    render(<ARCPage />);

    expect(screen.getByText('Submit an ARC Request')).toBeInTheDocument();
    expect(screen.queryByText('Request Queue')).not.toBeInTheDocument();
    expect(screen.getByText('Review Request')).toBeInTheDocument();
    expect(screen.getByText('Project Type: Deck')).toBeInTheDocument();
    expect(screen.getByLabelText('Address')).toBeInTheDocument();
  });

  it('shows the request queue for board members and updates selection on click', () => {
    mockUser = { primary_role: { name: 'BOARD' }, roles: [{ name: 'BOARD' }] };
    mockRequests = [
      buildRequest(2, 'Latest Request', 'Deck', '2024-06-10T12:00:00Z'),
      buildRequest(1, 'Older Request', 'Fence', '2024-05-01T12:00:00Z'),
    ];

    render(<ARCPage />);

    expect(screen.getByText('Request Queue')).toBeInTheDocument();
    expect(screen.getByText('Project Type: Deck')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Older Request'));
    expect(screen.getByText('Project Type: Fence')).toBeInTheDocument();
  });
});
