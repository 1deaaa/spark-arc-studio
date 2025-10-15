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

          <n-form-item label="场景标题(cap)">
            <n-input 
              id="scene-cap" 
              v-model:value="sceneDraft.cap" 
              @input="applyScene"
              clearable
              placeholder="输入场景标题"
            />
          </n-form-item>

          <n-form-item label="剧情进度(pgrs)">
            <n-input-number 
              id="scene-pgrs" 
              v-model:value="sceneDraft.pgrs" 
              @update:value="applyScene"
              :min="0"
              style="width: 100%"
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

          <n-form label-placement="top" size="small">
            <n-form-item label="添加新行为">
              <n-input 
                v-model:value="newActionKey" 
                placeholder="函数名 (key)"
                clearable
              />
            </n-form-item>
            <n-form-item>
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
          </n-form>
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
import { NCard, NForm, NFormItem, NInput, NInputNumber, NSelect, NButton, NIcon, NDivider, NSpace, NPopconfirm, NEmpty, NTag } from 'naive-ui';
import { FilmOutline, ChatbubbleEllipsesOutline, RadioButtonOnOutline, HelpCircleOutline, AddOutline, TrashOutline, AddCircleOutline, ArrowDownOutline, PersonOutline } from '@vicons/ionicons5';
import bus from '@/eventBus';
import { useSceneStore } from '@/components/stores/sceneStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { useFileStore } from '@/components/stores/fileStore';
import { saveStory } from '@/services/api';
import { useCharacterStore } from '@/components/stores/characterStore';

const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const characterStore = useCharacterStore();
const characterOptions = computed(() => characterStore.list);

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
  
  const allowedSceneKeys = new Set(['scene', 'cap', 'pgrs', 'dia']);
  const allowedDialogueKeys = new Set(['id', 'chr', 'txt', 'opt', 'act', 'next']);
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

// 场景草稿
const sceneDraft = reactive({ scene: '', cap: '', pgrs: 0 });
watch([
  () => sceneStore.currentScene,
  () => sceneStore.selectionType
], ([s, t]) => {
  if (!s || t !== 'scene') return;
  sceneDraft.scene = s.scene || '';
  sceneDraft.cap = s.cap || '';
  sceneDraft.pgrs = s.pgrs ?? 0;
}, { immediate: true });

function applyScene() {
  sceneStore.updateCurrentScene({ scene: sceneDraft.scene, cap: sceneDraft.cap, pgrs: sceneDraft.pgrs });
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
  sceneStore.updateCurrentDialogue({ chr: dialogueDraft.chr, txt: dialogueDraft.txt, next: dialogueDraft.next });
  debouncedAutoSave();
}

// 场景名选项（用于 next 选择）
const sceneNameOptions = computed(() => (sceneStore.scriptData || []).map(s => s?.scene).filter(Boolean));

// 行为(act)编辑
const newActionKey = ref('');
const newActionValue = ref('');
const actionEdits = reactive({});

const currentActEntries = computed(() => {
  const act = sceneStore.currentNode && sceneStore.selectionType === 'dialogue' ? sceneStore.currentNode.act : undefined;
  // 将当前值同步到可编辑缓存
  const entries = Object.entries(act || {});
  // 初始化 actionEdits 中缺失的键
  entries.forEach(([k, v]) => { if (!(k in actionEdits)) actionEdits[k] = v; });
  // 清理 actionEdits 中已删除的键
  Object.keys(actionEdits).forEach(k => { if (!entries.find(([ek]) => ek === k)) delete actionEdits[k]; });
  return entries;
});

function addAction() {
  const key = (newActionKey.value || '').trim();
  if (!key) return;
  const value = newActionValue.value ?? '';
  if (!sceneStore.currentNode || sceneStore.selectionType !== 'dialogue') return;
  if (!sceneStore.currentNode.act) sceneStore.currentNode.act = {};
  sceneStore.currentNode.act[key] = value;
  actionEdits[key] = value;
  newActionKey.value = '';
  newActionValue.value = '';
  debouncedAutoSave();
}

function removeAction(key) {
  if (!sceneStore.currentNode?.act) return;
  delete sceneStore.currentNode.act[key];
  delete actionEdits[key];
  if (Object.keys(sceneStore.currentNode.act).length === 0) delete sceneStore.currentNode.act;
  debouncedAutoSave();
}

function onEditActionValue(key) {
  if (!sceneStore.currentNode) return;
  if (!sceneStore.currentNode.act) sceneStore.currentNode.act = {};
  sceneStore.currentNode.act[key] = actionEdits[key];
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
  const option = { optn: '新选项', dia: [] };
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