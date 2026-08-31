import { describe, expect, it } from 'vitest';

import {
  PresentationRequestError,
  getPresentationErrorStatus,
  isPresentationEndpointNotFoundError,
  isPresentationUpstream500Error,
  isPresentationUpstreamBlockingError,
} from '../presentationService';

describe('演出生图错误状态', () => {
  it('优先读取请求错误上的 HTTP 状态码', () => {
    const error = new PresentationRequestError('上游节点故障', 500);

    expect(getPresentationErrorStatus(error)).toBe(500);
    expect(isPresentationUpstream500Error(error)).toBe(true);
    expect(isPresentationUpstreamBlockingError(error)).toBe(true);
  });

  it('兼容旧后端丢失状态码时的错误文本', () => {
    expect(getPresentationErrorStatus(new Error('Gemini 生图接口调用失败: HTTP 404'))).toBe(404);
    expect(isPresentationEndpointNotFoundError(new Error('Gemini 生图接口调用失败: HTTP 404'))).toBe(true);
    expect(isPresentationUpstreamBlockingError(new Error('Gemini 生图接口调用失败: HTTP 404'))).toBe(false);
    expect(isPresentationUpstreamBlockingError(new Error('Gemini 生图接口调用失败: HTTP 400'))).toBe(false);
  });
});
