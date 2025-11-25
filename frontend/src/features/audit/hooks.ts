import { useQuery } from '@tanstack/react-query';

import { fetchAuditLogs } from '../../services/api';
import { queryKeys } from '../../lib/api/queryKeys';
import type { AuditLogResponse } from '../../types';

export const useAuditLogsQuery = (limit: number, offset: number) =>
  useQuery<AuditLogResponse>({
    queryKey: [queryKeys.auditLogs, limit, offset],
    queryFn: () => fetchAuditLogs({ limit, offset }),
    keepPreviousData: true,
  });
