/**
 * macOS Dock 风格放大推开效果 composable
 *
 * 核心原理：纯 transform（translateX + scale），零 layout reflow。
 * 鼠标靠近时按钮放大，相邻按钮通过 translateX 被物理推开，
 * 全部在 GPU 合成层完成，不会触发浏览器重排，因此无抖动。
 *
 * 用法：
 *   const { dockRef, onDockEnter, onDockMove, onDockLeave } = useDockMagnify()
 *   // 模板: <div ref="dockRef" @mouseenter="onDockEnter" @mousemove="onDockMove" @mouseleave="onDockLeave">
 *
 * 任何新增按钮只要放在 dockRef 容器内即可自动获得放大推开效果，无需额外配置。
 */

import { ref } from 'vue';

export interface DockMagnifyOptions {
  /** 影响半径（px），鼠标距按钮中心在此范围内会放大，默认 130 */
  maxDist?: number;
  /** 最大放大增量，默认 0.18（即最大 scale = 1.18） */
  maxScaleExtra?: number;
  /** 衰减指数，越大衰减越陡，默认 1.6 */
  falloff?: number;
}

export function useDockMagnify(opts: DockMagnifyOptions = {}) {
  const { maxDist = 130, maxScaleExtra = 0.18, falloff = 1.6 } = opts;

  const dockRef = ref<HTMLElement | null>(null);

  /* ── 快照数据（enter 时一次性采集，move 中只读） ── */
  let baseCenters: number[] = [];
  let baseWidths: number[] = [];
  let baseGap = 0;

  /** 鼠标进入时快照各子元素的原始位置与间距 */
  function onDockEnter() {
    const bar = dockRef.value;
    if (!bar) return;
    const rects = Array.from(bar.children).map(el => (el as HTMLElement).getBoundingClientRect());
    baseCenters = rects.map(r => r.left + r.width / 2);
    baseWidths = rects.map(r => r.width);
    baseGap = rects.length >= 2 ? rects[1].left - rects[0].right : 0;
  }

  /** 鼠标移动时：纯 transform 推开 + 放大，零 reflow */
  function onDockMove(e: MouseEvent) {
    const bar = dockRef.value;
    if (!bar || !baseCenters.length) return;
    const mouseX = e.clientX;
    const children = Array.from(bar.children) as HTMLElement[];
    const n = baseCenters.length;

    /* 1. 计算每个子元素的缩放 */
    const scales: number[] = [];
    for (let i = 0; i < n; i++) {
      const dist = Math.abs(mouseX - baseCenters[i]);
      scales.push(dist < maxDist
        ? 1 + maxScaleExtra * Math.pow(Math.cos((dist / maxDist) * (Math.PI / 2)), falloff)
        : 1);
    }

    /* 2. 锚定最近按钮（pivot），向两侧展开 */
    let pivotIdx = 0;
    let minD = Infinity;
    for (let i = 0; i < n; i++) {
      const d = Math.abs(mouseX - baseCenters[i]);
      if (d < minD) { minD = d; pivotIdx = i; }
    }

    const txs: number[] = new Array(n).fill(0);
    // pivot 不偏移
    // 右侧：维持 baseGap 间距逐个推开
    for (let i = pivotIdx + 1; i < n; i++) {
      const prevCenter = baseCenters[i - 1] + txs[i - 1];
      const idealCenter = prevCenter + (baseWidths[i - 1] * scales[i - 1] + baseWidths[i] * scales[i]) / 2 + baseGap;
      txs[i] = idealCenter - baseCenters[i];
    }
    // 左侧：对称推开
    for (let i = pivotIdx - 1; i >= 0; i--) {
      const nextCenter = baseCenters[i + 1] + txs[i + 1];
      const idealCenter = nextCenter - (baseWidths[i] * scales[i] + baseWidths[i + 1] * scales[i + 1]) / 2 - baseGap;
      txs[i] = idealCenter - baseCenters[i];
    }

    /* 3. 应用纯 transform（translateX + scale），不触碰 margin/padding */
    for (let i = 0; i < n; i++) {
      children[i].style.transform = `translateX(${txs[i].toFixed(2)}px) scale(${scales[i].toFixed(4)})`;
    }
  }

  /** 鼠标离开时：添加 transition 类 → 下一帧清除 transform → 动画结束后移除类 */
  function onDockLeave() {
    baseCenters = [];
    baseWidths = [];
    baseGap = 0;
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
