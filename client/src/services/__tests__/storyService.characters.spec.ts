import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../apiClient', () => ({
  fetchWithAuth: vi.fn(),
}));

import { fetchWithAuth } from '../apiClient';
import { createCharacter, fetchCharacters } from '../storyService';

describe('角色写入服务', () => {
  beforeEach(() => {
    vi.mocked(fetchWithAuth).mockReset();
  });

  it('创建角色时同时提交当前项目名与角色名', async () => {
    vi.mocked(fetchWithAuth).mockResolvedValue(new Response(JSON.stringify({
      success: true, id: 0, name: '沈棠',
    }), { status: 200 }));

    await createCharacter('111', '沈棠');

    expect(fetchWithAuth).toHaveBeenCalledWith('/api/characters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName: '111', name: '沈棠' }),
    });
  });

  it('可在创建请求中一次提交角色详情', async () => {
    vi.mocked(fetchWithAuth).mockResolvedValue(new Response(JSON.stringify({
      success: true, id: 0, name: '沈棠',
    }), { status: 200 }));

    await createCharacter('111', '沈棠', '身份：档案管理员');

    expect(fetchWithAuth).toHaveBeenCalledWith('/api/characters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName: '111', name: '沈棠', content: '身份：档案管理员' }),
    });
  });

  it('保留后端返回的具体校验原因', async () => {
    vi.mocked(fetchWithAuth).mockResolvedValue(new Response(JSON.stringify({
      error: '角色名已存在',
    }), { status: 409 }));

    await expect(createCharacter('111', '沈棠')).rejects.toThrow('角色名已存在');
  });

  it('角色列表请求失败时抛出错误而不是伪装成空列表', async () => {
    vi.mocked(fetchWithAuth).mockResolvedValue(new Response(JSON.stringify({
      error: '角色列表暂时不可用',
    }), { status: 500 }));

    await expect(fetchCharacters('111', true)).rejects.toThrow('角色列表暂时不可用');
  });
});
