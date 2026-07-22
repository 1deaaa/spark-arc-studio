import { afterEach, describe, expect, it, vi } from 'vitest';

import { SPARKARC_GITHUB_URL } from '@/config';
import { openExternalUrl } from '@/utils/externalLinks';
import { openUrl } from '@tauri-apps/plugin-opener';

vi.mock('@tauri-apps/plugin-opener', () => ({
  openUrl: vi.fn(),
}));

const mockedOpenUrl = vi.mocked(openUrl);

afterEach(() => {
  vi.restoreAllMocks();
  mockedOpenUrl.mockReset();
  delete window.__TAURI__;
  delete window.__TAURI_INTERNALS__;
});

describe('openExternalUrl', () => {
  it('浏览器环境在新标签页打开仓库地址', async () => {
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue({} as Window);

    await openExternalUrl(SPARKARC_GITHUB_URL);

    expect(windowOpen).toHaveBeenCalledWith(
      SPARKARC_GITHUB_URL,
      '_blank',
      'noopener,noreferrer',
    );
    expect(mockedOpenUrl).not.toHaveBeenCalled();
  });

  it('Tauri 环境优先使用原生 opener', async () => {
    window.__TAURI_INTERNALS__ = {};
    mockedOpenUrl.mockResolvedValue(undefined);
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue({} as Window);

    await openExternalUrl(SPARKARC_GITHUB_URL);

    expect(mockedOpenUrl).toHaveBeenCalledWith(SPARKARC_GITHUB_URL);
    expect(windowOpen).not.toHaveBeenCalled();
  });

  it('旧版 Tauri 壳拒绝新仓库地址时回退到 WebView 导航', async () => {
    window.__TAURI_INTERNALS__ = {};
    mockedOpenUrl.mockRejectedValue(new Error('not allowed'));
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue({} as Window);

    await openExternalUrl(SPARKARC_GITHUB_URL);

    expect(windowOpen).toHaveBeenCalledWith(
      SPARKARC_GITHUB_URL,
      '_blank',
      'noopener,noreferrer',
    );
  });
});
