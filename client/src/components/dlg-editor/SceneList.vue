<template>
  <div class="scene-list-wrapper">
    <div class="scene-actions">
      <n-button block dashed size="small" @click="createNewScene" class="add-scene-btn">
        <template #icon>
          <n-icon :component="AddOutline" />
        </template>
        新建场景
      </n-button>
    </div>
    <div id="scene-list" class="scene-list">
      <Draggable
      v-model="sceneListModel"
      item-key="__sid"
      :animation="150"
      handle=".drag-handle"
      @end="onDragEnd"
    >
      <template #item="{ element: scene }">
        <div
          class="scene-item"
          :class="{ selected: scene === sceneStore.currentScene }"
          @click="onSelectScene(scene)"
        >
          <span class="drag-handle" title="拖动排序">≡</span>
          <span class="scene-title">{{ scene.scene }}</span>
        </div>
      </template>
      </Draggable>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { NButton, NIcon } from 'naive-ui';
import { AddOutline } from '@vicons/ionicons5';
import bus from '@/eventBus';
import { useSceneStore, type SceneWithClientId } from '@/components/stores/sceneStore';
import Draggable from 'vuedraggable';

const sceneStore = useSceneStore();

const sceneListModel = computed<SceneWithClientId[]>({
  get: () => Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : [],
  set: (value) => {
    sceneStore.scriptData = value;
  }
});

function createNewScene() {
  sceneStore.createNewScene();
}

function onSelectScene(scene: SceneWithClientId) {
  if (typeof sceneStore.selectScene === 'function') {
    sceneStore.selectScene(scene);
  } else {
    // 回退：直接写入状态，避免热更异常
    sceneStore.currentScene = scene;
    sceneStore.currentNode = null;
    sceneStore.nodeParent = null;
    sceneStore.selectionType = 'scene';
  }
  // 通知应用关闭设定面板，恢复对话树
  bus.emit('scene-selected');
}

function onDragEnd(evt) {
  try {
    if (evt && evt.oldIndex === evt.newIndex) return;
    // 仅在顺序改变时保存到文件
    sceneStore._saveStory?.();
  } catch {}
}
</script>

<style scoped>
.scene-list-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.scene-actions {
  padding: 8px;
  border-bottom: 1px solid var(--n-border-color);
}
.add-scene-btn {
  margin-bottom: 4px;
}
.drag-handle {
  cursor: grab;
  margin-right: 8px;
  user-select: none;
  color: #888;
}
.drag-handle:active { cursor: grabbing; }
.scene-item { display: flex; align-items: center; gap: 6px; }
.scene-title { flex: 1; }
/* 禁用文字选中，避免拖拽/点击误选 */
.scene-list, .scene-item, .scene-title {
  -webkit-user-select: none;
  -ms-user-select: none;
  user-select: none;
}
</style>
