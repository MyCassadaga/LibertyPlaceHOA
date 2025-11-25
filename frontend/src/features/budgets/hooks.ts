import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  addBudgetLineItem,
  addReserveItem,
  approveBudget,
  createBudget,
  deleteBudgetAttachment,
  deleteBudgetLineItem,
  deleteReserveItem,
  fetchBudgetDetail,
  fetchBudgets,
  lockBudget,
  revokeBudgetApproval,
  unlockBudget,
  updateBudget,
  updateBudgetLineItem,
  updateReserveItem,
  uploadBudgetAttachment,
} from '../../services/api';
import { queryKeys } from '../../lib/api/queryKeys';
import type { BudgetDetail, BudgetSummary } from '../../types';

export const useBudgetsQuery = () =>
  useQuery<BudgetSummary[]>({
    queryKey: queryKeys.budgets,
    queryFn: fetchBudgets,
  });

export const useBudgetDetailQuery = (budgetId: number | null) =>
  useQuery<BudgetDetail>({
    queryKey: budgetId != null ? [...queryKeys.budgetDetail, budgetId] : ['budgets', 'detail', 'noop'],
    queryFn: () => fetchBudgetDetail(budgetId!),
    enabled: budgetId != null,
  });

const useInvalidateBudgets = () => {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.budgets });
};

const useInvalidateBudgetDetail = () => {
  const queryClient = useQueryClient();
  return (budgetId: number) =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets }),
      queryClient.invalidateQueries({ queryKey: [...queryKeys.budgetDetail, budgetId] }),
    ]);
};

export const useCreateBudgetMutation = () => {
  const invalidate = useInvalidateBudgets();
  return useMutation({
    mutationFn: createBudget,
    onSuccess: invalidate,
  });
};

export const useUpdateBudgetMutation = () => {
  const invalidateDetail = useInvalidateBudgetDetail();
  return useMutation({
    mutationFn: ({
      budgetId,
      payload,
    }: {
      budgetId: number;
      payload: Parameters<typeof updateBudget>[1];
    }) => updateBudget(budgetId, payload),
    onSuccess: (_, variables) => {
      void invalidateDetail(variables.budgetId);
    },
  });
};

export const useBudgetStatusMutation = (action: 'approve' | 'withdraw' | 'lock' | 'unlock') => {
  const invalidateDetail = useInvalidateBudgetDetail();
  return useMutation({
    mutationFn: (budgetId: number) => {
      switch (action) {
        case 'approve':
          return approveBudget(budgetId);
        case 'withdraw':
          return revokeBudgetApproval(budgetId);
        case 'lock':
          return lockBudget(budgetId);
        case 'unlock':
          return unlockBudget(budgetId);
        default:
          return Promise.reject(new Error('Unknown action'));
      }
    },
    onSuccess: (data) => {
      void invalidateDetail(data.id);
    },
  });
};

export const useBudgetLineItemMutation = (type: 'add' | 'update' | 'delete') => {
  const invalidateDetail = useInvalidateBudgetDetail();
  return useMutation({
    mutationFn: ({
      budgetId,
      lineItemId,
      payload,
    }: {
      budgetId: number;
      lineItemId?: number;
      payload?: Parameters<typeof addBudgetLineItem>[1];
    }) => {
      switch (type) {
        case 'add':
          return addBudgetLineItem(budgetId, payload!);
        case 'update':
          return updateBudgetLineItem(lineItemId!, payload!);
        case 'delete':
          return deleteBudgetLineItem(lineItemId!);
        default:
          return Promise.reject(new Error('Unknown line item action'));
      }
    },
    onSuccess: (_, variables) => {
      void invalidateDetail(variables.budgetId);
    },
  });
};

export const useReserveItemMutation = (type: 'add' | 'update' | 'delete') => {
  const invalidateDetail = useInvalidateBudgetDetail();
  return useMutation({
    mutationFn: ({
      budgetId,
      reserveId,
      payload,
    }: {
      budgetId: number;
      reserveId?: number;
      payload?: Parameters<typeof addReserveItem>[1];
    }) => {
      switch (type) {
        case 'add':
          return addReserveItem(budgetId, payload!);
        case 'update':
          return updateReserveItem(reserveId!, payload!);
        case 'delete':
          return deleteReserveItem(reserveId!);
        default:
          return Promise.reject(new Error('Unknown reserve action'));
      }
    },
    onSuccess: (_, variables) => {
      void invalidateDetail(variables.budgetId);
    },
  });
};

export const useBudgetAttachmentMutation = (type: 'upload' | 'delete') => {
  const invalidateDetail = useInvalidateBudgetDetail();
  return useMutation({
    mutationFn: ({
      budgetId,
      attachmentId,
      file,
    }: {
      budgetId: number;
      attachmentId?: number;
      file?: File;
    }) => {
      if (type === 'upload') {
        return uploadBudgetAttachment(budgetId, file!);
      }
      return deleteBudgetAttachment(attachmentId!);
    },
    onSuccess: (_, variables) => {
      void invalidateDetail(variables.budgetId);
    },
  });
};
