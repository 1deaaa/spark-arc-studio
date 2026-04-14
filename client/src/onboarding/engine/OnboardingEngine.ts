/**
 * OnboardingEngine - 新手引导引擎核心
 *
 * 职责：步骤编排、状态机、GSAP Timeline 管理
 * 设计原则：引导逻辑与 UI 逻辑完全分离，宿主组件零改动
 */
import { ref, type Ref } from 'vue';
import gsap from 'gsap';

// ==================== 类型定义 ====================

export type TooltipPlacement = 'top' | 'bottom' | 'left' | 'right' | 'center';

export interface OnboardingStep {
  /** 唯一标识 */
  id: string;
  /** CSS 选择器或动态获取目标元素 */
  target: string | (() => Element | null);
  /** 气泡位置 */
  placement: TooltipPlacement;
  /** i18n key（标题） */
  titleKey: string;
  /** i18n key（描述） */
  descKey: string;
  /** 是否高亮目标元素 */
  spotlight?: boolean;
  /** 高亮区域 padding */
  spotlightPadding?: number;
  /** 进入前钩子（可切换视图、展开面板等） */
  beforeEnter?: () => Promise<void>;
  /** 离开后钩子 */
  afterLeave?: () => Promise<void>;
  /** 是否滚动到目标 */
  scrollIntoView?: boolean;
  /** 是否允许交互穿透高亮区域（用户可点击目标元素） */
  allowInteraction?: boolean;
  /** 自定义 GSAP 入场动画（覆盖默认） */
  enterAnimation?: (el: HTMLElement) => gsap.core.Tween;
  /** 自定义 GSAP 退场动画（覆盖默认） */
  leaveAnimation?: (el: HTMLElement) => gsap.core.Tween;
}

export interface OnboardingScene {
  /** 场景唯一标识 */
  id: string;
  /** 步骤列表 */
  steps: OnboardingStep[];
  /** 场景完成回调 */
  onComplete?: () => void;
  /** 场景跳过回调 */
  onSkip?: () => void;
}

export type EngineState = 'idle' | 'running' | 'paused' | 'completed';

// ==================== 引导引擎 ====================

export class OnboardingEngine {
  /** 当前引擎状态 */
  readonly state: Ref<EngineState> = ref('idle');

  /** 当前步骤索引 */
  readonly currentStepIndex: Ref<number> = ref(0);

  /** 当前活跃场景 */
  readonly currentSceneId: Ref<string | null> = ref(null);

  /** 当前步骤的目标元素矩形 */
  readonly targetRect: Ref<DOMRect | null> = ref(null);

  /** 总步骤数 */
  readonly totalSteps: Ref<number> = ref(0);

  /** 是否在引导中 */
  readonly isActive: Ref<boolean> = ref(false);

  /** 是否允许交互穿透（高亮区域可点击） */
  readonly allowInteraction: Ref<boolean> = ref(false);

  /** 步骤切换过渡中（Tooltip/Spotlight 应隐藏） */
  readonly isTransitioning: Ref<boolean> = ref(false);

  // 内部状态
  private scenes: Map<string, OnboardingScene> = new Map();
  private currentScene: OnboardingScene | null = null;
  private timeline: gsap.core.Timeline | null = null;
  private resizeObserver: ResizeObserver | null = null;
  private scrollHandler: (() => void) | null = null;

  /** 当前步骤（公开只读） */
  get currentStep(): OnboardingStep | null {
    return this.currentScene?.steps[this.currentStepIndex.value] ?? null;
  }

  /** 注册引导场景 */
  registerScene(scene: OnboardingScene): void {
    this.scenes.set(scene.id, scene);
  }

  /** 批量注册 */
  registerScenes(scenes: OnboardingScene[]): void {
    scenes.forEach(s => this.registerScene(s));
  }

  /** 启动指定场景 */
  async start(sceneId: string): Promise<void> {
    const scene = this.scenes.get(sceneId);
    if (!scene) {
      console.warn(`[OnboardingEngine] 场景 "${sceneId}" 未注册`);
      return;
    }
    if (this.state.value === 'running') {
      console.warn('[OnboardingEngine] 已有引导正在运行，请先完成或跳过');
      return;
    }

    this.currentScene = scene;
    this.currentSceneId.value = sceneId;
    this.currentStepIndex.value = 0;
    this.totalSteps.value = scene.steps.length;
    this.state.value = 'running';
    this.isActive.value = true;

    this._startTracking();

    // 执行第一步
    await this._showStep(0);
  }

  /** 下一步 */
  async next(): Promise<void> {
    if (this.state.value !== 'running' || !this.currentScene) return;
    const nextIdx = this.currentStepIndex.value + 1;
    if (nextIdx >= this.currentScene.steps.length) {
      await this.complete();
      return;
    }
    this.isTransitioning.value = true;
    await this._hideCurrentStep();
    this.currentStepIndex.value = nextIdx;
    await this._showStep(nextIdx);
    this.isTransitioning.value = false;
  }

