import { i18n } from '@/i18n';

type AutoWriteState = {
  status?: string;
  availableResumeChapterIndex?: number | null;
  availableRestartChapterIndex?: number | null;
  currentChapterIndex?: number | null;
  lastCompletedChapterIndex?: number | null;
  currentChapterTitle?: string;
  lastCompletedChapterTitle?: string;
};

function toIntegerOrNull(value) {
  return Number.isInteger(value) ? value : null;
}

type ChapterFile = { chapterIndex?: number; filename?: string; exists?: boolean };

export function collectOverwriteTargets(chapterFiles: ChapterFile[] = [], startChapterIndex = 0) {
  const normalizedStart = Math.max(0, Number(startChapterIndex) || 0);
  return (chapterFiles || []).filter((item: ChapterFile) => item?.exists && Number(item.chapterIndex) >= normalizedStart);
}

export function buildAutoWriteResumeActions(state: AutoWriteState = {}, totalChapters = 0) {
  const actions: Array<{ key: string; startChapterIndex: number; label: string; intent: string }> = [];
  const status = String(state?.status || '').trim();
  const resumeIndex = toIntegerOrNull(state?.availableResumeChapterIndex);
  const restartIndex = toIntegerOrNull(state?.availableRestartChapterIndex);

  if (status === 'chapter_paused' && resumeIndex !== null && resumeIndex < totalChapters) {
    actions.push({
      key: 'resume-next',
      startChapterIndex: resumeIndex,
      label: i18n.global.t('utils.autoWriteState.resumeFromChapter', { chapter: resumeIndex + 1 }),
      intent: 'resume-next',
    });
  }

  if (['running', 'interrupted', 'error'].includes(status) && restartIndex !== null && restartIndex < totalChapters) {
    actions.push({
      key: 'restart-current',
      startChapterIndex: restartIndex,
      label: i18n.global.t('utils.autoWriteState.restartFromChapter', { chapter: restartIndex + 1 }),
      intent: 'restart-current',
    });
  }

  return actions;
}

export function describeAutoWriteState(state: AutoWriteState = {}) {
  const status = String(state?.status || '').trim();
  const currentChapterIndex = toIntegerOrNull(state?.currentChapterIndex);
  const lastCompletedChapterIndex = toIntegerOrNull(state?.lastCompletedChapterIndex);
  const currentChapterTitle = String(state?.currentChapterTitle || '').trim();
  const lastCompletedChapterTitle = String(state?.lastCompletedChapterTitle || '').trim();

  if (status === 'chapter_paused') {
    const label = lastCompletedChapterTitle || (lastCompletedChapterIndex !== null ? i18n.global.t('utils.autoWriteState.chapterN', { n: lastCompletedChapterIndex + 1 }) : i18n.global.t('utils.autoWriteState.currentChapter'));
    return i18n.global.t('utils.autoWriteState.pausedAfter', { label });
  }

  if (status === 'interrupted') {
    const label = currentChapterTitle || (currentChapterIndex !== null ? i18n.global.t('utils.autoWriteState.chapterN', { n: currentChapterIndex + 1 }) : i18n.global.t('utils.autoWriteState.currentChapter'));
    return i18n.global.t('utils.autoWriteState.interruptedAt', { label });
  }

  if (status === 'error') {
    const label = currentChapterTitle || (currentChapterIndex !== null ? i18n.global.t('utils.autoWriteState.chapterN', { n: currentChapterIndex + 1 }) : i18n.global.t('utils.autoWriteState.currentChapter'));
    return i18n.global.t('utils.autoWriteState.errorAt', { label });
  }

  if (status === 'complete') {
    return i18n.global.t('utils.autoWriteState.completed');
  }

  return '';
}