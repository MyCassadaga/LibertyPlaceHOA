import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  cancelAutopay,
  contactOverdueOwner,
  createVendorPaymentRequest,
  fetchAutopayEnrollment,
  fetchBillingSummary,
  fetchContracts,
  fetchInvoices,
  fetchMyOwnerRecord,
  fetchMyLinkedOwners,
  fetchOverdueAccounts,
  fetchOwners,
  fetchVendorPayments,
  forwardOverdueToAttorney,
  markVendorPaymentPaid,
  sendVendorPayment,
  upsertAutopayEnrollment,
} from '../../services/api';
import { queryKeys } from '../../lib/api/queryKeys';
import type {
  AutopayEnrollment,
  AutopayEnrollmentPayload,
  BillingSummary,
  Contract,
  Invoice,
  OverdueAccount,
  Owner,
  VendorPayment,
} from '../../types';

export const useInvoicesQuery = (enabled: boolean) =>
  useQuery<Invoice[]>({
    queryKey: queryKeys.invoices,
    queryFn: fetchInvoices,
    enabled,
  });

export const useBillingSummaryQuery = (enabled: boolean) =>
  useQuery<BillingSummary>({
    queryKey: queryKeys.billingSummary,
    queryFn: fetchBillingSummary,
    enabled,
  });

export const useContractsQuery = (enabled: boolean) =>
  useQuery<Contract[]>({
    queryKey: queryKeys.contracts,
    queryFn: fetchContracts,
    enabled,
  });

export const useOwnersQuery = (enabled: boolean) =>
  useQuery<Owner[]>({
    queryKey: queryKeys.owners,
    queryFn: fetchOwners,
    enabled,
  });

export const useMyOwnerQuery = (enabled: boolean) =>
  useQuery<Owner>({
    queryKey: queryKeys.myOwner,
    queryFn: fetchMyOwnerRecord,
    enabled,
  });

export const useMyLinkedOwnersQuery = (enabled: boolean) =>
  useQuery<Owner[]>({
    queryKey: queryKeys.myLinkedOwners,
    queryFn: fetchMyLinkedOwners,
    enabled,
  });

export const useOverdueAccountsQuery = (enabled: boolean) =>
  useQuery<OverdueAccount[]>({
    queryKey: queryKeys.overdueAccounts,
    queryFn: fetchOverdueAccounts,
    enabled,
  });

export const useVendorPaymentsQuery = (enabled: boolean) =>
  useQuery<VendorPayment[]>({
    queryKey: queryKeys.vendorPayments,
    queryFn: fetchVendorPayments,
    enabled,
  });

export const useAutopayQuery = (enabled: boolean, ownerId?: number) =>
  useQuery<AutopayEnrollment>({
    queryKey: [...queryKeys.autopay, ownerId ?? 'self'],
    queryFn: () => fetchAutopayEnrollment(ownerId),
    enabled,
  });

export const useAutopayUpsertMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AutopayEnrollmentPayload) => upsertAutopayEnrollment(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.autopay });
    },
  });
};

export const useAutopayCancelMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ownerId?: number) => cancelAutopay(ownerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.autopay });
    },
  });
};

export const useCreateVendorPaymentMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createVendorPaymentRequest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.vendorPayments });
    },
  });
};

export const useSendVendorPaymentMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (paymentId: number) => sendVendorPayment(paymentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.vendorPayments });
    },
  });
};

export const useMarkVendorPaymentPaidMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (paymentId: number) => markVendorPaymentPaid(paymentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.vendorPayments });
    },
  });
};

export const useContactOverdueMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ownerId, message }: { ownerId: number; message?: string }) =>
      contactOverdueOwner(ownerId, message),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.overdueAccounts });
    },
  });
};

export const useForwardToAttorneyMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ownerId, notes }: { ownerId: number; notes?: string }) =>
      forwardOverdueToAttorney(ownerId, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.overdueAccounts });
    },
  });
};
