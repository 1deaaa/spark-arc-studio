import { describe, expect, it } from 'vitest';
import {
  isLauncherLocalBackendUrl,
  resolveLocalDeploymentPresentation,
  shouldAutoStartLocalBackend,
} from './deploymentPresentation';

describe('Launcher 本地部署入口', () => {
  it('桌面端首次启动且服务不可达时显示部署入口', () => {
    expect(resolveLocalDeploymentPresentation({
      isTauriDesktop: true,
      serverStatusOk: false,
      localBackendEntryExists: false,
    })).toEqual({
      showDeploymentAction: true,
      showUpdateAction: false,
    });
  });

  it('已有 Python 入口且服务不可达时隐藏部署入口并保留更新入口', () => {
    expect(resolveLocalDeploymentPresentation({
      isTauriDesktop: true,
      serverStatusOk: false,
      localBackendEntryExists: true,
    })).toEqual({
      showDeploymentAction: false,
      showUpdateAction: true,
    });
  });

  it('服务已连接时隐藏本地部署入口', () => {
    expect(resolveLocalDeploymentPresentation({
      isTauriDesktop: true,
      serverStatusOk: true,
      localBackendEntryExists: false,
    }).showDeploymentAction).toBe(false);
  });

  it('非桌面端不提供本地部署入口', () => {
    expect(resolveLocalDeploymentPresentation({
      isTauriDesktop: false,
      serverStatusOk: false,
      localBackendEntryExists: false,
    }).showDeploymentAction).toBe(false);
  });
});

describe('Launcher 本地后端自动启动', () => {
  it('桌面端已有 Python 入口但端口未响应时自动启动', () => {
    expect(shouldAutoStartLocalBackend({
      isTauriDesktop: true,
      localBackendEntryExists: true,
      localBackendReachable: false,
      hasExplicitServerOverride: false,
    })).toBe(true);
  });

  it.each([
    { localBackendEntryExists: false },
    { localBackendReachable: true },
    { hasExplicitServerOverride: true },
    { isTauriDesktop: false },
  ])('不会在条件不满足时自动启动：%o', (override) => {
    expect(shouldAutoStartLocalBackend({
      isTauriDesktop: true,
      localBackendEntryExists: true,
      localBackendReachable: false,
      hasExplicitServerOverride: false,
      ...override,
    })).toBe(false);
  });
});

describe('Launcher 本机后端地址识别', () => {
  it.each([
    'http://localhost:6688',
    'http://127.0.0.1:7788',
    'http://[::1]:6688',
  ])('识别受管本机地址 %s', (value) => {
    expect(isLauncherLocalBackendUrl(value, [6688, 7788])).toBe(true);
  });

  it.each([
    'https://arc.1dea.top',
    'http://192.168.1.20:6688',
    'http://localhost:9000',
  ])('保留远程或非受管端口地址 %s', (value) => {
    expect(isLauncherLocalBackendUrl(value, [6688, 7788])).toBe(false);
  });
});
