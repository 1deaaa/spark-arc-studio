import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

describe('登录页桌面端样式', () => {
  it('不得通过 Tauri 的 body 标记隐藏页面内容', () => {
    const css = readFileSync(
      resolve(process.cwd(), 'src/components/user/LoginPage.scoped.css'),
      'utf8',
    );

    expect(css).not.toMatch(/:global\(\.tauri-desktop\)[^{]*\{[^}]*display\s*:\s*none/i);
  });
});
