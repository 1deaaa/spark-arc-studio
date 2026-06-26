/**
 * directorAutoWriteStore.ts
 *
 * 全局 Pinia Store — Auto-Write 任务的状态管理中心（导演触发 + 手动触发统一收口）。
 *
 * 职责：
 * 1. 持有各项目的任务状态快照（轮询 /api/outline/{project}/auto-write-state 获取）
 * 2. 管理前端遮罩的显隐（基于 projectStore.currentProject）
 * 3. 提供 onDirectorStarted 入口供 chatStore 调用
 * 4. 提供 startManualWrite 入口供手动触发（后台线程执行，不受前端断连影响）
 * 5. 提供 requestPause / dismissTask 供遮罩组件调用
 *
 * 设计原则：
 * - 遮罩可见性绑定到「当前项目」：切换项目时遮罩自动消失（后台任务继续）
 * - 切换回来后，若该项目状态仍为 running，重新显示遮罩
 * - 导演触发：轮询模式（工具调用不支持流式）
 * - 手动触发：SSE 观察者模式（实时文字流）+ 轮询兜底
 */

import { defineStore } from 'pinia';
import { ref, computed, watch } from 'vue';
import { fetchWithAuth, resolveApiUrl, getSessionToken } from '@/services/apiClient';
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
  nextChapterIndex?: number;
  availableResumeChapterIndex?: number | null;
  availableResumeSceneIndex?: number | null;
  lastSavedFilename: string;
  lastError: string;
  updatedAt: string;
  startedAt: string;
  generatedSceneFiles: string[];
  // 实时流式统计（手动触发时由 SSE 观察者更新，导演触发时由轮询更新）
  streamingPreview: string;
  streamingSpeed: number;
  streamingChars: number;
  streamingElapsed: number;
  autoReviewEnabled?: boolean;
  lastReviewDecision?: string;
  lastReviewGrade?: string;
  lastReviewTarget?: string;
  lastReviewTicketCount?: number;
  lastReviewError?: string;
  /** 用户是否已确认该状态（关闭遮罩/手动中断后为 true，下次不再弹出） */
  acknowledged?: boolean;
}

