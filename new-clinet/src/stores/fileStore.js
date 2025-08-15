import { defineStore } from 'pinia';
import { fetchFileTree, createFileOrFolder, deleteFileOrFolder, renameFileOrFolder } from '@/services/api';
import { useProjectStore } from './projectStore';
import bus from '@/eventBus';

export const useFileStore = defineStore('file', {
  state: () => ({
    fileTree: [],
    selectedFile: null,
  }),
  actions: {
    async loadFileTree(projectName) {
      try {
        const files = await fetchFileTree(projectName);
        this.fileTree = files;
      } catch (error) {
        console.error('加载文件树失败:', error);
      }
    },
    async createFile(type, parentDir = '', opts = {}) {
      const projectStore = useProjectStore();
      const name = await new Promise((resolve) => bus.emit('prompt', { title: `新建${type==='folder'?'文件夹':'文件'}`, message: `请输入新的${type === 'folder' ? '文件夹' : '文件'}名称：`, resolve, ...opts }));
      if (name) {
        try {
          const target = parentDir ? `${parentDir.replace(/\/+$/,'').replace(/^\/+/, '')}/${name}` : name;
          await createFileOrFolder(projectStore.currentProject, type, target);
          await this.loadFileTree(projectStore.currentProject);
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
          await this.loadFileTree(projectStore.currentProject);
        } catch (error) {
          bus.emit('toast', { type: 'error', message: `删除失败: ${error.message}` });
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