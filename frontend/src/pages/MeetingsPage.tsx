import React, { useCallback, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import { getMeetingMinutesDownloadUrl } from '../services/api';
import { Meeting } from '../types';
import { userHasAnyRole } from '../utils/roles';
import {
  useCreateMeetingMutation,
  useDeleteMeetingMutation,
  useMeetingsQuery,
  useUpdateMeetingMutation,
  useUploadMinutesMutation,
} from '../features/meetings/hooks';

const MANAGER_ROLES = ['BOARD', 'SYSADMIN', 'SECRETARY', 'TREASURER'];

const MeetingsPage: React.FC = () => {
  const { user } = useAuth();
  const canManage = userHasAnyRole(user, MANAGER_ROLES);
  const [error, setError] = useState<string | null>(null);
  const meetingsQuery = useMeetingsQuery(true);
  const meetings = useMemo(() => meetingsQuery.data ?? [], [meetingsQuery.data]);
  const loading = meetingsQuery.isLoading;
  const meetingsError = meetingsQuery.isError ? 'Unable to load meetings.' : null;
  const createMeetingMutation = useCreateMeetingMutation();
  const deleteMeetingMutation = useDeleteMeetingMutation();
  const uploadMinutesMutation = useUploadMinutesMutation();
  const updateMeetingMutation = useUpdateMeetingMutation();
  const [calendarMonth, setCalendarMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [form, setForm] = useState({
    title: '',
    start_time: '',
    end_time: '',
    location: '',
    zoom_link: '',
    description: '',
  });

  const logError = useCallback((message: string, err: unknown) => {
    console.error(message, err);
  }, []);

  const combinedError = error ?? meetingsError;
  const upcomingMeetings = useMemo(
    () => meetings.filter((meeting) => new Date(meeting.start_time) >= new Date()),
    [meetings],
  );
  const pastMeetings = useMemo(
    () =>
      meetings
        .filter((meeting) => new Date(meeting.start_time) < new Date())
        .sort((a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime()),
    [meetings],
  );

  const monthMeetings = useMemo(() => {
    const start = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), 1);
    const end = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 0);
    return meetings.filter((meeting) => {
      const date = new Date(meeting.start_time);
      return date >= start && date <= end;
    });
  }, [meetings, calendarMonth]);

  const calendarDays = useMemo(() => buildCalendar(calendarMonth), [calendarMonth]);

  const handleCreateMeeting = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.title || !form.start_time) {
      setError('Title and start time are required.');
      return;
    }
    setError(null);
    try {
      await createMeetingMutation.mutateAsync({
        title: form.title,
        start_time: new Date(form.start_time).toISOString(),
        end_time: form.end_time ? new Date(form.end_time).toISOString() : undefined,
        location: form.location || undefined,
        zoom_link: form.zoom_link || undefined,
        description: form.description || undefined,
      });
      setForm({ title: '', start_time: '', end_time: '', location: '', zoom_link: '', description: '' });
    } catch (err) {
      logError('Unable to schedule meeting.', err);
      setError('Unable to schedule meeting.');
    }
  };

  const handleDeleteMeeting = async (meetingId: number) => {
    if (!window.confirm('Delete this meeting?')) return;
    try {
      setError(null);
      await deleteMeetingMutation.mutateAsync(meetingId);
    } catch (err) {
      logError('Unable to delete meeting.', err);
      setError('Unable to delete meeting.');
    }
  };

  const handleUploadMinutes = async (meetingId: number, file: File | null) => {
    if (!file) {
      setError('Select a transcript to upload.');
      return;
    }
    try {
      setError(null);
      await uploadMinutesMutation.mutateAsync({ meetingId, file });
    } catch (err) {
      logError('Unable to upload minutes.', err);
      setError('Unable to upload minutes.');
    }
  };

  const handleUpdateMeeting = async (
    meetingId: number,
    updates: Partial<{ title: string; zoom_link: string | null; location: string | null }>,
  ) => {
    try {
      setError(null);
      await updateMeetingMutation.mutateAsync({ meetingId, payload: updates });
    } catch (err) {
      logError('Unable to update meeting.', err);
      setError('Unable to update meeting.');
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-primary-600">Meetings & Calendar</h2>
          <p className="text-sm text-slate-500">Stay informed about board sessions, Zoom links, and posted minutes.</p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <button
            type="button"
            className="rounded border border-slate-300 px-3 py-1 text-slate-600"
            onClick={() =>
              setCalendarMonth(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() - 1, 1))
            }
          >
            Prev
          </button>
          <span className="font-semibold text-slate-600">
            {calendarMonth.toLocaleString('default', { month: 'long', year: 'numeric' })}
          </span>
          <button
            type="button"
            className="rounded border border-slate-300 px-3 py-1 text-slate-600"
            onClick={() =>
              setCalendarMonth(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 1))
            }
          >
            Next
          </button>
        </div>
      </header>

      {combinedError && <p className="text-sm text-red-600">{combinedError}</p>}
      {loading && <p className="text-sm text-slate-500">Loading meetings…</p>}

      <section className="rounded border border-slate-200 p-4">
        <CalendarGrid days={calendarDays} meetings={monthMeetings} />
      </section>

      {canManage && (
        <section className="rounded border border-slate-200 p-4">
          <h3 className="mb-2 text-lg font-semibold text-slate-700">Schedule a meeting</h3>
          <form className="grid gap-3 md:grid-cols-2" onSubmit={handleCreateMeeting}>
            <label className="text-sm">
              <span className="text-xs text-slate-500">Title</span>
              <input
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={form.title}
                onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
                required
              />
            </label>
            <label className="text-sm">
              <span className="text-xs text-slate-500">Zoom link</span>
              <input
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={form.zoom_link}
                onChange={(event) => setForm((prev) => ({ ...prev, zoom_link: event.target.value }))}
              />
            </label>
            <label className="text-sm">
              <span className="text-xs text-slate-500">Starts</span>
              <input
                type="datetime-local"
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={form.start_time}
                onChange={(event) => setForm((prev) => ({ ...prev, start_time: event.target.value }))}
                required
              />
            </label>
            <label className="text-sm">
              <span className="text-xs text-slate-500">Ends</span>
              <input
                type="datetime-local"
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={form.end_time}
                onChange={(event) => setForm((prev) => ({ ...prev, end_time: event.target.value }))}
              />
            </label>
            <label className="text-sm">
              <span className="text-xs text-slate-500">Location</span>
              <input
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                value={form.location}
                onChange={(event) => setForm((prev) => ({ ...prev, location: event.target.value }))}
              />
            </label>
            <label className="text-sm md:col-span-2">
              <span className="text-xs text-slate-500">Description</span>
              <textarea
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
                rows={2}
                value={form.description}
                onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
              />
            </label>
            <div className="md:col-span-2">
              <button
                type="submit"
                className="rounded bg-primary-600 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white"
              >
                Save meeting
              </button>
            </div>
          </form>
        </section>
      )}

      <section className="rounded border border-slate-200 p-4">
        <h3 className="text-lg font-semibold text-slate-700">Upcoming meetings</h3>
        <div className="mt-3 space-y-4">
          {upcomingMeetings.length === 0 && (
            <p className="text-sm text-slate-500">No meetings scheduled yet.</p>
          )}
          {upcomingMeetings.map((meeting) => (
            <MeetingCard
              key={meeting.id}
              meeting={meeting}
              canManage={canManage}
              onDelete={handleDeleteMeeting}
              onUploadMinutes={handleUploadMinutes}
              onUpdate={(updates) => handleUpdateMeeting(meeting.id, updates)}
            />
          ))}
        </div>
      </section>

      <section className="rounded border border-slate-200 p-4">
          <h3 className="text-lg font-semibold text-slate-700">Previous meetings & minutes</h3>
          <div className="mt-3 space-y-3">
            {pastMeetings.length === 0 && (
              <p className="text-sm text-slate-500">No historical meetings yet.</p>
            )}
            {pastMeetings.slice(0, 6).map((meeting) => (
              <div key={meeting.id} className="rounded border border-slate-100 p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-slate-700">{meeting.title}</p>
                    <p className="text-xs text-slate-500">
                      {new Date(meeting.start_time).toLocaleString()}
                      {meeting.location ? ` • ${meeting.location}` : ''}
                    </p>
                  </div>
                  {meeting.minutes_available ? (
                    <a
                      className="rounded border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50"
                      href={getMeetingMinutesDownloadUrl(meeting.id)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      View minutes
                    </a>
                  ) : (
                    canManage && (
                      <label className="text-xs text-slate-500">
                        Upload transcript
                        <input
                          type="file"
                          className="block text-xs"
                          onChange={(event) => handleUploadMinutes(meeting.id, event.target.files?.[0] ?? null)}
                        />
                      </label>
                    )
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
    </div>
  );
};

type MeetingCardProps = {
  meeting: Meeting;
  canManage: boolean;
  onDelete: (id: number) => void;
  onUploadMinutes: (id: number, file: File | null) => void;
  onUpdate: (updates: Partial<{ title: string; zoom_link: string | null; location: string | null }>) => Promise<void>;
};

const MeetingCard: React.FC<MeetingCardProps> = ({ meeting, canManage, onDelete, onUploadMinutes, onUpdate }) => {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({
    title: meeting.title,
    zoom_link: meeting.zoom_link ?? '',
    location: meeting.location ?? '',
  });

  const handleSave = async () => {
    await onUpdate({
      title: draft.title,
      zoom_link: draft.zoom_link || null,
      location: draft.location || null,
    });
    setEditing(false);
  };

  return (
    <div className="rounded border border-slate-200 p-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          {editing ? (
            <input
              className="rounded border border-slate-300 px-2 py-1 text-sm"
              value={draft.title}
              onChange={(event) => setDraft((prev) => ({ ...prev, title: event.target.value }))}
            />
          ) : (
            <p className="text-base font-semibold text-slate-700">{meeting.title}</p>
          )}
          <p className="text-xs text-slate-500">
            {new Date(meeting.start_time).toLocaleString()}
            {meeting.location ? ` • ${meeting.location}` : ''}
          </p>
        </div>
        {canManage && (
          <div className="flex gap-2 text-xs">
            {editing ? (
              <>
                <button
                  type="button"
                  className="rounded border border-slate-300 px-3 py-1 text-slate-600"
                  onClick={handleSave}
                >
                  Save
                </button>
                <button
                  type="button"
                  className="rounded border border-slate-300 px-3 py-1 text-slate-600"
                  onClick={() => setEditing(false)}
                >
                  Cancel
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  className="rounded border border-slate-300 px-3 py-1 text-slate-600"
                  onClick={() => setEditing(true)}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="rounded border border-rose-200 px-3 py-1 text-rose-600"
                  onClick={() => onDelete(meeting.id)}
                >
                  Delete
                </button>
              </>
            )}
          </div>
        )}
      </div>
      <div className="mt-3 space-y-2">
        {editing ? (
          <>
            <input
              className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
              placeholder="Zoom link"
              value={draft.zoom_link}
              onChange={(event) => setDraft((prev) => ({ ...prev, zoom_link: event.target.value }))}
            />
            <input
              className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
              placeholder="Location"
              value={draft.location}
              onChange={(event) => setDraft((prev) => ({ ...prev, location: event.target.value }))}
            />
          </>
        ) : (
          <>
            {meeting.zoom_link && (
              <a
                href={meeting.zoom_link}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center rounded border border-blue-200 px-3 py-1 text-xs font-semibold text-blue-600"
              >
                Join Zoom
              </a>
            )}
            {meeting.minutes_available && meeting.minutes_download_url && (
              <a
                href={getMeetingMinutesDownloadUrl(meeting.id)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center rounded border border-slate-300 px-3 py-1 text-xs text-slate-600"
              >
                Minutes
              </a>
            )}
            {canManage && (
              <label className="block text-xs text-slate-500">
                Upload minutes/transcript
                <input
                  type="file"
                  className="mt-1 text-xs"
                  onChange={(event) => onUploadMinutes(meeting.id, event.target.files?.[0] ?? null)}
                />
              </label>
            )}
          </>
        )}
        {meeting.description && <p className="text-xs text-slate-500">{meeting.description}</p>}
      </div>
    </div>
  );
};

type CalendarGridProps = {
  days: Date[];
  meetings: Meeting[];
};

const CalendarGrid: React.FC<CalendarGridProps> = ({ days, meetings }) => {
  return (
    <div className="grid grid-cols-7 gap-2 text-sm">
      {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((label) => (
        <div key={label} className="text-center text-xs font-semibold uppercase text-slate-500">
          {label}
        </div>
      ))}
      {days.map((day) => {
        const dayMeetings = meetings.filter(
          (meeting) => new Date(meeting.start_time).toDateString() === day.toDateString(),
        );
        const isCurrentMonth = day.getMonth() === new Date(day).getMonth();
        return (
          <div
            key={day.toISOString()}
            className={`min-h-[90px] rounded border border-slate-200 p-2 ${
              isCurrentMonth ? 'bg-white' : 'bg-slate-50 text-slate-400'
            }`}
          >
            <p className="text-xs font-semibold">{day.getDate()}</p>
            <div className="mt-1 space-y-1">
              {dayMeetings.map((meeting) => (
                <p key={meeting.id} className="rounded bg-primary-50 px-1 py-0.5 text-[11px] text-primary-700">
                  {new Date(meeting.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} •{' '}
                  {meeting.title}
                </p>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};

function buildCalendar(monthStart: Date): Date[] {
  const days: Date[] = [];
  const start = new Date(monthStart.getFullYear(), monthStart.getMonth(), 1);
  const end = new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 0);
  const startDay = start.getDay();
  for (let i = startDay; i > 0; i -= 1) {
    days.push(new Date(start.getFullYear(), start.getMonth(), 1 - i));
  }
  for (let date = 1; date <= end.getDate(); date += 1) {
    days.push(new Date(start.getFullYear(), start.getMonth(), date));
  }
  while (days.length % 7 !== 0) {
    const last = days[days.length - 1];
    days.push(new Date(last.getFullYear(), last.getMonth(), last.getDate() + 1));
  }
  return days;
}

export default MeetingsPage;
