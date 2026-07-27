<template>
  <!-- 触发器：AgentAvatar 自身就是原生按钮，不再额外包一层外壳 -->
  <AgentAvatar
    ref="triggerRef"
    as="button"
    type="button"
    class="picker-trigger"
    :class="[$attrs.class, { 'is-open': isOpen }]"
    :agent-id="value"
    :size="26"
    :disabled="disabled"
    :aria-haspopup="'listbox'"
    :aria-expanded="isOpen"
    :aria-label="`${currentName} (${t('components.agentRadialPicker.switchAgent')})`"
    :title="`${currentName} · ${t('components.agentRadialPicker.switchAgent')}`"
    @pointerdown="onTriggerPointerDown"
    @click="onTriggerClick"
    @keydown="onTriggerKeyDown"
  />

  <!-- 轮盘 -->
  <Teleport to="body">
      <Transition
        name="agent-radial-fade"
        @after-enter="onOverlayAfterEnter"
        @before-leave="onOverlayBeforeLeave"
        @after-leave="onOverlayAfterLeave"
      >
        <div
          v-if="isOpen"
          ref="overlayRef"
          class="agent-radial-overlay"
          :class="{ 'is-stable': overlayStable }"
          @pointerdown.self="onOverlayPointerDown"
        >
          <div
            ref="wheelRef"
            class="agent-radial-wheel"
            :style="wheelStyle"
            role="listbox"
            :aria-label="t('components.agentRadialPicker.label')"
          >
            <!-- 高拟真 SVG 连接线画布：使用实例隔离的 unique ID，防止多组件全局冲突导致渐变失效 -->
            <svg class="radial-connector-svg" viewBox="-300 -300 600 600" aria-hidden="true">
              <defs>
                <!-- 全色域动态渐变：从 sourceColor 渐变至 targetColor -->
                <linearGradient
                  :id="gradientId"
                  x1="0"
                  y1="0"
                  :x2="connectorEnd.x"
                  :y2="connectorEnd.y"
                  gradientUnits="userSpaceOnUse"
                >
                  <stop offset="0%" :stop-color="sourceColor" stop-opacity="1" />
                  <stop offset="100%" :stop-color="targetColor" stop-opacity="0.95" />
                </linearGradient>
                
                <!-- 霓虹发光滤镜：改用 userSpaceOnUse 空间，防止水平/垂直直线因 boundingBox 宽/高为 0 导致滤镜被截断坍塌 -->
                <filter
                  :id="glowId"
                  filterUnits="userSpaceOnUse"
                  x="-300"
                  y="-300"
                  width="600"
                  height="600"
                >
                  <feGaussianBlur stdDeviation="8" result="blur1" />
                  <feGaussianBlur stdDeviation="3" result="blur2" />
                  <feMerge>
                    <feMergeNode in="blur1" />
                    <feMergeNode in="blur2" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>

              <!-- 背景轨道：引导线 -->
              <g class="connector-tracks" v-if="pointerDownOnTrigger || isPointerDragging || hoverIndex >= 0">
                <circle cx="0" cy="0" :r="effectiveRadius" class="track-circle" />
                <line
                  v-for="(opt, idx) in displayOptions"
                  :key="`track-${opt.value}`"
                  x1="0"
                  y1="0"
                  :x2="slotOffset(idx).dx"
                  :y2="slotOffset(idx).dy"
                  class="track-ray"
                  :class="{ 'is-active': hoverIndex === idx }"
                  :style="{ '--slot-color': getAgentColor(opt.value) }"
                />
              </g>

              <!-- 动态发光连接线 -->
              <line
                v-if="shouldShowConnector"
                x1="0"
                y1="0"
                :x2="connectorEnd.x"
                :y2="connectorEnd.y"
                class="connector-line"
                :stroke="`url(#${gradientId})`"
                :filter="`url(#${glowId})`"
              />

              <!-- 连接末端微粒：同步目标主题色 -->
              <circle
                v-if="shouldShowConnector"
                :cx="connectorEnd.x"
                :cy="connectorEnd.y"
                r="5.5"
                class="connector-dot"
                :style="{ '--dot-color': targetColor }"
                :filter="`url(#${glowId})`"
              />
            </svg>

            <!-- 中央枢纽：当前选中的 Agent 头像（支持抓取拖拽，主题色呼吸光晕） -->
            <div
              class="agent-radial-hub"
              :class="{ 'is-active': pointerDownOnTrigger }"
              :style="{ '--hub-color': sourceColor }"
              @pointerdown.stop="onHubPointerDown"
            >
              <AgentAvatar
                :agent-id="value"
                :size="isCompactViewport ? 36 : 44"
              />
              <div class="hub-pulse-ring"></div>
            </div>

            <!-- 扇片：圆形头像 + 放射状散开的名字 -->
            <button
              v-for="(opt, idx) in displayOptions"
              :key="opt.value"
              :ref="(el) => setSlotRef(idx, el as HTMLElement | null)"
              type="button"
              class="agent-radial-slot"
              :class="{
                'is-current': opt.value === value,
                'is-hover': hoverIndex === idx,
                'is-disabled': isOptionDisabled(opt),
              }"
              :style="slotStyle(idx, opt.value)"
              :disabled="isOptionDisabled(opt)"
              :aria-label="slotAriaLabel(opt)"
              :title="slotTitle(opt)"
              role="option"
              :aria-selected="opt.value === value"
              @click.stop="onSlotClick(opt)"
              @pointerdown.stop="onSlotPointerDown($event, idx)"
              @pointerenter="hoverIndex = idx"
              @pointerleave="hoverIndex = -1"
            >
              <AgentAvatar
                :agent-id="opt.value"
                :size="effectiveSlotSize"
                :disabled="isOptionDisabled(opt)"
              />
              <span
                v-if="opt.running"
                class="agent-radial-slot-running"
                aria-hidden="true"
              />
              <span class="agent-radial-slot-name">{{ opt.label }}</span>
            </button>
          </div>
        </div>
      </Transition>
  </Teleport>
