import { getDerivedColors, mixHex, rgbaFromHex, tokens } from '@/styles/tokens';
import { FONT_PRESET_STACKS, applyAppFontCssVars, normalizeUserFontFamily } from '@/styles/fontStacks';

export type LauncherThemeMode = 'light' | 'dark' | 'system';

export type LauncherThemeSnapshot = {
  themeMode: LauncherThemeMode;
  prefersDark: boolean;
  primaryColorDark: string;
  primaryColorLight: string;
  fontKey: string;
  fontFamily: string;
  updatedAt: number;
};

const LOCAL_CACHE_KEY = 'spark_launcher_theme_snapshot';
const VALID_THEME_MODES = new Set<LauncherThemeMode>(['light', 'dark', 'system']);
const VALID_FONT_KEYS = new Set(['theme', 'yahei', 'pingfang', 'notoSans']);
function isTauriRuntime(): boolean {
  if (typeof window === 'undefined') return false;
  return !!(window.__TAURI_INTERNALS__ || window.__TAURI__);
}

function normalizeThemeMode(value: unknown): LauncherThemeMode {
  const mode = (value || '').toString().trim() as LauncherThemeMode;
  return VALID_THEME_MODES.has(mode) ? mode : 'system';
}

function normalizeHexColor(value: unknown): string {
  const raw = (value || '').toString().trim();
  if (!raw) return '';
  return /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(raw) ? raw : '';
}

function normalizeFontKey(value: unknown): string {
  const key = (value || '').toString().trim();
  return VALID_FONT_KEYS.has(key) ? key : 'theme';
}

function normalizeString(value: unknown): string {
  return (value || '').toString().trim();
}

export function normalizeLauncherThemeSnapshot(input: Partial<LauncherThemeSnapshot> | null | undefined): LauncherThemeSnapshot {
  return {
    themeMode: normalizeThemeMode(input?.themeMode),
    prefersDark: !!input?.prefersDark,
    primaryColorDark: normalizeHexColor(input?.primaryColorDark),
    primaryColorLight: normalizeHexColor(input?.primaryColorLight),
    fontKey: normalizeFontKey(input?.fontKey),
    fontFamily: normalizeString(input?.fontFamily),
    updatedAt: typeof input?.updatedAt === 'number' ? input.updatedAt : Date.now(),
  };
}

export function captureLauncherThemeSnapshot(themeStore: any): LauncherThemeSnapshot {
  return normalizeLauncherThemeSnapshot({
    themeMode: themeStore.themeMode,
    prefersDark: themeStore.prefersDark,
    primaryColorDark: themeStore.primaryColorDark,
    primaryColorLight: themeStore.primaryColorLight,
    fontKey: themeStore.fontKey,
    fontFamily: themeStore.fontFamily,
    updatedAt: Date.now(),
  });
}

function writeLocalSnapshot(snapshot: LauncherThemeSnapshot): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(LOCAL_CACHE_KEY, JSON.stringify(snapshot));
  } catch {
    // ignore
  }
}

function readLocalSnapshot(): LauncherThemeSnapshot | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(LOCAL_CACHE_KEY);
    if (!raw) return null;
    return normalizeLauncherThemeSnapshot(JSON.parse(raw));
  } catch {
    return null;
  }
}

export async function persistLauncherThemeSnapshot(snapshot: LauncherThemeSnapshot): Promise<void> {
  const normalized = normalizeLauncherThemeSnapshot(snapshot);
  writeLocalSnapshot(normalized);

  if (!isTauriRuntime()) return;
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    await invoke('set_launcher_theme_state', { state: normalized });
  } catch {
    // The web app can still run in browsers or remote shells without this command.
  }
}

export async function readLauncherThemeSnapshot(): Promise<LauncherThemeSnapshot | null> {
  const localSnapshot = readLocalSnapshot();

  if (!isTauriRuntime()) return localSnapshot;
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    const remoteSnapshot = await invoke<Partial<LauncherThemeSnapshot> | null>('get_launcher_theme_state');
    return remoteSnapshot ? normalizeLauncherThemeSnapshot(remoteSnapshot) : localSnapshot;
  } catch {
    return localSnapshot;
  }
}

export function applyLauncherThemeSnapshotToStore(themeStore: any, snapshot: LauncherThemeSnapshot | null): void {
  if (!snapshot) return;
  const normalized = normalizeLauncherThemeSnapshot(snapshot);

  themeStore.setThemeMode?.(normalized.themeMode);
  themeStore.setPrefersDark?.(normalized.prefersDark);
  themeStore.setPrimaryColorDark?.(normalized.primaryColorDark);
  themeStore.setPrimaryColorLight?.(normalized.primaryColorLight);
  themeStore.setFontKey?.(normalized.fontKey);
  themeStore.setFontFamily?.(normalized.fontFamily);
}

function getPresetFontStack(key: string): string {
  return FONT_PRESET_STACKS[key] || '';
}

export function applyLauncherThemeSnapshotToDocument(snapshot: LauncherThemeSnapshot): void {
  if (typeof document === 'undefined') return;

  const normalized = normalizeLauncherThemeSnapshot(snapshot);
  const isDark = normalized.themeMode === 'dark' || (normalized.themeMode === 'system' && normalized.prefersDark);
  const primaryOverride = (isDark ? normalized.primaryColorDark : normalized.primaryColorLight).trim();
  const colors = getDerivedColors(isDark, primaryOverride || null);
  const primary = colors.primary;
  const body = document.body;

  colors.primaryHover = mixHex(primary, '#000000', isDark ? 0.15 : 0.12);
  colors.primaryGlow = rgbaFromHex(primary, isDark ? 0.35 : 0.25);
  colors.primaryContainer = rgbaFromHex(primary, isDark ? 0.12 : 0.08);
  colors.body = mixHex(isDark ? tokens.bg.dark.main : tokens.bg.light.main, primary, isDark ? 0.02 : 0.03);
  colors.panel = isDark ? mixHex(tokens.bg.dark.main, primary, 0.06) : tokens.bg.light.panel;
  colors.border = isDark ? rgbaFromHex(primary, 0.2) : rgbaFromHex(primary, 0.15);

  const fontStack = normalizeUserFontFamily(normalized.fontFamily) || getPresetFontStack(normalized.fontKey);
  applyAppFontCssVars(body.style, fontStack);

  body.style.setProperty('--spark-primary', colors.primary);
  body.style.setProperty('--spark-primary-dim', colors.primaryHover);
  body.style.setProperty('--spark-primary-glow', colors.primaryGlow);
  body.style.setProperty('--spark-primary-container', colors.primaryContainer);
  body.style.setProperty('--spark-border', colors.border);
  body.style.setProperty('--spark-bg', colors.body);
  body.style.setProperty('--spark-panel-bg', colors.panel);
  body.style.setProperty('--spark-text', colors.text);
  body.style.setProperty('--spark-text-muted', colors.textMuted);
  body.style.setProperty('--spark-text-inverse', colors.textInverse);
  body.style.setProperty('--spark-success', colors.success);
  body.style.setProperty('--spark-warning', colors.warning);
  body.style.setProperty('--spark-danger', colors.danger);

  body.classList.toggle('dark-mode', isDark);
  body.classList.toggle('light-mode', !isDark);
}