interface DirectorAutoWriteTask {
  projectName: string;
  snapshot: AutoWriteSnapshot;
  /** 是否在当前会话由导演触发（区别于用户手动触发） */
  fromDirector: boolean;
  /** 最近一次轮询的时间戳 */
  lastPolledAt: number;
  /** SSE 观察者连接是否活跃 */
  sseConnected: boolean;
}

  const POLL_INTERVAL_MS = 5000; // 5 秒轮询一次

  /**
   * 导演触发后的"启动宽限期"：后端后台线程从启动到落盘 running 状态存在延迟，
   * 在此期间轮询可能返回 idle，会用旧状态覆盖前端乐观设置的 running，导致遮罩闪退。
   * 宽限期内若轮询返回 idle，保留前端的 running 不降级。
   */
  const DIRECTOR_STARTUP_GRACE_MS = 3000;
  /** 记录每个项目最近一次导演触发的时间戳，用于宽限期判定 */
  const directorStartedAtMap: Record<string, number> = {};

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
      const res = await fetchWithAuth(
        `/api/outline/${encodeURIComponent(projectName)}/auto-write-state`,
      );
      if (!res.ok) return;
      const data = await res.json();
      if (tasks.value[projectName]) {
        // 启动宽限期 + running 不降级保护：
        // 导演刚触发后，后端后台线程落盘 running 状态存在延迟，此时轮询可能返回 idle。
        // 若放任 idle 覆盖前端乐观设置的 running，遮罩会瞬间消失（"需要切换项目才弹出"的根因）。
        // 对策：宽限期内或 local 仍为 running 而 remote 为 idle 时，保留 local 的 running 状态，
        //       仅合并非 status 字段；待后端真正进入 running/complete/error 后再正常同步。
        const localStatus = tasks.value[projectName].snapshot.status;
        const remoteStatus = data?.status;
        const startedAt = directorStartedAtMap[projectName] || 0;
        const inGrace = startedAt > 0 && (Date.now() - startedAt) < DIRECTOR_STARTUP_GRACE_MS;
        if (
          (inGrace || localStatus === 'running')
          && remoteStatus === 'idle'
        ) {
          const { status: _dropped, ...safeData } = data;
          tasks.value[projectName].snapshot = {
            ...tasks.value[projectName].snapshot,
            ...safeData,
          };
        } else {
          tasks.value[projectName].snapshot = {
            ...tasks.value[projectName].snapshot,
            ...data,
          };
          // 后端已进入非 idle 的稳定态，清除宽限期标记
          if (remoteStatus && remoteStatus !== 'idle' && remoteStatus !== 'running') {
            delete directorStartedAtMap[projectName];
          }
        }
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
    start_scene_index?: number;
    mode: string;
    export_format: string;
    auto_review?: boolean;
    total_chapters: number;
    total_scenes: number;
  }): void {
    const { project_name, mode, export_format, auto_review, total_chapters, total_scenes } = payload;
    tasks.value[project_name] = {
      projectName: project_name,
      fromDirector: true,
      lastPolledAt: Date.now(),
      sseConnected: false,
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
        availableResumeChapterIndex: payload.start_chapter_index,
        availableResumeSceneIndex: payload.start_scene_index ?? 0,
        lastSavedFilename: '',
        lastError: '',
        updatedAt: new Date().toISOString(),
        startedAt: new Date().toISOString(),
        generatedSceneFiles: [],
        streamingPreview: '',
        streamingSpeed: 0,
        streamingChars: 0,
        streamingElapsed: 0,
        autoReviewEnabled: auto_review === true,
      },
    };
    // 记录启动时间戳，供轮询宽限期判定使用
    directorStartedAtMap[project_name] = Date.now();
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
      const res = await fetchWithAuth(
        `/api/outline/${encodeURIComponent(projectName)}/auto-write-state`,
      );
      if (!res.ok) return;
      const data = await res.json();
      
      // 如果 Store 里没有该项目记录
      if (!tasks.value[projectName]) {
        // idle 状态且毫无痕迹时静默，不予打扰
        if (data.status === 'idle') return;

        // 已确认的遗留状态（用户已关闭遮罩或手动中断），不再弹出。
        // 但 running 是后台仍在写作的强锁定态，刷新/重登后必须恢复遮罩。
        if (data.acknowledged && data.status !== 'running') return;

        // 服务器有活跃进度或错误/完成等遗留状态，进行强行恢复
        const isManual = data.status === 'running' && !data.fromDirector;
        tasks.value[projectName] = {
          projectName,
          fromDirector: data.status === 'running' || data.status === 'chapter_paused' ? !isManual : false,
          lastPolledAt: Date.now(),
          sseConnected: false,
          snapshot: {
            status: 'idle',
            mode: 'continuous_write',
            exportFormat: data.exportFormat || data.export_format || 'arc',
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
            streamingPreview: '',
            streamingSpeed: 0,
            streamingChars: 0,
            streamingElapsed: 0,
            ...data,
            // ensure totalChapters always correct (API legacy returns chapterCount)
            totalChapters: data.totalChapters || data.chapterCount || 0,
          }
        };

        // 如果是手动触发的活跃任务，重连 SSE 观察者
        if (data.status === 'running' && !tasks.value[projectName].fromDirector) {
          _connectProgressSSE(projectName);
        }
      } else {
        // 已有记录正常更新（同样施加 running 不降级保护，避免切换项目回来时被旧 idle 覆盖）
        const localStatus = tasks.value[projectName].snapshot.status;
        const remoteStatus = data?.status;
        const startedAt = directorStartedAtMap[projectName] || 0;
        const inGrace = startedAt > 0 && (Date.now() - startedAt) < DIRECTOR_STARTUP_GRACE_MS;
        if (
          (inGrace || localStatus === 'running')
          && remoteStatus === 'idle'
        ) {
          const { status: _dropped, ...safeData } = data;
          tasks.value[projectName].snapshot = {
            ...tasks.value[projectName].snapshot,
            ...safeData,
            totalChapters: data.totalChapters || data.chapterCount || tasks.value[projectName].snapshot.totalChapters || 0,
          };
        } else {
          tasks.value[projectName].snapshot = {
            ...tasks.value[projectName].snapshot,
            ...data,
            // 确保 totalChapters 始终正确（API 旧版返回 chapterCount）
            totalChapters: data.totalChapters || data.chapterCount || tasks.value[projectName].snapshot.totalChapters || 0,
          };
          if (remoteStatus && remoteStatus !== 'idle' && remoteStatus !== 'running') {
            delete directorStartedAtMap[projectName];
          }
        }
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
   * 删除任务记录（用户明确关闭面板后），同时通知后端标记 acknowledged
   */
  async function dismissTask(projectName: string): Promise<void> {
    _disconnectProgressSSE(projectName);
    delete directorStartedAtMap[projectName];
    delete tasks.value[projectName];
    if (activeProjects.value.length === 0) {
      _stopPolling();
    }
    // 通知后端标记 acknowledged=True，下次不再弹出
    try {
      await fetchWithAuth(
        `/api/outline/${encodeURIComponent(projectName)}/auto-write-acknowledge`,
        { method: 'POST' },
      );
    } catch {
      // 网络错误静默忽略
    }
  }

  // ──────────────────────────────────────────────
  // 手动触发（后台线程 + SSE 观察者）
  // ──────────────────────────────────────────────

  /** SSE 观察者的 AbortController，按 projectName 存储 */
  const _sseControllers: Record<string, AbortController> = {};

  /**
   * 手动触发 Auto-Write：调用后端 /auto-write-start 启动后台线程，
   * 然后连接 SSE 观察者获取实时进度。
   */
  async function startManualWrite(
    projectName: string,
    config: {
      mode?: string;
      startChapterIndex?: number;
      startSceneIndex?: number;
      autoReview?: boolean;
    } = {},
  ): Promise<{ success: boolean; error?: string }> {
    const mode = config.mode || 'chapter_by_chapter';
    const startChapterIndex = config.startChapterIndex ?? 0;
    const startSceneIndex = config.startSceneIndex ?? 0;
    const autoReview = config.autoReview === true;
    let exportFormat = 'arc';

    try {
      const res = await fetchWithAuth(
        `/api/outline/${encodeURIComponent(projectName)}/auto-write-start`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            mode,
            start_chapter_index: startChapterIndex,
            start_scene_index: startSceneIndex,
            auto_review: autoReview,
          }),
        },
      );
      const data = await res.json();
      if (!data.success) {
        return { success: false, error: data.error || '启动失败' };
      }
      exportFormat = data.export_format || data.exportFormat || exportFormat;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e || '网络错误');
      return { success: false, error: msg };
    }

    // 注册任务（fromDirector = false，表示手动触发）
    tasks.value[projectName] = {
      projectName,
      fromDirector: false,
      lastPolledAt: Date.now(),
      sseConnected: false,
      snapshot: {
        status: 'running',
        mode,
        exportFormat,
        currentChapterIndex: null,
        currentChapterTitle: '',
        currentSceneIndex: null,
        currentSceneTitle: '',
        lastSavedFilename: '',
        lastError: '',
        updatedAt: new Date().toISOString(),
        startedAt: new Date().toISOString(),
        generatedSceneFiles: [],
        streamingPreview: '',
        streamingSpeed: 0,
        streamingChars: 0,
        streamingElapsed: 0,
        autoReviewEnabled: autoReview,
      },
    };

    // 连接 SSE 观察者获取实时进度
    _connectProgressSSE(projectName);
    // 同时启动轮询作为兜底
    _startPolling();
    // 立即拉一次状态
    _pollSnapshot(projectName);

    return { success: true };
  }

  /**
   * 连接 SSE 观察者端点，实时接收后台线程推送的进度事件。
   * 前端断连后任务不受影响，重连后可重新调用此方法恢复实时流。
   */
  function _connectProgressSSE(projectName: string): void {
    // 先断开已有连接
    _disconnectProgressSSE(projectName);

    const controller = new AbortController();
    _sseControllers[projectName] = controller;

    const url = resolveApiUrl(
      `/api/outline/${encodeURIComponent(projectName)}/auto-write-progress-stream`,
    );

    // 使用 fetch + ReadableStream 手动解析 SSE
    const headers: Record<string, string> = { Accept: 'text/event-stream' };
    const token = getSessionToken();
    if (token) headers['X-Session-Token'] = token;

    fetch(url, {
      headers,
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok || !response.body) {
          return;
        }
        const task = tasks.value[projectName];
        if (task) task.sseConnected = true;

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function read(): Promise<void> {
          return reader.read().then(({ done, value }) => {
            if (done) {
              const t = tasks.value[projectName];
              if (t) t.sseConnected = false;
              return;
            }
            buffer += decoder.decode(value, { stream: true });
            // 解析 SSE 事件
            const lines = buffer.split('\n');
            // 保留最后一行（可能不完整）
            buffer = lines.pop() || '';

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  _handleProgressEvent(projectName, data);
                } catch {
                  // 解析失败静默忽略
                }
              }
              // 忽略 heartbeat（: heartbeat）和其他注释行
            }

            return read();
          });
        }

        return read();
      })
      .catch(() => {
        const t = tasks.value[projectName];
        if (t) t.sseConnected = false;
        // SSE 断连后回退到轮询模式，轮询已在 _startPolling 中运行
      });
  }

  /**
   * 断开指定项目的 SSE 观察者连接
   */
  function _disconnectProgressSSE(projectName: string): void {
    const controller = _sseControllers[projectName];
    if (controller) {
      controller.abort();
      delete _sseControllers[projectName];
    }
    const task = tasks.value[projectName];
    if (task) task.sseConnected = false;
  }

  /**
   * 处理 SSE 观察者推送的进度事件，更新 store 中的实时统计字段
   */
  function _handleProgressEvent(projectName: string, data: Record<string, unknown>): void {
    const task = tasks.value[projectName];
    if (!task) return;

    const snap = task.snapshot;

    // 状态事件
    if (data.status === 'started') {
      snap.status = 'running';
    } else if (data.status === 'chapter_start') {
      snap.currentChapterIndex = (data.chapter_index as number) ?? snap.currentChapterIndex;
      snap.currentChapterTitle = (data.chapter_title as string) ?? snap.currentChapterTitle;
    } else if (data.status === 'writing_scene') {
      snap.currentSceneIndex = (data.scene_index as number) ?? snap.currentSceneIndex;
      snap.currentSceneTitle = (data.scene_title as string) ?? snap.currentSceneTitle;
      snap.streamingPreview = '';
    } else if (data.status === 'streaming') {
      // 实时文字流！这是手动触发独有的体验
      snap.streamingPreview = (data.preview as string) ?? snap.streamingPreview;
      snap.streamingSpeed = (data.speed as number) ?? snap.streamingSpeed;
      snap.streamingChars = (data.total_chars as number) ?? snap.streamingChars;
      snap.streamingElapsed = (data.elapsed as number) ?? snap.streamingElapsed;
    } else if (data.status === 'scene_completed') {
      snap.streamingPreview = '';
    } else if (data.status === 'scene_saved') {
      snap.lastSavedFilename = (data.filename as string) ?? snap.lastSavedFilename;
      // 后端 SSE 事件携带精确的 completedScenes / totalScenes，实时更新进度条
      if (data.completedScenes != null) snap.completedScenes = data.completedScenes as number;
      if (data.totalScenes != null) snap.totalScenes = data.totalScenes as number;
    } else if (data.status === 'chapter_saved') {
      // 章节完成
    } else if (data.status === 'paused') {
      snap.status = 'chapter_paused';
      snap.nextChapterIndex = (data.next_chapter_index as number) ?? snap.nextChapterIndex;
    } else if (data.status === 'complete') {
      snap.status = 'complete';
      // 完成时强制进度条到顶
      if (data.totalScenes != null) {
        snap.totalScenes = data.totalScenes as number;
        snap.completedScenes = data.totalScenes as number;
      } else if (snap.totalScenes) {
        snap.completedScenes = snap.totalScenes;
      }
    } else if (data.status === 'error') {
      snap.status = 'error';
      snap.lastError = (data.message as string) ?? snap.lastError;
    } else if (data.status === 'cancelled') {
      snap.status = 'interrupted';
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
    startManualWrite,
    refreshSnapshot,
    requestPause,
    dismissTask,
  };
});
