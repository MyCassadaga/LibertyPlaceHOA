import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { createTemplate, fetchTemplateMergeTags, fetchTemplates, updateTemplate } from '../services/api';
import { Template } from '../types';
import { queryKeys } from '../lib/api/queryKeys';
import { renderMergeTags } from '../utils/mergeTags';

const TEMPLATE_TYPES = [
  { value: 'ANNOUNCEMENT', label: 'Announcement' },
  { value: 'BROADCAST', label: 'Broadcast' },
  { value: 'NOTICE', label: 'Notice' },
  { value: 'VIOLATION_NOTICE', label: 'Violation Notice' },
  { value: 'ARC_REQUEST', label: 'ARC Request' },
];

const TemplatesPage: React.FC = () => {
  const [typeFilter, setTypeFilter] = useState('');
  const [includeArchived, setIncludeArchived] = useState(false);
  const [search, setSearch] = useState('');
  const [editingTemplateId, setEditingTemplateId] = useState<number | null>(null);
  const [formState, setFormState] = useState({
    name: '',
    type: 'ANNOUNCEMENT',
    subject: '',
    body: '',
    is_archived: false,
  });
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const templatesQuery = useQuery<Template[]>({
    queryKey: [queryKeys.templates, { typeFilter, includeArchived, search }],
    queryFn: () =>
      fetchTemplates({
        type: typeFilter || undefined,
        include_archived: includeArchived,
        query: search || undefined,
      }),
  });

  const mergeTagsQuery = useQuery({
    queryKey: queryKeys.templateMergeTags,
    queryFn: fetchTemplateMergeTags,
  });

  const templates = useMemo(() => templatesQuery.data ?? [], [templatesQuery.data]);
  const mergeTags = mergeTagsQuery.data ?? [];

  const handleEdit = (template: Template) => {
    setEditingTemplateId(template.id);
    setFormState({
      name: template.name,
      type: template.type,
      subject: template.subject,
      body: template.body,
      is_archived: template.is_archived,
    });
    setStatus(null);
    setError(null);
  };

  const handleReset = () => {
    setEditingTemplateId(null);
    setFormState({
      name: '',
      type: 'ANNOUNCEMENT',
      subject: '',
      body: '',
      is_archived: false,
    });
    setStatus(null);
    setError(null);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setStatus(null);
    setError(null);
    try {
      if (editingTemplateId) {
        await updateTemplate(editingTemplateId, formState);
        setStatus('Template updated successfully.');
      } else {
        await createTemplate(formState);
        setStatus('Template created successfully.');
      }
      await templatesQuery.refetch();
      handleReset();
    } catch (err) {
      console.error('Unable to save template', err);
      setError('Unable to save template.');
    }
  };

  const previewSubject = renderMergeTags(formState.subject, mergeTags);
  const previewBody = renderMergeTags(formState.body, mergeTags);

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h2 className="text-xl font-semibold text-slate-700">Templates</h2>
        <p className="text-sm text-slate-500">Manage reusable message templates for communications and notices.</p>
      </header>

      <section className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-6">
          <div className="rounded border border-slate-200 p-4">
            <h3 className="mb-3 text-lg font-semibold text-slate-700">
              {editingTemplateId ? 'Edit Template' : 'Create Template'}
            </h3>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="template-name">
                    Name
                  </label>
                  <input
                    id="template-name"
                    className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                    value={formState.name}
                    onChange={(event) => setFormState((prev) => ({ ...prev, name: event.target.value }))}
                    required
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="template-type">
                    Template type
                  </label>
                  <select
                    id="template-type"
                    className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                    value={formState.type}
                    onChange={(event) => setFormState((prev) => ({ ...prev, type: event.target.value }))}
                    required
                  >
                    {TEMPLATE_TYPES.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="template-subject">
                  Subject
                </label>
                <input
                  id="template-subject"
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                  value={formState.subject}
                  onChange={(event) => setFormState((prev) => ({ ...prev, subject: event.target.value }))}
                  required
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="template-body">
                  Body
                </label>
                <textarea
                  id="template-body"
                  rows={6}
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                  value={formState.body}
                  onChange={(event) => setFormState((prev) => ({ ...prev, body: event.target.value }))}
                  required
                />
              </div>

              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-300"
                  checked={formState.is_archived}
                  onChange={(event) => setFormState((prev) => ({ ...prev, is_archived: event.target.checked }))}
                />
                Archived
              </label>

              <div className="rounded border border-slate-100 bg-slate-50 p-3 text-xs text-slate-600">
                <p className="font-semibold text-slate-700">Preview with sample data</p>
                <p className="mt-2 text-slate-500">Subject: {previewSubject || '—'}</p>
                <p className="mt-2 whitespace-pre-wrap text-slate-500">{previewBody || 'Preview will appear here.'}</p>
              </div>

              {status && <p className="text-sm text-green-600">{status}</p>}
              {error && <p className="text-sm text-red-600">{error}</p>}

              <div className="flex flex-wrap gap-2">
                <button
                  type="submit"
                  className="rounded bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-500"
                >
                  {editingTemplateId ? 'Save Changes' : 'Create Template'}
                </button>
                {editingTemplateId && (
                  <button
                    type="button"
                    className="rounded border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50"
                    onClick={handleReset}
                  >
                    Cancel
                  </button>
                )}
              </div>
            </form>
          </div>

          <div className="rounded border border-slate-200 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-lg font-semibold text-slate-700">Template Library</h3>
              <div className="flex flex-wrap gap-2">
                <input
                  className="rounded border border-slate-300 px-3 py-2 text-sm"
                  placeholder="Search by name or subject"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
                <select
                  className="rounded border border-slate-300 px-3 py-2 text-sm"
                  value={typeFilter}
                  onChange={(event) => setTypeFilter(event.target.value)}
                >
                  <option value="">All types</option>
                  {TEMPLATE_TYPES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <label className="flex items-center gap-2 text-sm text-slate-600">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-slate-300"
                    checked={includeArchived}
                    onChange={(event) => setIncludeArchived(event.target.checked)}
                  />
                  Include archived
                </label>
              </div>
            </div>
            {templatesQuery.isError && (
              <p className="mt-3 text-sm text-red-600">Unable to load templates.</p>
            )}
            <div className="mt-4 space-y-3">
              {templates.length === 0 ? (
                <p className="text-sm text-slate-500">No templates match the current filters.</p>
              ) : (
                templates.map((template) => (
                  <div
                    key={template.id}
                    className={`rounded border p-3 text-sm ${
                      template.is_archived ? 'border-amber-200 bg-amber-50/60' : 'border-slate-200'
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="font-semibold text-slate-700">{template.name}</p>
                        <p className="text-xs text-slate-500">{template.type}</p>
                      </div>
                      <button
                        type="button"
                        className="rounded border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                        onClick={() => handleEdit(template)}
                      >
                        Edit
                      </button>
                    </div>
                    <p className="mt-2 text-xs text-slate-500">Subject: {template.subject}</p>
                    <p className="mt-2 whitespace-pre-wrap text-xs text-slate-500">{template.body}</p>
                    {template.is_archived && (
                      <p className="mt-2 text-xs font-semibold text-amber-700">Archived</p>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <aside className="rounded border border-slate-200 p-4">
          <h3 className="text-lg font-semibold text-slate-700">Merge Tags</h3>
          <p className="mt-1 text-sm text-slate-500">
            Use merge tags in subjects or bodies. Preview data uses the sample values below.
          </p>
          {mergeTagsQuery.isError && (
            <p className="mt-3 text-sm text-red-600">Unable to load merge tags.</p>
          )}
          <div className="mt-4 space-y-3 text-sm text-slate-600">
            {mergeTags.map((tag) => (
              <div key={tag.key} className="rounded border border-slate-100 bg-slate-50 p-3">
                <p className="font-semibold text-slate-700">
                  {'{{'}
                  {tag.key}
                  {'}}'}
                </p>
                <p className="text-xs text-slate-500">{tag.description}</p>
                <p className="mt-1 text-xs text-slate-500">Sample: {tag.sample}</p>
              </div>
            ))}
          </div>
        </aside>
      </section>
    </div>
  );
};

export default TemplatesPage;
