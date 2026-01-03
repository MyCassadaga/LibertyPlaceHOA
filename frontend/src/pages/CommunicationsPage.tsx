import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import {
  createAnnouncement,
  createEmailBroadcast,
  fetchAnnouncements,
  fetchBroadcastSegments,
  fetchEmailBroadcasts,
  fetchTemplateMergeTags,
  fetchTemplates,
} from '../services/api';
import { Announcement, EmailBroadcast, EmailBroadcastSegment, Template } from '../types';
import { queryKeys } from '../lib/api/queryKeys';
import { renderMergeTags } from '../utils/mergeTags';

const CommunicationsPage: React.FC = () => {
  const [announcementSubject, setAnnouncementSubject] = useState('');
  const [announcementMessage, setAnnouncementMessage] = useState('');
  const [deliveryEmail, setDeliveryEmail] = useState(true);
  const [deliveryPrint, setDeliveryPrint] = useState(false);
  const [announcementStatus, setAnnouncementStatus] = useState<string | null>(null);
  const [announcementError, setAnnouncementError] = useState<string | null>(null);
  const [announcementTemplateId, setAnnouncementTemplateId] = useState('');

  const [selectedSegment, setSelectedSegment] = useState('');
  const [broadcastSubject, setBroadcastSubject] = useState('');
  const [broadcastBody, setBroadcastBody] = useState('');
  const [broadcastStatus, setBroadcastStatus] = useState<string | null>(null);
  const [broadcastFormError, setBroadcastFormError] = useState<string | null>(null);
  const [broadcastTemplateId, setBroadcastTemplateId] = useState('');
  const announcementsQuery = useQuery<Announcement[]>({
    queryKey: queryKeys.announcements,
    queryFn: fetchAnnouncements,
  });

  const broadcastsQuery = useQuery<EmailBroadcast[]>({
    queryKey: queryKeys.broadcasts,
    queryFn: fetchEmailBroadcasts,
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

  const announcements = announcementsQuery.data ?? [];
  const broadcasts = broadcastsQuery.data ?? [];
  const announcementTemplates = announcementTemplatesQuery.data ?? [];
  const broadcastTemplates = broadcastTemplatesQuery.data ?? [];
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

  const handleAnnouncementSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      const deliveryMethods = [] as string[];
      if (deliveryEmail) deliveryMethods.push('email');
      if (deliveryPrint) deliveryMethods.push('print');
      if (deliveryMethods.length === 0) {
        setAnnouncementError('Select at least one delivery method.');
        return;
      }
      await createAnnouncement({
        subject: announcementSubject,
        body: announcementMessage,
        delivery_methods: deliveryMethods,
      });
      setAnnouncementSubject('');
      setAnnouncementMessage('');
      setDeliveryEmail(true);
      setDeliveryPrint(false);
      setAnnouncementError(null);
      setAnnouncementStatus('Announcement queued successfully.');
      setAnnouncementTemplateId('');
      await announcementsQuery.refetch();
    } catch (err) {
      console.error('Unable to create announcement', err);
      setAnnouncementStatus(null);
      setAnnouncementError('Unable to create announcement.');
    }
  };

  const handleBroadcastSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBroadcastStatus(null);
    setBroadcastFormError(null);
    if (!resolvedSegment) {
      setBroadcastFormError('Choose at least one recipient segment.');
      return;
    }
    if (!broadcastSubject.trim() || !broadcastBody.trim()) {
      setBroadcastFormError('Subject and message are both required.');
      return;
    }

    try {
      await createEmailBroadcast({
        subject: broadcastSubject,
        body: broadcastBody,
        segment: resolvedSegment,
      });
      setBroadcastSubject('');
      setBroadcastBody('');
      setBroadcastStatus('Broadcast recorded for compliance.');
      setBroadcastFormError(null);
      setBroadcastTemplateId('');
      await Promise.all([broadcastsQuery.refetch(), segmentsQuery.refetch()]);
    } catch (err) {
      console.error('Unable to record broadcast', err);
      setBroadcastStatus(null);
      setBroadcastFormError('Unable to record the broadcast.');
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

  const handleAnnouncementTemplateChange = (templateId: string) => {
    setAnnouncementTemplateId(templateId);
    const template = announcementTemplates.find((item) => item.id === Number(templateId));
    if (template) {
      setAnnouncementSubject(template.subject);
      setAnnouncementMessage(template.body);
    }
  };

  const handleBroadcastTemplateChange = (templateId: string) => {
    setBroadcastTemplateId(templateId);
    const template = broadcastTemplates.find((item) => item.id === Number(templateId));
    if (template) {
      setBroadcastSubject(template.subject);
      setBroadcastBody(template.body);
    }
  };

  const announcementPreview = renderMergeTags(announcementMessage, mergeTags);
  const announcementSubjectPreview = renderMergeTags(announcementSubject, mergeTags);
  const broadcastPreview = renderMergeTags(broadcastBody, mergeTags);
  const broadcastSubjectPreview = renderMergeTags(broadcastSubject, mergeTags);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-slate-700">Community Communications</h2>

      <section className="rounded border border-slate-200 p-4">
        <h3 className="mb-3 text-lg font-semibold text-slate-700">Record Email Broadcast</h3>
        <form className="space-y-4" onSubmit={handleBroadcastSubmit}>
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

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="broadcast-template">
              Template (optional)
            </label>
            <select
              id="broadcast-template"
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              value={broadcastTemplateId}
              onChange={(event) => handleBroadcastTemplateChange(event.target.value)}
              disabled={broadcastTemplatesQuery.isLoading || broadcastTemplates.length === 0}
            >
              <option value="">No template</option>
              {broadcastTemplates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="broadcast-subject">
              Subject
            </label>
            <input
              id="broadcast-subject"
              className="w-full rounded border border-slate-300 px-3 py-2"
              value={broadcastSubject}
              onChange={(event) => setBroadcastSubject(event.target.value)}
              required
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="broadcast-body">
              Message
            </label>
            <textarea
              id="broadcast-body"
              rows={5}
              className="w-full rounded border border-slate-300 px-3 py-2"
              value={broadcastBody}
              onChange={(event) => setBroadcastBody(event.target.value)}
              required
            />
            <p className="mt-2 text-xs text-slate-500">
              Preview: <span className="font-medium text-slate-600">{broadcastSubjectPreview || '—'}</span>
            </p>
            <p className="mt-1 whitespace-pre-wrap text-xs text-slate-500">{broadcastPreview || '—'}</p>
          </div>

          {broadcastStatus && <p className="text-sm text-green-600">{broadcastStatus}</p>}
          {broadcastFormError && <p className="text-sm text-red-600">{broadcastFormError}</p>}

          <button
            type="submit"
            className="rounded bg-primary-600 px-4 py-2 text-white hover:bg-primary-500 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={broadcastSegments.length === 0}
          >
            Record Broadcast
          </button>
        </form>
      </section>

      <section className="rounded border border-slate-200 p-4">
        <h3 className="mb-3 text-lg font-semibold text-slate-700">Broadcast History</h3>
        {broadcastsQuery.isError && (
          <p className="mb-3 text-sm text-red-600">Unable to load recorded broadcasts.</p>
        )}
        {broadcasts.length === 0 ? (
          <p className="text-sm text-slate-500">
            {broadcastsQuery.isLoading ? 'Loading history…' : 'No outbound email broadcasts have been recorded.'}
          </p>
        ) : (
          <ul className="space-y-3 text-sm">
            {broadcasts.map((broadcast) => (
              <li key={broadcast.id} className="rounded border border-slate-200">
                <details className="group">
                  <summary className="flex cursor-pointer list-none items-start justify-between gap-4 rounded px-3 py-3 hover:bg-slate-50">
                    <div className="grid w-full gap-2 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto] sm:items-center">
                      <div className="min-w-0">
                        <p className="text-xs uppercase text-slate-400">Email broadcast</p>
                        <h4 className="truncate font-semibold text-slate-700">{broadcast.subject}</h4>
                      </div>
                      <div>
                        <p className="text-xs text-slate-400">Delivery method</p>
                        <p className="font-medium text-slate-600">Email</p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-slate-400">Sent</p>
                        <p className="font-medium text-slate-600">
                          {new Date(broadcast.created_at).toLocaleString()}
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
                        <p className="text-slate-400">Segment</p>
                        <p className="font-semibold text-slate-700">
                          {resolveSegmentLabel(broadcast.segment)}
                        </p>
                      </div>
                      <div>
                        <p className="text-slate-400">Recipients stored</p>
                        <p className="font-semibold text-slate-700">{broadcast.recipient_count}</p>
                      </div>
                      <div>
                        <p className="text-slate-400">Printable</p>
                        <p className="font-semibold text-slate-700">Not available</p>
                      </div>
                    </div>
                    <p className="mt-3 whitespace-pre-wrap text-sm text-slate-600">{broadcast.body}</p>
                    <div className="mt-4">
                      <p className="text-xs font-semibold text-primary-600">
                        Recipient snapshot ({broadcast.recipient_count})
                      </p>
                      <ul className="mt-2 grid gap-2 text-xs md:grid-cols-2">
                        {(broadcast.recipients ?? []).map((recipient) => (
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

      <section className="rounded border border-slate-200 p-4">
        <h3 className="mb-3 text-lg font-semibold text-slate-700">Community Announcements</h3>
        <form onSubmit={handleAnnouncementSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="announcement-template">
              Template (optional)
            </label>
            <select
              id="announcement-template"
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              value={announcementTemplateId}
              onChange={(event) => handleAnnouncementTemplateChange(event.target.value)}
              disabled={announcementTemplatesQuery.isLoading || announcementTemplates.length === 0}
            >
              <option value="">No template</option>
              {announcementTemplates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="announcement-subject">
              Subject
            </label>
            <input
              id="announcement-subject"
              className="w-full rounded border border-slate-300 px-3 py-2"
              value={announcementSubject}
              onChange={(event) => setAnnouncementSubject(event.target.value)}
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="announcement-message">
              Message
            </label>
            <textarea
              id="announcement-message"
              rows={4}
              className="w-full rounded border border-slate-300 px-3 py-2"
              value={announcementMessage}
              onChange={(event) => setAnnouncementMessage(event.target.value)}
              required
            />
            <p className="mt-2 text-xs text-slate-500">
              Preview: <span className="font-medium text-slate-600">{announcementSubjectPreview || '—'}</span>
            </p>
            <p className="mt-1 whitespace-pre-wrap text-xs text-slate-500">{announcementPreview || '—'}</p>
          </div>
          <fieldset className="flex gap-4 text-sm">
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
          {announcementStatus && <p className="text-sm text-green-600">{announcementStatus}</p>}
          {announcementError && <p className="text-sm text-red-600">{announcementError}</p>}
          <button
            type="submit"
            className="rounded bg-primary-600 px-4 py-2 text-white hover:bg-primary-500"
          >
            Send Announcement
          </button>
        </form>

        <div className="mt-6">
          <h4 className="mb-2 text-base font-semibold text-slate-700">Recent Announcements</h4>
          {announcements.length === 0 ? (
            <p className="text-sm text-slate-500">
              {announcementsQuery.isLoading ? 'Loading announcements…' : 'No announcements yet.'}
            </p>
          ) : (
            <ul className="space-y-3 text-sm">
              {announcements.map((announcement) => (
                <li key={announcement.id} className="rounded border border-slate-200">
                  <details className="group">
                    <summary className="flex cursor-pointer list-none items-start justify-between gap-4 rounded px-3 py-3 hover:bg-slate-50">
                      <div className="grid w-full gap-2 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto] sm:items-center">
                        <div className="min-w-0">
                          <p className="text-xs uppercase text-slate-400">Announcement</p>
                          <h5 className="truncate font-semibold text-slate-700">
                            {announcement.subject}
                          </h5>
                        </div>
                        <div>
                          <p className="text-xs text-slate-400">Delivery method</p>
                          <p className="font-medium text-slate-600">
                            {announcement.delivery_methods.join(', ')}
                          </p>
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
                          <p className="text-slate-400">Delivery methods</p>
                          <p className="font-semibold text-slate-700">
                            {announcement.delivery_methods.join(', ')}
                          </p>
                        </div>
                        <div>
                          <p className="text-slate-400">Printable packet</p>
                          <p className="font-semibold text-slate-700">
                            {announcement.pdf_path ? 'Available' : 'Not available'}
                          </p>
                        </div>
                        <div>
                          <p className="text-slate-400">Printable link</p>
                          {announcement.pdf_path ? (
                            <a
                              className="font-semibold text-primary-600 hover:text-primary-500"
                              href={announcement.pdf_path}
                              target="_blank"
                              rel="noreferrer"
                            >
                              View PDF
                            </a>
                          ) : (
                            <p className="font-semibold text-slate-700">—</p>
                          )}
                        </div>
                      </div>
                      <p className="mt-3 whitespace-pre-wrap text-sm text-slate-600">
                        {announcement.body}
                      </p>
                    </div>
                  </details>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
};

export default CommunicationsPage;
