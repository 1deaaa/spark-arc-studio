<template>
  <div class="share-manager-desktop">
    <div class="spark-desktop-header">
      <div class="spark-desktop-header__left">
        <div class="spark-desktop-header__title-row">
          <h1 class="spark-desktop-title">{{ t('views.shareManager.title') }}</h1>
          <p class="spark-desktop-subtitle">{{ t('views.shareManager.subtitle') }}</p>
        </div>
      </div>
    </div>
    <div class="share-manager-body">
      <VersionManager hide-title />
    </div>
  </div>
</template>

<script setup lang="ts">
import VersionManager from '@/components/dlg-editor/VersionManager.vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
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
  padding: var(--spark-panel-padding);
}
</style>
