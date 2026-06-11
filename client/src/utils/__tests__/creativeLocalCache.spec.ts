import { beforeEach, describe, expect, it } from 'vitest';
import {
  buildCreativeCacheKey,
  isCreativeCacheEqual,
  loadCreativeCache,
  refreshCreativeCache,
  saveCreativeCache,
} from '../creativeLocalCache';

describe('creativeLocalCache', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('spark_user_id', 'tester');
  });

  it('按用户与项目隔离缓存键', () => {
    const key = buildCreativeCacheKey('synopsis-workbench', '项目A', 'main');
    expect(key).toContain('creative_doc');
    expect(key).toContain('tester');
    expect(key).toContain('synopsis-workbench');
    expect(key).toContain('项目A');
  });

  it('保存后可以读取带 envelope 的缓存数据', () => {
    const key = buildCreativeCacheKey('world-workbench', 'demo');
    saveCreativeCache(key, {
      museInput: '种子',
      museResult: '结果',
    });

    expect(loadCreativeCache(key)).toEqual({
      museInput: '种子',
      museResult: '结果',
    });
  });

  it('异步刷新时只在远端内容变化时覆盖当前值', async () => {
    const key = buildCreativeCacheKey('structure-workbench', 'demo');
    let current = { context: '本地', guidance: '旧值' };
    const applied: Array<typeof current> = [];

    await refreshCreativeCache({
      cacheKey: key,
      fetcher: async () => ({ context: '远端', guidance: '新值' }),
      getCurrent: () => current,
      applyRemote: (value) => {
        current = value;
        applied.push(value);
      },
    });

    expect(applied).toEqual([{ context: '远端', guidance: '新值' }]);
    expect(loadCreativeCache(key)).toEqual({ context: '远端', guidance: '新值' });
    expect(isCreativeCacheEqual(current, { context: '远端', guidance: '新值' })).toBe(true);
  });
});
