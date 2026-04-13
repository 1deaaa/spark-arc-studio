/**
 * ScrollTrigger 配置 - 移动端滚动驱动动画
 *
 * 配合 GSAP ScrollTrigger 插件，实现移动端"向下刷"式的引导动画。
 * 每张 FlowCard 进入视口时触发对应动画效果。
 */
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

export interface ScrollSceneConfig {
  /** 触发元素（CSS 选择器或元素） */
  trigger: string | HTMLElement;
  /** 动画目标元素 */
  animTargets: string | HTMLElement[];
  /** 动画函数 */
  animate: (targets: HTMLElement[], tl: gsap.core.Timeline) => void;
  /** 起始位置 */
  start?: string;
  /** 结束位置 */
  end?: string;
  /** 是否只触发一次 */
  once?: boolean;
  /** 是否固定 */
  pin?: boolean;
  /** 持续时间（基于滚动距离） */
  scrub?: boolean | number;
}

/** 创建滚动驱动动画场景 */
export function createScrollScene(config: ScrollSceneConfig): ScrollTrigger {
  const {
    trigger,
    animTargets,
    animate,
    start = 'top 80%',
    end = 'bottom 20%',
    once = true,
    pin = false,
    scrub = false,
  } = config;

  const tl = gsap.timeline({
    scrollTrigger: {
      trigger,
      start,
      end,
      once,
      pin,
      scrub,
    } as ScrollTrigger.Vars,
  });

  // 解析目标元素
  const targets = typeof animTargets === 'string'
    ? Array.from(document.querySelectorAll<HTMLElement>(animTargets))
    : animTargets;

  animate(targets, tl);

  return tl.scrollTrigger as ScrollTrigger;
}

/** 批量创建移动端 FlowCard 滚动动画 */
export function createMobileFlowScrollAnimations(
  containerSelector: string
): ScrollTrigger[] {
  const triggers: ScrollTrigger[] = [];
  const cards = document.querySelectorAll<HTMLElement>(`${containerSelector} .flow-card`);

  cards.forEach((card, index) => {
    const stepId = `step-${index + 1}`;
    const animTargets = card.querySelectorAll<HTMLElement>('.onboarding-anim-target');

    if (animTargets.length === 0) return;

    const trigger = ScrollTrigger.create({
      trigger: card,
      start: 'top 60%',
      end: 'bottom 40%',
      once: true,
      onEnter: () => {
        const tl = gsap.timeline();
        // 依次入场
        tl.fromTo(animTargets,
          { opacity: 0, y: 30, scale: 0.95 },
          {
            opacity: 1,
            y: 0,
            scale: 1,
            duration: 0.6,
            stagger: 0.15,
            ease: 'back.out(1.4)',
          }
        );
      },
    });

    triggers.push(trigger);
  });

  return triggers;
}

/** 清理所有 ScrollTrigger */
export function killAllScrollTriggers(): void {
  ScrollTrigger.getAll().forEach(st => st.kill());
}
