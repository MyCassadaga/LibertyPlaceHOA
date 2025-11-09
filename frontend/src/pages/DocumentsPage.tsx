import React, { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import {
  createDocumentFolder,
  deleteDocumentFolder,
  deleteGovernanceDocument,
  fetchDocumentTree,
  getGovernanceDocumentDownloadUrl,
  uploadGovernanceDocument,
  updateDocumentFolder,
} from '../services/api';
import { DocumentFolder, DocumentTreeResponse, GovernanceDocument } from '../types';
import { userHasAnyRole } from '../utils/roles';

type FolderOption = {
  id: number | null;
  label: string;
};

const MANAGER_ROLES = ['BOARD', 'SYSADMIN', 'SECRETARY', 'TREASURER'];

const DocumentsPage: React.FC = () => {
  const { user } = useAuth();
  const canManage = userHasAnyRole(user, MANAGER_ROLES);
  const [tree, setTree] = useState<DocumentTreeResponse | null>(null);
  const [selectedFolderId, setSelectedFolderId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [folderForm, setFolderForm] = useState({ name: '', description: '', parent_id: null as number | null });
  const [uploadForm, setUploadForm] = useState<{ title: string; description: string; file: File | null }>({
    title: '',
    description: '',
    file: null,
  });

  const loadTree = async () => {
    setLoading(true);
    try {
      const data = await fetchDocumentTree();
      setTree(data);
      if (selectedFolderId !== null && !folderExists(data, selectedFolderId)) {
        setSelectedFolderId(null);
      }
      setError(null);
    } catch (err) {
      setError('Unable to load documents.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadTree();
  }, []);

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
    if (selectedFolderId === null) {
      return tree.root_documents;
    }
    const folder = findFolderById(tree.folders, selectedFolderId);
    return folder ? folder.documents : [];
  }, [tree, selectedFolderId]);

  const currentFolderName = useMemo(() => {
    if (selectedFolderId === null) return 'Community Library';
    const folder = tree ? findFolderById(tree.folders, selectedFolderId) : null;
    return folder ? folder.name : 'Community Library';
  }, [tree, selectedFolderId]);

  const handleFolderSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!folderForm.name.trim()) {
      setError('Folder name is required.');
      return;
    }
    try {
      await createDocumentFolder({
        name: folderForm.name,
        description: folderForm.description || undefined,
        parent_id: folderForm.parent_id,
      });
      setFolderForm({ name: '', description: '', parent_id: null });
      await loadTree();
    } catch (err) {
      setError('Unable to create folder.');
    }
  };

  const handleFolderUpdate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (selectedFolderId == null) return;
    if (!folderForm.name.trim()) {
      setError('Folder name is required.');
      return;
    }
    try {
      await updateDocumentFolder(selectedFolderId, {
        name: folderForm.name,
        description: folderForm.description,
        parent_id: folderForm.parent_id,
      });
      await loadTree();
    } catch (err) {
      setError('Unable to update folder.');
    }
  };

  const handleDeleteFolder = async (folderId: number) => {
    if (!window.confirm('Delete this folder? Documents will move to the parent level.')) return;
    try {
      await deleteDocumentFolder(folderId);
      if (selectedFolderId === folderId) {
        setSelectedFolderId(null);
      }
      await loadTree();
    } catch (err) {
      setError('Unable to delete folder.');
    }
  };

  const handleUpload = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!uploadForm.file) {
      setError('Choose a file to upload.');
      return;
    }
    try {
      setUploadStatus('Uploading…');
      await uploadGovernanceDocument({
        title: uploadForm.title || uploadForm.file.name,
        description: uploadForm.description || undefined,
        folder_id: selectedFolderId,
        file: uploadForm.file,
      });
      setUploadForm({ title: '', description: '', file: null });
      setUploadStatus('Document uploaded.');
      await loadTree();
    } catch (err) {
      setUploadStatus(null);
      setError('Unable to upload document.');
    }
  };

  const handleDeleteDocument = async (documentId: number) => {
    if (!window.confirm('Remove this document?')) return;
    try {
      await deleteGovernanceDocument(documentId);
      await loadTree();
    } catch (err) {
      setError('Unable to delete document.');
    }
  };

  const renderFolderTree = (folders: DocumentFolder[], depth = 0): React.ReactNode => {
    return folders.map((folder) => (
      <div key={folder.id} className="mb-1" style={{ marginLeft: depth * 16 }}>
        <button
          type="button"
          className={`text-sm font-medium ${selectedFolderId === folder.id ? 'text-primary-600' : 'text-slate-600'}`}
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

      {error && <p className="text-sm text-red-600">{error}</p>}
      {loading && <p className="text-sm text-slate-500">Loading documents…</p>}

      {!loading && tree && (
        <div className="grid gap-6 lg:grid-cols-3">
          <aside className="rounded border border-slate-200 p-4">
            <h3 className="text-sm font-semibold text-slate-600">Folders</h3>
            <div className="mt-3 space-y-1">
              <button
                type="button"
                className={`text-sm font-medium ${
                  selectedFolderId === null ? 'text-primary-600' : 'text-slate-600'
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

                {selectedFolderId !== null && (
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
                  <form className="flex flex-col gap-2 text-sm sm:flex-row sm:items-center" onSubmit={handleUpload}>
                    <input
                      className="rounded border border-slate-300 px-3 py-2 text-sm"
                      placeholder="Title"
                      value={uploadForm.title}
                      onChange={(event) => setUploadForm((prev) => ({ ...prev, title: event.target.value }))}
                    />
                    <input
                      className="rounded border border-slate-300 px-3 py-2 text-sm"
                      placeholder="Note"
                      value={uploadForm.description}
                      onChange={(event) => setUploadForm((prev) => ({ ...prev, description: event.target.value }))}
                    />
                    <input
                      type="file"
                      className="text-xs"
                      onChange={(event) =>
                        setUploadForm((prev) => ({ ...prev, file: event.target.files?.[0] ?? null }))
                      }
                      required
                    />
                    <button
                      type="submit"
                      className="rounded bg-primary-600 px-3 py-2 text-xs font-semibold text-white"
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
