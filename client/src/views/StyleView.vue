<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header">
      <h2>Style Agent / 风格提取</h2>
      <div class="toolbar">
        <AiSettingsPanel :visible="true" compact />
      </div>
    </div>
    <div class="content-area">
      <div class="style-grid">
        <!-- Current Style Card -->
        <div class="spark-card style-profile-card">
          <h3>当前风格档案</h3>
          <div v-if="isLoadingProfile" class="loading">
            <n-spin size="small" /> Loading...
          </div>
          <div v-else-if="currentProfile" class="profile-content">
            <div class="profile-section">
              <h4>Narrative Voice</h4>
              <p>{{ currentProfile.narrative_voice?.description || 'N/A' }}</p>
            </div>
            <div class="profile-section">
              <h4>Pacing</h4>
              <p>{{ currentProfile.pacing?.description || 'N/A' }}</p>
            </div>
            <div class="profile-section">
              <h4>Dialogue Style</h4>
              <p>{{ currentProfile.dialogue_style?.description || 'N/A' }}</p>
            </div>
            <n-button size="small" secondary class="view-json-btn" @click="showJson = !showJson">
              {{ showJson ? 'Hide JSON' : 'View Full JSON' }}
            </n-button>
            <pre v-if="showJson" class="json-view">{{ JSON.stringify(currentProfile, null, 2) }}</pre>
          </div>
          <div v-else class="empty-profile">
            <p>No style profile found for this project.</p>
            <p class="sub">Upload a text/epub file to analyze.</p>
          </div>
        </div>

        <!-- Upload Zone -->
        <div 
          class="spark-card upload-zone" 
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
            <p>Analyzing Style... This may take a while.</p>
          </template>
          <template v-else>
            <n-icon size="48"><CloudUploadOutline /></n-icon>
            <p>拖入文本文件 (.txt, .epub) 以分析风格</p>
            <p class="sub">Click to browse</p>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onActivated } from 'vue';
import { NIcon, NSpin, NButton, useMessage } from 'naive-ui';
import { CloudUploadOutline } from '@vicons/ionicons5';
import { analyzeStyle, getStyleProfile } from '../services/api';
import { useProjectStore } from '../components/stores/projectStore';
import AiSettingsPanel from '../components/lorebook/AiSettingsPanel.vue';

const projectStore = useProjectStore();
const message = useMessage();

const currentProfile = ref(null);
const isLoadingProfile = ref(false);
const isAnalyzing = ref(false);
const isDragOver = ref(false);
const showJson = ref(false);
const fileInput = ref(null);

onMounted(async () => {
  await loadProfile();
});

onActivated(async () => {
  if (!isAnalyzing.value) {
    await loadProfile();
  }
});

async function loadProfile() {
  if (!projectStore.currentProject) return;
  isLoadingProfile.value = true;
  try {
    const profile = await getStyleProfile(projectStore.currentProject);
    currentProfile.value = profile;
  } catch (e) {
    // Ignore 404
    console.log('No profile loaded:', e.message);
  } finally {
    isLoadingProfile.value = false;
  }
}

function triggerFileInput() {
  if (!isAnalyzing.value) {
    fileInput.value.click();
  }
}

function handleFileChange(e) {
  const file = e.target.files[0];
  if (file) processFile(file);
}

function handleDrop(e) {
  isDragOver.value = false;
  const file = e.dataTransfer.files[0];
  if (file) processFile(file);
}

async function processFile(file) {
  if (isAnalyzing.value) return;
  
  isAnalyzing.value = true;
  message.info('Starting style analysis...');
  
  try {
    const profile = await analyzeStyle(projectStore.currentProject, file);
    currentProfile.value = profile;
    message.success('Style analysis complete!');
  } catch (e) {
    message.error('Analysis failed: ' + e.message);
  } finally {
    isAnalyzing.value = false;
    // Reset input
    if (fileInput.value) fileInput.value.value = '';
  }
}
</script>

<style scoped>
.view-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--spark-bg);
}

.panel-header {
  height: 50px;
  border-bottom: 1px solid var(--spark-border);
  display: flex;
  align-items: center;
  padding: 0 20px;
  background-color: var(--spark-panel-bg);
}

.content-area {
  padding: 20px;
  overflow-y: auto;
}

.style-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 20px;
}

.style-profile-card {
  min-height: 300px;
  display: flex;
  flex-direction: column;
}

.profile-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
}

.profile-section h4 {
  color: var(--spark-primary);
  margin-bottom: 4px;
  font-size: 0.9rem;
  text-transform: uppercase;
}

.profile-section p {
  color: var(--spark-text);
  font-size: 0.95rem;
  line-height: 1.5;
}

.json-view {
  background: rgba(0,0,0,0.3);
  padding: 10px;
  border-radius: 4px;
  font-size: 0.8rem;
  max-height: 300px;
  overflow: auto;
}

.upload-zone {
  border: 2px dashed var(--spark-border);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  cursor: pointer;
  color: var(--spark-text-muted);
  transition: all 0.2s;
  gap: 12px;
}

.upload-zone:hover, .upload-zone.is-dragover {
  border-color: var(--spark-primary);
  color: var(--spark-primary);
  background-color: rgba(242, 204, 96, 0.05);
}

.upload-zone.is-analyzing {
  cursor: wait;
  border-color: var(--spark-accent);
  color: var(--spark-accent);
}

.sub {
  font-size: 0.8rem;
  opacity: 0.7;
}
</style>
