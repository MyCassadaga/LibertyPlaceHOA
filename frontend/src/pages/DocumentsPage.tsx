import React, { useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import { getGovernanceDocumentDownloadUrl } from '../services/api';
import { DocumentFolder, DocumentTreeResponse, GovernanceDocument } from '../types';
import { userHasAnyRole } from '../utils/roles';
import {
  useCreateFolderMutation,
  useDeleteDocumentMutation,
  useDeleteFolderMutation,
  useDocumentTreeQuery,
  useUpdateFolderMutation,
  useUploadDocumentMutation,
} from '../features/documents/hooks';

type FolderOption = {
  id: number | null;
  label: string;
};

const MANAGER_ROLES = ['BOARD', 'SYSADMIN', 'SECRETARY', 'TREASURER'];

const DocumentsPage: React.FC = () => {
  const { user } = useAuth();
  const canManage = userHasAnyRole(user, MANAGER_ROLES);
  const [selectedFolderId, setSelectedFolderId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [folderForm, setFolderForm] = useState({ name: '', description: '', parent_id: null as number | null });
  const [uploadForm, setUploadForm] = useState<{ title: string; description: string; file: File | null }>({
    title: '',
    description: '',
    file: null,
  });
  const documentTreeQuery = useDocumentTreeQuery();
  const tree = documentTreeQuery.data ?? null;
  const loading = documentTreeQuery.isLoading;
  const queryError = documentTreeQuery.isError ? 'Unable to load documents.' : null;
  const effectiveError = actionError ?? queryError;
  const createFolderMutation = useCreateFolderMutation();
  const updateFolderMutation = useUpdateFolderMutation();
  const deleteFolderMutation = useDeleteFolderMutation();
  const uploadDocumentMutation = useUploadDocumentMutation();
  const deleteDocumentMutation = useDeleteDocumentMutation();
  const resolvedFolderId = useMemo(() => {
    if (!tree) {
      return selectedFolderId;
    }
    if (selectedFolderId !== null && !folderExists(tree, selectedFolderId)) {
      return null;
    }
    return selectedFolderId;
  }, [tree, selectedFolderId]);

  const folderOptions = useMemo<FolderOption[]>(() => {
    if (!tree) return [{ id: null, label: 'Root' }];
    const options: FolderOption[] = [{ id: null, label: 'Root' }];
    const traverse = (folders: DocumentFolder[], prefix = '') => {
      folders.forEach((folder) => {
        options.push({ id: folder.id, label: `${prefix}${folder.name}` });
        if (folder.children?.length) {
          traverse(folder.children, `${prefix}• `);
        }
      });
    };
    traverse(tree.folders);
    return options;
  }, [tree]);

  const currentDocuments = useMemo<GovernanceDocument[]>(() => {
    if (!tree) return [];
    if (resolvedFolderId === null) {
      return tree.root_documents;
    }
    const folder = findFolderById(tree.folders, resolvedFolderId);
    return folder ? folder.documents : [];
  }, [tree, resolvedFolderId]);

  const currentFolderName = useMemo(() => {
    if (resolvedFolderId === null) return 'Community Library';
    const folder = tree ? findFolderById(tree.folders, resolvedFolderId) : null;
    return folder ? folder.name : 'Community Library';
  }, [tree, resolvedFolderId]);

const handleFolderSubmit = async (event: React.FormEvent) => {
  event.preventDefault();
  if (!folderForm.name.trim()) {
    setActionError('Folder name is required.');
    return;
  }
  setActionError(null);
  try {
    await createFolderMutation.mutateAsync({
      name: folderForm.name,
      description: folderForm.description || undefined,
      parent_id: folderForm.parent_id,
    });
    setFolderForm({ name: '', description: '', parent_id: null });
  } catch (err) {
    console.error('Unable to create folder.', err);
    setActionError('Unable to create folder.');
  }
};

const handleFolderUpdate = async (event: React.FormEvent) => {
  event.preventDefault();
    if (resolvedFolderId == null) return;
  if (!folderForm.name.trim()) {
    setActionError('Folder name is required.');
    return;
  }
  setActionError(null);
  try {
      await updateFolderMutation.mutateAsync({
        folderId: resolvedFolderId,
      payload: {
        name: folderForm.name,
        description: folderForm.description,
        parent_id: folderForm.parent_id,
      },
    });
  } catch (err) {
    console.error('Unable to update folder.', err);
    setActionError('Unable to update folder.');
  }
};

const handleDeleteFolder = async (folderId: number) => {
  if (!window.confirm('Delete this folder? Documents will move to the parent level.')) return;
  try {
    await deleteFolderMutation.mutateAsync(folderId);
    if (resolvedFolderId === folderId) {
      setSelectedFolderId(null);
    }
  } catch (err) {
    console.error('Unable to delete folder.', err);
    setActionError('Unable to delete folder.');
  }
};

  const handleUpload = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!uploadForm.file) {
      setActionError('Choose a file to upload.');
      return;
    }
    setActionError(null);
    try {
      setUploadStatus('Uploading…');
      await uploadDocumentMutation.mutateAsync({
        title: uploadForm.title || uploadForm.file.name,
        description: uploadForm.description || undefined,
        folder_id: resolvedFolderId,
        file: uploadForm.file,
      });
      setUploadForm({ title: '', description: '', file: null });
      setUploadStatus('Document uploaded.');
    } catch (err) {
      console.error('Unable to upload document.', err);
      setUploadStatus(null);
      setActionError('Unable to upload document.');
    }
  };

  const handleDeleteDocument = async (documentId: number) => {
    if (!window.confirm('Remove this document?')) return;
    try {
      await deleteDocumentMutation.mutateAsync(documentId);
    } catch (err) {
      console.error('Unable to delete document.', err);
      setActionError('Unable to delete document.');
    }
  };

  const renderFolderTree = (folders: DocumentFolder[], depth = 0): React.ReactNode => {
    return folders.map((folder) => (
      <div key={folder.id} className="mb-1" style={{ marginLeft: depth * 16 }}>
        <button
          type="button"
          className={`text-sm font-medium ${resolvedFolderId === folder.id ? 'text-primary-600' : 'text-slate-600'}`}
          onClick={() => {
            setSelectedFolderId(folder.id);
            setFolderForm({
              name: folder.name,
              description: folder.description || '',
              parent_id: folder.parent_id ?? null,
            });
          }}
        >
          {folder.name}
        </button>
        {folder.children?.length ? renderFolderTree(folder.children, depth + 1) : null}
        {canManage && (
          <button
            type="button"
            className="ml-2 text-xs text-rose-600"
            onClick={() => handleDeleteFolder(folder.id)}
          >
            Delete
          </button>
        )}
      </div>
    ));
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-primary-600">Community Documents</h2>
          <p className="text-sm text-slate-500">Governance policies, reports, and shared paperwork.</p>
        </div>
      </header>

      {effectiveError && <p className="text-sm text-red-600">{effectiveError}</p>}
      {loading && <p className="text-sm text-slate-500">Loading documents…</p>}

      {!loading && tree && (
        <div className="grid gap-6 lg:grid-cols-3">
          <aside className="rounded border border-slate-200 p-4">
            <h3 className="text-sm font-semibold text-slate-600">Folders</h3>
            <div className="mt-3 space-y-1">
              <button
                type="button"
                className={`text-sm font-medium ${
                  resolvedFolderId === null ? 'text-primary-600' : 'text-slate-600'
                }`}
                onClick={() => {
                  setSelectedFolderId(null);
                  setFolderForm({ name: '', description: '', parent_id: null });
                }}
              >
                Root
              </button>
              {renderFolderTree(tree.folders)}
            </div>

            {canManage && (
              <div className="mt-6 space-y-4 text-sm">
                <div>
                  <h4 className="text-xs font-semibold uppercase text-slate-500">Create folder</h4>
                  <form className="mt-2 space-y-2" onSubmit={handleFolderSubmit}>
                    <input
                      className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                      placeholder="Folder name"
                      value={folderForm.name}
                      onChange={(event) => setFolderForm((prev) => ({ ...prev, name: event.target.value }))}
                      required
                    />
                    <textarea
                      className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                      placeholder="Description (optional)"
                      value={folderForm.description}
                      onChange={(event) => setFolderForm((prev) => ({ ...prev, description: event.target.value }))}
                      rows={2}
                    />
                    <select
                      className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                      value={folderForm.parent_id ?? ''}
                      onChange={(event) =>
                        setFolderForm((prev) => ({
                          ...prev,
                          parent_id: event.target.value ? Number(event.target.value) : null,
                        }))
                      }
                    >
                      {folderOptions.map((option) => (
                        <option key={option.id ?? 'root'} value={option.id ?? ''}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <button
                      type="submit"
                      className="w-full rounded bg-primary-600 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-white"
                    >
                      Add folder
                    </button>
                  </form>
                </div>

                {resolvedFolderId !== null && (
                  <div>
                    <h4 className="text-xs font-semibold uppercase text-slate-500">Update selected folder</h4>
                    <form className="mt-2 space-y-2" onSubmit={handleFolderUpdate}>
                      <input
                        className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                        placeholder="Folder name"
                        value={folderForm.name}
                        onChange={(event) => setFolderForm((prev) => ({ ...prev, name: event.target.value }))}
                        required
                      />
                      <textarea
                        className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                        placeholder="Description"
                        value={folderForm.description}
                        onChange={(event) => setFolderForm((prev) => ({ ...prev, description: event.target.value }))}
                        rows={2}
                      />
                      <select
                        className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                        value={folderForm.parent_id ?? ''}
                        onChange={(event) =>
                          setFolderForm((prev) => ({
                            ...prev,
                            parent_id: event.target.value ? Number(event.target.value) : null,
                          }))
                        }
                      >
                        {folderOptions.map((option) => (
                          <option key={option.id ?? 'root'} value={option.id ?? ''}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                      <button
                        type="submit"
                        className="w-full rounded border border-slate-300 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-600 hover:bg-slate-50"
                      >
                        Save changes
                      </button>
                    </form>
                  </div>
                )}
              </div>
            )}
          </aside>

          <section className="lg:col-span-2">
            <div className="rounded border border-slate-200 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold text-slate-700">{currentFolderName}</h3>
                  <p className="text-xs text-slate-500">Download governance docs & shared reports.</p>
                </div>
                {canManage && (
                  <form
                    className="flex w-full flex-col gap-2 text-sm sm:flex-row sm:flex-wrap sm:items-center"
                    onSubmit={handleUpload}
                  >
                    <input
                      className="w-full rounded border border-slate-300 px-3 py-2 text-sm sm:w-40"
                      placeholder="Title"
                      value={uploadForm.title}
                      onChange={(event) => setUploadForm((prev) => ({ ...prev, title: event.target.value }))}
                    />
                    <input
                      className="w-full rounded border border-slate-300 px-3 py-2 text-sm sm:w-52"
                      placeholder="Note"
                      value={uploadForm.description}
                      onChange={(event) => setUploadForm((prev) => ({ ...prev, description: event.target.value }))}
                    />
                    <input
                      type="file"
                      className="w-full text-xs sm:w-auto"
                      onChange={(event) =>
                        setUploadForm((prev) => ({ ...prev, file: event.target.files?.[0] ?? null }))
                      }
                      required
                    />
                    <button
                      type="submit"
                      className="w-full rounded bg-primary-600 px-3 py-2 text-xs font-semibold text-white sm:w-auto"
                    >
                      Upload
                    </button>
                  </form>
                )}
              </div>

              {uploadStatus && <p className="mt-2 text-xs text-emerald-600">{uploadStatus}</p>}

              <div className="mt-4 divide-y divide-slate-200 text-sm">
                {currentDocuments.length === 0 && (
                  <p className="py-4 text-sm text-slate-500">No documents in this folder yet.</p>
                )}
                {currentDocuments.map((document) => (
                  <div key={document.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                    <div>
                      <p className="font-semibold text-slate-700">{document.title}</p>
                      <p className="text-xs text-slate-500">
                        Added {new Date(document.created_at).toLocaleDateString()}
                        {document.file_size ? ` • ${(document.file_size / 1024).toFixed(1)} KB` : ''}
                      </p>
                      {document.description && (
                        <p className="text-xs text-slate-500">{document.description}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <a
                        href={getGovernanceDocumentDownloadUrl(document.id)}
                        className="rounded border border-slate-300 px-3 py-1 text-slate-600 hover:bg-slate-50"
                        target="_blank"
                        rel="noreferrer"
                      >
                        Download
                      </a>
                      {canManage && (
                        <button
                          type="button"
                          className="rounded border border-rose-200 px-3 py-1 text-rose-600 hover:bg-rose-50"
                          onClick={() => handleDeleteDocument(document.id)}
                        >
                          Remove
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
};

function findFolderById(folders: DocumentFolder[], id: number): DocumentFolder | null {
  for (const folder of folders) {
    if (folder.id === id) return folder;
    if (folder.children?.length) {
      const match = findFolderById(folder.children, id);
      if (match) return match;
    }
  }
  return null;
}

function folderExists(tree: DocumentTreeResponse, id: number): boolean {
  if (id === null) return true;
  return Boolean(findFolderById(tree.folders, id));
}

export default DocumentsPage;
