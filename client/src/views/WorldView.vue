<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header">
      <div class="header-left">
        <h2>Genesis / 世界观构建</h2>
        <AiSettingsPanel :visible="true" :compact="true" />
      </div>
      <div class="toolbar"></div>
    </div>
    
    <div class="content-area">
      <div class="world-main">
        <div class="world-section">
          <h3 class="section-title">Lorebook 设定集</h3>
          <LorebookEditor :visible="true" :embedded="true" />
        </div>
        <div class="world-section">
          <h3 class="section-title">世界观 & 角色卡片</h3>
          <slot name="world-extra"></slot>
        </div>
      </div>
      <div 
        class="resizer world-resizer" 
        @mousedown="startDrag"
      ></div>
      <div class="world-side" :style="{ width: sideWidth + 'px' }">
        <h3 class="section-title">工具箱</h3>
        <CharacterGeneratorPanel :visible="true" :embedded="true" />
        <WorldGeneratorPanel />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue';
import LorebookEditor from '../components/lorebook/LorebookEditor.vue';
import CharacterGeneratorPanel from '../components/lorebook/CharacterGeneratorPanel.vue';
import AiSettingsPanel from '../components/lorebook/AiSettingsPanel.vue';
import WorldGeneratorPanel from '../components/lorebook/WorldGeneratorPanel.vue';

const sideWidth = ref(400);
let dragging = false;

function startDrag(e) {
  dragging = true;
  const startX = e.clientX;
  const startWidth = sideWidth.value;

  const onMove = (evt) => {
    if (!dragging) return;
    const delta = startX - evt.clientX;
    sideWidth.value = Math.max(startWidth + delta, 320);
  };

  const onUp = () => {
    dragging = false;
    window.removeEventListener('mousemove', onMove);
    window.removeEventListener('mouseup', onUp);
  };

  window.addEventListener('mousemove', onMove);
  window.addEventListener('mouseup', onUp);
}

onBeforeUnmount(() => {
  dragging = false;
});
</script>

<style scoped>
.view-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--spark-bg);
}

.panel-header {
  height: 50px;
  border-bottom: 1px solid var(--spark-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background-color: var(--spark-panel-bg);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.panel-header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--spark-text);
  -webkit-user-select: none;
  user-select: none;
  cursor: default;
}

.content-area {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.world-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: 16px 12px 16px 20px;
  gap: 16px;
  min-width: 0;
  /* Ensure initial render doesn't collapse */
  width: 100%; 
}

.world-side {
  min-width: 320px;
  border-left: 1px solid var(--spark-border);
  padding: 16px 20px;
  background-color: var(--spark-panel-bg);
  overflow-y: auto;
}

.world-section {
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius);
  padding: 12px;
}

.section-title {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: var(--spark-primary);
}

.world-resizer {
  cursor: col-resize;
}

:deep(.n-card) {
  background: transparent;
}
</style>
