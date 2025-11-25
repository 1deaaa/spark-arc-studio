<template>
  <div id="ai-screenwriter" class="right-panel-section" v-show="visible">
    <n-card 
      title="AI 编剧" 
      :segmented="{ content: true }" 
      :bordered="false"
      size="small"
    >
      <template #header-extra>
        <n-icon :component="CreateOutline" size="20" />
      </template>

      <n-form label-placement="top" size="medium">
        <!-- 模式选择 -->
        <n-form-item label="模式">
          <n-select 
            v-model:value="mode" 
            id="ai-mode-select" 
            placeholder="选择生成模式"
            :options="modeOptions"
          />
        </n-form-item>

        <!-- 单段续写控件 -->
        <div v-show="mode === 'single-node'" class="mode-content">
          <n-form-item label="长度">
            <n-input-number 
              id="ai-single-length" 
              v-model:value="singleLength" 
              :min="1" 
              :max="1000"
              style="width: 100%"
            />
          </n-form-item>
          
          <n-button 
            id="ai-generate-single-btn"
            type="primary" 
            :disabled="disableGenerate" 
            :loading="generating"
            @click="handleSingleNode"
            block
            strong
          >
            <template #icon>
              <n-icon :component="FlashOutline" />
            </template>
            {{ generating ? '生成中...' : '生成' }}
          </n-button>
        </div>

        <!-- 多段续写控件 -->
        <div v-show="mode === 'multi-node'" class="mode-content">
          <n-form-item label="引导提示">
            <n-input 
              id="ai-multi-prompt"
              v-model:value="multiPrompt" 
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 6 }"
              placeholder="给 AI 的额外指示..."
            />
          </n-form-item>

          <n-form-item label="段数">
            <n-input-number 
              id="ai-multi-segments"
              v-model:value="multiSegments" 
              :min="1" 
              :max="10"
              style="width: 100%"
            />
          </n-form-item>

          <n-form-item label="参与角色（1-4）">
            <n-select 
              id="ai-multi-chars"
              v-model:value="selectedCharacterIds" 
              multiple
              placeholder="选择参与角色"
              :options="characterOptions"
              filterable
            />
          </n-form-item>

          <n-button 
            id="ai-generate-multi-btn"
            type="primary" 
            :disabled="disableGenerate || selectedCharacterIds.length === 0 || selectedCharacterIds.length > 4" 
            :loading="generating"
            @click="handleMultiNode"
            block
            strong
          >
            <template #icon>
              <n-icon :component="FlashOutline" />
            </template>
            {{ generating ? '生成中...' : '生成' }}
          </n-button>
        </div>
      </n-form>
    </n-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { NCard, NForm, NFormItem, NSelect, NInputNumber, NButton, NInput, NIcon } from 'naive-ui';
import { CreateOutline, FlashOutline, DocumentTextOutline, DocumentsOutline, PersonOutline } from '@vicons/ionicons5';
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

// 模式选项
const modeOptions = [
  { label: '单段续写', value: 'single-node', icon: DocumentTextOutline },
  { label: '多段续写', value: 'multi-node', icon: DocumentsOutline }
];

// 多段续写
const multiPrompt = ref('');
const multiSegments = ref(3);
const characters = ref([]);
const selectedCharacterIds = ref([]);

// 角色选项
const characterOptions = computed(() => 
  characters.value.map(c => ({
    label: c.name || `角色 ${c.id}`,
    value: String(c.id)
  }))
);

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

/* 让 AI 面板占更少空间，给节点编辑器更多空间 */
#ai-screenwriter.right-panel-section {
  flex: 0.6;  /* AI 面板占更少空间 */
}

.mode-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>