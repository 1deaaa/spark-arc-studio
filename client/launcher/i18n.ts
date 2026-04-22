import { createI18n } from 'vue-i18n';
import { DEFAULT_LOCALE, normalizeLocale } from '@/i18n/types';

const messages = {
  'zh-CN': {
    launcher: {
      brand: 'SparkArc Launcher',
      title: '连接你的工作区',
      desc: '本地客户端现在只负责启动、掉线回退和服务器切换。',
      bootCheckingTitle: '正在连接服务器',
      bootCheckingDesc: '启动器会先尝试连接当前服务器；如果可用，就会继续进入正式页面。',
      openServer: '连接并进入',
      reconnecting: '连接检测中...',
      hint: '支持官方部署、自托管部署以及开发者本地地址。',
      autoEnterLabel: '下次服务器可用时直接进入',
      autoEnterHint: '默认关闭，方便自部署用户先检查或更换服务器端点。',
      selfHostedHint: '自部署用户请先把下方地址改成你自己的服务器。',
      footer: 'SparkArc 的安装包现在只负责启动、掉线回退与服务器切换。',
      serverStatusReadyManual: '服务器可用。你可以直接进入正式页面，也可以先调整地址。',
      serverStatusAutoOpen: '服务可用，正在进入正式页面...',
      serverStatusSavedDown: '已记住上次掉线的位置，恢复后会优先返回那个页面。',
      autoEnterPausedOnce: '已返回启动器，你可以先修改服务器地址。',
      titlebarMinimize: '最小化',
      titlebarMaximize: '最大化',
      titlebarRestore: '还原',
      titlebarClose: '关闭',
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
      brand: 'SparkArc Launcher',
      title: 'Connect Your Workspace',
      desc: 'The local client now handles only startup, offline fallback, and server switching.',
      bootCheckingTitle: 'Connecting to Your Server',
      bootCheckingDesc: 'The launcher checks the current server first and continues into the live app as soon as it is reachable.',
      openServer: 'Connect and Enter',
      reconnecting: 'Checking connection...',
      hint: 'Official deployments, self-hosted instances, and localhost developer servers are all supported.',
      autoEnterLabel: 'Enter automatically next time when the server is reachable',
      autoEnterHint: 'Disabled by default so self-hosted users still get a chance to review or change the endpoint first.',
      selfHostedHint: 'If you self-host, switch the address below to your own server before signing in.',
      footer: 'The packaged client is now responsible only for startup, offline fallback, and server switching.',
      serverStatusReadyManual: 'Server is reachable. You can open the live app now or adjust the endpoint first.',
      serverStatusAutoOpen: 'Server is reachable. Opening the live app...',
      serverStatusSavedDown: 'Your last dropped page has been remembered and will be restored when possible.',
      autoEnterPausedOnce: 'You are back in the launcher, so you can change the server address first.',
      titlebarMinimize: 'Minimize',
      titlebarMaximize: 'Maximize',
      titlebarRestore: 'Restore',
      titlebarClose: 'Close',
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
      brand: 'SparkArc Launcher',
      title: 'ワークスペースへ接続する',
      desc: 'ローカルクライアントは起動、切断時の退避、サーバー切替だけを担当します。',
      bootCheckingTitle: 'サーバーへ接続しています',
      bootCheckingDesc: '起動時に現在のサーバーを確認し、利用できればそのまま正式画面へ進みます。',
      openServer: '接続して入る',
      reconnecting: '接続確認中...',
      hint: '公式配布、自前ホスティング、localhost の開発サーバーをそのまま使えます。',
      autoEnterLabel: '次回はサーバーが使えれば直接入る',
      autoEnterHint: '既定ではオフです。自前ホスティング環境でも先に接続先を見直せるようにしています。',
      selfHostedHint: '自前で運用している場合は、下のアドレスを自分のサーバーに変更してください。',
      footer: 'インストール済みクライアントは起動、切断時の退避、サーバー切替だけを担当します。',
      serverStatusReadyManual: 'サーバーへ接続できました。このまま正式画面を開くことも、先にアドレスを調整することもできます。',
      serverStatusAutoOpen: 'サーバーへ接続できました。正式画面を開いています...',
      serverStatusSavedDown: '前回切断されたページを記録しました。復旧後はその場所へ戻れるようにします。',
      autoEnterPausedOnce: 'いまはランチャーに戻っているので、先にサーバーアドレスを変更できます。',
      titlebarMinimize: '最小化',
      titlebarMaximize: '最大化',
      titlebarRestore: '元に戻す',
      titlebarClose: '閉じる',
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
