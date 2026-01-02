import type { TemplateMergeTag } from '../types';

const TAG_REGEX = /{{\s*([a-zA-Z0-9_]+)\s*}}/g;

export const renderMergeTags = (text: string, tags: TemplateMergeTag[]): string => {
  if (!text) return text;
  const lookup = tags.reduce<Record<string, string>>((acc, tag) => {
    acc[tag.key] = tag.sample;
    return acc;
  }, {});
  return text.replace(TAG_REGEX, (match, key: string) => lookup[key] ?? match);
};
