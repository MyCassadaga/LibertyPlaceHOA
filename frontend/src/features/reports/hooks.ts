import { useQuery } from '@tanstack/react-query';

import {
  fetchARAgingReportData,
  fetchArcSlaReportData,
  fetchCashFlowReportData,
  fetchViolationsSummaryReportData,
} from '../../services/api';
import type {
  ARAgingReportRow,
  ArcSlaReportRow,
  CashFlowReportRow,
  ViolationsSummaryReportRow,
} from '../../types';

export const useArAgingReportQuery = () =>
  useQuery<ARAgingReportRow[]>({
    queryKey: ['reports', 'ar-aging'],
    queryFn: fetchARAgingReportData,
  });

export const useCashFlowReportQuery = () =>
  useQuery<CashFlowReportRow[]>({
    queryKey: ['reports', 'cash-flow'],
    queryFn: fetchCashFlowReportData,
  });

export const useViolationsSummaryReportQuery = () =>
  useQuery<ViolationsSummaryReportRow[]>({
    queryKey: ['reports', 'violations-summary'],
    queryFn: fetchViolationsSummaryReportData,
  });

export const useArcSlaReportQuery = () =>
  useQuery<ArcSlaReportRow[]>({
    queryKey: ['reports', 'arc-sla'],
    queryFn: fetchArcSlaReportData,
  });
