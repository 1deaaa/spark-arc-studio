<template>
  <div class="view-container">
    <div class="panel-header spark-desktop-header">
      <div class="spark-desktop-header__left">
        <h2 class="spark-desktop-title">{{ t('views.engine.desktop.title') }}</h2>
        <p class="spark-desktop-subtitle">{{ t('views.engine.desktop.subtitle') }}</p>
      </div>
    </div>
    <div class="content-area">
      <div class="engine-top-bar">
        <div class="engine-guide">{{ t('views.engine.desktop.promptGuide') }}</div>
        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button
              class="skills-trigger-btn"
              type="primary"
              secondary
              circle
              size="large"
              @click="skillsModalVisible = true"
            >
              <template #icon>
                <n-icon :component="BrainCircuit" size="20" />
              </template>
            </n-button>
          </template>
          {{ t('components.agentSkillManager.title') }}
        </n-tooltip>
      </div>

      <div class="engine-main">
        <AgentFlowBlueprint />
      </div>
    </div>

    <n-modal v-model:show="skillsModalVisible" preset="card" :title="t('components.agentSkillManager.title')" style="width: 560px; max-width: calc(100vw - 48px);">
      <AgentSkillManager />
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NIcon, NModal, NTooltip } from 'naive-ui';
import { BrainCircuit } from '@lucide/vue';
import AgentFlowBlueprint from '../../components/lorebook/AgentFlowBlueprint.vue';
import AgentSkillManager from '../../components/settings/AgentSkillManager.vue';

const { t } = useI18n();
const skillsModalVisible = ref(false);
</script>

<style scoped>
.view-container {
  height: 100%;
  width: 100%;
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background-color: var(--spark-bg);
}

.content-area {
  flex: 1;
  width: 100%;
  min-width: 0;
  padding: var(--spark-panel-padding);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.engine-top-bar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}

.engine-guide {
  padding: 10px 12px;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-sm);
  background: color-mix(in srgb, var(--spark-primary-container), transparent 35%);
  border: 1px solid color-mix(in srgb, var(--spark-primary), transparent 72%);
  border-radius: 8px;
  max-width: 720px;
}

.skills-trigger-btn {
  flex: 0 0 auto;
}

.engine-main {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  border-radius: var(--spark-radius);
  border: 1px solid var(--spark-border);
}

@media (max-width: 900px) {
  .engine-top-bar {
    flex-wrap: wrap;
  }

  .engine-guide {
    max-width: none;
    flex: 1 1 auto;
    order: 2;
  }

  .skills-trigger-btn {
    order: 1;
  }
}
</style>
