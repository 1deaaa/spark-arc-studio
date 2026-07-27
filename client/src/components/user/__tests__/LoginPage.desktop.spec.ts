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

    expect(css).not.toMatch(/:global\(\.tauri-desktop\)[^{]*\{[^}]*display\s*:\s*none/i);
    expect(css).toMatch(/:global\(\.platform-desktop-shell\)\s+\.login-lang-select\s*\{[^}]*top:\s*calc\(48px/i);
    expect(titleBar).not.toContain('titlebar-locale');
    expect(titleBar).toContain('<WindowControls variant="titlebar" />');
  });
});
