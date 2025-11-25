import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  claimPaperworkItem,
  fetchPaperwork,
  fetchPaperworkFeatures,
  mailPaperworkItem,
  sendPaperworkViaClick2Mail,
} from '../../services/api';
import { queryKeys } from '../../lib/api/queryKeys';
import type { PaperworkFeatures, PaperworkItem } from '../../types';

const paperworkKey = (status: string, requiredOnly: boolean) =>
  [...queryKeys.paperwork, status, requiredOnly] as const;

export const usePaperworkQuery = (status: string, requiredOnly: boolean) =>
  useQuery<PaperworkItem[]>({
    queryKey: paperworkKey(status, requiredOnly),
    queryFn: () => fetchPaperwork({ status, requiredOnly }),
  });

export const usePaperworkFeaturesQuery = () =>
  useQuery<PaperworkFeatures>({
    queryKey: queryKeys.paperworkFeatures,
    queryFn: fetchPaperworkFeatures,
  });

const useInvalidatePaperwork = () => {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.paperwork });
};

export const useClaimPaperworkMutation = () => {
  const invalidate = useInvalidatePaperwork();
  return useMutation({
    mutationFn: (paperworkId: number) => claimPaperworkItem(paperworkId),
    onSuccess: invalidate,
  });
};

export const useMailPaperworkMutation = () => {
  const invalidate = useInvalidatePaperwork();
  return useMutation({
    mutationFn: (paperworkId: number) => mailPaperworkItem(paperworkId),
    onSuccess: invalidate,
  });
};

export const useClick2MailMutation = () => {
  const invalidate = useInvalidatePaperwork();
  return useMutation({
    mutationFn: (paperworkId: number) => sendPaperworkViaClick2Mail(paperworkId),
    onSuccess: invalidate,
  });
};
