export interface LocalDeploymentPresentationInput {
  isTauriDesktop: boolean;
  serverStatusOk: boolean;
  localBackendReady: boolean;
}

export interface LocalDeploymentPresentation {
  showDeploymentAction: boolean;
  showUpdateAction: boolean;
}

export interface LocalBackendAutoStartInput {
  isTauriDesktop: boolean;
  localBackendReady: boolean;
  localBackendReachable: boolean;
  hasExplicitServerOverride: boolean;
}

const LOCAL_BACKEND_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]']);

/** 判断持久化地址是否指向 Launcher 管理的本机后端端口。 */
export function isLauncherLocalBackendUrl(value: string, ports: readonly number[]): boolean {
  try {
    const url = new URL(value);
    return LOCAL_BACKEND_HOSTS.has(url.hostname)
      && ports.includes(Number.parseInt(url.port, 10));
  } catch {
    return false;
  }
}

/** 统一计算 Launcher 本地部署入口，避免首次部署被“目录不存在”条件反向隐藏。 */
export function resolveLocalDeploymentPresentation(
  input: LocalDeploymentPresentationInput,
): LocalDeploymentPresentation {
  const showDeploymentAction = input.isTauriDesktop
    && !input.serverStatusOk
    && !input.localBackendReady;
  return {
    showDeploymentAction,
    showUpdateAction: input.isTauriDesktop && input.localBackendReady,
  };
}

/** 仅自动拉起已经部署的受管后端；显式服务器跳转始终优先。 */
export function shouldAutoStartLocalBackend(input: LocalBackendAutoStartInput): boolean {
  return input.isTauriDesktop
    && input.localBackendReady
    && !input.localBackendReachable
    && !input.hasExplicitServerOverride;
}
