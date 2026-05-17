/**
 * 全局自动保存响应式状态
 *
 * 问题：computed(() => localStorage.getItem(...)) 不会响应 localStorage 变化，
 * 导致切换开关后其他组件的 autoSaveEnabled 不更新。
 *
 * 方案：用 reactive 单例 + setter 统一管理，所有组件从此模块读取/写入。
 */
import { reactive, computed } from 'vue';

const state = reactive({
  enabled: localStorage.getItem('autoSaveEnabled') !== 'false',
});

/** 响应式只读计算属性 */
export const autoSaveEnabled = computed(() => state.enabled);

/** 切换自动保存（同步更新 localStorage + 响应式状态） */
export function setAutoSaveEnabled(val: boolean) {
  state.enabled = val;
  localStorage.setItem('autoSaveEnabled', String(val));
}
