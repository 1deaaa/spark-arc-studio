<template>
  <div id="node-editor" class="right-panel-section">
    <n-card 
      :title="title" 
      :segmented="{ content: true }" 
      :bordered="false"
      size="small"
    >
      <template #header-extra>
        <n-icon 
          :component="type === 'scene' ? FilmOutline : type === 'dialogue' ? ChatbubbleEllipsesOutline : type === 'option' ? RadioButtonOnOutline : HelpCircleOutline" 
          size="20" 
        />
      </template>

      <div id="node-editor-content">
        <!-- 场景编辑器 -->
        <n-form v-if="type === 'scene'" label-placement="top" size="medium">
          <n-form-item label="场景名称(scene)">
            <n-input 
              id="scene-name" 
              v-model:value="sceneDraft.scene" 
              @input="applyScene"
              clearable
              placeholder="输入场景名称"
            />
          </n-form-item>

          <n-form-item label="场景引导(任务简介显示 仅游戏开发用)">
            <n-input
              id="scene-guide"
              v-model:value="sceneDraft.guide"
              @input="applyScene"
              clearable
              placeholder="输入场景引导"
            />
          </n-form-item>

          <n-form-item label="场景引言(用于场景描述)">
            <n-input
              id="scene-intro"
              v-model:value="sceneDraft.intro"
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 8 }"
              @input="applyScene"
              placeholder="可选：本场景引言/目标/氛围/铺垫（对应 .arc 的 @intro）"
            />
          </n-form-item>

          <n-space vertical style="width: 100%" :size="8">
            <n-button type="primary" @click="addDialogue" block strong>
              <template #icon>
                <n-icon :component="AddOutline" />
              </template>
              添加对话节点
            </n-button>
            <n-popconfirm 
              @positive-click="deleteScene"
              positive-text="删除"
              negative-text="取消"
            >
              <template #trigger>
                <n-button type="error" block>
                  <template #icon>
                    <n-icon :component="TrashOutline" />
                  </template>
                  删除场景
                </n-button>
              </template>
              <template #default>
                确定要删除这个场景吗？
              </template>
            </n-popconfirm>
          </n-space>
          <n-form-item label="场景思路">
            <n-input
              v-model:value="sceneDraft.thought"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 10 }"
              placeholder="编辑场景思维链..."
              @input="applyScene"
            />
            <div v-if="!sceneDraft.thought && scriptwriterThought" class="thought-hint" style="margin-top: 8px; opacity: 0.8;">
              <n-text depth="3" size="small">最近一次 AI 思维链:</n-text>
              <div style="padding: 8px; background: rgba(0,0,0,0.05); border-radius: 4px; margin-top: 4px; font-size: 12px;">
                <MarkdownRenderer :content="scriptwriterThought" />
              </div>
            </div>
          </n-form-item>
        </n-form>

        <!-- 对话编辑器 -->
        <n-form v-else-if="type === 'dialogue'" label-placement="top" size="medium">
          <n-form-item label="对话ID(id)">
            <n-input id="dialogue-id" :value="String(dialogueDraft.id)" disabled />
          </n-form-item>

          <n-form-item label="角色(chr)">
            <n-select
              id="dialogue-chr"
              v-model:value="dialogueDraft.chr"
              @update:value="applyDialogue"
              placeholder="选择或搜索角色"
              filterable
              :options="characterSelectOptions"
            />
          </n-form-item>

          <n-form-item label="文本(txt)">
            <n-input 
              id="dialogue-txt" 
              v-model:value="dialogueDraft.txt" 
              type="textarea"
              :autosize="{ minRows: 5, maxRows: 12 }"
              @input="applyDialogue" 
              @keydown.enter.prevent="onEnterAddNextDialogue"
              placeholder="输入对话内容，按 Enter 添加下一对话"
            />
          </n-form-item>

          <n-form-item label="跳转(next)">
            <n-select
              id="dialogue-next"
              v-model:value="dialogueDraft.next"
              @update:value="applyDialogue"
              placeholder="选择跳转场景（可清除）"
              filterable
              clearable
              :options="sceneSelectOptions"
            />
          </n-form-item>

          <n-divider />

          <n-space vertical style="width: 100%" :size="8">
            <n-button @click="addOptionToDialogue" block>
              <template #icon>
                <n-icon :component="AddCircleOutline" />
              </template>
              添加选项
            </n-button>
            <n-button @click="addDialogueAfterCurrent" block>
              <template #icon>
                <n-icon :component="ArrowDownOutline" />
              </template>
              添加下一对话
            </n-button>
            <n-popconfirm 
              @positive-click="deleteDialogue"
              positive-text="删除"
              negative-text="取消"
            >
              <template #trigger>
                <n-button type="error" block>
                  <template #icon>
                    <n-icon :component="TrashOutline" />
                  </template>
                  删除对话
                </n-button>
              </template>
              <template #default>
                确定要删除这个对话吗？
              </template>
            </n-popconfirm>
          </n-space>

          <n-divider title-placement="left">行为(act)</n-divider>

          <n-empty v-if="currentActEntries.length === 0" description="暂无行为" size="small" />
          <div v-else class="action-list">
            <n-space vertical style="width: 100%" :size="8">
              <div v-for="([k, v], idx) in currentActEntries" :key="k" class="action-item">
                <n-tag 
                  type="info" 
                  closable 
                  @close="removeAction(k)"
                  size="medium"
                  :bordered="false"
                >
                  <strong>{{ k }}</strong>
                </n-tag>
                <n-input 
                  v-model:value="actionEdits[k]" 
                  @change="onEditActionValue(k)"
                  placeholder="参数/值"
                  size="small"
                />
              </div>
            </n-space>
          </div>

          <n-divider />
          <div class="new-action-form">
            <n-form-item label="添加新行为" size="small">
              <n-input
                ref="newActionKeyInput"
                v-model:value="newActionKey"
                placeholder="函数名 (key)"
                clearable
              />
            </n-form-item>
            <n-form-item size="small">
              <n-input
                v-model:value="newActionValue"
                placeholder="参数/值 (value)"
                clearable
              />
            </n-form-item>
            <n-button type="success" @click="addAction" block strong>
              <template #icon>
                <n-icon :component="AddCircleOutline" />
              </template>
              添加
            </n-button>
          </div>
        </n-form>

        <!-- 选项编辑器 -->
        <n-form v-else-if="type === 'option'" label-placement="top" size="medium">
          <n-form-item label="选项文本(optn)">
            <n-input 
              id="option-text" 
              v-model:value="optionDraft.optn" 
              @input="applyOption"
              clearable
              placeholder="输入选项文本"
            />
          </n-form-item>

          <n-space vertical style="width: 100%" :size="8">
            <n-button type="primary" @click="addDialogueToOption" block strong>
              <template #icon>
                <n-icon :component="AddOutline" />
              </template>
              添加子对话
            </n-button>
            <n-popconfirm 
              @positive-click="deleteOption"
              positive-text="删除"
              negative-text="取消"
            >
              <template #trigger>
                <n-button type="error" block>
                  <template #icon>
                    <n-icon :component="TrashOutline" />
                  </template>
                  删除选项
                </n-button>
              </template>
              <template #default>
                确定要删除这个选项吗？
              </template>
            </n-popconfirm>
          </n-space>
        </n-form>

        <div v-else class="no-selection">
          <n-empty description="请选择一个节点" />
        </div>
      </div>
    </n-card>
  </div>
  