</template>

<script setup lang="ts">
defineOptions({ inheritAttrs: false });

/**
 * AgentRadialPicker.vue —— Agent 轮盘选择器
 *
 * 缺陷修复版：
 * 1. 彻底解决多轮盘全局 SVG ID 冲突：每个组件实例随机生成 instanceId，完全隔离 <linearGradient> 和 <filter>，保证渐变色永久生效。
 * 2. 移除不稳定的 SVG 几何属性 CSS 过渡：移除 x2/y2/cx/cy 的 transition，防止部分浏览器中渲染管道断裂降级为“小细线”，提供 100% 稳定的 crisp 精致光流。
 * 3. 动态色彩虹桥与 HSL 空间无损线性混合。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import AgentAvatar from '@/components/share/AgentAvatar.vue';
import { useAgentRegistry } from '@/composables/useAgentRegistry';
import { TABLET_MAX_WIDTH } from '@/utils/responsive';

type RadialOption = {
  value: string;
  label: string;
  disabled?: boolean;
  disabledReason?: string;
  running?: boolean;
  [k: string]: unknown;
};

const props = defineProps({
  value: { type: String, default: '' },
  options: { type: Array as PropType<RadialOption[]>, default: () => [] },
  disabled: { type: Boolean, default: false },
  sweepAngle: { type: Number, default: 180 },
  startAngle: { type: Number, default: -45 },
  radius: { type: Number, default: 130 },
  slotAvatarSize: { type: Number, default: 40 },
});

const emit = defineEmits<{
  (e: 'update:value', val: string): void;
  (e: 'rerun'): void;
  (e: 'closed'): void;
}>();

type AgentAvatarExpose = {
  getElement: () => HTMLElement | null;
};

const { t } = useI18n();
const { getAgentName, getAgentColor } = useAgentRegistry();

// 实例级别随机 ID，用于 SVG definitions 命名空间隔离
const instanceId = Math.random().toString(36).substring(2, 9);
const gradientId = computed(() => `beam-gradient-${instanceId}`);
const glowId = computed(() => `radial-glow-${instanceId}`);

const isOpen = ref(false);
const triggerRef = ref<AgentAvatarExpose | null>(null);
const overlayRef = ref<HTMLDivElement | null>(null);
const wheelRef = ref<HTMLDivElement | null>(null);
const slotRefs = ref<Array<HTMLElement | null>>([]);
const hoverIndex = ref(-1);
const wheelCenter = ref({ x: 0, y: 0 });
// 入场动画结束前不挂 backdrop-filter，避免整屏高斯模糊与弹性 transform: scale 同帧合成
// 在弱 GPU 移动端，这是首次打开轮盘卡顿的主要根因
const overlayStable = ref(false);

const viewportWidth = ref(typeof window !== 'undefined' ? window.innerWidth : TABLET_MAX_WIDTH);
const isCompactViewport = computed(() => viewportWidth.value < 600);

const effectiveRadius = computed(() => isCompactViewport.value ? Math.min(props.radius, 112) : props.radius);
const effectiveSweep = computed(() => isCompactViewport.value ? Math.min(props.sweepAngle, 140) : props.sweepAngle);
const centerAngle = computed(() => props.startAngle + props.sweepAngle / 2);
// 动态扇形旋转偏移量：保持触发器按钮位置不变（不再钳制 cx），转而调整扇形整体旋转角度
// 让所有槽位都落在视口可见区域内，避免溢出屏幕边缘
const dynamicCenterDelta = ref(0);
const effectiveCenterAngle = computed(() => centerAngle.value + dynamicCenterDelta.value);
const effectiveStart = computed(() => effectiveCenterAngle.value - effectiveSweep.value / 2);
const effectiveSlotSize = computed(() => isCompactViewport.value ? Math.min(props.slotAvatarSize, 32) : props.slotAvatarSize);

// 拖拽与跟手
const isPointerDragging = ref(false);
const pointerDownOnTrigger = ref(false);
const pointerPos = ref({ x: 0, y: 0 });

const shouldShowConnector = computed(() => {
  return isOpen.value && (hoverIndex.value >= 0 || pointerDownOnTrigger.value || isPointerDragging.value);
});

const connectorEnd = computed(() => {
  let x = pointerPos.value.x;
  let y = pointerPos.value.y;
  if (hoverIndex.value >= 0) {
    const offset = slotOffset(hoverIndex.value);
    x = offset.dx;
    y = offset.dy;
  }
  
  // 【关键修复】防止 SVG 在完全水平 (y=0) 或垂直 (x=0) 时，渐变和滤镜在 Chromium (Skia) 渲染引擎中发生降维坍缩 Bug
  // 加上肉眼完全不可察觉的极小偏移量（0.1px），强制浏览器走 2D 路径绘制与渐变，稳定保障霓虹发光粗线效果
  if (Math.abs(y) < 0.1) {
    y = y >= 0 ? 0.1 : -0.1;
  }
  if (Math.abs(x) < 0.1) {
    x = x >= 0 ? 0.1 : -0.1;
  }
  
  return { x, y };
});

// ==================== 顶级视觉配色与全色域混合理论 ====================

/** 源端中枢色彩 */
const sourceColor = computed(() => {
  return getAgentColor(props.value);
});

