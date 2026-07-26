import { describe, expect, it } from 'vitest';
import {
  hasWorkspaceWindowMarker,
  markWorkspaceWindow,
  preserveWorkspaceWindow,
} from '@/utils/workspaceWindow';

describe('独立业务窗口标记', () => {
  it('为业务地址添加稳定标记且不丢失现有查询参数', () => {
    const target = markWorkspaceWindow('https://example.com/login?locale=zh-CN');

    expect(hasWorkspaceWindowMarker(target)).toBe(true);
    expect(new URL(target).searchParams.get('locale')).toBe('zh-CN');
  });

  it('业务窗口内部跳转时继承标记', () => {
    expect(preserveWorkspaceWindow(
      'https://example.com/editor?project=demo',
      'https://example.com/?spark_workspace_window=1',
    )).toContain('spark_workspace_window=1');
    expect(preserveWorkspaceWindow(
      'https://example.com/editor?project=demo',
      'https://example.com/',
    )).not.toContain('spark_workspace_window');
  });
});
