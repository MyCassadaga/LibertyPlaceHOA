const API_BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? '';

const inferMimeFromName = (name: string): string => {
  const extension = name.split('.').pop()?.toLowerCase() ?? '';
  switch (extension) {
    case 'png':
    case 'jpg':
    case 'jpeg':
    case 'gif':
    case 'webp':
      return `image/${extension === 'jpg' ? 'jpeg' : extension}`;
    case 'pdf':
      return 'application/pdf';
    default:
      return 'application/octet-stream';
  }
};

export const resolveFileUrl = (path: string): string => {
  if (!path) return '';
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  const sanitized = path.replace(/^\.?\/*/, '');
  if (!API_BASE) {
    return `/${sanitized}`;
  }
  return `${API_BASE}/${sanitized}`;
};

export const isImageFile = (name: string, mimeType?: string | null): boolean => {
  const mime = (mimeType || inferMimeFromName(name)).toLowerCase();
  return mime.startsWith('image/');
};

export const isPdfFile = (name: string, mimeType?: string | null): boolean => {
  const mime = (mimeType || inferMimeFromName(name)).toLowerCase();
  return mime === 'application/pdf';
};
