<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header">
      <h2>Style Agent / 风格管理</h2>
      <div class="toolbar">
        <n-button @click="showCreateMode = true" type="primary" size="small">
          <template #icon><n-icon><AddOutline /></n-icon></template>
          新建风格
        </n-button>
        <AiSettingsPanel :visible="true" compact />
      </div>
    </div>
    
    <div class="content-area style-layout">
      <!-- Left Sidebar: Style List -->
      <div class="style-sidebar spark-card">
        <div class="sidebar-header">
          <h3>我的风格档案</h3>
          <n-button size="tiny" secondary circle @click="loadStyles">
            <template #icon><n-icon><RefreshOutline /></n-icon></template>
          </n-button>
        </div>
        
        <div v-if="isLoadingList" class="loading-list">
          <n-spin size="small" />
        </div>
        <div v-else-if="styles.length === 0" class="empty-list">
          <p>暂无风格档案</p>
        </div>
        <n-list v-else hoverable clickable>
          <n-list-item 
            v-for="style in styles" 
            :key="style"
            :class="{ 'active': selectedStyleName === style }"
            @click="selectStyle(style)"
          >
            <div class="style-item-content">
              <span class="style-name">{{ style }}</span>
              <div class="style-actions">
                 <n-popconfirm @positive-click.stop="handleDelete(style)">
                    <template #trigger>
                      <n-button size="tiny" quaternary circle type="error" @click.stop>
                        <template #icon><n-icon><TrashOutline /></n-icon></template>
                      </n-button>
                    </template>
                    确定要删除这个风格档案吗？
                 </n-popconfirm>
              </div>
            </div>
          </n-list-item>
        </n-list>
      </div>

      <!-- Right Content: Details or Create -->
      <div class="style-main">
        
        <!-- Create Mode -->
        <div v-if="showCreateMode" class="create-panel spark-card">
          <div class="panel-title">
            <h3>新建风格档案</h3>
            <n-button size="small" quaternary @click="showCreateMode = false">取消</n-button>
          </div>
          
          <div class="form-group">
            <label>风格名称</label>
            <n-input v-model:value="newStyleName" placeholder="例如: 鲁迅风格, 赛博朋克风..." />
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
              <p>正在分析风格... (这可能需要几分钟)</p>
            </template>
            <template v-else>
              <n-icon size="48"><CloudUploadOutline /></n-icon>
              <p>拖入文本文件 (.txt, .epub) 以分析风格</p>
              <p class="sub">点击浏览文件</p>
            </template>
          </div>
        </div>

        <!-- Details Mode -->
        <div v-else-if="selectedStyleName" class="details-panel spark-card">
          <div class="panel-title">
            <h3>{{ selectedStyleName }}</h3>
            <div class="actions">
               <n-button 
                 type="primary" 
                 size="small" 
                 @click="handleApplyToProject"
                 :loading="isApplying"
               >
                 应用到当前项目
               </n-button>
            </div>
          </div>
          
          <div v-if="isLoadingProfile" class="loading-profile">
             <n-spin size="medium" />
          </div>
          <div v-else-if="currentProfile" class="profile-content">
            <div class="profile-grid">
              <div class="profile-section">
                <h4>Narrative Voice / 叙事声音</h4>
                <p>{{ currentProfile.narrative_voice?.description || 'N/A' }}</p>
              </div>
              <div class="profile-section">
                <h4>Pacing / 节奏</h4>
                <p>{{ currentProfile.pacing?.description || 'N/A' }}</p>
              </div>
              <div class="profile-section">
                <h4>Dialogue Style / 对话风格</h4>
                <p>{{ currentProfile.dialogue_style?.description || 'N/A' }}</p>
              </div>
              <div class="profile-section">
                <h4>Tone / 基调</h4>
                <p>{{ currentProfile.tone?.description || 'N/A' }}</p>
              </div>
            </div>
            
            <div class="json-section">
              <n-collapse>
                  <n-collapse-item title="查看完整 JSON 数据" name="1">
                      <pre class="json-view">{{ JSON.stringify(currentProfile, null, 2) }}</pre>
                  </n-collapse-item>
              </n-collapse>
            </div>
          </div>
        </div>
        
        <!-- Empty State -->
        <div v-else class="empty-state spark-card">
          <n-empty description="请选择左侧风格档案或新建一个">
             <template #extra>
                <n-button type="primary" @click="showCreateMode = true">
                  新建风格
                </n-button>
             </template>
          </n-empty>
        </div>
        
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onActivated } from 'vue';
import { 
  NIcon, NSpin, NButton, NList, NListItem, NInput, NPopconfirm, NEmpty, NCollapse, NCollapseItem,
  useMessage, useDialog 
} from 'naive-ui';
import { 
  CloudUploadOutline, AddOutline, TrashOutline, RefreshOutline 
} from '@vicons/ionicons5';
import { analyzeStyle, getStyles, deleteStyle, applyStyle } from '../services/aiService';
import { getStyleProfile } from '../services/storyService';
import { useProjectStore } from '../components/stores/projectStore';
import AiSettingsPanel from '../components/lorebook/AiSettingsPanel.vue';

const projectStore = useProjectStore();
const message = useMessage();

