import { describe, expect, it } from 'vitest';

import zhCN from '../locales/zh-CN';
import enUS from '../locales/en-US';
import jaJP from '../locales/ja-JP';
import koKR from '../locales/ko-KR';

describe('模型用途说明', () => {
  it('四语都把 Director 默认用途放在推理模型说明前面', () => {
    expect(zhCN.components.modelUsageManager.usageDescReason).toMatch(/^导演未单独绑定模型时的默认用途/);
    expect(enUS.components.modelUsageManager.usageDescReason).toMatch(/^Director's default usage/);
    expect(jaJP.components.modelUsageManager.usageDescReason).toMatch(/^専用モデル未設定時のDirectorの既定用途/);
    expect(koKR.components.modelUsageManager.usageDescReason).toMatch(/^전용 모델이 없을 때 Director가 사용하는 기본 용도/);
  });

  it('不再把未实现的设定核查、结构评估和深度审稿写成推理用途', () => {
    const descriptions = [
      zhCN.components.modelUsageManager.usageDescReason,
      enUS.components.modelUsageManager.usageDescReason,
      jaJP.components.modelUsageManager.usageDescReason,
      koKR.components.modelUsageManager.usageDescReason,
    ];

    for (const description of descriptions) {
      expect(description).not.toMatch(/复杂设定核查|structure evaluation|構成評価|구조 평가/);
      expect(description).not.toMatch(/深度审稿|deep critique|深い批評|심층 비평/);
      expect(description).not.toMatch(/复杂任务核查|complex lore checks|複雑な設定確認|복잡한 설정 검토/);
    }
  });
});
