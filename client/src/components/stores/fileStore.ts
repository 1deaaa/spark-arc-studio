import { defineStore } from 'pinia';
import { fetchFileTree, createFileOrFolder, deleteFileOrFolder, renameFileOrFolder } from '@/services/api';
import { useProjectStore } from './projectStore';
import { useSceneStore } from './sceneStore';
import bus from '@/eventBus';
import type { StoryFileTreeNode } from '@/services/aiContracts';

type FileTreeNode = StoryFileTreeNode;

let fileTreeRequestSeq = 0;

type FileStoreState = {
  fileTree: FileTreeNode[];
  selectedFile: FileTreeNode | null;
  activeFormatFilter: 'arc' | 'novel';
  selectedFiles: FileTreeNode[];
  lastSelectedFile: FileTreeNode | null;
};

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}

export const useFileStore = defineStore('file', {
  state: (): FileStoreState => ({
    fileTree: [],
    selectedFile: null,
    activeFormatFilter: 'arc',
    // 多选支持
    selectedFiles: [],      // 多选的文件列表
    lastSelectedFile: null, // 用于 Shift 连续选择的锚点
  }),
  getters: {
    // 判断某个文件是否在多选列表中
    isFileSelected: (state: FileStoreState) => (item: FileTreeNode) => {
      if (!item.path) return false;
      return state.selectedFiles.some(f => f.path === item.path);
    },
    // 多选数量
    selectedCount: (state: FileStoreState) => state.selectedFiles.length,
  },
  actions: {
    // 清空多选
    clearSelection() {
      this.selectedFiles = [];
      this.lastSelectedFile = null;
    },
    // 单选（普通点击）
    selectSingle(item: FileTreeNode) {
      this.selectedFile = item;
      this.selectedFiles = [item];
      this.lastSelectedFile = item;
    },
    // Ctrl 点击切换选中
    toggleSelect(item: FileTreeNode) {
      if (!item.path) return;
      const idx = this.selectedFiles.findIndex(f => f.path === item.path);
      if (idx >= 0) {
        this.selectedFiles.splice(idx, 1);
        // 如果取消的是当前 selectedFile，更新它
        if (this.selectedFile?.path === item.path) {
          this.selectedFile = this.selectedFiles[0] || null;
        }
      } else {
        this.selectedFiles.push(item);
        this.selectedFile = item;
      }
      this.lastSelectedFile = item;
    },
    // Shift 点击范围选择
    selectRange(item: FileTreeNode, flatList: FileTreeNode[]) {
      if (!item.path) return;
      if (!this.lastSelectedFile) {
        this.selectSingle(item);
        return;
      }
      const anchor = this.lastSelectedFile;
      const lastIdx = flatList.findIndex(f => f.path === anchor.path);
      const curIdx = flatList.findIndex(f => f.path === item.path);
      if (lastIdx < 0 || curIdx < 0) {
        this.selectSingle(item);
        return;
      }
      const start = Math.min(lastIdx, curIdx);
      const end = Math.max(lastIdx, curIdx);
      const rangeItems = flatList.slice(start, end + 1);
      // 合并到现有选择（去重）
      for (const it of rangeItems) {
        if (!this.selectedFiles.some(f => f.path === it.path)) {
          this.selectedFiles.push(it);
        }
      }
      this.selectedFile = item;
    },
    async loadFileTree(projectName: string, format: string | null = null) {
      try {
        const normalizedFormat: 'arc' | 'novel' = format === 'novel'
          ? 'novel'
          : format === 'arc' || format === 'script'
            ? 'arc'
            : this.activeFormatFilter;
        const requestId = ++fileTreeRequestSeq;
        const selectedPath = this.selectedFile?.path || null;
        this.activeFormatFilter = normalizedFormat;

        // 1. 同步加载本地 localStorage 缓存，实现瞬间“秒开”
        const cacheKey = `filetree-cache:${projectName}:${normalizedFormat}`;
        try {
          const cached = localStorage.getItem(cacheKey);
          if (cached) {
            const cachedFiles = JSON.parse(cached);
            if (Array.isArray(cachedFiles)) {
              this.fileTree = cachedFiles;
              if (selectedPath) {
                this.selectedFile = findByPath(cachedFiles, selectedPath);
              }
            }
          }
        } catch (cacheError) {
          console.warn('[fileStore] 加载或解析本地文件树缓存失败:', cacheError);
        }

        // 2. 异步静默拉取后端最新数据
        const files = await fetchFileTree(projectName, normalizedFormat);
        if (requestId !== fileTreeRequestSeq) {
          return;
        }

        // 3. 对比差异 (SWR 策略)：仅在确实有变动时更新 State 并重新写入缓存，避免 DOM 震荡
        const newFilesStr = JSON.stringify(files);
        const oldFilesStr = JSON.stringify(this.fileTree);
        if (newFilesStr !== oldFilesStr) {
          this.fileTree = files;
          if (selectedPath) {
            this.selectedFile = findByPath(files, selectedPath);
          }
          try {
            localStorage.setItem(cacheKey, newFilesStr);
          } catch (storageError) {
            console.warn('[fileStore] 保存本地文件树缓存失败:', storageError);
          }
        }
      } catch (error: unknown) {
        console.error('加载文件树失败:', error);
      }
    },
    async setCurrentFile(projectName: string, filePath: string) {
      // 确保文件树存在（首次进入时可能还未加载或未完成）
      if (!Array.isArray(this.fileTree) || this.fileTree.length === 0) {
        await this.loadFileTree(projectName, String(filePath).endsWith('.md') ? 'novel' : 'arc');
      }
      // 在树中查找该文件并选中，同时加载剧本
      const target = findByPath(this.fileTree, filePath);
      if (target) {
        this.selectedFile = target;
        if (target.type === 'story' && target.path) {
          const sceneStore = useSceneStore();
          await sceneStore.loadStory(target.path);
        }
      } else {
        // 兼容仅传入文件名（在根目录下）
        const maybe = findByNameInTree(this.fileTree, filePath);
        if (maybe) {
          this.selectedFile = maybe;
          if (maybe.type === 'story' && maybe.path) {
            const sceneStore = useSceneStore();
            await sceneStore.loadStory(maybe.path);
          }
        } else {
          throw new Error(`文件未找到: ${filePath}`);
        }
      }
    },
    async createFile(type: 'folder' | 'story', parentDir = '', opts: Record<string, unknown> = {}): Promise<string | null> {
      const projectStore = useProjectStore();
      const sceneStore = useSceneStore();
      // prompt 弹窗始终居中显示，不使用鼠标坐标定位（坐标仅 confirm 类弹窗使用）
      const { x: _x, y: _y, ...promptOpts } = opts as { x?: unknown; y?: unknown; [k: string]: unknown };
      // 兜底文案：当调用方未传入 i18n 文案时使用（应尽量由调用方传入 i18n 文案）
      const isNovel = sceneStore.workspaceMode === 'novel';
      const defaultTitle = type === 'folder'
        ? '新建分卷'
        : (isNovel ? '新建章节' : '新建剧幕');
      const defaultMessage = type === 'folder'
        ? '请输入新的分卷名称：'
        : (isNovel ? '请输入新的章节名称：' : '请输入新的剧幕名称：');
      const name = await new Promise<string | null>((resolve) => {
        bus.emit('prompt', {
          title: defaultTitle,
          message: defaultMessage,
          resolve: (value: unknown) => resolve(typeof value === 'string' ? value : null),
          ...promptOpts
        });
      });
      if (name) {
        try {
          let normalizedName = String(name || '').trim();
          if (type === 'story' && !/\.(arc|md)$/i.test(normalizedName)) {
            normalizedName += this.activeFormatFilter === 'novel' ? '.md' : '.arc';
          }
          const target = parentDir ? `${parentDir.replace(/\/+$/,'').replace(/^\/+/, '')}/${normalizedName}` : normalizedName;
          await createFileOrFolder(projectStore.currentProject, type, target);
          await this.loadFileTree(projectStore.currentProject, this.activeFormatFilter);
          return type === 'story' && this.activeFormatFilter === 'arc'
            ? target.replace(/\.arc$/i, '')
            : target;
        } catch (error: unknown) {
          bus.emit('toast', { type: 'error', message: `创建失败: ${getErrorMessage(error)}` });
        }
      }
      return null;
    },
    async deleteSelectedFile(opts: Record<string, unknown> = {}) {
      if (!this.selectedFile) {
        bus.emit('toast', { type: 'error', message: '请先选择一个作品或章节' });
        return;
      }
      const ok = await new Promise<boolean>((resolve) => bus.emit('confirm', {
        title: '删除',
        message: `确定要删除 "${this.selectedFile?.name}" 吗？`,
        resolve: (value: unknown) => resolve(Boolean(value)),
        ...opts
      }));
      if (ok) {
        try {
          if (!this.selectedFile.path) {
            throw new Error('无效文件路径');
          }
          const projectStore = useProjectStore();
          await deleteFileOrFolder(projectStore.currentProject, this.selectedFile.path);
          this.selectedFile = null;
          this.selectedFiles = this.selectedFiles.filter(f => f.path !== this.selectedFile?.path);
          await this.loadFileTree(projectStore.currentProject);
        } catch (error: unknown) {
          bus.emit('toast', { type: 'error', message: `删除失败: ${getErrorMessage(error)}` });
        }
      }
    },
    // 批量删除多选文件
    async deleteSelectedFiles(opts: Record<string, unknown> = {}) {
      if (this.selectedFiles.length === 0) {
        bus.emit('toast', { type: 'error', message: '请先选择要删除的作品或章节' });
        return;
      }
      const count = this.selectedFiles.length;
      const names = this.selectedFiles.map(f => f.name).join(', ');
      const ok = await new Promise<boolean>((resolve) => bus.emit('confirm', {
        title: '批量删除',
        message: `确定要删除选中的 ${count} 个项目吗？\n${names}`,
        resolve: (value: unknown) => resolve(Boolean(value)),
        ...opts 
      }));
      if (ok) {
        const projectStore = useProjectStore();
        let successCount = 0;
        let failCount = 0;
        // 逐个删除
        for (const file of [...this.selectedFiles]) {
          try {
            if (!file.path) {
              failCount++;
              continue;
            }
            await deleteFileOrFolder(projectStore.currentProject, file.path);
            successCount++;
          } catch (error: unknown) {
            failCount++;
            console.error(`删除 ${file.name} 失败:`, error);
          }
        }
        // 清空选择
        this.selectedFiles = [];
        this.selectedFile = null;
        this.lastSelectedFile = null;
        await this.loadFileTree(projectStore.currentProject);
        if (failCount > 0) {
          bus.emit('toast', { type: 'warning', message: `删除完成：成功 ${successCount} 个，失败 ${failCount} 个` });
        } else {
          bus.emit('toast', { type: 'success', message: `成功删除 ${successCount} 个项目` });
        }
      }
    },
  async renameSelectedFile(opts: Record<string, unknown> = {}) {
      if (!this.selectedFile) {
        bus.emit('toast', { type: 'error', message: '请先选择一个作品或章节' });
        return;
      }
  const newName = await new Promise<string | null>((resolve) => bus.emit('prompt', {
        title: '重命名',
        message: '请输入新的名称：',
        resolve: (value: unknown) => resolve(typeof value === 'string' ? value : null),
        ...opts
      }));
      const normalizedNewName = typeof newName === 'string' ? newName : String(newName || '');
      if (normalizedNewName && normalizedNewName !== this.selectedFile.name) {
        try {
          const projectStore = useProjectStore();
  // 计算新路径：仅替换路径末尾段（兼容 Windows 与 POSIX 分隔符）
  const rawPath = this.selectedFile.path || this.selectedFile.name;
  const segments = String(rawPath).split(/[\\/]+/);
          segments[segments.length - 1] = normalizedNewName;
      const newPath = segments.join('/');
      await renameFileOrFolder(projectStore.currentProject, rawPath, newPath);
          // 刷新树并尝试选中新项
          await this.loadFileTree(projectStore.currentProject);
          this.selectedFile = findByPath(this.fileTree, newPath);
        } catch (error: unknown) {
          bus.emit('toast', { type: 'error', message: `重命名失败: ${getErrorMessage(error)}` });
        }
      }
    },
  },
});

function findByPath(tree: FileTreeNode[], path: string): FileTreeNode | null {
  for (const item of tree) {
    if (item.path && item.path === path) return item;
    if (Array.isArray(item.children)) {
      const r = findByPath(item.children, path);
      if (r) return r;
    }
  }
  return null;
}

function findByNameInTree(tree: FileTreeNode[], name: string): FileTreeNode | null {
  const nn = String(name).replace(/^.*\//, '');
  for (const item of tree) {
    if (item.name === nn) return item;
    if (Array.isArray(item.children)) {
      const r = findByNameInTree(item.children, nn);
      if (r) return r;
    }
  }
  return null;
}

// 将文件树展平为一维数组（用于 Shift 范围选择）
export function flattenFileTree(tree: FileTreeNode[]): FileTreeNode[] {
  const result: FileTreeNode[] = [];
  function walk(items: FileTreeNode[]) {
    for (const item of items) {
      result.push(item);
      if (Array.isArray(item.children) && item.children.length > 0) {
        walk(item.children);
      }
    }
  }
  walk(tree);
  return result;
}
