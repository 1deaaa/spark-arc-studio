import { describe, expect, it, vi } from 'vitest';
import bus from '@/eventBus';
import {
  consumeNdjsonReader,
  consumeSSEReader,
  consumeTextReader,
  createStreamingTask,
  createThinkStreamParser,
  parseSSEEventPayload,
} from '@/utils/streamingRuntime';

function readerFromChunks(chunks: string[]): ReadableStreamDefaultReader<Uint8Array> {
  const encoder = new TextEncoder();
  const values = chunks.map(chunk => encoder.encode(chunk));
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      const value = values.shift();
      if (value) {
        controller.enqueue(value);
      } else {
        controller.close();
      }
    },
  }).getReader();
}

describe('streamingRuntime 架构契约', () => {
  it('跨 chunk 解析 think 标签，正文和推理不串流', () => {
    const parser = createThinkStreamParser();

    expect(parser.push('正文<th')).toEqual({ display: '正文', reasoning: '', inThinkBlock: false });
    expect(parser.push('ink>推理')).toEqual({ display: '', reasoning: '推理', inThinkBlock: true });
    expect(parser.push('</think>结尾')).toEqual({ display: '结尾', reasoning: '', inThinkBlock: false });
    expect(parser.flush()).toEqual({ display: '', reasoning: '', inThinkBlock: false });
  });

  it('consumeNdjsonReader 支持半行、坏行和尾行', async () => {
    const events: Record<string, unknown>[] = [];
    const malformed: string[] = [];
    const textFallback: string[] = [];

    await consumeNdjsonReader(readerFromChunks(['{"a":', '1}\n坏行\n{"b":2}']), {
      onEvent: evt => {
        events.push(evt);
      },
      onMalformedLine: line => {
        malformed.push(line);
      },
      onText: text => {
        textFallback.push(text);
      },
    });

    expect(events).toEqual([{ a: 1 }, { b: 2 }]);
    expect(malformed).toEqual(['坏行']);
    expect(textFallback).toEqual(['坏行']);
  });

  it('consumeSSEReader 支持命名事件和多行 data', async () => {
    const events: { event: string; data: string }[] = [];

    await consumeSSEReader(readerFromChunks(['event: progress\n', 'data: 第一行\n', 'data: 第二行\n\n']), {
      onEvent: evt => {
        events.push(evt);
      },
    });

    expect(events).toEqual([{ event: 'progress', data: '第一行\n第二行' }]);
  });

  it('consumeTextReader 拼接全文并在完成后回调', async () => {
    const chunks: string[] = [];
    let doneText = '';

    const fullText = await consumeTextReader(readerFromChunks(['甲', '乙']), {
      onChunk: chunk => {
        chunks.push(chunk);
      },
      onDone: text => {
        doneText = text;
      },
    });

    expect(fullText).toBe('甲乙');
    expect(chunks).toEqual(['甲', '乙']);
    expect(doneText).toBe('甲乙');
  });

  it('createStreamingTask 只响应匹配 scope/target 的取消事件', () => {
    const onCancel = vi.fn();
    const task = createStreamingTask('world', {
      target: 'worldview',
      text: '生成中',
      onCancel,
    });

    bus.emit('cancel-loading', { scope: 'world', target: 'characters', reason: 'wrong-target' });
    expect(task.aborted).toBe(false);

    bus.emit('cancel-loading', { scope: 'world', target: 'worldview', reason: 'user_cancelled' });
    expect(task.aborted).toBe(true);
    expect(task.cancelReason).toBe('user_cancelled');
    expect(onCancel).toHaveBeenCalledWith({
      scope: 'world',
      target: 'worldview',
      reason: 'user_cancelled',
    });

    task.dispose();
  });

  it('parseSSEEventPayload 对非 JSON 数据保持兼容', () => {
    expect(parseSSEEventPayload('{"ok":true}')).toEqual({ ok: true });
    expect(parseSSEEventPayload('plain text')).toEqual({ raw: 'plain text' });
  });
});
