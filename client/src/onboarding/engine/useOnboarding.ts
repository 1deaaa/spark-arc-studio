/**
 * useOnboarding - 引导引擎 Composable
 *
 * 提供注册/触发/跳过/重置引导的便捷接口，
 * 宿主组件只需一行调用即可接入引导系统。
 */
import { onUnmounted } from 'vue';
import { getOnboardingEngine, type OnboardingScene } from './OnboardingEngine';

const ONBOARDING_STATE_KEY = 'sparkarc_onboarding_state';

interface OnboardingPersistState {
  completedScenes: string[];
  skippedScenes: string[];
}

/** 读取持久化状态 */
function loadState(): OnboardingPersistState {
  try {
    const raw = localStorage.getItem(ONBOARDING_STATE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return { completedScenes: [], skippedScenes: [] };
}

/** 写入持久化状态 */
function saveState(state: OnboardingPersistState): void {
  try {
    localStorage.setItem(ONBOARDING_STATE_KEY, JSON.stringify(state));
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
    const state = loadState();
    if (state.completedScenes.includes(sceneId) || state.skippedScenes.includes(sceneId)) {
      return;
    }
    // 注册完成/跳过回调以持久化
    const scene = engine['scenes'].get(sceneId);
    if (scene) {
      const origComplete = scene.onComplete;
      const origSkip = scene.onSkip;
      scene.onComplete = () => {
        const s = loadState();
        if (!s.completedScenes.includes(sceneId)) {
          s.completedScenes.push(sceneId);
          saveState(s);
        }
        origComplete?.();
      };
      scene.onSkip = () => {
        const s = loadState();
        if (!s.skippedScenes.includes(sceneId)) {
          s.skippedScenes.push(sceneId);
          saveState(s);
        }
        origSkip?.();
      };
    }
    engine.start(sceneId);
  }

  /** 强制触发引导（无论是否已完成） */
  function trigger(sceneId: string): void {
    engine.start(sceneId);
  }

  /** 重置指定场景的完成状态（允许重看） */
  function resetScene(sceneId: string): void {
    const state = loadState();
    state.completedScenes = state.completedScenes.filter(id => id !== sceneId);
    state.skippedScenes = state.skippedScenes.filter(id => id !== sceneId);
    saveState(state);
  }

  /** 重置所有引导状态 */
  function resetAll(): void {
    saveState({ completedScenes: [], skippedScenes: [] });
  }

  /** 检查场景是否已完成 */
  function isSceneCompleted(sceneId: string): boolean {
    return loadState().completedScenes.includes(sceneId);
  }

  /** 检查场景是否已跳过 */
  function isSceneSkipped(sceneId: string): boolean {
    return loadState().skippedScenes.includes(sceneId);
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
