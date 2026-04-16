/**
 * Onboarding 模块入口
 *
 * 注册引导场景，导出公共 API。
 * 使用方式：在 App.vue 中调用 setupOnboarding() 即可完成全局注册。
 */
import { getOnboardingEngine } from './engine/OnboardingEngine';
import { desktopWorkspaceScene, mobileWorkspaceScene } from './engine/stepDefinitions';
import type { OnboardingScene } from './engine/OnboardingEngine';
import { loadOnboardingState, saveOnboardingState } from './engine/useOnboarding';

// 导出公共 API
export { getOnboardingEngine } from './engine/OnboardingEngine';
export { useOnboarding } from './engine/useOnboarding';
export type { OnboardingStep, OnboardingScene, TooltipPlacement } from './engine/OnboardingEngine';

// 导出场景组件
export { default as DesktopWelcomeScene } from './scenes/desktop/DesktopWelcomeScene.vue';
export { default as DesktopWorkspaceScene } from './scenes/desktop/DesktopWorkspaceScene.vue';
export { default as MobileWelcomeScene } from './scenes/mobile/MobileWelcomeScene.vue';

// 导出 Overlay（供 App.vue 全局挂载）
export { default as OnboardingOverlay } from './engine/OnboardingOverlay.vue';

// 导出 i18n 词条
export { default as onboardingZhCN } from './i18n/onboarding.zh-CN';
export { default as onboardingEnUS } from './i18n/onboarding.en-US';
export { default as onboardingJaJP } from './i18n/onboarding.ja-JP';

/**
 * 为场景绑定完成/跳过持久化回调
 */
function bindPersistenceCallbacks(scene: OnboardingScene): void {
  const sceneId = scene.id;
  const origComplete = scene.onComplete;
  const origSkip = scene.onSkip;
  scene.onComplete = () => {
    const s = loadOnboardingState();
    if (!s.completedScenes.includes(sceneId)) {
      s.completedScenes.push(sceneId);
      saveOnboardingState(s);
    }
    origComplete?.();
  };
  scene.onSkip = () => {
    const s = loadOnboardingState();
    if (!s.skippedScenes.includes(sceneId)) {
      s.skippedScenes.push(sceneId);
      saveOnboardingState(s);
    }
    origSkip?.();
  };
}

/**
 * 注册所有内置引导场景到引擎
 */
export function setupOnboarding(): void {
  const engine = getOnboardingEngine();
  const scenes: OnboardingScene[] = [
    desktopWorkspaceScene,
    mobileWorkspaceScene,
  ];
  // 注册前绑定持久化回调，确保完成/跳过时状态一定会写入 localStorage
  scenes.forEach(bindPersistenceCallbacks);
  engine.registerScenes(scenes);
}
