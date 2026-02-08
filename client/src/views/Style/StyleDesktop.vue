
<template>
  <div class="view-container spark-anim-fade">
    <!-- Header Section -->
    <div class="view-header spark-desktop-header">
      <div class="spark-desktop-header__left">
        <div class="spark-desktop-header__title-row">
          <h2 class="spark-desktop-title">风格与克隆</h2>
          <AiSettingsPanel :visible="true" compact agent-name="agent_style" />
          <span class="spark-desktop-subtitle">克隆作者文风，减少AI味</span>
        </div>
      </div>
      <div class="header-right spark-desktop-header__actions">
        <n-button type="primary" @click="openCreateModal">
          <template #icon><n-icon><AddOutline /></n-icon></template>
          新建风格
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

    <!-- Create Modal -->
    <n-modal v-model:show="showCreateModal" preset="card" title="新建风格档案" style="width: 600px" :bordered="false">
      <div class="create-modal-content">
        <div class="form-group">
          <label>风格名称</label>
          <n-input v-model:value="newStyleName" placeholder="例如: 鲁迅风格, 赛博朋克风..." size="large" />
        </div>
        
        <div 
          class="upload-zone" 
          :class="{ 'is-dragover': isDragOver, 'is-analyzing': isAnalyzing }"
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
          
          <template v-if="isAnalyzing">
            <n-spin size="large" />
            <p class="upload-text">{{ progressMessage || '正在分析风格... (这可能需要几分钟)' }}</p>
            <div class="progress-bar-container" v-if="analysisProgress > 0 && analysisProgress < 100">
                 <n-progress
                    type="line"
                    :percentage="analysisProgress"
                    :height="12"
                    :border-radius="6"
                    processing
                    indicator-placement="inside"
                  />
                  <p class="progress-sub">正在深度分析作者风格 (串行模式)...</p>
            </div>
          </template>
          <template v-else>
            <div class="upload-icon-wrapper">
              <n-icon size="48"><CloudUploadOutline /></n-icon>
            </div>
            <p class="upload-text">拖入文本文件 (.txt, .epub) 以分析风格</p>
            <p class="upload-sub">点击浏览文件</p>
          </template>
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
  BookmarkOutline
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
  isAnalyzing,
  progressMessage,
  vectorProgress,
  isDragOver,
  fileInput,
  isApplying,
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

.progress-bar-container {
    width: 80%;
    margin-top: 16px;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.progress-sub {
    font-size: 12px;
    color: var(--text-color-secondary);
    margin-top: 4px;
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
