import React from 'react';

export interface TimelineEvent {
  timestamp: string;
  label: string;
  description?: string;
  meta?: string;
}

interface TimelineProps {
  events: TimelineEvent[];
  emptyMessage?: string;
}

const Timeline: React.FC<TimelineProps> = ({ events, emptyMessage = 'No activity recorded yet.' }) => {
  if (!events.length) {
    return <p className="text-xs text-slate-500">{emptyMessage}</p>;
  }

  return (
    <ol className="relative border-l border-slate-200 pl-4">
      {events.map((event, index) => {
        const displayDate = event.timestamp ? new Date(event.timestamp).toLocaleString() : 'Unknown time';
        return (
          <li key={`${event.label}-${event.timestamp}-${index}`} className="mb-6 ml-2">
            <span className="absolute -left-[9px] flex h-4 w-4 items-center justify-center rounded-full border border-white bg-primary-500" />
            <p className="text-xs font-semibold uppercase text-slate-500">{displayDate}</p>
            <h4 className="text-sm font-semibold text-slate-700">{event.label}</h4>
            {event.meta && <p className="text-xs text-slate-500">{event.meta}</p>}
            {event.description && <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">{event.description}</p>}
          </li>
        );
      })}
    </ol>
  );
};

export default Timeline;