/** 终端追踪色彩：支持自由拖拽夹角混合与 HSL 高保真渐变 */
const targetColor = computed(() => {
  if (hoverIndex.value >= 0) {
    const opt = displayOptions.value[hoverIndex.value];
    return getAgentColor(opt.value);
  }

  if (isPointerDragging.value || pointerDownOnTrigger.value) {
    const N = displayOptions.value.length;
    if (N > 0) {
      const px = pointerPos.value.x;
      const py = pointerPos.value.y;
      
      const dragAngleRad = Math.atan2(py, px);
      let dragAngleDeg = (dragAngleRad * 180) / Math.PI;

      let closestIdx = 0;
      let minDiff = Infinity;
      for (let i = 0; i < N; i++) {
        const slotAng = angleOf(i);
        let diff = Math.abs(((dragAngleDeg - slotAng + 180 + 360) % 360) - 180);
        if (diff < minDiff) {
          minDiff = diff;
          closestIdx = i;
        }
      }

      const opt = displayOptions.value[closestIdx];
      const slotColor = getAgentColor(opt.value);

      const dist = Math.hypot(px, py);
      const maxDist = effectiveRadius.value;
      const ratio = Math.min(1, Math.max(0, dist / maxDist)); // 0.0 ~ 1.0

      return blendColorsHsl(sourceColor.value, slotColor, ratio);
    }
  }

  return 'var(--spark-accent, #bd93f9)';
});

function rgbToHsl(r: number, g: number, b: number) {
  r /= 255;
  g /= 255;
  b /= 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;

  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      case b: h = (r - g) / d + 4; break;
    }
    h /= 6;
  }
  return { h: h * 360, s: s * 100, l: l * 100 };
}

function hslToRgb(h: number, s: number, l: number) {
  h /= 360;
  s /= 100;
  l /= 100;
  let r = l;
  let g = l;
  let b = l;

  if (s !== 0) {
    const hue2rgb = (p: number, q: number, t: number) => {
      if (t < 0) t += 1;
      if (t > 1) t -= 1;
      if (t < 1/6) return p + (q - p) * 6 * t;
      if (t < 1/2) return q;
      if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
      return p;
    };

    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    r = hue2rgb(p, q, h + 1/3);
    g = hue2rgb(p, q, h);
    b = hue2rgb(p, q, h - 1/3);
  }

  return {
    r: Math.round(r * 255),
    g: Math.round(g * 255),
    b: Math.round(b * 255),
  };
}

function blendColorsHsl(color1: string, color2: string, ratio: number): string {
  const parseToRgb = (c: string): { r: number; g: number; b: number } => {
    if (c.startsWith('#')) {
      const hex = c.slice(1);
      if (hex.length === 3) {
        return {
          r: parseInt(hex[0] + hex[0], 16),
          g: parseInt(hex[1] + hex[1], 16),
          b: parseInt(hex[2] + hex[2], 16),
        };
      }
      return {
        r: parseInt(hex.slice(0, 2), 16),
        g: parseInt(hex.slice(2, 4), 16),
        b: parseInt(hex.slice(4, 6), 16),
      };
    }
    if (c.includes('primary')) return { r: 91, g: 140, b: 255 };
    if (c.includes('accent')) return { r: 188, g: 147, b: 249 };
    return { r: 255, g: 255, b: 255 };
  };

  const rgb1 = parseToRgb(color1);
  const rgb2 = parseToRgb(color2);

  const hsl1 = rgbToHsl(rgb1.r, rgb1.g, rgb1.b);
  const hsl2 = rgbToHsl(rgb2.r, rgb2.g, rgb2.b);

  let h1 = hsl1.h;
  let h2 = hsl2.h;
  const diff = h2 - h1;

  if (Math.abs(diff) > 180) {
    if (diff > 0) h1 += 360;
    else h2 += 360;
  }

  const h = (h1 + (h2 - h1) * ratio) % 360;
  const s = hsl1.s + (hsl2.s - hsl1.s) * ratio;
  const l = hsl1.l + (hsl2.l - hsl1.l) * ratio;

  const rgb = hslToRgb(h, s, l);
  return `rgb(${rgb.r}, ${rgb.g}, ${rgb.b})`;
}

// ========================================================

function setSlotRef(idx: number, el: HTMLElement | null): void {
  slotRefs.value[idx] = el;
}

function onWindowResize(): void {
  viewportWidth.value = window.innerWidth;
  if (isOpen.value) recalcWheelCenter();
}

onMounted(() => {
  window.addEventListener('resize', onWindowResize);
});

const currentName = computed(() => {
  const opt = props.options.find(o => o.value === props.value);
  return opt?.label || getAgentName(props.value) || props.value || '';
});

const renderableOptions = computed<RadialOption[]>(() => {
  return props.options.filter(o => o.value !== props.value);
});

const renderSnapshot = ref<RadialOption[] | null>(null);

