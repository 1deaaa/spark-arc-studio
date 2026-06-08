<template>
  <div id="settings-editor-container" class="settings-editor-container" :class="{ 'is-embedded': embedded }">
    <div class="lorebook-content">
      <!-- 世界观设定 -->
      <div class="lorebook-card-wrap worldview-wrap">
        <GlobalLoading scope="world" target="worldview" variant="card" />
        <n-card 
          :segmented="{ content: true }"
          :bordered="false"
          size="small"
          class="lorebook-card worldview-card"
        >
          
          <n-input 
            v-model:value="worldview" 
            @input="onWorldviewInput" 
            type="textarea"
            class="full-width-input worldview-input"
            :placeholder="t('components.lorebookEditor.worldviewPlaceholder')"
          />
        </n-card>
      </div>

      <!-- 角色设定 -->
      <div class="lorebook-card-wrap character-wrap">
        <GlobalLoading scope="world" target="characters" variant="card" />
        <n-card 
          :segmented="{ content: true }"
          :bordered="false"
          size="small"
          class="lorebook-card character-section-card"
        >

          <div class="character-section">
            <!-- 角色列表 -->
            <div class="character-grid">
              <n-card
                v-for="(ch, index) in characters"
                :key="ch.id"
                size="small"
                hoverable
                class="character-card"
              >
                <template #header>
                  <span class="character-name">{{ ch.id === -1 ? t('components.lorebookEditor.narrator') : (ch.name || t('components.lorebookEditor.characterN', { n: ch.id })) }}</span>
                </template>
                <template #header-extra>
                  <n-space :size="4">
                    <n-button size="tiny" type="primary" @click="saveCharacter(ch)" :disabled="ch.id === -1">
                      <template #icon>
                        <n-icon :component="Save" />
                      </template>
                    </n-button>
                    <n-button size="tiny" @click="renameCharacter(ch)" :disabled="ch.id === -1">
                      <template #icon>
                        <n-icon :component="SquarePen" />
                      </template>
                    </n-button>
                    <n-popconfirm
                      v-if="ch.id !== -1"
                      @positive-click="deleteCharacter(ch)"
                      :positive-text="t('common.delete')"
                      :negative-text="t('common.cancel')"
                    >
                      <template #trigger>
                        <n-button size="tiny" type="error">
                          <template #icon>
                            <n-icon :component="Trash" />
                          </template>
                        </n-button>
                      </template>
                      <template #default>
                        {{ t('components.lorebookEditor.confirmDeleteCharacter', { name: ch.name || t('components.lorebookEditor.characterN', { n: ch.id }) }) }}
                      </template>
                    </n-popconfirm>
                    <n-button v-else size="tiny" type="error" disabled>
                      <template #icon>
                        <n-icon :component="Trash" />
                      </template>
                    </n-button>
                    <!-- 最后一个角色卡片显示加号按钮 -->
                    <n-button v-if="index === characters.length - 1" size="tiny" type="primary" @click="handleAddCharacter">
                      <template #icon>
                        <n-icon :component="Plus" />
                      </template>
                    </n-button>
                  </n-space>
                </template>

                <StudioSeamlessTextarea
                  v-model:value="ch.content"
                  @input="onCharacterInput(ch)"
                  :placeholder="ch.id === -1 ? t('components.lorebookEditor.narratorPlaceholder') : t('components.lorebookEditor.characterPlaceholder')"
                  :disabled="ch.id === -1"
                  class="character-editor"
                />
              </n-card>
            </div>
          </div>
        </n-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed, onActivated, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';
import { NCard, NInput, NButton, NIcon, NSpace, NPopconfirm } from 'naive-ui';
import { Plus, Save, SquarePen, Trash } from '@lucide/vue';
import StudioSeamlessTextarea from '../editors/StudioSeamlessTextarea.vue';
import bus from '../../eventBus';
import GlobalLoading from '../share/GlobalLoading.vue';
import { useProjectStore } from '../stores/projectStore';
import { useFileStore } from '../stores/fileStore';
import { fetchWithAuth, fetchCharacters, createCharacter, saveCharacter as saveCharacterApi, renameCharacter as renameCharacterApi, deleteCharacter as deleteCharacterApi } from '../../services/api';
import { AUTO_SAVE_DEBOUNCE_TIME } from '../../config';
import { autoSaveEnabled } from '@/utils/autoSaveState';

