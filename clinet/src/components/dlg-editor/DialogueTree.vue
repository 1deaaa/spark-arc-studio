<template>
  <div id="dialogue-tree" class="dialogue-tree">
    <n-empty v-if="!sceneStore.currentScene" description="请选择一个场景" size="large">
      <template #icon>
        <span style="font-size: 48px;">💬</span>
      </template>
    </n-empty>
    <template v-else>
      <Draggable
        v-model="sceneStore.currentScene.dia"
        item-key="id"
        :group="{ name: 'root', pull: false, put: false }"
        :animation="150"
        handle=".dialogue-handle"
        :move="onMove"
        @end="onDragEndRoot"
      >
        <template #item="{ element: d }">
          <div class="tree-node-wrapper">
            <n-card 
              class="tree-node dialogue-node dialogue-handle" 
              :class="{ selected: isSelectedDialogue(d) }" 
              size="small"
              hoverable
              @click="selectDialogue(d)"
            >
              <div class="node-content">
                <div class="node-title">
                  <n-text strong>ID: {{ d.id }}</n-text>
                  <n-text depth="3"> | 角色: {{ chrName(d.chr) }}</n-text>
                </div>
                <div class="node-preview">
                  <n-ellipsis :line-clamp="2">{{ d.txt }}</n-ellipsis>
                </div>
                <n-space v-if="hasAnyBadge(d)" size="small" class="badges">
                  <n-tag v-if="d.opt && d.opt.length" type="success" size="small" :bordered="false">
                    选项: {{ d.opt.length }}
                  </n-tag>
                  <n-tag v-if="d.act && Object.keys(d.act).length" type="warning" size="small" :bordered="false">
                    行为
                  </n-tag>
                  <n-tag v-if="d.next" type="info" size="small" :bordered="false">
                    跳转至: {{ d.next }}
                  </n-tag>
                </n-space>
              </div>
            </n-card>
            <Draggable
              v-if="d.opt && d.opt.length"
              class="node-children options-list"
              v-model="d.opt"
              item-key="__oid"
              :group="{ name: 'options-' + d.id, pull: false, put: false }"
              :animation="150"
              handle=".option-handle"
              @end="(evt) => onDragEndOptions(evt, d)"
            >
              <template #item="{ element: o }">
                <div class="tree-node-wrapper">
                  <n-card 
                    class="tree-node option-node option-handle" 
                    :class="{ selected: isSelectedOption(o) }" 
                    size="small"
                    hoverable
                    @click.stop="selectOption(o, d)"
                  >
                    <div class="node-content">
                      <div class="node-title">
                        <n-text type="success" strong>📝 选项: {{ o.optn }}</n-text>
                      </div>
                    </div>
                  </n-card>
                  <Draggable
                    v-if="o.dia && o.dia.length"
                    class="node-children"
                    v-model="o.dia"
                    item-key="id"
                    :group="{ name: 'child-' + optionKey(d, o), pull: false, put: false }"
                    :animation="150"
                    handle=".dialogue-handle"
                    :move="onMove"
                    @end="(evt) => onDragEndOption(evt, o)"
                  >
                    <template #item="{ element: sd }">
                      <div class="tree-node-wrapper">
                        <n-card 
                          class="tree-node dialogue-node dialogue-handle" 
                          :class="{ selected: isSelectedDialogue(sd) }" 
                          size="small"
                          hoverable
                          @click.stop="selectDialogue(sd, o)"
                        >
                          <div class="node-content">
                            <div class="node-title">
                              <n-text strong>ID: {{ sd.id }}</n-text>
                              <n-text depth="3"> | 角色: {{ chrName(sd.chr) }}</n-text>
                            </div>
                            <div class="node-preview">
                              <n-ellipsis :line-clamp="2">{{ sd.txt }}</n-ellipsis>
                            </div>
                            <n-space v-if="hasAnyBadge(sd)" size="small" class="badges">
                              <n-tag v-if="sd.opt && sd.opt.length" type="success" size="small" :bordered="false">
                                选项: {{ sd.opt.length }}
                              </n-tag>
                              <n-tag v-if="sd.act && Object.keys(sd.act).length" type="warning" size="small" :bordered="false">
                                行为
                              </n-tag>
                              <n-tag v-if="sd.next" type="info" size="small" :bordered="false">
                                跳转至: {{ sd.next }}
                              </n-tag>
                            </n-space>
                          </div>
                        </n-card>
                      </div>
                    </template>
                  </Draggable>
                </div>
              </template>
            </Draggable>
          </div>
        </template>
      </Draggable>
    </template>
  </div>
  
</template>

<script setup>
import { computed, onMounted, watch } from 'vue';
import { NCard, NEmpty, NText, NTag, NSpace, NEllipsis } from 'naive-ui';
import { useSceneStore } from '@/components/stores/sceneStore';
import Draggable from 'vuedraggable';
import { useProjectStore } from '@/components/stores/projectStore';
import { useFileStore } from '@/components/stores/fileStore';
import { saveStory } from '@/services/api';
import { useCharacterStore } from '@/components/stores/characterStore';

const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const characterStore = useCharacterStore();

const dialogueData = computed(() => sceneStore.currentScene?.dia || []);