// State
const styles = ref([]);
const isLoadingList = ref(false);
const showCreateMode = ref(false);
const selectedStyleName = ref(null);
const currentProfile = ref(null);
const isLoadingProfile = ref(false);

// Create State
const newStyleName = ref('');
const isAnalyzing = ref(false);
const isDragOver = ref(false);
const fileInput = ref(null);

// Apply State
const isApplying = ref(false);

// Methods
const loadStyles = async () => {
  isLoadingList.value = true;
  try {
    styles.value = await getStyles();
  } catch (e) {
    message.error('加载风格列表失败: ' + e.message);
  } finally {
    isLoadingList.value = false;
  }
};

const selectStyle = async (name) => {
  selectedStyleName.value = name;
  showCreateMode.value = false;
  isLoadingProfile.value = true;
  currentProfile.value = null;
  
  try {
    // Pass styleName to getStyleProfile
    currentProfile.value = await getStyleProfile(null, name);
  } catch (e) {
    message.error('加载风格详情失败: ' + e.message);
  } finally {
    isLoadingProfile.value = false;
  }
};

const handleDelete = async (name) => {
  try {
    await deleteStyle(name);
    message.success('删除成功');
    if (selectedStyleName.value === name) {
      selectedStyleName.value = null;
      currentProfile.value = null;
    }
    await loadStyles();
  } catch (e) {
    message.error('删除失败: ' + e.message);
  }
};

const handleApplyToProject = async () => {
  if (!projectStore.currentProject) {
    message.warning('请先打开一个项目');
    return;
  }
  
  isApplying.value = true;
  try {
    await applyStyle(selectedStyleName.value, projectStore.currentProject);
    message.success(`已将 "${selectedStyleName.value}" 应用到当前项目`);
  } catch (e) {
    message.error('应用失败: ' + e.message);
  } finally {
    isApplying.value = false;
  }
};

// Upload Logic
const triggerFileInput = () => {
  if (isAnalyzing.value) return;
  fileInput.value.click();
};

const handleFileChange = (event) => {
  const file = event.target.files[0];
  if (file) processFile(file);
  // Reset input
  event.target.value = '';
};

const handleDrop = (event) => {
  isDragOver.value = false;
  if (isAnalyzing.value) return;
  const file = event.dataTransfer.files[0];
  if (file) processFile(file);
};

const processFile = async (file) => {
  if (!newStyleName.value.trim()) {
    message.warning('请输入风格名称');
    return;
  }
  
  // Check if name exists
  if (styles.value.includes(newStyleName.value)) {
     message.warning('风格名称已存在，请换一个');
     return;
  }

  isAnalyzing.value = true;
  message.info('开始分析风格，请稍候...');
  
  try {
    const profile = await analyzeStyle(projectStore.currentProject, file, newStyleName.value);
    message.success('风格分析完成！');
    await loadStyles();
    selectStyle(newStyleName.value); // Select the new style
    newStyleName.value = ''; // Reset name
  } catch (e) {
    message.error('分析失败: ' + e.message);
  } finally {
    isAnalyzing.value = false;
  }
};

onMounted(() => {
  loadStyles();
});

onActivated(() => {
  loadStyles();
});

</script>

<style scoped>
.view-container {
  height: 100%;
  width: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  background: var(--bg-color);
}

.panel-header {
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--panel-bg);
}

.content-area {
  flex: 1;
  overflow: hidden;
  padding: 24px;
  background-color: var(--bg-color-soft);
}

.style-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 24px;
  height: 100%;
  width: 100%;
  max-width: 1800px;
  margin: 0 auto;
}

.style-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: var(--panel-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-color-soft);
}

.style-main {
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.create-panel, .details-panel, .empty-state {
  height: 100%;
  padding: 32px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  background: var(--panel-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.empty-state {
    justify-content: center;
    align-items: center;
    background: var(--bg-color);
    border: 2px dashed var(--border-color);
}

.panel-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}

.form-group {
  margin-bottom: 24px;
  max-width: 600px;
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
  padding: 60px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: var(--bg-color);
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  max-height: 400px;
}

.upload-zone:hover, .upload-zone.is-dragover {
  border-color: var(--primary-color);
  background: var(--primary-color-alpha-10);
}

.upload-zone.is-analyzing {
  cursor: wait;
  opacity: 0.8;
}

.style-item-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    padding: 4px 0;
}

.active {
    background-color: var(--primary-color-alpha-10);
    color: var(--primary-color);
}

.profile-content {
    display: flex;
    flex-direction: column;
    gap: 32px;
}

.profile-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
    gap: 24px;
}

.profile-section {
    background: var(--bg-color);
    padding: 24px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.profile-section h4 {
    margin-bottom: 12px;
    color: var(--primary-color);
    font-size: 0.95em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
}

.profile-section p {
    line-height: 1.7;
    color: var(--text-color);
    font-size: 1.05em;
}

.json-section {
    margin-top: 16px;
}

.json-view {
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 16px;
    border-radius: 6px;
    overflow: auto;
    font-family: 'Fira Code', monospace;
    font-size: 13px;
    max-height: 400px;
    line-height: 1.5;
}

.loading-list, .loading-profile {
    display: flex;
    justify-content: center;
    padding: 40px;
}

.empty-list {
    padding: 40px 20px;
    text-align: center;
    color: var(--text-color-secondary);
}
</style>