</template>

<script setup>
import { computed, reactive, ref, watch, getCurrentInstance, onMounted, onBeforeUnmount } from 'vue';
import { NCard, NForm, NFormItem, NInput, NSelect, NButton, NIcon, NDivider, NSpace, NPopconfirm, NEmpty, NTag, NCollapse, NCollapseItem, NText } from 'naive-ui';
import { FilmOutline, ChatbubbleEllipsesOutline, RadioButtonOnOutline, HelpCircleOutline, AddOutline, TrashOutline, AddCircleOutline, ArrowDownOutline, PersonOutline, AnalyticsOutline } from '@vicons/ionicons5';
import bus from '@/eventBus';
import { useSceneStore } from '@/components/stores/sceneStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { useFileStore } from '@/components/stores/fileStore';
import { saveStory } from '@/services/api';
import { useCharacterStore } from '@/components/stores/characterStore';
import MarkdownRenderer from '@/components/share/MarkdownRenderer.vue';

const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const characterStore = useCharacterStore();
const characterOptions = computed(() => characterStore.list);

const newActionKeyInput = ref(null);

onMounted(() => {
  bus.on('focus-act-input', () => {
    newActionKeyInput.value?.focus();
  });
});

onBeforeUnmount(() => {
  bus.off('focus-act-input');
});

