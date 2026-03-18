<template>
  <div class="view-container">
    <div class="panel-header spark-desktop-header">
      <div class="spark-desktop-header__left">
        <h2 class="spark-desktop-title">信标与引擎</h2>
        <p class="spark-desktop-subtitle">Agent Flow 与函数映射</p>
      </div>
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
  flex: 0 0 260px;
  min-width: 240px;
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
