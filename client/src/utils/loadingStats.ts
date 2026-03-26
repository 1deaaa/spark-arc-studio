import bus from '@/eventBus';

/**
 * loadingStats.js — 全局加载统计引擎（GlobalLoading 遮罩的内部驱动层）
 *
 * 本模块是加载遮罩系统的核心计算引擎，负责维护生成任务的运行时状态
 * （字数统计、字速计算、思考计时、进度文字）并通过 event bus 驱动 GlobalLoading.vue 更新。
 *
 * 【层级关系】
 *   GlobalLoading.vue          ← 视图渲染层（只监听 bus 事件，不主动拉取数据）
 *         ↑
 *   loadingStats.js            ← 本文件：状态计算与事件发射层
 *         ↑
 *   streamingRuntime.js        ← 标准入口层（createStreamingTask 组装控制器并调用本模块）
 *         ↑
 *   业务调用方（AiPanel.vue、chatStore.js 等）
 *
 * ⚠️  不要绕过 streamingRuntime.js 直接使用本模块，以免绕过任务隔离、取消控制等机制。
 */

/**
 * 创建一次生成任务的全局加载统计器实例。
 *
 * 通常由 streamingRuntime.js 中的 `createStreamingTask` 在内部调用。
 * 业务方**不应直接调用本函数**——请统一从 `createStreamingTask` 接入，
 * 以确保同时拿到实例化的 AbortController、scope 隔离和任务生命周期管理。
 *
 * @param {string} scope  - 作用域隔离标识，如 'production', 'lorebook'。
 * @param {Object} options - 统计器行为配置。
 */
type StatsMode = 'output' | 'elapsed' | 'tool_elapsed';

type LoadingStatsOptions = {
  target?: string;
  text?: string;
  canCancel?: boolean;
  progress?: string;
  showStats?: boolean;
  statsMode?: StatsMode;
};

type StatsPayload = {
  chars?: number;
  total_chars?: number;
  elapsed?: number;
  speed?: number;
};

type ExtraPayload = Record<string, unknown>;

type GlobalLoadingStats = {
  start(nextText?: string, extra?: ExtraPayload): void;
  push(chunk?: string, nextText?: string, extra?: ExtraPayload): void;
  applyStats(stats?: StatsPayload, nextText?: string, extra?: ExtraPayload): void;
  setProgressText(progressText: string): void;
  hide(): void;
};