// 将角色ID映射为名称，找不到时回退显示ID
function chrName(id) {
  const name = characterStore.map?.[Number(id)];
  return name ?? id ?? '';
}

function selectDialogue(d, parent = null) {
  if (typeof sceneStore.selectDialogue === 'function') {
    sceneStore.selectDialogue(d, parent);
  } else {
    // 回退：直接写入状态
    sceneStore.currentNode = d;
    sceneStore.nodeParent = parent;
    sceneStore.selectionType = 'dialogue';
  }
}
function selectOption(o, d) {
  if (typeof sceneStore.selectOption === 'function') {
    sceneStore.selectOption(o, d);
  } else {
    sceneStore.currentNode = o;
    sceneStore.nodeParent = d;
    sceneStore.selectionType = 'option';
  }
}
const isSelectedDialogue = (d) => sceneStore.selectionType === 'dialogue' && sceneStore.currentNode === d;
const isSelectedOption = (o) => sceneStore.selectionType === 'option' && sceneStore.currentNode === o;
const hasAnyBadge = (d) => (d?.opt && d.opt.length) || (d?.act && Object.keys(d.act || {}).length) || d?.next;

// 允许任意对话节点拖拽（去除“必须选中才能拖动”的限制）
function onMove(evt) {
  try {
    const el = evt?.draggedContext?.element;
    return !!el; // 有有效元素即可拖动
  } catch { return true; }
}

async function saveAfterDrag(evt) {
  const autoSave = localStorage.getItem('autoSaveEnabled') === 'true';
  if (!autoSave) return;
  if (!fileStore.selectedFile?.path || !projectStore.currentProject) return;
  if (evt && evt.oldIndex === evt.newIndex) return;
  try {
    await saveStory(projectStore.currentProject, fileStore.selectedFile.path, sceneStore.scriptData);
    window.dispatchEvent(new CustomEvent('saved'));
  } catch {}
}

function onDragEndRoot(evt) {
  saveAfterDrag(evt);
}
function onDragEndOption(evt, option) {
  saveAfterDrag(evt);
}

function optionKey(parentDialogue, option) {
  // 生成稳定 key，防止仅用 optn 文本导致 key 冲突
  const idx = parentDialogue.opt?.indexOf(option) ?? -1;
  return `${parentDialogue.id}-${idx}-${option.optn || 'opt'}`;
}

// 为选项分配稳定的 __oid，避免使用文本或索引导致拖拽错乱
function ensureOptionIds() {
  const scene = sceneStore.currentScene;
  if (!scene?.dia) return;
  let seq = 1;
  const walk = (dias) => {
    dias.forEach(d => {
      if (Array.isArray(d.opt)) {
        d.opt.forEach(o => { if (!o.__oid) o.__oid = `oid-${d.id}-${seq++}`; });
      }
      if (Array.isArray(d.opt)) d.opt.forEach(o => walk(o.dia || []));
    });
  };
  walk(scene.dia);
}

onMounted(() => { ensureOptionIds(); });
watch(() => sceneStore.currentScene, () => { ensureOptionIds(); }, { deep: true });
// 在项目切换或首次进入时加载角色
watch(() => projectStore.currentProject, (p) => { characterStore.load(p); }, { immediate: true });

function onDragEndOptions(evt, d) {
  saveAfterDrag(evt);
}
</script>

<style scoped>
.dialogue-tree {
  font-size: 14px;
  flex: 1;
  overflow-y: auto;
  padding-right: 5px;
}

.tree-node-wrapper {
  transition: background-color 0.3s;
  margin: 8px 0;
}

.tree-node {
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  box-shadow: 0 0 0 1px var(--spark-border);
  background-color: var(--spark-panel-bg);
  color: var(--spark-text);
}

.dialogue-node {
  border-left: 3px solid var(--node-dialogue);
}

.option-node {
  border-left: 3px solid var(--node-option);
  margin-left: 20px;
}

.tree-node.selected {
  box-shadow: 0 0 0 2px var(--node-border-selected) !important;
  background-color: var(--spark-primary-glow);
}

.tree-node:hover {
  box-shadow: 0 0 0 1px var(--node-border-selected);
}

.tree-node:deep(.n-card__content) {
  padding: 8px 12px !important;
}

.node-children {
  margin-left: 30px;
  position: relative;
}

.node-children::before {
  content: '';
  position: absolute;
  top: 0;
  left: -15px;
  height: 100%;
  border-left: 1px dashed rgba(128, 128, 128, 0.3);
}

.node-title {
  font-weight: bold;
  margin-bottom: 4px;
}

.node-preview {
  margin-top: 4px;
  line-height: 1.4;
  opacity: 0.85;
}

.badges {
  margin-top: 8px;
}

.sortable-ghost {
  opacity: 0.3;
  background: rgba(52, 152, 219, 0.1);
}

.sortable-chosen {
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.2);
}

.sortable-drag {
  opacity: 0.8;
  transform: rotate(2deg);
}

/* 深色模式下增强对话内容可见性 */
:global(body.dark-mode) .node-preview {
  opacity: 1;
}

:global(body.dark-mode) .node-title {
  opacity: 0.95;
}

/* Naive UI 会自动处理大部分深浅色主题 */
</style>