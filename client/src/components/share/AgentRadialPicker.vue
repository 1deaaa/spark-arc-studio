<template>
  <div class="agent-radial-picker" :class="{ 'is-disabled': disabled }">
    <!-- 触发器：纯圆形 Agent 头像（与扇片视觉一致），不再使用"下拉框 + 箭头"样式 -->
    <button
      ref="triggerRef"
      type="button"
      class="picker-trigger"
      :class="{ 'is-open': isOpen }"
      :disabled="disabled"
      :aria-haspopup="'listbox'"
      :aria-expanded="isOpen"
      :aria-label="`${currentName} (${t('components.agentRadialPicker.switchAgent')})`"
      :title="`${currentName} · ${t('components.agentRadialPicker.switchAgent')}`"
      @pointerdown="onTriggerPointerDown"
      @click="onTriggerClick"
      @keydown="onTriggerKeyDown"
    >
      <AgentAvatar
        class="picker-trigger-avatar"
        :agent-id="value"
        :size="26"
      />
    </button>

    <!-- 轮盘：Teleport 到 body 避免被 chat-panel-header 的 overflow 裁剪 -->
    <Teleport to="body">
      <Transition name="agent-radial-fade">
        <div
          v-if="isOpen"
          ref="overlayRef"
          class="agent-radial-overlay"
          @pointerdown.self="onOverlayPointerDown"
        >
          <div
            ref="wheelRef"
            class="agent-radial-wheel"
            :style="wheelStyle"
            role="listbox"
            :aria-label="t('components.agentRadialPicker.label')"
          >
            <!-- 中央交互提示：呼吸动效徽章，告诉用户这是可拖动 / 可点击的选择器；拖动状态下自动淡出 -->
            <div
              class="agent-radial-hint"
              :class="{ 'is-dragging': pointerDownOnTrigger }"
              aria-hidden="true"
            >
              {{ t('components.agentRadialPicker.dragHint') }}
            </div>

            <!-- 扇片：圆形头像 + 浮于圆下方的名字（pointer-events:none 避免 hover 区域抖动） -->
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
              :style="slotStyle(idx)"
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
              <span class="agent-radial-slot-name">{{ opt.label }}</span>
            </button>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
/**
 * AgentRadialPicker.vue —— Agent 轮盘选择器
 *
 * 设计目标：
 * 1. 替代普通下拉选择器，让多 Agent 切换具备"召唤"的仪式感。
 * 2. 桌面端：点击展开轮盘，单击或按住拖到扇片释放选中。
 * 3. 移动端：通过 PointerEvent 统一处理，触摸长按弹出，touchmove 选中扇片。
 * 4. 中央不放按钮：当前选中 Agent 已由 trigger 圆形头像承担，避免视觉冗余。
 * 5. 占用提示：disabled 扇片显示灰化，hover 显示占用原因。
 *
 * 对外契约（与 n-select 等价）：
 *   props.value      ←→ v-model:value
 *   props.options    ←→ Array<{ value, label, disabled?, disabledReason? }>
 *   emit('update:value', val)
 *   emit('rerun')   ← 预留 API：未来"重生成"功能可复用此事件，当前版本不会触发
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import AgentAvatar from '@/components/share/AgentAvatar.vue';
import { useAgentRegistry } from '@/composables/useAgentRegistry';

type RadialOption = {
  value: string;
  label: string;
  disabled?: boolean;
  disabledReason?: string;
  [k: string]: unknown;
};

const props = defineProps({
  /** 当前选中的 agentId */
  value: { type: String, default: '' },
  /** Agent 选项列表（与 n-select options 同构） */
  options: { type: Array as PropType<RadialOption[]>, default: () => [] },
  /** 整体禁用（轮盘不可展开） */
  disabled: { type: Boolean, default: false },
  /**
   * 扇形跨度（度），默认 180°——覆盖"右上 45° → 右 → 右下 → 下 → 左下 45°"安全 180°。
   * 这样在浮窗紧贴屏幕顶部 / 左侧时，扇形不会被裁切。
   */
  sweepAngle: { type: Number, default: 180 },
  /**
   * 扇形起始角度（度），相对屏幕坐标 0=右，90=下，180=左，-90=上。
   * 默认 -45°：扇形从"右上 45°"开始，经 0°（正右）-> 90°（正下）-> 135°（左下 45°）结束。
   * 中央方向 = startAngle + sweepAngle/2 = 45°（右下对角线）。
   */
  startAngle: { type: Number, default: -45 },
  /** 扇形半径（px），默认 130，给 7 个 Agent 留出更宽松间距 */
  radius: { type: Number, default: 130 },
  /** 周围 Agent 头像尺寸 */
  slotAvatarSize: { type: Number, default: 40 },
});

