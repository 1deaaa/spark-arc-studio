<template>
  <div class="lorebook-mobile-host">
    <GlobalLoading scope="world" />
    <div class="lorebook-mobile-flow">
      <!-- 世界观输入 -->
      <div class="flow-section">
      <div class="section-header">
        <n-icon :component="GlobeOutline" size="18" />
        <span>世界观设定</span>
      </div>
      <MobileTextArea
        v-model:value="worldview"
        customClass="worldview-input"
        title="世界观设定"
        placeholder="在这里描述你的故事世界..."
        :autosize="{ minRows: 3, maxRows: 7 }"
      />
      <n-button type="primary" block @click="saveWorldview">
        <template #icon><n-icon :component="SaveOutline" /></template>
        保存世界观
      </n-button>
      </div>
    
    <!-- 角色列表 -->
      <div class="flow-section">
      <div class="section-header">
        <n-icon :component="PeopleOutline" size="18" />
        <span>角色设定</span>
        <n-tag type="info" size="small">{{ characters.length }}</n-tag>
      </div>
      
      <n-spin :show="loading">
        <div v-if="characters.length > 0" class="character-list">
          <div 
            v-for="ch in characters.slice(0, 6)" 
            :key="ch.id"
            class="character-card"
            @click="editCharacter(ch)"
          >
            <div class="char-avatar">
              <n-icon :component="PersonCircleOutline" size="24" />
            </div>
            <div class="char-info">
              <div class="char-name">{{ ch.name || `角色 ${ch.id}` }}</div>
              <div class="char-desc">{{ ch.content?.substring(0, 50) || '暂无设定' }}...</div>
            </div>
            <n-icon :component="ChevronForward" size="18" class="char-arrow" />
          </div>
          
          <div v-if="characters.length > 6" class="more-hint" @click="showEditor = true">
            查看全部 {{ characters.length }} 个角色
          </div>
        </div>
        
        <n-empty v-else description="暂无角色设定" style="padding: 20px 0;">
          <template #extra>
            <n-button size="small" type="primary" @click="showEditor = true">
              添加角色
            </n-button>
          </template>
        </n-empty>
      </n-spin>
      </div>
    
    <!-- 快捷工具 -->
      <div class="flow-section">
      <div class="section-header">
        <n-icon :component="ConstructOutline" size="18" />
        <span>快捷工具</span>
      </div>
      
      <div class="action-buttons-row">
        <n-button type="primary" secondary class="action-btn" @click="showCharGen = true">
          <template #icon><n-icon :component="PersonAddOutline" /></template>
          AI 角色生成
        </n-button>
        <n-button type="primary" secondary class="action-btn" @click="showWorldGen = true">
          <template #icon><n-icon :component="GlobeOutline" /></template>
          调整世界观
        </n-button>
      </div>
      </div>
    
    <!-- 完整编辑器抽屉（仅通过快捷工具访问） -->
      <n-drawer v-model:show="showEditor" placement="bottom" height="90%">
      <n-drawer-content title="设定管理" closable>
        <LorebookEditor :visible="true" :embedded="true" @close="showEditor = false" />
      </n-drawer-content>
      </n-drawer>

    <!-- 单一角色编辑器抽屉（点击卡片访问） -->
      <n-drawer v-model:show="showSingleCharDrawer" placement="bottom" height="75%" class="mobile-char-drawer">
      <n-drawer-content :title="editingChar.name || '新角色'" closable>
        <div class="char-editor-form" v-if="editingChar">
           <div class="form-item">
             <label>角色名称</label>
             <n-input v-model:value="editingChar.name" placeholder="输入角色名" size="large" />
           </div>
           
           <div class="form-item">
             <label>详细设定</label>
             <MobileTextArea 
               v-model:value="editingChar.content" 
               title="角色详情设定"
               placeholder="描述角色的外貌、性格、背景故事..." 
               customClass="desc-input"
               :autosize="{ minRows: 4, maxRows: 8 }"
             />
           </div>

           <div class="action-bar">
              <n-button 
                type="error" 
                ghost 
                @click="handleDeleteChar" 
                v-if="editingChar.id !== -1 && editingChar.id"
              >
                删除
              </n-button>
              <div style="flex:1"></div>
              <n-button type="primary" class="brand-btn" @click="saveSingleCharacter">
                <template #icon><n-icon :component="SaveOutline" /></template>
                保存角色
              </n-button>
           </div>
        </div>
      </n-drawer-content>
      </n-drawer>
    
    <!-- 角色生成器抽屉 -->
      <n-drawer v-model:show="showCharGen" placement="bottom" height="80%">
      <n-drawer-content title="AI 角色生成" closable>
        <CharacterGeneratorPanel :visible="true" :embedded="true" />
      </n-drawer-content>
      </n-drawer>

    <!-- 调整世界观抽屉 -->
      <n-drawer v-model:show="showWorldGen" placement="bottom" height="85%">
      <n-drawer-content title="调整世界观" closable>
        <WorldGeneratorPanel />
      </n-drawer-content>
      </n-drawer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, inject, watch, reactive, onBeforeUnmount } from 'vue';
