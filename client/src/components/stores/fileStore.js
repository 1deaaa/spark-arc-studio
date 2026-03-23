import { defineStore } from 'pinia';
import { fetchFileTree, createFileOrFolder, deleteFileOrFolder, renameFileOrFolder } from '@/services/api';
import { useProjectStore } from './projectStore';
import { useSceneStore } from './sceneStore';
import bus from '@/eventBus';

export const useFileStore = defineStore('file', {
  state: () => ({
    fileTree: [],
    selectedFile: null,
    activeFormatFilter: 'arc',
    // 多选支持
    selectedFiles: [],      // 多选的文件列表
    lastSelectedFile: null, // 用于 Shift 连续选择的锚点
  }),
  getters: {
    // 判断某个文件是否在多选列表中
    isFileSelected: (state) => (item) => {
      return state.selectedFiles.some(f => f.path === item.path);
    },
    // 多选数量
    selectedCount: (state) => state.selectedFiles.length,
  },
  actions: {
    // 清空多选
    clearSelection() {
      this.selectedFiles = [];
      this.lastSelectedFile = null;
    },
    // 单选（普通点击）
    selectSingle(item) {
      this.selectedFile = item;
      this.selectedFiles = [item];
      this.lastSelectedFile = item;
    },
    // Ctrl 点击切换选中
    toggleSelect(item) {
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
    selectRange(item, flatList) {
      if (!this.lastSelectedFile) {
        this.selectSingle(item);
        return;
      }
      const lastIdx = flatList.findIndex(f => f.path === this.lastSelectedFile.path);
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
    async loadFileTree(projectName, format = null) {
      try {
        const normalizedFormat = format === 'novel' ? 'novel' : 'arc';
        this.activeFormatFilter = normalizedFormat;
        const files = await fetchFileTree(projectName, normalizedFormat);
        this.fileTree = files;
      } catch (error) {
        console.error('加载文件树失败:', error);
      }
    },
    async setCurrentFile(projectName, filePath) {
      // 确保文件树存在（首次进入时可能还未加载或未完成）
      if (!Array.isArray(this.fileTree) || this.fileTree.length === 0) {
        await this.loadFileTree(projectName, String(filePath).endsWith('.md') ? 'novel' : 'arc');
      }
      // 在树中查找该文件并选中，同时加载剧本
      const target = findByPath(this.fileTree, filePath);
      if (target) {
        this.selectedFile = target;
        if (target.type === 'story') {
          const sceneStore = useSceneStore();
          await sceneStore.loadStory(target.path);
        }
      } else {
        // 兼容仅传入文件名（在根目录下）
        const maybe = findByNameInTree(this.fileTree, filePath);
        if (maybe) {
          this.selectedFile = maybe;
          if (maybe.type === 'story') {
            const sceneStore = useSceneStore();
            await sceneStore.loadStory(maybe.path);
          }
        } else {
          throw new Error(`文件未找到: ${filePath}`);
        }
      }
    },
    async createFile(type, parentDir = '', opts = {}) {
      console.log('[fileStore] createFile called:', { type, parentDir, opts });
      const projectStore = useProjectStore();
      console.log('[fileStore] Emitting prompt event...');
      const name = await new Promise((resolve) => {
        console.log('[fileStore] Creating promise with resolve');
        bus.emit('prompt', { title: `新建${type==='folder'?'文件夹':'文件'}`, message: `请输入新的${type === 'folder' ? '文件夹' : '文件'}名称：`, resolve, ...opts });
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
        } catch (error) {
          bus.emit('toast', { type: 'error', message: `创建失败: ${error.message}` });
        }
      }
    },
    async deleteSelectedFile(opts = {}) {
      if (!this.selectedFile) {
        bus.emit('toast', { type: 'error', message: '请先选择一个文件或文件夹' });
        return;
      }
      const ok = await new Promise((resolve) => bus.emit('confirm', { title: '删除', message: `确定要删除 "${this.selectedFile.name}" 吗？`, resolve, ...opts }));
      if (ok) {
        try {
          const projectStore = useProjectStore();
          await deleteFileOrFolder(projectStore.currentProject, this.selectedFile.path);
          this.selectedFile = null;
          this.selectedFiles = this.selectedFiles.filter(f => f.path !== this.selectedFile?.path);
          await this.loadFileTree(projectStore.currentProject);
        } catch (error) {
          bus.emit('toast', { type: 'error', message: `删除失败: ${error.message}` });
        }
      }
    },
    // 批量删除多选文件
    async deleteSelectedFiles(opts = {}) {
      if (this.selectedFiles.length === 0) {
        bus.emit('toast', { type: 'error', message: '请先选择要删除的文件或文件夹' });
        return;
      }
      const count = this.selectedFiles.length;
      const names = this.selectedFiles.map(f => f.name).join(', ');
      const ok = await new Promise((resolve) => bus.emit('confirm', { 
        title: '批量删除', 
        message: `确定要删除选中的 ${count} 个项目吗？\n${names}`, 
        resolve, 
        ...opts 
      }));
      if (ok) {
        const projectStore = useProjectStore();
        let successCount = 0;
        let failCount = 0;
        // 逐个删除
        for (const file of [...this.selectedFiles]) {
          try {
            await deleteFileOrFolder(projectStore.currentProject, file.path);
            successCount++;
          } catch (error) {
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
  async renameSelectedFile(opts = {}) {
      if (!this.selectedFile) {
        bus.emit('toast', { type: 'error', message: '请先选择一个文件或文件夹' });
        return;
      }
  const newName = await new Promise((resolve) => bus.emit('prompt', { title: '重命名', message: '请输入新的名称：', resolve, ...opts }));
      if (newName && newName !== this.selectedFile.name) {
        try {
          const projectStore = useProjectStore();
  // 计算新路径：仅替换路径末尾段（兼容 Windows 与 POSIX 分隔符）
  const rawPath = this.selectedFile.path || this.selectedFile.name;
  const segments = String(rawPath).split(/[\\/]+/);
          segments[segments.length - 1] = newName;
      const newPath = segments.join('/');
      await renameFileOrFolder(projectStore.currentProject, rawPath, newPath);
          // 刷新树并尝试选中新项
          await this.loadFileTree(projectStore.currentProject);
          this.selectedFile = findByPath(this.fileTree, newPath);
        } catch (error) {
          bus.emit('toast', { type: 'error', message: `重命名失败: ${error.message}` });
        }
      }
    },
  },
});

function findByPath(tree, path) {
  for (const item of tree) {
    if (item.path === path) return item;
    if (item.children) {
      const r = findByPath(item.children, path);
      if (r) return r;
    }
  }
  return null;
}

function findByNameInTree(tree, name) {
  const nn = String(name).replace(/^.*\//, '');
  for (const item of tree) {
    if (item.name === nn) return item;
    if (item.children) {
      const r = findByNameInTree(item.children, nn);
      if (r) return r;
    }
  }
  return null;
}

// 将文件树展平为一维数组（用于 Shift 范围选择）
export function flattenFileTree(tree) {
  const result = [];
  function walk(items) {
    for (const item of items) {
      result.push(item);
      if (item.children && item.children.length > 0) {
        walk(item.children);
      }
    }
  }
  walk(tree);
  return result;
}