const projectStore = useProjectStore();
const fileStore = useFileStore();
const route = useRoute();

defineProps({
  embedded: {
    type: Boolean,
    default: false
  }
});

// 暴露方法给父组件
defineExpose({
  saveWorldview
});

const worldview = ref('');
const { t } = useI18n();

const characters = ref([]); // [{id, name, content}]

// 加载世界观
async function loadWorldview() {
  const projectId = projectStore.currentProject;
  const fileId = '世界观.txt';
  if (!projectId || !fileId) return;
  try {
    const res = await fetchWithAuth(`/api/lorebooks/${projectId}/${fileId}`);
    if (res.ok) {
      const data = await res.json();
      worldview.value = data?.content || '';
    } else if (res.status === 404) {
      worldview.value = '';
    }
  } catch {}
}

// 保存世界观
async function saveWorldview() {
  const projectId = projectStore.currentProject;
  const fileId = '世界观.txt';
  if (!projectId || !fileId) return;
  try {
    const res = await fetchWithAuth('/api/lorebooks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName: projectId, fileName: fileId, content: worldview.value })
    });
    const result = await res.json();
    if (res.ok && result?.success !== false) bus.emit('toast', { message: t('components.lorebookEditor.saveSuccess'), type: 'success' });
  } catch {}
}

let worldviewTimer: ReturnType<typeof setTimeout> | null = null;
function onWorldviewInput() {
  if (worldviewTimer) {
    clearTimeout(worldviewTimer);
  }
  worldviewTimer = setTimeout(() => {
    if (autoSaveEnabled.value) saveWorldview();
  }, AUTO_SAVE_DEBOUNCE_TIME);
}

// 加载角色设定
async function loadCharacters() {
  if (!projectStore.currentProject) return;
  try {
    characters.value = await fetchCharacters(projectStore.currentProject, true);
  } catch {
    characters.value = [];
  }
}

// 添加角色（通过弹窗输入名称）
async function handleAddCharacter() {
  const name = await new Promise<string | null>(resolve => {
    bus.emit('prompt', {
      title: t('components.lorebookEditor.addCharacter'),
      message: t('components.lorebookEditor.enterCharacterName'),
      defaultValue: '',
      resolve
    });
  });
  if (!name || !name.trim()) return;
  try {
    await createCharacter(projectStore.currentProject, name.trim());
    await loadCharacters();
    window.dispatchEvent(new CustomEvent('saved'));
  } catch {}
}

// 保存角色
async function saveCharacter(ch) {
  try {
    await saveCharacterApi(projectStore.currentProject, ch.id, ch.content || '');
    window.dispatchEvent(new CustomEvent('saved'));
  } catch {}
}

// 重命名角色
async function renameCharacter(ch) {
  const newName = await new Promise(resolve => {
    bus.emit('prompt', {
      title: t('components.lorebookEditor.renameCharacter'),
      message: t('components.lorebookEditor.enterNewCharacterName'),
      defaultValue: ch.name || '',
      resolve
    });
  });
  const normalizedNewName = typeof newName === 'string' ? newName : null;
  if (normalizedNewName === null || normalizedNewName === ch.name) return;
  try {
    await renameCharacterApi(projectStore.currentProject, ch.id, normalizedNewName);
    await loadCharacters();
    window.dispatchEvent(new CustomEvent('saved'));
  } catch {}
}

