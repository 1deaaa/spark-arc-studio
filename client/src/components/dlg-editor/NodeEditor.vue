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

          <!-- Unity 运行时配置（可折叠，仅游戏开发使用） -->
          <n-collapse style="margin-top: 8px;">
            <n-collapse-item name="unity-scene">
              <template #header>
                <n-space align="center" :size="6">
                  <n-icon :component="GameControllerOutline" size="16" />
                  <span style="font-size: 13px; font-weight: 500;">Unity 运行时配置</span>
                </n-space>
              </template>
              <template #header-extra>
                <n-text depth="3" style="font-size: 11px;">触发条件 / 效果 / 按钮文案等</n-text>
              </template>

              <n-form label-placement="top" size="small" style="margin-top: 4px;">

                <n-form-item>
                  <template #label>
                    <n-space align="center" :size="4">
                      <span>交互按钮文案</span>
                      <n-text depth="3" style="font-size: 11px;">(button_text) — DialogueTrigger 悬浮提示</n-text>
                    </n-space>
                  </template>
                  <n-input
                    v-model:value="sceneDraft.button_text"
                    @input="applyScene"
                    clearable
                    placeholder="例如：启动机关"
                  />
                </n-form-item>

                <n-form-item>
                  <template #label>
                    <n-space align="center" :size="4">
                      <span>外部触发事件</span>
                      <n-text depth="3" style="font-size: 11px;">(trigger_event) — 非玩家触碰触发时填写</n-text>
                    </n-space>
                  </template>
                  <n-input
                    v-model:value="sceneDraft.trigger_event"
                    @input="applyScene"
                    clearable
                    placeholder="例如：battle.end.camp_01"
                  />
                </n-form-item>

                <n-form-item>
                  <template #label>
                    <n-space align="center" :size="4">
                      <span>播放优先级</span>
                      <n-text depth="3" style="font-size: 11px;">(priority) — 多场景同时满足时数值越大越先触发</n-text>
                    </n-space>
                  </template>
                  <n-input-number
                    v-model:value="sceneDraft.priority"
                    @update:value="applyScene"
                    :show-button="true"
                    placeholder="默认 0"
                    style="width: 100%"
                  />
                </n-form-item>

                <n-form-item>
                  <template #label>
                    <n-space align="center" :size="4">
                      <span>一次性标记键</span>
                      <n-text depth="3" style="font-size: 11px;">(once_key) — 场景完成后自动写入 StoryStateStore，防重放</n-text>
                    </n-space>
                  </template>
                  <n-input
                    v-model:value="sceneDraft.once_key"
                    @input="applyScene"
                    clearable
                    placeholder="例如：cutscene.windrise_intro"
                  />
                </n-form-item>

                <n-form-item>
                  <template #label>
                    <n-space align="center" :size="4">
                      <span>隐藏场景</span>
                      <n-text depth="3" style="font-size: 11px;">(hiden) — 开启后不在触发列表中显示，仅可由条件或事件激活</n-text>
                    </n-space>
                  </template>
                  <n-switch v-model:value="sceneDraft.hiden" @update:value="applyScene" />
                </n-form-item>

                <n-form-item>
                  <template #label>
                    <n-space align="center" :size="4">
                      <span>触发条件</span>
                      <n-text depth="3" style="font-size: 11px;">(conditions) — 满足条件才可见/可触发</n-text>
                    </n-space>
                  </template>
                  <conditions-editor
                    v-model:model-value="sceneDraft.conditions"
                    @update:model-value="applyScene"
                    style="width: 100%"
                  />
                </n-form-item>

                <n-form-item>
                  <template #label>
                    <n-space align="center" :size="4">
                      <span>场景完成后状态写入</span>
                      <n-text depth="3" style="font-size: 11px;">(effects) — 场景结束后写回 StoryStateStore（≠ act，不触发函数，只记状态）</n-text>
                    </n-space>
                  </template>
                  <effects-editor
                    v-model:model-value="sceneDraft.effects"
                    @update:model-value="applyScene"
                    style="width: 100%"
                  />
                </n-form-item>

              </n-form>
            </n-collapse-item>
          </n-collapse>
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

          <!-- Unity 行为配置（可折叠） -->
          <n-collapse style="margin-top: 8px;">
            <n-collapse-item name="unity-act">
              <template #header>
                <n-space align="center" :size="6">
                  <n-icon :component="GameControllerOutline" size="16" />
                  <span style="font-size: 13px; font-weight: 500;">Unity 行为绑定 (act)</span>
                </n-space>
              </template>
              <template #header-extra>
                <n-tag v-if="currentActCount > 0" type="info" size="small" :bordered="false">
                  {{ currentActCount }} 个
                </n-tag>
                <n-text v-else depth="3" style="font-size: 11px;">节点执行时广播给 Unity 监听器</n-text>
              </template>

              <!-- ActEditor 组件 -->
              <ActEditor
                :model-value="currentDialogueAct"
                @update:model-value="onActChange"
              />
            </n-collapse-item>
          </n-collapse>
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

