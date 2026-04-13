/**
 * GSAP 预设动画库
 *
 * 提供引导动画中常用的动画效果，所有动画均为纯程序化实现，
 * 不依赖外部设计资源，方便开发者独立调整。
 */
import gsap from 'gsap';

// ==================== 基础动画 ====================

/** 淡入 */
export function gsapFadeIn(el: HTMLElement, duration = 0.4, delay = 0): gsap.core.Tween {
  return gsap.fromTo(el,
    { opacity: 0 },
    { opacity: 1, duration, delay, ease: 'power2.out' }
  );
}

/** 淡出 */
export function gsapFadeOut(el: HTMLElement, duration = 0.3, delay = 0): gsap.core.Tween {
  return gsap.to(el, { opacity: 0, duration, delay, ease: 'power2.in' });
}

/** 从下方滑入 + 淡入 */
export function gsapSlideUp(el: HTMLElement, distance = 30, duration = 0.5, delay = 0): gsap.core.Tween {
  return gsap.fromTo(el,
    { opacity: 0, y: distance },
    { opacity: 1, y: 0, duration, delay, ease: 'power3.out' }
  );
}

/** 从上方滑入 + 淡入 */
export function gsapSlideDown(el: HTMLElement, distance = 30, duration = 0.5, delay = 0): gsap.core.Tween {
  return gsap.fromTo(el,
    { opacity: 0, y: -distance },
    { opacity: 1, y: 0, duration, delay, ease: 'power3.out' }
  );
}

/** 从左滑入 + 淡入 */
export function gsapSlideFromLeft(el: HTMLElement, distance = 60, duration = 0.5, delay = 0): gsap.core.Tween {
  return gsap.fromTo(el,
    { opacity: 0, x: -distance },
    { opacity: 1, x: 0, duration, delay, ease: 'power3.out' }
  );
}

/** 从右滑入 + 淡入 */
export function gsapSlideFromRight(el: HTMLElement, distance = 60, duration = 0.5, delay = 0): gsap.core.Tween {
  return gsap.fromTo(el,
    { opacity: 0, x: distance },
    { opacity: 1, x: 0, duration, delay, ease: 'power3.out' }
  );
}

// ==================== 特效动画 ====================

/** 缩放弹入（带弹性） */
export function gsapScaleIn(el: HTMLElement, duration = 0.5, delay = 0): gsap.core.Tween {
  return gsap.fromTo(el,
    { opacity: 0, scale: 0.5 },
    { opacity: 1, scale: 1, duration, delay, ease: 'back.out(1.7)' }
  );
}

/** 脉冲效果（放大 → 回弹 → 呼吸） */
export function gsapPulse(el: HTMLElement, duration = 1.5): gsap.core.Timeline {
  const tl = gsap.timeline();
  tl.to(el, { scale: 1.15, duration: duration * 0.3, ease: 'power2.out' });
  tl.to(el, { scale: 1, duration: duration * 0.2, ease: 'power2.in' });
  tl.to(el, { scale: 1.05, duration: duration * 0.25, ease: 'sine.inOut' });
  tl.to(el, { scale: 1, duration: duration * 0.25, ease: 'sine.inOut' });
  return tl;
}

/** 打字机效果 */
export function gsapTypewriter(
  el: HTMLElement,
  text: string,
  speed = 50,
  delay = 0
): gsap.core.Timeline {
  const tl = gsap.timeline({ delay });
  // 先清空文本
  tl.set(el, { textContent: '' });
  // 逐字添加
  for (let i = 0; i < text.length; i++) {
    tl.to(el, {
      textContent: text.substring(0, i + 1),
      duration: speed / 1000,
    });
  }
  return tl;
}

/** SVG 路径描边动画 */
export function gsapStrokeDraw(
  svgPath: SVGPathElement | HTMLElement,
  duration = 1.5,
  delay = 0
): gsap.core.Tween {
  const el = svgPath as SVGPathElement;
  const length = el.getTotalLength?.() ?? 100;
  return gsap.fromTo(el,
    { strokeDasharray: length, strokeDashoffset: length },
    { strokeDashoffset: 0, duration, delay, ease: 'power2.inOut' }
  );
}

/** 粒子扩散效果（从中心向外） */
export function gsapParticleBurst(
  container: HTMLElement,
  count = 12,
  color = '#ffaa40',
  duration = 1,
  delay = 0
): gsap.core.Timeline {
  const tl = gsap.timeline({ delay });
  for (let i = 0; i < count; i++) {
    const particle = document.createElement('div');
    particle.style.cssText = `
      position: absolute;
      width: 4px; height: 4px;
      border-radius: 50%;
      background: ${color};
      top: 50%; left: 50%;
      transform: translate(-50%, -50%);
    `;
    container.appendChild(particle);

    const angle = (Math.PI * 2 / count) * i;
    const distance = 40 + Math.random() * 60;

    tl.to(particle, {
      x: Math.cos(angle) * distance,
      y: Math.sin(angle) * distance,
      opacity: 0,
      scale: 0.3,
      duration: duration * (0.7 + Math.random() * 0.3),
      ease: 'power2.out',
      onComplete: () => particle.remove(),
    }, 0);
  }
  return tl;
}

/** 连线流动动画（点沿线移动） */
export function gsapFlowAlongPath(
  dot: HTMLElement,
  path: SVGPathElement,
  duration = 2,
  delay = 0
): gsap.core.Tween {
  const length = path.getTotalLength?.() ?? 100;
  return gsap.fromTo(dot,
    { opacity: 0 },
    {
      opacity: 1,
      duration: duration * 0.1,
      delay,
      ease: 'power2.out',
      modifiers: {
        x: (i: number) => {
          const progress = gsap.utils.clamp(0, 1, i);
          const point = path.getPointAtLength(progress * length);
          return point.x + 'px';
        },
        y: (i: number) => {
          const progress = gsap.utils.clamp(0, 1, i);
          const point = path.getPointAtLength(progress * length);
          return point.y + 'px';
        },
      },
    }
  );
}

/** 依次入场动画（一组元素依次出现） */
export function gsapStaggerIn(
  elements: HTMLElement[],
  stagger = 0.1,
  duration = 0.4,
  delay = 0
): gsap.core.Tween {
  return gsap.fromTo(elements,
    { opacity: 0, y: 20, scale: 0.9 },
    { opacity: 1, y: 0, scale: 1, duration, delay, stagger, ease: 'back.out(1.4)' }
  );
}

/** 呼吸光环效果 */
export function gsapBreathingGlow(
  el: HTMLElement,
  color = '#ffaa40',
  duration = 2,
): gsap.core.Timeline {
  const tl = gsap.timeline({ repeat: -1 });
  tl.to(el, {
    boxShadow: `0 0 20px ${color}80, 0 0 40px ${color}40`,
    duration: duration / 2,
    ease: 'sine.inOut',
  });
  tl.to(el, {
    boxShadow: `0 0 8px ${color}40, 0 0 16px ${color}20`,
    duration: duration / 2,
    ease: 'sine.inOut',
  });
  return tl;
}
