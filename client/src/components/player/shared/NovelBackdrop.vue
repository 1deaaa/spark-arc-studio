<template>
  <div class="novel-backdrop" :class="[`mode-${mode}`, { 'is-framed': framed }]">
    <div class="novel-backdrop-light" aria-hidden="true"></div>
    <div class="novel-backdrop-texture" aria-hidden="true"></div>
    <div class="novel-backdrop-content">
      <slot name="overlay"></slot>
      <slot></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  mode?: 'panel' | 'viewport';
  framed?: boolean;
}>(), {
  mode: 'panel',
  framed: false,
});
</script>

<style scoped>
.novel-backdrop {
  position: relative;
  overflow: hidden;
  color: var(--spark-text);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--spark-panel-bg), black 4%), var(--spark-bg));
}

.novel-backdrop.mode-panel {
  height: 100%;
}

.novel-backdrop.mode-viewport {
  min-height: 100vh;
}

.novel-backdrop.is-framed {
  border: 1px solid color-mix(in srgb, var(--spark-primary), var(--spark-border) 24%);
}

.novel-backdrop-light,
.novel-backdrop-texture,
.novel-backdrop-content {
  position: absolute;
  inset: 0;
}

.novel-backdrop-light {
  background:
    linear-gradient(180deg, color-mix(in srgb, white, transparent 98.6%), transparent 18%),
    linear-gradient(90deg, color-mix(in srgb, var(--spark-primary), transparent 98.8%) 0%, transparent 16%, transparent 84%, color-mix(in srgb, var(--spark-primary), transparent 98.8%) 100%);
}

.novel-backdrop-texture {
  opacity: 0.82;
  background:
    repeating-linear-gradient(
      35deg,
      color-mix(in srgb, var(--spark-primary), transparent 98.9%) 0,
      color-mix(in srgb, var(--spark-primary), transparent 98.9%) 2px,
      transparent 2px,
      transparent 8px
    ),
    repeating-linear-gradient(
      125deg,
      color-mix(in srgb, white, transparent 99%) 0,
      color-mix(in srgb, white, transparent 99%) 1px,
      transparent 1px,
      transparent 7px
    ),
    radial-gradient(circle at 20% 24%, color-mix(in srgb, white, transparent 99.1%) 0 1px, transparent 1px),
    radial-gradient(circle at 78% 68%, color-mix(in srgb, var(--spark-primary), transparent 99.15%) 0 1px, transparent 1px);
  background-size: auto, auto, 18px 18px, 22px 22px;
  mix-blend-mode: soft-light;
}

.novel-backdrop-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  min-height: inherit;
  height: 100%;
}
</style>
