
<template>
  <div class="mobile-style-view">
    <GlobalLoading scope="style" />
    <input
      ref="styleProfileImportInput"
      class="hidden-file-input"
      type="file"
      accept=".json,application/json"
      @change="handleStyleProfileImportFile"
    />
    <div class="mobile-header">
       <div class="status-summary" v-if="projectStore.currentProject">
        <SparkTag :type="hasProjectStyle ? 'success' : 'warning'">
            {{ projectStyleTitle }}
        </SparkTag>
       </div>
       <div class="status-summary-placeholder" v-else></div>
       <n-button circle quaternary size="small" @click="loadStyles">
         <template #icon><n-icon><RefreshCw /></n-icon></template>
       </n-button>
    </div>

    <!-- Content -->
    <div class="style-list-mobile">
        <n-spin v-if="isLoadingList" />
        <n-empty v-else-if="styles.length === 0" :description="t('views.style.mobile.noLocalStyle')" />
        <div 
          v-else 
          v-for="style in styles" 
          :key="style"
          class="mobile-style-item"
          @click="openStyleDetails(style)"
        >
           <div class="style-indicator" :style="{ background: getGradient(style) }"></div>
           <div class="style-info">
              <span class="style-name">{{ style }}</span>
            </div>
            <div class="mobile-style-actions">
             <n-button
               v-if="projectStore.currentProject"
               size="tiny"
               type="primary"
               secondary
               :disabled="isApplying || isStyleAppliedToCurrentProject(style)"
               :loading="isApplying && applyingStyleName === style"
               @click.stop="handleApplyToProject(style)"
             >
               {{ isStyleAppliedToCurrentProject(style) ? t('views.style.common.applied') : t('views.style.common.apply') }}
             </n-button>
             <n-button
               size="tiny"
               :type="isDefaultStyle(style) ? 'warning' : 'default'"
               secondary
               :disabled="isDefaultStyle(style)"
               @click.stop="handleSetDefault(style)"
             >
               {{ isDefaultStyle(style) ? t('views.style.common.isDefault') : t('views.style.common.setDefault') }}
             </n-button>
             <n-button
               size="tiny"
               quaternary
               circle
               :title="t('views.style.common.exportProfile')"
               @click.stop="handleExportStyle(style)"
             >
               <template #icon><n-icon><Download /></n-icon></template>
             </n-button>
            </div>
            <n-icon class="chevron"><ChevronRight /></n-icon>
         </div>
     </div>

     <div class="mobile-footer-actions">
       <n-button
         secondary
         block
         :loading="isImportingStyleProfile"
         @click="triggerStyleProfileImport"
       >
         <template #icon><n-icon><Upload /></n-icon></template>
         {{ t('views.style.common.importProfile') }}
       </n-button>
       <n-button
         type="primary"
         block
         :disabled="hasRunningAnalysis"
         @click="openCreateModal"
       >
         <template #icon><n-icon><Plus /></n-icon></template>
         {{ hasRunningAnalysis ? t('views.common.analyzing') : t('views.common.create') }}
       </n-button>
    </div>

    <!-- Details Sidebar (using full screen for mobile or adjusted drawer) -->
    <n-drawer v-model:show="showDetailsDrawer" width="100%" placement="right">
       <n-drawer-content :title="selectedStyleName" closable>
         <!-- @vue-ignore -->
         <template #header-extra>
             <div class="mobile-drawer-actions">
               <n-button
                 secondary
                 size="small"
                 @click="handleExportStyle(selectedStyleName)"
               >
                 <template #icon><n-icon><Download /></n-icon></template>
                 {{ t('views.style.common.exportProfile') }}
               </n-button>
               <n-button
                 type="primary"
                 size="small"
                 @click="handleApplyToProject()"
                 :loading="isApplying && applyingStyleName === selectedStyleName"
                 :disabled="isApplying || isStyleAppliedToCurrentProject(selectedStyleName)"
               >
                 {{ isStyleAppliedToCurrentProject(selectedStyleName) ? t('views.style.common.applied') : t('views.style.common.apply') }}
               </n-button>
             </div>
          </template>

         <div v-if="isLoadingProfile" class="loading-state">
            <n-spin size="medium" />
         </div>

         <div v-else-if="currentProfile" class="mobile-profile-content">
            <div 
              v-for="(sectionData, sectionKey) in profileSections" 
              :key="sectionKey"
              class="mobile-profile-card"
            >
               <div class="card-header">
                  <n-icon :component="getSectionIcon(sectionKey)" />
                  <h4>{{ getSectionTitle(sectionKey) }}</h4>
               </div>
               <div class="card-body">
                  <div v-for="(value, key) in sectionData" :key="key" class="attr-group">
                      <label>{{ formatKey(key) }}</label>
                      <div v-if="Array.isArray(value)" class="chip-group">
                         <SparkTag v-for="tag in value" :key="tag" size="tiny" type="default" :ghost="true">{{ tag }}</SparkTag>
                      </div>
                      <div v-else class="attr-text">{{ value }}</div>
                  </div>
               </div>
            </div>
         </div>
       </n-drawer-content>
    </n-drawer>

    <!-- Simple Create Modal for Mobile -->
     <n-modal v-model:show="showCreateModal" preset="card" :title="t('views.style.mobile.createStyle')" style="width: 90vw">
       <div class="mobile-form">
         <n-form-item :label="t('views.style.desktop.styleNameLabel')">
           <n-input v-model:value="newStyleName" :placeholder="t('views.style.mobile.styleName')" />
          </n-form-item>
          
          <div
            class="mobile-upload-zone"
          >
            <DocumentImportPicker
              usage="style_analysis"
              variant="mobile"
              :icon-size="32"
              :title="t('views.style.mobile.selectFile')"
              :subtitle="t('views.style.mobile.uploadHint')"
              @select="handleImportedFile"
              @invalid="handleInvalidImportedFile"
            />
          </div>

       </div>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { NIcon, NSpin, NButton, NInput, NEmpty, NDrawer, NDrawerContent, NModal, NFormItem } from 'naive-ui';
