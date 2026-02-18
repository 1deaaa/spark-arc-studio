
<template>
  <div class="view-container spark-anim-fade">
    <!-- Header Section -->
    <div class="view-header spark-desktop-header">
      <div class="spark-desktop-header__left">
        <div class="spark-desktop-header__title-row">
          <h2 class="spark-desktop-title">风格与克隆</h2>
          <AiSettingsPanel :visible="true" compact agent-name="agent_style" />
          <span class="spark-desktop-subtitle">克隆作者文风，减少AI味，推荐使用最强模型</span>
        </div>
      </div>
      <div class="header-right spark-desktop-header__actions">
        <n-button
          type="primary"
          :disabled="analyzingTasks.some(t => t.status === 'running')"
          @click="openCreateModal"
        >
          <template #icon><n-icon><AddOutline /></n-icon></template>
          {{ analyzingTasks.some(t => t.status === 'running') ? '分析中...' : '新建风格' }}
        </n-button>
        <n-button secondary circle @click="loadStyles">
          <template #icon><n-icon><RefreshOutline /></n-icon></template>
        </n-button>
      </div>
    </div>

    <!-- Main Content: Grid Layout -->
    <div class="style-content">
      <!-- Project Status Bar -->
      <div class="status-bar" v-if="projectStore.currentProject && !isLoadingList">
        <n-alert :type="hasProjectStyle ? 'success' : 'warning'" class="mb-4">
          <template #icon>
            <n-icon><BookmarkOutline /></n-icon>
          </template>
          <span class="status-title">{{ projectStyleTitle }}</span>
          <span class="status-desc">{{ projectStyleMessage }}</span>
        </n-alert>
      </div>

      <div v-if="isLoadingList" class="loading-state">
        <n-spin size="large" description="正在加载风格档案..." />
      </div>
      
      <div v-else-if="styles.length === 0" class="empty-state">
        <n-empty description="暂无风格档案" size="large">
          <template #extra>
            <n-button type="primary" @click="openCreateModal">
              创建第一个风格
            </n-button>
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
              <n-icon size="48" color="rgba(255,255,255,0.9)"><ColorPaletteOutline /></n-icon>
            </div>
            <div class="card-overlay">
              <n-button size="small" secondary round class="view-btn">查看详情</n-button>
            </div>
          </div>
          <div class="card-body">
            <div class="card-info">
              <h3>{{ style }}</h3>
              <p class="card-meta">点击查看详细分析报告</p>
            </div>
            <div class="card-actions">
               <n-popconfirm @positive-click.stop="handleDelete(style)">
                  <template #trigger>
                    <n-button size="small" quaternary circle type="error" @click.stop>
                      <template #icon><n-icon><TrashOutline /></n-icon></template>
                    </n-button>
                  </template>
                  确定要删除这个风格档案吗？
               </n-popconfirm>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 任务浮层（仅在风格页内渲染，position:fixed 保证视口居中） -->
      <transition name="task-overlay-fade">
        <div v-if="analyzingTasks.length > 0" class="task-overlay-backdrop">
          <div class="task-overlay-panel">
            <div class="task-overlay-title">风格分析任务</div>
            <transition-group name="task-card" tag="div" class="task-overlay-list">
              <div
                v-for="task in analyzingTasks"
                :key="task.id"
                class="task-card"
                :class="`task-card--${task.status}`"
              >
                <div class="task-card__header">
                  <div class="task-card__title-row">
                    <n-spin v-if="task.status === 'running'" size="small" />
                    <n-icon v-else-if="task.status === 'done'" size="18" color="var(--success-color, #18a058)"><CheckmarkCircleOutline /></n-icon>
                    <n-icon v-else size="18" color="var(--error-color, #d03050)"><CloseCircleOutline /></n-icon>
                    <span class="task-card__name">{{ task.styleName }}</span>
                    <span class="task-card__status-text">{{ task.progressMessage }}</span>
                  </div>
                  <div class="task-card__actions">
                    <n-button
                      v-if="task.status === 'done'"
                      size="tiny"
                      type="primary"
                      @click="openStyleDetails(task.styleName)"
                    >查看详情</n-button>
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
                </div>
                <n-progress
                  v-if="task.status === 'running'"
                  type="line"
                  :percentage="task.analysisProgress"
                  :height="6"
                  :border-radius="3"
                  processing
                  :show-indicator="false"
                  class="task-card__progress"
                />
                <div v-if="task.status === 'error'" class="task-card__error">{{ task.error }}</div>
              </div>
            </transition-group>
          </div>
        </div>
      </transition>

    <!-- Create Modal -->
    <n-modal v-model:show="showCreateModal" preset="card" title="新建风格档案" style="width: 560px" :bordered="false">
      <div class="create-modal-content">
        <div class="form-group">
          <label>风格名称</label>
          <n-input v-model:value="newStyleName" placeholder="例如: 鲁迅风格, 赛博朋克风..." size="large" />
        </div>
        <div 
          class="upload-zone" 
          :class="{ 'is-dragover': isDragOver }"
          @dragover.prevent="isDragOver = true"
          @dragleave.prevent="isDragOver = false"
          @drop.prevent="handleDrop"
          @click="triggerFileInput"
        >
          <input 
            type="file" 
            ref="fileInput" 
            style="display: none" 
            accept=".txt,.epub" 
            @change="handleFileChange" 
          />
          <div class="upload-icon-wrapper">
            <n-icon size="48"><CloudUploadOutline /></n-icon>
          </div>
          <p class="upload-text">拖入文本文件 (.txt, .epub) 以分析风格</p>
          <p class="upload-sub">点击浏览文件 · 上传后立即开始后台分析</p>
        </div>
      </div>
    </n-modal>

    <!-- Details Drawer -->
    <n-drawer v-model:show="showDetailsDrawer" :width="600" placement="right">
      <n-drawer-content :title="selectedStyleName" closable>
        <template #header-extra>
           <n-button 
             type="primary" 
             size="small" 
             @click="handleApplyToProject"
             :loading="isApplying"
           >
             应用到当前项目
           </n-button>
        </template>

        <div v-if="isLoadingProfile" class="loading-profile">
           <n-spin size="medium" description="正在加载分析报告..." />
        </div>
        
        <div v-else-if="currentProfile" class="profile-content">
          <template v-if="currentProfile.writing_style_analysis_framework">
            <div 
              v-for="(sectionData, sectionKey) in currentProfile.writing_style_analysis_framework" 
              :key="sectionKey"
              class="profile-section-card"
            >
              <div class="section-header">
                <n-icon :component="getSectionIcon(sectionKey)" color="var(--primary-color)" />
                <h4>{{ getSectionTitle(sectionKey) }}</h4>
              </div>
              
              <div class="section-body">
                <div v-for="(value, key) in sectionData" :key="key" class="attribute-row">
                   <template v-if="Array.isArray(value)">
                     <div class="attribute-label">{{ formatKey(key) }}</div>
                     <ul class="attribute-list">
                       <li v-for="(item, idx) in value" :key="idx">{{ item }}</li>
                     </ul>
                   </template>
                   <template v-else-if="typeof value === 'string'">
                     <div class="attribute-label">{{ formatKey(key) }}</div>
                     <div class="attribute-value">{{ value }}</div>
                   </template>
                </div>
              </div>
            </div>
          </template>
          
          <div class="json-section">
            <n-collapse>
                <n-collapse-item title="查看完整 JSON 数据" name="1">
                    <pre class="json-view">{{ JSON.stringify(currentProfile, null, 2) }}</pre>
                </n-collapse-item>
            </n-collapse>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<script setup>