const displayOptions = computed<RadialOption[]>(() => renderSnapshot.value ?? renderableOptions.value);

function isOptionDisabled(opt: RadialOption): boolean {
  return !!opt.disabled;
}

function slotAriaLabel(opt: RadialOption): string {
  const states = [
    opt.running ? t('components.agentRadialPicker.running') : '',
    isOptionDisabled(opt) ? opt.disabledReason || '' : '',
  ].filter(Boolean);
  return states.length > 0 ? `${opt.label} - ${states.join(' - ')}` : opt.label;
}

function slotTitle(opt: RadialOption): string {
  const states = [
    opt.running ? t('components.agentRadialPicker.running') : '',
    isOptionDisabled(opt) ? opt.disabledReason || '' : '',
  ].filter(Boolean);
  return states.length > 0 ? `${opt.label} · ${states.join(' · ')}` : opt.label;
}

function angleOf(idx: number): number {
  const N = displayOptions.value.length;
  if (N <= 0) return effectiveStart.value + effectiveSweep.value / 2;
  if (N === 1) return effectiveStart.value + effectiveSweep.value / 2;
  return effectiveStart.value + ((idx + 0.5) / N) * effectiveSweep.value;
}

function slotOffset(idx: number): { dx: number; dy: number } {
  const rad = (angleOf(idx) * Math.PI) / 180;
  return {
    dx: Math.cos(rad) * effectiveRadius.value,
    dy: Math.sin(rad) * effectiveRadius.value,
  };
}

function slotStyle(idx: number, agentId: string): Record<string, string> {
  const { dx, dy } = slotOffset(idx);
  const angle = angleOf(idx);
  const rad = (angle * Math.PI) / 180;
  const ux = Math.cos(rad);
  const uy = Math.sin(rad);
  const color = getAgentColor(agentId);
  return {
    '--dx': `${dx}px`,
    '--dy': `${dy}px`,
    '--ux': `${ux}`,
    '--uy': `${uy}`,
    '--slot-color': color,
    '--slot-size': `${effectiveSlotSize.value}px`,
  };
}

const wheelStyle = computed(() => ({
  left: `${wheelCenter.value.x}px`,
  top: `${wheelCenter.value.y}px`,
}));

function recalcWheelCenter(): void {
  const trig = getTriggerElement();
  if (!trig) return;
  const rect = trig.getBoundingClientRect();
  // 关键：不再钳制 cx/cy，wheel 中心严格对齐触发器按钮中心，按钮位置永远不漂移
  const cx = rect.left + rect.width / 2;
  const cy = rect.bottom + 14;
  wheelCenter.value = { x: cx, y: cy };

  // 仅在压缩视口（移动端/窄聊天窗）下启用动态扇形旋转：
  // 桌面端保持原始视觉设计（默认扇形朝右下方），不因小幅顶部溢出而调整
  if (isCompactViewport.value) {
    dynamicCenterDelta.value = computeFanDelta(cx, cy);
  } else {
    dynamicCenterDelta.value = 0;
  }
}

function getTriggerElement(): HTMLElement | null {
  return triggerRef.value?.getElement() ?? null;
}

/**
 * 启发式算法：根据轮盘几何中心 (cx, cy) 在视口中的位置，
 * 寻找一个使所有槽位都不溢出视口边界的 centerAngle 偏移量。
 *
 * 策略：从 0° 开始，按 5° 递增对正负方向交替试探（优先无偏移），
 * 只要找到能让全部槽位完整落入安全区域的角度即返回。
 */
function computeFanDelta(cx: number, cy: number): number {
  if (typeof window === 'undefined') return 0;
  const N = displayOptions.value.length;
  if (N <= 0) return 0;

  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const radius = effectiveRadius.value;
  const sweep = effectiveSweep.value;
  const baseCenter = centerAngle.value;
  const margin = 12;
  // 槽位自身半径，用于计算槽位边缘是否溢出视口
  const slotHalf = (effectiveSlotSize.value + 8) / 2;

  const fits = (delta: number): boolean => {
    const start = baseCenter + delta - sweep / 2;
    for (let i = 0; i < N; i++) {
      const angle = start + ((i + 0.5) / N) * sweep;
      const rad = (angle * Math.PI) / 180;
      const sx = cx + Math.cos(rad) * radius;
      const sy = cy + Math.sin(rad) * radius;
      if (sx - slotHalf < margin) return false;
      if (sx + slotHalf > vw - margin) return false;
      if (sy - slotHalf < margin) return false;
      if (sy + slotHalf > vh - margin) return false;
    }
    return true;
  };

  // 优先 delta = 0（保持原始视觉设计）
  if (fits(0)) return 0;
  // 然后按 5° 步进对正负方向同步搜索（先试小偏移）
  for (let step = 5; step <= 120; step += 5) {
    if (fits(step)) return step;
    if (fits(-step)) return -step;
  }
  // 实在塞不下时按按钮在视口的水平比例给一个粗略偏移（保底，不会找不到结果）
  const ratio = Math.max(0, Math.min(1, cx / vw));
  if (ratio < 0.3) return -30;  // 按钮靠左，扇形朝右下方倾斜（centerAngle 减小）
  if (ratio > 0.7) return 30;   // 按钮靠右，扇形朝左下方倾斜（centerAngle 增大）
  return 0;
}

