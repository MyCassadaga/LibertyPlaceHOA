import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import {
  createCommunicationMessage,
  fetchBroadcastSegments,
  fetchCommunicationMessages,
  fetchTemplateMergeTags,
  fetchTemplates,
} from '../services/api';
import {
  CommunicationMessage,
  EmailBroadcastSegment,
  Template,
} from '../types';
import { queryKeys } from '../lib/api/queryKeys';
import { renderMergeTags } from '../utils/mergeTags';

const CommunicationsPage: React.FC = () => {
  const [messageType, setMessageType] = useState<'BROADCAST' | 'ANNOUNCEMENT'>('BROADCAST');
  const [subject, setSubject] = useState('');
  const [messageBody, setMessageBody] = useState('');
  const [deliveryEmail, setDeliveryEmail] = useState(true);
  const [deliveryPrint, setDeliveryPrint] = useState(false);
  const [selectedSegment, setSelectedSegment] = useState('');
  const [formStatus, setFormStatus] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [templateId, setTemplateId] = useState('');

  const messagesQuery = useQuery<CommunicationMessage[]>({
    queryKey: queryKeys.communicationsMessages,
    queryFn: fetchCommunicationMessages,
  });

  const segmentsQuery = useQuery<EmailBroadcastSegment[]>({
    queryKey: queryKeys.broadcastSegments,
    queryFn: fetchBroadcastSegments,
  });

  const announcementTemplatesQuery = useQuery<Template[]>({
    queryKey: [queryKeys.templates, 'announcement'],
    queryFn: () => fetchTemplates({ type: 'ANNOUNCEMENT' }),
  });

  const broadcastTemplatesQuery = useQuery<Template[]>({
    queryKey: [queryKeys.templates, 'broadcast'],
    queryFn: () => fetchTemplates({ type: 'BROADCAST' }),
  });

  const mergeTagsQuery = useQuery({
    queryKey: queryKeys.templateMergeTags,
    queryFn: fetchTemplateMergeTags,
  });

  const messages = messagesQuery.data ?? [];
  const announcementTemplates = useMemo(
    () => announcementTemplatesQuery.data ?? [],
    [announcementTemplatesQuery.data],
  );
  const broadcastTemplates = useMemo(
    () => broadcastTemplatesQuery.data ?? [],
    [broadcastTemplatesQuery.data],
  );
  const mergeTags = mergeTagsQuery.data ?? [];
  const broadcastSegments = useMemo(
    () => segmentsQuery.data ?? [],
    [segmentsQuery.data],
  );

  const resolvedSegment = useMemo(() => {
    if (!broadcastSegments.length) {
      return '';
    }
    if (selectedSegment && broadcastSegments.some((segment) => segment.key === selectedSegment)) {
      return selectedSegment;
    }
    return broadcastSegments[0]?.key ?? '';
  }, [broadcastSegments, selectedSegment]);

  const handleMessageTypeChange = (value: 'BROADCAST' | 'ANNOUNCEMENT') => {
    setMessageType(value);
    setTemplateId('');
    setFormStatus(null);
    setFormError(null);
  };

  const handleMessageSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormStatus(null);
    setFormError(null);

    if (!subject.trim() || !messageBody.trim()) {
      setFormError('Subject and message are both required.');
      return;
    }

    try {
      if (messageType === 'BROADCAST') {
        if (!resolvedSegment) {
          setFormError('Choose at least one recipient segment.');
          return;
        }
        await createCommunicationMessage({
          message_type: 'BROADCAST',
          subject,
          body: messageBody,
          segment: resolvedSegment,
        });
        setFormStatus('Broadcast recorded for compliance.');
      } else {
        const deliveryMethods = [] as string[];
        if (deliveryEmail) deliveryMethods.push('email');
        if (deliveryPrint) deliveryMethods.push('print');
        if (deliveryMethods.length === 0) {
          setFormError('Select at least one delivery method.');
          return;
        }
        await createCommunicationMessage({
          message_type: 'ANNOUNCEMENT',
          subject,
          body: messageBody,
          delivery_methods: deliveryMethods,
        });
        setFormStatus('Announcement queued successfully.');
      }

      setSubject('');
      setMessageBody('');
      setDeliveryEmail(true);
      setDeliveryPrint(false);
      setFormError(null);
      setTemplateId('');
      await messagesQuery.refetch();
    } catch (err) {
      console.error('Unable to create communication message', err);
      setFormStatus(null);
      setFormError('Unable to record the communication.');
    }
  };

  const selectedSegmentDetails = useMemo(
    () => broadcastSegments.find((segment) => segment.key === resolvedSegment),
    [broadcastSegments, resolvedSegment],
  );

  const segmentLookup = useMemo(() => {
    return broadcastSegments.reduce<Record<string, EmailBroadcastSegment>>((acc, segment) => {
      acc[segment.key] = segment;
      return acc;
    }, {});
  }, [broadcastSegments]);

  const resolveSegmentLabel = (segmentKey: string) => {
    if (segmentLookup[segmentKey]) {
      return segmentLookup[segmentKey].label;
    }
    return segmentKey.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (char) => char.toUpperCase());
  };

  const availableTemplates = useMemo(
    () => (messageType === 'BROADCAST' ? broadcastTemplates : announcementTemplates),
    [announcementTemplates, broadcastTemplates, messageType],
  );

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
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium text-slate-600">Delivery type</legend>
            <div className="flex flex-wrap gap-4 text-sm text-slate-600">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="delivery-type"
                  value="BROADCAST"
                  checked={messageType === 'BROADCAST'}
                  onChange={() => handleMessageTypeChange('BROADCAST')}
                />
                Email broadcast
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="delivery-type"
                  value="ANNOUNCEMENT"
                  checked={messageType === 'ANNOUNCEMENT'}
                  onChange={() => handleMessageTypeChange('ANNOUNCEMENT')}
                />
                Announcement
              </label>
            </div>
          </fieldset>

          {messageType === 'BROADCAST' && (
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="broadcast-segment">
                Recipient segment
              </label>
              <select
                id="broadcast-segment"
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                value={resolvedSegment}
                onChange={(event) => setSelectedSegment(event.target.value)}
                disabled={segmentsQuery.isLoading || broadcastSegments.length === 0}
              >
                {segmentsQuery.isLoading && <option value="">Loading segments...</option>}
                {broadcastSegments.map((segment) => (
                  <option key={segment.key} value={segment.key}>
                    {segment.label} ({segment.recipient_count})
                  </option>
                ))}
              </select>
              {selectedSegmentDetails && (
                <p className="mt-2 text-xs text-slate-500">
                  {selectedSegmentDetails.description}{' '}
                  <span className="font-medium text-slate-600">
                    • Recipients with email: {selectedSegmentDetails.recipient_count}
                  </span>
                </p>
              )}
              {segmentsQuery.isError && (
                <p className="mt-2 text-xs text-red-600">Unable to load broadcast segments.</p>
              )}
            </div>
          )}

          {messageType === 'ANNOUNCEMENT' && (
            <fieldset className="flex gap-4 text-sm text-slate-600">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={deliveryEmail}
                  onChange={(event) => setDeliveryEmail(event.target.checked)}
                />
                Email blast
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={deliveryPrint}
                  onChange={(event) => setDeliveryPrint(event.target.checked)}
                />
                Print-ready packet
              </label>
            </fieldset>
          )}

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="message-template">
              Template (optional)
            </label>
            <select
              id="message-template"
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              value={templateId}
              onChange={(event) => handleTemplateChange(event.target.value)}
              disabled={
                (messageType === 'BROADCAST' && broadcastTemplatesQuery.isLoading) ||
                (messageType === 'ANNOUNCEMENT' && announcementTemplatesQuery.isLoading) ||
                availableTemplates.length === 0
              }
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

          <button
            type="submit"
            className="rounded bg-primary-600 px-4 py-2 text-white hover:bg-primary-500 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={messageType === 'BROADCAST' && broadcastSegments.length === 0}
          >
            {messageType === 'BROADCAST' ? 'Record Broadcast' : 'Send Announcement'}
          </button>
        </form>
      </section>

      <section className="rounded border border-slate-200 p-4">
        <h3 className="mb-3 text-lg font-semibold text-slate-700">Communication History</h3>
        {messagesQuery.isError && (
          <p className="mb-3 text-sm text-red-600">Unable to load communication history.</p>
        )}
        {messages.length === 0 ? (
          <p className="text-sm text-slate-500">
            {messagesQuery.isLoading ? 'Loading history…' : 'No communications have been recorded yet.'}
          </p>
        ) : (
          <ul className="space-y-3 text-sm">
            {messages.map((message) => {
              const isBroadcast = message.message_type === 'BROADCAST';
              const deliveryLabel =
                message.delivery_methods.length > 0 ? message.delivery_methods.join(', ') : '—';
              return (
                <li key={message.id} className="rounded border border-slate-200 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h4 className="font-semibold text-slate-700">{message.subject}</h4>
                      <p className="text-xs uppercase text-slate-400">
                        {isBroadcast
                          ? `Segment: ${resolveSegmentLabel(message.segment ?? '')} • Recipients stored: ${
                              message.recipient_count
                            }`
                          : `Delivery: ${deliveryLabel} • Recipients stored: ${message.recipient_count}`}
                      </p>
                    </div>
                    <span className="text-xs text-slate-500">
                      {new Date(message.created_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="mt-2 whitespace-pre-wrap text-slate-600">{message.body}</p>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                    <span className="rounded bg-slate-100 px-2 py-1 uppercase">
                      {isBroadcast ? 'Email broadcast' : 'Announcement'}
                    </span>
                    {!isBroadcast && message.pdf_path && (
                      <span className="text-primary-600">PDF generated: {message.pdf_path}</span>
                    )}
                  </div>
                  {isBroadcast && message.recipients.length > 0 && (
                    <details className="mt-3">
                      <summary className="cursor-pointer text-xs font-semibold text-primary-600">
                        View recipient snapshot ({message.recipient_count})
                      </summary>
                      <ul className="mt-2 grid gap-2 text-xs md:grid-cols-2">
                        {message.recipients.map((recipient) => (
                          <li
                            key={`${recipient.email}-${recipient.owner_id ?? 'none'}-${
                              recipient.contact_type ?? 'contact'
                            }`}
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
                    </details>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
};

export default CommunicationsPage;
