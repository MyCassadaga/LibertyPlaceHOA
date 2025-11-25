import { useQuery } from '@tanstack/react-query';

import { fetchARCRequests, fetchInvoices, fetchReconciliations, fetchViolations } from '../../services/api';
import type { ARCRequest, Invoice, Reconciliation, Violation } from '../../types';

export const useInvoicesQuery = () =>
  useQuery<Invoice[]>({
    queryKey: ['reports', 'invoices'],
    queryFn: fetchInvoices,
  });

export const useReconciliationsQuery = () =>
  useQuery<Reconciliation[]>({
    queryKey: ['reports', 'reconciliations'],
    queryFn: fetchReconciliations,
  });

export const useViolationsQuery = () =>
  useQuery<Violation[]>({
    queryKey: ['reports', 'violations'],
    queryFn: () => fetchViolations({}),
  });

export const useArcRequestsQuery = () =>
  useQuery<ARCRequest[]>({
    queryKey: ['reports', 'arc-requests'],
    queryFn: fetchARCRequests,
  });