import bus from '../../eventBus';
import { NButton, NIcon, NInput, NSpin, NEmpty, NTag, NDrawer, NDrawerContent, useMessage } from 'naive-ui';
import { 
  GlobeOutline, 
  PeopleOutline, 
  SaveOutline,
  PersonCircleOutline,
  ChevronForward,
  ConstructOutline,
  PersonAddOutline,
  BookOutline,
  ExpandOutline
} from '@vicons/ionicons5';
import LorebookEditor from '../../components/lorebook/LorebookEditor.vue';
import GlobalLoading from '../../components/share/GlobalLoading.vue';
import CharacterGeneratorPanel from '../../components/lorebook/CharacterGeneratorPanel.vue';
import WorldGeneratorPanel from '../../components/lorebook/WorldGeneratorPanel.vue';
import MobileTextArea from '../../components/share/MobileTextArea.vue';
import { fetchWithAuth, fetchCharacters, saveCharacter, deleteCharacter, createCharacter } from '../../services/api';

const message = useMessage();
const projectId = inject('projectId', ref(null));

const loading = ref(false);
const showEditor = ref(false);
const showCharGen = ref(false);
const showWorldGen = ref(false);
const showSingleCharDrawer = ref(false);
const worldview = ref('');
const characters = ref([]);

// 编辑状态
const editingChar = reactive({
  id: null,
  name: '',
  content: ''
});

// 加载世界观
async function loadWorldview() {
  const pid = projectId.value;
  const fileId = '世界观.txt';
  if (!pid) return;
  try {
    const res = await fetchWithAuth(`/api/lorebooks/${pid}/${fileId}`);
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
  const pid = projectId.value;
  const fileId = '世界观.txt';
  if (!pid) return;
  try {
    const res = await fetchWithAuth('/api/lorebooks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName: pid, fileName: fileId, content: worldview.value })
    });
    const result = await res.json();
    if (res.ok && result?.success !== false) {
      message.success('世界观已保存');
    }
  } catch {
    message.error('保存失败');
  }
}

// 加载角色
async function loadCharacters() {
  const pid = projectId.value;
  if (!pid) return;
  loading.value = true;
  try {
    characters.value = await fetchCharacters(pid, true);
  } catch {
    characters.value = [];
  } finally {
    loading.value = false;
  }
}

function openCreateChar() {
  editingChar.id = null; // null for new
  editingChar.name = '';
  editingChar.content = '';
  showSingleCharDrawer.value = true;
}

function editCharacter(ch) {
  editingChar.id = ch.id;
  editingChar.name = ch.name;
  editingChar.content = ch.content;
  showSingleCharDrawer.value = true;
}

// 需要引入 renameCharacter 和 createCharacter
import { renameCharacter } from '../../services/api';

