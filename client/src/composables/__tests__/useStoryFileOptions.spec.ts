import { beforeEach, describe, expect, it } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useStoryFileOptions } from '../useStoryFileOptions';
import { useFileStore } from '../../components/stores/fileStore';
import type { StoryFileTreeNode } from '../../services/aiContracts';

function story(name: string, path: string, sortKey?: StoryFileTreeNode['sortKey']): StoryFileTreeNode {
  return {
    name,
    path,
    type: 'story',
    sortKey,
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

describe('useStoryFileOptions', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('按章节自然序、后端 sortKey 与根文件兜底顺序生成移动端选项', () => {
    const fileStore = useFileStore();
    fileStore.fileTree = [
      folder('第十章', [
        story('第二场.arc', '第十章/第二场.arc', [10, 2]),
        story('第一场.arc', '第十章/第一场.arc', [10, 1]),
      ]),
      story('根文件10.arc', '根文件10.arc'),
      folder('第二章', [
        story('场景二.arc', '第二章/场景二.arc', ['002', '002']),
        story('场景一.arc', '第二章/场景一.arc', ['002', '001']),
      ]),
      story('根文件2.arc', '根文件2.arc'),
      folder('一 · 开端', [
        story('10.arc', '一 · 开端/10.arc'),
        story('2.arc', '一 · 开端/2.arc'),
      ]),
    ];

    const { flatOptions, groupedOptions } = useStoryFileOptions(() => '根目录');

    expect(flatOptions.value.map(option => option.value)).toEqual([
      '一 · 开端/2.arc',
      '一 · 开端/10.arc',
      '第二章/场景一.arc',
      '第二章/场景二.arc',
      '第十章/第一场.arc',
      '第十章/第二场.arc',
      '根文件2.arc',
      '根文件10.arc',
    ]);

    expect(groupedOptions.value).toMatchObject([
      {
        label: '一 · 开端',
        key: 'folder:一 · 开端',
        children: [{ value: '一 · 开端/2.arc' }, { value: '一 · 开端/10.arc' }],
      },
      {
        label: '第二章',
        key: 'folder:第二章',
        children: [{ value: '第二章/场景一.arc' }, { value: '第二章/场景二.arc' }],
      },
      {
        label: '第十章',
        key: 'folder:第十章',
        children: [{ value: '第十章/第一场.arc' }, { value: '第十章/第二场.arc' }],
      },
      {
        label: '根目录',
        key: 'root',
        children: [{ value: '根文件2.arc' }, { value: '根文件10.arc' }],
      },
    ]);
  });
});
