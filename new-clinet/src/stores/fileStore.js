import { defineStore } from 'pinia';
import { fetchFileTree, createFileOrFolder, deleteFileOrFolder, renameFileOrFolder } from '@/services/api';
import { useProjectStore } from './projectStore';

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
    async createFile(type) {
      const projectStore = useProjectStore();
      const name = prompt(`请输入新的${type === 'folder' ? '文件夹' : '文件'}名称:`);
      if (name) {
        try {
          await createFileOrFolder(projectStore.currentProject, type, name);
          await this.loadFileTree(projectStore.currentProject);
        } catch (error) {
          alert(`创建失败: ${error.message}`);
        }
      }
    },
    async deleteSelectedFile() {
      if (!this.selectedFile) {
        alert('请先选择一个文件或文件夹');
        return;
      }
      if (confirm(`确定要删除 "${this.selectedFile.name}" 吗？`)) {
        try {
          const projectStore = useProjectStore();
          await deleteFileOrFolder(projectStore.currentProject, this.selectedFile.path);
          this.selectedFile = null;
          await this.loadFileTree(projectStore.currentProject);
        } catch (error) {
          alert(`删除失败: ${error.message}`);
        }
      }
    },
    async renameSelectedFile() {
      if (!this.selectedFile) {
        alert('请先选择一个文件或文件夹');
        return;
      }
    const newName = prompt('请输入新的名称:', this.selectedFile.name);
      if (newName && newName !== this.selectedFile.name) {
        try {
          const projectStore = useProjectStore();
      // 计算新路径：仅替换路径末尾段（兼容 / 与 \\\ 分隔符）
      const rawPath = this.selectedFile.path || this.selectedFile.name;
      const segments = rawPath.split(/\\\\|\//);
          segments[segments.length - 1] = newName;
      const newPath = segments.join('/');
      await renameFileOrFolder(projectStore.currentProject, rawPath, newPath);
          // 刷新树并尝试选中新项
          await this.loadFileTree(projectStore.currentProject);
          this.selectedFile = findByPath(this.fileTree, newPath);
        } catch (error) {
          alert(`重命名失败: ${error.message}`);
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