<template>
  <div id="settings-editor-container" class="settings-editor-container" :style="{ display: visible ? 'block' : 'none' }">
    <div class="editor-toolbar" style="display:flex; align-items:center; justify-content:space-between; margin-bottom:10px;">
      <h2 class="toolbar-title" style="margin:0;">设定编辑</h2>
      <div class="toolbar-buttons">
        <button class="btn-secondary" @click="$emit('close')">返回</button>
      </div>
    </div>

    <!-- 世界观设定 -->
    <section class="settings-section">
      <h3>世界观设定</h3>
      <textarea v-model="worldview" @input="onWorldviewInput" placeholder="在这里描述你的故事世界..." />
      <div style="margin-top:10px; display:flex; gap:8px;">
        <button @click="saveWorldview">保存世界观</button>
        <span v-if="autoSaveEnabled" class="autosave-hint">（已启用自动保存）</span>
      </div>
    </section>

    <!-- 角色设定 -->
    <section class="settings-section">
      <h3>角色设定</h3>
      <div style="margin-bottom:10px; display:flex; gap:8px;">
        <input v-model="newCharacterName" placeholder="新角色名称" style="max-width:260px;" />
        <button @click="addCharacter">添加新角色</button>
      </div>

      <div id="character-list">
        <div v-for="ch in characters" :key="ch.id" class="character-item">
          <h5>
            {{ ch.name || ('角色 ' + ch.id) }}
          </h5>
          <textarea v-model="ch.content" @input="onCharacterInput(ch)" rows="5" />
          <div class="button-group">
            <button @click="saveCharacter(ch)">保存</button>
            <button class="btn-secondary" @click="renameCharacter(ch)">重命名</button>
            <button class="btn-danger" @click="deleteCharacter(ch)">删除</button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import bus from '@/eventBus';
import { useProjectStore } from '@/components/stores/projectStore';
import { fetchWithAuth } from '@/services/api';
import { AUTO_SAVE_DEBOUNCE_TIME } from '@/config';

const props = defineProps({ visible: { type: Boolean, default: false } });
const emit = defineEmits(['close']);

const projectStore = useProjectStore();

const worldview = ref('');
const characters = ref([]); // [{id, name, content}]
const newCharacterName = ref('');
const autoSaveEnabled = computed(() => localStorage.getItem('autoSaveEnabled') === 'true');

// 加载世界观
async function loadWorldview() {
  if (!projectStore.currentProject) return;
  try {
    const res = await fetchWithAuth(`/api/worldview/${projectStore.currentProject}`);
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
  if (!projectStore.currentProject) return;
  try {
    const res = await fetchWithAuth('/api/worldview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName: projectStore.currentProject, content: worldview.value })
    });
    const result = await res.json();
    if (res.ok && result?.success !== false) window.dispatchEvent(new CustomEvent('saved'));
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
watch(() => props.visible, (v) => { if (v) { loadWorldview(); loadCharacters(); } }, { immediate: true });
watch(() => projectStore.currentProject, () => { if (props.visible) { loadWorldview(); loadCharacters(); } });

onMounted(() => { if (props.visible) { loadWorldview(); loadCharacters(); } });
</script>