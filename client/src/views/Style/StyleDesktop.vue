
<template>
  <div class="view-container">
    <GlobalLoading scope="style" />
    <!-- Header Section -->
    <div class="view-header spark-desktop-header">
      <div class="spark-desktop-header__left">
        <div class="spark-desktop-header__title-row">
          <h2 class="spark-desktop-title">{{ t('views.style.desktop.title') }}</h2>
          <AiSettingsPanel :visible="true" compact agent-name="agent_style" />
          <span class="spark-desktop-subtitle">{{ t('views.style.desktop.subtitle') }}</span>
        </div>
      </div>
      <div class="header-right spark-desktop-header__actions">
        <input
          ref="styleProfileImportInput"
          class="hidden-file-input"
          type="file"
          accept=".json,.md,application/json,text/markdown"
          @change="handleStyleProfileImportFile"
        />
        <n-button
          secondary
          :loading="isImportingStyleProfile"
          @click="triggerStyleProfileImport"
        >
          <template #icon><n-icon><Upload /></n-icon></template>
          {{ t('views.style.common.importProfile') }}
        </n-button>
        <n-button
          type="primary"
          :disabled="hasRunningAnalysis"
          @click="openCreateModal"
        >
          <template #icon><n-icon><Plus /></n-icon></template>
          {{ hasRunningAnalysis ? t('views.common.analyzing') : t('views.style.desktop.createStyle') }}
        </n-button>
        <n-button secondary circle @click="loadStyles">
          <template #icon><n-icon><RefreshCw /></n-icon></template>
        </n-button>
      </div>
    </div>

    <!-- Main Content: Grid Layout -->
    <div class="style-content">
      <div v-if="isLoadingList" class="loading-state">
        <n-spin size="large" :description="t('views.style.desktop.loadingStyles')" />
      </div>
      
      <div v-else-if="styles.length === 0" class="empty-state">
        <n-empty :description="t('views.style.desktop.noStyles')" size="large">
          <template #extra>
            <div class="empty-actions">
              <n-button secondary :loading="isImportingStyleProfile" @click="triggerStyleProfileImport">
                <template #icon><n-icon><Upload /></n-icon></template>
                {{ t('views.style.common.importProfile') }}
              </n-button>
              <n-button type="primary" @click="openCreateModal">
                {{ t('views.style.desktop.createFirstStyle') }}
              </n-button>
            </div>
          </template>
        </n-empty>
      </div>

      <div v-else class="style-grid">
        <div 
          v-for="style in styles" 
          :key="style" 
          class="style-card"
          @click="openStyleDetails(style)"
        >
          <div class="card-preview" :style="{ background: getGradient(style) }">
            <div class="card-icon">
              <n-icon size="48" color="rgba(255,255,255,0.9)"><Palette /></n-icon>
            </div>
            <div class="card-name">
              <h3>{{ style }}</h3>
            </div>
          </div>
          <div class="card-body">
            <div class="card-actions">
               <n-button
                 v-if="projectStore.currentProject"
                 size="small"
                 type="primary"
                 secondary
                 :disabled="isApplying || isStyleAppliedToCurrentProject(style)"
                 :loading="isApplying && applyingStyleName === style"
                 @click.stop="handleApplyToProject(style)"
               >
                 {{ isStyleAppliedToCurrentProject(style) ? t('views.style.common.applied') : t('views.style.desktop.applyToProject') }}
               </n-button>
               <n-button
                 size="small"
                 :type="isDefaultStyle(style) ? 'warning' : 'default'"
                 secondary
                 :disabled="isDefaultStyle(style)"
                 @click.stop="handleSetDefault(style)"
                >
                  {{ isDefaultStyle(style) ? t('views.style.common.isDefault') : t('views.style.common.setDefault') }}
                </n-button>
               <n-button
                 size="small"
                 quaternary
                 circle
                 :title="t('views.style.common.exportProfile')"
                 @click.stop="handleExportStyle(style)"
               >
                 <template #icon><n-icon><Download /></n-icon></template>
               </n-button>
                <n-popconfirm @positive-click.stop="handleDelete(style)">
                   <template #trigger>
                     <n-button size="small" quaternary circle type="error" @click.stop>
                      <template #icon><n-icon><Trash /></n-icon></template>
                    </n-button>
                  </template>
                  {{ t('views.style.desktop.confirmDeleteStyle') }}
               </n-popconfirm>
            </div>
          </div>
        </div>
      </div>

      <div class="runtime-panel">
        <n-collapse class="runtime-collapse">
          <n-collapse-item :title="t('views.style.desktop.runtimeBindings')" name="runtime-bindings">
            <BindingEditor />
          </n-collapse-item>
        </n-collapse>
      </div>
    </div>

    <!-- Create Modal -->
    <n-modal v-model:show="showCreateModal" preset="card" :title="t('views.style.desktop.createStyleModalTitle')" style="width: 560px" :bordered="false">
      <div class="create-modal-content">
        <div class="form-group">
          <label>{{ t('views.style.desktop.styleNameLabel') }}</label>
          <n-input v-model:value="newStyleName" :placeholder="t('views.style.desktop.styleNamePlaceholder')" size="large" />
        </div>
        <div 
          class="upload-zone"
        >
          <DocumentImportPicker
            usage="style_analysis"
            variant="desktop"
            :title="t('views.style.desktop.uploadText')"
            :subtitle="t('views.style.desktop.uploadSub')"
            @select="handleImportedFile"
            @invalid="handleInvalidImportedFile"
          />
        </div>
      </div>
    </n-modal>

    <!-- Details Drawer -->
    <n-drawer v-model:show="showDetailsDrawer" :width="600" placement="right">
      <n-drawer-content :title="selectedStyleName" closable>
        <!-- @vue-ignore -->
        <template #header-extra>
          <div class="drawer-header-actions">
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
              {{ isStyleAppliedToCurrentProject(selectedStyleName) ? t('views.style.desktop.appliedToCurrentProject') : t('views.style.desktop.applyToCurrentProject') }}
            </n-button>
          </div>
        </template>

        <div v-if="isLoadingProfile" class="loading-profile">
           <n-spin size="medium" :description="t('views.style.desktop.loadingReport')" />
        </div>
        
        <div v-else-if="currentProfile" class="profile-content">
          <div class="profile-markdown" v-html="profileMarkdown"></div>
        </div>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import {
  NIcon, NSpin, NButton, NInput, NPopconfirm, NEmpty, NModal, NDrawer, NDrawerContent, NCollapse, NCollapseItem
} from 'naive-ui';
import SparkAlert from '../../components/share/SparkAlert.vue';
import DocumentImportPicker from '../../components/import/DocumentImportPicker.vue';
import { Bookmark, Download, Palette, Plus, RefreshCw, Trash, Upload } from '@lucide/vue';
import AiSettingsPanel from '../../components/lorebook/AiSettingsPanel.vue';
import BindingEditor from '../../components/lorebook/BindingEditor.vue';
import GlobalLoading from '../../components/share/GlobalLoading.vue';
import { useStyleLogic } from '../../composables/useStyleLogic';
import { renderStyleMarkdown } from '../../utils/styleMarkdown';

