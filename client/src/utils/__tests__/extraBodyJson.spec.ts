import { describe, expect, it } from 'vitest';
import { addReasoningEffort, formatExtraBodyJson, parseExtraBodyJson } from '../extraBodyJson';

describe('Extra Body JSON 工具', () => {
  it('格式化合法 JSON', () => {
    expect(formatExtraBodyJson('{"top_k":40}')).toBe('{\n  "top_k": 40\n}');
  });

  it('自动补齐缺失的最外层大括号', () => {
    expect(parseExtraBodyJson('"top_k": 40, "enable_thinking": true')).toEqual({
      top_k: 40,
      enable_thinking: true,
    });
  });

  it('快捷添加并覆盖 reasoning_effort', () => {
    const result = addReasoningEffort('{"reasoning_effort":"low","top_k":40}', 'max');
    expect(JSON.parse(result)).toEqual({ reasoning_effort: 'max', top_k: 40 });
  });

  it('支持 xhigh 推理强度预制', () => {
    const result = addReasoningEffort('', 'xhigh');
    expect(JSON.parse(result)).toEqual({ reasoning_effort: 'xhigh' });
  });

  it('拒绝非对象 JSON', () => {
    expect(() => parseExtraBodyJson('[1, 2]')).toThrow();
  });
});
