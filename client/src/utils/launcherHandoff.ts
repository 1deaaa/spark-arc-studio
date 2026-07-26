import { normalizeApiBaseUrl } from '@/services/apiClient';
import { LOCALE_QUERY_PARAM, LOCALE_STORAGE_KEY, normalizeLocale } from '@/i18n/types';
import { preserveWorkspaceWindow } from './workspaceWindow';

const LAUNCHER_ORIGIN_PARAM = 'spark_launcher_origin';
const LAUNCHER_SERVER_PARAM = 'spark_server';
const LAUNCHER_RESUME_PARAM = 'spark_resume_url';
const LAUNCHER_REASON_PARAM = 'spark_reason';
const LAUNCHER_SKIP_AUTO_PARAM = 'spark_skip_auto_enter';
const PENDING_RESUME_KEY = 'spark_launcher_pending_resume';

export type LauncherResumeState = {
  serverBase: string;
  resumeUrl: string;
  reason: string;
  capturedAt: number;
};

export type LauncherStartupHints = {
  serverBase: string;
  resumeUrl: string;
  reason: string;
  skipAutoConnect: boolean;
  capturedAt: number;
};

function normalizeAbsoluteUrl(input: string): string {
  const raw = (input || '').trim();
  if (!raw) return '';
  try {
    return new URL(raw).toString();
  } catch {
    return '';
  }
}

function getLocationOrigin(): string {
  if (typeof window === 'undefined') return '';

  const { origin, protocol, host } = window.location;
  if (origin && origin !== 'null') return origin;
  if (protocol === 'tauri:') return 'tauri://localhost';
  return host ? `${protocol}//${host}` : '';
}

function readCurrentLocale(): string {
  if (typeof window === 'undefined') return '';
  try {
    return normalizeLocale(localStorage.getItem(LOCALE_STORAGE_KEY) || navigator.languages?.[0] || navigator.language);
  } catch {
    return normalizeLocale(typeof navigator !== 'undefined' ? navigator.language : '');
  }
}

export function getLocalLauncherOrigin(): string {
  return getLocationOrigin();
}

export function readLauncherOriginFromUrl(inputUrl = typeof window !== 'undefined' ? window.location.href : ''): string {
  const absolute = normalizeAbsoluteUrl(inputUrl);
  if (!absolute) return '';

  try {
    const url = new URL(absolute);
    return normalizeAbsoluteUrl(url.searchParams.get(LAUNCHER_ORIGIN_PARAM) || '');
  } catch {
    return '';
  }
}

export function attachLauncherOrigin(targetUrl: string, launcherOrigin: string): string {
  const absolute = normalizeAbsoluteUrl(targetUrl);
  const normalizedOrigin = normalizeAbsoluteUrl(launcherOrigin);
  if (!absolute) return '';

  try {
    const url = new URL(absolute);
    if (normalizedOrigin) {
      url.searchParams.set(LAUNCHER_ORIGIN_PARAM, normalizedOrigin);
    }
    const locale = readCurrentLocale();
    if (locale) {
      url.searchParams.set(LOCALE_QUERY_PARAM, locale);
    }
    return preserveWorkspaceWindow(
      url.toString(),
      typeof window !== 'undefined' ? window.location.href : '',
    );
  } catch {
    return absolute;
  }
}

export function buildLauncherReturnUrl(options: {
  launcherOrigin: string;
  serverBase?: string;
  resumeUrl?: string;
  reason?: string;
  skipAutoConnect?: boolean;
}): string {
  const launcherOrigin = normalizeAbsoluteUrl(options.launcherOrigin);
  if (!launcherOrigin) return '';

  try {
    const url = new URL(launcherOrigin);
    const serverBase = normalizeApiBaseUrl(options.serverBase || '');
    const resumeUrl = normalizeAbsoluteUrl(options.resumeUrl || '');
    const reason = (options.reason || 'offline').trim() || 'offline';
    const skipAutoConnect = !!options.skipAutoConnect;

    if (serverBase) url.searchParams.set(LAUNCHER_SERVER_PARAM, serverBase);
    if (resumeUrl) url.searchParams.set(LAUNCHER_RESUME_PARAM, resumeUrl);
    url.searchParams.set(LAUNCHER_REASON_PARAM, reason);
    if (skipAutoConnect) {
      url.searchParams.set(LAUNCHER_SKIP_AUTO_PARAM, '1');
    }
    return preserveWorkspaceWindow(
      url.toString(),
      typeof window !== 'undefined' ? window.location.href : '',
    );
  } catch {
    return '';
  }
}

