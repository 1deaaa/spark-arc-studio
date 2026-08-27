/**
 * 聊天正文必须保留完整 DOM，保证长消息可回看、选择和复制。
 * markstream-vue 约定 0 表示关闭节点虚拟化；长文仍由 Worker 和分批渲染负责降载。
 */
export const CHAT_MARKDOWN_MAX_LIVE_NODES = 0;
