/**
 * useOnboarding - 引导引擎 Composable
 *
 * 提供注册/触发/跳过/重置引导的便捷接口，
 * 宿主组件只需一行调用即可接入引导系统。
 *
 * 持久化 key 包含当前用户 ID，
 * 确保每个用户只引导一次，换用户后重新引导。
 */
import { onUnmounted } from 'vue';
import { getOnboardingEngine, type OnboardingScene } from './OnboardingEngine';
import { getUserId } from '../../services/apiClient';

/** 基础 key 前缀 */
const ONBOARDING_STATE_KEY_PREFIX = 'sparkarc_onboarding_';

interface OnboardingPersistState {
  completedScenes: string[];
  skippedScenes: string[];
}

/**
 * 根据当前用户 ID 生成用户级持久化 key
 * 使用后端返回的 user_id 作为稳定标识，确保不同用户引导状态隔离
 */
function getOnboardingStateKey(): string {
  const userId = getUserId();
  if (!userId) return `${ONBOARDING_STATE_KEY_PREFIX}anonymous`;
  return `${ONBOARDING_STATE_KEY_PREFIX}uid_${userId}`;
}

/** 读取持久化状态 */
export function loadOnboardingState(): OnboardingPersistState {
  try {
    const key = getOnboardingStateKey();
    const raw = localStorage.getItem(key);
    if (raw) return JSON.parse(raw);
  } catch {}
  return { completedScenes: [], skippedScenes: [] };
}

/** 写入持久化状态 */
export function saveOnboardingState(state: OnboardingPersistState): void {
  try {
    const key = getOnboardingStateKey();
    localStorage.setItem(key, JSON.stringify(state));
  } catch {}
}

export function useOnboarding() {
  const engine = getOnboardingEngine();

  /** 注册引导场景 */
  function registerScene(scene: OnboardingScene): void {
    engine.registerScene(scene);
  }

  /** 批量注册 */
  function registerScenes(scenes: OnboardingScene[]): void {
    engine.registerScenes(scenes);
  }

  /** 触发引导（仅首次） */
  function triggerIfFirst(sceneId: string): void {
    // 引擎级防重入：已有引导在运行时不再触发
    if (engine.state.value === 'running') return;
    const state = loadOnboardingState();
    if (state.completedScenes.includes(sceneId) || state.skippedScenes.includes(sceneId)) {
      return;
    }
    // 持久化回调已在 setupOnboarding 注册时绑定，此处只需启动场景
    engine.start(sceneId);
  }

  /** 强制触发引导（无论是否已完成） */
  function trigger(sceneId: string): void {
    engine.start(sceneId);
  }

  /** 重置指定场景的完成状态（允许重看） */
  function resetScene(sceneId: string): void {
    const state = loadOnboardingState();
    state.completedScenes = state.completedScenes.filter(id => id !== sceneId);
    state.skippedScenes = state.skippedScenes.filter(id => id !== sceneId);
    saveOnboardingState(state);
  }

  /** 重置所有引导状态（当前用户） */
  function resetAll(): void {
    saveOnboardingState({ completedScenes: [], skippedScenes: [] });
  }

  /** 检查场景是否已完成 */
  function isSceneCompleted(sceneId: string): boolean {
    return loadOnboardingState().completedScenes.includes(sceneId);
  }

  /** 检查场景是否已跳过 */
  function isSceneSkipped(sceneId: string): boolean {
    return loadOnboardingState().skippedScenes.includes(sceneId);
  }

  // 组件卸载时清理
  onUnmounted(() => {
    // 不销毁引擎（单例跨组件共享），仅停止当前引导
  });

  return {
    engine,
    registerScene,
    registerScenes,
    triggerIfFirst,
    trigger,
    resetScene,
    resetAll,
    isSceneCompleted,
    isSceneSkipped,
  };
}