const emit = defineEmits<{
  (e: 'update:value', val: string): void;
  (e: 'rerun'): void;
}>();

const { t } = useI18n();
const { getAgentName } = useAgentRegistry();

const isOpen = ref(false);
const triggerRef = ref<HTMLButtonElement | null>(null);
const overlayRef = ref<HTMLDivElement | null>(null);
const wheelRef = ref<HTMLDivElement | null>(null);
const slotRefs = ref<Array<HTMLElement | null>>([]);
const hoverIndex = ref(-1);

// 轮盘的圆心绝对坐标（基于触发器底部中心，或小屏时屏幕中央）
const wheelCenter = ref({ x: 0, y: 0 });

// 响应式 viewport 宽度，用于小屏自适应
const viewportWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1024);
const isCompactViewport = computed(() => viewportWidth.value < 600);

/** 自适应半径：移动端/窄屏时缩小避免溢出 */
const effectiveRadius = computed(() => isCompactViewport.value ? Math.min(props.radius, 112) : props.radius);
/** 自适应扇形跨度：窄屏时收窄避免左右扇片超出可视区 */
const effectiveSweep = computed(() => isCompactViewport.value ? Math.min(props.sweepAngle, 140) : props.sweepAngle);
/** 扇形中央方向（保持由 props 决定） */
const centerAngle = computed(() => props.startAngle + props.sweepAngle / 2);
/** 自适应起始角：以中央方向对称收窄，保证扇形中央方向不变 */
const effectiveStart = computed(() => centerAngle.value - effectiveSweep.value / 2);
/** 自适应扇片头像尺寸 */
const effectiveSlotSize = computed(() => isCompactViewport.value ? Math.min(props.slotAvatarSize, 32) : props.slotAvatarSize);

// 拖放状态：pointerdown 在触发器或扇片上后，移动到扇片上的索引
const isPointerDragging = ref(false);
const pointerDownOnTrigger = ref(false);

function setSlotRef(idx: number, el: HTMLElement | null): void {
  slotRefs.value[idx] = el;
}

function onWindowResize(): void {
  viewportWidth.value = window.innerWidth;
  // 打开状态下窗口变化时重新定位
  if (isOpen.value) {
    recalcWheelCenter();
  }
}

onMounted(() => {
  window.addEventListener('resize', onWindowResize);
});

/** 当前选中 Agent 的展示名称 */
const currentName = computed(() => {
  const opt = props.options.find(o => o.value === props.value);
  return opt?.label || getAgentName(props.value) || props.value || '';
});

/** 渲染时排除"当前选中项"——它已经在中央显示 */
const renderableOptions = computed<RadialOption[]>(() => {
  return props.options.filter(o => o.value !== props.value);
});

/**
 * leave 动画期间冻结的扇片列表快照。
 *
 * 当用户选中某扇片时，会先 emit('update:value')，父组件立即更新 `props.value`，
 * 这会让 `renderableOptions` computed 立刻重新计算——被选中的扇片 DOM 会被 v-for diff 销毁，
 * 同时旧中央项作为新扇片插入，剩余扇片的索引偏移导致 transform 瞬移。
 * 视觉上呈现"选中扇片消失 + 其他扇片往中间闪动"的 bug。
 *
 * 解决：commit 选中时拍下当前列表快照，让 leave 动画结束（或下次 open）前都用这个快照渲染。
 */
const renderSnapshot = ref<RadialOption[] | null>(null);

/** 实际用于 v-for 渲染的列表：commit 关闭期间使用冻结快照，平时使用最新计算 */
const displayOptions = computed<RadialOption[]>(() => renderSnapshot.value ?? renderableOptions.value);

function isOptionDisabled(opt: RadialOption): boolean {
  return !!opt.disabled;
}

function slotAriaLabel(opt: RadialOption): string {
  return isOptionDisabled(opt) && opt.disabledReason
    ? `${opt.label} - ${opt.disabledReason}`
    : opt.label;
}

