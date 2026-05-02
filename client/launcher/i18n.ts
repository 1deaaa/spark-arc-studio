import { createI18n } from 'vue-i18n';
import { DEFAULT_LOCALE, LOCALE_STORAGE_KEY, normalizeLocale, type AppLocale } from '@/i18n/types';

const messages = {
  'zh-CN': {
    launcher: {
      brand: '引火AI创作台',
      bootCheckingTitle: '正在连接服务器',
      openServer: '连接并进入',
      autoEnterLabel: '下次服务器可用时直接进入',
      titlebarMinimize: '最小化',
      titlebarMaximize: '最大化',
      titlebarRestore: '还原',
      titlebarClose: '关闭',
      localeSwitcher: {
        title: '切换显示语言',
        labels: {
          'zh-CN': '中文',
          'en-US': 'EN',
          'ja-JP': '日本語',
        },
      },
    },
    server: {
      title: '服务器配置',
      defaultAddress: '默认地址',
      connected: '已连接',
      unreachable: '未连接/连通异常',
      checkAndApply: '检查并设置',
      resetDefault: '恢复默认地址',
      inlinePlaceholder: 'arc.1dea.top',
      status: {
        checking: '连接检测中...',
        connectedAndApplied: '已连接并应用',
        restoringDefault: '已恢复默认地址，请重新连接',
      },
      errors: {
        emptyAddress: '服务器地址不能为空',
        connectFailed: '连接失败，请检查服务地址与网络状态',
        connectFailedWithDetail: '连接失败：{detail}',
        currentUnavailable: '当前保存的服务不可用，请检查后重试',
      },
    },
  },
  'en-US': {
    launcher: {
      brand: 'SparkArc',
      bootCheckingTitle: 'Connecting to Your Server',
      openServer: 'Connect and Enter',
      autoEnterLabel: 'Enter automatically next time when the server is reachable',
      titlebarMinimize: 'Minimize',
      titlebarMaximize: 'Maximize',
      titlebarRestore: 'Restore',
      titlebarClose: 'Close',
      localeSwitcher: {
        title: 'Switch display language',
        labels: {
          'zh-CN': '中文',
          'en-US': 'EN',
          'ja-JP': '日本語',
        },
      },
    },
    server: {
      title: 'Server Settings',
      defaultAddress: 'Default address',
      connected: 'Connected',
      unreachable: 'Disconnected / unreachable',
      checkAndApply: 'Check and Apply',
      resetDefault: 'Reset Default',
      inlinePlaceholder: 'arc.1dea.top',
      status: {
        checking: 'Checking connection...',
        connectedAndApplied: 'Connected and applied',
        restoringDefault: 'Default address restored. Connect again when ready.',
      },
      errors: {
        emptyAddress: 'Server address cannot be empty',
        connectFailed: 'Connection failed. Check the server address and network state.',
        connectFailedWithDetail: 'Connection failed: {detail}',
        currentUnavailable: 'The saved server is unavailable. Please review it and try again.',
      },
    },
  },
  'ja-JP': {
    launcher: {
      brand: 'SparkArc',
      bootCheckingTitle: 'サーバーへ接続しています',
      openServer: '接続して入る',
      autoEnterLabel: '次回はサーバーが使えれば直接入る',
      titlebarMinimize: '最小化',
      titlebarMaximize: '最大化',
      titlebarRestore: '元に戻す',
      titlebarClose: '閉じる',
      localeSwitcher: {
        title: '表示言語を切り替え',
        labels: {
          'zh-CN': '中文',
          'en-US': 'EN',
          'ja-JP': '日本語',
        },
      },
    },
    server: {
      title: 'サーバー設定',
      defaultAddress: '既定アドレス',
      connected: '接続済み',
      unreachable: '未接続 / 到達不可',
      checkAndApply: '確認して適用',
      resetDefault: '既定に戻す',
      inlinePlaceholder: 'arc.1dea.top',
      status: {
        checking: '接続確認中...',
        connectedAndApplied: '接続して適用しました',
        restoringDefault: '既定アドレスに戻しました。必要なら再接続してください。',
      },
      errors: {
        emptyAddress: 'サーバーアドレスは必須です',
        connectFailed: '接続に失敗しました。アドレスとネットワーク状態を確認してください。',
        connectFailedWithDetail: '接続に失敗しました: {detail}',
        currentUnavailable: '保存済みサーバーに接続できません。確認してから再試行してください。',
      },
    },
  },
} as const;

function resolveInitialLocale() {
  if (typeof window === 'undefined') {
    return DEFAULT_LOCALE;
  }

  try {
    const stored = localStorage.getItem('spark_locale');
    if (stored) return normalizeLocale(stored);
  } catch {
    // ignore
  }

  return normalizeLocale(navigator.languages?.[0] || navigator.language);
}

const locale = resolveInitialLocale();

if (typeof document !== 'undefined') {
  document.documentElement.lang = locale;
}

export const i18n = createI18n({
  legacy: false,
  locale,
  fallbackLocale: {
    zh: ['zh-CN'],
    ja: ['ja-JP'],
    en: ['en-US'],
    default: ['zh-CN'],
  },
  fallbackWarn: import.meta.env.DEV,
  missingWarn: import.meta.env.DEV,
  messages,
});

/**
 * 切换 launcher 当前显示语言。会同步：
 * 1) vue-i18n 全局 locale
 * 2) `<html lang>`
 * 3) localStorage[LOCALE_STORAGE_KEY] —— 与主端共享同一存储键，进入工作台后保持一致
 */
export function setI18nLocale(next: string): void {
  const normalized: AppLocale = normalizeLocale(next);
  i18n.global.locale.value = normalized;

  if (typeof document !== 'undefined') {
    document.documentElement.lang = normalized;
  }

  if (typeof window !== 'undefined') {
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, normalized);
    } catch {
      // ignore
    }
  }
}