async function open(): Promise<void> {
  if (props.disabled || isOpen.value) return;
  renderSnapshot.value = null;
  hoverIndex.value = -1;
  recalcWheelCenter();
  isOpen.value = true;
  await nextTick();
  overlayRef.value?.focus?.();
}

function close(): void {
  if (!isOpen.value) return;
  restoreTriggerFocus();
  isOpen.value = false;
  hoverIndex.value = -1;
  isPointerDragging.value = false;
  pointerDownOnTrigger.value = false;
}

/** 在遮罩隐藏前把焦点归还触发器，避免焦点落入 aria-hidden 的焦点陷阱哨兵。 */
function restoreTriggerFocus(): void {
  const trigger = getTriggerElement();
  if (trigger && typeof trigger.focus === 'function') {
    trigger.focus({ preventScroll: true });
  }
}

/**
 * 入场动画完整结束后再挂 backdrop-filter：
 * 入场期间 wheel 在做 cubic-bezier 弹性 scale，整屏 backdrop blur 与之同帧合成会拖慢首帧。
 * 等 transform 收敛后再缓 fade-in 磨砂背景，视觉上几乎察觉不到差异。
 */
function onOverlayAfterEnter(): void {
  overlayStable.value = true;
}

/**
 * 退出前先撤掉 backdrop-filter，使其立即消失，再让透明度收尾。
 * 避免退出动画期间 backdrop blur 仍在持续合成，进一步拖慢关闭。
 */
function onOverlayBeforeLeave(): void {
  overlayStable.value = false;
  restoreTriggerFocus();
}

function onOverlayAfterLeave(): void {
  renderSnapshot.value = null;
  emit('closed');
}

function commitSelectionAndClose(value: string, idx: number): void {
  renderSnapshot.value = [...renderableOptions.value];
  hoverIndex.value = idx;
  emit('update:value', value);
  restoreTriggerFocus();
  isOpen.value = false;
  isPointerDragging.value = false;
  pointerDownOnTrigger.value = false;
}

function toggle(): void {
  if (isOpen.value) close();
  else open();
}

let activePointerId: number | null = null;
const DRAG_THRESHOLD_PX = 6;
let pointerStart = { x: 0, y: 0 };

function onTriggerClick(evt: MouseEvent): void {
  if (isPointerDragging.value) {
    isPointerDragging.value = false;
  }
  evt?.preventDefault?.();
}

function onTriggerPointerDown(evt: PointerEvent): void {
  if (props.disabled) return;
  if (isOpen.value) return;

  evt.preventDefault();
  pointerDownOnTrigger.value = true;
  isPointerDragging.value = false;
  activePointerId = evt.pointerId;
  pointerStart = { x: evt.clientX, y: evt.clientY };
  open();

  pointerPos.value = {
    x: evt.clientX - wheelCenter.value.x,
    y: evt.clientY - wheelCenter.value.y,
  };

  window.addEventListener('pointermove', onWindowPointerMove, true);
  window.addEventListener('pointerup', onWindowPointerUp, true);
  window.addEventListener('pointercancel', onWindowPointerUp, true);
}

function onWindowPointerMove(evt: PointerEvent): void {
  if (activePointerId !== null && evt.pointerId !== activePointerId) return;
  if (!isOpen.value || !pointerDownOnTrigger.value) return;

  if (!isPointerDragging.value) {
    const dx = evt.clientX - pointerStart.x;
    const dy = evt.clientY - pointerStart.y;
    if (Math.hypot(dx, dy) < DRAG_THRESHOLD_PX) return;
    isPointerDragging.value = true;
  }

  pointerPos.value = {
    x: evt.clientX - wheelCenter.value.x,
    y: evt.clientY - wheelCenter.value.y,
  };

  const hit = findSlotAt(evt.clientX, evt.clientY);
  hoverIndex.value = hit;
}

function onWindowPointerUp(evt: PointerEvent): void {
  if (activePointerId !== null && evt.pointerId !== activePointerId) return;

  window.removeEventListener('pointermove', onWindowPointerMove, true);
  window.removeEventListener('pointerup', onWindowPointerUp, true);
  window.removeEventListener('pointercancel', onWindowPointerUp, true);
  activePointerId = null;

  const wasDragging = isPointerDragging.value;
  pointerDownOnTrigger.value = false;

  if (!isOpen.value) {
    isPointerDragging.value = false;
    return;
  }

  if (wasDragging) {
    const hit = findSlotAt(evt.clientX, evt.clientY);
    if (hit >= 0) {
      const opt = displayOptions.value[hit];
      if (opt && !isOptionDisabled(opt)) {
        commitSelectionAndClose(opt.value, hit);
        return;
      }
    }
    hoverIndex.value = -1;
  } else {
    /*
     * 关键修复：单击 trigger 后立即抬起的场景。
     * 由于 overlay 在 open() 后立即覆盖整个视口，pointerup 的 hit-test 通常会落在 overlay 上而不是 trigger。
     * 同时 wheel 中央 hub 位于 trigger 下方 14px 处，仅右上边少量与 trigger 重叠，
     * 这造成点击 trigger 视觉中心时 evt.target === overlayRef 为真 → close()，出现“点一下立刻消失”。
     * 修复：按鼠标抬起的物理坐标是否仍在 trigger rect 内判断，是则保持轮盘打开。
     */
    const trig = getTriggerElement();
    let stillOnTrigger = false;
    if (trig) {
      const r = trig.getBoundingClientRect();
      stillOnTrigger =
        evt.clientX >= r.left && evt.clientX <= r.right &&
        evt.clientY >= r.top && evt.clientY <= r.bottom;
    }
    if (stillOnTrigger) {
      // 单击未拖动 + 抬起仍在 trigger 上，保持轮盘打开等待后续选择
      return;
    }
    if (evt.target === overlayRef.value) {
      close();
    }
  }
  isPointerDragging.value = false;
}

