<template>
  <div class="step-indicator">
    <div 
      v-for="(step, index) in steps" 
      :key="step.id"
      class="step-dot"
      :class="{ 
        'is-active': currentStep === index,
        'is-completed': index < currentStep 
      }"
      @click="scrollToStep(index)"
    >
      <div class="dot-inner" />
      <span class="step-label">{{ step.label }}</span>
    </div>
    
    <!-- 进度线 -->
    <div class="progress-line">
      <div 
        class="progress-fill" 
        :style="{ height: progressHeight }"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';

const props = defineProps({
  steps: {
    type: Array,
    required: true,
    // 格式: [{ id: 'world', label: '灵感' }, ...]
  },
  containerRef: {
    type: Object,
    default: null
  }
});

const currentStep = ref(0);

const progressHeight = computed(() => {
  if (props.steps.length <= 1) return '0%';
  const percent = (currentStep.value / (props.steps.length - 1)) * 100;
  return `${percent}%`;
});

function scrollToStep(index) {
  const stepId = `step-${index + 1}`;
  const element = document.getElementById(stepId);
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

// 使用 IntersectionObserver 检测当前可见卡片
let observer = null;

function setupObserver() {
  const options = {
    root: props.containerRef?.value || null,
    rootMargin: '-40% 0px -40% 0px',
    threshold: 0
  };
  
  observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const id = entry.target.id;
        const match = id.match(/step-(\d+)/);
        if (match) {
          currentStep.value = parseInt(match[1]) - 1;
        }
      }
    });
  }, options);
  
  // 观察所有步骤卡片
  props.steps.forEach((_, index) => {
    const element = document.getElementById(`step-${index + 1}`);
    if (element) {
      observer.observe(element);
    }
  });
}

onMounted(() => {
  // 延迟设置以确保 DOM 已渲染
  setTimeout(setupObserver, 100);
});

onUnmounted(() => {
  if (observer) {
    observer.disconnect();
  }
});
</script>

<style scoped>
.step-indicator {
  position: fixed;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 100;
  
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 12px 8px;
  
  background: rgba(var(--spark-panel-bg-rgb), 0.8);
  backdrop-filter: blur(12px);
  border-radius: 20px;
  border: 1px solid rgba(var(--spark-border-rgb), 0.5);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}

.step-dot {
  position: relative;
  width: 12px;
  height: 12px;
  cursor: pointer;
  z-index: 2;
  
  display: flex;
  align-items: center;
  justify-content: center;
}

.dot-inner {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--spark-text-muted);
  transition: all 0.3s ease;
}

.step-dot.is-active .dot-inner {
  width: 12px;
  height: 12px;
  background: var(--spark-primary);
  box-shadow: 0 0 12px rgba(var(--spark-primary-rgb), 0.5);
}

.step-dot.is-completed .dot-inner {
  background: var(--spark-success);
}

.step-label {
  position: absolute;
  right: 20px;
  white-space: nowrap;
  
  font-size: 11px;
  font-weight: 500;
  color: var(--spark-text);
  background: var(--spark-panel-bg);
  padding: 4px 8px;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  
  opacity: 0;
  transform: translateX(8px);
  pointer-events: none;
  transition: all 0.2s ease;
}

.step-dot:hover .step-label,
.step-dot.is-active .step-label {
  opacity: 1;
  transform: translateX(0);
}

/* 进度线 */
.progress-line {
  position: absolute;
  top: 18px;
  bottom: 18px;
  left: 50%;
  transform: translateX(-50%);
  width: 2px;
  background: rgba(var(--spark-border-rgb), 0.5);
  border-radius: 1px;
  z-index: 1;
  overflow: hidden;
}

.progress-fill {
  width: 100%;
  background: linear-gradient(
    to bottom,
    var(--spark-primary),
    var(--spark-success)
  );
  border-radius: 1px;
  transition: height 0.3s ease;
}

/* 小屏幕隐藏标签，只显示圆点 */
@media (max-width: 380px) {
  .step-indicator {
    right: 8px;
    padding: 8px 6px;
    gap: 12px;
  }
  
  .step-label {
    display: none;
  }
}
</style>
