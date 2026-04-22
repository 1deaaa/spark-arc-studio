import { isLocalTauriShell, isTauri } from '@/composables/usePlatform';
import { getApiBaseUrl, normalizeApiBaseUrl } from '@/services/apiClient';
import {
  buildLauncherReturnUrl,
  readLauncherOriginFromUrl,
} from './launcherHandoff';

let offlineFallbackInstalled = false;

function getCurrentServerBase(): string {
  const configured = normalizeApiBaseUrl(getApiBaseUrl());
  if (configured) return configured;

  if (typeof window === 'undefined') return '';
  const origin = window.location.origin;
  return origin && origin !== 'null' ? origin : '';
}

function returnToLauncherOnOffline() {
  if (!isTauri.value || isLocalTauriShell.value || typeof window === 'undefined') return;

  const launcherOrigin = readLauncherOriginFromUrl(window.location.href);
  if (!launcherOrigin) return;

  const target = buildLauncherReturnUrl({
    launcherOrigin,
    serverBase: getCurrentServerBase(),
    resumeUrl: window.location.href,
    reason: 'offline',
  });

  if (target) {
    window.location.replace(target);
  }
}

export function setupTauriOfflineFallback(): void {
  if (offlineFallbackInstalled || typeof window === 'undefined') return;
  offlineFallbackInstalled = true;
  window.addEventListener('offline', returnToLauncherOnOffline);
}
