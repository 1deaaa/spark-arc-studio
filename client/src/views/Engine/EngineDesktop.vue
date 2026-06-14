<template>
  <div class="view-container">
    <div class="panel-header spark-desktop-header">
      <div class="spark-desktop-header__left">
        <h2 class="spark-desktop-title">{{ t('views.engine.desktop.title') }}</h2>
        <p class="spark-desktop-subtitle">{{ t('views.engine.desktop.subtitle') }}</p>
      </div>
    </div>
    <div class="content-area">
      <div class="engine-guide">{{ t('views.engine.desktop.promptGuide') }}</div>
      <div class="engine-workspace">
        <div class="engine-main">
          <AgentFlowBlueprint />
        </div>
        <aside class="engine-side">
          <AgentSkillManager />
        </aside>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import AgentFlowBlueprint from '../../components/lorebook/AgentFlowBlueprint.vue';
import AgentSkillManager from '../../components/settings/AgentSkillManager.vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
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

.engine-guide {
  flex: 0 0 auto;
  padding: 10px 12px;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-sm);
  background: color-mix(in srgb, var(--spark-primary-container), transparent 35%);
  border: 1px solid color-mix(in srgb, var(--spark-primary), transparent 72%);
  border-radius: 8px;
}

.engine-workspace {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 16px;
}

.engine-main {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.engine-side {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

@media (max-width: 1100px) {
  .engine-workspace {
    grid-template-columns: 1fr;
    overflow: auto;
  }

  .engine-main {
    min-height: 680px;
  }
}
</style>
