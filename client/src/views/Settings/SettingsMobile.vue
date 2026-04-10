<template>
  <div class="view-container">
    <div class="mobile-content">
        <div class="settings-column-mobile">
            <AIManager />
            <ModelUsageManager />
            <SystemNoticeBoard />
            <AppearanceSettings />
            <LanguageSettings />
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

const { aiStore } = useSettingsLogic();
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
    gap: 16px;
    padding-bottom: 80px;
}
</style>
