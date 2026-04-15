
<template>
  <div class="view-container">
        <div class="panel-header spark-desktop-header">
            <div class="spark-desktop-header__left">
                <h2 class="spark-desktop-title">{{ t('settings.title') }}</h2>
                <p class="spark-desktop-subtitle">{{ t('settings.subtitle') }}</p>
            </div>
        </div>
    
    <div class="content-area">
        <div class="settings-columns">
            <div class="settings-col settings-col--left">
                <ModelUsageManager />
            </div>
            <div class="settings-col settings-col--middle">
                <AIManager />
            </div>
            <div class="settings-col settings-col--right">
                <SystemNoticeBoard />
                <div class="right-split">
                    <div class="right-half">
                        <AppearanceSettings />
                        <LanguageSettings />
                    </div>
                    <div class="right-half">
                        <AdminConfigPanel v-if="isAdmin" />
                        <div class="onboarding-replay-section">
                            <button class="onboarding-replay-btn" @click="replayOnboarding">
                                {{ t('onboarding.common.restartGuide') }}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import AppearanceSettings from '../../components/settings/AppearanceSettings.vue';
import AIManager from '../../components/settings/AIManager.vue';
import ModelUsageManager from '../../components/settings/ModelUsageManager.vue';
import SystemNoticeBoard from '../../components/settings/SystemNoticeBoard.vue';
import AdminConfigPanel from '../../components/settings/AdminConfigPanel.vue';
import LanguageSettings from '../../components/settings/LanguageSettings.vue';
import { useSettingsLogic } from '../../composables/useSettingsLogic';
import { ref, onMounted } from 'vue';
import { fetchWithAuth } from '../../services/api';
import { useI18n } from 'vue-i18n';
import { useOnboarding } from '../../onboarding';

const { aiStore } = useSettingsLogic();
const isAdmin = ref(false);
const { t } = useI18n();
const { resetAll, trigger } = useOnboarding();

function replayOnboarding() {
    resetAll();
    trigger('desktop-workspace');
}

async function checkAdmin() {
    try {
        const res = await fetchWithAuth('/api/user/info');
        if (res.ok) {
            const data = await res.json();
            if (data.success && data.user && data.user.is_admin) {
                isAdmin.value = true;
            }
        }
    } catch (e) {
        console.error(e);
    }
}

onMounted(() => {
    checkAdmin();
});
</script>

<style scoped>
.view-container {
  height: 100%;
    width: 100%;
    min-width: 0;
  display: flex;
  flex-direction: column;
  background-color: var(--spark-bg);
}

.content-area {
  flex: 1;
    /* 布局修复：防止无内容时宽度坍缩 */
    width: 100%;
    min-width: 0;
  overflow-y: auto;
    padding: var(--spark-panel-padding);
}

.settings-columns {
    display: grid;
    grid-template-columns: minmax(220px, 1fr) minmax(300px, 2.1fr) minmax(300px, 1.9fr);
    gap: 20px;
    align-items: start;
    max-width: 99%;
    margin: 0;
}

.settings-col {
    display: flex;
    flex-direction: column;
    gap: 20px;
    min-width: 0;
}

.right-split {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    align-items: start;
}

.right-half {
    min-width: 0;
}

.onboarding-replay-section {
    margin-top: 16px;
}

.onboarding-replay-btn {
    width: 100%;
    padding: 10px 16px;
    border: 1px solid var(--spark-border, rgba(255, 255, 255, 0.12));
    border-radius: 8px;
    background: transparent;
    color: var(--spark-text-muted, #999);
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
    color: var(--spark-primary, #ffaa40);
    border-color: var(--spark-primary, #ffaa40);
    background: var(--spark-bg, #1a1a1a);
}

@media (max-width: 1200px) {
    .settings-columns {
        grid-template-columns: 1fr;
    }

    .right-split {
        grid-template-columns: 1fr;
    }
}


</style>
