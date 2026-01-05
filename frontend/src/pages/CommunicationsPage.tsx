import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { useAuth } from '../hooks/useAuth';
import {
  createCommunicationMessage,
  fetchCommunicationMessages,
  fetchTemplateMergeTags,
  fetchTemplates,
} from '../services/api';
import {
  CommunicationMessage,
  Template,
} from '../types';
import { queryKeys } from '../lib/api/queryKeys';
import { renderMergeTags } from '../utils/mergeTags';

const CommunicationsPage: React.FC = () => {
  const { user } = useAuth();
  const [subject, setSubject] = useState('');
  const [messageBody, setMessageBody] = useState('');
  const [formStatus, setFormStatus] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [templateId, setTemplateId] = useState('');
  const [confirmSend, setConfirmSend] = useState(false);

  const messagesQuery = useQuery<CommunicationMessage[]>({
    queryKey: queryKeys.communicationsMessages,
    queryFn: fetchCommunicationMessages,
  });

  const canUseTemplates = useMemo(() => !!user && user.roles?.some((role) => role.name === 'SYSADMIN'), [user]);
  const announcementTemplatesQuery = useQuery<Template[]>({
    queryKey: [queryKeys.templates, 'announcement'],
    queryFn: () => fetchTemplates({ type: 'ANNOUNCEMENT' }),
    enabled: canUseTemplates,
  });

  const mergeTagsQuery = useQuery({
    queryKey: queryKeys.templateMergeTags,
    queryFn: fetchTemplateMergeTags,
    enabled: canUseTemplates,
  });

  const messages = messagesQuery.data ?? [];
  const announcements = useMemo(
    () => messages.filter((message) => message.message_type === 'ANNOUNCEMENT'),
    [messages],
  );
  const announcementTemplates = useMemo(
    () => announcementTemplatesQuery.data ?? [],
    [announcementTemplatesQuery.data],
  );
  const mergeTags = mergeTagsQuery.data ?? [];

  const handleMessageSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormStatus(null);
    setFormError(null);

    if (!subject.trim() || !messageBody.trim()) {
      setFormError('Subject and message are both required.');
      return;
    }

    if (!confirmSend) {
      setFormError('Confirm that you are ready to send this email before continuing.');
      return;
    }

    try {
      await createCommunicationMessage({
        message_type: 'ANNOUNCEMENT',
        subject,
        body: messageBody,
        delivery_methods: ['email'],
      });
      setFormStatus('Email sent to all homeowners.');

      setSubject('');
      setMessageBody('');
      setFormError(null);
      setTemplateId('');
      setConfirmSend(false);
      await messagesQuery.refetch();
    } catch (err) {
      console.error('Unable to create communication message', err);
      setFormStatus(null);
      setFormError('Unable to record the communication.');
    }
  };

  const availableTemplates = useMemo(() => announcementTemplates, [announcementTemplates]);

  const handleTemplateChange = (selectedId: string) => {
    setTemplateId(selectedId);
    const template = availableTemplates.find((item) => item.id === Number(selectedId));
    if (template) {
      setSubject(template.subject);
      setMessageBody(template.body);
    }
  };

  const bodyPreview = renderMergeTags(messageBody, mergeTags);
  const subjectPreview = renderMergeTags(subject, mergeTags);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-slate-700">Community Communications</h2>

      <section className="rounded border border-slate-200 p-4">
        <h3 className="mb-3 text-lg font-semibold text-slate-700">Create Communication</h3>
        <form className="space-y-4" onSubmit={handleMessageSubmit}>
          <p className="text-sm text-slate-500">
            All messages sent here are delivered as an email to every homeowner on file.
          </p>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="message-template">
              Template (optional)
            </label>
            <select
              id="message-template"
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              value={templateId}
              onChange={(event) => handleTemplateChange(event.target.value)}
              disabled={announcementTemplatesQuery.isLoading || availableTemplates.length === 0}
            >
              <option value="">No template</option>
              {availableTemplates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="message-subject">
              Subject
            </label>
            <input
              id="message-subject"
              className="w-full rounded border border-slate-300 px-3 py-2"
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              required
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="message-body">
              Message
            </label>
            <textarea
              id="message-body"
              rows={5}
              className="w-full rounded border border-slate-300 px-3 py-2"
              value={messageBody}
              onChange={(event) => setMessageBody(event.target.value)}
              required
            />
            <p className="mt-2 text-xs text-slate-500">
              Preview: <span className="font-medium text-slate-600">{subjectPreview || '—'}</span>
            </p>
            <p className="mt-1 whitespace-pre-wrap text-xs text-slate-500">{bodyPreview || '—'}</p>
          </div>

          {formStatus && <p className="text-sm text-green-600">{formStatus}</p>}
          {formError && <p className="text-sm text-red-600">{formError}</p>}

          <label className="flex items-start gap-3 rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
            <input
              type="checkbox"
              className="mt-1"
              checked={confirmSend}
              onChange={(event) => setConfirmSend(event.target.checked)}
              required
            />
            <span>
              Click here to confirm you want to send this email. This prevents accidentally pressing send before the
              message is complete.
            </span>
          </label>

          <button
            type="submit"
            className="rounded bg-primary-600 px-4 py-2 text-white hover:bg-primary-500 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            Send
          </button>
        </form>
      </section>

      <section className="rounded border border-slate-200 p-4">
        <h3 className="mb-3 text-lg font-semibold text-slate-700">Email History</h3>
        {messagesQuery.isError && (
          <p className="mb-3 text-sm text-red-600">Unable to load communication history.</p>
        )}
        {announcements.length === 0 ? (
          <p className="text-sm text-slate-500">
            {messagesQuery.isLoading ? 'Loading history…' : 'No communications have been recorded yet.'}
          </p>
        ) : (
          <ul className="space-y-3 text-sm">
            {announcements.map((announcement) => (
              <li key={announcement.id} className="rounded border border-slate-200">
                <details className="group">
                  <summary className="flex cursor-pointer list-none items-start justify-between gap-4 rounded px-3 py-3 hover:bg-slate-50">
                    <div className="grid w-full gap-2 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto] sm:items-center">
                      <div className="min-w-0">
                        <p className="text-xs uppercase text-slate-400">Email blast</p>
                        <h4 className="truncate font-semibold text-slate-700">{announcement.subject}</h4>
                      </div>
                      <div>
                        <p className="text-xs text-slate-400">Delivery method</p>
                        <p className="font-medium text-slate-600">Email</p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-slate-400">Sent</p>
                        <p className="font-medium text-slate-600">
                          {new Date(announcement.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    <span className="text-xs font-semibold text-primary-600 group-open:text-primary-700">
                      Details
                    </span>
                  </summary>
                  <div className="border-t border-slate-200 px-3 py-3">
                    <div className="grid gap-4 text-xs text-slate-600 sm:grid-cols-3">
                      <div>
                        <p className="text-slate-400">Delivery</p>
                        <p className="font-semibold text-slate-700">
                          All homeowners
                        </p>
                      </div>
                      <div>
                        <p className="text-slate-400">Recipients stored</p>
                        <p className="font-semibold text-slate-700">{announcement.recipient_count}</p>
                      </div>
                      <div>
                        <p className="text-slate-400">Printable</p>
                        <p className="font-semibold text-slate-700">Not available</p>
                      </div>
                    </div>
                    <p className="mt-3 whitespace-pre-wrap text-sm text-slate-600">{announcement.body}</p>
                    <div className="mt-4">
                      <p className="text-xs font-semibold text-primary-600">
                        Recipient snapshot ({announcement.recipient_count})
                      </p>
                      <ul className="mt-2 grid gap-2 text-xs md:grid-cols-2">
                        {(announcement.recipients ?? []).map((recipient) => (
                          <li
                            key={`${recipient.email}-${recipient.owner_id ?? 'none'}-${recipient.contact_type ?? 'contact'}`}
                            className="rounded border border-slate-200 p-2"
                          >
                            <p className="font-medium text-slate-700">{recipient.email}</p>
                            <p className="text-slate-500">
                              {recipient.owner_name ?? 'Unassigned'}
                              {recipient.property_address ? ` • ${recipient.property_address}` : ''}
                              {recipient.contact_type ? ` (${recipient.contact_type})` : ''}
                            </p>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </details>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
};

export default CommunicationsPage;