export function persistLauncherResume(state: LauncherResumeState): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(PENDING_RESUME_KEY, JSON.stringify(state));
  } catch {
    // ignore
  }
}

export function readLauncherResume(): LauncherResumeState | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(PENDING_RESUME_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<LauncherResumeState>;
    const serverBase = normalizeApiBaseUrl(parsed.serverBase || '');
    const resumeUrl = normalizeAbsoluteUrl(parsed.resumeUrl || '');
    if (!serverBase || !resumeUrl) return null;
    return {
      serverBase,
      resumeUrl,
      reason: (parsed.reason || 'offline').trim() || 'offline',
      capturedAt: typeof parsed.capturedAt === 'number' ? parsed.capturedAt : Date.now(),
    };
  } catch {
    return null;
  }
}

export function clearLauncherResume(): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.removeItem(PENDING_RESUME_KEY);
  } catch {
    // ignore
  }
}

export function consumeLauncherStartupHintsFromUrl(): LauncherStartupHints | null {
  if (typeof window === 'undefined') return null;

  let startupHints: LauncherStartupHints | null = null;

  try {
    const url = new URL(window.location.href);
    const serverBase = normalizeApiBaseUrl(url.searchParams.get(LAUNCHER_SERVER_PARAM) || '');
    const resumeUrl = normalizeAbsoluteUrl(url.searchParams.get(LAUNCHER_RESUME_PARAM) || '');
    const reason = (url.searchParams.get(LAUNCHER_REASON_PARAM) || 'offline').trim() || 'offline';
    const skipAutoConnect = ['1', 'true', 'yes'].includes(
      (url.searchParams.get(LAUNCHER_SKIP_AUTO_PARAM) || '').trim().toLowerCase()
    );

    if (serverBase || resumeUrl || skipAutoConnect) {
      startupHints = {
        serverBase,
        resumeUrl,
        reason,
        skipAutoConnect,
        capturedAt: Date.now(),
      };
    }

    if (serverBase && resumeUrl && startupHints) {
      persistLauncherResume({
        serverBase,
        resumeUrl,
        reason,
        capturedAt: startupHints.capturedAt,
      });
    }

    const hadHints =
      url.searchParams.has(LAUNCHER_SERVER_PARAM) ||
      url.searchParams.has(LAUNCHER_RESUME_PARAM) ||
      url.searchParams.has(LAUNCHER_REASON_PARAM) ||
      url.searchParams.has(LAUNCHER_SKIP_AUTO_PARAM);

    url.searchParams.delete(LAUNCHER_SERVER_PARAM);
    url.searchParams.delete(LAUNCHER_RESUME_PARAM);
    url.searchParams.delete(LAUNCHER_REASON_PARAM);
    url.searchParams.delete(LAUNCHER_SKIP_AUTO_PARAM);

    if (hadHints) {
      window.history.replaceState(null, '', url.toString());
    }
  } catch {
    return null;
  }

  return startupHints;
}

export function getLauncherTargetForServer(serverBase: string, launcherOrigin = getLocalLauncherOrigin()): string {
  const normalizedServer = normalizeApiBaseUrl(serverBase);
  if (!normalizedServer) return '';

  const pending = readLauncherResume();
  if (pending && normalizeApiBaseUrl(pending.serverBase) === normalizedServer) {
    return attachLauncherOrigin(pending.resumeUrl, launcherOrigin);
  }

  return attachLauncherOrigin(normalizedServer, launcherOrigin);
}
