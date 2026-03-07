import bus from '@/eventBus';

export function createGlobalLoadingStats(scope, options = {}) {
  const {
    target = '',
    text = '正在创作中...',
    canCancel = false,
    progress = '',
  } = options;

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

  const emit = (nextText = text, extra = {}) => {
    let statsLabel = '正在思考中...';
    let speed = 0;

    if (hasStartedOutput && startedAt) {
      const elapsed = Math.max((performance.now() - startedAt) / 1000, 0.001);
      speed = Number((totalChars / elapsed).toFixed(2));
      statsLabel = `已撰写 ${totalChars} 字 · ${speed} 字/秒`;
    } else if (thinkStartedAt && !hasStartedOutput) {
      const thinkElapsed = Math.floor((performance.now() - thinkStartedAt) / 1000);
      statsLabel = `正在思考中... ${thinkElapsed}秒`;
    }

    bus.emit('global-loading', {
      show: true,
      scope,
      target,
      text: nextText,
      canCancel,
      progress,
      statsEnabled: true,
      statsChars: totalChars,
      statsSpeed: speed,
      statsLabel: statsLabel,
      ...extra,
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
        if (!hasStartedOutput) {
          emit(nextText, extra);
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
      let statsLabel = '正在思考中...';

      if (hasStartedOutput && startedAt) {
        const elapsed = Number(stats.elapsed ?? Math.max((performance.now() - startedAt) / 1000, 0.001));
        speed = Number(stats.speed ?? (totalChars / Math.max(elapsed, 0.001)));
        speed = Number(speed.toFixed(2));
        statsLabel = `已撰写 ${totalChars} 字 · ${speed} 字/秒`;
      } else if (thinkStartedAt && !hasStartedOutput) {
        const thinkElapsed = Math.floor((performance.now() - thinkStartedAt) / 1000);
        statsLabel = `正在思考中... (${thinkElapsed}秒)`;
      }

      bus.emit('global-loading', {
        show: true,
        scope,
        target,
        text: nextText,
        canCancel,
        progress,
        statsEnabled: true,
        statsChars: totalChars,
        statsSpeed: speed,
        statsLabel: statsLabel,
        ...extra,
      });
    },
    hide() {
      stopThinkTimer();
      bus.emit('global-loading', { show: false, scope, target });
    },
  };
}
