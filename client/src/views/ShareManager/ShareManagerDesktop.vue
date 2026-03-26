<template>
  <div class="share-manager-desktop">
    <div class="spark-desktop-header">
      <div class="spark-desktop-header__left">
        <div class="spark-desktop-header__title-row">
          <h1 class="spark-desktop-title">发布与版本</h1>
          <p class="spark-desktop-subtitle">版本管理与分享历史</p>
        </div>
      </div>
    </div>
    <div class="share-manager-body">
      <VersionManager />
    </div>
  </div>
</template>

<script setup lang="ts">
import VersionManager from '@/components/dlg-editor/VersionManager.vue';
</script>

<style scoped>
.share-manager-desktop {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  overflow: hidden;
}

.share-manager-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px;
}
</style>
