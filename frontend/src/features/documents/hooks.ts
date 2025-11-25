import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createDocumentFolder,
  deleteDocumentFolder,
  deleteGovernanceDocument,
  fetchDocumentTree,
  uploadGovernanceDocument,
  updateDocumentFolder,
} from '../../services/api';
import { queryKeys } from '../../lib/api/queryKeys';
import type { DocumentTreeResponse } from '../../types';

export const useDocumentTreeQuery = () =>
  useQuery<DocumentTreeResponse>({
    queryKey: queryKeys.documents,
    queryFn: fetchDocumentTree,
  });

const useInvalidateDocuments = () => {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.documents });
};

export const useCreateFolderMutation = () => {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: (payload: { name: string; description?: string; parent_id?: number | null }) =>
      createDocumentFolder(payload),
    onSuccess: invalidate,
  });
};

export const useUpdateFolderMutation = () => {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: ({
      folderId,
      payload,
    }: {
      folderId: number;
      payload: { name?: string; description?: string | null; parent_id?: number | null };
    }) => updateDocumentFolder(folderId, payload),
    onSuccess: invalidate,
  });
};

export const useDeleteFolderMutation = () => {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: (folderId: number) => deleteDocumentFolder(folderId),
    onSuccess: invalidate,
  });
};

export const useUploadDocumentMutation = () => {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: (payload: {
      folder_id?: number | null;
      title: string;
      description?: string;
      file: File;
    }) => uploadGovernanceDocument(payload),
    onSuccess: invalidate,
  });
};

export const useDeleteDocumentMutation = () => {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: (documentId: number) => deleteGovernanceDocument(documentId),
    onSuccess: invalidate,
  });
};
