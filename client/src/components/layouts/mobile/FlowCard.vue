<template>
  <section 
    class="flow-card" 
    :id="`step-${step}`"
    :class="{ 'is-active': isActive }"
  >
    <!-- Secondary titles removed to maximize vertical space -->
    
    <div class="flow-card-content">
      <slot />
    </div>
    
    <footer class="flow-card-footer" v-if="showNextButton || $slots.footer">
      <slot name="footer">
        <button 
          v-if="showNextButton" 
          class="next-step-fab"
          @click="scrollToNext"
          aria-label="下一步"
        >
          <svg viewBox="0 0 24 24" fill="none" class="fab-icon">
             <circle cx="12" cy="12" r="11" stroke="currentColor" stroke-width="1.5" class="fab-circle"/>
             <path d="M12 8L12 16M12 16L15 13M12 16L9 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="fab-arrow"/>
          </svg>
          <span class="fab-ripple"></span>
        </button>
      </slot>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps({
  step: {
    type: Number,
    required: true
  },
  title: {
    type: String,
    required: true
  },
  subtitle: {
    type: String,
    default: ''
  },
  nextLabel: {
    type: String,
    default: '下一步'
  },
  showNextButton: {
    type: Boolean,
    default: true
  },
  isActive: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['next']);

function scrollToNext() {
  const nextStep = document.getElementById(`step-${props.step + 1}`);
  if (nextStep) {
    nextStep.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  emit('next');
}
</script>

<style scoped>
.flow-card {
  /* 确保宽度正确 */
  width: 100%;
  max-width: 100vw;
  flex-shrink: 0;

  min-height: 100vh;
  min-height: 100dvh;
  scroll-snap-align: start;
  scroll-snap-stop: always;
  
  display: flex;
  flex-direction: column;
  padding: 10px;
  padding-top: calc(var(--mobile-header-height, 48px) + var(--sat, 0px) + 8px);
  padding-bottom: calc(var(--sab, env(safe-area-inset-bottom, 0px)) + 12px);
  
  /* 简化背景 */
  background: var(--spark-bg);
  border-bottom: 1px solid var(--spark-border);
  
  position: relative;
  overflow: hidden;
  box-sizing: border-box;
}

/* 移除装饰性伪元素 */
.flow-card::before,
.flow-card::after {
  display: none;
}

/* 卡片激活时的视觉反馈 */
.flow-card.is-active .flow-card-header {
  opacity: 1;
}

.flow-card-header {
  display: flex;
  align-items: flex-start;
  margin-bottom: 24px;
  opacity: 0.85;
  transition: opacity 0.3s ease;
  padding-left: 4px;
}

.header-text {
  flex: 1;
  min-width: 0;
}

.title-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
}

.card-title {
  margin: 0;
  font-size: var(--spark-fs-display); /* 更大一点 */
  font-weight: 800;
  color: var(--spark-text);
  line-height: 1.2;
  letter-spacing: -0.5px;
}

.card-subtitle {
  margin: 0;
  font-size: var(--spark-fs-base);
  color: var(--spark-text-muted);
  line-height: 1.4;
  font-weight: 500;
}

.flow-card-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
  padding-bottom: 20px;
}

.flow-card-footer {
  padding-top: 16px;
  display: flex;
  justify-content: center;
  align-items: center;
}

/* 下一步 FAB 按钮 */
.next-step-fab {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: transparent;
  border: none;
  cursor: pointer;
  position: relative;
  color: var(--spark-primary); /* 使用主题色 */
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  margin-bottom: 12px;
}

.next-step-fab:active {
  transform: scale(0.9);
}

.fab-icon {
  width: 44px;
  height: 44px;
  overflow: visible;
}

.fab-circle {
  opacity: 0.3;
  transition: opacity 0.3s;
}

.next-step-fab:hover .fab-circle {
  opacity: 0.8;
}

.fab-arrow {
  animation: flow-arrow 2s infinite ease-in-out;
  transform-origin: center;
}

@keyframes flow-arrow {
  0%, 100% { transform: translateY(-3px); }
  50% { transform: translateY(3px); }
}

/* 呼吸光环 */
.next-step-fab::before {
  content: '';
  position: absolute;
  inset: 0px;
  border-radius: 50%;
  border: 1px solid var(--spark-primary);
  opacity: 0;
  animation: ripple 3s infinite;
}

@keyframes ripple {
  0% { transform: scale(0.8); opacity: 0; }
  30% { opacity: 0.4; }
  100% { transform: scale(1.2); opacity: 0; }
}
</style>
