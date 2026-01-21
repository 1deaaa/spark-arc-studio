<template>
  <div class="production-mobile">
    <div class="mobile-section">
      <h3 class="section-title">
        <n-icon :component="CreateOutline" />
        剧本创作
      </h3>
      <p class="section-desc">当前项目的场景与对话概览</p>
    </div>
    
    <n-spin :show="loading">
      <!-- 项目信息卡片 -->
      <div class="project-card" v-if="currentFile">
        <div class="project-icon">
          <n-icon :component="DocumentTextOutline" size="24" />
        </div>
        <div class="project-info">
          <div class="project-name">{{ currentFile }}</div>
          <div class="project-meta">{{ sceneCount }} 个场景 · {{ totalDialogues }} 个对话节点</div>
        </div>
      </div>
      
      <!-- 场景快速预览 -->
      <div class="scene-preview" v-if="scenes.length > 0">
        <h4 class="preview-title">场景预览</h4>
        <div class="preview-list">
          <div 
            v-for="scene in scenes.slice(0, 5)" 
            :key="scene.scene"
            class="preview-item"
          >
            <span class="preview-name">{{ scene.scene }}</span>
            <span class="preview-count">{{ scene.dialogues?.length || 0 }} 对话</span>
          </div>
          <div v-if="scenes.length > 5" class="preview-more">
            还有 {{ scenes.length - 5 }} 个场景...
          </div>
        </div>
      </div>
      
      <n-empty v-else description="尚未创建任何场景" style="padding: 40px 0;" />
    </n-spin>
    
    <!-- 功能入口 -->
    <div class="action-grid">
      <div class="action-card" @click="openAiChat">
        <div class="action-icon ai">
          <n-icon :component="SparklesOutline" size="24" />
        </div>
        <div class="action-text">
          <div class="action-title">AI 助写</div>
          <div class="action-desc">对话式生成内容</div>
        </div>
      </div>
      
      <div class="action-card disabled">
        <div class="action-icon">
          <n-icon :component="DesktopOutline" size="24" />
        </div>
        <div class="action-text">
          <div class="action-title">完整编辑</div>
          <div class="action-desc">请使用桌面端</div>
        </div>
      </div>
    </div>
    
    <div class="desktop-notice">
      <n-icon :component="InformationCircleOutline" size="18" />
      <p>对话树节点编辑器需要较大屏幕空间，建议在电脑端进行完整创作。移动端可通过 AI 助写快速生成内容。</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, inject, watch } from 'vue';
import { NIcon, NSpin, NEmpty } from 'naive-ui';
import { 
  CreateOutline, 
  DocumentTextOutline, 
  SparklesOutline, 
  DesktopOutline,
  InformationCircleOutline
} from '@vicons/ionicons5';
import { useSceneStore } from '../../components/stores/sceneStore';
import { useFileStore } from '../../components/stores/fileStore';
import bus from '../../eventBus';

const sceneStore = useSceneStore();
const fileStore = useFileStore();
const projectId = inject('projectId', ref(null));

const loading = ref(false);
const currentFile = computed(() => fileStore.currentFile);
const scenes = computed(() => sceneStore.scriptData || []);
const sceneCount = computed(() => scenes.value.length);
const totalDialogues = computed(() => {
  return scenes.value.reduce((sum, s) => sum + (s.dialogues?.length || 0), 0);
});

function openAiChat() {
  // 触发全局 AI 聊天面板展开
  bus.emit('open-global-chat');
}

async function loadData() {
  if (!projectId.value) return;
  loading.value = true;
  try {
    await fileStore.loadFileTree(projectId.value);
  } finally {
    loading.value = false;
  }
}

onMounted(loadData);
watch(projectId, loadData);
</script>

<style scoped>
.production-mobile {
  padding: 0 4px;
}

.mobile-section {
  margin-bottom: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--spark-primary);
  margin: 0 0 8px 0;
}

.section-desc {
  font-size: 13px;
  color: var(--spark-text-muted);
  margin: 0;
}

.project-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  background: linear-gradient(135deg, 
    rgba(var(--spark-primary-rgb), 0.1),
    rgba(var(--spark-primary-rgb), 0.05)
  );
  border: 1px solid rgba(var(--spark-primary-rgb), 0.2);
  border-radius: 12px;
  margin-bottom: 20px;
}

.project-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: var(--spark-primary);
  color: var(--spark-text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
}

.project-info {
  flex: 1;
  min-width: 0;
}

.project-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--spark-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.project-meta {
  font-size: 13px;
  color: var(--spark-text-muted);
  margin-top: 4px;
}

.scene-preview {
  margin-bottom: 20px;
}

.preview-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--spark-text-muted);
  margin: 0 0 10px 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.preview-list {
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 10px;
  overflow: hidden;
}

.preview-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid var(--spark-border);
}

.preview-item:last-child {
  border-bottom: none;
}

.preview-name {
  font-size: 14px;
  color: var(--spark-text);
}

.preview-count {
  font-size: 12px;
  color: var(--spark-text-muted);
}

.preview-more {
  padding: 10px 14px;
  font-size: 13px;
  color: var(--spark-primary);
  text-align: center;
  background: rgba(var(--spark-primary-rgb), 0.05);
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.action-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 20px 16px;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-card:active:not(.disabled) {
  transform: scale(0.97);
  background: rgba(var(--spark-primary-rgb), 0.05);
}

.action-card.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.action-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: var(--spark-border);
  color: var(--spark-text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-icon.ai {
  background: linear-gradient(135deg, #8B5CF6, #EC4899);
  color: white;
}

.action-text {
  text-align: center;
}

.action-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--spark-text);
}

.action-desc {
  font-size: 12px;
  color: var(--spark-text-muted);
  margin-top: 2px;
}

.desktop-notice {
  display: flex;
  gap: 10px;
  padding: 14px;
  background: rgba(var(--spark-primary-rgb), 0.06);
  border: 1px solid rgba(var(--spark-primary-rgb), 0.15);
  border-radius: 10px;
  color: var(--spark-text-muted);
}

.desktop-notice p {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
}
</style>
