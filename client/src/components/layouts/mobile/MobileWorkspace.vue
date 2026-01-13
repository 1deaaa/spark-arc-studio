
<template>
  <MobileShell @open-settings="openSettings">
    <div class="workspace-area mobile-workspace">
        <keep-alive>
          <component :is="activeComponent" :projectId="projectStore.currentProject" />
        </keep-alive>

        <div v-show="viewStore.currentView === 'production'" class="production-layout-mobile">
             <n-empty description="剧本创作模式暂未完全适配移动端" style="padding-top: 50px; margin: 0 auto;">
               <template #extra>
                 <n-button size="small" @click="viewStore.setView('world')">去灵感工坊</n-button>
               </template>
             </n-empty>
        </div>
    </div>
    
    <GlobalChatFloat />
    
    <transition name="save-hint">
        <div v-show="saveHintVisible" class="save-hint">已自动保存</div>
    </transition>
  </MobileShell>
</template>

<script setup>
import { computed } from 'vue';
import { NButton, NEmpty } from 'naive-ui';
import MobileShell from './MobileShell.vue';
import GlobalChatFloat from '../../share/GlobalChatFloat.vue';
import StoryBlueprint from '../../dlg-editor/StoryBlueprint.vue';

// 这里的 View 引用改为新的分发器路径
import WorldView from '../../../views/World/WorldView.vue';
import SynopsisView from '../../../views/Synopsis/SynopsisView.vue';
import StructureView from '../../../views/Structure/StructureView.vue';
import StyleView from '../../../views/Style/StyleView.vue';
import EngineView from '../../../views/Engine/EngineView.vue'; 
import SettingsView from '../../../views/Settings/SettingsView.vue';
import AdminView from '../../../views/Admin/AdminView.vue';

import { useScriptWriterLogic } from '../../../composables/useScriptWriterLogic';

const {
  viewStore,
  projectStore,
  saveHintVisible,
  openSettings
} = useScriptWriterLogic();

const activeComponent = computed(() => {
  switch (viewStore.currentView) {
    case 'world': return WorldView;
    case 'synopsis': return SynopsisView;
    case 'structure': return StructureView;
    case 'style': return StyleView;
    case 'engine': return EngineView;
    case 'blueprint': return StoryBlueprint;
    case 'settings': return SettingsView;
    case 'admin': return AdminView;
    default: return null;
  }
});
</script>

<style scoped>
.workspace-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.production-layout-mobile {
  padding: 20px;
  text-align: center;
}

.save-hint {
  position: fixed;
  right: 16px;
  bottom: 80px; /* 留出底部导航空间 */
  background: var(--spark-success);
  color: var(--spark-text-inverse);
  padding: 8px 12px;
  border-radius: var(--spark-radius-sm);
  box-shadow: var(--spark-shadow-sm);
  z-index: 9999;
}

.save-hint-enter-from,
.save-hint-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.98);
}
.save-hint-enter-active,
.save-hint-leave-active {
  transition: opacity .18s ease, transform .18s ease;
}
</style>