// 删除角色
async function deleteCharacter(ch) {
  // n-popconfirm 已经提供确认功能，无需额外确认
  try {
    await deleteCharacterApi(projectStore.currentProject, ch.id);
    await loadCharacters();
    window.dispatchEvent(new CustomEvent('saved'));
    bus.emit('toast', { type: 'success', message: t('components.lorebookEditor.characterDeleted') });
  } catch {
    bus.emit('toast', { type: 'error', message: t('components.lorebookEditor.deleteFailed') });
  }
}

// 输入防抖自动保存角色
const timers = new Map();
function onCharacterInput(ch) {
  const key = ch.id;
  clearTimeout(timers.get(key));
  const timer = setTimeout(() => {
    if (autoSaveEnabled.value) saveCharacter(ch);
  }, AUTO_SAVE_DEBOUNCE_TIME);
  timers.set(key, timer);
}

// 当显示或项目变化时加载数据
// 当显示或项目变化时加载数据
onMounted(() => {
  loadWorldview();
  loadCharacters();
  bus.on('lorebook-refresh', onLorebookRefresh);
  bus.on('character-streamed', onStreamedCharacter);
  bus.on('characters-cleared', onCharactersCleared);
  bus.on('worldview-stream-start', onWorldviewStreamStart);
  bus.on('worldview-stream-chunk', onWorldviewStreamChunk);
  bus.on('worldview-stream-end', onWorldviewStreamEnd);
  bus.on('lorebook-refresh-worldview', onLorebookRefreshWorldview);
  bus.on('lorebook-refresh-characters', onLorebookRefreshCharacters);
});

watch(() => projectStore.currentProject, (nextProject, prevProject) => {
  if (nextProject === prevProject) return;
  loadWorldview();
  loadCharacters();
});

onBeforeUnmount(() => {
  bus.off('lorebook-refresh', onLorebookRefresh);
  bus.off('character-streamed', onStreamedCharacter);
  bus.off('characters-cleared', onCharactersCleared);
  bus.off('worldview-stream-start', onWorldviewStreamStart);
  bus.off('worldview-stream-chunk', onWorldviewStreamChunk);
  bus.off('worldview-stream-end', onWorldviewStreamEnd);
  bus.off('lorebook-refresh-worldview', onLorebookRefreshWorldview);
  bus.off('lorebook-refresh-characters', onLorebookRefreshCharacters);
});

onActivated(() => {
  // Silently refresh data when view is reactivated
  loadWorldview();
  loadCharacters();
});

function onLorebookRefresh() {
  loadWorldview();
  loadCharacters();
}

function onLorebookRefreshWorldview() {
  loadWorldview();
}

function onLorebookRefreshCharacters() {
  loadCharacters();
}

function onWorldviewStreamStart() {
  worldview.value = '';
}

function onWorldviewStreamChunk(payload) {
  const text = payload?.text ?? '';
  if (!text) return;
  worldview.value += text;
}

function onWorldviewStreamEnd() {
  loadWorldview();
}

function onCharactersCleared(payload) {
  try {
    if (!payload || payload.projectName !== projectStore.currentProject) return;
    characters.value = [];
    streamBuffers.clear();
  } catch {}
}

// 流式数据缓冲区：用于减少 Vue 更新频率
const streamBuffers = new Map(); // id -> {buffer, timer}
const UPDATE_INTERVAL = 100; // 每100ms最多更新一次

function extractXmlTagValue(text, tag) {
  const raw = String(text || '');
  const startTag = `<${tag}>`;
  const endTag = `</${tag}>`;
  const start = raw.indexOf(startTag);
  if (start === -1) return null;
  const valueStart = start + startTag.length;
  const end = raw.indexOf(endTag, valueStart);
  if (end === -1) return null;
  return raw.slice(valueStart, end).trim();
}

function extractXmlTagFragment(text, tag) {
  const raw = String(text || '');
  const startTag = `<${tag}>`;
  const endTag = `</${tag}>`;
  const start = raw.indexOf(startTag);
  if (start === -1) return null;
  const valueStart = start + startTag.length;
  const end = raw.indexOf(endTag, valueStart);
  if (end === -1) return raw.slice(valueStart).replace(/^[\r\n]+/, '');
  return raw.slice(valueStart, end).replace(/^[\r\n]+/, '');
}