const { t } = useI18n();

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
  projectStyleMessage,
  isStyleAppliedToCurrentProject,
  isDefaultStyle,
  handleSetDefault,
  loadStyles,
  openCreateModal,
  openStyleDetails,
  handleDelete,
  handleExportStyle,
  triggerStyleProfileImport,
  handleStyleProfileImportFile,
  handleApplyToProject,
  handleImportedFile,
  handleInvalidImportedFile,
  getGradient,
  projectStore
} = useStyleLogic();

/**
 * 把 currentProfile(Markdown 字符串)渲染成 HTML。
 */
const profileMarkdown = computed(() => {
  if (!currentProfile.value) return '';
  return renderStyleMarkdown(currentProfile.value);
});
</script>

<style scoped>
.view-container {
  height: 100%;
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-color);
}

.subtitle {
  margin: 0;
}

.header-right {
  display: flex;
  gap: 12px;
  align-items: center;
}

.hidden-file-input {
  display: none;
}

.empty-actions,
.drawer-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.style-content {
  flex: 1;
  /* 关键布局修复：防止Flex在无内容时坍缩 */
  width: 100%;
  min-width: 0;
  overflow-y: auto;
  padding: var(--spark-panel-padding);
  background-color: var(--bg-color-soft);
}

.status-bar {
  max-width: 1600px;
  margin: 0 auto 24px;
}