function slotTitle(opt: RadialOption): string {
  return isOptionDisabled(opt) ? (opt.disabledReason || opt.label) : opt.label;
}

/** 计算扇片在轮盘上的角度（度），基于 displayOptions 长度 + effectiveStart / effectiveSweep */
function angleOf(idx: number): number {
  const N = displayOptions.value.length;
  if (N <= 0) return effectiveStart.value + effectiveSweep.value / 2;
  if (N === 1) return effectiveStart.value + effectiveSweep.value / 2;
  // 角度均匀分布：第 i 个扇片在区间 [start, start+sweep] 内取 (i + 0.5) / N
  return effectiveStart.value + ((idx + 0.5) / N) * effectiveSweep.value;
}

/** 扇片相对中央的位移（px），基于自适应 effectiveRadius */
function slotOffset(idx: number): { dx: number; dy: number } {
  const rad = (angleOf(idx) * Math.PI) / 180;
  return {
    dx: Math.cos(rad) * effectiveRadius.value,
    dy: Math.sin(rad) * effectiveRadius.value,
  };
}

/** 扇片偏移量（CSS 变量传递），便于动画与定位共享 transform */
function slotStyle(idx: number): Record<string, string> {
  const { dx, dy } = slotOffset(idx);
  return {
    '--dx': `${dx}px`,
    '--dy': `${dy}px`,
  };
}

/** 轮盘容器绝对定位 style（圆心 = 触发器底部中心） */
const wheelStyle = computed(() => ({
  left: `${wheelCenter.value.x}px`,
  top: `${wheelCenter.value.y}px`,
}));

/**
 * 计算轮盘圆心位置。
 *
 * 扇形已经居中在右下对角线（默认中央方向 45°），所以圆心放在触发器右下方向附近就好：
 * - X：触发器水平中央
 * - Y：触发器底部下方 14px 间距
 * 由于扇形展开方向均朝右下，左侧/上侧不会被裁切；
 * 仅需对右侧/下侧做一次 clamp 防止溢出 viewport。
 */
function recalcWheelCenter(): void {
  const trig = triggerRef.value;
  if (!trig) return;
  const rect = trig.getBoundingClientRect();
  let cx = rect.left + rect.width / 2;
  let cy = rect.bottom + 14;
  const margin = 16;
  // 右侧边缘 clamp：保证扇形最右端不超出 viewport
  const maxCx = window.innerWidth - effectiveRadius.value - margin;
  if (cx > maxCx) cx = maxCx;
  // 下侧边缘 clamp：保证扇形最下端不超出 viewport
  const maxCy = window.innerHeight - effectiveRadius.value - margin;
  if (cy > maxCy) cy = maxCy;
  wheelCenter.value = { x: cx, y: cy };
}

/** 打开轮盘：计算位置 + 清空上一次的快照后显示 */
async function open(): Promise<void> {
  if (props.disabled || isOpen.value) return;
  // 清空上一次 commit 冻结的快照，让轮盘使用最新的 renderableOptions
  renderSnapshot.value = null;
  hoverIndex.value = -1;
  recalcWheelCenter();
  isOpen.value = true;
  await nextTick();
  // 焦点交给 overlay 以便 Escape 键能关闭
  overlayRef.value?.focus?.();
}

function close(): void {
  if (!isOpen.value) return;
  isOpen.value = false;
  hoverIndex.value = -1;
  isPointerDragging.value = false;
  pointerDownOnTrigger.value = false;
}

/**
 * 提交选中并关闭轮盘。
 *
 * 关键步骤顺序（不可调换）：
 * 1. **先拍快照**：冻结当前 displayOptions，避免 emit 后 v-for 重排
 * 2. **保持 hoverIndex**：让被选中扇片在 leave 动画期间维持高亮（提供被选中反馈）
 * 3. **emit 更新**：props.value 变化后 renderableOptions 重算，但渲染仅看 renderSnapshot 快照
 * 4. **手动收尾**：不走 close()，避免 hoverIndex 被提前清零
 */
