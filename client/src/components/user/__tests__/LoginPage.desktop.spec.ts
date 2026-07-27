import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

describe('登录页桌面端样式', () => {
  it('桌面 Launcher 保留右上角语言入口并避开标题栏', () => {
    const css = readFileSync(
      resolve(process.cwd(), 'src/components/user/LoginPage.scoped.css'),
      'utf8',
    );
    const titleBar = readFileSync(
      resolve(process.cwd(), 'src/components/layouts/desktop/TitleBar.vue'),
      'utf8',
    );
    const page = readFileSync(
      resolve(process.cwd(), 'src/components/user/LoginPage.vue'),
      'utf8',
    );
    const theme = readFileSync(resolve(process.cwd(), 'src/styles/theme.css'), 'utf8');

    expect(css).not.toMatch(/:global\(\.tauri-desktop\)[^{]*\{[^}]*display\s*:\s*none/i);
    expect(page).toContain("'is-desktop-shell': isTauriDesktop");
    expect(page).toContain("import { isTauriDesktop } from '@/composables/usePlatform'");
    expect(css).toMatch(/\.login-wrap\.is-desktop-shell\s+\.login-lang-select\s*\{[^}]*var\(--spark-desktop-titlebar-height\)/i);
    expect(theme).toContain('--spark-desktop-titlebar-height: 40px');
    expect(titleBar).toContain('height: var(--spark-desktop-titlebar-height)');
    expect(titleBar).not.toContain('titlebar-locale');
    expect(titleBar).toContain('<WindowControls variant="titlebar" />');
  });
});
