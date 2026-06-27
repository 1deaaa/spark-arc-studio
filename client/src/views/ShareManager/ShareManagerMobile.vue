<template>
  <div class="share-manager-mobile">
    <div class="mobile-header">
      <h2>{{ t('views.shareManager.title') }}</h2>
      <p class="subtitle">{{ t('views.shareManager.mobileSubtitle') }}</p>
    </div>
    <div class="mobile-body">
      <VersionManager hide-title />
    </div>
  </div>
</template>

<script setup lang="ts">
import VersionManager from '../../components/dlg-editor/VersionManager.vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
</script>

<style scoped>
.share-manager-mobile {
  padding: 16px;
  padding-top: calc(16px + var(--sat, 0px));
  min-height: 100vh;
  background: var(--spark-bg);
  display: flex;
  flex-direction: column;
}

.mobile-header {
  margin-bottom: 20px;
}

.mobile-header h2 {
  font-size: var(--spark-fs-h2);
  margin: 0 0 4px;
  color: var(--spark-text);
}

.subtitle {
  font-size: var(--spark-fs-sm);
  color: var(--spark-text-muted);
  margin: 0;
}

.mobile-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
</style>