// 角色选项（Naive UI format）
const characterSelectOptions = computed(() => 
  characterOptions.value.map(c => ({
    label: c.name || `角色 ${c.id}`,
    value: Number(c.id)
  }))
);

// 场景选项（Naive UI format）
const sceneSelectOptions = computed(() => 
  (sceneStore.scriptData || [])
    .map(s => s?.scene)
    .filter(Boolean)
    .map(name => ({ label: name, value: name }))
);
const vm = getCurrentInstance();
const autoSaveEnabled = computed(() => localStorage.getItem('autoSaveEnabled') === 'true');

function cleanStoryDataForSave(story) {
  // Deep copy to avoid mutating the reactive state used by the UI
  const storyCopy = JSON.parse(JSON.stringify(story));
  
  const allowedSceneKeys = new Set(['scene', 'guide', 'intro', 'dia', 'thought']);
  const allowedDialogueKeys = new Set(['id', 'chr', 'txt', 'opt', 'act', 'next', 'thought']);
  const allowedOptionKeys = new Set(['optn', 'dia']);

  function cleanObject(obj, allowedKeys) {
    if (typeof obj !== 'object' || obj === null) return;
    Object.keys(obj).forEach(key => {
      if (!allowedKeys.has(key)) {
        delete obj[key];
      }
    });
  }

  function traverseDialogues(dialogues) {
    if (!Array.isArray(dialogues)) return;
    dialogues.forEach(dia => {
      cleanObject(dia, allowedDialogueKeys);
      if (dia.opt) {
        dia.opt.forEach(option => {
          cleanObject(option, allowedOptionKeys);
          if (option.dia) {
            traverseDialogues(option.dia);
          }
        });
      }
    });
  }

  if (Array.isArray(storyCopy)) {
    storyCopy.forEach(scene => {
      cleanObject(scene, allowedSceneKeys);
      if (scene.dia) {
        traverseDialogues(scene.dia);
      }
    });
  }
  
  return storyCopy;
}

async function maybeAutoSave() {
  if (!autoSaveEnabled.value) return;
  const path = fileStore.selectedFile?.path;
  if (!path || !projectStore.currentProject) return;
  try {
    const cleanedData = cleanStoryDataForSave(sceneStore.scriptData);
    await saveStory(projectStore.currentProject, path, cleanedData);
    bus.emit('saved');
  } catch (e) {
    console.error('Auto save failed:', e);
  }
}

// 简易防抖封装
function useDebounce(fn, delay = 600) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), delay);
  };
}
import { AUTO_SAVE_DEBOUNCE_TIME } from '@/config';

const debouncedAutoSave = useDebounce(maybeAutoSave, AUTO_SAVE_DEBOUNCE_TIME);

const type = computed(() => sceneStore.selectionType);
const title = computed(() => {
  if (type.value === 'scene') return '场景编辑';
  if (type.value === 'dialogue') return '对话编辑';
  if (type.value === 'option') return '选项编辑';
  return '请选择一个节点';
});

const scriptwriterThought = computed(() => (sceneStore.lastScriptwriterThought || '').trim());

// 场景草稿
const sceneDraft = reactive({ scene: '', guide: '', intro: '', thought: '' });
watch([
  () => sceneStore.currentScene,
  () => sceneStore.selectionType
], ([s, t]) => {
  if (!s || t !== 'scene') return;
  sceneDraft.scene = s.scene || '';
  sceneDraft.guide = s.guide || '';
  sceneDraft.intro = s.intro || '';
  sceneDraft.thought = s.thought || '';
}, { immediate: true });

function applyScene() {
  sceneStore.updateCurrentScene({
    scene: sceneDraft.scene,
    guide: sceneDraft.guide,
    intro: sceneDraft.intro,
    thought: sceneDraft.thought
  });
  debouncedAutoSave();
}

function addDialogue() {
  if (!sceneStore.currentScene) return;
  const nextId = (() => {
    // 计算场景内最大 id + 1
    let max = 0;
    const dfs = (dias) => {
      dias?.forEach(d => { max = Math.max(max, Number(d.id) || 0); d.opt?.forEach(o => dfs(o.dia)); });
    };
    dfs(sceneStore.currentScene.dia);
    return max + 1;
  })();
  const node = { id: nextId, chr: 0, txt: '新对话内容' };
    sceneStore.currentScene.dia = sceneStore.currentScene.dia || [];
    sceneStore.currentScene.dia.push(node);
    sceneStore.selectDialogue(node);
    debouncedAutoSave();
  }
