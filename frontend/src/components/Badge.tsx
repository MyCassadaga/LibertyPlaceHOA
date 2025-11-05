import React from 'react';

type BadgeTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger';

const TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: 'bg-slate-200 text-slate-700',
  info: 'bg-blue-100 text-blue-700',
  success: 'bg-emerald-100 text-emerald-700',
  warning: 'bg-amber-100 text-amber-700',
  danger: 'bg-rose-100 text-rose-700',
};

interface BadgeProps {
  children: React.ReactNode;
  tone?: BadgeTone;
  className?: string;
}

const Badge: React.FC<BadgeProps> = ({ children, tone = 'neutral', className }) => {
  const toneClasses = TONE_CLASSES[tone] ?? TONE_CLASSES.neutral;
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${toneClasses} ${className ?? ''}`}>
      {children}
    </span>
  );
};

export default Badge;
