import type { StoryFileTreeNode } from '@/services/aiContracts';

function isPositiveInteger(value: unknown): boolean {
  if (typeof value === 'number') {
    return Number.isInteger(value) && value > 0;
  }
  if (typeof value !== 'string') return false;
  const normalized = value.trim();
  return /^\d+$/.test(normalized) && Number(normalized) > 0;
}

function hasSceneIdentity(file: StoryFileTreeNode): boolean {
  const meta = file.meta;
  if (!meta || typeof meta !== 'object') return false;
  return isPositiveInteger(meta.chap) && isPositiveInteger(meta.scene);
}

function isExplicitFreeFile(file: StoryFileTreeNode): boolean {
  const meta = file.meta;
  if (!meta || typeof meta !== 'object') return false;
  const value = meta.free;
  return value === true || value === 1 || ['1', 'true', 'yes'].includes(String(value).trim().toLowerCase());
}

function isRootLevelFile(file: StoryFileTreeNode): boolean {
  const path = String(file.path || '').replace(/\\/g, '/').trim();
  return Boolean(path) && !path.includes('/');
}

export function flattenStoryFileTree(tree: StoryFileTreeNode[]): StoryFileTreeNode[] {
  const files: StoryFileTreeNode[] = [];
  for (const item of tree) {
    if (item.type === 'folder') {
      files.push(...flattenStoryFileTree(item.children || []));
    } else {
      files.push(item);
    }
  }
  return files;
}

export function selectBlueprintStoryFiles(tree: StoryFileTreeNode[]): StoryFileTreeNode[] {
  const storyFiles = flattenStoryFileTree(tree).filter((file) => file.type === 'story');
  const hasStructuredSceneFiles = storyFiles.some(hasSceneIdentity);

  if (!hasStructuredSceneFiles) return storyFiles;

  // 结构化正文出现后，根目录无身份文件只代表历史聚合文件，不应再作为蓝图节点。
  return storyFiles.filter((file) => {
    const isLegacyAggregate = isRootLevelFile(file) && !hasSceneIdentity(file) && !isExplicitFreeFile(file);
    return !isLegacyAggregate;
  });
}
