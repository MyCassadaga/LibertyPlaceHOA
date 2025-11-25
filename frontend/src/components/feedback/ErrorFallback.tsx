import React from 'react';
import { FallbackProps } from 'react-error-boundary';

type Props = Partial<FallbackProps> & {
  onRetry?: () => void;
};

const ErrorFallback: React.FC<Props> = ({ error, resetErrorBoundary, onRetry }) => (
  <div className="m-4 rounded border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
    <p className="font-semibold">Something went wrong.</p>
    {error?.message ? <p className="mt-1 text-rose-600">{error.message}</p> : null}
    {(onRetry || resetErrorBoundary) && (
      <button
        type="button"
        onClick={() => {
          if (onRetry) onRetry();
          if (resetErrorBoundary) resetErrorBoundary();
        }}
        className="mt-3 rounded bg-rose-600 px-3 py-1 text-white hover:bg-rose-500"
      >
        Try again
      </button>
    )}
  </div>
);

export default ErrorFallback;
