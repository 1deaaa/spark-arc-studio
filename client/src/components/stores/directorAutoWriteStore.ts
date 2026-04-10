/**
 * directorAutoWriteStore.ts
 *
 * 全局 Pinia Store — 导演触发 Auto-Write 任务的状态管理中心。
 *
 * 职责：
 * 1. 持有各项目的任务状态快照（轮询 /api/outline/{project}/auto-write-state 获取）
 * 2. 管理前端遮罩的显隐（基于 projectStore.currentProject）
 * 3. 提供 onDirectorStarted 入口供 chatStore 调用
 * 4. 提供 requestPause / forceStop 供遮罩组件调用
 *
 * 设计原则：
 * - 遮罩可见性绑定到「当前项目」：切换项目时遮罩自动消失（后台任务继续）
 * - 切换回来后，若该项目状态仍为 running，重新显示遮罩
 * - SSE 连接不做；改为轮询（30s），避免多余长连接冲突现有 modal 的 fetchEventSource
 */

import { defineStore } from 'pinia';
import { ref, computed, watch } from 'vue';
import { fetchWithAuth } from '@/services/apiClient';
import { useProjectStore } from '@/components/stores/projectStore';

export type AutoWriteStatus =
  | 'idle'
  | 'running'
  | 'chapter_paused'
  | 'interrupted'
  | 'complete'
  | 'error';

export interface AutoWriteSnapshot {
  status: AutoWriteStatus;
  mode: string;
  exportFormat: string;
  currentChapterIndex: number | null;
  currentChapterTitle: string;
  currentSceneIndex: number | null;
  currentSceneTitle: string;
  totalChapters?: number;    // 前端注册时从旁路事件得到
  totalScenes?: number;
  completedScenes?: number;
  lastCompletedChapterIndex?: number;
  lastSavedFilename: string;
  lastError: string;
  updatedAt: string;
  startedAt: string;
  generatedSceneFiles: string[];
}

interface DirectorAutoWriteTask {
  projectName: string;
  snapshot: AutoWriteSnapshot;
  /** 是否在当前会话由导演触发（区别于用户手动打开 Modal 触发） */
  fromDirector: boolean;
  /** 最近一次轮询的时间戳 */
  lastPolledAt: number;
}

const POLL_INTERVAL_MS = 5000; // 5 秒轮询一次

