<template>
  <div id="dialogue-tree" class="dialogue-tree">
    <div v-if="!sceneStore.currentScene" class="no-selection">请选择一个场景</div>
    <template v-else>
      <Draggable
        v-model="sceneStore.currentScene.dia"
        item-key="id"
        :group="{ name: 'root', pull: false, put: false }"
        :animation="150"
        handle=".tree-node"
        :move="onMove"
        @end="onDragEndRoot"
      >
        <template #item="{ element: d }">
          <div class="tree-node-wrapper">
            <div class="tree-node dialogue-node" :class="{ selected: isSelectedDialogue(d) }" @click="selectDialogue(d)">
              <div class="node-content">
                <div class="node-title">ID: {{ d.id }}, 角色: {{ d.chr }}</div>
                <div class="node-preview">{{ d.txt }}</div>
                <div class="badges" v-if="hasAnyBadge(d)">
                  <span v-if="d.opt && d.opt.length" class="badge badge-options">选项个数: {{ d.opt.length }}</span>
                  <span v-if="d.act && Object.keys(d.act).length" class="badge badge-act">行为</span>
                  <span v-if="d.next" class="badge badge-next">跳转至: {{ d.next }}</span>
                </div>
              </div>
            </div>
            <div v-if="d.opt && d.opt.length" class="node-children">
              <div v-for="o in d.opt" :key="optionKey(d, o)" class="tree-node-wrapper">
                <div class="tree-node option-node" :class="{ selected: isSelectedOption(o) }" @click.stop="selectOption(o, d)">
                  <div class="node-content">
                    <div class="node-title">选项: {{ o.optn }}</div>
                  </div>
                </div>
                <Draggable
                  v-if="o.dia && o.dia.length"
                  class="node-children"
                  v-model="o.dia"
                  item-key="id"
                  :group="{ name: 'child-' + optionKey(d, o), pull: false, put: false }"
                  :animation="150"
                  handle=".tree-node"
                  :move="onMove"
                  @end="(evt) => onDragEndOption(evt, o)"
                >
                  <template #item="{ element: sd }">
                    <div class="tree-node-wrapper">
                      <div class="tree-node dialogue-node" :class="{ selected: isSelectedDialogue(sd) }" @click.stop="selectDialogue(sd, o)">
                        <div class="node-content">
                          <div class="node-title">ID: {{ sd.id }}, 角色: {{ sd.chr }}</div>
                          <div class="node-preview">{{ sd.txt }}</div>
                          <div class="badges" v-if="hasAnyBadge(sd)">
                            <span v-if="sd.opt && sd.opt.length" class="badge badge-options">选项个数: {{ sd.opt.length }}</span>
                            <span v-if="sd.act && Object.keys(sd.act).length" class="badge badge-act">行为</span>
                            <span v-if="sd.next" class="badge badge-next">跳转至: {{ sd.next }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </template>
                </Draggable>
              </div>
            </div>
          </div>
        </template>
      </Draggable>
    </template>
  </div>
  
</template>

<script setup>
import { computed } from 'vue';
import { useSceneStore } from '@/stores/sceneStore';
import Draggable from 'vuedraggable';
import { useProjectStore } from '@/stores/projectStore';
import { useFileStore } from '@/stores/fileStore';
import { saveStory } from '@/services/api';

const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();

const dialogueData = computed(() => sceneStore.currentScene?.dia || []);

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

// 仅允许选中的节点才可拖拽
function onMove(evt) {
  try {
    const el = evt?.draggedContext?.element;
    if (!el) return false;
    if (sceneStore.selectionType !== 'dialogue') return false;
    return sceneStore.currentNode === el;
  } catch { return false; }
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
</script>

<style scoped>
.badges { display: flex; gap: 6px; margin-top: 4px; flex-wrap: wrap; }
.badge { display: inline-block; padding: 2px 6px; border-radius: 10px; font-size: 12px; line-height: 1; }
.badge-options { background: #eaf9f0; color: #1e8449; border: 1px solid #a9e5bf; }
.badge-act { background: #fff4e6; color: #b9770e; border: 1px solid #f5c37a; }
/* next 标签需要是紫色 */
.badge-next { background: #f2e6ff; color: #6c2db5; border: 1px solid #cdb3ee; }
</style>