function parseCharacterStreamPayload(text, fallbackName) {
  const raw = String(text || '');
  const xmlName = extractXmlTagValue(raw, 'name');
  const xmlContent = extractXmlTagFragment(raw, 'content');

  if (xmlName || xmlContent !== null) {
    return {
      name: xmlName || fallbackName,
      content: xmlContent || '',
    };
  }

  const separatorPos = raw.indexOf('\n\n');
  if (separatorPos !== -1) {
    const legacyName = raw.substring(0, separatorPos).trim() || fallbackName;
    const legacyContent = raw.substring(separatorPos + 2);
    return {
      name: legacyName,
      content: legacyContent,
    };
  }

  return {
    name: fallbackName,
    content: raw,
  };
}

// 应用缓冲区的流式内容到 Vue 数据
function applyStreamBuffer(charId) {
  const bufferData = streamBuffers.get(charId);
  if (!bufferData || !bufferData.buffer) return;
  
  const idx = characters.value.findIndex(x => String(x.id) === String(charId));
  
  if (idx >= 0) {
    const prev = characters.value[idx];
    const streamBuffer = (prev.streamBuffer || '') + bufferData.buffer;
    const parsed = parseCharacterStreamPayload(streamBuffer, prev.name || t('components.lorebookEditor.characterN', { n: charId }));
    
    // 直接修改对象属性，触发响应式更新
    prev.name = parsed.name;
    prev.content = parsed.content;
    prev.streamBuffer = streamBuffer;
  } else {
    // 新角色，初始化
    const streamBuffer = bufferData.buffer;
    const parsed = parseCharacterStreamPayload(streamBuffer, t('components.lorebookEditor.characterN', { n: charId }));
    
    characters.value.push({ 
      id: charId, 
      name: parsed.name,
      content: parsed.content,
      streamBuffer: streamBuffer
    });
  }
  
  // 清空缓冲区
  bufferData.buffer = '';
}

// 流式新增：接收 CharacterGeneratorPanel 发出的事件
function onStreamedCharacter(payload) {
  try {
    if (!payload || payload.projectName !== projectStore.currentProject) return;
    const ch = payload.character;
    if (!ch || typeof ch.id === 'undefined') return;
    
    // 处理增量内容（来自 character-delta 事件）
    if (typeof ch.appendContent === 'string') {
      // 获取或创建缓冲区
      let bufferData = streamBuffers.get(ch.id);
      if (!bufferData) {
        bufferData = { buffer: '', timer: null };
        streamBuffers.set(ch.id, bufferData);
      }
      
      // 累加到缓冲区
      bufferData.buffer += ch.appendContent;
      
      // 节流更新：防抖，最后一次更新后才真正应用
      if (bufferData.timer) {
        clearTimeout(bufferData.timer);
      }
      
      bufferData.timer = setTimeout(() => {
        applyStreamBuffer(ch.id);
        bufferData.timer = null;
      }, UPDATE_INTERVAL);
      
      return;
    }
    
    // 非增量更新（来自 character-start/character-streamed/character-end 事件）
    
    // 清空该角色的缓冲区和定时器
    const bufferData = streamBuffers.get(ch.id);
    if (bufferData) {
      if (bufferData.timer) {
        clearTimeout(bufferData.timer);
        bufferData.timer = null;
      }
      // 先应用缓冲区中的内容
      if (bufferData.buffer) {
        applyStreamBuffer(ch.id);
      }
    }
    
    const idx = characters.value.findIndex(x => String(x.id) === String(ch.id));
    
    if (idx >= 0) {
      const prev = characters.value[idx];
      
      // 如果提供了 name，更新 name
      if (ch.name !== undefined && ch.name !== null) {
        prev.name = ch.name || `角色 ${ch.id}`;
      }
      
      // 如果提供了 content，更新 content
      if (ch.content !== undefined && ch.content !== null) {
        prev.content = ch.content;
      }
      
      // 清除流式缓冲（仅在收到 character-end 且有完整 content 时）
      if (ch.content !== undefined) {
        delete prev.streamBuffer;
      }
    } else {
      // 新角色
      const newChar = { 
        id: ch.id, 
        name: ch.name || `角色 ${ch.id}`, 
        content: ch.content || '',
        streamBuffer: ''
      };
      characters.value.push(newChar);
    }
    
  } catch (err) {
    // 静默处理错误
  }
}

