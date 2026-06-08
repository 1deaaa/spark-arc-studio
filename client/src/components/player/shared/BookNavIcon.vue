<template>
  <span class="book-nav-icon" :class="{ active }" @mouseenter="active = true" @mouseleave="active = false">
    <svg viewBox="0 0 32 32" width="28" height="28" xmlns="http://www.w3.org/2000/svg">
      <!-- 书脊 -->
      <rect class="spine" x="15" y="2" width="2" height="28" rx="1" fill="currentColor" opacity="0.5" />

      <!-- 左封面（固定） -->
      <rect class="cover-left" x="3" y="2" width="12" height="28" rx="2"
        fill="currentColor" opacity="0.25" />

      <!-- 右封面（可翻转） -->
      <g class="cover-right-origin" style="transform-origin: 16px 16px;">
        <rect class="cover-right" x="17" y="2" width="12" height="28" rx="2"
          fill="currentColor" opacity="0.25" />
      </g>

      <!-- 翻页层（每页独立翻转） -->
      <g class="page-wrap page-wrap-1" style="transform-origin: 16px 16px;">
        <rect x="16" y="4" width="11" height="24" rx="1.5"
          fill="currentColor" opacity="0.12" />
      </g>
      <g class="page-wrap page-wrap-2" style="transform-origin: 16px 16px;">
        <rect x="16" y="4" width="11" height="24" rx="1.5"
          fill="currentColor" opacity="0.10" />
      </g>
      <g class="page-wrap page-wrap-3" style="transform-origin: 16px 16px;">
        <rect x="16" y="4" width="11" height="24" rx="1.5"
          fill="currentColor" opacity="0.08" />
      </g>

      <!-- 左页文字装饰线 -->
      <g class="text-lines" opacity="0.3">
        <rect x="5" y="8" width="8" height="1.2" rx="0.6" fill="currentColor" />
        <rect x="5" y="12" width="7" height="1.2" rx="0.6" fill="currentColor" />
        <rect x="5" y="16" width="8" height="1.2" rx="0.6" fill="currentColor" />
        <rect x="5" y="20" width="6" height="1.2" rx="0.6" fill="currentColor" />
      </g>
    </svg>
  </span>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const active = ref(false);
</script>

<style scoped>
.book-nav-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--book-nav-text, var(--spark-text, #d8dce8));
  transition: color 0.3s;
}

.book-nav-icon:hover {
  color: var(--book-nav-accent, var(--spark-primary, #7b9ec4));
}

/* --- 右封面：打开动画 --- */
.cover-right-origin {
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  transform: perspective(200px) rotateY(0deg);
}

.book-nav-icon.active .cover-right-origin {
  transform: perspective(200px) rotateY(-160deg);
}

/* --- 翻页动画：每页独立级联翻转 --- */
.page-wrap {
  transform: perspective(200px) rotateY(0deg);
}

.book-nav-icon.active .page-wrap-1 {
  animation: flip-page 3s ease-in-out infinite 0.35s;
}
.book-nav-icon.active .page-wrap-2 {
  animation: flip-page 3s ease-in-out infinite 1.35s;
}
.book-nav-icon.active .page-wrap-3 {
  animation: flip-page 3s ease-in-out infinite 2.35s;
}

@keyframes flip-page {
  0%   { transform: perspective(200px) rotateY(0deg); }
  10%  { transform: perspective(200px) rotateY(-170deg); }
  23%  { transform: perspective(200px) rotateY(-170deg); }
  33%  { transform: perspective(200px) rotateY(0deg); }
  100% { transform: perspective(200px) rotateY(0deg); }
}

/* --- 左页文字淡入 --- */
.text-lines {
  transition: opacity 0.3s;
  opacity: 0.2;
}

.book-nav-icon.active .text-lines {
  opacity: 0.45;
}
</style>
