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

          <n-form-item label="段数 (0为无限)">
            <n-input-number
              id="ai-multi-segments"
              v-model:value="multiSegments"
              :min="0"
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

        <!-- 场景衔接控件 (Bridge) -->
        <div v-show="mode === 'bridge'" class="mode-content">
          <n-form-item label="前一场景">
            <n-select 
              v-model:value="bridgePrevScene"
              placeholder="选择前一场景"
              :options="sceneOptions"
              filterable
            />
          </n-form-item>

          <n-form-item label="后一场景">
            <n-select 
              v-model:value="bridgeNextScene"
              placeholder="选择后一场景"
              :options="sceneOptions"
              filterable
            />
          </n-form-item>

          <n-form-item label="节奏">
            <n-select 
              v-model:value="bridgePacing"
              :options="pacingOptions"
            />
          </n-form-item>

          <n-form-item label="用户指导（可选）">
            <n-input 
              v-model:value="bridgeGuidance" 
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 4 }"
              placeholder="例如：增加悬念、使用特定角色对话..."
            />
          </n-form-item>

          <n-button 
            type="primary" 
            :disabled="!canGenerateBridge" 
            :loading="generating"
            @click="handleBridge"
            block
            strong
          >
            <template #icon>
              <n-icon :component="GitBranchOutline" />
            </template>
            {{ generating ? '生成中...' : '生成过渡对话' }}
          </n-button>

          <!-- 生成结果预览 -->
          <div v-if="bridgeResult.length > 0" class="bridge-result">
            <n-divider title-placement="left">生成结果</n-divider>
            <div class="bridge-dialogues">
              <div v-for="(d, idx) in bridgeResult" :key="idx" class="bridge-dialogue-item">
                <n-tag :type="d.chr === 0 ? 'default' : 'info'" size="small">
                  {{ chrName(d.chr) }}
                </n-tag>
                <span class="dialogue-text">{{ d.txt }}</span>
              </div>
            </div>
            <n-space justify="end" style="margin-top: 12px;">
              <n-button @click="bridgeResult = []" secondary size="small">清除</n-button>
              <n-button type="primary" @click="insertBridgeResult" size="small">插入到场景</n-button>
            </n-space>
          </div>
        </div>
      </n-form>
    </n-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { NCard, NForm, NFormItem, NSelect, NInputNumber, NButton, NInput, NIcon, NSpace, NTag, NDivider, useDialog } from 'naive-ui';
import { CreateOutline, FlashOutline, DocumentTextOutline, DocumentsOutline, PersonOutline, GitBranchOutline } from '@vicons/ionicons5';
import bus from '@/eventBus';
import { useSceneStore } from '@/components/stores/sceneStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { useFileStore } from '@/components/stores/fileStore';
import { useCharacterStore } from '@/components/stores/characterStore';
import { fetchWithAuth, generateBridge } from '@/services/api';

const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const characterStore = useCharacterStore();
const dialog = useDialog();

const visible = computed(() => sceneStore.selectionType === 'dialogue' || mode.value === 'bridge');
const mode = ref('single-node');
const singleLength = ref(50);
const generating = ref(false);
const disableGenerate = computed(() => generating.value || !sceneStore.currentNode || sceneStore.selectionType !== 'dialogue');

// 模式选项
const modeOptions = [
  { label: '单段续写', value: 'single-node', icon: DocumentTextOutline },
  { label: '多段续写', value: 'multi-node', icon: DocumentsOutline },
  { label: '场景过渡', value: 'bridge', icon: GitBranchOutline }
];

// 多段续写
const multiPrompt = ref('');
const multiSegments = ref(3);
const characters = ref([]);
const selectedCharacterIds = ref([]);
let abortController = null;

// Bridge 场景过渡
const bridgePrevScene = ref(null);
const bridgeNextScene = ref(null);
const bridgePacing = ref('Normal');
const bridgeGuidance = ref('');
const bridgeResult = ref([]);

const pacingOptions = [
  { label: '慢节奏 (Slow)', value: 'Slow' },
  { label: '正常节奏 (Normal)', value: 'Normal' },
  { label: '快节奏 (Fast)', value: 'Fast' }
];

// 场景选项
const sceneOptions = computed(() => {
  const scenes = sceneStore.scriptData || [];
  return scenes.map((s, idx) => ({
    label: s.scene || `场景 ${idx + 1}`,
    value: s.scene
  }));
});

// 是否可以生成过渡
const canGenerateBridge = computed(() => {
  return !generating.value && 
         bridgePrevScene.value && 
         bridgeNextScene.value && 
         bridgePrevScene.value !== bridgeNextScene.value;
});