</script>

<style scoped>
.lorebook-card-wrap {
  position: relative;
  border-radius: 14px;
  overflow: hidden;
}

.settings-editor-container {
  width: 100%;
  height: 100%;
}

.lorebook-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
  height: 100%;
}

.lorebook-card {
  width: 100%;
  border-radius: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
}

.settings-editor-container :deep(.lorebook-card.n-card) {
  border-radius: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
}

.settings-editor-container :deep(.lorebook-card .n-card__header),
.settings-editor-container :deep(.lorebook-card .n-card-content),
.settings-editor-container :deep(.lorebook-card .n-card__action) {
  border-radius: 0 !important;
  background: transparent !important;
}

.settings-editor-container.is-embedded :deep(.lorebook-card .n-card__header) {
  padding: 0 0 8px !important;
}

.settings-editor-container.is-embedded :deep(.lorebook-card .n-card-content) {
  padding: 0 !important;
}

.settings-editor-container.is-embedded :deep(.lorebook-card .n-card__action) {
  padding: 10px 0 0 !important;
}

.worldview-wrap {
  height: 45%;
  flex-shrink: 0;
}

.worldview-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.worldview-card :deep(.n-card-content) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.worldview-input {
  flex: 1;
  min-height: 0;
}

.worldview-input :deep(.n-input),
.worldview-input :deep(.n-input-wrapper),
.worldview-input :deep(.n-input__textarea),
.worldview-input :deep(.n-input__textarea-el) {
  height: 100% !important;
  min-height: 100% !important;
}

.character-wrap {
  height: 55%;
  flex-shrink: 0;
  overflow: auto;
}

.character-section-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.character-section-card :deep(.n-card-content) {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.character-section {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.full-width-space {
  width: 100%;
}

.character-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-auto-rows: calc(50% - 6px);
  gap: 12px;
  width: 100%;
  flex: 1;
  min-height: 0;
  align-content: start;
}

.character-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.character-card :deep(.n-card-header) {
  padding: 6px 10px !important;
  min-height: 32px;
  flex-shrink: 0;
}

.character-card :deep(.n-card-header__main) {
  font-size: var(--spark-fs-sm);
  line-height: 1.2;
}

.character-name {
  font-weight: 600;
}

.character-card :deep(.n-card-content) {
  padding: 0 !important;
  overflow: auto;
  flex: 1;
  min-height: 0;
}

.character-editor {
  width: 100%;
  height: 100%;
}

.character-editor :deep(.n-input),
.character-editor :deep(.n-input-wrapper),
.character-editor :deep(.n-input__textarea),
.character-editor :deep(.n-input__textarea-el) {
  height: 100% !important;
  min-height: 100% !important;
}

.character-editor :deep(.n-input__textarea-mirror) {
  min-height: 100% !important;
  max-height: 100% !important;
}

/* 窄屏：保持 2 列 */
@media (max-width: 1920px) {
  .character-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.settings-editor-container.is-embedded {
  height: auto;
  overflow: visible;
  padding: 0;
}

.settings-editor-container.is-embedded .lorebook-content {
  padding: 0;
}

/* Force Naive UI components to fill width */
.settings-editor-container :deep(.n-input),
.settings-editor-container :deep(.n-input-wrapper),
.settings-editor-container :deep(.n-input__textarea) {
  width: 100% !important;
}

.settings-editor-container :deep(.n-card) {
  width: 100%;
}

.settings-editor-container :deep(.n-space) {
  width: 100% !important;
  display: flex !important;
}
</style>
