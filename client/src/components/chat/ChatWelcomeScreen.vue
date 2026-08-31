<template>
  <div class="chat-welcome">
    <!-- 中心火花动画：复用全局加载动画 -->
    <SparkLoaderAnimation class="welcome-spark-anim" aria-hidden="true" />

    <!-- 欢迎标题 -->
    <h2 class="welcome-title">{{ t('components.chatWelcome.title') }}</h2>
    <p class="welcome-subtitle">{{ t('components.chatWelcome.subtitle') }}</p>

    <!-- 快速开始提示 -->
    <div class="welcome-tips">
      <div class="tip-section">
        <div class="tip-section-header">
          <svg viewBox="0 0 20 20" fill="none" class="tip-icon tip-icon-rocket">
            <path d="M10 2C10 2 14 6 14 10C14 12 12.5 14 10 14C7.5 14 6 12 6 10C6 6 10 2 10 2Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M10 14V18" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            <path d="M7 18H13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
          </svg>
          <span class="tip-section-title">{{ t('components.chatWelcome.quickStart') }}</span>
        </div>
        <ul class="tip-list">
          <li v-for="(tip, i) in quickStartTips" :key="i" class="tip-item">
            <span class="tip-num">{{ i + 1 }}</span>
            <span class="tip-text">{{ tip }}</span>
          </li>
        </ul>
      </div>

      <div class="tip-divider"></div>

      <div class="tip-section">
        <div class="tip-section-header">
          <svg viewBox="0 0 20 20" fill="none" class="tip-icon tip-icon-studio">
            <rect x="2" y="4" width="16" height="12" rx="2" stroke="currentColor" stroke-width="1.5" />
            <path d="M6 8H10M6 11H14" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
            <circle cx="15" cy="7" r="1.2" fill="currentColor" />
          </svg>
          <span class="tip-section-title">{{ t('components.chatWelcome.proWorkflow') }}</span>
        </div>
        <p class="tip-section-hint">{{ t('components.chatWelcome.proWorkflowHint') }}</p>
        <ul class="tip-list">
          <li v-for="(tip, i) in proTips" :key="i" class="tip-item">
            <span class="tip-num">{{ i + 1 }}</span>
            <span class="tip-text">{{ tip.text }}</span>
            <n-tooltip trigger="hover">
              <template #trigger>
                <button class="tip-goto" @click.stop="goToView(tip.view)">
                  <svg viewBox="0 0 18 18" fill="none" class="tip-goto-svg">
                    <circle cx="9" cy="9" r="7.5" stroke="currentColor" stroke-width="0.8"/>
                    <path d="M7.5 5.5L11.5 9L7.5 12.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </button>
              </template>
              {{ t('components.chatWelcome.goToPage') }}
            </n-tooltip>
          </li>
        </ul>
      </div>
    </div>

    <!-- 底部快捷提示 -->
    <div class="welcome-footer">
      <span class="footer-hint">{{ t('components.chatWelcome.footerHint') }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { NTooltip } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import { useViewStore, type AppViewKey } from '@/components/stores/viewStore';
import SparkLoaderAnimation from '@/components/share/SparkLoaderAnimation.vue';

const { t } = useI18n();
const viewStore = useViewStore();

const quickStartTips = computed(() => [
  t('components.chatWelcome.quickTip1'),
  t('components.chatWelcome.quickTip2'),
  t('components.chatWelcome.quickTip3'),
  t('components.chatWelcome.quickTip4'),
]);

const proTips = computed(() => [
  { text: t('components.chatWelcome.proTip1'), view: 'world' as AppViewKey },
  { text: t('components.chatWelcome.proTip2'), view: 'synopsis' as AppViewKey },
  { text: t('components.chatWelcome.proTip3'), view: 'structure' as AppViewKey },
  { text: t('components.chatWelcome.proTip4'), view: 'blueprint' as AppViewKey },
  { text: t('components.chatWelcome.proTip5'), view: 'engine' as AppViewKey },
]);

function goToView(view: AppViewKey) {
  viewStore.setView(view);
}
</script>

<style scoped>
.chat-welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: clamp(20px, 5vh, 40px) clamp(16px, 5%, 28px) clamp(16px, 3vh, 28px);
  gap: clamp(10px, 1.8vh, 18px);
  min-height: 100%;
  overflow-y: auto;
  user-select: none;
  -webkit-user-select: none;
}

/* ===== 火花动画 ===== */
.welcome-spark-anim {
  width: clamp(110px, 18vh, 160px);
  height: clamp(110px, 18vh, 160px);
  flex-shrink: 0;
}

.welcome-spark-anim :deep(.spark-loader-stage) {
  width: 100%;
  height: 100%;
  margin-bottom: 0;
}

/* ===== 文字区域 ===== */
.welcome-title {
  font-size: var(--spark-fs-h2);
  font-weight: 800;
  color: var(--spark-text);
  margin: 0;
  text-align: center;
  letter-spacing: -0.3px;
}

.welcome-subtitle {
  font-size: var(--spark-fs-sm);
  color: var(--spark-primary);
  margin: 0;
  text-align: center;
  max-width: min(88%, 340px);
  line-height: 1.5;
}

/* ===== 提示区域 ===== */
.welcome-tips {
  display: flex;
  flex-direction: column;
  gap: clamp(8px, 1.2vh, 14px);
  width: 100%;
  max-width: min(100%, 560px);
  margin-top: 4px;
}

.tip-section {
  background: color-mix(in srgb, var(--spark-primary), transparent 92%);
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius-sm);
  padding: clamp(10px, 1.8vh, 16px) clamp(12px, 3%, 18px);
}

.tip-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.tip-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  color: var(--spark-primary);
}

.tip-section-title {
  font-size: var(--spark-fs-lg);
  font-weight: 700;
  color: var(--spark-text);
}

.tip-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tip-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: var(--spark-fs-sm);
  color: var(--spark-text-muted);
  line-height: 1.55;
}

.tip-section-hint {
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-muted);
  margin: 0 0 8px 0;
  line-height: 1.5;
  opacity: 0.85;
}

.tip-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--spark-primary-container);
  color: var(--spark-primary);
  font-size: var(--spark-fs-3xs);
  font-weight: 700;
  line-height: 1;
}

.tip-text {
  flex: 1;
}

.tip-goto {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  align-self: center;
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  padding: 0;
  border: none;
  background: color-mix(in srgb, var(--spark-primary), transparent 92%);
  color: var(--spark-primary);
  opacity: 0.55;
  cursor: pointer;
  transition: opacity 0.2s ease, transform 0.2s ease, background 0.2s ease;
  border-radius: 50%;
}

.tip-goto:hover {
  opacity: 1;
  transform: scale(1.12);
  background: color-mix(in srgb, var(--spark-primary), transparent 82%);
}

.tip-goto:active {
  transform: scale(0.92);
  opacity: 1;
}

.tip-goto-svg {
  width: 18px;
  height: 18px;
}

.tip-divider {
  width: 40px;
  height: 1px;
  background: var(--spark-border);
  align-self: center;
}

/* ===== 底部 ===== */
.welcome-footer {
  margin-top: 4px;
}

.footer-hint {
  font-size: var(--spark-fs-2xs);
  color: var(--spark-text-muted);
  opacity: 0.7;
}
</style>
