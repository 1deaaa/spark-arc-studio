import bus from '@/eventBus';

export function createGlobalLoadingStats(scope, options = {}) {
  const {
    target = '',
    text = '正在创作中...',
    canCancel = false,
    progress: initialProgress = '',
    statsMode = 'output',   // 'output'(字/秒) | 'elapsed'(已用时)
  } = options;

  let currentProgress = initialProgress;  // mutable – updated by setProgressText()
  let currentEmitText = text;             // tracks latest text used in start/push
  let startedAt = null;
  let totalChars = 0;
  let hasStartedOutput = false;
  let thinkStartedAt = null;
  let thinkTimer = null;

  const stopThinkTimer = () => {
    if (thinkTimer) {
      clearInterval(thinkTimer);
      thinkTimer = null;
    }
  };

  const emit = (nextText = currentEmitText, extra = {}) => {
    currentEmitText = nextText || currentEmitText;
    let statsLabel = '';
    let speed = 0;

    if (statsMode === 'elapsed') {
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

    bus.emit('global-loading', {
      ...extra,
      show: true,
      scope,
      target,
      text: currentEmitText,
      canCancel,
      progress: currentProgress,
      statsEnabled: true,
      statsChars: totalChars,
      statsSpeed: speed,
      statsLabel: statsLabel,
    });
  };

  return {
    start(nextText = text, extra = {}) {
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
    push(chunk = '', nextText = text, extra = {}) {
      const chunkStr = String(chunk || '');
      if (chunkStr.length > 0 && !hasStartedOutput) {
        hasStartedOutput = true;
        startedAt = performance.now();
        stopThinkTimer();
      }
      totalChars += chunkStr.length;
      emit(nextText, extra);
    },
    applyStats(stats = {}, nextText = text, extra = {}) {
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

      if (statsMode === 'elapsed') {
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

      bus.emit('global-loading', {
        ...extra,
        show: true,
        scope,
        target,
        text: currentEmitText,
        canCancel,
        progress: currentProgress,
        statsEnabled: true,
        statsChars: totalChars,
        statsSpeed: speed,
        statsLabel: statsLabel,
      });
    },
    /** 更新进度副文本并立即重新发布 */
    setProgressText(progressText) {
      currentProgress = String(progressText || '');
      emit();
    },
    hide() {
      stopThinkTimer();
      bus.emit('global-loading', { show: false, scope, target });
    },
  };
}