function deleteScene() { sceneStore.deleteCurrentScene(); }

// 对话草稿
const dialogueDraft = reactive({ id: 0, chr: 0, txt: '', next: '' });
watch(() => sceneStore.currentNode, (n) => {
  if (sceneStore.selectionType !== 'dialogue' || !n) return;
  dialogueDraft.id = n.id;
  dialogueDraft.chr = n.chr ?? 0;
  dialogueDraft.txt = n.txt ?? '';
  dialogueDraft.next = n.next ?? '';
}, { immediate: true });

function applyDialogue() {
  sceneStore.updateCurrentDialogue({
    chr: dialogueDraft.chr,
    txt: dialogueDraft.txt,
    next: dialogueDraft.next
  });
  debouncedAutoSave();
}

// 场景名选项（用于 next 选择）
const sceneNameOptions = computed(() => (sceneStore.scriptData || []).map(s => s?.scene).filter(Boolean));

// 行为(act)编辑
const newActionKey = ref('');
const newActionValue = ref('');
const actionEdits = reactive({});

// 监听节点切换，重置编辑缓存
watch(() => sceneStore.currentNode, (node) => {
  // 清空旧缓存
  Object.keys(actionEdits).forEach(k => delete actionEdits[k]);
  if (node?.act) {
    Object.entries(node.act).forEach(([k, v]) => {
      actionEdits[k] = Array.isArray(v) ? v.join(', ') : v;
    });
  }
}, { immediate: true });

const currentActEntries = computed(() => {
  if (!sceneStore.currentNode || sceneStore.selectionType !== 'dialogue') return [];
  return Object.entries(sceneStore.currentNode.act || {});
});

function addAction() {
  const key = (newActionKey.value || '').trim();
  if (!key) return;
  const value = newActionValue.value ?? '';
  if (!sceneStore.currentNode || sceneStore.selectionType !== 'dialogue') return;
  if (!sceneStore.currentNode.act) sceneStore.currentNode.act = {};
  
  // 如果输入包含逗号，尝试转为数组（与解析器逻辑一致）
  const finalValue = value.includes(',') ? value.split(',').map(s => s.trim()) : value;
  
  sceneStore.currentNode.act[key] = finalValue;
  actionEdits[key] = value;
  newActionKey.value = '';
  newActionValue.value = '';
  debouncedAutoSave();
}

function removeAction(key) {
  if (!sceneStore.currentNode?.act) return;
  delete sceneStore.currentNode.act[key];
  delete actionEdits[key];
  if (Object.keys(sceneStore.currentNode.act).length === 0) {
    delete sceneStore.currentNode.act;
  }
  debouncedAutoSave();
}

function onEditActionValue(key) {
  if (!sceneStore.currentNode) return;
  if (!sceneStore.currentNode.act) sceneStore.currentNode.act = {};
  
  const value = actionEdits[key];
  const finalValue = typeof value === 'string' && value.includes(',') 
    ? value.split(',').map(s => s.trim()) 
    : value;
    
  sceneStore.currentNode.act[key] = finalValue;
  debouncedAutoSave();
}

// 选项草稿
const optionDraft = reactive({ optn: '' });
watch(() => sceneStore.currentNode, (n) => {
  if (sceneStore.selectionType !== 'option' || !n) return;
  optionDraft.optn = n.optn ?? '';
}, { immediate: true });

function applyOption() { sceneStore.updateCurrentOption({ optn: optionDraft.optn }); }
watch(() => optionDraft.optn, () => { if (sceneStore.selectionType === 'option') debouncedAutoSave(); });

