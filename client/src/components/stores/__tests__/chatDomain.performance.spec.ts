import { describe, expect, it } from 'vitest';
import { normalizeHistoryMessage } from '../chatDomain';

describe('聊天历史归一化性能契约', () => {
  it('单次读取助手长正文并同时拆出思考与展示内容', () => {
    let contentReads = 0;
    const message = {
      role: 'assistant',
      get content() {
        contentReads += 1;
        return '<think>推理过程</think>最终正文';
      },
      metadata: {},
    };

    expect(normalizeHistoryMessage(message)).toMatchObject({
      content: '最终正文',
      reasoning: '推理过程',
    });
    expect(contentReads).toBe(1);
  });

  it('显式 reasoning 继续优先于正文内嵌思考', () => {
    expect(normalizeHistoryMessage({
      role: 'assistant',
      content: '<think>旧思考</think>最终正文',
      reasoning: '独立思考',
    })).toMatchObject({
      content: '最终正文',
      reasoning: '独立思考',
    });
  });
});
