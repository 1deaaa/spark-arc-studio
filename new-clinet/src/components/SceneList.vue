<template>
  <div id="scene-list" class="scene-list">
    <div 
      v-for="scene in scenes" 
      :key="scene.scene" 
  class="scene-item"
  :class="{ selected: scene === sceneStore.currentScene }"
  @click="onSelectScene(scene)"
    >
      {{ scene.scene }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useSceneStore } from '@/stores/sceneStore';

const sceneStore = useSceneStore();

const scenes = computed(() => sceneStore.scriptData);

function onSelectScene(scene) {
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
  window.dispatchEvent(new CustomEvent('scene-selected'));
}
</script>