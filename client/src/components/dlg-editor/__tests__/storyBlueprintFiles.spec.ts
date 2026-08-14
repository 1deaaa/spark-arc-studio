import { describe, expect, it } from 'vitest';
import type { StoryFileTreeNode } from '../../../services/aiContracts';
import { selectBlueprintStoryFiles } from '../storyBlueprintFiles';

function story(
  name: string,
  path: string,
  extra: Partial<StoryFileTreeNode> = {},
): StoryFileTreeNode {
  return {
    name,
    path,
    type: 'story',
    ...extra,
  };
}

function folder(name: string, children: StoryFileTreeNode[]): StoryFileTreeNode {
  return {
    name,
    path: name,
    type: 'folder',
    children,
  };
}

describe('selectBlueprintStoryFiles', () => {
  it('结构化正文存在时排除根目录下的空旧聚合文件', () => {
    const files = selectBlueprintStoryFiles([
      story('三 · 诸神黄昏.arc', '三 · 诸神黄昏.arc', { sceneCount: 0 }),
      folder('三 · 诸神黄昏', [
        story('三-1.arc', '三 · 诸神黄昏/三-1.arc', {
          meta: { chap: '003', scene: '001', order: '003001' },
        }),
      ]),
    ]);

    expect(files.map((file) => file.path)).toEqual(['三 · 诸神黄昏/三-1.arc']);
  });

  it('结构化正文存在时也排除带占位场景的根目录旧聚合文件', () => {
    const files = selectBlueprintStoryFiles([
      story('一 · 绝境火种.arc', '一 · 绝境火种.arc', { sceneCount: 6 }),
      folder('一 · 绝境火种', [
        story('一-1.arc', '一 · 绝境火种/一-1.arc', {
          meta: { chap: 1, scene: 1 },
        }),
      ]),
    ]);

    expect(files.map((file) => file.path)).toEqual(['一 · 绝境火种/一-1.arc']);
  });

  it('保留结构化正文、明确标记的自由文件和非根目录文件', () => {
    const files = selectBlueprintStoryFiles([
      story('正文.arc', '正文.arc', { meta: { chap: '001', scene: '002' } }),
      story('自由创作.arc', '自由创作.arc', { meta: { free: '1' } }),
      folder('第一章', [story('旧章节.arc', '第一章/旧章节.arc')]),
    ]);

    expect(files.map((file) => file.path)).toEqual([
      '正文.arc',
      '自由创作.arc',
      '第一章/旧章节.arc',
    ]);
  });

  it('纯旧格式项目不误过滤根目录故事文件', () => {
    const files = selectBlueprintStoryFiles([
      story('第一章.arc', '第一章.arc', { sceneCount: 3 }),
      story('第二章.arc', '第二章.arc', { sceneCount: 0 }),
    ]);

    expect(files.map((file) => file.path)).toEqual(['第一章.arc', '第二章.arc']);
  });
});
