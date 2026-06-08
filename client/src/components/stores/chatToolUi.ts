import { i18n } from '@/i18n';
import { normalizeToolName } from './chatDomain';

export type ToolUiBinding = {
  scope: string;
  target: string;
  refreshEvents: string[];
};

type AnyRecord = Record<string, any>;

export function getToolProgressText(toolName: unknown, fallbackText = '') {
  const normalizedToolName = normalizeToolName(toolName);
  if (fallbackText && fallbackText.trim()) return fallbackText.trim();
  const mapping: Record<string, string> = {
    rewrite_inspiration: i18n.global.t('chatStore.toolProgress.rewriteInspiration'),
    rewrite_worldview: i18n.global.t('chatStore.toolProgress.rewriteWorldview'),
    rewrite_all_characters: i18n.global.t('chatStore.toolProgress.rewriteAllCharacters'),
    update_character: i18n.global.t('chatStore.toolProgress.updateCharacter'),
    rewrite_synopsis: i18n.global.t('chatStore.toolProgress.rewriteSynopsis'),
    rewrite_beat_sheet: i18n.global.t('chatStore.toolProgress.rewriteBeatSheet'),
    rewrite_outline: i18n.global.t('chatStore.toolProgress.rewriteOutline'),
    patch_outline: i18n.global.t('chatStore.toolProgress.patchOutline'),
    patch_synopsis: i18n.global.t('chatStore.toolProgress.patchSynopsis'),
    patch_beat_sheet: i18n.global.t('chatStore.toolProgress.patchBeatSheet'),
    patch_worldview: i18n.global.t('chatStore.toolProgress.patchWorldview'),
    list_chapters: i18n.global.t('chatStore.toolProgress.listChapters'),
    read_chapter_scene: i18n.global.t('chatStore.toolProgress.readChapterScene'),
    read_chapter_outline_raw: i18n.global.t('chatStore.toolProgress.readChapterOutlineRaw'),
    read_attachment_chunk: i18n.global.t('chatStore.toolProgress.readAttachmentChunk'),
    read_worldview: i18n.global.t('chatStore.toolProgress.readWorldview'),
    read_character: i18n.global.t('chatStore.toolProgress.readCharacter'),
    read_synopsis: i18n.global.t('chatStore.toolProgress.readSynopsis'),
    read_beat_sheet: i18n.global.t('chatStore.toolProgress.readBeatSheet'),
    work_tracker: i18n.global.t('chatStore.toolProgress.workTracker'),
    create_chapter: i18n.global.t('chatStore.toolProgress.createChapter'),
    create_or_rewrite_script: i18n.global.t('chatStore.toolProgress.createOrRewriteScript'),
    patch_script: i18n.global.t('chatStore.toolProgress.patchScript'),
    trigger_auto_write: i18n.global.t('chatStore.toolProgress.triggerAutoWrite'),
    check_scriptwriter_status: i18n.global.t('chatStore.toolProgress.checkScriptwriterStatus'),
    search_project: i18n.global.t('chatStore.toolProgress.searchProject'),
    semantic_search: i18n.global.t('chatStore.toolProgress.semanticSearch'),
    replace_from_search: i18n.global.t('chatStore.toolProgress.replaceFromSearch'),
    web_search: i18n.global.t('chatStore.toolProgress.webSearch'),
    graph_rag_tool: i18n.global.t('chatStore.toolProgress.graphRagTool'),
    delegate_task: i18n.global.t('chatStore.toolProgress.delegateTask'),
    capture_inspiration: i18n.global.t('chatStore.toolProgress.captureInspiration'),
  };
  return mapping[normalizedToolName] || i18n.global.t('chatStore.toolProgress.executingTool', { tool: normalizedToolName || 'unknown' });
}

function isLorebookRewriteTool(toolName: unknown) {
  const normalizedToolName = normalizeToolName(toolName);
  return normalizedToolName === 'rewrite_worldview' || normalizedToolName === 'rewrite_all_characters' || normalizedToolName === 'update_character';
}

function isMuseRewriteTool(toolName: unknown) {
  return normalizeToolName(toolName) === 'rewrite_inspiration';
}

function isOutlineRewriteTool(toolName: unknown) {
  const normalizedToolName = normalizeToolName(toolName);
  return normalizedToolName === 'rewrite_outline' || normalizedToolName === 'patch_outline' || normalizedToolName === 'read_chapter_outline_raw';
}

function isSynopsisTool(toolName: unknown) {
  const normalizedToolName = normalizeToolName(toolName);
  return normalizedToolName === 'rewrite_synopsis' || normalizedToolName === 'patch_synopsis';
}

function isBeatSheetTool(toolName: unknown) {
  const normalizedToolName = normalizeToolName(toolName);
  return normalizedToolName === 'rewrite_beat_sheet' || normalizedToolName === 'patch_beat_sheet';
}

function getLorebookRefreshTarget(toolName: unknown) {
  const normalizedToolName = normalizeToolName(toolName);
  if (normalizedToolName === 'rewrite_worldview') return 'worldview';
  if (normalizedToolName === 'rewrite_all_characters' || normalizedToolName === 'update_character') return 'characters';
  return '';
}

function getToolUiBinding(toolName: unknown): ToolUiBinding {
  if (isMuseRewriteTool(toolName)) {
    return {
      scope: 'muse',
      target: '',
      refreshEvents: ['muse-refresh'],
    };
  }

  if (isLorebookRewriteTool(toolName)) {
    const target = getLorebookRefreshTarget(toolName);
    const refreshEvents = ['lorebook-refresh'];
    if (target === 'worldview') refreshEvents.unshift('lorebook-refresh-worldview');
    if (target === 'characters') refreshEvents.unshift('lorebook-refresh-characters');
    return {
      scope: 'world',
      target,
      refreshEvents,
    };
  }

  if (isOutlineRewriteTool(toolName)) {
    return {
      scope: 'outline',
      target: '',
      refreshEvents: ['outline-refresh'],
    };
  }

  if (isSynopsisTool(toolName)) {
    return {
      scope: 'synopsis',
      target: 'content',
      refreshEvents: ['synopsis-refresh'],
    };
  }

  if (isBeatSheetTool(toolName)) {
    return {
      scope: 'synopsis',
      target: 'beats',
      refreshEvents: ['synopsis-refresh'],
    };
  }

  return {
    scope: '',
    target: '',
    refreshEvents: [],
  };
}

export function resolveToolUiBinding(toolName: unknown, evt: AnyRecord = {}): ToolUiBinding {
  const base = getToolUiBinding(toolName);
  const uiScope = String(evt?.ui_scope || evt?.uiScope || '').trim();
  const uiTarget = String(evt?.ui_target || evt?.uiTarget || '').trim();
  const uiRefreshEvents = Array.isArray(evt?.ui_refresh_events)
    ? evt.ui_refresh_events
    : Array.isArray(evt?.uiRefreshEvents)
      ? evt.uiRefreshEvents
      : null;

  return {
    scope: uiScope || base.scope || '',
    target: uiTarget || base.target || '',
    refreshEvents: uiRefreshEvents?.filter(Boolean) || base.refreshEvents || [],
  };
}

export function getToolUiTaskKey(binding: AnyRecord = {}) {
  const scope = String(binding?.scope || '').trim();
  const target = String(binding?.target || '').trim();
  return scope ? `${scope}::${target}` : '';
}
