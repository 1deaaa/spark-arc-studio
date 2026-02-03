<template>
  <div class="view-container">
    <div class="mobile-header">
      <h3>设置</h3>
    </div>
    
    <div class="mobile-content">
        <div class="settings-column-mobile">
            <AIManager />
            <ModelUsageManager />
            <SystemNoticeBoard />
            <AppearanceSettings />
        </div>
    </div>
  </div>
</template>

<script setup>
import AIManager from '../../components/settings/AIManager.vue';
import ModelUsageManager from '../../components/settings/ModelUsageManager.vue';
import SystemNoticeBoard from '../../components/settings/SystemNoticeBoard.vue';
import AppearanceSettings from '../../components/settings/AppearanceSettings.vue';
import { useSettingsLogic } from '../../composables/useSettingsLogic';

const { aiStore } = useSettingsLogic();
</script>

<style scoped>
.view-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--spark-bg);
}

.mobile-header {
  padding: 16px;
  border-bottom: 1px solid var(--spark-border);
}

.mobile-header h3 {
  margin: 0;
  font-size: 18px;
}

.mobile-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.settings-column-mobile {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding-bottom: 80px;
}
</style>
