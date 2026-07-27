import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

interface TauriConfig {
  plugins?: Record<string, unknown>;
  bundle?: {
    active?: boolean;
    windows?: {
      nsis?: {
        installerHooks?: string;
      };
    };
  };
}

const configPath = resolve(process.cwd(), 'src-tauri/tauri.conf.json');
const cargoPath = resolve(process.cwd(), 'src-tauri/Cargo.toml');
const libPath = resolve(process.cwd(), 'src-tauri/src/lib.rs');
const launcherPath = resolve(process.cwd(), 'launcher/LauncherApp.vue');
const windowControlsPath = resolve(process.cwd(), 'src/components/layouts/desktop/WindowControls.vue');
const mainCapabilityPath = resolve(process.cwd(), 'src-tauri/capabilities/main.json');
const remoteCapabilityPath = resolve(process.cwd(), 'src-tauri/capabilities/remote-desktop.json');

describe('Windows 桌面端 Tauri 配置', () => {
  it('不再加载会导致 Launcher 启动 panic 的 Shell 插件配置', () => {
    const config = JSON.parse(readFileSync(configPath, 'utf8')) as TauriConfig;
    const cargo = readFileSync(cargoPath, 'utf8');
    const lib = readFileSync(libPath, 'utf8');

    expect(config.plugins?.shell).toBeUndefined();
    expect(cargo).not.toContain('tauri-plugin-shell');
    expect(lib).not.toContain('tauri_plugin_shell::init()');
    expect(cargo).toContain('tauri-plugin-opener');
    expect(lib).toContain('.plugin(tauri_plugin_opener::init())');
  });

  it('不再使用 Tauri 2 文件插件无法识别的旧版 scope 配置', () => {
    const config = JSON.parse(readFileSync(configPath, 'utf8')) as TauriConfig;

    expect(config.plugins?.fs).toBeUndefined();
  });

  it('Windows 发布产物必须走带快捷方式和自启动钩子的 NSIS 安装流程', () => {
    const config = JSON.parse(readFileSync(configPath, 'utf8')) as TauriConfig;
    const hooksPath = resolve(process.cwd(), 'src-tauri/windows/installer-hooks.nsh');
    const hooks = readFileSync(hooksPath, 'utf8');

    expect(config.bundle?.active).toBe(true);
    expect(config.bundle?.windows?.nsis).toMatchObject({
      installerHooks: './windows/installer-hooks.nsh',
    });
    expect(config.bundle?.windows?.nsis).not.toHaveProperty('installMode');
    expect(config.bundle?.windows?.nsis).not.toHaveProperty('languages');
    expect(config.bundle?.windows?.nsis).not.toHaveProperty('startMenuFolder');
    expect(hooks).toContain('CreateOrUpdateDesktopShortcut');
    expect(hooks).toContain('CurrentVersion\\Run');
    expect(hooks).toContain('NSIS_HOOK_PREUNINSTALL');
    expect(hooks).toContain('DeleteRegValue HKCU');
  });

  it('连接后在当前窗口导航，关闭按钮会关闭当前客户端', () => {
    const lib = readFileSync(libPath, 'utf8');
    const launcher = readFileSync(launcherPath, 'utf8');
    const windowControls = readFileSync(windowControlsPath, 'utf8');
    const mainCapability = JSON.parse(readFileSync(mainCapabilityPath, 'utf8')) as {
      permissions: string[];
    };
    const remoteCapability = JSON.parse(readFileSync(remoteCapabilityPath, 'utf8')) as {
      permissions: string[];
    };

    expect(lib).not.toContain('async fn open_remote_app');
    expect(lib).not.toContain('WebviewWindowBuilder');
    expect(launcher).toContain('window.location.replace(target)');
    expect(launcher).not.toContain('markWorkspaceWindow');
    expect(windowControls).toContain('class="win-btn win-btn--close"');
    expect(mainCapability.permissions).toContain('core:window:allow-close');
    expect(remoteCapability.permissions).toContain('core:window:allow-close');
  });
});