function commitSelectionAndClose(value: string, idx: number): void {
  // 冻结当前扇片列表：下一次 open() 才会重置
  renderSnapshot.value = [...renderableOptions.value];
  // 保持被选中扇片的 hover/active 高亮状态直到 leave 动画结束
  hoverIndex.value = idx;

  emit('update:value', value);

  // 手动收尾：不调 close() 避免提前重置 hoverIndex
  isOpen.value = false;
  isPointerDragging.value = false;
  pointerDownOnTrigger.value = false;
}

function toggle(): void {
  if (isOpen.value) close();
  else open();
}

// 当前正在追踪的 pointer id（多指/多设备过滤）
let activePointerId: number | null = null;
// 拖动阈值：手指/鼠标按下后移动 > N 像素才视为"拖动"，否则视作"点击"
const DRAG_THRESHOLD_PX = 6;
let pointerStart = { x: 0, y: 0 };

/**
 * 触发器 click handler——仅做防御性收尾。
 *
 * 鼠标点击：已由 pointerdown 处理（open）+ pointerup 处理（drag 选中/保持开）。
 * 键盘点击：由 keydown 处理（Enter/Space toggle）。
 * 浏览器在键盘激活时也会派发 click，本 handler 主要是防止 click 引发的副作用。
 */
function onTriggerClick(evt: MouseEvent): void {
  // 若是拖放路径刚刚 emit 过，避免后续 click 把状态搞混
  if (isPointerDragging.value) {
    isPointerDragging.value = false;
  }
  evt?.preventDefault?.();
}

/**
 * 触发器按下：双模式预备态。
 *
 * - 单击（无移动）：pointerdown 时 open()；pointerup 时保持打开。
 *   → 用户后续可点击扇片选中，或点击 overlay 空白关闭。
 * - 按住拖动：pointerdown → pointermove 超阈值 → isPointerDragging=true。
 *   → pointerup 时落点在可选扇片 → 自动选中并关闭。
 *
 * 不使用 setPointerCapture：它会把 pointermove/pointerup 路由到 trigger，
 * 与 window 级监听冲突。改为 window-level 监听确保事件流畅地从 trigger 流到 overlay。
 */
function onTriggerPointerDown(evt: PointerEvent): void {
  if (props.disabled) return;
  if (isOpen.value) return; // 已开时 overlay 覆盖 trigger，理论不会到这里；防御性早退

  evt.preventDefault();
  pointerDownOnTrigger.value = true;
  isPointerDragging.value = false;
  activePointerId = evt.pointerId;
  pointerStart = { x: evt.clientX, y: evt.clientY };
  open();

  window.addEventListener('pointermove', onWindowPointerMove, true);
  window.addEventListener('pointerup', onWindowPointerUp, true);
  window.addEventListener('pointercancel', onWindowPointerUp, true);
}

/** 全局 pointermove：当 trigger 按下时跟踪拖放并高亮当前扇片 */
function onWindowPointerMove(evt: PointerEvent): void {
  if (activePointerId !== null && evt.pointerId !== activePointerId) return;
  if (!isOpen.value || !pointerDownOnTrigger.value) return;

  // 距离阈值：移动 < 6px 视为微抖，不进入拖动态
  if (!isPointerDragging.value) {
    const dx = evt.clientX - pointerStart.x;
    const dy = evt.clientY - pointerStart.y;
    if (Math.hypot(dx, dy) < DRAG_THRESHOLD_PX) return;
    isPointerDragging.value = true;
  }

  const hit = findSlotAt(evt.clientX, evt.clientY);
  hoverIndex.value = hit;
}

/** 全局 pointerup / pointercancel：判定拖放选中或保持打开 */
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
    // 拖放路径：检查落点是否在可选扇片上
    const hit = findSlotAt(evt.clientX, evt.clientY);
    if (hit >= 0) {
      const opt = displayOptions.value[hit];
      if (opt && !isOptionDisabled(opt)) {
        commitSelectionAndClose(opt.value, hit);
        return;
      }
    }
    // 拖到空白或 disabled 扇片：视为取消，保持打开等待用户点击
    hoverIndex.value = -1;
  }
  // 纯点击（无拖动）：保持打开，用户后续可点击扇片或空白
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

/** Overlay 上的 pointerdown：点击空白关闭轮盘 */
function onOverlayPointerDown(evt: PointerEvent): void {
  if (evt.target === overlayRef.value) {
    close();
  }
}

