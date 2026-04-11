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
    <!-- 火柴棒（能量导管） -->
    <rect x="10.8" y="12" width="2.4" height="10" rx="1.2" class="ci-stick" />
    <!-- 火焰外层（星云光晕） -->
    <path
      d="M12 1C12 1 7 6.2 7 10C7 12.8 8.8 14.5 12 14.5C15.2 14.5 17 12.8 17 10C17 6.2 12 1 12 1Z"
      class="ci-flame-outer"
    />
    <!-- 火焰中层（星火） -->
    <path
      d="M12 4C12 4 9 7.2 9 9.5C9 11.2 10.2 12.5 12 12.5C13.8 12.5 15 11.2 15 9.5C15 7.2 12 4 12 4Z"
      class="ci-flame-mid"
    />
    <!-- 火焰核心（白热中心） -->
    <path
      d="M12 6.5C12 6.5 10.5 8.2 10.5 9.5C10.5 10.5 11.1 11.2 12 11.2C12.9 11.2 13.5 10.5 13.5 9.5C13.5 8.2 12 6.5 12 6.5Z"
      class="ci-flame-core"
    />
    <!-- 发光粒子点缀 -->
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
  color?: 'auto' | 'primary' | 'warning' | 'danger';
}>(), {
  size: '1em',
  color: 'auto',
});

const colorClass = computed(() => `credit-icon--${props.color}`);
</script>

<style scoped>
.credit-icon {
  display: inline-flex;
  vertical-align: middle;
  flex-shrink: 0;
}

/* ---- 火柴棒（能量导管） ---- */
.ci-stick {
  fill: #a0785a;
}

/* ---- 火焰外层（星云光晕） ---- */
.ci-flame-outer {
  fill: #f0a040;
  filter: drop-shadow(0 0 2px rgba(240, 160, 64, 0.45));
}

/* ---- 火焰中层（星火） ---- */
.ci-flame-mid {
  fill: #ff6b35;
}

/* ---- 火焰核心（白热中心） ---- */
.ci-flame-core {
  fill: #ffe066;
}

/* ---- 发光粒子 ---- */
.ci-spark {
  fill: #ffd43b;
  opacity: 0.7;
}

/* ---- primary 配色 ---- */
.credit-icon--primary .ci-flame-outer {
  fill: #f0a040;
}
.credit-icon--primary .ci-flame-mid {
  fill: #ff6b35;
}

/* ---- warning 配色 ---- */
.credit-icon--warning .ci-flame-outer {
  fill: #f0a040;
  filter: drop-shadow(0 0 3px rgba(240, 160, 64, 0.5));
}
.credit-icon--warning .ci-flame-mid {
  fill: #ffd43b;
}
.credit-icon--warning .ci-flame-core {
  fill: #fff3bf;
}

/* ---- danger 配色 ---- */
.credit-icon--danger .ci-flame-outer {
  fill: #e03131;
  filter: drop-shadow(0 0 3px rgba(224, 49, 49, 0.5));
}
.credit-icon--danger .ci-flame-mid {
  fill: #f76707;
}
.credit-icon--danger .ci-flame-core {
  fill: #ffe066;
}
</style>
