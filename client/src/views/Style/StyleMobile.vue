
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
        <n-tag :type="hasProjectStyle ? 'success' : 'warning'" round>
             <template #icon><n-icon :component="BookmarkOutline" /></template>
             {{ projectStyleTitle }}
        </n-tag>
    </div>

    <!-- 后台分析任务浮层（仅在风格页内渲染，position:fixed 保证视口居中） -->
      <transition name="task-overlay-fade">
        <div v-if="analyzingTasks.length > 0" class="task-overlay-backdrop">
          <div class="task-overlay-panel">
            <div class="task-overlay-title">风格分析任务</div>
            <transition-group name="task-card" tag="div" class="task-overlay-list">
              <div
                v-for="task in analyzingTasks"
                :key="task.id"
                class="task-card-mobile"
                :class="`task-card-mobile--${task.status}`"
              >
                <div class="task-card-mobile__header">
                  <n-spin v-if="task.status === 'running'" size="small" />
                  <n-icon v-else-if="task.status === 'done'" size="16" color="var(--success-color, #18a058)"><CheckmarkCircleOutline /></n-icon>
                  <n-icon v-else size="16" color="var(--error-color, #d03050)"><CloseCircleOutline /></n-icon>
                  <span class="task-card-mobile__name">{{ task.styleName }}</span>
                  <span class="task-card-mobile__msg">{{ task.progressMessage }}</span>
                  <div style="flex:1" />
                  <n-button
                    v-if="task.status === 'running'"
                    size="tiny"
                    secondary
                    type="warning"
                    @click="cancelTask(task.id)"
                  >取消</n-button>
                  <n-button
                    v-if="task.status === 'done'"
                    size="tiny"
                    type="primary"
                    @click="openStyleDetails(task.styleName)"
                  >查看</n-button>
                  <n-button
                    v-if="task.status !== 'running'"
                    size="tiny"
                    quaternary
                    circle
                    @click="dismissTask(task.id)"
                  >
                    <template #icon><n-icon><CloseOutline /></n-icon></template>
                  </n-button>
                </div>
                <n-progress
                  v-if="task.status === 'running'"
                  type="line"
                  :percentage="task.analysisProgress"
                  :height="4"
                  :border-radius="2"
                  processing
                  :show-indicator="false"
                  style="margin-top: 6px"
                />
              </div>
            </transition-group>
          </div>
        </div>
      </transition>

    <!-- Content -->
    <div class="style-list-mobile">
        <n-spin v-if="isLoadingList" />
        <n-empty v-else-if="styles.length === 0" description="暂无本地风格" />
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
              <span class="style-sub">点击查看报告</span>
           </div>
           <n-icon class="chevron"><ChevronForwardOutline /></n-icon>
        </div>
    </div>

    <div class="mobile-footer-actions">
       <n-button
         type="primary"
         block
         :disabled="analyzingTasks.some(t => t.status === 'running')"
         @click="openCreateModal"
       >
         <template #icon><n-icon><AddOutline /></n-icon></template>
         {{ analyzingTasks.some(t => t.status === 'running') ? '分析中...' : '新建' }}
       </n-button>
    </div>

    <!-- Details Sidebar (using full screen for mobile or adjusted drawer) -->
    <n-drawer v-model:show="showDetailsDrawer" width="100%" placement="right">
       <n-drawer-content :title="selectedStyleName" closable>
         <template #header-extra>
            <n-button type="primary" size="small" @click="handleApplyToProject" :loading="isApplying">
              应用
            </n-button>
         </template>

         <div v-if="isLoadingProfile" class="loading-state">
            <n-spin size="medium" />
         </div>

         <div v-else-if="currentProfile" class="mobile-profile-content">
            <div 
              v-for="(sectionData, sectionKey) in currentProfile.writing_style_analysis_framework" 
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
                         <n-tag v-for="tag in value" :key="tag" size="tiny" quaternary round>{{ tag }}</n-tag>
                      </div>
                      <div v-else class="attr-text">{{ value }}</div>
                  </div>
               </div>
            </div>
         </div>
       </n-drawer-content>
    </n-drawer>

    <!-- Simple Create Modal for Mobile -->
    <n-modal v-model:show="showCreateModal" preset="card" title="新建风格" style="width: 90vw">
       <div class="mobile-form">
          <n-form-item label="名称">
             <n-input v-model:value="newStyleName" placeholder="风格名称" />
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
            <p>点击选择文件 (.txt, .epub)</p>
          </div>

          <div class="mobile-upload-hint">
             上传后将立即在后台开始风格分析。
          </div>
       </div>
    </n-modal>
  </div>
</template>

<script setup>
import { NIcon, NSpin, NButton, NInput, NEmpty, NDrawer, NDrawerContent, NTag, NModal, NFormItem, NProgress } from 'naive-ui';
import {
  RefreshOutline, ChevronForwardOutline, BookmarkOutline, AddOutline,
  CheckmarkCircleOutline, CloseCircleOutline, CloseOutline, CloudUploadOutline
} from '@vicons/ionicons5';
import GlobalLoading from '../../components/share/GlobalLoading.vue';
import { useStyleLogic } from '../../composables/useStyleLogic';

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
  analyzingTasks,
  hasProjectStyle,
  projectStyleTitle,
  getSectionTitle,
  getSectionIcon,
  formatKey,
  loadStyles,
  openCreateModal,
  openStyleDetails,
  handleDelete,
  handleApplyToProject,
  triggerFileInput,
  handleFileChange,
  handleDrop,
  cancelTask,
  dismissTask,
  getGradient,
  projectStore
} = useStyleLogic();
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
  gap: 16px;
}

.mobile-profile-card {
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 8px;
  padding: 12px;
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
  margin-bottom: 12px;
}

.attr-group label {
  font-size: 11px;
  font-weight: bold;
  color: var(--spark-text-muted);
  text-transform: uppercase;
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
.task-overlay-backdrop {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9000;
  pointer-events: none;
}

.task-overlay-panel {
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border-hover);
  border-radius: 14px;
  padding: 16px;
  width: min(88vw, 360px);
  box-shadow: 0 8px 32px color-mix(in srgb, var(--spark-primary) 20%, black 60%);
  pointer-events: auto;
}

.task-overlay-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--spark-text-muted);
  margin-bottom: 10px;
  text-align: center;
  letter-spacing: 0.04em;
}

.task-overlay-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-overlay-fade-enter-active,
.task-overlay-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.task-overlay-fade-enter-from,
.task-overlay-fade-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.97);
}

/* 任务卡片 */
.task-card-mobile {
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-primary) 4%);
  border: 1px solid var(--spark-border);
  border-radius: 10px;
  padding: 10px 12px;
  border-left: 3px solid var(--spark-primary);
}

.task-card-mobile--done {
  border-left-color: var(--spark-success, #50fa7b);
}

.task-card-mobile--error {
  border-left-color: var(--spark-danger, #ff5555);
}

.task-card-mobile__header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.task-card-mobile__name {
  font-weight: 600;
  font-size: 13px;
  white-space: nowrap;
}

.task-card-mobile__msg {
  font-size: 11px;
  color: var(--spark-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100px;
}

/* 动画 */
.task-card-enter-active,
.task-card-leave-active {
  transition: all 0.3s ease;
}
.task-card-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}
.task-card-leave-to {
  opacity: 0;
  transform: translateX(16px);
}
</style>