import {
  NIcon, NSpin, NButton, NInput, NPopconfirm, NEmpty, NCollapse, NCollapseItem,
  NModal, NDrawer, NDrawerContent, NAlert, NProgress
} from 'naive-ui';
import {
  CloudUploadOutline, AddOutline, TrashOutline, RefreshOutline, ColorPaletteOutline,
  BookmarkOutline, CheckmarkCircleOutline, CloseCircleOutline, CloseOutline
} from '@vicons/ionicons5';
import AiSettingsPanel from '../../components/lorebook/AiSettingsPanel.vue';
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
  projectStyleMessage,
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
  dismissTask,
  getGradient,
  projectStore
} = useStyleLogic();
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

.style-content {
  flex: 1;
  /* 关键布局修复：防止Flex在无内容时坍缩 */
  width: 100%;
  min-width: 0;
  overflow-y: auto;
  padding: 32px;
  background-color: var(--bg-color-soft);
}

.status-bar {
  max-width: 1600px;
  margin: 0 auto 24px;
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
  height: 240px;
}

.style-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0,0,0,0.1);
}

.card-preview {
  height: 140px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.card-overlay {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s;
}

.style-card:hover .card-overlay {
  opacity: 1;
}

.card-body {
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  background: var(--panel-bg);
  flex: 1;
}

.card-info h3 {
  margin: 0 0 4px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-color);
}

