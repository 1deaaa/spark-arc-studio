import { describe, expect, it } from 'vitest';
import { i18n } from '@/i18n';
import zhCN from '@/i18n/locales/zh-CN';
import enUS from '@/i18n/locales/en-US';
import jaJP from '@/i18n/locales/ja-JP';
import koKR from '@/i18n/locales/ko-KR';
import { normalizeToolName } from '../../chatDomain';
import {
  getToolNameLabelKey,
  getToolProgressText,
  getToolUiTaskKey,
  resolveToolUiBinding,
  TOOL_PRESENTATION_KEY_MAP,
} from '../toolUi';

describe('聊天工具 UI 绑定契约', () => {
  it('工具名归一化兼容历史别名', () => {
    expect(normalizeToolName('rewrite-worldview')).toBe('rewrite_worldview');
    expect(normalizeToolName('rewrite characters')).toBe('rewrite_all_characters');
    expect(normalizeToolName('update_character')).toBe('update_character');
    expect(normalizeToolName('update story tags')).toBe('update_project_story_tags');
  });

  it('落盘工具拥有稳定的 scope/target/refreshEvents', () => {
    expect(resolveToolUiBinding('rewrite_inspiration')).toEqual({
      scope: 'muse',
      target: '',
      refreshEvents: ['muse-refresh'],
    });

    expect(resolveToolUiBinding('rewrite_worldview')).toEqual({
      scope: 'world',
      target: 'worldview',
      refreshEvents: ['lorebook-refresh-worldview', 'lorebook-refresh'],
    });

    expect(resolveToolUiBinding('rewrite_all_characters')).toEqual({
      scope: 'world',
      target: 'characters',
      refreshEvents: ['lorebook-refresh-characters', 'lorebook-refresh'],
    });

    expect(resolveToolUiBinding('rewrite_outline').scope).toBe('outline');
    expect(resolveToolUiBinding('rewrite_synopsis')).toMatchObject({ scope: 'synopsis', target: 'content' });
    expect(resolveToolUiBinding('rewrite_beat_sheet')).toMatchObject({ scope: 'synopsis', target: 'beats' });
    expect(resolveToolUiBinding('update_project_story_tags')).toEqual({
      scope: 'story-tags',
      target: '',
      refreshEvents: ['story-tags-refresh'],
    });
  });

  it('后端事件注入的 UI 元数据优先于前端默认绑定', () => {
    const binding = resolveToolUiBinding('rewrite_worldview', {
      ui_scope: 'custom',
      ui_target: 'panel',
      ui_refresh_events: ['custom-refresh'],
    });

    expect(binding).toEqual({
      scope: 'custom',
      target: 'panel',
      refreshEvents: ['custom-refresh'],
    });
    expect(getToolUiTaskKey(binding)).toBe('custom::panel');
  });

  it('进度板和故事记忆工具共用本地化展示映射', () => {
    expect(getToolNameLabelKey('work_tracker')).toBe(
      'components.chatMessageList.tools.workTracker',
    );
    expect(getToolNameLabelKey('story_memory_tool')).toBe(
      'components.chatMessageList.tools.storyMemoryTool',
    );
    expect(getToolProgressText('story_memory_tool', 'Executing story_memory_tool')).toBe(
      i18n.global.t('chatStore.toolProgress.storyMemoryTool'),
    );
    expect(getToolNameLabelKey('prepare_script_creation')).toBe(
      'components.chatMessageList.tools.prepareScriptCreation',
    );
    expect(getToolProgressText('prepare_script_creation')).toBe(
      i18n.global.t('chatStore.toolProgress.prepareScriptCreation'),
    );
  });

  it('联网搜索按提供商显示名称和执行文案', () => {
    expect(getToolNameLabelKey('web_search', { tool_provider: 'exa' })).toBe(
      'components.chatMessageList.tools.webSearchExa',
    );
    expect(getToolNameLabelKey('web_search', { tool_provider: 'tavily' })).toBe(
      'components.chatMessageList.tools.webSearchTavily',
    );
    expect(getToolProgressText('web_search', '', { tool_provider: 'exa' })).toBe(
      i18n.global.t('chatStore.toolProgress.webSearchExa'),
    );
    expect(getToolProgressText('web_search', '', { tool_provider: 'tavily' })).toBe(
      i18n.global.t('chatStore.toolProgress.webSearchTavily'),
    );
  });

  it('所有已映射工具都有四语名称和执行中文案', () => {
    const locales = [zhCN, enUS, jaJP, koKR] as Array<Record<string, any>>;
    const suffixes = new Set(Object.values(TOOL_PRESENTATION_KEY_MAP));

    for (const locale of locales) {
      for (const suffix of suffixes) {
        expect(locale.components.chatMessageList.tools[suffix]).toEqual(expect.any(String));
        expect(locale.chatStore.toolProgress[suffix]).toEqual(expect.any(String));
      }
    }
  });
});