export function createGlobalLoadingStats(scope: string, options: LoadingStatsOptions = {}): GlobalLoadingStats {
  const {
    target = '',
    text = '正在创作中...',
    canCancel = false,
    progress: initialProgress = '',
    showStats = true,
    // 'output'：手动生成型任务，先显示思考时长，进入稳定输出后显示字数/速度
    // 'elapsed'：仅显示通用耗时
    // 'tool_elapsed'：工具调用型遮罩，显示“正在工作中 xx秒”，不显示速度
    statsMode = 'output',
  } = options;

  let currentProgress = initialProgress;  // mutable – updated by setProgressText()
  let currentEmitText = text;             // tracks latest text used in start/push
  let startedAt: number | null = null;
  let totalChars = 0;
  let hasStartedOutput = false;
  let thinkStartedAt: number | null = null;
  let thinkTimer: ReturnType<typeof setInterval> | null = null;

  const stopThinkTimer = () => {
    if (thinkTimer) {
      clearInterval(thinkTimer);
      thinkTimer = null;
    }
  };

  const emit = (nextText = currentEmitText, extra: ExtraPayload = {}) => {
    currentEmitText = nextText || currentEmitText;
    let statsLabel = '';
    let speed = 0;

    if (statsMode === 'tool_elapsed') {
      const totalElapsed = thinkStartedAt
        ? Math.floor((performance.now() - thinkStartedAt) / 1000)
        : 0;
      statsLabel = `正在工作中 ${totalElapsed}秒`;
    } else if (statsMode === 'elapsed') {
      const totalElapsed = thinkStartedAt
        ? Math.floor((performance.now() - thinkStartedAt) / 1000)
        : 0;
      statsLabel = `已用时 ${totalElapsed}秒`;
    } else if (hasStartedOutput && startedAt) {
      const elapsed = Math.max((performance.now() - startedAt) / 1000, 0.001);
      speed = Number((totalChars / elapsed).toFixed(2));
      statsLabel = `已撰写 ${totalChars} 字 · ${speed} 字/秒`;
    } else if (thinkStartedAt && !hasStartedOutput) {
      const thinkElapsed = Math.floor((performance.now() - thinkStartedAt) / 1000);
      statsLabel = `正在思考中... ${thinkElapsed}秒`;
    }

    const secondaryText = showStats ? statsLabel : '';

    bus.emit('global-loading', {
      ...extra,
      show: true,
      scope,
      target,
      text: currentEmitText,
      canCancel,
      progress: currentProgress,
      // 手动触发的生成任务拥有稳定的正文输出流，展示字数/速度能真实反映生成进度；
      // 工具调用型遮罩更多承担“锁定编辑区 + 告知正在执行哪个工具”的职责，
      // 很多工具执行阶段并没有持续正文流，若强行显示速度会制造伪精度并误导用户，
      // 因此这里允许调用方显式关闭 stats 展示。
      statsEnabled: showStats,
      secondaryText,
      secondaryVisible: !!secondaryText,
      secondaryMode: statsMode,
      statsChars: totalChars,
      statsSpeed: speed,
      statsLabel: statsLabel,
    });
  };

  return {
    start(nextText = text, extra: ExtraPayload = {}) {
      hasStartedOutput = false;
      startedAt = null;
      totalChars = 0;
      thinkStartedAt = performance.now();

      stopThinkTimer();
      thinkTimer = setInterval(() => {
        // elapsed 模式始终每秒更新计时器；output 模式在有输出后停止
        if (statsMode === 'elapsed' || !hasStartedOutput) {
          emit(currentEmitText, extra);
        } else {
          stopThinkTimer();
        }
      }, 1000);

      emit(nextText, extra);
    },
    push(chunk = '', nextText = text, extra: ExtraPayload = {}) {
      const chunkStr = String(chunk || '');
      if (chunkStr.length > 0 && !hasStartedOutput) {
        hasStartedOutput = true;
        startedAt = performance.now();
        stopThinkTimer();
      }
      totalChars += chunkStr.length;
      emit(nextText, extra);
    },
    applyStats(stats: StatsPayload = {}, nextText = text, extra: ExtraPayload = {}) {
      const chars = Number(stats.chars ?? stats.total_chars ?? totalChars ?? 0);
      totalChars = Number.isFinite(chars) ? chars : totalChars;

      if (!hasStartedOutput && totalChars > 0) {
        hasStartedOutput = true;
        const elapsedFallback = stats.elapsed || 0.001;
        startedAt = performance.now() - (elapsedFallback * 1000);
        stopThinkTimer();
      }

      let speed = 0;
      let statsLabel = '';

      if (statsMode === 'tool_elapsed') {
        const totalElapsed = thinkStartedAt
          ? Math.floor((performance.now() - thinkStartedAt) / 1000)
          : 0;
        statsLabel = `正在工作中 ${totalElapsed}秒`;
      } else if (statsMode === 'elapsed') {
        const totalElapsed = thinkStartedAt
          ? Math.floor((performance.now() - thinkStartedAt) / 1000)
          : 0;
        statsLabel = `已用时 ${totalElapsed}秒`;
      } else if (hasStartedOutput && startedAt) {
        const elapsed = Number(stats.elapsed ?? Math.max((performance.now() - startedAt) / 1000, 0.001));
        speed = Number(stats.speed ?? (totalChars / Math.max(elapsed, 0.001)));
        speed = Number(speed.toFixed(2));
        statsLabel = `已撰写 ${totalChars} 字 · ${speed} 字/秒`;
      } else if (thinkStartedAt && !hasStartedOutput) {
        const thinkElapsed = Math.floor((performance.now() - thinkStartedAt) / 1000);
        statsLabel = `正在思考中... ${thinkElapsed}秒`;
      }

      const secondaryText = showStats ? statsLabel : '';

      bus.emit('global-loading', {
        ...extra,
        show: true,
        scope,
        target,
        text: currentEmitText,
        canCancel,
        progress: currentProgress,
        statsEnabled: showStats,
        secondaryText,
        secondaryVisible: !!secondaryText,
        secondaryMode: statsMode,
        statsChars: totalChars,
        statsSpeed: speed,
        statsLabel: statsLabel,
      });
    },
    /** 更新进度副文本并立即重新发布 */
    setProgressText(progressText: string) {
      currentProgress = String(progressText || '');
      emit();
    },
    hide() {
      stopThinkTimer();
      bus.emit('global-loading', { show: false, scope, target });
    },
  };
}
