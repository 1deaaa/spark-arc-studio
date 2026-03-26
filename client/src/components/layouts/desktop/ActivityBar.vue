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

    <!-- 创作工具与系统功能的视觉分隔 -->
    <div class="activity-separator"></div>

    <div
      v-if="isAdmin"
      class="activity-item"
      :class="{ active: viewStore.currentView === 'admin' }"
      @click="viewStore.setView('admin')"
      title="管理中心"
    >
      <n-icon size="24">
        <SpeedometerOutline />
      </n-icon>
    </div>

    <div
      class="activity-item"
      :class="{ active: viewStore.currentView === 'settings' }"
      @click="viewStore.setView('settings')"
      title="设置"
    >
      <n-icon size="24">
        <CogOutline />
      </n-icon>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, markRaw } from 'vue';
import { NIcon } from 'naive-ui';
import {
  BulbOutline,          // 灵感 (替代 FlashOutline)
  PulseOutline,         // 梗概节奏 (替代 DocumentTextOutline)
  ListOutline,          // 大纲结构 (替代 GitNetworkOutline)
  CreateOutline,        // 剧本创作
  LibraryOutline,       // 风格管理 (替代 ColorPaletteOutline)
  MapOutline,           // 故事蓝图
  CodeSlashOutline,     // 引擎绑定
  ChatbubblesOutline,   // AI 沉浸聊天
  SpeedometerOutline,   // 管理中心
  CogOutline            // 设置 (替代 SettingsOutline)
} from '@vicons/ionicons5';
import { useViewStore, type AppViewKey } from '../../stores/viewStore';

type ActivityItem = {
  id: string;
  view: AppViewKey;
  title: string;
  icon: unknown;
};

defineProps({
  isAdmin: {
    type: Boolean,
    default: false,
  },
});

const viewStore = useViewStore();

defineEmits(['open-settings']);

// 统一图标配置 - 双端共用
const defaultItems: ActivityItem[] = [
  { id: 'world', view: 'world', title: '灵感与世界观', icon: markRaw(BulbOutline) },
  { id: 'synopsis', view: 'synopsis', title: '故事梗概 (Synopsis)', icon: markRaw(PulseOutline) },
  { id: 'structure', view: 'structure', title: '大纲与节奏 (总编剧)', icon: markRaw(ListOutline) },
  { id: 'production', view: 'production', title: '剧本创作 (执笔编剧)', icon: markRaw(CreateOutline) },
  { id: 'chat', view: 'chat', title: 'AI 沉浸工作台', icon: markRaw(ChatbubblesOutline) },
  { id: 'style', view: 'style', title: '风格管理 (Style)', icon: markRaw(LibraryOutline) },
  { id: 'blueprint', view: 'blueprint', title: '故事蓝图 (Blueprint)', icon: markRaw(MapOutline) },
  { id: 'engine', view: 'engine', title: '引擎绑定 (Engine)', icon: markRaw(CodeSlashOutline) }
];

const items = ref<ActivityItem[]>(loadInitialItems());
const draggingId = ref<string | null>(null);

function loadInitialItems(): ActivityItem[] {
  try {
    const savedOrder = localStorage.getItem('activityBarOrder');
    if (savedOrder) {
      const orderIds = JSON.parse(savedOrder) as string[];
      // Sort items based on saved order, append any new items at the end
      const ordered: ActivityItem[] = [];
      const remaining: ActivityItem[] = [...defaultItems];
      
      orderIds.forEach(id => {
        const idx = remaining.findIndex(item => item.id === id);
        if (idx !== -1) {
          ordered.push(remaining[idx]);
          remaining.splice(idx, 1);
        }
      });
      
      return [...ordered, ...remaining];
    }
  } catch (e: unknown) {
    console.error('Failed to load activity bar order', e);
  }
  return [...defaultItems];
}

const sortedItems = computed(() => items.value);

// Drag and Drop Logic
let lastSwapTime = 0;
let lastSwappedId: string | null = null;

function onDragStart(event: DragEvent, item: ActivityItem) {
  draggingId.value = item.id;
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move';
  }
}

function onDragEnter(targetItem: ActivityItem) {
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
  align-items: center;
  width: 100%;
}

.list-move {
  transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.5, 1);
}

.activity-item.dragging {
  opacity: 0.5;
  background: var(--n-color-hover);
}

.activity-separator {
  width: 32px;
  height: 1px;
  background: var(--spark-border);
  margin: 4px 0 12px;
  opacity: 0.6;
}
</style>
