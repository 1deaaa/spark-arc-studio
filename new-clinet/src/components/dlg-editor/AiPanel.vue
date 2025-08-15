<template>
  <div id="ai-screenwriter" class="right-panel-section" v-show="visible">
    <div class="toolbar-title">AI 编剧</div>

    <div class="ai-controls">
      <label>模式：</label>
      <select v-model="mode" id="ai-mode-select">
        <option value="single-node">单段续写</option>
        <option value="multi-node">多段续写</option>
      </select>
    </div>

    <!-- 单段续写控件 -->
    <div id="single-node-controls" v-show="mode === 'single-node'" class="ai-section">
      <label for="ai-single-length">长度：</label>
      <input id="ai-single-length" type="number" v-model.number="singleLength" min="1" />
      <button id="ai-generate-single-btn" :disabled="disableGenerate" @click="handleSingleNode">{{ generating ? '生成中...' : '生成' }}</button>
    </div>

    <!-- 多段续写控件 -->
    <div id="multi-node-controls" v-show="mode === 'multi-node'" class="ai-section">
      <label for="ai-multi-prompt">引导提示：</label>
      <textarea id="ai-multi-prompt" rows="3" v-model="multiPrompt" placeholder="给 AI 的额外指示..." />

      <label for="ai-multi-segments">段数：</label>
      <input id="ai-multi-segments" type="number" v-model.number="multiSegments" min="1" max="10" />

      <label for="ai-multi-chars">参与角色（1-4）：</label>
      <select id="ai-multi-chars" v-model="selectedCharacterIds" multiple size="5">
        <option v-for="c in characters" :key="c.id" :value="String(c.id)">{{ c.name || ('角色 ' + c.id) }}</option>
      </select>

      <button id="ai-generate-multi-btn" :disabled="disableGenerate || selectedCharacterIds.length === 0 || selectedCharacterIds.length > 4" @click="handleMultiNode">{{ generating ? '生成中...' : '生成' }}</button>
    </div>
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
.ai-controls, .ai-section { margin: 8px 0; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
textarea { width: 100%; }
select[multiple] { width: 100%; }
.toolbar-title { margin-bottom: 6px; }
</style>