<script setup lang="ts">
import { computed, reactive, ref, watch, getCurrentInstance, onMounted, onBeforeUnmount } from 'vue';
import { NCard, NForm, NFormItem, NInput, NInputNumber, NSwitch, NSelect, NButton, NIcon, NDivider, NSpace, NPopconfirm, NEmpty, NTag, NCollapse, NCollapseItem, NText } from 'naive-ui';
import { FilmOutline, ChatbubbleEllipsesOutline, RadioButtonOnOutline, HelpCircleOutline, AddOutline, TrashOutline, AddCircleOutline, ArrowDownOutline, PersonOutline, AnalyticsOutline, GameControllerOutline } from '@vicons/ionicons5';
import bus from '@/eventBus';
import ConditionsEditor from './ConditionsEditor.vue';
import EffectsEditor from './EffectsEditor.vue';
import ActEditor from './ActEditor.vue';
import { useSceneStore } from '@/components/stores/sceneStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { useFileStore } from '@/components/stores/fileStore';
import { saveStory } from '@/services/api';
import { useCharacterStore } from '@/components/stores/characterStore';
import { useActionBindingStore } from '@/components/stores/actionBindingStore';
import MarkdownRenderer from '@/components/share/MarkdownRenderer.vue';
import type { ArcDialogueNode, ArcOptionNode, ArcScene, SceneEffectItem } from '@/services/arcParser';

const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const characterStore = useCharacterStore();
const actionBindingStore = useActionBindingStore();
const characterOptions = computed(() => characterStore.list);

function isDialogueNode(node: unknown): node is ArcDialogueNode {
  return !!node && typeof node === 'object' && 'id' in node && 'txt' in node;
}

function isOptionNode(node: unknown): node is ArcOptionNode {
  return !!node && typeof node === 'object' && 'optn' in node && 'dia' in node;
}


// 角色选项（Naive UI format）
const characterSelectOptions = computed(() => 
  characterOptions.value.map(c => ({
    label: c.name || `角色 ${c.id}`,
    value: Number(c.id)
  }))
);

// 场景选项（Naive UI format）
const sceneSelectOptions = computed(() => 
  (Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : [])
    .map(s => s?.scene)
    .filter(Boolean)
    .map(name => ({ label: name, value: name }))
);
const vm = getCurrentInstance();
const autoSaveEnabled = computed(() => localStorage.getItem('autoSaveEnabled') === 'true');

