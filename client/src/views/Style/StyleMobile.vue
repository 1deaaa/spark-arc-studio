
<template>
  <div class="mobile-style-view">
    <GlobalLoading scope="style" />
    <div class="mobile-header">
       <div style="flex:1"></div>
       <n-button circle quaternary @click="loadStyles">
         <template #icon><n-icon><RefreshOutline /></n-icon></template>
       </n-button>
    </div>

    <!-- Status -->
    <div class="status-summary" v-if="projectStore.currentProject">
        <SparkTag :type="hasProjectStyle ? 'success' : 'warning'">
            {{ projectStyleTitle }}
        </SparkTag>
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
              <span class="style-sub">{{ t('views.style.mobile.tapToViewReport') }}</span>
           </div>
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
           <n-icon class="chevron"><ChevronForwardOutline /></n-icon>
        </div>
    </div>

    <div class="mobile-footer-actions">
       <n-button
         type="primary"
         block
         :disabled="hasRunningAnalysis"
         @click="openCreateModal"
       >
         <template #icon><n-icon><AddOutline /></n-icon></template>
         {{ hasRunningAnalysis ? t('views.common.analyzing') : t('views.common.create') }}
       </n-button>
    </div>

    <!-- Details Sidebar (using full screen for mobile or adjusted drawer) -->
    <n-drawer v-model:show="showDetailsDrawer" width="100%" placement="right">
       <n-drawer-content :title="selectedStyleName" closable>
         <!-- @vue-ignore -->
         <template #header-extra>
            <n-button
              type="primary"
              size="small"
              @click="handleApplyToProject()"
              :loading="isApplying && applyingStyleName === selectedStyleName"
              :disabled="isApplying || isStyleAppliedToCurrentProject(selectedStyleName)"
            >
              {{ isStyleAppliedToCurrentProject(selectedStyleName) ? t('views.style.common.applied') : t('views.style.common.apply') }}
            </n-button>
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
            @click="triggerFileInput"
          >
            <input
              type="file"
              ref="fileInput"
              style="display: none"
              accept=".txt,.epub"
              @change="handleFileChange"
            />
            <n-icon size="32"><CloudUploadOutline /></n-icon>
            <p>{{ t('views.style.mobile.selectFile') }}</p>
          </div>

          <div class="mobile-upload-hint">
             {{ t('views.style.mobile.uploadHint') }}
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
import {
  RefreshOutline, ChevronForwardOutline, AddOutline, CloudUploadOutline
} from '@vicons/ionicons5';
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
  showCreateModal,
  showDetailsDrawer,
  selectedStyleName,
  currentProfile,
  isLoadingProfile,
  newStyleName,
  isDragOver,
  fileInput,
  isApplying,
  applyingStyleName,
  hasRunningAnalysis,
  hasProjectStyle,
  projectStyleTitle,
  isStyleAppliedToCurrentProject,
  getSectionTitle,
  getSectionIcon,
  formatKey,
  loadStyles,
  openCreateModal,
  openStyleDetails,
  handleApplyToProject,
  triggerFileInput,
  handleFileChange,
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
  padding: 16px 12px;
  gap: 16px;
  background: transparent;
}

.mobile-header {
  display: flex;
  justify-content: flex-end;
  align-items: center;
}

.status-summary {
  display: flex;
  justify-content: center;
}

.style-list-mobile {
  flex: 1;
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
  display: flex;
  flex-direction: column;
}

.style-name {
  font-weight: 600;
  color: var(--spark-text-bright);
}

.style-sub {
  font-size: 12px;
  color: var(--spark-text-muted);
}

.chevron {
  color: var(--spark-text-muted);
}

.mobile-footer-actions {
  padding-bottom: 24px;
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
  font-size: 11px;
  font-weight: bold;
  color: var(--spark-text-muted);
}

.attr-text {
  font-size: 14px;
  line-height: 1.5;
}

.chip-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.mobile-upload-hint {
  font-size: 12px;
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
  font-size: 13px;
}

/* 任务浮层（屏幕居中） */
</style>
