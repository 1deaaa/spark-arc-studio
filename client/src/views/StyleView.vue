<template>
  <div class="view-container spark-anim-fade">
    <!-- Header Section -->
    <div class="view-header">
      <div class="header-left">
        <h2>Style Agent / 风格管理</h2>
        <p class="subtitle">管理和应用您的写作风格模型，让 AI 学习特定的叙事声音。</p>
      </div>
      <div class="header-right">
        <AiSettingsPanel :visible="true" compact />
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
          
          <!-- New Format -->
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

          <!-- Legacy Format Fallback -->
          <template v-else>
            <div class="profile-section-card">
              <div class="section-header">
                <n-icon color="#2080f0"><mic-outline /></n-icon>
                <h4>Narrative Voice / 叙事声音</h4>
              </div>
              <p>{{ currentProfile.narrative_voice?.description || 'N/A' }}</p>
            </div>

            <div class="profile-section-card">
              <div class="section-header">
                <n-icon color="#18a058"><speedometer-outline /></n-icon>
                <h4>Pacing / 节奏</h4>
              </div>
              <p>{{ currentProfile.pacing?.description || 'N/A' }}</p>
            </div>

            <div class="profile-section-card">
              <div class="section-header">
                <n-icon color="#f0a020"><chatbubbles-outline /></n-icon>
                <h4>Dialogue Style / 对话风格</h4>
              </div>
              <p>{{ currentProfile.dialogue_style?.description || 'N/A' }}</p>
            </div>

            <div class="profile-section-card">
              <div class="section-header">
                <n-icon color="#d03050"><musical-notes-outline /></n-icon>
                <h4>Tone / 基调</h4>
              </div>
              <p>{{ currentProfile.tone?.description || 'N/A' }}</p>
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
import { ref, onMounted, onActivated } from 'vue';
import { 
  NIcon, NSpin, NButton, NInput, NPopconfirm, NEmpty, NCollapse, NCollapseItem,
  NModal, NDrawer, NDrawerContent, useMessage
} from 'naive-ui';
import { 
  CloudUploadOutline, AddOutline, TrashOutline, RefreshOutline, ColorPaletteOutline,
  MicOutline, SpeedometerOutline, ChatbubblesOutline, MusicalNotesOutline,
  BookOutline, LayersOutline, EyeOutline, ImageOutline, SearchOutline, GitNetworkOutline,
  PulseOutline, ChatboxEllipsesOutline
} from '@vicons/ionicons5';
import { analyzeStyle, analyzeStyleStream, getStyles, deleteStyle, applyStyle } from '../services/aiService';
import { getStyleProfile } from '../services/storyService';
import { useProjectStore } from '../components/stores/projectStore';
import AiSettingsPanel from '../components/lorebook/AiSettingsPanel.vue';

const projectStore = useProjectStore();
const message = useMessage();

// State
const styles = ref([]);
const isLoadingList = ref(false);
const showCreateModal = ref(false);
const showDetailsDrawer = ref(false);
const selectedStyleName = ref(null);
const currentProfile = ref(null);
const isLoadingProfile = ref(false);

// Create State
const newStyleName = ref('');
const isAnalyzing = ref(false);
const progressMessage = ref('');
const isDragOver = ref(false);
const fileInput = ref(null);

// Apply State
const isApplying = ref(false);

const sectionMap = {
  inner_monologue: { title: '内心独白 (Inner Monologue)', icon: ChatbubblesOutline },
  emotional_progression: { title: '情感推进 (Emotional Progression)', icon: PulseOutline },
  theme_tendency: { title: '主题倾向 (Theme Tendency)', icon: BookOutline },
  subtext_layer: { title: '潜台词 (Subtext Layer)', icon: LayersOutline },
  dialogue_system: { title: '对话系统 (Dialogue System)', icon: ChatboxEllipsesOutline },
  perspective_system: { title: '视角系统 (Perspective System)', icon: EyeOutline },
  scene_construction: { title: '场景构建 (Scene Construction)', icon: ImageOutline },
  detail_craftsmanship: { title: '细节描写 (Detail Craftsmanship)', icon: SearchOutline },
  structural_breathing: { title: '结构节奏 (Structural Breathing)', icon: GitNetworkOutline }
};

const getSectionTitle = (key) => sectionMap[key]?.title || key;
const getSectionIcon = (key) => sectionMap[key]?.icon || ColorPaletteOutline;

const formatKey = (key) => {
  if (!key || typeof key !== 'string') return String(key);
  return key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
};

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

const openCreateModal = () => {
  newStyleName.value = '';
  showCreateModal.value = true;
};

const openStyleDetails = async (styleName) => {
  selectedStyleName.value = styleName;
  showDetailsDrawer.value = true;
  currentProfile.value = null;
  isLoadingProfile.value = true;
  
  try {
    // Pass styleName to getStyleProfile
    currentProfile.value = await getStyleProfile(null, styleName);
  } catch (e) {
    message.error('加载风格详情失败: ' + e.message);
  } finally {
    isLoadingProfile.value = false;
  }
};

const confirmDelete = (style) => {
    // Wrapper to stop propagation if needed, though @click.stop on button handles it
    handleDelete(style);
};

const handleDelete = async (styleName) => {
  try {
    await deleteStyle(styleName);
    message.success(`已删除风格: ${styleName}`);
    if (selectedStyleName.value === styleName) {
      showDetailsDrawer.value = false;
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
    await applyStyle(projectStore.currentProject, selectedStyleName.value);
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
  progressMessage.value = '正在初始化分析...';
  
  try {
    const profile = await analyzeStyleStream(
      projectStore.currentProject, 
      file, 
      newStyleName.value,
      (data) => {
        if (data.message) {
          progressMessage.value = data.message;
        }
      }
    );
    
    if (!profile) {
        // If stream finished but no profile returned (e.g. error in stream but not thrown)
        // Check if we should throw or if analyzeStyleStream throws on error step
        // My implementation of analyzeStyleStream returns finalProfile if found.
        throw new Error('分析未返回结果');
    }

    message.success('风格分析完成！');
    showCreateModal.value = false;
    await loadStyles();
    openStyleDetails(newStyleName.value); // Select the new style
    newStyleName.value = ''; // Reset name
  } catch (e) {
    message.error('分析失败: ' + e.message);
  } finally {
    isAnalyzing.value = false;
    progressMessage.value = '';
  }
};

// Utility for random gradients
const getGradient = (str) => {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  const c1 = Math.floor(Math.abs(Math.sin(hash) * 16777215) % 16777215).toString(16);
  const c2 = Math.floor(Math.abs(Math.sin(hash + 1) * 16777215) % 16777215).toString(16);
  return `linear-gradient(135deg, #${c1.padStart(6,'0')} 0%, #${c2.padStart(6,'0')} 100%)`;
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

.view-header {
  padding: 24px 32px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--panel-bg);
}

.header-left h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: var(--text-color);
}

.subtitle {
  margin: 4px 0 0;
  color: var(--text-color-secondary);
  font-size: 14px;
}

.header-right {
  display: flex;
  gap: 12px;
  align-items: center;
}

.style-content {
  flex: 1;
  overflow-y: auto;
  padding: 32px;
  background-color: var(--bg-color-soft);
}

/* Grid Layout */
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

/* Create Modal */
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

/* Profile Details */
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

.profile-section-card p {
  margin: 0;
  line-height: 1.6;
  color: var(--text-color-secondary);
  font-size: 14px;
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
</style>
