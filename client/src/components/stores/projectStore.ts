import bus from '@/eventBus';
import { defineStore } from 'pinia';
import { fetchProjects, createProject, deleteProject } from '@/services/api';
import { useFileStore } from './fileStore';
import { useCharacterStore } from './characterStore';
import { useChatStore } from './chatStore';
import { useSceneStore } from './sceneStore';
import { useBlueprintStore } from './blueprintStore';

const LAST_PROJECT_KEY = 'sparkarc_last_project';

type PendingSynopsisAdoption = {
  projectName?: string;
  logline?: string;
  inspiration?: string;
  lengthHint?: unknown;
  [key: string]: unknown;
};

type ProjectStoreState = {
  projects: string[];
  _currentProject: string | null;
  currentInspiration: string;
  currentInspirationId: string | null;
  pendingSynopsisAdoption: PendingSynopsisAdoption | null;
};

export const useProjectStore = defineStore('project', {
  state: (): ProjectStoreState => ({
    projects: [],
    _currentProject: null,
    currentInspiration: '', // 当前灵感，供大纲页面使用
    currentInspirationId: null,
    pendingSynopsisAdoption: null,
  }),
  getters: {
    currentProject: (state): string => state._currentProject || '',
  },
  actions: {
    async loadProjects() {
      try {
        let projects = await fetchProjects();
        // 过滤掉无效的项目名称，以防意外创建
        projects = projects.filter((p) => {
          if (typeof p !== 'string') return false;
          const normalized = p.trim();
          return normalized && normalized !== 'undefined' && normalized !== 'null';
        });
        this.projects = projects;
        if (Array.isArray(projects) && projects.length > 0) {
          // 优先恢复上次缓存的项目（直接访问不带 URL 锁定时）
          const lastProject = localStorage.getItem(LAST_PROJECT_KEY);
          if (lastProject && projects.includes(lastProject)) {
            if (this._currentProject !== lastProject) {
              this.setCurrentProject(lastProject);
            }
          } else if (!this._currentProject || !projects.includes(this._currentProject)) {
            // 当前未选择或选择的项目不再存在时，选择第一个项目
            this.setCurrentProject(projects[0]);
          }
        } else {
          // 无项目时清空当前项目
          this.setCurrentProject(null);
        }
      } catch (error: unknown) {
        console.error('加载项目失败:', error);
      }
    },
    setCurrentProject(projectName: string | string[] | null | undefined) {
      // 纠正误传数组的情况，取第一个作为当前项目
      if (Array.isArray(projectName)) {
        projectName = projectName[0] ?? null;
      }

      // 如果传入既不是字符串也不是 null/undefined，直接忽略
      if (projectName !== null && projectName !== undefined && typeof projectName !== 'string') {
        console.warn('非法的项目名称，已忽略:', projectName);
        return;
      }

      const normalizedProjectName = typeof projectName === 'string' ? projectName.trim() : projectName;
      const safeProjectName = !normalizedProjectName || normalizedProjectName === 'undefined' || normalizedProjectName === 'null'
        ? null
        : normalizedProjectName;

      // 避免重复设置触发不必要的加载
      if (this._currentProject === safeProjectName) return;

      this._currentProject = safeProjectName;

      // 缓存最后切换的项目，下次访问时自动恢复
      if (safeProjectName) {
        localStorage.setItem(LAST_PROJECT_KEY, safeProjectName);
      } else {
        localStorage.removeItem(LAST_PROJECT_KEY);
      }

      // 项目切换时清空聊天历史缓存，避免显示旧项目的记录
      const chatStore = useChatStore();
      chatStore.resetAllSessions();

      // 清空剧本编辑器，避免残留旧项目的场景数据
      const sceneStore = useSceneStore();
      sceneStore.scriptData = sceneStore.workspaceMode === 'novel' ? '' : [];
      sceneStore.currentFilePath = null;
      sceneStore.currentScene = null;
      sceneStore.currentNode = null;
      sceneStore.nodeParent = null;
      sceneStore.selectionType = sceneStore.workspaceMode === 'novel' ? 'novel' : '';
      sceneStore.lastScriptwriterThought = '';

      // 清空灵感数据
      this.currentInspiration = '';
      this.currentInspirationId = null;

      const fileStore = useFileStore();
      const chrStore = useCharacterStore();
      const blueprintStore = useBlueprintStore();
      if (this._currentProject) {
        fileStore.loadFileTree(this._currentProject, fileStore.activeFormatFilter);
        chrStore.load(this._currentProject);
        blueprintStore.loadBlueprint(this._currentProject);
      } else {
        // 没有项目时清空文件树和蓝图
        fileStore.fileTree = [];
        fileStore.selectedFile = null;
        chrStore.load(null);
        blueprintStore.loadBlueprint(null);
      }
    },
    async createProject() {
      const projectName = await new Promise<unknown>((resolve) => bus.emit('prompt', { title: '新建项目', message: '请输入项目名称：', resolve }));
      const finalName = typeof projectName === 'string' ? projectName.trim() : '';
      if (finalName && finalName !== 'undefined' && finalName !== 'null') {
        try {
          await createProject(finalName);
          await this.loadProjects();
          // 创建成功后切换到新项目
          this.setCurrentProject(finalName);
          return finalName;
        } catch (error: unknown) {
          const errorMessage = error instanceof Error ? error.message : String(error || '未知错误');
          bus.emit('toast', { type: 'error', message: `创建项目失败: ${errorMessage}` });
          return null;
        }
      } else if (projectName !== null) { // 如果不是用户取消，而是输入了无效名称
        bus.emit('toast', { type: 'error', message: '无效的项目名称' });
      }
      return null;
    },
    async deleteCurrentProject() {
      // n-popconfirm 已提供二次确认（含数据丢失警告）
      if (!this.currentProject) {
        bus.emit('toast', { type: 'error', message: '没有选中的项目' });
        return;
      }
      try {
        await deleteProject(this.currentProject);
        await this.loadProjects(); // 重新加载项目列表
        // 删除后，自动选择第一个项目或置空
        this.setCurrentProject(this.projects[0] ?? null);
        bus.emit('toast', { type: 'success', message: '项目已删除' });
      } catch (error: unknown) {
        const errorMessage = error instanceof Error ? error.message : String(error || '未知错误');
        bus.emit('toast', { type: 'error', message: `删除项目失败: ${errorMessage}` });
      }
    },
    setPendingSynopsisAdoption(payload: PendingSynopsisAdoption | null | undefined) {
      this.pendingSynopsisAdoption = payload || null;
    },
    clearPendingSynopsisAdoption() {
      this.pendingSynopsisAdoption = null;
    },
  },
});
