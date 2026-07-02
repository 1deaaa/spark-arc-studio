<template>
  <div class="view-container">
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

    <div class="engine-main">
      <AgentFlowBlueprint />
    </div>

    <n-modal
      v-model:show="skillsModalVisible"
      preset="card"
      :title="t('components.agentSkillManager.title')"
      style="width: 680px; max-width: calc(100vw - 48px);"
    >
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
  position: relative;
  height: 100%;
  width: 100%;
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  background-color: var(--spark-bg);
  overflow: hidden;
}

.skills-trigger-btn {
  position: absolute;
  top: 16px;
  left: 16px;
  z-index: 40;
}

.engine-main {
  flex: 1 1 auto;
  width: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

@media (max-width: 900px) {
  .skills-trigger-btn {
    top: 12px;
    left: 12px;
  }
}
</style>
