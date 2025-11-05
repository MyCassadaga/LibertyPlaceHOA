import React from 'react';

import { isImageFile, isPdfFile, resolveFileUrl } from '../utils/files';

interface FilePreviewProps {
  name: string;
  storedPath: string;
  uploadedAt?: string;
  contentType?: string | null;
  sizeBytes?: number | null;
}

const formatSize = (size?: number | null): string | null => {
  if (!size || size <= 0) return null;
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
};

const FilePreview: React.FC<FilePreviewProps> = ({ name, storedPath, uploadedAt, contentType, sizeBytes }) => {
  const fileUrl = resolveFileUrl(storedPath);
  const isImage = isImageFile(name, contentType);
  const isPdf = isPdfFile(name, contentType);
  const sizeLabel = formatSize(sizeBytes);

  return (
    <div className="flex flex-col gap-2 rounded border border-slate-200 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-slate-700">{name}</span>
        {sizeLabel && <span className="text-xs text-slate-500">{sizeLabel}</span>}
        {uploadedAt && (
          <span className="text-xs text-slate-500">
            Uploaded {new Date(uploadedAt).toLocaleString()}
          </span>
        )}
      </div>
      <div className="flex flex-col gap-3">
        {isImage && (
          <img
            src={fileUrl}
            alt={name}
            className="max-h-48 w-auto rounded border border-slate-200 object-contain"
          />
        )}
        {isPdf && (
          <iframe
            title={name}
            src={fileUrl}
            className="h-48 w-full rounded border border-slate-200"
          />
        )}
        <div>
          <a
            href={fileUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-semibold text-primary-600 hover:text-primary-500"
          >
            Open File
          </a>
        </div>
      </div>
    </div>
  );
};

export default FilePreview;
