<template>
  <div class="view-container">
    <div class="mobile-content">
        <div class="settings-column-mobile">
            <AIManager />
            <ModelUsageManager />
            <SystemNoticeBoard />
            <AppearanceSettings />
            <LanguageSettings />
            <div class="onboarding-replay-section">
                <button class="onboarding-replay-btn" @click="replayOnboarding">
                    {{ t('onboarding.common.restartGuide') }}
                </button>
            </div>
        </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import AIManager from '../../components/settings/AIManager.vue';
import ModelUsageManager from '../../components/settings/ModelUsageManager.vue';
import SystemNoticeBoard from '../../components/settings/SystemNoticeBoard.vue';
import AppearanceSettings from '../../components/settings/AppearanceSettings.vue';
import LanguageSettings from '../../components/settings/LanguageSettings.vue';
import { useSettingsLogic } from '../../composables/useSettingsLogic';
import { useI18n } from 'vue-i18n';
import { useOnboarding } from '../../onboarding';
import { useMobile } from '../../composables/useMobile';

const { aiStore } = useSettingsLogic();
const { t } = useI18n();
const { resetAll, trigger } = useOnboarding();
const { isMobile } = useMobile();

function replayOnboarding() {
    resetAll();
    trigger(isMobile.value ? 'mobile-workspace' : 'desktop-workspace');
}
</script>

<style scoped>
.view-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: transparent; 
}

.mobile-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0;
}

.settings-column-mobile {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding-bottom: 80px;
}

.onboarding-replay-section {
    margin-top: 8px;
}

.onboarding-replay-btn {
    width: 100%;
    padding: 10px 16px;
    border: 1px solid var(--spark-border, rgba(255, 255, 255, 0.12));
    border-radius: 8px;
    background: transparent;
    color: var(--spark-text, #ccc);
    font-size: var(--spark-fs-sm);
    cursor: pointer;
    transition: all 0.2s ease;
}

.onboarding-replay-btn:hover {
    color: var(--spark-primary, #ffaa40);
    border-color: var(--spark-primary, #ffaa40);
}

.onboarding-replay-btn:focus-visible {
    outline: 2px solid var(--spark-primary, #ffaa40);
    outline-offset: 2px;
    background: var(--spark-primary, #ffaa40);
    color: var(--spark-bg, #1a1a1a);
    border-color: var(--spark-primary, #ffaa40);
}
</style>