// 结构操作：与旧前端功能对齐
function nextIdFromScene(scene) {
  let max = 0;
  const dfs = (dias) => dias?.forEach(d => { max = Math.max(max, Number(d.id) || 0); d.opt?.forEach(o => dfs(o.dia)); });
  dfs(scene?.dia);
  return max + 1;
}
function addOptionToDialogue() {
  if (sceneStore.selectionType !== 'dialogue' || !sceneStore.currentNode) return;
  const option = { optn: '新选项', dia: [], __oid: `oid-${Date.now()}` };
  sceneStore.currentNode.opt = sceneStore.currentNode.opt || [];
  // 默认给选项加一个子对话，便于继续编写
  const nid = nextIdFromScene(sceneStore.currentScene);
  option.dia.push({ id: nid, chr: 0, txt: '新选项对话内容' });
  sceneStore.currentNode.opt.push(option);
  sceneStore.selectOption(option, sceneStore.currentNode);
  debouncedAutoSave();
}

function deleteDialogue() {
  if (sceneStore.selectionType !== 'dialogue' || !sceneStore.currentNode) return;
  const node = sceneStore.currentNode;
  const parent = sceneStore.nodeParent; // 若存在则为所属选项
  if (parent && Array.isArray(parent.dia)) {
    const idx = parent.dia.indexOf(node);
    if (idx >= 0) parent.dia.splice(idx, 1);
  sceneStore.selectOption(parent, sceneStore.nodeParent); // 回到父选项
  } else if (sceneStore.currentScene?.dia) {
    const idx = sceneStore.currentScene.dia.indexOf(node);
    if (idx >= 0) sceneStore.currentScene.dia.splice(idx, 1);
    sceneStore.selectScene(sceneStore.currentScene);
  }
  debouncedAutoSave();
}

function addDialogueToOption() {
  if (sceneStore.selectionType !== 'option' || !sceneStore.currentNode) return;
  const nid = nextIdFromScene(sceneStore.currentScene);
  const dlg = { id: nid, chr: 0, txt: '新对话' };
  sceneStore.currentNode.dia = sceneStore.currentNode.dia || [];
  sceneStore.currentNode.dia.push(dlg);
  sceneStore.selectDialogue(dlg, sceneStore.currentNode);
  debouncedAutoSave();
}

function deleteOption() {
  if (sceneStore.selectionType !== 'option' || !sceneStore.currentNode) return;
  const option = sceneStore.currentNode;
  const parent = sceneStore.nodeParent; // 父对话
  if (parent?.opt) {
    const idx = parent.opt.indexOf(option);
    if (idx >= 0) parent.opt.splice(idx, 1);
    if (parent.opt.length === 0) delete parent.opt;
    sceneStore.selectDialogue(parent, null);
  }
  debouncedAutoSave();
}

// 在当前对话节点后面添加一个新的对话并选中
function addDialogueAfterCurrent() {
  if (sceneStore.selectionType !== 'dialogue' || !sceneStore.currentNode) return;
  const nid = nextIdFromScene(sceneStore.currentScene);
  const dlg = { id: nid, chr: 0, txt: '' };
  const parent = sceneStore.nodeParent; // 如果存在则为选项
  if (parent && Array.isArray(parent.dia)) {
    const arr = parent.dia;
    const idx = arr.indexOf(sceneStore.currentNode);
    if (idx >= 0) arr.splice(idx + 1, 0, dlg); else arr.push(dlg);
    sceneStore.selectDialogue(dlg, parent);
  } else if (sceneStore.currentScene?.dia) {
    const arr = sceneStore.currentScene.dia;
    const idx = arr.indexOf(sceneStore.currentNode);
    if (idx >= 0) arr.splice(idx + 1, 0, dlg); else arr.push(dlg);
    sceneStore.selectDialogue(dlg, null);
  }
  debouncedAutoSave();
}

function onEnterAddNextDialogue() {
  // 已通过 .prevent 阻止换行，这里直接添加下一对话
  addDialogueAfterCurrent();
}

// 监听 AI 面板生成文本的追加事件，只更新编辑器草稿与 store
function onAiAppend(e) {
  if (sceneStore.selectionType !== 'dialogue') return;
  const chunk = e?.chunk ?? '';
  dialogueDraft.txt = (dialogueDraft.txt || '') + chunk;
  applyDialogue();
}

onMounted(() => {
  bus.on('ai-append-text', onAiAppend);
  // 确保加载角色列表
  characterStore.load(projectStore.currentProject);
});
onBeforeUnmount(() => {
  bus.off('ai-append-text', onAiAppend);
});

</script>

<style scoped>
.right-panel-section {
  padding: 0;
}
.action-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.action-item :deep(.n-input) {
  flex: 1;
}
.no-selection {
  padding: 20px 0;
}
</style>