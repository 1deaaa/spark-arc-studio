
<template>
  <div class="view-container">
        <div class="panel-header spark-desktop-header">
            <div class="spark-desktop-header__left">
                <h2 class="spark-desktop-title">设置</h2>
                <p class="spark-desktop-subtitle">模型、外观与平台配置</p>
            </div>
        </div>
    
    <div class="content-area">
        <div class="settings-columns">
            <div class="settings-col settings-col--left">
                <MyQuotaStatusCard />
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
                    </div>
                    <div class="right-half">
                        <AdminConfigPanel v-if="isAdmin" />
                    </div>
                </div>
            </div>
        </div>
    </div>
  </div>
</template>

<script setup>
import AppearanceSettings from '../../components/settings/AppearanceSettings.vue';
import AIManager from '../../components/settings/AIManager.vue';
import ModelUsageManager from '../../components/settings/ModelUsageManager.vue';
import MyQuotaStatusCard from '../../components/settings/MyQuotaStatusCard.vue';
import SystemNoticeBoard from '../../components/settings/SystemNoticeBoard.vue';
import AdminConfigPanel from '../../components/settings/AdminConfigPanel.vue';
import { useSettingsLogic } from '../../composables/useSettingsLogic';
import { ref, onMounted } from 'vue';
import { fetchWithAuth } from '../../services/api';

const { aiStore } = useSettingsLogic();
const isAdmin = ref(false);

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
    padding: 20px 20px 20px 8px;
}

.settings-columns {
    display: grid;
    grid-template-columns: minmax(220px, 1fr) minmax(300px, 2fr) minmax(300px, 2fr);
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

@media (max-width: 1200px) {
    .settings-columns {
        grid-template-columns: 1fr;
    }

    .right-split {
        grid-template-columns: 1fr;
    }
}


</style>
