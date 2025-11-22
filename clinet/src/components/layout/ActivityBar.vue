<template>
  <div class="activity-bar">
    <div 
      class="activity-item" 
      :class="{ active: viewStore.currentView === 'muse' }"
      @click="viewStore.setView('muse')"
      title="灵感 (Muse)"
    >
      <n-icon size="24">
        <FlashOutline />
      </n-icon>
    </div>

    <div 
      class="activity-item" 
      :class="{ active: viewStore.currentView === 'world' }"
      @click="viewStore.setView('world')"
      title="世界观 (Genesis)"
    >
      <n-icon size="24">
        <PlanetOutline />
      </n-icon>
    </div>

    <div 
      class="activity-item" 
      :class="{ active: viewStore.currentView === 'structure' }"
      @click="viewStore.setView('structure')"
      title="大纲与节奏 (Showrunner)"
    >
      <n-icon size="24">
        <GitNetworkOutline />
      </n-icon>
    </div>

    <div 
      class="activity-item" 
      :class="{ active: viewStore.currentView === 'production' }"
      @click="viewStore.setView('production')"
      title="剧本创作 (Production)"
    >
      <n-icon size="24">
        <CreateOutline />
      </n-icon>
    </div>

    <div 
      class="activity-item" 
      :class="{ active: viewStore.currentView === 'style' }"
      @click="viewStore.setView('style')"
      title="风格管理 (Style)"
    >
      <n-icon size="24">
        <ColorPaletteOutline />
      </n-icon>
    </div>

    <div 
      class="activity-item" 
      :class="{ active: viewStore.currentView === 'bridge' }"
      @click="viewStore.setView('bridge')"
      title="场景衔接 (Bridge)"
    >
      <n-icon size="24">
        <LinkOutline />
      </n-icon>
    </div>

    <div style="flex: 1"></div>

    <div 
      class="activity-item" 
      @click="$emit('open-settings')"
      title="设置"
    >
      <n-icon size="24">
        <SettingsOutline />
      </n-icon>
    </div>
  </div>
</template>

<script setup>
import { NIcon } from 'naive-ui';
import { 
  FlashOutline, 
  PlanetOutline, 
  GitNetworkOutline, 
  CreateOutline, 
  ColorPaletteOutline,
  SettingsOutline,
  LinkOutline
} from '@vicons/ionicons5';
import { useViewStore } from '../stores/viewStore';

const viewStore = useViewStore();

defineEmits(['open-settings']);
</script>

<style scoped>
/* Styles are handled globally in studio.css for .activity-bar and .activity-item */
</style>
