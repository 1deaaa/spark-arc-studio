<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header">
      <h2>Agent管理与函数映射</h2>
    </div>
    <div class="content-area">
      <div class="engine-main">
        <AgentFlowBlueprint />
      </div>
      <div class="engine-right">
        <BindingEditor />
      </div>
    </div>
  </div>
</template>

<script setup>
import BindingEditor from '../../components/lorebook/BindingEditor.vue';
import AgentFlowBlueprint from '../../components/lorebook/AgentFlowBlueprint.vue';
</script>

<style scoped>
.view-container {
  height: 100%;
  width: 100%;
  flex: 1 1 auto;
  min-width: 0;
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
  width: 100%;
  min-width: 0;
  padding: 20px;
  overflow: hidden;
  display: flex;
  gap: 16px;
}

.engine-main {
  flex: 1 1 85%;
  min-width: 0;
  height: 100%;
  overflow: hidden;
}

.engine-right {
  flex: 0 0 15%;
  min-width: 0;
  height: 100%;
  overflow: auto;
}

@media (max-width: 1100px) {
  .content-area {
    flex-direction: column;
  }

  .engine-right {
    flex: 0 0 auto;
  }
}
</style>