/** 点击某个扇片直接选中并关闭轮盘 */
function onSlotClick(opt: RadialOption): void {
  if (isOptionDisabled(opt)) return;
  if (opt.value === props.value) {
    close();
    return;
  }
  // 查找被点击扇片在当前渲染列表中的索引，保证 commit 后 hover 高亮位置准确
  const idx = displayOptions.value.findIndex(o => o.value === opt.value);
  commitSelectionAndClose(opt.value, idx);
}

/** 在扇片上按下，仅同步 hover 状态（不进入 trigger 的拖放追踪） */
function onSlotPointerDown(_evt: PointerEvent, idx: number): void {
  hoverIndex.value = idx;
}

/** 在指定屏幕坐标上找出最接近的可选扇片索引（返回 -1 表示无） */
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

/** 监听 Escape 全局关闭 */
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

// 当渲染的扇片数量变化时重置 slotRefs 长度
watch(() => displayOptions.value.length, (len) => {
  slotRefs.value = slotRefs.value.slice(0, len);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onGlobalKeyDown, true);
  window.removeEventListener('resize', onWindowResize);
  // 防御性：组件卸载时若仍处于拖放追踪态，清理监听
  window.removeEventListener('pointermove', onWindowPointerMove, true);
  window.removeEventListener('pointerup', onWindowPointerUp, true);
  window.removeEventListener('pointercancel', onWindowPointerUp, true);
});
</script>

<style scoped>
.agent-radial-picker {
  position: relative;
  display: inline-flex;
  align-items: center;
}

/* ============ 触发器：纯圆形 Agent 头像 ============ */
.picker-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  background: var(--spark-bg-soft, var(--spark-bg));
  border: 1px solid var(--spark-border);
  border-radius: 50%;
  color: var(--spark-text);
  cursor: pointer;
  font-family: inherit;
  outline: none;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.18s ease;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
}

.picker-trigger:hover:not(:disabled),
.picker-trigger.is-open {
  border-color: color-mix(in srgb, var(--spark-primary) 55%, var(--spark-border));
  background: color-mix(in srgb, var(--spark-primary) 8%, var(--spark-bg-soft, var(--spark-bg)));
  box-shadow: 0 2px 10px color-mix(in srgb, var(--spark-primary) 16%, transparent);
}

.picker-trigger:focus-visible {
  border-color: var(--spark-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--spark-primary) 25%, transparent);
}

.picker-trigger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.picker-trigger-avatar {
  flex-shrink: 0;
}

/* ============ 轮盘 Overlay ============ */
.agent-radial-overlay {
  position: fixed;
  inset: 0;
  z-index: 9000;
  /* 中等强度背景遮罩：让轮盘视觉聚焦，避免下方聊天内容透过来盖住扇片名字 */
  background: color-mix(in srgb, var(--spark-bg) 70%, transparent);
  backdrop-filter: blur(6px) saturate(0.85);
  -webkit-backdrop-filter: blur(6px) saturate(0.85);
  pointer-events: auto;
  outline: none;
  touch-action: none;
}

.agent-radial-wheel {
  position: absolute;
  /* 轮盘视为 0x0 的圆心点，通过 left/top 定位，子元素以中心展开 */
  width: 0;
  height: 0;
  pointer-events: none;
}

/* 让子元素可点击（覆盖 wheel 的 pointer-events: none） */
.agent-radial-wheel > * {
  pointer-events: auto;
}

/* ============ 中央交互提示徽章 ============ */
.agent-radial-hint {
  position: absolute;
  left: 0;
  top: 0;
  /* 居中于 wheel 圆心 */
  transform: translate(-50%, -50%);
  padding: 9px 16px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--spark-bg-soft, var(--spark-bg)) 90%, transparent);
  border: 1px dashed color-mix(in srgb, var(--spark-primary) 45%, transparent);
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-xs, 12px);
  font-weight: 600;
  letter-spacing: 0.3px;
  white-space: nowrap;
  /* 不参与命中判定，避免拖动时被它截胡 */
  pointer-events: none;
  /* 呼吸光环动画——暗示"可交互" */
  animation: agentRadialHintBreathe 2.4s ease-in-out infinite;
}

@keyframes agentRadialHintBreathe {
  0%, 100% {
    opacity: 0.65;
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--spark-primary) 24%, transparent);
  }
  50% {
    opacity: 1;
    box-shadow: 0 0 0 10px color-mix(in srgb, var(--spark-primary) 0%, transparent);
  }
}

