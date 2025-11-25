import React from 'react';
import clsx from 'clsx';

type Props = {
  label?: string;
  className?: string;
};

const FullPageSpinner: React.FC<Props> = ({ label = 'Loading…', className }) => (
  <div
    className={clsx(
      'flex h-full w-full flex-col items-center justify-center gap-3 p-6 text-sm text-slate-500',
      className,
    )}
  >
    <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
    <p>{label}</p>
  </div>
);

export default FullPageSpinner;
