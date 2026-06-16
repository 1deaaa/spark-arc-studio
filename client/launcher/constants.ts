/**
 * Launcher 全局常量。
 *
 * 这里存放 launcher 专用的、可能随版本调整的常量。
 * 注意：不要把 API 密钥等敏感信息放进来。
 */

/** 默认远端体验服务器 */
export const LAUNCHER_DEFAULT_REMOTE_SERVER = 'https://arc.1dea.top';

/** 本地后端默认探测端口 */
export const LAUNCHER_LOCAL_PORTS = [6688, 7788] as const;

/** 本地后端目录候选名（从 launcher 可执行文件位置向上查找） */
export const LAUNCHER_LOCAL_BACKEND_DIR_NAMES = ['server', 'sparkarc-server'] as const;

/** 用户目录状态文件名（Tauri fs 插件使用） */
export const LAUNCHER_SERVICE_RECORD_FILE = '.sparkarc/service.json';

/** 项目 GitHub 仓库地址 */
export const LAUNCHER_GITHUB_REPO_URL = 'https://github.com/1deaaa/sparkarc.git';

/** localStorage key：用户是否已确认过默认远端免责声明 */
export const LAUNCHER_DEFAULT_REMOTE_ACK_KEY = 'spark_launcher_default_remote_acknowledged';
