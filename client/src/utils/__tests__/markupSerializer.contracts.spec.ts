import { describe, expect, it } from 'vitest';

import {
  parseBeatSheetMarkup,
  parseOutlineMarkup,
  serializeBeatSheetToMarkup,
  serializeOutlineToMarkup,
} from '../markupSerializer';


describe('结构产物 Markup 契约', () => {
  it('往返保存节拍状态变化字段', () => {
    const raw = [
      '@arc 疏离到重逢',
      '---beat 2',
      '> 类型：惊喜揭晓 | 情感目标：惊喜 | 张力：High',
      '> 前置状态：弟弟不知道哥哥已到门外',
      '> 触发：弟弟开门',
      '> 选择/行动：哥哥现身',
      '> 后置状态：兄弟重逢',
      '> 知情变化：弟弟确认哥哥归来',
      '> 因果依赖：Beat 1',
      '惊喜在开门时揭晓。',
    ].join('\n');

    const parsed = parseBeatSheetMarkup(raw);
    expect(parsed.beats[0].post_state).toBe('兄弟重逢');
    expect(parsed.beats[0].causal_dependencies).toEqual(['Beat 1']);

    const reparsed = parseBeatSheetMarkup(serializeBeatSheetToMarkup(parsed));
    expect(reparsed.beats[0].knowledge_change).toBe('弟弟确认哥哥归来');
    expect(reparsed.beats[0].trigger).toBe('弟弟开门');
  });

  it('往返保存大纲连续性契约', () => {
    const raw = [
      '## 一 · 归来',
      '### 1-1 门外',
      '> 情绪：期待 | 张力：Medium | 登场：哥哥 | 对应节拍：2 | 指引：保护信息差',
      '> 地点：弟弟家门外 | 时间：傍晚',
      '> 前置状态：弟弟不知道哥哥已经返程',
      '> 后置状态：弟弟确认哥哥已经回来',
      '> 知情前：只有哥哥知道返程计划',
      '> 知情后：兄弟二人都知道哥哥已经返家',
      '> 禁止铺垫：哥哥不得提前询问礼物或透露返程',
      '@key_dialogue 门开了。',
    ].join('\n');

    const parsed = parseOutlineMarkup(raw);
    const scene = parsed.nodes[0].children[0];
    expect(scene.beat_refs).toEqual(['2']);
    expect(scene.forbidden_setup).toContain('不得提前询问礼物');

    const reparsed = parseOutlineMarkup(serializeOutlineToMarkup(parsed));
    const reparsedScene = reparsed.nodes[0].children[0];
    expect(reparsedScene.knowledge_before).toBe('只有哥哥知道返程计划');
    expect(reparsedScene.knowledge_after).toBe('兄弟二人都知道哥哥已经返家');
    expect(reparsedScene.key_dialogues).toEqual(['门开了。']);
  });
});
