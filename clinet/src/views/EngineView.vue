<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header">
      <h2>Engine / 引擎绑定</h2>
    </div>
    <div class="content-area">
      <div class="engine-left">
        <AgentModelManager />
      </div>
      <div class="engine-right">
        <BindingEditor />
      </div>
    </div>
  </div>
</template>

<script setup>
import BindingEditor from '../components/lorebook/BindingEditor.vue';
import AgentModelManager from '../components/lorebook/AgentModelManager.vue';
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
  padding: 0 20px;
  background-color: var(--spark-panel-bg);
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
  padding: 20px;
  overflow-y: auto;
  display: grid;
  grid-template-columns: 720px 1fr;
  gap: 24px;
}

.engine-left, .engine-right {
  width: 100%;
}

@media (max-width: 1100px) {
  .content-area {
    grid-template-columns: 1fr;
  }
}
</style>
