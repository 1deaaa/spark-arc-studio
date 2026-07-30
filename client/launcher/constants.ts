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

/** localStorage key：用户是否已确认过默认远端免责声明 */
export const LAUNCHER_DEFAULT_REMOTE_ACK_KEY = 'spark_launcher_default_remote_acknowledged';
