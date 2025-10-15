<template>
  <div id="settings-editor-container" class="settings-editor-container">
    <n-space vertical :size="16">
      <!-- 世界观设定 -->
      <n-card title="世界观设定" :segmented="{ content: true }">
        <template #header-extra>
          <n-icon :component="GlobeOutline" size="20" />
        </template>
        
        <n-input 
          v-model:value="worldview" 
          @input="onWorldviewInput" 
          type="textarea"
          :autosize="{ minRows: 6, maxRows: 15 }"
          placeholder="在这里描述你的故事世界..."
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

      <!-- 角色设定 -->
      <n-card title="角色设定" :segmented="{ content: true }">
        <template #header-extra>
          <n-icon :component="PeopleOutline" size="20" />
        </template>

        <n-space vertical :size="12">
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
              :title="ch.name || `角色 ${ch.id}`"
              hoverable
            >
              <template #header-extra>
                <n-icon :component="PersonCircleOutline" />
              </template>

              <n-input 
                v-model:value="ch.content" 
                @input="onCharacterInput(ch)" 
                type="textarea"
                :autosize="{ minRows: 4, maxRows: 10 }"
                placeholder="角色设定..."
              />

              <template #action>
                <n-space :size="8">
                  <n-button size="small" type="primary" @click="saveCharacter(ch)">
                    <template #icon>
                      <n-icon :component="SaveOutline" />
                    </template>
                    保存
                  </n-button>
                  <n-button size="small" @click="renameCharacter(ch)">
                    <template #icon>
                      <n-icon :component="CreateOutline" />
                    </template>
                    重命名
                  </n-button>
                  <n-popconfirm 
                    @positive-click="deleteCharacter(ch)"
                    positive-text="删除"
                    negative-text="取消"
                  >
                    <template #trigger>
                      <n-button size="small" type="error">
                        <template #icon>
                          <n-icon :component="TrashOutline" />
                        </template>
                        删除
                      </n-button>
                    </template>
                    确定要删除角色 "{{ ch.name || `角色 ${ch.id}` }}" 吗？
                  </n-popconfirm>
                </n-space>
              </template>
            </n-card>
          </div>
        </n-space>
      </n-card>
    </n-space>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue';
import { useRoute } from 'vue-router';
import { NCard, NInput, NButton, NIcon, NSpace, NInputGroup, NPopconfirm } from 'naive-ui';
import { GlobeOutline, PeopleOutline, SaveOutline, PersonAddOutline, AddOutline, PersonCircleOutline, CreateOutline, TrashOutline } from '@vicons/ionicons5';
import bus from '../../eventBus';
import { useProjectStore } from '../stores/projectStore';
import { useFileStore } from '../stores/fileStore';
import { fetchWithAuth } from '../../services/api';
import { AUTO_SAVE_DEBOUNCE_TIME } from '../../config';

const projectStore = useProjectStore();
const fileStore = useFileStore();
const route = useRoute();

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
    const res = await fetchWithAuth(`/api/character-settings/${projectStore.currentProject}`);
    if (res.ok) {
      characters.value = await res.json();
    } else if (res.status === 404) {
      characters.value = [];
    }
  } catch {
    characters.value = [];
  }
}

// 添加角色
async function addCharacter() {
  const name = newCharacterName.value.trim();
  if (!name) return;
  try {
    const res = await fetchWithAuth('/api/character-settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName: projectStore.currentProject, name })
    });
    const result = await res.json();
    if (res.ok && result?.success !== false) {
      newCharacterName.value = '';
      await loadCharacters();
      window.dispatchEvent(new CustomEvent('saved'));
    }
  } catch {}
}

// 保存角色
async function saveCharacter(ch) {
  try {
    const res = await fetchWithAuth('/api/character-settings/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName: projectStore.currentProject, id: ch.id, content: ch.content || '' })
    });
    const result = await res.json();
    if (res.ok && result?.success !== false) window.dispatchEvent(new CustomEvent('saved'));
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
    const res = await fetchWithAuth('/api/character-settings/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName: projectStore.currentProject, id: ch.id, newName })
    });
    const result = await res.json();
    if (res.ok && result?.success !== false) {
      await loadCharacters();
      window.dispatchEvent(new CustomEvent('saved'));
    }
  } catch {}
}

// 删除角色
async function deleteCharacter(ch) {
  const confirmed = await new Promise(resolve => {
    bus.emit('confirm', {
      title: '删除角色',
      message: '确定要删除这个角色吗？',
      resolve
    });
  });
  if (!confirmed) return;
  try {
    const res = await fetchWithAuth('/api/character-settings/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName: projectStore.currentProject, id: ch.id })
    });
    const result = await res.json();
    if (res.ok && result?.success !== false) {
      await loadCharacters();
      window.dispatchEvent(new CustomEvent('saved'));
    }
  } catch {}
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
onMounted(() => {
  loadWorldview();
  loadCharacters();
});

// 流式新增：接收 CharacterGeneratorPanel 发出的事件，立刻插入到当前列表
function onStreamedCharacter(payload) {
  try {
    if (!payload || payload.projectName !== projectStore.currentProject) return;
    const ch = payload.character;
    if (!ch || typeof ch.id === 'undefined') return;
    const idx = characters.value.findIndex(x => String(x.id) === String(ch.id));
    // 处理增量内容
    if (typeof ch.appendContent === 'string') {
      if (idx >= 0) {
        const prev = characters.value[idx];
        characters.value[idx] = { ...prev, content: (prev.content || '') + ch.appendContent };
      } else {
        characters.value.push({ id: ch.id, name: ch.name || '', content: ch.appendContent });
      }
      return;
    }
    // 非增量：整块更新或插入
    let charToSave;
    if (idx >= 0) {
      characters.value[idx] = { ...characters.value[idx], ...ch };
      charToSave = characters.value[idx];
    } else {
      const newChar = { id: ch.id, name: ch.name || '', content: ch.content || '' };
      characters.value.push(newChar);
      charToSave = newChar;
    }
    // AI 生成角色后自动保存的逻辑已移至 CharacterGeneratorPanel.vue
  } catch {}
}

bus.on('character-streamed', onStreamedCharacter);
onBeforeUnmount(() => { bus.off('character-streamed', onStreamedCharacter); });
</script>

<style scoped>
.character-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

@media (max-width: 768px) {
  .character-grid {
    grid-template-columns: 1fr;
  }
}
</style>