function cleanStoryDataForSave(story) {
  // Deep copy to avoid mutating the reactive state used by the UI
  const storyCopy = JSON.parse(JSON.stringify(story));
  
  const allowedSceneKeys = new Set(['scene', 'guide', 'intro', 'dia', 'thought', 'button_text', 'conditions', 'effects', 'trigger_event', 'priority', 'once_key', 'hiden']);
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

// 场景草稿（conditions / effects 直接存对象，由子组件负责序列化）
const sceneDraft = reactive<{
  scene: string;
  guide: string;
  intro: string;
  thought: string;
  button_text: string;
  trigger_event: string;
  priority: number;
  once_key: string;
  hiden: boolean;
  conditions: ArcScene['conditions'];
  effects: ArcScene['effects'];
}>({
  scene: '',
  guide: '',
  intro: '',
  thought: '',
  button_text: '',
  trigger_event: '',
  priority: 0,
  once_key: '',
  hiden: false,
  conditions: null,
  effects: null,
});

watch([
  () => sceneStore.currentScene,
  () => sceneStore.selectionType
], ([s, t]) => {
  if (!s || t !== 'scene') return;
  sceneDraft.scene = s.scene || '';
  sceneDraft.guide = s.guide || '';
  sceneDraft.intro = s.intro || '';
  sceneDraft.thought = s.thought || '';
  sceneDraft.button_text = typeof s.button_text === 'string' ? s.button_text : '';
  sceneDraft.trigger_event = typeof s.trigger_event === 'string' ? s.trigger_event : '';
  sceneDraft.priority = Number.isFinite(Number(s.priority)) ? Number(s.priority) : 0;
  sceneDraft.once_key = typeof s.once_key === 'string' ? s.once_key : '';
  sceneDraft.hiden = !!s.hiden;
  sceneDraft.conditions = (s.conditions != null && typeof s.conditions === 'object') ? s.conditions as ArcScene['conditions'] : null;
  sceneDraft.effects = (s.effects != null) ? s.effects as ArcScene['effects'] : null;
}, { immediate: true });

function applyScene() {
  sceneStore.updateCurrentScene({
    scene: sceneDraft.scene,
    guide: sceneDraft.guide,
    intro: sceneDraft.intro,
    thought: sceneDraft.thought,
    button_text: sceneDraft.button_text.trim() || undefined,
    trigger_event: sceneDraft.trigger_event.trim() || undefined,
    priority: Number.isFinite(Number(sceneDraft.priority)) ? Number(sceneDraft.priority) : 0,
    once_key: sceneDraft.once_key.trim() || undefined,
    hiden: !!sceneDraft.hiden,
    conditions: sceneDraft.conditions,
    effects: sceneDraft.effects,
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
  if (sceneStore.selectionType !== 'dialogue' || !isDialogueNode(n)) return;
  dialogueDraft.id = n.id ?? 0;
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
const sceneNameOptions = computed(() => (Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : []).map(s => s?.scene).filter(Boolean));

// ──────────────────────────────────────────
// 行为(act)编辑 — 委托给 ActEditor 组件
// ──────────────────────────────────────────
const currentDialogueAct = computed(() => {
  if (!isDialogueNode(sceneStore.currentNode) || sceneStore.selectionType !== 'dialogue') return null;
  return sceneStore.currentNode.act ?? null;
});

const currentActCount = computed(() => {
  if (!isDialogueNode(sceneStore.currentNode) || sceneStore.selectionType !== 'dialogue') return 0;
  return Object.keys(sceneStore.currentNode.act || {}).length;
});

function onActChange(val: Record<string, string | string[]> | null) {
  if (!isDialogueNode(sceneStore.currentNode) || sceneStore.selectionType !== 'dialogue') return;
  if (!val || Object.keys(val).length === 0) {
    delete (sceneStore.currentNode as any).act;
  } else {
    sceneStore.currentNode.act = val;
  }
  debouncedAutoSave();
}

// 选项草稿
const optionDraft = reactive({ optn: '' });
watch(() => sceneStore.currentNode, (n) => {
  if (sceneStore.selectionType !== 'option' || !isOptionNode(n)) return;
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
  if (sceneStore.selectionType !== 'dialogue' || !isDialogueNode(sceneStore.currentNode)) return;
  const option: { optn: string; dia: Array<{ id: number; chr: number; txt: string }>; __oid: string } = {
    optn: '新选项',
    dia: [],
    __oid: `oid-${Date.now()}`,
  };
  sceneStore.currentNode.opt = sceneStore.currentNode.opt || [];
  // 默认给选项加一个子对话，便于继续编写
  const nid = nextIdFromScene(sceneStore.currentScene);
  option.dia.push({ id: nid, chr: 0, txt: '新选项对话内容' });
  sceneStore.currentNode.opt.push(option);
  sceneStore.selectOption(option, sceneStore.currentNode);
  debouncedAutoSave();
}

function deleteDialogue() {
  if (sceneStore.selectionType !== 'dialogue' || !isDialogueNode(sceneStore.currentNode)) return;
  const node = sceneStore.currentNode;
  const parent = sceneStore.nodeParent; // 若存在则为所属选项
  if (isOptionNode(parent) && Array.isArray(parent.dia)) {
    const idx = parent.dia.indexOf(node);
    if (idx >= 0) parent.dia.splice(idx, 1);
    sceneStore.selectOption(parent, sceneStore.nodeParent || parent); // 回到父选项
  } else if (sceneStore.currentScene?.dia) {
    const idx = sceneStore.currentScene.dia.indexOf(node);
    if (idx >= 0) sceneStore.currentScene.dia.splice(idx, 1);
    sceneStore.selectScene(sceneStore.currentScene);
  }
  debouncedAutoSave();
}

function addDialogueToOption() {
  if (sceneStore.selectionType !== 'option' || !isOptionNode(sceneStore.currentNode)) return;
  const nid = nextIdFromScene(sceneStore.currentScene);
  const dlg = { id: nid, chr: 0, txt: '新对话' };
  sceneStore.currentNode.dia = sceneStore.currentNode.dia || [];
  sceneStore.currentNode.dia.push(dlg);
  sceneStore.selectDialogue(dlg, sceneStore.currentNode);
  debouncedAutoSave();
}

function deleteOption() {
  if (sceneStore.selectionType !== 'option' || !isOptionNode(sceneStore.currentNode)) return;
  const option = sceneStore.currentNode;
  const parent = sceneStore.nodeParent; // 父对话
  if (isDialogueNode(parent) && parent.opt) {
    const idx = parent.opt.indexOf(option);
    if (idx >= 0) parent.opt.splice(idx, 1);
    if (parent.opt.length === 0) delete parent.opt;
    sceneStore.selectDialogue(parent, null);
  }
  debouncedAutoSave();
}

// 在当前对话节点后面添加一个新的对话并选中
function addDialogueAfterCurrent() {
  if (sceneStore.selectionType !== 'dialogue' || !isDialogueNode(sceneStore.currentNode)) return;
  const nid = nextIdFromScene(sceneStore.currentScene);
  const dlg = { id: nid, chr: 0, txt: '' };
  const parent = sceneStore.nodeParent; // 如果存在则为选项
  if (isOptionNode(parent) && Array.isArray(parent.dia)) {
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
  // 加载 action bindings（供 ActEditor 动态预设使用）
  actionBindingStore.load(projectStore.currentProject);
});
onBeforeUnmount(() => {
  bus.off('ai-append-text', onAiAppend);
});

// 切换项目时重新加载 action bindings
watch(
  () => projectStore.currentProject,
  (proj) => {
    if (proj) actionBindingStore.load(proj);
  }
);

</script>

<style scoped>
.right-panel-section {
  padding: 0;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 让 n-card 本体填满右侧面板（flex 子项必须用 flex: 1 而非 height: 100%） */
#node-editor :deep(.n-card) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 让 n-card header 固定，content 区域可滚动 */
#node-editor :deep(.n-card__content) {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

/* 内容区域底部留白，防止内容被滚动条遮住 */
#node-editor-content {
  padding: 4px 0 20px;
}

#node-editor :deep(.n-card-header__main) {
  font-weight: 700;
}

#node-editor :deep(.n-form) {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

#node-editor :deep(.n-form-item) {
  margin-bottom: 0;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 8%);
  border-radius: 14px;
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-primary) 2%);
}

#node-editor :deep(.n-form-item-label) {
  padding-bottom: 6px !important;
}

#node-editor :deep(.n-form-item-feedback-wrapper) {
  min-height: 0;
}

#node-editor :deep(.n-collapse-item) {
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 6%);
  border-radius: 14px;
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-primary) 2%);
}

#node-editor :deep(.n-collapse-item__header) {
  padding: 10px 12px;
}

#node-editor :deep(.n-collapse-item__content-inner) {
  padding: 0 12px 12px;
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