function onTriggerKeyDown(evt: KeyboardEvent): void {
  if (evt.key === 'Enter' || evt.key === ' ') {
    evt.preventDefault();
    toggle();
  } else if (evt.key === 'Escape') {
    close();
  } else if (evt.key === 'ArrowDown' && !isOpen.value) {
    evt.preventDefault();
    open();
  }
}

function onOverlayPointerDown(evt: PointerEvent): void {
  if (evt.target === overlayRef.value) {
    pointerDownOnTrigger.value = true;
    isPointerDragging.value = false;
    activePointerId = evt.pointerId;
    pointerStart = { x: evt.clientX, y: evt.clientY };
    pointerPos.value = {
      x: evt.clientX - wheelCenter.value.x,
      y: evt.clientY - wheelCenter.value.y,
    };

    window.addEventListener('pointermove', onWindowPointerMove, true);
    window.addEventListener('pointerup', onWindowPointerUp, true);
    window.addEventListener('pointercancel', onWindowPointerUp, true);
  }
}

function onHubPointerDown(evt: PointerEvent): void {
  if (props.disabled) return;
  evt.preventDefault();
  pointerDownOnTrigger.value = true;
  isPointerDragging.value = true;
  activePointerId = evt.pointerId;
  pointerStart = { x: evt.clientX, y: evt.clientY };
  pointerPos.value = {
    x: evt.clientX - wheelCenter.value.x,
    y: evt.clientY - wheelCenter.value.y,
  };

  window.addEventListener('pointermove', onWindowPointerMove, true);
  window.addEventListener('pointerup', onWindowPointerUp, true);
  window.addEventListener('pointercancel', onWindowPointerUp, true);
}

function onSlotClick(opt: RadialOption): void {
  if (isOptionDisabled(opt)) return;
  if (opt.value === props.value) {
    close();
    return;
  }
  const idx = displayOptions.value.findIndex(o => o.value === opt.value);
  commitSelectionAndClose(opt.value, idx);
}

function onSlotPointerDown(_evt: PointerEvent, idx: number): void {
  hoverIndex.value = idx;
}

function findSlotAt(clientX: number, clientY: number): number {
  const els = slotRefs.value;
  for (let i = 0; i < els.length; i++) {
    const el = els[i];
    if (!el) continue;
    const rect = el.getBoundingClientRect();
    if (clientX >= rect.left && clientX <= rect.right
      && clientY >= rect.top && clientY <= rect.bottom) {
      return i;
    }
  }
  return -1;
}

function onGlobalKeyDown(evt: KeyboardEvent): void {
  if (!isOpen.value) return;
  if (evt.key === 'Escape') {
    evt.stopPropagation();
    close();
  }
}

watch(isOpen, (open) => {
  if (open) {
    window.addEventListener('keydown', onGlobalKeyDown, true);
  } else {
    window.removeEventListener('keydown', onGlobalKeyDown, true);
  }
});

watch(() => displayOptions.value.length, (len) => {
  slotRefs.value = slotRefs.value.slice(0, len);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onGlobalKeyDown, true);
  window.removeEventListener('resize', onWindowResize);
  window.removeEventListener('pointermove', onWindowPointerMove, true);
  window.removeEventListener('pointerup', onWindowPointerUp, true);
  window.removeEventListener('pointercancel', onWindowPointerUp, true);
});
</script>

<style scoped>
/* ============ 触发器：AgentAvatar 自身就是按钮 ============ */
/*
 * 设计原则：AgentAvatar 根元素直接渲染为 button，避免 button 外壳 + avatar 内壳的双层圆形。
 * 必须彻底重置 button 的 user-agent 默认样式（特别是 iOS Safari/Chrome 移动端会给 button 默认加
 * 渐变背景、圆角、font/line-height 偏移、默认 padding 等），避免移动端出现 button “压变形”。
 * 高亮反馈直接作用在头像按钮本身。
 */
.picker-trigger {
  /* 重置 button 默认盒模型，但保留 AgentAvatar 自己的背景、边框、颜色 */
  -webkit-appearance: none;
  appearance: none;
  margin: 0;
  padding: 0;
  font: inherit;
  line-height: 0; /* 除去 button 默认 baseline 间距，防止产生高度变形 */

  /* 仅保留 hit area 与交互反馈所需的样式 */
  display: inline-flex;
  flex-shrink: 0; /* 在 flex 父容器（如聊天 header）中防止按钮被压缩 */
  position: relative; /* 为 ::before 扩展 hit area 提供定位上下文 */
  border-radius: 50%;
  cursor: pointer;
  outline: none;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  touch-action: none; /* 彻底打通移动端“一气呵成滑动”：禁用原生的滑动手势与页面滚动判定，确保手指划动时 pointermove 能够持续稳定触发，不被系统的 pointercancel 截断 */
  transition: transform 0.18s ease;
}

