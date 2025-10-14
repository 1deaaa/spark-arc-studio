<template>
  <div id="node-editor" class="right-panel-section">
    <el-card shadow="hover" :body-style="{ padding: '16px' }">
      <template #header>
        <div class="card-header">
          <el-icon v-if="type === 'scene'"><Film /></el-icon>
          <el-icon v-else-if="type === 'dialogue'"><ChatDotRound /></el-icon>
          <el-icon v-else-if="type === 'option'"><Pointer /></el-icon>
          <el-icon v-else><QuestionFilled /></el-icon>
          <span id="node-editor-title">{{ title }}</span>
        </div>
      </template>

      <div id="node-editor-content">
        <!-- 场景编辑器 -->
        <el-form v-if="type === 'scene'" label-position="top" size="default">
          <el-form-item label="场景名称(scene)">
            <el-input 
              id="scene-name" 
              v-model="sceneDraft.scene" 
              @input="applyScene"
              clearable
              placeholder="输入场景名称"
            >
              <template #prefix>
                <el-icon><LocationInformation /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item label="场景标题(cap)">
            <el-input 
              id="scene-cap" 
              v-model="sceneDraft.cap" 
              @input="applyScene"
              clearable
              placeholder="输入场景标题"
            >
              <template #prefix>
                <el-icon><Tickets /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item label="剧情进度(pgrs)">
            <el-input-number 
              id="scene-pgrs" 
              v-model="sceneDraft.pgrs" 
              @change="applyScene"
              :min="0"
              controls-position="right"
              style="width: 100%"
            />
          </el-form-item>

          <el-space direction="vertical" style="width: 100%" :size="8">
            <el-button type="primary" @click="addDialogue" style="width: 100%">
              <el-icon><Plus /></el-icon>
              添加对话节点
            </el-button>
            <el-popconfirm 
              title="确定要删除这个场景吗？" 
              @confirm="deleteScene"
              confirm-button-text="删除"
              cancel-button-text="取消"
            >
              <template #reference>
                <el-button type="danger" style="width: 100%">
                  <el-icon><Delete /></el-icon>
                  删除场景
                </el-button>
              </template>
            </el-popconfirm>
          </el-space>
        </el-form>

        <!-- 对话编辑器 -->
        <el-form v-else-if="type === 'dialogue'" label-position="top" size="default">
          <el-form-item label="对话ID(id)">
            <el-input id="dialogue-id" :value="dialogueDraft.id" disabled>
              <template #prefix>
                <el-icon><Key /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item label="角色(chr)">
            <el-select
              id="dialogue-chr"
              v-model="dialogueDraft.chr"
              @change="applyDialogue"
              placeholder="选择或搜索角色"
              filterable
              style="width: 100%"
            >
              <el-option
                v-for="c in characterOptions"
                :key="c.id"
                :value="Number(c.id)"
                :label="c.name || `角色 ${c.id}`"
              >
                <div style="display: flex; align-items: center; gap: 8px;">
                  <el-icon><Avatar /></el-icon>
                  <span>{{ c.name || `角色 ${c.id}` }}</span>
                </div>
              </el-option>
            </el-select>
          </el-form-item>

          <el-form-item label="文本(txt)">
            <el-input 
              id="dialogue-txt" 
              v-model="dialogueDraft.txt" 
              type="textarea"
              :autosize="{ minRows: 5, maxRows: 12 }"
              @input="applyDialogue" 
              @keydown.enter.prevent="onEnterAddNextDialogue"
              placeholder="输入对话内容，按 Enter 添加下一对话"
            />
          </el-form-item>

          <el-form-item label="跳转(next)">
            <el-select
              id="dialogue-next"
              v-model="dialogueDraft.next"
              @change="applyDialogue"
              placeholder="选择跳转场景（可清除）"
              filterable
              clearable
              style="width: 100%"
            >
              <el-option
                v-for="sceneName in sceneNameOptions"
                :key="sceneName"
                :value="sceneName"
                :label="sceneName"
              >
                <div style="display: flex; align-items: center; gap: 8px;">
                  <el-icon><Right /></el-icon>
                  <span>{{ sceneName }}</span>
                </div>
              </el-option>
            </el-select>
          </el-form-item>

          <el-divider />

          <el-space direction="vertical" style="width: 100%" :size="8">
            <el-button @click="addOptionToDialogue" style="width: 100%">
              <el-icon><CirclePlus /></el-icon>
              添加选项
            </el-button>
            <el-button @click="addDialogueAfterCurrent" style="width: 100%">
              <el-icon><Bottom /></el-icon>
              添加下一对话
            </el-button>
            <el-popconfirm 
              title="确定要删除这个对话吗？" 
              @confirm="deleteDialogue"
              confirm-button-text="删除"
              cancel-button-text="取消"
            >
              <template #reference>
                <el-button type="danger" style="width: 100%">
                  <el-icon><Delete /></el-icon>
                  删除对话
                </el-button>
              </template>
            </el-popconfirm>
          </el-space>

          <el-divider content-position="left">
            <el-icon><Operation /></el-icon>
            <span style="margin-left: 4px">行为(act)</span>
          </el-divider>

          <div v-if="currentActEntries.length === 0" class="muted">
            <el-empty description="暂无行为" :image-size="60" />
          </div>
          <div v-else class="action-list">
            <el-space direction="vertical" style="width: 100%" :size="8">
              <div v-for="([k, v], idx) in currentActEntries" :key="k" class="action-item">
                <el-tag type="info" closable @close="removeAction(k)" size="large">
                  <strong>{{ k }}</strong>
                </el-tag>
                <el-input 
                  v-model="actionEdits[k]" 
                  @change="onEditActionValue(k)"
                  placeholder="参数/值"
                  size="small"
                />
              </div>
            </el-space>
          </div>

          <el-divider />

          <el-form label-position="top" size="small">
            <el-form-item label="添加新行为">
              <el-input 
                v-model="newActionKey" 
                placeholder="函数名 (key)"
                clearable
              >
                <template #prefix>
                  <el-icon><Key /></el-icon>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item>
              <el-input 
                v-model="newActionValue" 
                placeholder="参数/值 (value)"
                clearable
              >
                <template #prefix>
                  <el-icon><DocumentCopy /></el-icon>
                </template>
              </el-input>
            </el-form-item>
            <el-button type="success" @click="addAction" style="width: 100%">
              <el-icon><CirclePlus /></el-icon>
              添加
            </el-button>
          </el-form>
        </el-form>

        <!-- 选项编辑器 -->
        <el-form v-else-if="type === 'option'" label-position="top" size="default">
          <el-form-item label="选项文本(optn)">
            <el-input 
              id="option-text" 
              v-model="optionDraft.optn" 
              @input="applyOption"
              clearable
              placeholder="输入选项文本"
            >
              <template #prefix>
                <el-icon><Edit /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-space direction="vertical" style="width: 100%" :size="8">
            <el-button type="primary" @click="addDialogueToOption" style="width: 100%">
              <el-icon><Plus /></el-icon>
              添加子对话
            </el-button>
            <el-popconfirm 
              title="确定要删除这个选项吗？" 
              @confirm="deleteOption"
              confirm-button-text="删除"
              cancel-button-text="取消"
            >
              <template #reference>
                <el-button type="danger" style="width: 100%">
                  <el-icon><Delete /></el-icon>
                  删除选项
                </el-button>
              </template>
            </el-popconfirm>
          </el-space>
        </el-form>

        <div v-else class="no-selection">
          <el-empty description="请选择一个节点" />
        </div>
      </div>
    </el-card>
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

const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const characterStore = useCharacterStore();
const characterOptions = computed(() => characterStore.list);
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
.action-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.action-item .el-input {
  flex: 1;
}
.muted {
  color: #909399;
  text-align: center;
  padding: 12px 0;
}
.no-selection {
  padding: 20px 0;
}
</style>