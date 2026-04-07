<template>
  <div class="blueprint-mobile">
    <div class="mobile-section">
      <h3 class="section-title">
        <n-icon :component="GitNetworkOutline" />
        场景概览
      </h3>
      <p class="section-desc">以下是当前文件的场景列表，点击可查看详情。</p>
    </div>
    
    <n-spin :show="loading">
      <div class="scene-list" v-if="scenes.length > 0">
        <div 
          v-for="(scene, index) in scenes" 
          :key="scene.scene"
          class="scene-card"
          @click="viewScene(scene)"
        >
          <div class="scene-index">{{ index + 1 }}</div>
          <div class="scene-info">
            <div class="scene-name">{{ scene.scene }}</div>
            <div class="scene-guide" v-if="scene.guide">{{ scene.guide }}</div>
          </div>
          <n-icon :component="ChevronForward" size="20" class="scene-arrow" />
        </div>
      </div>
      
      <n-empty v-else description="暂无场景数据" style="padding: 40px 0;">
        <template #extra>
          <p class="empty-hint">请先在「剧本创作」中创建场景</p>
        </template>
      </n-empty>
    </n-spin>
    
    <div class="desktop-hint">
      <n-icon :component="DesktopOutline" size="20" />
      <span>完整的节点连接编辑请使用桌面端</span>
    </div>
    
    <!-- 场景详情抽屉 -->
    <n-drawer v-model:show="drawerVisible" placement="bottom" height="70%">
      <n-drawer-content :title="selectedScene?.scene || '场景详情'" closable>
        <div v-if="selectedScene" class="scene-detail">
          <div class="detail-row">
            <label>场景名称</label>
            <span>{{ selectedScene.scene }}</span>
          </div>
          <div class="detail-row" v-if="selectedScene.guide">
            <label>编剧导语</label>
            <p>{{ selectedScene.guide }}</p>
          </div>
          <div class="detail-row">
            <label>对话节点数</label>
            <span>{{ selectedScene.dialogues?.length || 0 }} 个</span>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, inject, watch } from 'vue';
import { NIcon, NSpin, NEmpty, NDrawer, NDrawerContent } from 'naive-ui';
import { GitNetworkOutline, ChevronForward, DesktopOutline } from '@vicons/ionicons5';
import { useSceneStore } from '../../components/stores/sceneStore';

const sceneStore = useSceneStore();
const projectId = inject('projectId', ref(null));

const loading = ref(false);
const scenes = ref([]);
const drawerVisible = ref(false);
const selectedScene = ref(null);

async function loadScenes() {
  if (!projectId.value) return;
  loading.value = true;
  try {
    // 从 sceneStore 获取当前脚本数据
    if (sceneStore.scriptData && Array.isArray(sceneStore.scriptData)) {
      scenes.value = sceneStore.scriptData;
    }
  } finally {
    loading.value = false;
  }
}

function viewScene(scene) {
  selectedScene.value = scene;
  drawerVisible.value = true;
}

onMounted(loadScenes);
watch(projectId, loadScenes);
watch(() => sceneStore.scriptData, () => {
  if (sceneStore.scriptData && Array.isArray(sceneStore.scriptData)) {
    scenes.value = sceneStore.scriptData;
  }
}, { deep: true });
</script>

<style scoped>
.blueprint-mobile {
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

.scene-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.scene-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.scene-card:active {
  transform: scale(0.98);
  background: rgba(var(--spark-primary-rgb), 0.05);
}

.scene-index {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--spark-primary), var(--spark-primary-hover));
  color: var(--spark-text-inverse);
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.scene-info {
  flex: 1;
  min-width: 0;
}

.scene-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--spark-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.scene-guide {
  font-size: 12px;
  color: var(--spark-text-muted);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.scene-arrow {
  color: var(--spark-text-muted);
  flex-shrink: 0;
}

.desktop-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 24px;
  padding: 12px;
  background: rgba(var(--spark-primary-rgb), 0.08);
  border: 1px dashed rgba(var(--spark-primary-rgb), 0.3);
  border-radius: 10px;
  font-size: 13px;
  color: var(--spark-primary);
}

.empty-hint {
  font-size: 13px;
  color: var(--spark-text-muted);
  margin: 8px 0 0 0;
}

.scene-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-row label {
  font-size: 12px;
  font-weight: 500;
  color: var(--spark-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.detail-row span,
.detail-row p {
  font-size: 14px;
  color: var(--spark-text);
  margin: 0;
}
</style>