/*
 * 透明 hit area 扩展：在不改变头像视觉尺寸的前提下，把可点击区域从 26x26 拓到 ≈34x34。
 * 伪元素不会成为 event.target，鼠标命中 ::before 时事件仍会派发到父 button 上，onTriggerPointerDown 正常触发。
 * inset -4px 与两侧兄弟元素的 gap 8px 不产生重叠，不会误伤邻居点击区。
 */
.picker-trigger::before {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: inherit;
}

.picker-trigger:hover:not(:disabled),
.picker-trigger.is-open {
  /* 微放大＋内层头像光环表达高亮，不需要外层边框 */
  transform: scale(1.06);
}

.picker-trigger:active:not(:disabled) {
  transform: scale(0.96);
  transition-duration: 0.08s;
}

.picker-trigger:focus-visible {
  /* focus ring 贴着圆形头像边缘，不在外面形成矩形 outline、避免破坏圆形视觉 */
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--spark-primary) 60%, transparent),
    0 4px 10px rgba(0, 0, 0, 0.08);
}

.picker-trigger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.picker-trigger:hover:not(:disabled),
.picker-trigger.is-open {
  /* 高亮通过头像自身的光环表达——不是外层多一圈边框，而是头像本身“亮起来” */
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--spark-primary) 32%, transparent),
    0 6px 14px rgba(0, 0, 0, 0.16);
}

/* ============ 轮盘 Overlay ============ */
.agent-radial-overlay {
  position: fixed;
  inset: 0;
  z-index: 9000;
  background: color-mix(in srgb, var(--spark-bg) 70%, transparent);
  /*
   * 默认不挂 backdrop-filter：入场弹性动画期间整屏高斯模糊会与 wheel 的 transform: scale 同帧重做合成，
   * 是移动端首次打开轮盘的主要卡顿源。改为入场动画结束（@after-enter）后通过 .is-stable 缓 fade-in。
   */
  pointer-events: auto;
  outline: none;
  touch-action: none;
  /* 提示浏览器为后续 backdrop-filter 留独立合成层，避免动态加滤镜时再做一次 layer promotion */
  will-change: backdrop-filter;
}

.agent-radial-overlay.is-stable {
  backdrop-filter: blur(6px) saturate(0.85);
  -webkit-backdrop-filter: blur(6px) saturate(0.85);
  transition:
    backdrop-filter 0.18s ease,
    -webkit-backdrop-filter 0.18s ease;
}

.agent-radial-wheel {
  position: absolute;
  width: 0;
  height: 0;
  pointer-events: none;
  /* 入场期间 transform: scale 走独立合成层，与 overlay 解耦，进一步降低首帧合成耦合 */
  will-change: transform;
  --slot-size: 56px;
  --label-offset: 44px;
}

@media (max-width: 599.9px) {
  .agent-radial-overlay,
  .agent-radial-overlay.is-stable {
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    will-change: auto;
  }

  .agent-radial-wheel {
    --slot-size: 46px;
    --label-offset: 38px;
  }

  .agent-radial-fade-enter-active .agent-radial-wheel {
    animation-duration: 0.18s;
    animation-timing-function: ease-out;
  }
}

@media (pointer: coarse) {
  .agent-radial-wheel {
    --slot-size: 60px;
    --label-offset: 46px;
  }
}

@media (max-width: 599.9px) and (pointer: coarse) {
  .agent-radial-wheel {
    --slot-size: 48px;
    --label-offset: 38px;
  }
}

.agent-radial-wheel > * {
  pointer-events: auto;
}

/* ============ 中央枢纽 (Central Hub) ============ */
.agent-radial-hub {
  position: absolute;
  left: 0;
  top: 0;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  pointer-events: auto;
  cursor: grab;
  z-index: 10;
  background: var(--spark-bg);
  box-shadow: 0 0 28px color-mix(in srgb, var(--hub-color, var(--spark-primary)) 35%, transparent);
  transition: width 0.2s ease, height 0.2s ease, box-shadow 0.25s ease;
}

.agent-radial-hub:active {
  cursor: grabbing;
}

@media (max-width: 599.9px) {
  .agent-radial-hub {
    width: 40px;
    height: 40px;
  }
}

.hub-pulse-ring {
  position: absolute;
  inset: -4px;
  border: 1px solid color-mix(in srgb, var(--hub-color, var(--spark-primary)) 30%, transparent);
  border-radius: 50%;
  animation: hubBreathe 2.4s ease-in-out infinite;
  transition: border-color 0.25s ease;
}

@keyframes hubBreathe {
  0%, 100% {
    transform: scale(1);
    opacity: 0.35;
  }
  50% {
    transform: scale(1.16);
    opacity: 0.85;
    border-color: color-mix(in srgb, var(--hub-color, var(--spark-primary)) 60%, transparent);
  }
}

/* ============ SVG 连线画布 ============ */
.radial-connector-svg {
  position: absolute;
  left: 0;
  top: 0;
  width: 600px;
  height: 600px;
  transform: translate(-50%, -50%);
  pointer-events: none;
  overflow: visible;
  z-index: 1;
}

/* 背景轨道圈 */
.track-circle {
  fill: none;
  stroke: color-mix(in srgb, var(--spark-primary) 8%, transparent);
  stroke-width: 1;
  stroke-dasharray: 4 4;
}

/* 每个槽位的放射导向虚线 */
.track-ray {
  stroke: color-mix(in srgb, var(--slot-color, var(--spark-primary)) 7%, transparent);
  stroke-width: 1;
  stroke-dasharray: 3 3;
  transition: stroke 0.25s ease, stroke-width 0.25s ease;
}

