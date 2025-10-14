<template>
  <div id="ai-screenwriter" class="right-panel-section" v-show="visible">
    <el-card shadow="hover" :body-style="{ padding: '16px' }">
      <template #header>
        <div class="card-header">
          <el-icon><EditPen /></el-icon>
          <span>AI 编剧</span>
        </div>
      </template>

      <el-form label-position="top" size="default">
        <!-- 模式选择 -->
        <el-form-item label="模式">
          <el-select v-model="mode" id="ai-mode-select" placeholder="选择生成模式" style="width: 100%">
            <el-option value="single-node" label="单段续写">
              <el-icon><Document /></el-icon>
              <span style="margin-left: 8px">单段续写</span>
            </el-option>
            <el-option value="multi-node" label="多段续写">
              <el-icon><DocumentCopy /></el-icon>
              <span style="margin-left: 8px">多段续写</span>
            </el-option>
          </el-select>
        </el-form-item>

        <!-- 单段续写控件 -->
        <div v-show="mode === 'single-node'">
          <el-form-item label="长度">
            <el-input-number 
              id="ai-single-length" 
              v-model="singleLength" 
              :min="1" 
              :max="1000"
              controls-position="right"
              style="width: 100%"
            />
          </el-form-item>
          <el-button 
            id="ai-generate-single-btn"
            type="primary" 
            :disabled="disableGenerate" 
            :loading="generating"
            @click="handleSingleNode"
            style="width: 100%"
          >
            <el-icon v-if="!generating"><MagicStick /></el-icon>
            {{ generating ? '生成中...' : '生成' }}
          </el-button>
        </div>

        <!-- 多段续写控件 -->
        <div v-show="mode === 'multi-node'">
          <el-form-item label="引导提示">
            <el-input 
              id="ai-multi-prompt"
              v-model="multiPrompt" 
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 6 }"
              placeholder="给 AI 的额外指示..."
            />
          </el-form-item>

          <el-form-item label="段数">
            <el-input-number 
              id="ai-multi-segments"
              v-model="multiSegments" 
              :min="1" 
              :max="10"
              controls-position="right"
              style="width: 100%"
            />
          </el-form-item>

          <el-form-item label="参与角色（1-4）">
            <el-select 
              id="ai-multi-chars"
              v-model="selectedCharacterIds" 
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="选择参与角色"
              style="width: 100%"
            >
              <el-option 
                v-for="c in characters" 
                :key="c.id" 
                :value="String(c.id)"
                :label="c.name || ('角色 ' + c.id)"
              >
                <el-icon><Avatar /></el-icon>
                <span style="margin-left: 8px">{{ c.name || ('角色 ' + c.id) }}</span>
              </el-option>
            </el-select>
          </el-form-item>

          <el-button 
            id="ai-generate-multi-btn"
            type="primary" 
            :disabled="disableGenerate || selectedCharacterIds.length === 0 || selectedCharacterIds.length > 4" 
            :loading="generating"
            @click="handleMultiNode"
            style="width: 100%"
          >
            <el-icon v-if="!generating"><MagicStick /></el-icon>
            {{ generating ? '生成中...' : '生成' }}
          </el-button>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import bus from '@/eventBus';
import { useSceneStore } from '@/components/stores/sceneStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { useFileStore } from '@/components/stores/fileStore';
import { fetchWithAuth } from '@/services/api';

const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();

const visible = computed(() => sceneStore.selectionType === 'dialogue');
const mode = ref('single-node');
const singleLength = ref(50);
const generating = ref(false);
const disableGenerate = computed(() => generating.value || !sceneStore.currentNode || sceneStore.selectionType !== 'dialogue');

// 多段续写
const multiPrompt = ref('');
const multiSegments = ref(3);
const characters = ref([]);
const selectedCharacterIds = ref([]);

async function loadCharacters() {
  if (!projectStore.currentProject) return;
  try {
    const res = await fetchWithAuth(`/api/character-settings/${projectStore.currentProject}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    characters.value = await res.json();
  } catch (e) {
    characters.value = [];
  }
}

onMounted(() => {
  loadCharacters();
});
watch(() => projectStore.currentProject, () => loadCharacters());

async function handleSingleNode() {
  if (!sceneStore.currentNode || sceneStore.selectionType !== 'dialogue') return;
  generating.value = true;
  try {
    const context = sceneStore.currentNode.txt || '';
    const res = await fetchWithAuth('/api/ai/single-node', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        projectName: projectStore.currentProject,
        context,
        length: Number(singleLength.value) || 50,
        character_ids: [Number(sceneStore.currentNode.chr) || 0]
      })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const reader = res.body?.getReader?.();
    if (reader) {
      const decoder = new TextDecoder();
      // 逐块读取并追加到对话编辑器文本框（不直接修改树）
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        bus.emit('ai-append-text', { chunk });
      }
    } else {
      // 非流式回退：一次性追加到文本框
      const text = await res.text();
      bus.emit('ai-append-text', { chunk: text });
    }
  } catch (e) {
    bus.emit('toast', { type: 'error', message: 'AI 单段续写失败' });
  } finally {
    generating.value = false;
  }
}

async function handleMultiNode() {
  if (!sceneStore.currentNode || sceneStore.selectionType !== 'dialogue') return;
  if (selectedCharacterIds.value.length === 0 || selectedCharacterIds.value.length > 4) {
    bus.emit('toast', { type: 'error', message: '请选择 1 到 4 个参与角色' });
    return;
  }
  generating.value = true;
  try {
    const context = `场景: ${sceneStore.currentScene?.scene}\n当前对话ID: ${sceneStore.currentNode.id}\n对话内容: ${sceneStore.currentNode.txt || ''}`;
    const payload = {
      projectName: projectStore.currentProject,
      context,
      guidance: multiPrompt.value,
      character_ids: selectedCharacterIds.value.map((v) => Number(v)).filter((n) => !Number.isNaN(n)),
      segment_count: Number(multiSegments.value) || 3,
      current_file: fileStore.selectedFile?.path || '',
      scene_name: sceneStore.currentScene?.scene || '',
      after_node_id: sceneStore.currentNode.id
    };
    const res = await fetchWithAuth('/api/ai/multi-node', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const result = await res.json();
    if (!res.ok) throw new Error(result?.error || `HTTP ${res.status}`);
  // 后续用 toast 提示
    // 刷新当前故事文件
    if (fileStore.selectedFile?.path) {
      // 复用 sceneStore.loadStory 以重新加载
      await sceneStore.loadStory(fileStore.selectedFile.path);
    }
  } catch (e) {
    bus.emit('toast', { type: 'error', message: 'AI 多段续写失败' });
  } finally {
    generating.value = false;
  }
}
</script>

<style scoped>
.right-panel-section {
  padding: 0;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 16px;
  color: #409eff;
}
:deep(.el-form-item) {
  margin-bottom: 16px;
}
:deep(.el-form-item__label) {
  font-weight: 500;
  color: #606266;
}
</style>