/**
 * API Service Entry
 * 聚合所有子模块导出，保持对旧代码的兼容性，同时提供模块化支持。
 */

export * from './apiClient';
export * from './authService';
export * from './projectService';
export * from './storyService';
export * from './aiService';
export * from './chatService';

// 特殊导出（如果某些老代码显式使用了 default）
import { fetchWithAuth } from './apiClient';
export default {
  fetchWithAuth
};