import SparkTag from '../../components/share/SparkTag.vue';
import DocumentImportPicker from '../../components/import/DocumentImportPicker.vue';
import { ChevronRight, Download, Plus, RefreshCw, Upload } from '@lucide/vue';
import GlobalLoading from '../../components/share/GlobalLoading.vue';
import { useStyleLogic } from '../../composables/useStyleLogic';

const { t } = useI18n();

// 已知的顶层区块键名
const KNOWN_SECTION_KEYS = new Set([
  'cognitive_fingerprint', 'verbal_physicality', 'emotional_processing',
  'sensory_and_attention', 'interpersonal_field', 'coordinator',
  'inner_monologue', 'emotional_progression', 'theme_tendency',
  'subtext_layer', 'dialogue_system', 'perspective_system',
  'scene_construction', 'detail_craftsmanship', 'structural_breathing',
]);

const {
  styles,
  isLoadingList,
  isImportingStyleProfile,
  styleProfileImportInput,
  showCreateModal,
  showDetailsDrawer,
  selectedStyleName,
  currentProfile,
  isLoadingProfile,
  newStyleName,
  isApplying,
  applyingStyleName,
  hasRunningAnalysis,
  hasProjectStyle,
  projectStyleTitle,
  isStyleAppliedToCurrentProject,
  isDefaultStyle,
  handleSetDefault,
  handleExportStyle,
  triggerStyleProfileImport,
  handleStyleProfileImportFile,
  getSectionTitle,
  getSectionIcon,
  formatKey,
  loadStyles,
  openCreateModal,
  openStyleDetails,
  handleApplyToProject,
  handleImportedFile,
  handleInvalidImportedFile,
  getGradient,
  projectStore
} = useStyleLogic();

// 适配层：兼容新旧两种 JSON 格式
const profileSections = computed(() => {
  if (!currentProfile.value) return null;
  const profile = currentProfile.value;
  const hasKnownSections = Object.keys(profile).some(k => KNOWN_SECTION_KEYS.has(k));
  if (hasKnownSections) {
    const sections = {};
    for (const [k, v] of Object.entries(profile)) {
      if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
        sections[k] = v;
      }
    }
    return Object.keys(sections).length > 0 ? sections : null;
  }
  if (profile.writing_style_analysis_framework) {
    return profile.writing_style_analysis_framework;
  }
  return null;
});
</script>

<style scoped>
.mobile-style-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0 4px;
  gap: 10px;
  background: transparent;
  min-height: 0;
}

.hidden-file-input {
  display: none;
}

.mobile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  min-height: 34px;
}

.status-summary {
  display: flex;
  justify-content: flex-start;
  min-width: 0;
}

.status-summary :deep(.spark-tag) {
  max-width: 100%;
}

.status-summary-placeholder {
  flex: 1;
  min-width: 0;
}

.style-list-mobile {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mobile-style-item {
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.style-indicator {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  flex-shrink: 0;
}

.style-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.style-name {
  font-weight: 600;
  color: var(--spark-text-bright);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.style-sub {
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-muted);
}

.chevron {
  color: var(--spark-text-muted);
  flex-shrink: 0;
}

.mobile-style-actions,
.mobile-drawer-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.mobile-footer-actions {
  padding-bottom: 24px;
  display: flex;
  gap: 8px;
}

.mobile-footer-actions :deep(.n-button) {
  flex: 1;
  min-width: 0;
}

.mobile-profile-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mobile-profile-card {
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 8px;
  padding: 8px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  color: var(--spark-primary);
}

.card-header h4 {
  margin: 0;
}

.attr-group {
  margin-bottom: 6px;
}

.attr-group label {
  font-size: var(--spark-fs-2xs);
  font-weight: bold;
  color: var(--spark-text-muted);
}

.attr-text {
  font-size: var(--spark-fs-base);
  line-height: 1.5;
}

.chip-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.mobile-upload-hint {
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-muted);
  text-align: center;
  padding: 12px 0;
}

.mobile-upload-zone {
  border: 2px dashed var(--spark-border);
  border-radius: 12px;
  padding: 24px;
  text-align: center;
  background: var(--spark-panel-bg);
  color: var(--spark-text-muted);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.mobile-upload-zone p {
  margin: 0;
  font-size: var(--spark-fs-sm);
}

/* 任务浮层（屏幕居中） */
</style>