// 将角色ID映射为名称
function chrName(id) {
  if (id === -1) return '旁白';
  const name = characterStore.map?.[Number(id)];
  return name ?? `角色 ${id}`;
}

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

// 监听外部触发的 Bridge 请求（从蓝图连线）
bus.on('trigger-bridge', ({ prevScene, nextScene }) => {
  mode.value = 'bridge';
  bridgePrevScene.value = prevScene;
  bridgeNextScene.value = nextScene;
});

// 监听取消生成事件
bus.on('cancel-loading', () => {
  if (abortController) {
    abortController.abort();
    abortController = null;
    generating.value = false;
    bus.emit('global-loading', false);
    bus.emit('toast', { type: 'info', message: '已取消生成' });
  }
});

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
  abortController = new AbortController();
  bus.emit('global-loading', { show: true, text: 'AI 正在构思剧情...', canCancel: true });
  
  try {
    const context = `场景: ${sceneStore.currentScene?.scene}\n当前对话ID: ${sceneStore.currentNode.id}\n对话内容: ${sceneStore.currentNode.txt || ''}`;
    const payload = {
      projectName: projectStore.currentProject,
      context,
      guidance: multiPrompt.value,
      character_ids: selectedCharacterIds.value.map((v) => Number(v)).filter((n) => !Number.isNaN(n)),
      segment_count: Number(multiSegments.value), // 允许为 0
      current_file: fileStore.selectedFile?.path || '',
      scene_name: sceneStore.currentScene?.scene || '',
      after_node_id: sceneStore.currentNode.id
    };
    
    let res = await fetchWithAuth('/api/ai/multi-node', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: abortController.signal
    });

    // 处理 409 缺失信息确认
    if (res.status === 409) {
      const errorData = await res.json();
      
      // 暂时隐藏 Loading 以显示对话框
      bus.emit('global-loading', false);

      // 使用 Naive UI 的 Dialog
      return new Promise((resolve) => {
        dialog.warning({
          title: '信息缺失',
          content: errorData.message || '检测到缺失信息，是否继续？',
          positiveText: '继续生成',
          negativeText: '取消',
          onPositiveClick: async () => {
            try {
              // 重新显示 Loading
              bus.emit('global-loading', { show: true, text: 'AI 正在强制生成...', canCancel: true });
              
              // 用户确认继续，重新发送请求
              payload.confirm_continue = true;
              // 重新创建 abortController，因为之前的可能已经被 abort 了（虽然这里是用户确认继续，但逻辑上是新的请求）
              abortController = new AbortController();
              
              const currentSceneName = sceneStore.currentScene?.scene;
              const currentNodeId = sceneStore.currentNode?.id;

              res = await fetchWithAuth('/api/ai/multi-node', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                signal: abortController.signal
              });
              
              const result = await res.json();
              if (!res.ok) throw new Error(result?.error || `HTTP ${res.status}`);
              
              bus.emit('toast', { type: 'success', message: 'AI 续写完成' });
              if (fileStore.selectedFile?.path) {
                await sceneStore.loadStory(fileStore.selectedFile.path);

                // 恢复场景和节点选择
                if (currentSceneName) {
                  const scene = (sceneStore.scriptData || []).find(s => s.scene === currentSceneName);
                  if (scene) {
                    sceneStore.selectScene(scene);
                    if (currentNodeId) {
                      const findNode = (nodes) => {
                        for (const n of nodes) {
                          if (n.id === currentNodeId) return n;
                          if (n.opt) {
                            for (const o of n.opt) {
                              const found = findNode(o.dia || []);
                              if (found) return found;
                            }
                          }
                        }
                        return null;
                      };
                      const node = findNode(scene.dia || []);
                      if (node) {
                        sceneStore.selectDialogue(node);
                      }
                    }
                  }
                }
              }
            } catch (e) {
              if (e.name === 'AbortError') return;
              bus.emit('toast', { type: 'error', message: e.message || 'AI 多段续写失败' });
            } finally {
              generating.value = false;
              bus.emit('global-loading', false);
              abortController = null;
              resolve();
            }
          },
          onNegativeClick: () => {
            generating.value = false;
            resolve();
          }
        });
      });
    }

    const result = await res.json();
    if (!res.ok) throw new Error(result?.error || `HTTP ${res.status}`);
    
    // 成功提示
    bus.emit('toast', { type: 'success', message: 'AI 续写完成' });

    // 刷新当前故事文件
    if (fileStore.selectedFile?.path) {
      const currentSceneName = sceneStore.currentScene?.scene;
      const currentNodeId = sceneStore.currentNode?.id;

      // 复用 sceneStore.loadStory 以重新加载
      await sceneStore.loadStory(fileStore.selectedFile.path);

      // 恢复场景和节点选择
      if (currentSceneName) {
        const scene = (sceneStore.scriptData || []).find(s => s.scene === currentSceneName);
        if (scene) {
          sceneStore.selectScene(scene);
          if (currentNodeId) {
            // 递归查找节点
            const findNode = (nodes) => {
              for (const n of nodes) {
                if (n.id === currentNodeId) return n;
                if (n.opt) {
                  for (const o of n.opt) {
                    const found = findNode(o.dia || []);
                    if (found) return found;
                  }
                }
              }
              return null;
            };
            const node = findNode(scene.dia || []);
            if (node) {
              sceneStore.selectDialogue(node);
            }
          }
        }
      }
    }
  } catch (e) {
    if (e.name === 'AbortError') return;
    bus.emit('toast', { type: 'error', message: e.message || 'AI 多段续写失败' });
  } finally {
    generating.value = false;
    bus.emit('global-loading', false);
    abortController = null;
  }
}
async function handleBridge() {
  if (!canGenerateBridge.value) return;
  generating.value = true;
  bridgeResult.value = [];
  
  try {
    const scenes = sceneStore.scriptData || [];
    const prevSceneData = scenes.find(s => s.scene === bridgePrevScene.value);
    const nextSceneData = scenes.find(s => s.scene === bridgeNextScene.value);
    
    if (!prevSceneData || !nextSceneData) {
      throw new Error('找不到指定场景');
    }
    
    // 构建场景摘要
    const prevScene = {
      id: bridgePrevScene.value,
      title: prevSceneData.scene,
      summary: prevSceneData.cap || extractSummary(prevSceneData)
    };
    
    const nextScene = {
      id: bridgeNextScene.value,
      title: nextSceneData.scene,
      summary: nextSceneData.cap || extractSummary(nextSceneData)
    };
    
    const dialogues = await generateBridge(
      projectStore.currentProject,
      prevScene,
      nextScene,
      {
        pacing: bridgePacing.value,
        guidance: bridgeGuidance.value
      }
    );
    
    bridgeResult.value = dialogues || [];
    
    if (bridgeResult.value.length > 0) {
      bus.emit('toast', { type: 'success', message: `生成了 ${bridgeResult.value.length} 条过渡对话` });
    } else {
      bus.emit('toast', { type: 'warning', message: '未生成任何对话' });
    }
  } catch (e) {
    console.error('Bridge generation failed:', e);
    bus.emit('toast', { type: 'error', message: e.message || '生成过渡对话失败' });
  } finally {
    generating.value = false;
  }
}