.runtime-panel {
  max-width: 1600px;
  margin: 0 auto 24px;
  padding: 4px 12px;
  background: var(--panel-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.status-title {
  font-weight: 600;
  margin-right: 12px;
}

.status-desc {
  opacity: 0.9;
}

.style-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 24px;
  max-width: 1600px;
  margin: 0 auto;
}

.style-card {
  background: var(--panel-bg);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
  transition: transform 0.2s, box-shadow 0.2s;
  cursor: pointer;
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
}

.style-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0,0,0,0.1);
}

.card-preview {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.card-name {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 8px 16px;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.5), transparent);
}

.card-name h3 {
  margin: 0;
  font-size: var(--spark-fs-lg);
  font-weight: 600;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.card-body {
  padding: 10px 16px;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  background: var(--panel-bg);
  gap: 8px;
}

.card-meta {
  margin: 0;
  font-size: var(--spark-fs-xs);
  color: var(--text-color-secondary);
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.create-modal-content {
  padding: 12px 0;
}

.form-group {
  margin-bottom: 24px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: var(--text-color);
}

.upload-zone {
  border: 2px dashed var(--border-color);
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: var(--bg-color-secondary);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}

.upload-zone:hover, .upload-zone.is-dragover {
  border-color: var(--primary-color);
  background: var(--primary-color-alpha-10);
}

.upload-icon-wrapper {
  margin-bottom: 16px;
  color: var(--text-color-secondary);
}

.upload-text {
  font-size: var(--spark-fs-md);
  color: var(--text-color);
  margin-bottom: 8px;
}

.upload-sub {
  font-size: var(--spark-fs-sm);
  color: var(--text-color-secondary);
}

.profile-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 12px 0;
}

.profile-markdown {
  font-size: var(--spark-fs-base);
  color: var(--text-color);
  line-height: 1.7;
  padding: 0 4px;
}

.profile-markdown :deep(.style-md-h2),
.profile-markdown :deep(.style-md-h3) {
  margin: 24px 0 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border-color);
  font-weight: 600;
  color: var(--primary-color);
}

.profile-markdown :deep(.style-md-h2) {
  font-size: 1.15rem;
}

.profile-markdown :deep(.style-md-h3) {
  font-size: 1.05rem;
  color: var(--text-color);
  border-bottom-style: dashed;
  opacity: 0.95;
}

.profile-markdown :deep(.style-md-p) {
  margin: 8px 0;
  color: var(--text-color);
}

.profile-markdown :deep(.style-md-ul) {
  margin: 8px 0;
  padding-left: 22px;
  list-style: disc;
}

.profile-markdown :deep(.style-md-li) {
  margin-bottom: 4px;
  color: var(--text-color);
}

.profile-markdown :deep(.style-md-hr) {
  margin: 20px 0;
  border: none;
  border-top: 1px dashed var(--border-color);
}

.profile-markdown :deep(strong) {
  color: var(--primary-color);
  font-weight: 600;
}

.loading-state, .loading-profile {
  display: flex;
  justify-content: center;
  padding: 60px;
}

.empty-state {
  padding: 80px 0;
  text-align: center;
}

.empty-profile {
  padding: 40px 0;
  text-align: center;
}

.runtime-collapse :deep(.n-collapse-item__header) {
  user-select: none;
}
.runtime-collapse :deep(.n-collapse-item__content-wrapper),
.runtime-collapse :deep(.n-collapse-item__content-inner) {
  padding-left: 0 !important;
  margin-left: 0 !important;
}
</style>
