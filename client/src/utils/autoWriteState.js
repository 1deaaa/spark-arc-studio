function toIntegerOrNull(value) {
  return Number.isInteger(value) ? value : null;
}

export function collectOverwriteTargets(chapterFiles = [], startChapterIndex = 0) {
  const normalizedStart = Math.max(0, Number(startChapterIndex) || 0);
  return (chapterFiles || []).filter(item => item?.exists && Number(item.chapterIndex) >= normalizedStart);
}

export function buildAutoWriteResumeActions(state = {}, totalChapters = 0) {
  const actions = [];
  const status = String(state?.status || '').trim();
  const resumeIndex = toIntegerOrNull(state?.availableResumeChapterIndex);
  const restartIndex = toIntegerOrNull(state?.availableRestartChapterIndex);

  if (status === 'chapter_paused' && resumeIndex !== null && resumeIndex < totalChapters) {
    actions.push({
      key: 'resume-next',
      startChapterIndex: resumeIndex,
      label: `从第 ${resumeIndex + 1} 章继续`,
      intent: 'resume-next',
    });
  }

  if (['running', 'interrupted', 'error'].includes(status) && restartIndex !== null && restartIndex < totalChapters) {
    actions.push({
      key: 'restart-current',
      startChapterIndex: restartIndex,
      label: `从第 ${restartIndex + 1} 章重跑`,
      intent: 'restart-current',
    });
  }

  return actions;
}

export function describeAutoWriteState(state = {}) {
  const status = String(state?.status || '').trim();
  const currentChapterIndex = toIntegerOrNull(state?.currentChapterIndex);
  const lastCompletedChapterIndex = toIntegerOrNull(state?.lastCompletedChapterIndex);
  const currentChapterTitle = String(state?.currentChapterTitle || '').trim();
  const lastCompletedChapterTitle = String(state?.lastCompletedChapterTitle || '').trim();

  if (status === 'chapter_paused') {
    const label = lastCompletedChapterTitle || (lastCompletedChapterIndex !== null ? `第 ${lastCompletedChapterIndex + 1} 章` : '当前章节');
    return `上次运行已在 ${label} 完成后暂停。`;
  }

  if (status === 'interrupted') {
    const label = currentChapterTitle || (currentChapterIndex !== null ? `第 ${currentChapterIndex + 1} 章` : '当前章节');
    return `上次运行在 ${label} 中断，可从该章重跑。`;
  }

  if (status === 'error') {
    const label = currentChapterTitle || (currentChapterIndex !== null ? `第 ${currentChapterIndex + 1} 章` : '当前章节');
    return `上次运行在 ${label} 出错，可从该章重跑。`;
  }

  if (status === 'complete') {
    return '上次运行已完成。';
  }

  return '';
}