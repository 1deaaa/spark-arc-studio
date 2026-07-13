import { describe, expect, it } from 'vitest';
import {
  estimateChatMessageRenderCost,
  selectChatTailWindowStart,
  selectOlderChatWindowStart,
  type ChatMessageItem,
} from '../message/render';

const initialWindow = { maxMessages: 4, maxContentChars: 6000 };
const olderWindow = { maxMessages: 6, maxContentChars: 12000 };

describe('聊天历史渲染窗口', () => {
  it('长历史切换时只检查并选择尾部少量消息', () => {
    const history: ChatMessageItem[] = Array.from({ length: 200 }, (_, index) => ({
      id: `message-${index}`,
      role: index % 2 === 0 ? 'user' : 'assistant',
      content: `第 ${index} 条消息`,
    }));

    const start = selectChatTailWindowStart(history, initialWindow);
    expect(history.length - start).toBe(4);
    expect(history[start]?.id).toBe('message-196');
    expect(history.at(-1)?.id).toBe('message-199');
  });

  it('单条助手回复超过预算时仍保留完整正文和前一条用户请求', () => {
    const history: ChatMessageItem[] = [
      { id: 'old', role: 'assistant', content: '旧消息' },
      { id: 'user', role: 'user', content: '请继续写' },
      {
        id: 'assistant',
        role: 'assistant',
        content: '长回复'.repeat(5000),
        segments: [{ type: 'text', text: '长回复'.repeat(5000) }],
      },
    ];

    const start = selectChatTailWindowStart(history, initialWindow);
    expect(start).toBe(1);
    expect(history.slice(start).map(message => message.id)).toEqual(['user', 'assistant']);
    expect(estimateChatMessageRenderCost(history[2])).toBeGreaterThan(initialWindow.maxContentChars);
  });

  it('触顶每次只补一个批次，并尽量从用户消息开始', () => {
    const history: ChatMessageItem[] = Array.from({ length: 40 }, (_, index) => ({
      id: index,
      role: index % 2 === 0 ? 'user' : 'assistant',
      content: `消息 ${index}`,
    }));
    const currentStart = 36;
    const nextStart = selectOlderChatWindowStart(history, currentStart, olderWindow);

    expect(currentStart - nextStart).toBeGreaterThan(0);
    expect(currentStart - nextStart).toBeLessThanOrEqual(7);
    expect(history[nextStart]?.role).toBe('user');
  });
});