.track-ray.is-active {
  stroke: color-mix(in srgb, var(--slot-color, var(--spark-primary)) 35%, transparent);
  stroke-width: 1.5;
  stroke-dasharray: none;
}

/* 霓虹发光连接线：稳定无 transition 几何属性 */
.connector-line {
  stroke-width: 3.8px;
  stroke-linecap: round;
  transition: none;
}

/* 连线末端的追踪微粒：稳定无 transition 几何属性 */
.connector-dot {
  fill: var(--dot-color, var(--spark-accent));
  stroke: #ffffff;
  stroke-width: 1.5px;
  transition: fill 0.15s ease;
}

/* ============ 扇片：圆形头像按钮 ============ */
.agent-radial-slot {
  position: absolute;
  left: 0;
  top: 0;
  width: var(--slot-size);
  height: var(--slot-size);
  border-radius: 50%;
  transform: translate(calc(-50% + var(--dx, 0px)), calc(-50% + var(--dy, 0px)));
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  box-shadow: 0 6px 14px rgba(0, 0, 0, 0.12);
  cursor: pointer;
  font-family: inherit;
  color: var(--spark-text);
  transition:
    box-shadow 0.18s ease,
    border-color 0.18s ease;
  -webkit-tap-highlight-color: transparent;
}

.agent-radial-slot:hover:not(:disabled),
.agent-radial-slot.is-hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--slot-color) 60%, var(--spark-border));
  box-shadow:
    0 10px 24px rgba(0, 0, 0, 0.18),
    0 0 0 3.5px color-mix(in srgb, var(--slot-color) 25%, transparent);
}

.agent-radial-slot:focus-visible {
  outline: none;
  border-color: var(--slot-color, var(--spark-primary));
  box-shadow:
    0 6px 14px rgba(0, 0, 0, 0.12),
    0 0 0 3px color-mix(in srgb, var(--slot-color, var(--spark-primary)) 35%, transparent);
}

.agent-radial-slot.is-disabled,
.agent-radial-slot:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  filter: grayscale(0.45);
}

.agent-radial-slot-running {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 10px;
  height: 10px;
  border: 2px solid var(--spark-surface, #fff);
  border-radius: 50%;
  background: var(--slot-color, var(--spark-primary));
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--slot-color, var(--spark-primary)) 25%, transparent);
  transform: translate(
    calc(var(--slot-size) / 2 - 7px),
    calc(var(--slot-size) / -2 - 3px)
  );
  pointer-events: none;
  animation: agent-running-pulse 1.4s ease-in-out infinite;
}

@keyframes agent-running-pulse {
  0%, 100% { opacity: 0.72; box-shadow: 0 0 0 2px color-mix(in srgb, var(--slot-color, var(--spark-primary)) 20%, transparent); }
  50% { opacity: 1; box-shadow: 0 0 0 5px color-mix(in srgb, var(--slot-color, var(--spark-primary)) 8%, transparent); }
}

/* 名字悬浮在外侧，高亮时体现专属主题色 */
.agent-radial-slot-name {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(
    calc(-50% + var(--ux) * var(--label-offset)),
    calc(-50% + var(--uy) * var(--label-offset))
  );
  font-size: var(--spark-fs-3xs, 10px);
  color: var(--spark-text-muted);
  font-weight: 600;
  letter-spacing: 0.2px;
  white-space: nowrap;
  pointer-events: none;
  text-shadow: 0 0 6px var(--spark-bg);
  transition: color 0.15s ease, text-shadow 0.15s ease;
}

.agent-radial-slot:hover .agent-radial-slot-name,
.agent-radial-slot.is-hover .agent-radial-slot-name {
  color: var(--slot-color);
  text-shadow: 0 0 8px color-mix(in srgb, var(--slot-color) 35%, var(--spark-bg));
}

/* ============ 入场/退场动画 ============ */
.agent-radial-fade-enter-active,
.agent-radial-fade-leave-active {
  transition: opacity 0.22s ease;
}

.agent-radial-fade-enter-from,
.agent-radial-fade-leave-to {
  opacity: 0;
}

.agent-radial-fade-enter-active .agent-radial-wheel {
  animation: agentWheelPop 0.34s cubic-bezier(0.34, 1.4, 0.64, 1) both;
  will-change: transform;
}

.agent-radial-fade-leave-active .agent-radial-wheel {
  animation: agentWheelCollapse 0.2s cubic-bezier(0.4, 0, 0.7, 0.2) both;
  will-change: transform;
}

@keyframes agentWheelPop {
  0% { transform: scale(0.4); }
  60% { transform: scale(1.04); }
  100% { transform: scale(1); }
}

@keyframes agentWheelCollapse {
  0% { transform: scale(1); }
  100% { transform: scale(0.6); }
}

@media (prefers-reduced-motion: reduce) {
  .agent-radial-fade-enter-active,
  .agent-radial-fade-leave-active {
    transition: opacity 0.12s linear;
  }

  .agent-radial-fade-enter-active .agent-radial-wheel,
  .agent-radial-fade-leave-active .agent-radial-wheel {
    animation: none;
  }

  .picker-trigger,
  .agent-radial-slot {
    transition: none;
  }

}

@media (pointer: coarse) {
  .picker-trigger::before {
    inset: -8px;
  }
}
</style>
