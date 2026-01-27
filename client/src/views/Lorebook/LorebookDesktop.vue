<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header spark-desktop-header">
      <div class="spark-desktop-header__left">
        <h2 class="spark-desktop-title">设定集</h2>
        <p class="spark-desktop-subtitle">角色与世界观管理</p>
      </div>
    </div>

    <div class="content-area">
      <LorebookEditor :visible="true" :embedded="true" />
    </div>
  </div>
</template>

<script setup>
import LorebookEditor from '../../components/lorebook/LorebookEditor.vue';
</script>

<style scoped>
.view-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--spark-bg);
}

.content-area {
  flex: 1;
  overflow: hidden;
}
</style>