.card-meta {
  margin: 0;
  font-size: 12px;
  color: var(--text-color-secondary);
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
  font-size: 15px;
  color: var(--text-color);
  margin-bottom: 8px;
}

.upload-sub {
  font-size: 13px;
  color: var(--text-color-secondary);
}

.task-area {
  padding: 0 32px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 8px;
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
  padding: 20px;
  width: min(92vw, 480px);
  box-shadow: 0 12px 40px color-mix(in srgb, var(--spark-primary) 20%, black 60%);
  pointer-events: auto;
}

.task-overlay-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--spark-text-muted);
  margin-bottom: 12px;
  text-align: center;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.task-overlay-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-overlay-fade-enter-active,
.task-overlay-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.task-overlay-fade-enter-from,
.task-overlay-fade-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.97);
}

.task-card {
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-primary) 4%);
  border: 1px solid var(--spark-border);
  border-radius: 10px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: box-shadow 0.2s;
}

.task-card--running {
  border-left: 3px solid var(--spark-primary);
}

.task-card--done {
  border-left: 3px solid var(--spark-success, #50fa7b);
}

.task-card--error {
  border-left: 3px solid var(--spark-danger, #ff5555);
}

.task-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.task-card__title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.task-card__name {
  font-weight: 600;
  font-size: 14px;
  color: var(--spark-text);
  white-space: nowrap;
}

.task-card__status-text {
  font-size: 12px;
  color: var(--spark-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-card__actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.task-card__progress {
  margin-top: 2px;
}

.task-card__error {
  font-size: 12px;
  color: var(--spark-danger, #ff5555);
  margin-top: 2px;
}

/* 任务卡片进入/离开动画 */
.task-card-enter-active,
.task-card-leave-active {
  transition: all 0.3s ease;
}
.task-card-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}
.task-card-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

.profile-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 12px 0;
}

.profile-section-card {
  background: var(--bg-color-secondary);
  padding: 20px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
}

.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.section-header h4 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-color);
}

.section-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.attribute-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.attribute-label {
  font-size: 12px;
  color: var(--text-color-secondary);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.attribute-value {
  font-size: 14px;
  color: var(--text-color);
  line-height: 1.6;
}

.attribute-list {
  margin: 0;
  padding-left: 20px;
  font-size: 14px;
  color: var(--text-color);
  line-height: 1.6;
}

.attribute-list li {
  margin-bottom: 4px;
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

.json-view {
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 16px;
    border-radius: 6px;
    overflow: auto;
    font-family: var(--spark-mono);
    font-size: 13px;
    max-height: 400px;
    line-height: 1.5;
}

.spark-anim-fade {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
