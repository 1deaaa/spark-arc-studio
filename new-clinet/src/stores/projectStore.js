import bus from '@/eventBus';
import { defineStore } from 'pinia';
import { fetchProjects, createProject, deleteProject } from '@/services/api';
import { useFileStore } from './fileStore';

export const useProjectStore = defineStore('project', {
  state: () => ({
    projects: [],
    _currentProject: null,
  }),
  getters: {
    currentProject: (state) => state._currentProject,
  },
  actions: {
    async loadProjects() {
      try {
        const projects = await fetchProjects();
        this.projects = projects;
        // 仅在当前未选择或选择的项目不再存在时，选择第一个项目
        if (Array.isArray(projects) && projects.length > 0) {
          if (!this._currentProject || !projects.includes(this._currentProject)) {
            this.setCurrentProject(projects[0]);
          }
        } else {
          // 无项目时清空当前项目
          this.setCurrentProject(null);
        }
      } catch (error) {
        console.error('加载项目失败:', error);
      }
    },
    setCurrentProject(projectName) {
      // 纠正误传数组的情况，取第一个作为当前项目
      if (Array.isArray(projectName)) {
        projectName = projectName[0] ?? null;
      }

      // 如果传入既不是字符串也不是 null/undefined，直接忽略
      if (projectName !== null && projectName !== undefined && typeof projectName !== 'string') {
        console.warn('非法的项目名称，已忽略:', projectName);
        return;
      }

      // 避免重复设置触发不必要的加载
      if (this._currentProject === projectName) return;

      this._currentProject = projectName || null;

      const fileStore = useFileStore();
      if (this._currentProject) {
        fileStore.loadFileTree(this._currentProject);
      } else {
        // 没有项目时清空文件树
        fileStore.fileTree = [];
        fileStore.selectedFile = null;
      }
    },
    async createProject() {
      const projectName = await new Promise((resolve) => bus.emit('prompt', { title: '新建项目', message: '请输入项目名称：', resolve }));
      if (projectName) {
        try {
          await createProject(projectName);
          await this.loadProjects();
          // 创建成功后切换到新项目
          this.setCurrentProject(projectName);
        } catch (error) {
          bus.emit('toast', { type: 'error', message: `创建项目失败: ${error.message}` });
        }
      }
    },
    async deleteCurrentProject() {
      if (!this.currentProject) {
        bus.emit('toast', { type: 'error', message: '没有选中的项目' });
        return;
      }
      const ok = await new Promise((resolve) => bus.emit('confirm', { title: '删除项目', message: `确定要删除项目 "${this.currentProject}" 吗？此操作不可撤销！`, resolve }));
      if (ok) {
        try {
          await deleteProject(this.currentProject);
          await this.loadProjects(); // 重新加载项目列表
          // 删除后，自动选择第一个项目或置空
          this.setCurrentProject(this.projects[0] ?? null);
        } catch (error) {
          bus.emit('toast', { type: 'error', message: `删除项目失败: ${error.message}` });
        }
      }
    },
  },
});