import { describe, expect, it } from 'vitest';
import { adaptToolDetails } from '../toolDetails';

describe('工具详情展示适配', () => {
  it('只展示委派工具允许的输入字段，并保留返回结果', () => {
    const details = adaptToolDetails('delegate_task', {
      tool_input: {
        target_agent: 'agent_muse',
        task_description: '寻找灵感',
        api_key: '不能展示',
      },
      tool_result: '__DELEGATE__:完成',
    });

    expect(details.expandable).toBe(true);
    expect(details.sections).toHaveLength(2);
    expect(details.sections[0].entries.map(item => item.key)).toEqual([
      'target_agent',
      'task_description',
    ]);
    expect(details.sections[0].entries.some(item => item.text.includes('不能展示'))).toBe(false);
    expect(details.sections[1].entries[0].text).toContain('__DELEGATE__');
  });

  it('隐藏工具发生失败时也允许展开错误原因', () => {
    const details = adaptToolDetails('list_files', {
      tool_input: { path: 'stories', api_key: '不能展示' },
      tool_error: '参数校验失败',
    });

    expect(details.expandable).toBe(true);
    expect(details.sections.map(section => section.key)).toEqual(['error']);
    expect(details.sections[0].entries[0].text).toBe('参数校验失败');
  });

  it('局部替换和联网搜索只暴露适合用户阅读的字段', () => {
    const patch = adaptToolDetails('patch_script', {
      tool_input: {
        search_text: '旧内容',
        replace_text: '新内容',
        export_format: 'arc',
      },
      tool_result: '已完成局部替换',
    });
    const search = adaptToolDetails('web_search', {
      tool_input: {
        query: '资料',
        provider: 'exa',
        api_key: '不能展示',
      },
    });

    expect(patch.sections[0].entries.map(item => item.key)).toEqual(['search_text', 'replace_text']);
    expect(search.sections[0].entries.map(item => item.key)).toEqual(['provider', 'query']);
  });
});
