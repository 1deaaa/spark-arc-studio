import { describe, expect, it } from 'vitest';
import {
  appendWorldviewSection,
  moveWorldviewSection,
  parseWorldviewFields,
  parseWorldviewMarkdown,
  removeWorldviewField,
  removeWorldviewSection,
  updateWorldviewField,
  updateWorldviewSection,
} from '../worldviewMarkdown';

describe('世界观 Markdown 协议', () => {
  const markdown = [
    '# 世界设定',
    '',
    '这里是旧版导语。',
    '',
    '## 战力体系',
    '',
    '- 力量来源：灵气',
    '- 使用代价：寿命',
    '',
    '普通补充说明。',
    '',
    '## 货币体系',
    '',
    '- 通用货币：灵石',
  ].join('\n');

  it('按二级标题拆分模块并保留模块正文', () => {
    const document = parseWorldviewMarkdown(markdown);
    expect(document.title).toBe('世界设定');
    expect(document.sections.map(section => section.title)).toEqual(['', '战力体系', '货币体系']);
    expect(document.sections[0].legacy).toBe(true);
    expect(document.sections[0].body).toContain('这里是旧版导语。');
    expect(document.sections[1].body).toContain('普通补充说明。');
  });

  it('没有二级标题的旧文档作为未分组内容读取', () => {
    const legacy = '# 世界观\n\n一整段旧版正文。';
    const document = parseWorldviewMarkdown(legacy);
    expect(document.sections).toHaveLength(1);
    expect(document.sections[0].legacy).toBe(true);
    expect(document.sections[0].body).toBe(legacy);
  });

  it('识别并局部更新字段行，不改动自由文本', () => {
    const body = parseWorldviewMarkdown(markdown).sections[1].body;
    const fields = parseWorldviewFields(body);
    expect(fields.map(field => field.label)).toEqual(['力量来源', '使用代价']);
    const updated = updateWorldviewField(body, fields[1].lineIndex, { value: '记忆' });
    expect(updated).toContain('- 使用代价： 记忆');
    expect(updated).toContain('普通补充说明。');

    const removed = removeWorldviewField(body, fields[0].lineIndex);
    expect(removed).not.toContain('力量来源');
    expect(removed).toContain('- 使用代价：寿命');
    expect(removed).toContain('普通补充说明。');
  });

  it('更新一个模块时保留其他模块与文档前言', () => {
    const updated = updateWorldviewSection(markdown, 1, { title: '能力体系', body: '- 上限：金丹' });
    expect(updated).toContain('这里是旧版导语。');
    expect(updated).toContain('## 能力体系');
    expect(updated).toContain('- 上限：金丹');
    expect(updated).toContain('## 货币体系');
    expect(updated).toContain('- 通用货币：灵石');
  });

  it('支持追加、排序与删除模块', () => {
    const appended = appendWorldviewSection(markdown, '规则与禁忌', '- 禁忌：不可回头');
    expect(parseWorldviewMarkdown(appended).sections).toHaveLength(4);

    const moved = moveWorldviewSection(appended, 3, -1);
    expect(parseWorldviewMarkdown(moved).sections.map(section => section.title)).toEqual([
      '',
      '战力体系',
      '规则与禁忌',
      '货币体系',
    ]);

    const removed = removeWorldviewSection(moved, 2);
    expect(parseWorldviewMarkdown(removed).sections.map(section => section.title)).toEqual([
      '',
      '战力体系',
      '货币体系',
    ]);
  });

  it('旧版正文添加第一个模块后仍作为未分组设定可视编辑', () => {
    const legacy = '# 世界观\n\n旧版正文不会消失。';
    const appended = appendWorldviewSection(legacy, '战力体系', '- 力量来源：灵气');
    const document = parseWorldviewMarkdown(appended);
    expect(document.sections).toHaveLength(2);
    expect(document.sections[0].legacy).toBe(true);
    expect(document.sections[0].body).toContain('旧版正文不会消失。');
    expect(document.sections[1].title).toBe('战力体系');
  });
});
