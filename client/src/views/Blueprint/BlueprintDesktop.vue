<template>
  <div class="blueprint-desktop">
    <div class="spark-desktop-header">
      <div class="spark-desktop-header__left">
        <div class="spark-desktop-header__title-row">
          <h1 class="spark-desktop-title">故事蓝图</h1>
          <p class="spark-desktop-subtitle">可视化节点鸟瞰项目结构</p>
        </div>
      </div>
    </div>
    <div class="blueprint-body">
      <StoryBlueprint :projectId="projectId || undefined" />
    </div>
  </div>
</template>

<script setup lang="ts">
import StoryBlueprint from '@/components/dlg-editor/StoryBlueprint.vue';
import { useProjectStore } from '@/components/stores/projectStore';
import { computed } from 'vue';

const projectStore = useProjectStore();
const projectId = computed(() => projectStore.currentProject);
</script>

<style scoped>
.blueprint-desktop {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  overflow: hidden;
}

.blueprint-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
</style>
