<template>
  <div id="dialogue-tree" class="dialogue-tree">
    <div v-if="!sceneStore.currentScene" class="dialogue-tree-empty">
      <div class="empty-scene-illustration">
        <!-- 精致电影场记板与Spark微光场景分镜插画 -->
        <svg class="empty-scene-svg" viewBox="0 0 200 160" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <defs>
            <!-- 柔和聚光光晕 -->
            <radialGradient id="empty-scene-glow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stop-color="var(--spark-primary)" stop-opacity="0.22" />
              <stop offset="55%" stop-color="var(--spark-primary)" stop-opacity="0.05" />
              <stop offset="100%" stop-color="transparent" stop-opacity="0" />
            </radialGradient>
            <!-- 画板玻璃质感渐变 -->
            <linearGradient id="empty-card-bg" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="var(--spark-panel-bg, #ffffff)" stop-opacity="0.9" />
              <stop offset="100%" stop-color="var(--spark-panel-header-bg, #f8f9fa)" stop-opacity="0.5" />
            </linearGradient>
            <!-- 边框高光渐变 -->
            <linearGradient id="empty-card-border" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="var(--spark-primary)" stop-opacity="0.65" />
              <stop offset="50%" stop-color="var(--spark-border)" stop-opacity="0.5" />
              <stop offset="100%" stop-color="var(--spark-primary)" stop-opacity="0.2" />
            </linearGradient>
            <!-- 阴影滤镜 -->
            <filter id="empty-card-shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="rgba(0,0,0,0.06)" />
            </filter>
          </defs>

          <!-- 1. 背景聚光光晕 -->
          <circle cx="100" cy="80" r="76" fill="url(#empty-scene-glow)" />

          <!-- 2. 后景场景分镜卡片 (景深透视) -->
          <g transform="rotate(-6 100 80)" opacity="0.45">
            <rect x="52" y="32" width="96" height="72" rx="10" fill="url(#empty-card-bg)" stroke="url(#empty-card-border)" stroke-width="1.2" stroke-dasharray="3 3" />
            <line x1="64" y1="46" x2="88" y2="46" stroke="var(--spark-text-muted)" stroke-width="2" stroke-linecap="round" opacity="0.3" />
            <line x1="64" y1="56" x2="132" y2="56" stroke="var(--spark-text-muted)" stroke-width="1.5" stroke-linecap="round" opacity="0.2" />
            <line x1="64" y1="66" x2="116" y2="66" stroke="var(--spark-text-muted)" stroke-width="1.5" stroke-linecap="round" opacity="0.2" />
          </g>

          <!-- 3. 前景电影场记板 / 场景主卡片 -->
          <g filter="url(#empty-card-shadow)">
            <rect x="42" y="44" width="116" height="82" rx="12" fill="url(#empty-card-bg)" stroke="url(#empty-card-border)" stroke-width="1.5" />
            
            <!-- 场记板顶部斜条纹栏 -->
            <path d="M42 56 C42 49.37 47.37 44 54 44 L146 44 C152.63 44 158 49.37 158 56 L158 60 L42 60 Z" fill="color-mix(in srgb, var(--spark-primary) 12%, var(--spark-panel-bg, #fff))" />
            <line x1="42" y1="60" x2="158" y2="60" stroke="var(--spark-border)" stroke-width="1" />
            <!-- 斜纹装饰 -->
            <path d="M58 44 L50 60 M78 44 L70 60 M98 44 L90 60 M118 44 L110 60 M138 44 L130 60" stroke="var(--spark-primary)" stroke-width="2" stroke-linecap="round" opacity="0.45" />

            <!-- 取景框中心准心 [+] -->
            <circle cx="100" cy="90" r="16" stroke="var(--spark-primary)" stroke-width="1" stroke-dasharray="2 3" opacity="0.35" />
            <line x1="100" y1="80" x2="100" y2="100" stroke="var(--spark-primary)" stroke-width="1.2" stroke-linecap="round" opacity="0.55" />
            <line x1="90" y1="90" x2="110" y2="90" stroke="var(--spark-primary)" stroke-width="1.2" stroke-linecap="round" opacity="0.55" />

            <!-- 场景剧本文本线模拟 -->
            <rect x="56" y="70" width="32" height="4" rx="2" fill="var(--spark-primary)" opacity="0.45" />
            <line x1="56" y1="110" x2="144" y2="110" stroke="var(--spark-border)" stroke-width="1.5" stroke-linecap="round" />
            <line x1="56" y1="117" x2="112" y2="117" stroke="var(--spark-border)" stroke-width="1.5" stroke-linecap="round" opacity="0.6" />
          </g>

          <!-- 4. Spark 核心灵感火花（漂浮在右上角） -->
          <g class="empty-spark-main">
            <!-- 大四角星 -->
            <path d="M144 28 L147 38 L157 41 L147 44 L144 54 L141 44 L131 41 L141 38 Z" fill="var(--spark-primary)" />
            <!-- 星芒发光点 -->
            <circle cx="144" cy="41" r="2.5" fill="#fff" opacity="0.9" />
          </g>

          <!-- 5. 漂浮小星火粒子 -->
          <circle cx="46" cy="36" r="1.5" fill="var(--spark-primary)" opacity="0.75" class="empty-spark-dot-1" />
          <path d="M54 126 L55.5 130.5 L60 132 L55.5 133.5 L54 138 L52.5 133.5 L48 132 L52.5 130.5 Z" fill="var(--spark-primary)" opacity="0.5" class="empty-spark-dot-2" />
          <circle cx="158" cy="116" r="2" fill="var(--spark-primary)" opacity="0.6" class="empty-spark-dot-3" />
        </svg>
        
        <div class="empty-scene-title">{{ t('views.scriptWriter.desktop.noSceneSelected') || '请选择一个场景' }}</div>
        <div class="empty-scene-subtitle">{{ t('views.scriptWriter.desktop.noFileSubtitle') || '从左侧作品管理器选择章节或剧本后开始创作' }}</div>
      </div>
    </div>
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
          <DialogueNode 
            :node="d"
            :parent="null"
            :selected-node="sceneStore.currentNode"
            :selection-type="sceneStore.selectionType"
            :character-map="characterStore.map"
            @select="selectDialogue"
            @select-option="selectOption"
            @drag-end="saveAfterDrag"
            @add-act="onAddAct"
          />
        </template>
      </Draggable>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useSceneStore } from '@/components/stores/sceneStore';
