<template>
  <div class="view-container">
    <div class="mobile-content">
        <div class="settings-column-mobile">
            <AIManager />
            <AdminConfigPanel v-if="isAdmin" policy-only />
            <ModelUsageManager />
            <SemanticSearchCard />
            <SystemNoticeBoard />
            <AppearanceSettings />
            <LanguageSettings />
            <div class="onboarding-replay-section">
                <button class="onboarding-replay-btn" @click="replayOnboarding">
                    {{ t('onboarding.common.restartGuide') }}
                </button>
            </div>
            <div class="logout-section">
                <button class="logout-btn" @click="handleLogout">
                    {{ t('components.headerToolbar.logout') }}
                </button>
            </div>
        </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import AIManager from '../../components/settings/AIManager.vue';
import AdminConfigPanel from '../../components/settings/AdminConfigPanel.vue';
import ModelUsageManager from '../../components/settings/ModelUsageManager.vue';
import SemanticSearchCard from '../../components/settings/SemanticSearchCard.vue';
import SystemNoticeBoard from '../../components/settings/SystemNoticeBoard.vue';
import AppearanceSettings from '../../components/settings/AppearanceSettings.vue';
import LanguageSettings from '../../components/settings/LanguageSettings.vue';
import { useSettingsLogic } from '../../composables/useSettingsLogic';
import { useI18n } from 'vue-i18n';
import { useOnboarding } from '../../onboarding';
import { useMobile } from '../../composables/useMobile';
import { useRouter } from 'vue-router';
import { useProjectStore } from '../../components/stores/projectStore';
import { fetchWithAuth, logout as apiLogout } from '../../services/api';
import { onMounted, ref } from 'vue';

const { aiStore } = useSettingsLogic();
const { t } = useI18n();
const { resetAll, trigger } = useOnboarding();
const { isMobile } = useMobile();
const router = useRouter();
const projectStore = useProjectStore();
const isAdmin = ref(false);

async function checkAdmin() {
    try {
        const response = await fetchWithAuth('/api/user/info');
        if (!response.ok) return;
        const data = await response.json();
        isAdmin.value = Boolean(data?.success && data?.user?.is_admin);
    } catch {
        isAdmin.value = false;
    }
}

onMounted(checkAdmin);

function replayOnboarding() {
    resetAll();
    trigger(isMobile.value ? 'mobile-workspace' : 'desktop-workspace');
}

async function handleLogout() {
    projectStore.resetForLogout();
    try { await apiLogout(); } catch {}
    router.push('/login');
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
    padding-bottom: calc(var(--mobile-bottom-nav-height, 60px) + var(--sab, 0px));
}

.onboarding-replay-section {
    margin-top: 8px;
}

button.onboarding-replay-btn {
    width: 100%;
    padding: 10px 16px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    font-weight: 600;
    letter-spacing: 0.3px;
    text-decoration: none;
    border: 1px solid var(--spark-border, rgba(255, 255, 255, 0.12)) !important;
    border-radius: 8px;
    background: var(--spark-panel-bg, rgba(255, 255, 255, 0.04)) !important;
    color: var(--spark-text, #e6e6e6) !important;
    font-size: var(--spark-fs-sm);
    cursor: pointer;
    transform: none !important;
    box-shadow: none !important;
    transition: color 0.2s ease, border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
}

button.onboarding-replay-btn:hover {
    background: color-mix(in srgb, var(--spark-panel-bg, #1f1f1f), white 4%) !important;
    color: var(--spark-text, #f2f2f2) !important;
    border-color: color-mix(in srgb, var(--spark-primary, #ffaa40), white 12%) !important;
    transform: none !important;
    box-shadow: none !important;
}

button.onboarding-replay-btn:active {
    transform: none !important;
    background: color-mix(in srgb, var(--spark-panel-bg, #1f1f1f), white 6%) !important;
    box-shadow: none !important;
}

button.onboarding-replay-btn:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--spark-primary, #ffaa40), white 20%) !important;
    outline-offset: 2px;
    background: color-mix(in srgb, var(--spark-panel-bg, #1f1f1f), white 8%) !important;
    color: #ffffff !important;
    border-color: color-mix(in srgb, var(--spark-primary, #ffaa40), white 20%) !important;
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--spark-primary, #ffaa40), transparent 72%) !important;
}

.logout-section {
    margin-top: 4px;
}

button.logout-btn {
    width: 100%;
    padding: 10px 16px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    font-weight: 600;
    letter-spacing: 0.3px;
    text-decoration: none;
    border: 1px solid var(--spark-border, rgba(255, 255, 255, 0.12)) !important;
    border-radius: 8px;
    background: var(--spark-panel-bg, rgba(255, 255, 255, 0.04)) !important;
    color: var(--spark-danger, #f56c6c) !important;
    font-size: var(--spark-fs-sm);
    cursor: pointer;
    transform: none !important;
    box-shadow: none !important;
    transition: color 0.2s ease, border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
}

button.logout-btn:hover {
    background: color-mix(in srgb, var(--spark-panel-bg, #1f1f1f), white 4%) !important;
    color: var(--spark-danger, #f89898) !important;
    border-color: color-mix(in srgb, var(--spark-danger, #f56c6c), white 12%) !important;
    transform: none !important;
    box-shadow: none !important;
}

button.logout-btn:active {
    transform: none !important;
    background: color-mix(in srgb, var(--spark-panel-bg, #1f1f1f), white 6%) !important;
    box-shadow: none !important;
}

button.logout-btn:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--spark-danger, #f56c6c), white 20%) !important;
    outline-offset: 2px;
    background: color-mix(in srgb, var(--spark-panel-bg, #1f1f1f), white 8%) !important;
    color: #ffffff !important;
    border-color: color-mix(in srgb, var(--spark-danger, #f56c6c), white 20%) !important;
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--spark-danger, #f56c6c), transparent 72%) !important;
}
</style>
