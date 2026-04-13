/**
 * Onboarding 模块入口
 *
 * 注册引导场景，导出公共 API。
 * 使用方式：在 App.vue 中调用 setupOnboarding() 即可完成全局注册。
 */
import { getOnboardingEngine } from './engine/OnboardingEngine';
import { desktopWorkspaceScene, mobileFlowScene, mobileChatScene } from './engine/stepDefinitions';
import type { OnboardingScene } from './engine/OnboardingEngine';

// 导出公共 API
export { getOnboardingEngine } from './engine/OnboardingEngine';
export { useOnboarding } from './engine/useOnboarding';
export type { OnboardingStep, OnboardingScene, TooltipPlacement } from './engine/OnboardingEngine';

// 导出场景组件
export { default as DesktopWelcomeScene } from './scenes/desktop/DesktopWelcomeScene.vue';
export { default as DesktopWorkspaceScene } from './scenes/desktop/DesktopWorkspaceScene.vue';
export { default as MobileWelcomeScene } from './scenes/mobile/MobileWelcomeScene.vue';
export { default as MobileFlowScene } from './scenes/mobile/MobileFlowScene.vue';
export { default as MobileChatScene } from './scenes/mobile/MobileChatScene.vue';

// 导出 Overlay（供 App.vue 全局挂载）
export { default as OnboardingOverlay } from './engine/OnboardingOverlay.vue';

// 导出 i18n 词条
export { default as onboardingZhCN } from './i18n/onboarding.zh-CN';
export { default as onboardingEnUS } from './i18n/onboarding.en-US';
export { default as onboardingJaJP } from './i18n/onboarding.ja-JP';

/**
 * 注册所有内置引导场景到引擎
 */
export function setupOnboarding(): void {
  const engine = getOnboardingEngine();
  const scenes: OnboardingScene[] = [
    desktopWorkspaceScene,
    mobileFlowScene,
    mobileChatScene,
  ];
  engine.registerScenes(scenes);
}