// 从场景数据中提取摘要
function extractSummary(sceneData) {
  if (!sceneData?.dia?.length) return '(空场景)';
  const firstFew = sceneData.dia.slice(0, 3);
  return firstFew.map(d => `${chrName(d.chr)}: ${(d.txt || '').slice(0, 50)}...`).join(' | ');
}

// 将生成结果插入到场景
function insertBridgeResult() {
  if (!bridgeResult.value.length) return;
  
  // 查找目标场景（插入到 nextScene 的开头）
  const scenes = sceneStore.scriptData || [];
  const targetScene = scenes.find(s => s.scene === bridgeNextScene.value);
  
  if (!targetScene) {
    bus.emit('toast', { type: 'error', message: '找不到目标场景' });
    return;
  }
  
  // 生成新的对话节点 ID
  let maxId = 0;
  scenes.forEach(s => {
    (s.dia || []).forEach(d => {
      if (d.id > maxId) maxId = d.id;
    });
  });
  
  // 构建新对话节点
  const newNodes = bridgeResult.value.map((d, idx) => ({
    id: maxId + idx + 1,
    chr: d.chr,
    txt: d.txt
  }));
  
  // 插入到场景开头
  if (!targetScene.dia) targetScene.dia = [];
  targetScene.dia.unshift(...newNodes);
  
  // 保存
  sceneStore._saveStory?.();
  
  bus.emit('toast', { type: 'success', message: `已插入 ${newNodes.length} 条对话到「${targetScene.scene}」` });
  bridgeResult.value = [];
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

/* Bridge 结果样式 */
.bridge-result {
  margin-top: 16px;
}

.bridge-dialogues {
  max-height: 200px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bridge-dialogue-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  background: var(--spark-bg);
  border-radius: 4px;
  border-left: 3px solid var(--node-dialogue);
}

.bridge-dialogue-item .dialogue-text {
  flex: 1;
  font-size: 13px;
  line-height: 1.4;
  color: var(--spark-text);
}
</style>