import { describe, expect, it } from 'vitest';
import { normalizeToolName } from '../../chatDomain';
import { getToolUiTaskKey, resolveToolUiBinding } from '../toolUi';

describe('聊天工具 UI 绑定契约', () => {
  it('工具名归一化兼容历史别名', () => {
    expect(normalizeToolName('rewrite-worldview')).toBe('rewrite_worldview');
    expect(normalizeToolName('rewrite characters')).toBe('rewrite_all_characters');
    expect(normalizeToolName('update_character')).toBe('update_character');
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
});
