
<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header">
      <h2>Settings / 设置</h2>
    </div>
    
    <div class="content-area">
        <div class="settings-container">
            <div class="settings-column">
                <AppearanceSettings />
                <AIManager />
            </div>

            <div class="settings-column">
                <ModelUsageManager />
            </div>

            <div class="settings-column">
                <SystemNoticeBoard />
            </div>
        </div>
    </div>
  </div>
</template>

<script setup>
import AppearanceSettings from '../../components/settings/AppearanceSettings.vue';
import AIManager from '../../components/settings/AIManager.vue';
import ModelUsageManager from '../../components/settings/ModelUsageManager.vue';
import SystemNoticeBoard from '../../components/settings/SystemNoticeBoard.vue';
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

.panel-header {
  height: 50px;
  border-bottom: 1px solid var(--spark-border);
  display: flex;
  align-items: center;
  padding: 0 20px;
  background-color: var(--spark-panel-bg);
}

.panel-header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--spark-text);
  user-select: none;
}

.content-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.settings-container {
    display: grid;
    grid-template-columns: 1fr 0.6fr 1fr;
    gap: 24px;
    max-width: 100%;
    margin: 0 auto;
}

@media (max-width: 1600px) {
    .settings-container {
        grid-template-columns: repeat(2, 1fr);
    }
}

@media (max-width: 1100px) {
    .settings-container {
        grid-template-columns: 1fr;
    }
}

.spark-anim-fade {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
