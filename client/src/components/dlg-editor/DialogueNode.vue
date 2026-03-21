<template>
  <div class="tree-node-wrapper">
    <n-card 
      class="tree-node dialogue-node dialogue-handle" 
      :class="{ selected: isSelected, 'narrator-node': characterName === '旁白' }" 
      size="small"
      hoverable
      @click.stop="$emit('select', node, parent)"
    >
      <div class="node-content">
        <div class="node-title">
          <n-text strong>ID: {{ node.id }}</n-text>
          <n-text depth="3" v-if="characterName === '旁白'"> [旁白]</n-text>
          <n-text depth="3" v-else> | 角色: {{ characterName }}</n-text>
        </div>
        <div class="node-preview">
          <n-ellipsis :line-clamp="2">{{ node.txt }}</n-ellipsis>
        </div>
        <n-space v-if="hasAnyBadge" size="small" class="badges">
          <n-tag v-if="node.opt?.length" type="success" size="small" :bordered="false">
            选项: {{ node.opt.length }}
          </n-tag>
          <n-tag v-for="(val, key) in node.act" :key="key" type="warning" size="small" :bordered="false" :title="Array.isArray(val) ? val.join(', ') : val">
            {{ key }}
          </n-tag>
          <n-button 
            v-if="isSelected"
            size="tiny" 
            type="warning" 
            ghost 
            circle
            @click.stop="$emit('add-act', node)"
          >
            <template #icon>+</template>
          </n-button>
          <n-tag v-if="node.next" type="info" size="small" :bordered="false">
            跳转至: {{ node.next }}
          </n-tag>
        </n-space>
      </div>
    </n-card>

    <Draggable
      v-if="node.opt?.length"
      class="node-children options-list"
      v-model="node.opt"
      item-key="__oid"
      :group="{ name: 'options-' + node.id, pull: false, put: false }"
      :animation="150"
      handle=".option-handle"
      @end="$emit('drag-end', $event, node)"
    >
      <template #item="{ element: o }">
        <div class="tree-node-wrapper">
          <n-card 
            class="tree-node option-node option-handle" 
            :class="{ selected: isSelectedOption(o) }" 
            size="small"
            hoverable
            @click.stop="$emit('select-option', o, node)"
          >
            <div class="node-content">
              <div class="node-title">
                <n-text type="success" strong>📝 选项: {{ o.optn }}</n-text>
              </div>
            </div>
          </n-card>
          
          <Draggable
            v-if="o.dia?.length"
            class="node-children"
            v-model="o.dia"
            item-key="id"
            :group="{ name: 'child-' + getOptionKey(o), pull: false, put: false }"
            :animation="150"
            handle=".dialogue-handle"
            @end="$emit('drag-end', $event, o)"
          >
            <template #item="{ element: sd }">
              <DialogueNode 
                :node="sd" 
                :parent="o"
                :selected-node="selectedNode"
                :selection-type="selectionType"
                :character-map="characterMap"
                @select="(n, p) => $emit('select', n, p)"
                @select-option="(opt, n) => $emit('select-option', opt, n)"
                @drag-end="(e, target) => $emit('drag-end', e, target)"
                @add-act="(n) => $emit('add-act', n)"
              />
            </template>
          </Draggable>
        </div>
      </template>
    </Draggable>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { NCard, NText, NTag, NSpace, NEllipsis, NButton } from 'naive-ui';
import Draggable from 'vuedraggable';

const props = defineProps({
  node: Object,
  parent: Object,
  selectedNode: Object,
  selectionType: String,
  characterMap: Object
});

defineEmits(['select', 'select-option', 'drag-end', 'add-act']);

const characterName = computed(() => {
  if (Number(props.node.chr) === -1) return '旁白';
  const name = props.characterMap?.[Number(props.node.chr)];
  return name || props.node.chr || '';
});

const isSelected = computed(() => props.selectionType === 'dialogue' && props.selectedNode === props.node);
const isSelectedOption = (o) => props.selectionType === 'option' && props.selectedNode === o;
const hasAnyBadge = computed(() => (props.node?.opt?.length) || (props.node?.act && Object.keys(props.node.act).length) || props.node?.next);

const getOptionKey = (option) => {
  const idx = props.node.opt?.indexOf(option) ?? -1;
  return `${props.node.id}-${idx}-${option.optn || 'opt'}`;
};
</script>

<style scoped>
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
  z-index: 1;
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

/* 递归层级的虚线连接 */
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
  color: var(--spark-primary);
}

.node-preview {
  margin-top: 4px;
  line-height: 1.4;
  opacity: 0.95;
  color: var(--spark-text);
}

.narrator-node {
  background-color: color-mix(in srgb, var(--spark-primary) 8%, transparent) !important;
}

.badges {
  margin-top: 8px;
}

/* 拖拽态样式 */
.sortable-ghost {
  opacity: 0.3;
  background: rgba(52, 152, 219, 0.1);
}
.sortable-drag {
  opacity: 0.8;
  transform: rotate(2deg);
}

:global(body.dark-mode) .node-preview {
  opacity: 1;
}
</style>