import Draggable from 'vuedraggable';
import { useProjectStore } from '@/components/stores/projectStore';
import { useFileStore } from '@/components/stores/fileStore';
import { useCharacterStore } from '@/components/stores/characterStore';
import DialogueNode from './DialogueNode.vue';
import bus from '@/eventBus';

const { t } = useI18n();
const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const characterStore = useCharacterStore();

function onAddAct(node) {
  selectDialogue(node, null);
  // 延迟一点确保 NodeEditor 已更新
  setTimeout(() => {
    bus.emit('focus-act-input');
  }, 50);
}

function selectDialogue(d, parent = null) {
  if (typeof sceneStore.selectDialogue === 'function') {
    sceneStore.selectDialogue(d, parent);
  } else {
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

// 允许任意对话节点拖拽
function onMove(evt) {
  try {
    const el = evt?.draggedContext?.element;
    return !!el; 
  } catch { return true; }
}

function saveAfterDrag(evt) {
  if (!fileStore.selectedFile?.path || !projectStore.currentProject) return;
  if (evt && evt.oldIndex === evt.newIndex) return;
  sceneStore.scheduleStorySave({ boundary: true });
}

function onDragEndRoot(evt) {
  saveAfterDrag(evt);
}

onMounted(() => {
  // 项目初始加载时确保角色列表已就绪
  if (projectStore.currentProject) {
    characterStore.load(projectStore.currentProject);
  }
});

// 在项目切换或首次进入时加载角色
watch(() => projectStore.currentProject, (p) => { characterStore.load(p); }, { immediate: true });

function onDragEndOptions(evt, d) {
  saveAfterDrag(evt);
}
</script>

<style scoped>
.dialogue-tree {
  font-size: var(--spark-fs-base);
  flex: 1;
  overflow-y: auto;
  padding-right: 5px;
}

.dialogue-tree-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
  height: 100%;
  padding: 32px 16px;
}

.empty-scene-illustration {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  max-width: 360px;
  user-select: none;
}

.empty-scene-svg {
  width: 160px;
  height: 128px;
  margin-bottom: 12px;
  filter: drop-shadow(0 4px 16px rgba(var(--spark-primary-rgb), 0.08));
}

.empty-spark-main {
  transform-origin: 144px 41px;
  animation: spark-float-pulse 3s ease-in-out infinite;
}

.empty-spark-dot-1 {
  animation: spark-fade-dot 2.4s ease-in-out infinite alternate;
}

.empty-spark-dot-2 {
  animation: spark-float-dot 3.6s ease-in-out infinite alternate;
}

.empty-spark-dot-3 {
  animation: spark-fade-dot 2.8s ease-in-out infinite 0.5s alternate;
}

@keyframes spark-float-pulse {
  0%, 100% {
    transform: translateY(0) scale(1);
    opacity: 0.95;
  }
  50% {
    transform: translateY(-4px) scale(1.08);
    opacity: 1;
  }
}

@keyframes spark-fade-dot {
  0% {
    opacity: 0.3;
    transform: scale(0.85);
  }
  100% {
    opacity: 0.85;
    transform: scale(1.15);
  }
}

@keyframes spark-float-dot {
  0% {
    transform: translate(0, 0);
    opacity: 0.35;
  }
  100% {
    transform: translate(2px, -3px);
    opacity: 0.75;
  }
}

.empty-scene-title {
  font-size: var(--spark-fs-base, 15px);
  font-weight: 600;
  color: var(--spark-text);
  margin-bottom: 6px;
  letter-spacing: 0.5px;
}

.empty-scene-subtitle {
  font-size: var(--spark-fs-xs, 12px);
  color: var(--spark-text-muted);
  line-height: 1.6;
  max-width: 280px;
}

.sortable-ghost {
  opacity: 0.3;
  background: rgba(52, 152, 219, 0.1);
}

.sortable-drag {
  opacity: 0.8;
  transform: rotate(2deg);
}
</style>
