<template>
  <div class="view-container">
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

<script setup lang="ts">
import LorebookEditor from '../../components/lorebook/LorebookEditor.vue';
</script>

<style scoped>
.view-container {
  height: 100%;
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background-color: var(--spark-bg);
}

.content-area {
  flex: 1;
  /* 布局修复：防止Flex在无内容时宽度坍缩 */
  width: 100%;
  min-width: 0;
  overflow: hidden;
}
</style>
