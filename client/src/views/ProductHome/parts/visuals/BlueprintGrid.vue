<!--
  BlueprintGrid · 全局蓝图网格背景层
  纯 SVG pattern，零网络请求，零主线程占用。
  两层网格叠加：40px 细网 + 200px 粗网，模拟工业蓝图坐标系。
-->
<template>
  <div class="blueprint-grid" aria-hidden="true">
    <svg
      class="grid-svg"
      width="100%"
      height="100%"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <!-- 细网 40px -->
        <pattern id="bp-fine" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="var(--blueprint)" stroke-width="0.8" />
        </pattern>
        <!-- 粗网 200px -->
        <pattern id="bp-coarse" width="200" height="200" patternUnits="userSpaceOnUse">
          <path d="M 200 0 L 0 0 0 200" fill="none" stroke="var(--blueprint-k)" stroke-width="1.1" />
        </pattern>
        <!-- 墨水晕染滤镜 -->
        <filter id="ink-blot">
          <feGaussianBlur stdDeviation="60" />
        </filter>
      </defs>

      <!-- 双层网格 -->
      <rect width="100%" height="100%" fill="url(#bp-fine)" />
      <rect width="100%" height="100%" fill="url(#bp-coarse)" />

      <!-- 几处柔和墨水晕染（装饰，随视口固定） -->
      <g filter="url(#ink-blot)" opacity="0.06">
        <ellipse cx="15%" cy="20%" rx="180" ry="120" fill="var(--ember)" />
        <ellipse cx="85%" cy="70%" rx="240" ry="160" fill="var(--moss)" />
        <ellipse cx="50%" cy="50%" rx="120" ry="80" fill="var(--gold)" />
      </g>
    </svg>
  </div>
</template>

<script setup lang="ts">
/* 纯展示组件，无逻辑 */
</script>

<style scoped>
.blueprint-grid {
  width: 100%;
  height: 100%;
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.grid-svg {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
