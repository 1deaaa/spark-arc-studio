<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header">
      <h2>Settings / 设置</h2>
      <div class="header-actions">
      </div>
    </div>
    
    <div class="content-area">
        <div class="settings-container">
            <!-- Column 1: Appearance & Platforms & Models -->
            <div class="settings-column">
                <AppearanceSettings />
                <PlatformManager />
                <ModelManager />
            </div>

            <!-- Column 2: Model Usage -->
            <div class="settings-column">
                <ModelUsageManager />
            </div>

            <!-- Column 3: Notice Board -->
            <div class="settings-column">
                <SystemNoticeBoard />
            </div>
        </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue';
import AppearanceSettings from '../components/settings/AppearanceSettings.vue';
import PlatformManager from '../components/settings/PlatformManager.vue';
import ModelManager from '../components/settings/ModelManager.vue';
import ModelUsageManager from '../components/settings/ModelUsageManager.vue';
import SystemNoticeBoard from '../components/settings/SystemNoticeBoard.vue';
import { useAiStore } from '../components/stores/aiStore';

const aiStore = useAiStore();

onMounted(async () => {
    // Initial data load for the entire settings view
    // Equivalent to original loadData() which was aiStore.loadData(true, false)
    await aiStore.loadData(true);
});
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
  -webkit-user-select: none;
  user-select: none;
  cursor: default;
}

.content-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.settings-container {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
