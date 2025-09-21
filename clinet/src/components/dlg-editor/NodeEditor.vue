<template>
  <div id="node-editor" class="right-panel-section">
    <div class="toolbar-title" id="node-editor-title">{{ title }}</div>
    <div id="node-editor-content">
      <!-- 场景编辑器 -->
      <div v-if="type === 'scene'" class="editor-form">
        <label>场景名称(scene):</label>
        <input id="scene-name" v-model="sceneDraft.scene" @input="applyScene" autocomplete="off" />

        <label>场景标题(cap):</label>
        <input id="scene-cap" v-model="sceneDraft.cap" @input="applyScene" autocomplete="off" />

        <label>剧情进度(pgrs):</label>
        <input id="scene-pgrs" type="number" v-model.number="sceneDraft.pgrs" @input="applyScene" autocomplete="off" />

        <div class="button-group">
          <button @click="addDialogue">添加对话节点</button>
          <button class="btn-danger" @click="deleteScene">删除场景</button>
        </div>
      </div>

      <!-- 对话编辑器 -->
      <div v-else-if="type === 'dialogue'" class="editor-form">
        <label>对话ID(id):</label>
        <input id="dialogue-id" :value="dialogueDraft.id" disabled />

        <label>角色(chr):</label>
        <VSelect
          id="dialogue-chr"
          :options="characterOptions"
          label="name"
          v-model="selectedChrOption"
          :clearable="false"
          :searchable="true"
          placeholder="选择或搜索角色"
        />

  <label>文本(txt):</label>
  <textarea id="dialogue-txt" rows="5" v-model="dialogueDraft.txt" @input="applyDialogue" @keydown.enter.prevent="onEnterAddNextDialogue" autocomplete="off" />

        <label>跳转(next):</label>
        <VSelect
          id="dialogue-next"
          :options="sceneNameOptions"
          v-model="selectedNextOption"
          :clearable="true"
          :searchable="true"
          placeholder="选择跳转场景（可清除）"
        />

        <hr />
        <div class="button-group">
          <button class="btn-secondary" @click="addOptionToDialogue">添加选项</button>
          <button class="btn-secondary" @click="addDialogueAfterCurrent">添加下一对话</button>
          <button class="btn-danger" @click="deleteDialogue">删除对话</button>
        </div>

        <div class="actions-section">
          <div class="section-title">行为(act)</div>
          <div v-if="currentActEntries.length === 0" class="muted">暂无行为</div>
          <div v-else class="action-list">
            <div v-for="([k, v], idx) in currentActEntries" :key="k" class="action-item">
              <span class="action-key">{{ k }}</span>
              <span class="sep">:</span>
              <input class="action-value" v-model="actionEdits[k]" @change="onEditActionValue(k)" autocomplete="off" />
              <button class="btn-danger small" @click="removeAction(k)">删除</button>
            </div>
          </div>
          <div class="action-add">
            <input placeholder="函数名 (key)" v-model="newActionKey" autocomplete="off" />
            <input placeholder="参数/值 (value)" v-model="newActionValue" autocomplete="off" />
            <button class="btn-secondary" @click="addAction">添加</button>
          </div>
        </div>
      </div>

      <!-- 选项编辑器 -->
      <div v-else-if="type === 'option'" class="editor-form">
        <label>选项文本(optn):</label>
        <input id="option-text" v-model="optionDraft.optn" @input="applyOption" autocomplete="off" />

        <div class="button-group">
          <button class="btn-secondary" @click="addDialogueToOption">添加子对话</button>
          <button class="btn-danger" @click="deleteOption">删除选项</button>
        </div>
      </div>

      <div v-else class="no-selection">请选择一个节点</div>
    </div>
  </div>
  
</template>

<script setup>
import { computed, reactive, ref, watch, getCurrentInstance, onMounted, onBeforeUnmount } from 'vue';
import bus from '@/eventBus';
import { useSceneStore } from '@/components/stores/sceneStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { useFileStore } from '@/components/stores/fileStore';
import { saveStory } from '@/services/api';
import { useCharacterStore } from '@/components/stores/characterStore';
import VSelect from 'vue-select';
import 'vue-select/dist/vue-select.css';

const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const characterStore = useCharacterStore();
const characterOptions = computed(() => characterStore.list);
const selectedChrOption = computed({
  get() {
    const id = dialogueDraft.chr;
    return characterStore.list.find(c => Number(c.id) === Number(id)) || null;
  },
  set(opt) {
    dialogueDraft.chr = opt ? Number(opt.id) : 0;
    applyDialogue();
  }
});
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
const selectedNextOption = computed({
  get() { return dialogueDraft.next || null; },
  set(val) { dialogueDraft.next = val || ''; applyDialogue(); }
});

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