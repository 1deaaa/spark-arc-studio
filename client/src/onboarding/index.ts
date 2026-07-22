/**
 * Onboarding 模块入口
 *
 * 注册引导场景，导出公共 API。
 * 使用方式：在 App.vue 中调用 setupOnboarding() 即可完成全局注册。
 */
import { getOnboardingEngine } from './engine/OnboardingEngine';
import { desktopPageScenes, desktopWorkspaceScene, mobileWorkspaceScene } from './engine/stepDefinitions';
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
 * 场景组定义：同组场景完成/跳过任一后，其余场景也标记完成/跳过。
 * 用于桌面端和移动端引导联动，避免切换布局后重复触发。
 */
const ONBOARDING_SCENE_GROUPS: string[][] = [
  ['desktop-workspace', 'mobile-workspace'],
];

/**
 * 查找场景所在组，返回同组所有场景 ID（含自身）
 */
function getSceneGroup(sceneId: string): string[] {
  return ONBOARDING_SCENE_GROUPS.find(g => g.includes(sceneId)) || [sceneId];
}

/**
 * 为场景绑定完成/跳过持久化回调（含场景组联动）
 */
function bindPersistenceCallbacks(scene: OnboardingScene): void {
  const sceneId = scene.id;
  const group = getSceneGroup(sceneId);
  const origComplete = scene.onComplete;
  const origSkip = scene.onSkip;
  scene.onComplete = () => {
    const s = loadOnboardingState();
    for (const id of group) {
      if (!s.completedScenes.includes(id)) {
        s.completedScenes.push(id);
      }
    }
    saveOnboardingState(s);
    origComplete?.();
  };
  scene.onSkip = () => {
    const s = loadOnboardingState();
    for (const id of group) {
      if (!s.skippedScenes.includes(id)) {
        s.skippedScenes.push(id);
      }
    }
    saveOnboardingState(s);
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
    ...desktopPageScenes,
  ];
  // 注册前绑定持久化回调，确保完成/跳过时状态一定会写入 localStorage
  scenes.forEach(bindPersistenceCallbacks);
  engine.registerScenes(scenes);
}
