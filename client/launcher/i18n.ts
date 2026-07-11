import { createI18n } from 'vue-i18n';
import {
  DEFAULT_LOCALE,
  LOCALE_SOURCE_STORAGE_KEY,
  LOCALE_STORAGE_KEY,
  isPersistentLocaleSource,
  normalizeLocale,
  type AppLocale,
} from '@/i18n/types';

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
          'ko-KR': '한국어',
        },
      },
      disclaimer: {
        title: '免责声明',
        body: '您选择的是项目作者运营的仅供临时体验的测试实例。\n\n本项目完全开源免费，因此，最佳使用方式是直接拉取代码运行服务端。这样您可以自由地管理接入模型，自行控制审查开关等。\n\n测试实例会提供一些额度供您体验。限于本人的精力与财力，该实例无法保证稳定。该实例仅供临时评估，数据可能会被删除，切勿存储重要数据。',
        acknowledge: '我已知晓',
        deploy: '一键本地部署',
      },
      mobileGuide: {
        title: '移动端部署引导',
        body: '移动端不支持在本地一键部署服务端。推荐方案：\n\n1. 最佳：在服务器或 PC 上部署 SparkArc 后端，填入公网地址。\n2. 临时：在同一局域网的 PC 上运行后端，然后填入 http://PC的IP:6688。',
        gotIt: '我知道了',
      },
      localDeploy: {
        title: '启动本地后端',
        startButton: '启动本地后端',
        starting: '正在启动本地后端',
        help: '首次使用会下载 main 源码、便携 Python 与受管 Node.js，并自动安装依赖；整个过程可能需要几分钟。保持此窗口打开即可。',
        idle: '等待开始',
        running: '正在准备本地后端...',
        ready: '本地后端已就绪，正在进入工作台',
        failed: '启动失败',
        timeout: '本地后端启动超时。请查看日志，确认网络和防火墙状态后重试。',
        retry: '重试',
        close: '关闭',
        checkUpdate: '检查本地更新',
        checkingUpdate: '正在检查更新',
        updateAvailable: '发现 main 新版本',
        applyUpdateAndStart: '更新并启动',
        upToDate: '本地服务已是最新版本',
        checkUpdateFailed: '无法检查更新',
        launcherUpdateAvailable: 'Launcher 有新版本',
        openRelease: '查看下载',
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
          'ko-KR': '한국어',
        },
      },
      disclaimer: {
        title: 'Disclaimer',
        body: 'You are connecting to a temporary demo instance operated by the project author.\n\nThis project is fully open-source and free. The recommended way is to run your own server from the source code, so you can freely manage models and control content filters.\n\nThe demo instance provides limited quota for evaluation. Due to limited resources, stability cannot be guaranteed. Data may be deleted at any time — please do not store important data.',
        acknowledge: 'I Understand',
        deploy: 'Deploy Locally',
      },
      mobileGuide: {
        title: 'Mobile Deployment Guide',
        body: 'Mobile devices do not support one-click local deployment. Recommended options:\n\n1. Best: Deploy SparkArc backend on a server or PC, then enter the public address.\n2. Temporary: Run the backend on a PC in the same LAN, then enter http://PC-IP:6688.',
        gotIt: 'Got It',
      },
      localDeploy: {
        title: 'Start Local Backend',
        startButton: 'Start Local Backend',
        starting: 'Starting Local Backend',
        help: 'On first use, SparkArc downloads main, a portable Python runtime, and a managed Node.js runtime, then installs dependencies automatically. This can take a few minutes; keep this window open.',
        idle: 'Ready to start',
        running: 'Preparing the local backend...',
        ready: 'Local backend is ready. Entering the workspace',
        failed: 'Startup failed',
        timeout: 'Timed out waiting for the local backend. Check the log, network, and firewall, then retry.',
        retry: 'Retry',
        close: 'Close',
        checkUpdate: 'Check Local Updates',
        checkingUpdate: 'Checking for Updates',
        updateAvailable: 'A New main Version Is Available',
        applyUpdateAndStart: 'Update and Start',
        upToDate: 'The Local Service Is Up to Date',
        checkUpdateFailed: 'Unable to Check for Updates',
        launcherUpdateAvailable: 'A Launcher Update Is Available',
        openRelease: 'View Download',
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
          'ko-KR': '한국어',
        },
      },
      disclaimer: {
        title: '免責事項',
        body: '選択中のサーバーは、プロジェクト作者が運用する体験用のテストインスタンスです。\n\n本プロジェクトは完全にオープンソースかつ無料です。最も推奨される利用方法は、ソースコードから自分のサーバーを実行することです。そうすれば、利用するモデルやコンテンツフィルターを自由に管理できます。\n\nテストインスタンスは体験用の一定の枠を提供しますが、作者のリソースに限りがあるため、安定性は保証できません。データは削除される可能性があるため、重要なデータは保存しないでください。',
        acknowledge: '理解しました',
        deploy: 'ローカルにデプロイ',
      },
      mobileGuide: {
        title: 'モバイルデプロイガイド',
        body: 'モバイル端末ではローカルへのワンクリックデプロイに対応していません。推奨方法：\n\n1. 最善：サーバーまたはPCにSparkArcバックエンドをデプロイし、公网アドレスを入力する。\n2. 臨時：同一LAN内のPCでバックエンドを実行し、http://PCのIP:6688 を入力する。',
        gotIt: 'わかりました',
      },
      localDeploy: {
        title: 'ローカルバックエンドを起動',
        startButton: 'ローカルバックエンドを起動',
        starting: 'ローカルバックエンドを起動中',
        help: '初回は main のソース、ポータブル Python、管理された Node.js をダウンロードし、依存関係を自動でインストールします。数分かかる場合があるため、このウィンドウを開いたままにしてください。',
        idle: '開始待ち',
        running: 'ローカルバックエンドを準備しています...',
        ready: 'ローカルバックエンドの準備が完了しました。ワークスペースへ移動します',
        failed: '起動に失敗しました',
        timeout: 'ローカルバックエンドの起動待ちがタイムアウトしました。ログ、ネットワーク、ファイアウォールを確認して再試行してください。',
        retry: '再試行',
        close: '閉じる',
        checkUpdate: 'ローカル更新を確認',
        checkingUpdate: '更新を確認中',
        updateAvailable: 'main の新しいバージョンがあります',
        applyUpdateAndStart: '更新して起動',
        upToDate: 'ローカルサービスは最新です',
        checkUpdateFailed: '更新を確認できませんでした',
        launcherUpdateAvailable: 'Launcher の新しいバージョンがあります',
        openRelease: 'ダウンロードを見る',
      },
    },
    server: {
      title: 'サーバー設定',
      defaultAddress: '既定アドレス',
      connected: '接続済み',
      unreachable: '未接続 / 到達不可',
      checkAndApply: '확인해 적용',
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
  'ko-KR': {
    launcher: {
      brand: 'SparkArc',
      bootCheckingTitle: '서버 접속을 시도하고 있습니다',
      openServer: '연결 후 작업실 입장',
      autoEnterLabel: '다음 실행 시 서버가 사용 가능하면 자동 입장',
      titlebarMinimize: '최소화',
      titlebarMaximize: '최대화',
      titlebarRestore: '이전 크기로 복원',
      titlebarClose: '닫기',
      localeSwitcher: {
        title: '화면 표시 언어 전환',
        labels: {
          'zh-CN': '中文',
          'en-US': 'EN',
          'ja-JP': '日本語',
          'ko-KR': '한국어',
        },
      },
      disclaimer: {
        title: '면책 조항',
        body: '선택하신 서버는 프로젝트 원작자가 운영하는 임시 체험용 테스트 인스턴스입니다.\n\n본 프로젝트는 완전히 오픈소스이며 무료입니다. 따라서 소스코드를 직접 가져와서 서버를 실행하는 것이 가장 좋은 방법입니다. 그렇게 하면 연동할 모델을 자유롭게 관리하고 필터링 설정을 직접 제어할 수 있습니다.\n\n테스트 인스턴스는 체험을 위한 일부 크레딧을 제공합니다. 다만 개인의 리소스 한계로 인해 서비스의 안정성을 보장할 수 없습니다. 임시 평가용으로 데이터가 언제든지 삭제될 수 있으니 중요한 데이터는 저장하지 마십시오.',
        acknowledge: '이해했습니다',
        deploy: '로컬에 배포',
      },
      mobileGuide: {
        title: '모바일 배포 가이드',
        body: '모바일 기기에서는 로컬 원클릭 배포를 지원하지 않습니다. 권장 방법:\n\n1. 최선: 서버 또는 PC에 SparkArc 백엔드를 배포하고 공개 주소를 입력하세요.\n2. 임시: 동일 LAN의 PC에서 백엔드를 실행한 후 http://PC의IP:6688을 입력하세요.',
        gotIt: '확인',
      },
      localDeploy: {
        title: '로컬 백엔드 시작',
        startButton: '로컬 백엔드 시작',
        starting: '로컬 백엔드 시작 중',
        help: '처음 사용할 때는 main 소스, 휴대용 Python 런타임, 관리형 Node.js 런타임을 내려받고 의존성을 자동 설치합니다. 몇 분 정도 걸릴 수 있으니 이 창을 열어 두세요.',
        idle: '시작 대기 중',
        running: '로컬 백엔드를 준비하고 있습니다...',
        ready: '로컬 백엔드가 준비되었습니다. 작업실로 이동합니다',
        failed: '시작 실패',
        timeout: '로컬 백엔드 시작 대기 시간이 초과되었습니다. 로그, 네트워크, 방화벽 상태를 확인한 뒤 다시 시도하세요.',
        retry: '다시 시도',
        close: '닫기',
        checkUpdate: '로컬 업데이트 확인',
        checkingUpdate: '업데이트 확인 중',
        updateAvailable: '새 main 버전이 있습니다',
        applyUpdateAndStart: '업데이트 후 시작',
        upToDate: '로컬 서비스가 최신 상태입니다',
        checkUpdateFailed: '업데이트를 확인할 수 없습니다',
        launcherUpdateAvailable: '새 Launcher 버전이 있습니다',
        openRelease: '다운로드 보기',
      },
    },
    server: {
      title: '서버 환경 구성',
      defaultAddress: '기본 주소',
      connected: '연결됨',
      unreachable: '연결이 끊어졌거나 반응이 없습니다',
      checkAndApply: '접속 상태 확인 및 등록',
      resetDefault: '기본 주소로 초기화',
      inlinePlaceholder: 'arc.1dea.top',
      status: {
        checking: '연결 상태 조회 중...',
        connectedAndApplied: '연결 성공 및 설정 적용됨',
        restoringDefault: '기본 주소로 복구되었습니다. 다시 접속하세요.',
      },
      errors: {
        emptyAddress: '서버 주소는 비워둘 수 없습니다',
        connectFailed: '연결 실패. 연동 서버 주소와 네트워크 상태를 점검하세요.',
        connectFailedWithDetail: '연결 실패: {detail}',
        currentUnavailable: '현재 저장된 연동 서버가 응답하지 않습니다. 확인 후 다시 시도하세요.',
      },
    },
  },
} as const;

function resolveInitialLocale() {
  if (typeof window === 'undefined') {
    return DEFAULT_LOCALE;
  }

  try {
    const source = localStorage.getItem(LOCALE_SOURCE_STORAGE_KEY);
    const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
    if (stored && isPersistentLocaleSource(source)) return normalizeLocale(stored);
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
    ko: ['ko-KR'],
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
      localStorage.setItem(LOCALE_SOURCE_STORAGE_KEY, 'manual');
    } catch {
      // ignore
    }
  }
}
