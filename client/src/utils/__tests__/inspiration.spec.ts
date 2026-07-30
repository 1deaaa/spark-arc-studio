import { describe, expect, it } from 'vitest';

import { shouldRestoreInspirationWorkbenchCache } from '../inspiration';

describe('灵感工坊缓存恢复契约', () => {
  it('仅在缓存灵感与项目当前灵感一致时恢复', () => {
    expect(shouldRestoreInspirationWorkbenchCache('inspiration-a', 'inspiration-a')).toBe(true);
    expect(shouldRestoreInspirationWorkbenchCache('inspiration-a', 'inspiration-b')).toBe(false);
    expect(shouldRestoreInspirationWorkbenchCache('inspiration-a', null)).toBe(false);
    expect(shouldRestoreInspirationWorkbenchCache(null, 'inspiration-a')).toBe(false);
  });
});
