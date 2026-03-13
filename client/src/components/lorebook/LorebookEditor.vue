<template>
  <div id="settings-editor-container" class="settings-editor-container" :class="{ 'is-embedded': embedded }">
    <div class="lorebook-content">
      <!-- 世界观设定 -->
      <div class="lorebook-card-wrap">
        <GlobalLoading scope="world" target="worldview" variant="card" />
        <n-card 
          title="世界观设定" 
          :segmented="{ content: true }"
          :bordered="false"
          size="small"
          class="lorebook-card"
        >
          <template #header-extra>
            <n-icon :component="GlobeOutline" size="20" />
          </template>
          
          <n-input 
            v-model:value="worldview" 
            @input="onWorldviewInput" 
            type="textarea"
            :autosize="{ minRows: 6, maxRows: 15 }"
            placeholder="在这里描述你的故事世界..."
            class="full-width-input"
          />
          
          <template #action>
            <n-button type="primary" @click="saveWorldview" strong block>
              <template #icon>
                <n-icon :component="SaveOutline" />
              </template>
              保存世界观
            </n-button>
          </template>
        </n-card>
      </div>

      <!-- 角色设定 -->
      <div class="lorebook-card-wrap">
        <GlobalLoading scope="world" target="characters" variant="card" />
        <n-card 
          title="角色设定" 
          :segmented="{ content: true }"
          :bordered="false"
          size="small"
          class="lorebook-card"
        >
          <template #header-extra>
            <n-icon :component="PeopleOutline" size="20" />
          </template>

          <n-space vertical :size="12" class="full-width-space">
            <!-- 添加角色 -->
            <n-input-group>
              <n-input 
                v-model:value="newCharacterName" 
                placeholder="新角色名称"
                @keydown.enter="addCharacter"
                clearable
              >
                <template #prefix>
                  <n-icon :component="PersonAddOutline" />
                </template>
              </n-input>
              <n-button type="primary" @click="addCharacter" strong>
                <template #icon>
                  <n-icon :component="AddOutline" />
                </template>
                添加
              </n-button>
            </n-input-group>

            <!-- 角色列表 -->
            <div class="character-grid" style="margin-top: 16px">
              <n-card
                v-for="ch in characters"
                :key="ch.id"
                size="small"
                hoverable
              >
                <template #header>
                  <span style="font-weight: 600;">{{ ch.id === -1 ? '旁白' : (ch.name || `角色 ${ch.id}`) }}</span>
                </template>
                <template #header-extra>
                  <n-icon :component="PersonCircleOutline" />
                </template>

                <n-input
                  v-model:value="ch.content"
                  @input="onCharacterInput(ch)"
                  type="textarea"
                  :autosize="{ minRows: 4, maxRows: 10 }"
                  :placeholder="ch.id === -1 ? '这是旁白角色，用于叙述和场景描述' : '角色设定...'"
                  :disabled="ch.id === -1"
                />

                <template #action>
                  <n-space :size="8">
                    <n-button size="small" type="primary" @click="saveCharacter(ch)" :disabled="ch.id === -1">
                      <template #icon>
                        <n-icon :component="SaveOutline" />
                      </template>
                    </n-button>
                    <n-button size="small" @click="renameCharacter(ch)" :disabled="ch.id === -1">
                      <template #icon>
                        <n-icon :component="CreateOutline" />
                      </template>
                    </n-button>
                    <n-popconfirm
                      v-if="ch.id !== -1"
                      @positive-click="deleteCharacter(ch)"
                      positive-text="删除"
                      negative-text="取消"
                    >
                      <template #trigger>
                        <n-button size="small" type="error">
                          <template #icon>
                            <n-icon :component="TrashOutline" />
                          </template>
                        </n-button>
                      </template>
                      <template #default>
                        确定要删除角色 "{{ ch.name || `角色 ${ch.id}` }}" 吗？
                      </template>
                    </n-popconfirm>
                    <n-button v-else size="small" type="error" disabled>
                      <template #icon>
                        <n-icon :component="TrashOutline" />
                      </template>
                    </n-button>
                  </n-space>
                </template>
              </n-card>
            </div>
          </n-space>
        </n-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed, onActivated, watch } from 'vue';
import { useRoute } from 'vue-router';
import { NCard, NInput, NButton, NIcon, NSpace, NInputGroup, NPopconfirm } from 'naive-ui';
import { GlobeOutline, PeopleOutline, SaveOutline, PersonAddOutline, AddOutline, PersonCircleOutline, CreateOutline, TrashOutline } from '@vicons/ionicons5';
import bus from '../../eventBus';
import GlobalLoading from '../share/GlobalLoading.vue';
import { useProjectStore } from '../stores/projectStore';
import { useFileStore } from '../stores/fileStore';
import { fetchWithAuth, fetchCharacters, createCharacter, saveCharacter as saveCharacterApi, renameCharacter as renameCharacterApi, deleteCharacter as deleteCharacterApi } from '../../services/api';
import { AUTO_SAVE_DEBOUNCE_TIME } from '../../config';

const projectStore = useProjectStore();
const fileStore = useFileStore();
const route = useRoute();

defineProps({
  embedded: {
    type: Boolean,
    default: false
  }
});

const worldview = ref('');
const characters = ref([]); // [{id, name, content}]
const newCharacterName = ref('');
const autoSaveEnabled = computed(() => localStorage.getItem('autoSaveEnabled') === 'true');

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
    if (res.ok && result?.success !== false) bus.emit('toast', { message: '保存成功', type: 'success' });
  } catch {}
}

let worldviewTimer = null;
function onWorldviewInput() {
  clearTimeout(worldviewTimer);
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

// 添加角色
async function addCharacter() {
  const name = newCharacterName.value.trim();
  if (!name) return;
  try {
    await createCharacter(projectStore.currentProject, name);
    newCharacterName.value = '';
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
      title: '重命名角色',
      message: '请输入新的角色名称：',
      defaultValue: ch.name || '',
      resolve
    });
  });
  if (newName === null || newName === ch.name) return;
  try {
    await renameCharacterApi(projectStore.currentProject, ch.id, newName);
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
    bus.emit('toast', { type: 'success', message: '角色已删除' });
  } catch {
    bus.emit('toast', { type: 'error', message: '删除失败' });
  }
}

// 输入防抖自动保存角色
const timers = new Map();
function onCharacterInput(ch) {
  const key = ch.id;
  clearTimeout(timers.get(key));
  const t = setTimeout(() => {
    if (autoSaveEnabled.value) saveCharacter(ch);
  }, AUTO_SAVE_DEBOUNCE_TIME);
  timers.set(key, t);
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
    const parsed = parseCharacterStreamPayload(streamBuffer, prev.name || `角色 ${charId}`);
    
    // 直接修改对象属性，触发响应式更新
    prev.name = parsed.name;
    prev.content = parsed.content;
    prev.streamBuffer = streamBuffer;
  } else {
    // 新角色，初始化
    const streamBuffer = bufferData.buffer;
    const parsed = parseCharacterStreamPayload(streamBuffer, `角色 ${charId}`);
    
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
}

.lorebook-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
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
.settings-editor-container :deep(.lorebook-card .n-card__content),
.settings-editor-container :deep(.lorebook-card .n-card__action) {
  border-radius: 0 !important;
  background: transparent !important;
}

.full-width-input {
  width: 100%;
}

.full-width-space {
  width: 100%;
}

.character-grid {
  display: grid;
  /* 基础设为 3 列 */
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  width: 100%;
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
  padding: 0 4px;
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