/* 拖动时 hint 淡出：用户已经在拖了，不需要继续提示——同时避免文字干扰扇片视觉 */
.agent-radial-hint.is-dragging {
  animation: none;
  opacity: 0;
  transition: opacity 0.16s ease-out;
}

/* ============ 扇片：圆形头像按钮 ============ */
.agent-radial-slot {
  position: absolute;
  left: 0;
  top: 0;
  /* 圆形尺寸固定 */
  width: 64px;
  height: 64px;
  border-radius: 50%;
  /* 偏移：所有 transform 都收口在这里，hover 状态不再额外修改 transform 通道 */
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
  border-color: color-mix(in srgb, var(--spark-primary) 60%, var(--spark-border));
  box-shadow:
    0 10px 24px rgba(0, 0, 0, 0.18),
    0 0 0 3px color-mix(in srgb, var(--spark-primary) 22%, transparent);
}

.agent-radial-slot:focus-visible {
  outline: none;
  border-color: var(--spark-primary);
  box-shadow:
    0 6px 14px rgba(0, 0, 0, 0.12),
    0 0 0 3px color-mix(in srgb, var(--spark-primary) 35%, transparent);
}

.agent-radial-slot.is-disabled,
.agent-radial-slot:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  filter: grayscale(0.45);
}

/* 名字浮在圆下方：pointer-events:none 保证 hover 命中区域只算圆形本体，避免抖动循环 */
.agent-radial-slot-name {
  position: absolute;
  top: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  font-size: var(--spark-fs-2xs, 11px);
  color: var(--spark-text-muted);
  font-weight: 600;
  letter-spacing: 0.2px;
  white-space: nowrap;
  pointer-events: none;
  /* 暗背景上的可读性兜底 */
  text-shadow: 0 0 6px var(--spark-bg);
}

/* ============ 入场/退场动画 ============
 * 设计：
 *   - Overlay（背景遮罩 + blur）走 opacity fade
 *   - 内部 wheel 整体走 scale 动画——从 trigger 附近的"小种子"爆发到完整尺寸
 *   - wheel 是 0×0 圆点 + 静态没有 transform，所以这里加 scale 安全可控
 *   - ⚠️ 严禁在子 button（.agent-radial-slot）上加 transform 动画，
 *     否则会与它们自身的 absolute 定位 transform 抢占同一属性通道，产生闪烁
 */
.agent-radial-fade-enter-active,
.agent-radial-fade-leave-active {
  transition: opacity 0.22s ease;
}

.agent-radial-fade-enter-from,
.agent-radial-fade-leave-to {
  opacity: 0;
}

/* Wheel 整体 scale 入场——从 0.4 倍带轻微 overshoot 反弹到 1.0 */
.agent-radial-fade-enter-active .agent-radial-wheel {
  animation: agentWheelPop 0.34s cubic-bezier(0.34, 1.4, 0.64, 1) both;
  /* 提示浏览器开启 GPU 合成层，让 scale 动画更顺滑 */
  will-change: transform;
}

/* Wheel 整体 scale 退场——平滑收缩回中心 */
.agent-radial-fade-leave-active .agent-radial-wheel {
  animation: agentWheelCollapse 0.2s cubic-bezier(0.4, 0, 0.7, 0.2) both;
  will-change: transform;
}

@keyframes agentWheelPop {
  0% {
    transform: scale(0.4);
  }
  60% {
    transform: scale(1.04);
  }
  100% {
    transform: scale(1);
  }
}

@keyframes agentWheelCollapse {
  0% {
    transform: scale(1);
  }
  100% {
    transform: scale(0.6);
  }
}

/* Trigger 在轮盘展开时温和"内陷"，给点视觉反馈表示"已经按下并展开了" */
.picker-trigger.is-open {
  /* 已通过 background/border 颜色变化体现，这里不动 transform */
}

/* 尊重"减少动效"偏好——禁用 scale 动画，只保留 opacity fade */
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

/* 移动端触屏调优：圆形扇片放大方便点击 */
@media (pointer: coarse) {
  .picker-trigger {
    padding: 5px 10px 5px 5px;
  }
  .agent-radial-slot {
    width: 72px;
    height: 72px;
  }
}
</style>