export const useDirectorAutoWriteStore = defineStore('directorAutoWrite', () => {
  /** 所有项目的任务记录，key = projectName */
  const tasks = ref<Record<string, DirectorAutoWriteTask>>({});

  /** 轮询定时器 handle */
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  // ──────────────────────────────────────────────
  // 计算属性
  // ──────────────────────────────────────────────

  /** 当前项目名（来自 projectStore，响应式） */
  const projectStore = useProjectStore();

  /** 当前项目的任务（可能为 undefined） */
  const currentTask = computed<DirectorAutoWriteTask | null>(
    () => (projectStore.currentProject ? tasks.value[projectStore.currentProject] ?? null : null),
  );

  /** 当前项目是否正在运行（遮罩可见性依据） */
  const isRunningForCurrentProject = computed<boolean>(
    () => currentTask.value?.snapshot.status === 'running'
      || currentTask.value?.snapshot.status === 'chapter_paused',
  );

  /** 所有活跃项目列表（status = running / chapter_paused） */
  const activeProjects = computed<string[]>(() =>
    Object.values(tasks.value)
      .filter(t => t.snapshot.status === 'running' || t.snapshot.status === 'chapter_paused')
      .map(t => t.projectName),
  );

  // ──────────────────────────────────────────────
  // 内部：轮询
  // ──────────────────────────────────────────────

  async function _pollSnapshot(projectName: string): Promise<void> {
    try {
      const task = tasks.value[projectName];
      const exportFormat = task?.snapshot.exportFormat || 'arc';
      const res = await fetchWithAuth(
        `/api/outline/${encodeURIComponent(projectName)}/auto-write-state?export_format=${encodeURIComponent(exportFormat)}`,
      );
      if (!res.ok) return;
      const data = await res.json();
      if (tasks.value[projectName]) {
        tasks.value[projectName].snapshot = {
          ...tasks.value[projectName].snapshot,
          ...data,
        };
        tasks.value[projectName].lastPolledAt = Date.now();
      }
    } catch {
      // 网络错误静默忽略，不中断轮询
    }
  }

  function _startPolling(): void {
    if (pollTimer !== null) return;
    pollTimer = setInterval(() => {
      for (const proj of activeProjects.value) {
        _pollSnapshot(proj);
      }
      // 若没有活跃任务，停止轮询
      if (activeProjects.value.length === 0) {
        _stopPolling();
      }
    }, POLL_INTERVAL_MS);
  }

  function _stopPolling(): void {
    if (pollTimer !== null) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  // ──────────────────────────────────────────────
  // 公开 API
  // ──────────────────────────────────────────────

  /**
   * 被 chatStore 调用 —— 导演刚刚触发了 Auto-Write。
   * 注册任务并立即拉取一次快照以同步初始状态。
   */
  function onDirectorStarted(payload: {
    project_name: string;
    start_chapter_index: number;
    mode: string;
    export_format: string;
    total_chapters: number;
    total_scenes: number;
  }): void {
    const { project_name, mode, export_format, total_chapters, total_scenes } = payload;
    tasks.value[project_name] = {
      projectName: project_name,
      fromDirector: true,
      lastPolledAt: Date.now(),
      snapshot: {
        status: 'running',
        mode,
        exportFormat: export_format,
        currentChapterIndex: null,
        currentChapterTitle: '',
        currentSceneIndex: null,
        currentSceneTitle: '',
        totalChapters: total_chapters,
        totalScenes: total_scenes,
        lastSavedFilename: '',
        lastError: '',
        updatedAt: new Date().toISOString(),
        startedAt: new Date().toISOString(),
        generatedSceneFiles: [],
      },
    };
    // 立即拉一次最新状态
    _pollSnapshot(project_name);
    _startPolling();
  }

  /**
   * 立即拉取指定项目的快照（切换回项目或 F5 刷新时调用）
   * 如果 Store 里不存在但服务器正在运行/暂停，会予以恢复重建。
   */
  async function refreshSnapshot(projectName: string): Promise<void> {
    try {
      const task = tasks.value[projectName];
      const exportFormat = task?.snapshot.exportFormat || 'arc';
      const res = await fetchWithAuth(
        `/api/outline/${encodeURIComponent(projectName)}/auto-write-state?export_format=${encodeURIComponent(exportFormat)}`,
      );
      if (!res.ok) return;
      const data = await res.json();
      
      // 如果 Store 里没有该项目记录
      if (!tasks.value[projectName]) {
        // idle 状态且毫无痕迹时静默，不予打扰
        if (data.status === 'idle') return;

        // 服务器有活跃进度或错误/完成等遗留状态，进行强行恢复
        tasks.value[projectName] = {
          projectName,
          fromDirector: data.status === 'running' || data.status === 'chapter_paused',
          lastPolledAt: Date.now(),
          snapshot: {
            status: 'idle',
            mode: 'continuous_write',
            exportFormat: exportFormat,
            currentChapterIndex: null,
            currentChapterTitle: '',
            currentSceneIndex: null,
            currentSceneTitle: '',
            totalScenes: data.totalScenes ?? 0,
            completedScenes: data.completedScenes ?? 0,
            lastSavedFilename: '',
            lastError: '',
            updatedAt: new Date().toISOString(),
            startedAt: new Date().toISOString(),
            generatedSceneFiles: [],
            ...data,
            // ensure totalChapters always correct (API legacy returns chapterCount)
            totalChapters: data.totalChapters || data.chapterCount || 0,
          }
        };
      } else {
        // 已有记录正常更新
        tasks.value[projectName].snapshot = {
          ...tasks.value[projectName].snapshot,
          ...data,
          // 确保 totalChapters 始终正确（API 旧版返回 chapterCount）
          totalChapters: data.totalChapters || data.chapterCount || tasks.value[projectName].snapshot.totalChapters || 0,
        };
        tasks.value[projectName].lastPolledAt = Date.now();
      }

      // 如果发现处于活跃态，启动轮询
      if (activeProjects.value.length > 0) {
        _startPolling();
      }
    } catch {
      // 容错处理
    }
  }

  /**
   * 请求暂停（发送中断信号到后端）
   */
  async function requestPause(projectName: string): Promise<void> {
    try {
      await fetchWithAuth(
        `/api/outline/${encodeURIComponent(projectName)}/auto-write-pause`,
        { method: 'POST' },
      );
      await refreshSnapshot(projectName);
    } catch {
      // 静默处理
    }
  }

  /**
   * 删除任务记录（用户明确关闭面板后）
   */
  function dismissTask(projectName: string): void {
    delete tasks.value[projectName];
    if (activeProjects.value.length === 0) {
      _stopPolling();
    }
  }

  // ──────────────────────────────────────────────
  // 监听项目切换，刷新快照
  // ──────────────────────────────────────────────
  watch(
    () => projectStore.currentProject,
    async (newProject) => {
      if (!newProject) return;
      // 切换回来时（或 F5 初始时），立即刷新快照，若有服务端进度自动恢复
      await refreshSnapshot(newProject);
    },
    { immediate: true }
  );

  return {
    tasks,
    currentTask,
    isRunningForCurrentProject,
    activeProjects,
    onDirectorStarted,
    refreshSnapshot,
    requestPause,
    dismissTask,
  };
});
