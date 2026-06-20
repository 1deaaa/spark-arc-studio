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
type SceneFile = { chapterIndex?: number; sceneIndex?: number; filename?: string; exists?: boolean };

export function collectOverwriteTargets(chapterFiles: ChapterFile[] = [], startChapterIndex = 0) {
  const normalizedStart = Math.max(0, Number(startChapterIndex) || 0);
  return (chapterFiles || []).filter((item: ChapterFile) => item?.exists && Number(item.chapterIndex) >= normalizedStart);
}

export function collectSceneOverwriteTargets(
  sceneFiles: SceneFile[] = [],
  startChapterIndex = 0,
  startSceneIndex = 0,
  endChapterIndex: number | null = null,
) {
  const normalizedChapter = Math.max(0, Number(startChapterIndex) || 0);
  const normalizedScene = Math.max(0, Number(startSceneIndex) || 0);
  const normalizedEndChapter = Number.isInteger(endChapterIndex) ? Number(endChapterIndex) : null;
  return (sceneFiles || []).filter((item: SceneFile) => {
    if (!item?.exists) return false;
    const chapterIndex = Number(item.chapterIndex ?? 0);
    const sceneIndex = Number(item.sceneIndex ?? 0);
    const afterStart = chapterIndex > normalizedChapter
      || (chapterIndex === normalizedChapter && sceneIndex >= normalizedScene);
    const beforeEnd = normalizedEndChapter === null || chapterIndex <= normalizedEndChapter;
    return afterStart && beforeEnd;
  });
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
