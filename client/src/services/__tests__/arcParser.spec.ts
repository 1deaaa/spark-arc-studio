import { describe, expect, it } from 'vitest';

import { parseArc, serializeToArc } from '@/services/arcParser';

describe('ARC 演出提示协议', () => {
  it('只解析 @presentation，并把废弃视觉指令静默丢弃', () => {
    const scenes = parseArc([
      '# 雨夜',
      '[旁白]',
      '雨落在玻璃上。',
      '@presentation bg:bg_rainy_window',
      '@presentation illustration_prompt:雨夜窗边，低机位，中景',
      '@act sound:rain_loop',
      '[林澈]',
      '别回头。',
      '@act bg:bg_legacy',
      '@act sprite:sprite_legacy',
      '@web bg:bg_deprecated',
      '@web illustration_prompt:废弃描述',
      '@unknown visual:ignored',
    ].join('\n'));

    const [first, second] = scenes[0].dia;
    expect(first.presentation).toEqual({
      bg: 'bg_rainy_window',
      illustration_prompt: '雨夜窗边，低机位，中景',
    });
    expect(first.act).toEqual({ sound: 'rain_loop' });
    expect(second.presentation).toBeUndefined();
    expect(second.act).toBeUndefined();
    expect(second.txt).toBe('别回头。');

    const serialized = serializeToArc(scenes);
    expect(serialized).toContain('@presentation bg:bg_rainy_window');
    expect(serialized).toContain('@presentation illustration_prompt:雨夜窗边，低机位，中景');
    expect(serialized).toContain('@act sound:rain_loop');
    expect(serialized).not.toContain('@web');
    expect(serialized).not.toContain('@act bg:');
    expect(serialized).not.toContain('@act sprite:');
    expect(serialized).not.toContain('废弃描述');
  });

  it('保留 pending 演出构思标记并可序列化', () => {
    const scenes = parseArc([
      '# 高潮',
      '[旁白]',
      '门在身后合上。',
      '@presentation illustration_pending:true',
    ].join('\n'));

    expect(scenes[0].dia[0].presentation?.illustration_pending).toBe('true');
    expect(serializeToArc(scenes)).toContain('@presentation illustration_pending:true');
  });
});
