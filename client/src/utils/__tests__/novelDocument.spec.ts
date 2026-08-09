import { describe, expect, it } from 'vitest';
import { parseNovelDocument, serializeNovelDocument } from '../novelDocument';

describe('小说文档构思拆装', () => {
  it('加载时拆出构思，保存时恢复单一构思块', () => {
    const parsed = parseNovelDocument('<conception>章末揭示秘密</conception>\n\n正文第一段');
    expect(parsed).toEqual({ conception: '章末揭示秘密', body: '正文第一段' });
    expect(serializeNovelDocument(parsed.body, parsed.conception)).toBe(
      '<conception>\n章末揭示秘密\n</conception>\n\n正文第一段',
    );
  });

  it('兼容模型返回的 JSON conception 字段', () => {
    expect(parseNovelDocument(JSON.stringify({ conception: '伏笔', content: '正文' }))).toEqual({
      conception: '伏笔',
      body: '正文',
    });
  });

  it('空正文 JSON 不会作为可见正文泄漏', () => {
    expect(parseNovelDocument(JSON.stringify({ conception: '仅有构思', content: '' }))).toEqual({
      conception: '仅有构思',
      body: '',
    });
  });

  it('兼容多行缩进的 conception 字段', () => {
    expect(parseNovelDocument('conception:\n  第一行\n  第二行\n\n正文。')).toEqual({
      conception: '第一行\n第二行',
      body: '正文。',
    });
  });
});
