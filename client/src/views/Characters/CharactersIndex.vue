<template>
  <div class="characters-view">
    <GlobalLoading scope="world" target="characters" />

    <header class="characters-header spark-desktop-header">
      <div class="spark-desktop-header__left">
        <div class="spark-desktop-header__title-row">
          <h2 class="spark-desktop-title">{{ t('views.characters.title') }}</h2>
          <span class="spark-desktop-subtitle">{{ t('views.characters.subtitle') }}</span>
        </div>
      </div>
      <div class="spark-desktop-header__right">
        <n-button size="small" secondary @click="toolboxOpen = !toolboxOpen">
          <template #icon><n-icon :component="toolboxOpen ? PanelRightClose : WandSparkles" /></template>
          {{ toolboxOpen ? t('views.characters.hideAiTools') : t('views.characters.showAiTools') }}
        </n-button>
      </div>
    </header>

    <main class="characters-body" :class="{ 'toolbox-open': toolboxOpen }">
      <section class="characters-canvas">
        <LorebookEditor :visible="true" :embedded="true" mode="characters" />
      </section>

      <Transition name="toolbox-slide">
        <aside v-show="toolboxOpen" class="characters-toolbox">
          <div class="toolbox-heading">
            <div>
              <strong>{{ t('views.characters.aiTools') }}</strong>
              <span>{{ t('views.characters.aiToolsDescription') }}</span>
            </div>
            <AiSettingsPanel :visible="true" :compact="true" agent-name="agent_lorebook" />
          </div>
          <CharacterGeneratorPanel :visible="true" :embedded="true" />
        </aside>
      </Transition>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NIcon } from 'naive-ui';
import { PanelRightClose, WandSparkles } from '@lucide/vue';
import LorebookEditor from '../../components/lorebook/LorebookEditor.vue';
import CharacterGeneratorPanel from '../../components/lorebook/CharacterGeneratorPanel.vue';
import AiSettingsPanel from '../../components/lorebook/AiSettingsPanel.vue';
import GlobalLoading from '../../components/share/GlobalLoading.vue';

const { t } = useI18n();
const toolboxOpen = ref(false);
</script>

<style scoped>
.characters-view { width: 100%; height: 100%; min-height: 0; display: flex; flex-direction: column; overflow: hidden; background: var(--spark-bg); }
.characters-header { padding: 0 20px; }
.characters-body { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 1fr) 0; overflow: hidden; transition: grid-template-columns 220ms cubic-bezier(.4, 0, .2, 1); }
.characters-body.toolbox-open { grid-template-columns: minmax(0, 1fr) minmax(270px, 320px); }
.characters-canvas { min-width: 0; min-height: 0; overflow: hidden; }
.characters-toolbox { min-width: 0; overflow: auto; padding: 12px; border-left: 1px solid var(--spark-border); background: var(--spark-panel-bg); }
.toolbox-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--spark-border); }
.toolbox-heading > div:first-child { min-width: 0; display: grid; gap: 3px; }
.toolbox-heading strong { color: var(--spark-text); }
.toolbox-heading span { color: var(--spark-text-muted); font-size: var(--spark-fs-xs); line-height: 1.45; }
.toolbox-slide-enter-active, .toolbox-slide-leave-active { transition: opacity 180ms ease, transform 220ms ease; }
.toolbox-slide-enter-from, .toolbox-slide-leave-to { opacity: 0; transform: translateX(18px); }
@media (max-width: 760px) {
  .characters-header { padding: 0 10px; }
  .spark-desktop-subtitle { display: none; }
  .characters-body, .characters-body.toolbox-open { position: relative; display: block; }
  .characters-canvas { height: 100%; }
  .characters-toolbox { position: absolute; z-index: 5; inset: 0 0 0 auto; width: min(88vw, 320px); box-shadow: var(--spark-shadow-lg); }
}
</style>
