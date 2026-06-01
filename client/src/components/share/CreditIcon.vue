<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    class="credit-icon"
    :class="[colorClass]"
  >
    <!-- 火柴棒（能量导管，木色保持不变，与主题色无关） -->
    <rect x="10.8" y="12" width="2.4" height="10" rx="1.2" class="ci-stick" />
    <!-- 火焰外层（光晕，主题色淡化） -->
    <path
      d="M12 1C12 1 7 6.2 7 10C7 12.8 8.8 14.5 12 14.5C15.2 14.5 17 12.8 17 10C17 6.2 12 1 12 1Z"
      class="ci-flame-outer"
    />
    <!-- 火焰中层（主题色主体） -->
    <path
      d="M12 4C12 4 9 7.2 9 9.5C9 11.2 10.2 12.5 12 12.5C13.8 12.5 15 11.2 15 9.5C15 7.2 12 4 12 4Z"
      class="ci-flame-mid"
    />
    <!-- 火焰核心（白热中心，主题色提亮） -->
    <path
      d="M12 6.5C12 6.5 10.5 8.2 10.5 9.5C10.5 10.5 11.1 11.2 12 11.2C12.9 11.2 13.5 10.5 13.5 9.5C13.5 8.2 12 6.5 12 6.5Z"
      class="ci-flame-core"
    />
    <!-- 发光粒子（强调色点缀） -->
    <circle cx="8.5" cy="5.5" r="0.6" class="ci-spark" />
    <circle cx="15.5" cy="4" r="0.5" class="ci-spark" />
    <circle cx="6.5" cy="9" r="0.4" class="ci-spark" />
    <circle cx="17.5" cy="8" r="0.45" class="ci-spark" />
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(defineProps<{
  size?: number | string;
  /**
   * 颜色模式：
   * - auto: 跟随父元素 currentColor（推荐，自动适配主题色和上下文状态）
   * - primary: 强制使用主题主色 --spark-primary
   * - warning: 强制使用主题警告色 --spark-warning
   * - danger: 强制使用主题危险色 --spark-danger
   */
  color?: 'auto' | 'primary' | 'warning' | 'danger';
}>(), {
  size: '1em',
  // 默认 primary：火柴作为计费货币符号，默认就应当醒目地呈现主题色
  // 需要跟随父元素文字色（如开关 active 状态切换）的场景请显式传 color="auto"
  color: 'primary',
});

const colorClass = computed(() => `credit-icon--${props.color}`);
</script>

<style scoped>
.credit-icon {
  display: inline-flex;
  vertical-align: middle;
  flex-shrink: 0;
}

/* ============================================================
   火柴棒：始终保持木色，与主题色无关（毕竟火柴棒就是木头）
   ============================================================ */
.ci-stick {
  fill: #a0785a;
}

/* ============================================================
   auto 模式（默认）：火焰跟随 currentColor
   - 父元素设置什么 color，火焰就是什么色
   - 通过透明度分层（外淡、中实、核亮）形成立体感
   ============================================================ */
.credit-icon--auto .ci-flame-outer {
  fill: currentColor;
  opacity: 0.45;
}
.credit-icon--auto .ci-flame-mid {
  fill: currentColor;
  opacity: 0.85;
}
.credit-icon--auto .ci-flame-core {
  /* 核心用主题色与白色混合，营造"白热中心"效果 */
  fill: color-mix(in srgb, currentColor 35%, #ffffff 65%);
}
.credit-icon--auto .ci-spark {
  fill: currentColor;
  opacity: 0.7;
}

/* ============================================================
   primary 模式：强制主题主色
   ============================================================ */
.credit-icon--primary .ci-flame-outer {
  fill: var(--spark-primary);
  opacity: 0.45;
  filter: drop-shadow(0 0 2px color-mix(in srgb, var(--spark-primary), transparent 60%));
}
.credit-icon--primary .ci-flame-mid {
  fill: var(--spark-primary);
}
.credit-icon--primary .ci-flame-core {
  fill: color-mix(in srgb, var(--spark-primary) 30%, #ffffff 70%);
}
.credit-icon--primary .ci-spark {
  fill: var(--spark-accent, var(--spark-primary));
  opacity: 0.8;
}

/* ============================================================
   warning 模式：强制主题警告色
   ============================================================ */
.credit-icon--warning .ci-flame-outer {
  fill: var(--spark-warning);
  opacity: 0.45;
  filter: drop-shadow(0 0 3px color-mix(in srgb, var(--spark-warning), transparent 50%));
}
.credit-icon--warning .ci-flame-mid {
  fill: var(--spark-warning);
}
.credit-icon--warning .ci-flame-core {
  fill: color-mix(in srgb, var(--spark-warning) 25%, #ffffff 75%);
}
.credit-icon--warning .ci-spark {
  fill: var(--spark-warning);
  opacity: 0.75;
}

/* ============================================================
   danger 模式：强制主题危险色
   ============================================================ */
.credit-icon--danger .ci-flame-outer {
  fill: var(--spark-danger);
  opacity: 0.45;
  filter: drop-shadow(0 0 3px color-mix(in srgb, var(--spark-danger), transparent 50%));
}
.credit-icon--danger .ci-flame-mid {
  fill: var(--spark-danger);
}
.credit-icon--danger .ci-flame-core {
  fill: color-mix(in srgb, var(--spark-danger) 30%, #ffffff 70%);
}
.credit-icon--danger .ci-spark {
  fill: var(--spark-danger);
  opacity: 0.75;
}
</style>