async function saveSingleCharacter() {
  const pid = projectId.value;
  if (!pid) return;
  
  try {
    if (editingChar.id) {
       // Update Content
       await saveCharacter(pid, editingChar.id, editingChar.content || '');
       
       // Check if name changed
       const original = characters.value.find(c => c.id === editingChar.id);
       if (original && original.name !== editingChar.name) {
           await renameCharacter(pid, editingChar.id, editingChar.name);
       }
    } else {
       // Create New
       if (!editingChar.name) {
           message.warning('请输入角色名');
           return;
       }
       // 先创建角色
       await createCharacter(pid, editingChar.name);
       message.success('角色已创建'); 
       
       // 如果有内容，尝试更新内容（需要重新获取ID）
       // 由于API限制，这里最简单的做法是重新加载列表，找到同名角色，然后更新内容
       // 但为了用户体验，我们可以只创建，让用户再次点击编辑内容。
       // 或者：fetchCharacters 获取最新列表，匹配名字，拿到 ID，再 update。
       
       if (editingChar.content) {
          const list = await fetchCharacters(pid, false);
          // 假设没有重名，或取最后一个匹配的
          const created = list.find(c => c.name === editingChar.name);
          if (created) {
             await saveCharacter(pid, created.id, editingChar.content);
          }
       }
    }
    
    // 重新加载列表
    await loadCharacters();
    showSingleCharDrawer.value = false;
    message.success('保存成功');
  } catch (e) {
    message.error('保存失败');
    console.error(e);
  }
}

async function handleDeleteChar() {
    if (!editingChar.id) return;
    try {
        await deleteCharacter(projectId.value, editingChar.id);
        await loadCharacters();
        showSingleCharDrawer.value = false;
        message.success('已删除');
    } catch {
        message.error('删除失败');
    }
}


async function loadData() {
  await Promise.all([loadWorldview(), loadCharacters()]);
}

function onLorebookRefresh() {
  loadData();
}

onMounted(loadData);
onMounted(() => {
  bus.on('lorebook-refresh', onLorebookRefresh);
});

onBeforeUnmount(() => {
  bus.off('lorebook-refresh', onLorebookRefresh);
});
watch(projectId, loadData);
</script>

<style scoped>
/* ... previous styles ... */

.brand-btn {
  background-color: var(--spark-primary);
  border-color: var(--spark-primary);
  color: var(--spark-text-inverse); 
}

.brand-btn:hover, .brand-btn:active {
  background-color: var(--spark-primary-dim);
  border-color: var(--spark-primary-dim);
  color: var(--spark-text-inverse);
}

.char-editor-form {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 8px 0;
}

.form-item label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--spark-text-muted);
  margin-bottom: 8px;
}

.action-bar {
  display: flex;
  align-items: center;
  margin-top: 12px;
}

.lorebook-mobile-flow {
  display: flex;
  flex-direction: column;
  gap: 20px;
  position: relative;
}

.lorebook-mobile-host {
  position: relative;
  width: calc(100% + 32px);
  margin: 0 -16px;
  padding: 16px;
  box-sizing: border-box;
}

.flow-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--spark-primary);
}

.section-header .n-tag {
  margin-left: auto;
}

.character-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.character-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.character-card:active {
  transform: scale(0.98);
  background: rgba(var(--spark-primary-rgb), 0.03);
}

.char-avatar {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, 
    rgba(var(--spark-primary-rgb), 0.15),
    rgba(var(--spark-primary-rgb), 0.08)
  );
  color: var(--spark-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.char-info {
  flex: 1;
  min-width: 0;
}

.char-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--spark-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.char-desc {
  font-size: 12px;
  color: var(--spark-text-muted);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.char-arrow {
  color: var(--spark-text-muted);
  flex-shrink: 0;
}

.more-hint {
  text-align: center;
  padding: 12px;
  font-size: 13px;
  color: var(--spark-primary);
  cursor: pointer;
}

.action-buttons-row {
  display: flex;
  gap: 12px;
}

.action-buttons-row .action-btn {
  flex: 1;
}

/* Custom Textarea Heights */

:deep(.n-input-wrapper),
:deep(.n-input__state-border),
:deep(.n-input__border) {
  height: 100% !important;
}

:deep(.n-input__textarea-el) {
  height: 100% !important;
  overflow-y: auto !important;
}
</style>
