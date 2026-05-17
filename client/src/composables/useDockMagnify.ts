/**
 * macOS Dock 风格放大推开效果 composable
 *
 * 核心原理：每个按钮完全独立地基于自己到鼠标的距离做 scale 和 translateX，
 * 距离超过影响半径时直接清空 transform，远端按钮 100% 静止。
 * 任意按钮的 transform 都是 mouseX 的连续函数，且不依赖其他按钮的状态，
 * 因此既不会有"远端闪动"，也不会有 pivot 切换带来的离散跳变。
 *
 * 用法：
 *   const { dockRef, onDockEnter, onDockMove, onDockLeave } = useDockMagnify()
 *   // 模板: <div ref="dockRef" @mouseenter="onDockEnter" @mousemove="onDockMove" @mouseleave="onDockLeave">
 *
 * 任何新增按钮只要放在 dockRef 容器内即可自动获得 Dock 效果，无需额外配置。
 */

import { ref } from 'vue';

export interface DockMagnifyOptions {
  /** 影响半径（px），鼠标距按钮中心 < 此值才会触发缩放/推开；远端按钮完全不动。默认 130 */
  maxDist?: number;
  /** 最大放大增量，鼠标贴在按钮中心时 scale = 1 + maxScaleExtra。默认 0.18 */
  maxScaleExtra?: number;
  /** 邻近按钮被推离鼠标的最大像素数，默认 8 */
  maxPush?: number;
  /** 衰减指数，越大衰减越陡（仅在 maxDist 半径内起作用）。默认 1.6 */
  falloff?: number;
}

export function useDockMagnify(opts: DockMagnifyOptions = {}) {
  const { maxDist = 130, maxScaleExtra = 0.18, maxPush = 8, falloff = 1.6 } = opts;

  const dockRef = ref<HTMLElement | null>(null);

  /** 进入时快照各按钮的原始中心 X，move 中只读，避免每帧 reflow 测量 */
  let baseCenters: number[] = [];

  function onDockEnter() {
    const bar = dockRef.value;
    if (!bar) return;
    baseCenters = Array.from(bar.children).map(el => {
      const r = (el as HTMLElement).getBoundingClientRect();
      return r.left + r.width / 2;
    });
  }

  /** 鼠标移动时：每个按钮独立计算 transform，远端按钮置空保持静止 */
  function onDockMove(e: MouseEvent) {
    const bar = dockRef.value;
    if (!bar || !baseCenters.length) return;
    const mouseX = e.clientX;
    const children = Array.from(bar.children) as HTMLElement[];
    const n = baseCenters.length;

    for (let i = 0; i < n; i++) {
      const delta = mouseX - baseCenters[i];
      const dist = Math.abs(delta);

      // ── 远端按钮：完全静止。清空 transform 后哪怕鼠标在 dock 内乱晃，远端也不会有 1px 闪动 ──
      if (dist >= maxDist) {
        if (children[i].style.transform) children[i].style.transform = '';
        continue;
      }

      // ── 影响半径内：纯局部计算 ──
      // falloffT 在 dist=0 时为 1，在 dist=maxDist 处平滑收敛到 0
      const falloffT = Math.pow(Math.cos((dist / maxDist) * (Math.PI / 2)), falloff);

      // 缩放：贴近鼠标的按钮放大
      const scale = 1 + maxScaleExtra * falloffT;

      // 推离：与鼠标 delta 反号 → 被推开远离鼠标；delta=0 时 push=0，hover 中心不偏移
      // 同时强度被 falloffT 加权，所以接近 maxDist 时 push 也 → 0，与 dist >= maxDist 的"清零"无缝衔接
      const push = -(delta / maxDist) * maxPush * falloffT;

      children[i].style.transform = `translate3d(${push.toFixed(2)}px, 0, 0) scale(${scale.toFixed(4)})`;
    }
  }

  /** 鼠标离开时：添加 transition 类 → 下一帧清除 transform → 动画结束后移除类 */
  function onDockLeave() {
    baseCenters = [];
    const bar = dockRef.value;
    if (!bar) return;
    const children = Array.from(bar.children) as HTMLElement[];

    // 先启用 CSS transition
    children.forEach(el => el.classList.add('dock-leaving'));

    // 下一帧清除 transform，transition 自动产生平滑回弹
    requestAnimationFrame(() => {
      children.forEach(el => {
        el.style.transform = '';
      });
      // 动画结束后移除类，避免影响下次 move 的即时响应
      setTimeout(() => {
        children.forEach(el => el.classList.remove('dock-leaving'));
      }, 250);
    });
  }

  return { dockRef, onDockEnter, onDockMove, onDockLeave };
}
