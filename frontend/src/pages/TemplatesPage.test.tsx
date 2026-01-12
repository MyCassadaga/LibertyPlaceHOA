import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import TemplatesPage from './TemplatesPage';

vi.mock('../services/api', () => ({
  createTemplate: vi.fn(),
  fetchTemplateMergeTags: vi.fn().mockResolvedValue([]),
  fetchTemplates: vi.fn().mockResolvedValue([]),
  fetchTemplateTypes: vi.fn().mockResolvedValue([
    {
      key: 'billing_notice',
      label: 'Billing Notice',
      definition: 'Emails sent to individuals as a result of billing.',
    },
    {
      key: 'announcement',
      label: 'Announcement',
      definition: 'General communications sent to homeowners.',
    },
  ]),
  updateTemplate: vi.fn(),
}));

const renderTemplatesPage = () => {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={client}>
      <TemplatesPage />
    </QueryClientProvider>,
  );
};

describe('TemplatesPage', () => {
  it('shows Billing Notice in the type selector and definitions table', async () => {
    renderTemplatesPage();

    expect(await screen.findByRole('option', { name: 'Billing Notice' })).toBeInTheDocument();

    const definitionsTable = await screen.findByRole('table');
    expect(within(definitionsTable).getByText('Billing Notice')).toBeInTheDocument();
    expect(
      within(definitionsTable).getByText('Emails sent to individuals as a result of billing.'),
    ).toBeInTheDocument();
  });
});
