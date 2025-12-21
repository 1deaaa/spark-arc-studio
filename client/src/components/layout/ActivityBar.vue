<template>
  <div class="activity-bar">
    <transition-group name="list" tag="div" class="activity-list">
      <div 
        v-for="item in sortedItems"
        :key="item.id"
        class="activity-item" 
        :class="{ 
          active: viewStore.currentView === item.view,
          dragging: draggingId === item.id
        }"
        @click="viewStore.setView(item.view)"
        :title="item.title"
        draggable="true"
        @dragstart="onDragStart($event, item)"
        @dragenter.prevent="onDragEnter(item)"
        @dragover.prevent
        @dragend="onDragEnd"
      >
        <n-icon size="24">
          <component :is="item.icon" />
        </n-icon>
      </div>
    </transition-group>

    <div style="flex: 1"></div>

    <div 
      class="activity-item" 
      :class="{ active: viewStore.currentView === 'settings' }"
      @click="viewStore.setView('settings')"
      title="设置"
    >
      <n-icon size="24">
        <SettingsOutline />
      </n-icon>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, markRaw } from 'vue';
import { NIcon } from 'naive-ui';
import { 
  FlashOutline, 
  PlanetOutline, 
  GitNetworkOutline, 
  CreateOutline, 
  ColorPaletteOutline,
  SettingsOutline,
  MapOutline,
  CodeSlashOutline,
  DocumentTextOutline,
  PulseOutline
} from '@vicons/ionicons5';
import { useViewStore } from '../stores/viewStore';

const viewStore = useViewStore();

defineEmits(['open-settings']);

// Default items configuration
const defaultItems = [
  { id: 'world', view: 'world', title: '世界观 (设定专家)', icon: markRaw(PlanetOutline) },
  { id: 'synopsis', view: 'synopsis', title: '故事梗概 (Synopsis)', icon: markRaw(DocumentTextOutline) },
  { id: 'structure', view: 'structure', title: '大纲与节奏 (总编剧)', icon: markRaw(GitNetworkOutline) },
  { id: 'production', view: 'production', title: '剧本创作 (执笔编剧)', icon: markRaw(CreateOutline) },
  { id: 'style', view: 'style', title: '风格管理 (Style)', icon: markRaw(ColorPaletteOutline) },
  { id: 'blueprint', view: 'blueprint', title: '故事蓝图 (Blueprint)', icon: markRaw(MapOutline) },
  { id: 'engine', view: 'engine', title: '引擎绑定 (Engine)', icon: markRaw(CodeSlashOutline) }
];

const items = ref(loadInitialItems());
const draggingId = ref(null);

function loadInitialItems() {
  try {
    const savedOrder = localStorage.getItem('activityBarOrder');
    if (savedOrder) {
      const orderIds = JSON.parse(savedOrder);
      // Sort items based on saved order, append any new items at the end
      const ordered = [];
      const remaining = [...defaultItems];
      
      orderIds.forEach(id => {
        const idx = remaining.findIndex(item => item.id === id);
        if (idx !== -1) {
          ordered.push(remaining[idx]);
          remaining.splice(idx, 1);
        }
      });
      
      return [...ordered, ...remaining];
    }
  } catch (e) {
    console.error('Failed to load activity bar order', e);
  }
  return [...defaultItems];
}

const sortedItems = computed(() => items.value);

// Drag and Drop Logic
let lastSwapTime = 0;
let lastSwappedId = null;

function onDragStart(event, item) {
  draggingId.value = item.id;
  event.dataTransfer.effectAllowed = 'move';
}

function onDragEnter(targetItem) {
  if (!draggingId.value || draggingId.value === targetItem.id) return;

  // Prevent flickering: Don't swap with the same item we just swapped with immediately
  // This prevents the item animating under the cursor from triggering a reverse swap
  if (targetItem.id === lastSwappedId && Date.now() - lastSwapTime < 300) {
    return;
  }

  const sourceIndex = items.value.findIndex(i => i.id === draggingId.value);
  const targetIndex = items.value.findIndex(i => i.id === targetItem.id);

  if (sourceIndex !== -1 && targetIndex !== -1) {
    const newItems = [...items.value];
    const [movedItem] = newItems.splice(sourceIndex, 1);
    newItems.splice(targetIndex, 0, movedItem);
    items.value = newItems;
    
    lastSwapTime = Date.now();
    lastSwappedId = targetItem.id;
  }
}

function onDragEnd() {
  draggingId.value = null;
  localStorage.setItem('activityBarOrder', JSON.stringify(items.value.map(i => i.id)));
}
</script>

<style scoped>
/* Styles are handled globally in studio.css for .activity-bar and .activity-item */

.activity-list {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.list-move {
  transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.5, 1);
}

.activity-item.dragging {
  opacity: 0.5;
  background: var(--n-color-hover);
}
</style>
