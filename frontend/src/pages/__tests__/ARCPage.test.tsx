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
  useSubmitArcReviewMutation: () => ({ mutateAsync: vi.fn(), isLoading: false }),
  useArcReviewersQuery: () => ({ data: [], isLoading: false, isError: false }),
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
  reviews: [],
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

  it('shows reviewer notes after a board member clicks review', () => {
    mockUser = { primary_role: { name: 'BOARD' }, roles: [{ name: 'BOARD' }] };
    mockRequests = [
      { ...buildRequest(1, 'Review Request', 'Fence', '2024-05-01T12:00:00Z'), status: 'IN_REVIEW' },
    ];

    render(<ARCPage />);

    expect(screen.queryByText('Reviewer Notes')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Review' }));
    expect(screen.getByText('Reviewer Notes')).toBeInTheDocument();
  });

  it('hides reviewer notes when a request is not in review', () => {
    mockUser = { primary_role: { name: 'BOARD' }, roles: [{ name: 'BOARD' }] };
    mockRequests = [
      { ...buildRequest(1, 'Submitted Request', 'Fence', '2024-05-01T12:00:00Z'), status: 'SUBMITTED' },
    ];

    render(<ARCPage />);

    expect(screen.queryByText('Reviewer Notes')).not.toBeInTheDocument();
  });

  it('uses the submit label for reviewer notes', () => {
    mockUser = { primary_role: { name: 'BOARD' }, roles: [{ name: 'BOARD' }] };
    mockRequests = [
      { ...buildRequest(1, 'Review Request', 'Fence', '2024-05-01T12:00:00Z'), status: 'IN_REVIEW' },
    ];

    render(<ARCPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Review' }));
    expect(screen.getByRole('button', { name: 'Submit' })).toBeInTheDocument();
  });

  it('renders comments without resolved controls', () => {
    mockUser = { primary_role: { name: 'BOARD' }, roles: [{ name: 'BOARD' }] };
    mockRequests = [
      {
        ...buildRequest(1, 'Review Request', 'Fence', '2024-05-01T12:00:00Z'),
        status: 'IN_REVIEW',
        conditions: [
          {
            id: 1,
            arc_request_id: 1,
            condition_type: 'COMMENT',
            text: 'Looks good.',
            status: 'RESOLVED',
            created_at: '2024-05-02T12:00:00Z',
            resolved_at: '2024-05-03T12:00:00Z',
            created_by_user_id: 1,
          },
        ],
      },
    ];

    render(<ARCPage />);

    expect(screen.getByText('Looks good.')).toBeInTheDocument();
    expect(screen.queryByText('Resolved')).not.toBeInTheDocument();
    expect(screen.queryByText('Mark Resolved')).not.toBeInTheDocument();
    expect(screen.queryByText('Reopen')).not.toBeInTheDocument();
  });

  it('renders the review button after attachments and comments', () => {
    mockUser = { primary_role: { name: 'BOARD' }, roles: [{ name: 'BOARD' }] };
    mockRequests = [
      { ...buildRequest(1, 'Submitted Request', 'Fence', '2024-05-01T12:00:00Z'), status: 'SUBMITTED' },
    ];

    render(<ARCPage />);

    const attachmentsHeading = screen.getByText('Attachments');
    const commentsHeading = screen.getByText('Comments & Conditions');
    const reviewButton = screen.getByRole('button', { name: 'Review' });

    expect(attachmentsHeading.compareDocumentPosition(reviewButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(commentsHeading.compareDocumentPosition(reviewButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
