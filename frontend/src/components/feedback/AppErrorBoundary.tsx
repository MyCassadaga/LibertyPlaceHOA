import React from 'react';
import { ErrorBoundary } from 'react-error-boundary';

import ErrorFallback from './ErrorFallback';

type Props = {
  children: React.ReactNode;
};

const AppErrorBoundary: React.FC<Props> = ({ children }) => (
  <ErrorBoundary
    FallbackComponent={(props) => (
      <ErrorFallback
        {...props}
        onRetry={() => {
          window.location.reload();
        }}
      />
    )}
  >
    {children}
  </ErrorBoundary>
);

export default AppErrorBoundary;
