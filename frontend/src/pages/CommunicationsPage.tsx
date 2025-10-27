import React, { useEffect, useState } from 'react';

import { createAnnouncement, fetchAnnouncements } from '../services/api';
import { Announcement } from '../types';

const CommunicationsPage: React.FC = () => {
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [deliveryEmail, setDeliveryEmail] = useState(true);
  const [deliveryPrint, setDeliveryPrint] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadAnnouncements = async () => {
    const data = await fetchAnnouncements();
    setAnnouncements(data);
  };

  useEffect(() => {
    loadAnnouncements();
  }, []);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      const deliveryMethods = [] as string[];
      if (deliveryEmail) deliveryMethods.push('email');
      if (deliveryPrint) deliveryMethods.push('print');
      if (deliveryMethods.length === 0) {
        setError('Select at least one delivery method.');
        return;
      }
      await createAnnouncement({
        subject,
        body: message,
        delivery_methods: deliveryMethods,
      });
      setSubject('');
      setMessage('');
      setDeliveryEmail(true);
      setDeliveryPrint(false);
      setError(null);
      setStatus('Announcement queued successfully.');
      await loadAnnouncements();
    } catch (err) {
      setStatus(null);
      setError('Unable to create announcement.');
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-slate-700">Community Communications</h2>
      <form onSubmit={handleSubmit} className="space-y-4 rounded border border-slate-200 p-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="subject">
            Subject
          </label>
          <input
            id="subject"
            className="w-full rounded border border-slate-300 px-3 py-2"
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            required
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="message">
            Message
          </label>
          <textarea
            id="message"
            rows={4}
            className="w-full rounded border border-slate-300 px-3 py-2"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
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
        {status && <p className="text-sm text-green-600">{status}</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          className="rounded bg-primary-600 px-4 py-2 text-white hover:bg-primary-500"
        >
          Send Announcement
        </button>
      </form>

      <section className="rounded border border-slate-200 p-4">
        <h3 className="mb-3 text-lg font-semibold text-slate-700">Recent Announcements</h3>
        {announcements.length === 0 ? (
          <p className="text-sm text-slate-500">No announcements yet.</p>
        ) : (
          <ul className="space-y-3 text-sm">
            {announcements.map((announcement) => (
              <li key={announcement.id} className="rounded border border-slate-200 p-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold text-slate-700">{announcement.subject}</h4>
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
      </section>
    </div>
  );
};

export default CommunicationsPage;