  /** 上一步 */
  async prev(): Promise<void> {
    if (this.state.value !== 'running' || !this.currentScene) return;
    const prevIdx = this.currentStepIndex.value - 1;
    if (prevIdx < 0) return;
    this.isTransitioning.value = true;
    await this._hideCurrentStep();
    this.currentStepIndex.value = prevIdx;
    await this._showStep(prevIdx);
    this.isTransitioning.value = false;
  }

  /** 跳过当前场景 */
  async skip(): Promise<void> {
    if (!this.currentScene) return;
    await this._hideCurrentStep();
    this.currentScene.onSkip?.();
    this._reset();
  }

  /** 完成当前场景 */
  async complete(): Promise<void> {
    if (!this.currentScene) return;
    await this._hideCurrentStep();
    this.currentScene.onComplete?.();
    this._reset();
  }

  /** 暂停 */
  pause(): void {
    this.state.value = 'paused';
    this.timeline?.pause();
  }

  /** 恢复 */
  resume(): void {
    this.state.value = 'running';
    this.timeline?.resume();
  }

  /** 销毁引擎，清理所有资源 */
  destroy(): void {
    this._stopTracking();
    this.timeline?.kill();
    this.timeline = null;
    this._reset();
  }

  /** 获取当前步骤定义 */
  getCurrentStep(): OnboardingStep | null {
    if (!this.currentScene) return null;
    return this.currentScene.steps[this.currentStepIndex.value] ?? null;
  }

  // ==================== 内部方法 ====================

  private _reset(): void {
    this.state.value = 'idle';
    this.isActive.value = false;
    this.currentScene = null;
    this.currentSceneId.value = null;
    this.currentStepIndex.value = 0;
    this.totalSteps.value = 0;
    this.targetRect.value = null;
    this.allowInteraction.value = false;
    this.isTransitioning.value = false;
    this.timeline?.kill();
    this.timeline = null;
  }

  private async _showStep(index: number): Promise<void> {
    if (!this.currentScene) return;
    const step = this.currentScene.steps[index];
    if (!step) return;

    // 执行 beforeEnter 钩子
    if (step.beforeEnter) {
      await step.beforeEnter();
    }

    // 获取目标元素并计算位置
    this._updateTargetRect(step);

    // 滚动到目标
    if (step.scrollIntoView) {
      const el = this._resolveElement(step.target);
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      // 等待滚动完成
      await new Promise(r => setTimeout(r, 400));
      this._updateTargetRect(step);
    }

    // 高亮区域允许交互穿透
    this.allowInteraction.value = step.allowInteraction ?? false;
  }

  private async _hideCurrentStep(): Promise<void> {
    if (!this.currentScene) return;
    const step = this.currentScene.steps[this.currentStepIndex.value];
    if (step?.afterLeave) {
      await step.afterLeave();
    }
    this.targetRect.value = null;
    this.allowInteraction.value = false;
  }

  private _resolveElement(target: string | (() => Element | null)): Element | null {
    if (typeof target === 'string') {
      return document.querySelector(target);
    }
    return target();
  }

  private _updateTargetRect(step: OnboardingStep): void {
    const el = this._resolveElement(step.target);
    if (el) {
      const padding = step.spotlightPadding ?? 8;
      const rect = el.getBoundingClientRect();
      // 扩展矩形以包含 padding
      this.targetRect.value = DOMRect.fromRect({
        x: rect.left - padding,
        y: rect.top - padding,
        width: rect.width + padding * 2,
        height: rect.height + padding * 2,
      }) as DOMRect;
    } else {
      this.targetRect.value = null;
    }
  }

  /** 启动位置追踪（窗口 resize / 滚动时更新高亮位置） */
  private _startTracking(): void {
    this.scrollHandler = () => {
      const step = this.getCurrentStep();
      if (step) this._updateTargetRect(step);
    };
    this.resizeObserver = new ResizeObserver(() => {
      const step = this.getCurrentStep();
      if (step) this._updateTargetRect(step);
    });

    window.addEventListener('scroll', this.scrollHandler, true);
    this.resizeObserver.observe(document.body);
  }

  /** 停止位置追踪 */
  private _stopTracking(): void {
    if (this.scrollHandler) {
      window.removeEventListener('scroll', this.scrollHandler, true);
      this.scrollHandler = null;
    }
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
      this.resizeObserver = null;
    }
  }
}

// ==================== 单例 ====================

let _instance: OnboardingEngine | null = null;

export function getOnboardingEngine(): OnboardingEngine {
  if (!_instance) {
    _instance = new OnboardingEngine();
  }
  return _instance;
}
