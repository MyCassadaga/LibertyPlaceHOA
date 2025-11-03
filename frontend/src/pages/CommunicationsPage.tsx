import React, { useEffect, useMemo, useState } from 'react';

import {
  createAnnouncement,
  createEmailBroadcast,
  fetchAnnouncements,
  fetchBroadcastSegments,
  fetchEmailBroadcasts,
} from '../services/api';
import { Announcement, EmailBroadcast, EmailBroadcastSegment } from '../types';

const CommunicationsPage: React.FC = () => {
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [announcementSubject, setAnnouncementSubject] = useState('');
  const [announcementMessage, setAnnouncementMessage] = useState('');
  const [deliveryEmail, setDeliveryEmail] = useState(true);
  const [deliveryPrint, setDeliveryPrint] = useState(false);
  const [announcementStatus, setAnnouncementStatus] = useState<string | null>(null);
  const [announcementError, setAnnouncementError] = useState<string | null>(null);

  const [broadcasts, setBroadcasts] = useState<EmailBroadcast[]>([]);
  const [broadcastSegments, setBroadcastSegments] = useState<EmailBroadcastSegment[]>([]);
  const [selectedSegment, setSelectedSegment] = useState('');
  const [broadcastSubject, setBroadcastSubject] = useState('');
  const [broadcastBody, setBroadcastBody] = useState('');
  const [broadcastStatus, setBroadcastStatus] = useState<string | null>(null);
  const [broadcastFormError, setBroadcastFormError] = useState<string | null>(null);
  const [broadcastSegmentsError, setBroadcastSegmentsError] = useState<string | null>(null);
  const [broadcastHistoryError, setBroadcastHistoryError] = useState<string | null>(null);

  const loadAnnouncements = async () => {
    const data = await fetchAnnouncements();
    setAnnouncements(data);
  };

  const loadBroadcastSegments = async () => {
    try {
      const data = await fetchBroadcastSegments();
      setBroadcastSegments(data);
      if (!selectedSegment || !data.some((segment) => segment.key === selectedSegment)) {
        setSelectedSegment(data[0]?.key ?? '');
      }
      setBroadcastSegmentsError(null);
    } catch (err) {
      setBroadcastSegmentsError('Unable to load broadcast segments.');
    }
  };

  const loadBroadcasts = async () => {
    try {
      const data = await fetchEmailBroadcasts();
      setBroadcasts(data);
      setBroadcastHistoryError(null);
    } catch (err) {
      setBroadcastHistoryError('Unable to load recorded broadcasts.');
    }
  };

  useEffect(() => {
    void loadAnnouncements();
    void loadBroadcastSegments();
    void loadBroadcasts();
  }, []);

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
      await loadAnnouncements();
    } catch (err) {
      setAnnouncementStatus(null);
      setAnnouncementError('Unable to create announcement.');
    }
  };

  const handleBroadcastSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBroadcastStatus(null);
    setBroadcastFormError(null);
    if (!selectedSegment) {
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
        segment: selectedSegment,
      });
      setBroadcastSubject('');
      setBroadcastBody('');
      setBroadcastStatus('Broadcast recorded for compliance.');
      setBroadcastFormError(null);
      await Promise.all([loadBroadcasts(), loadBroadcastSegments()]);
    } catch (err) {
      setBroadcastStatus(null);
      setBroadcastFormError('Unable to record the broadcast.');
    }
  };

  const selectedSegmentDetails = useMemo(
    () => broadcastSegments.find((segment) => segment.key === selectedSegment),
    [broadcastSegments, selectedSegment],
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
              value={selectedSegment}
              onChange={(event) => setSelectedSegment(event.target.value)}
              disabled={broadcastSegments.length === 0}
            >
              {broadcastSegments.length === 0 && <option value="">Loading segments...</option>}
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
            {broadcastSegmentsError && (
              <p className="mt-2 text-xs text-red-600">{broadcastSegmentsError}</p>
            )}
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
        {broadcastHistoryError && broadcasts.length > 0 && (
          <p className="mb-3 text-sm text-red-600">{broadcastHistoryError}</p>
        )}
        {broadcasts.length === 0 ? (
          <p className="text-sm text-slate-500">
            {broadcastHistoryError ?? 'No outbound email broadcasts have been recorded.'}
          </p>
        ) : (
          <ul className="space-y-3 text-sm">
            {broadcasts.map((broadcast) => (
              <li key={broadcast.id} className="rounded border border-slate-200 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h4 className="font-semibold text-slate-700">{broadcast.subject}</h4>
                    <p className="text-xs uppercase text-slate-400">
                      Segment: {resolveSegmentLabel(broadcast.segment)} • Recipients stored:{' '}
                      {broadcast.recipient_count}
                    </p>
                  </div>
                  <span className="text-xs text-slate-500">
                    {new Date(broadcast.created_at).toLocaleString()}
                  </span>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-slate-600">{broadcast.body}</p>
                <details className="mt-3">
                  <summary className="cursor-pointer text-xs font-semibold text-primary-600">
                    View recipient snapshot ({broadcast.recipient_count})
                  </summary>
                  <ul className="mt-2 grid gap-2 text-xs md:grid-cols-2">
                    {broadcast.recipients.map((recipient) => (
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
            <p className="text-sm text-slate-500">No announcements yet.</p>
          ) : (
            <ul className="space-y-3 text-sm">
              {announcements.map((announcement) => (
                <li key={announcement.id} className="rounded border border-slate-200 p-3">
                  <div className="flex items-center justify-between">
                    <h5 className="font-semibold text-slate-700">{announcement.subject}</h5>
                    <span className="text-xs text-slate-500">
                      {new Date(announcement.created_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="mt-2 whitespace-pre-wrap text-slate-600">{announcement.body}</p>
                  <p className="mt-2 text-xs uppercase text-slate-400">
                    Delivery: {announcement.delivery_methods.join(', ')}
                    {announcement.pdf_path && (
                      <span className="ml-2 text-primary-600">PDF generated: {announcement.pdf_path}</span>
                    )}
                  </p>
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
