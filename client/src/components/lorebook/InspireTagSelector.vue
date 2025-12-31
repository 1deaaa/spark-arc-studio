<template>
  <div class="inspire-tag-selector">
    <!-- 风格选择 - 点击显示标签面板 -->
    <div class="selector-row">
      <n-popover trigger="click" placement="bottom-start" width="trigger">
        <template #trigger>
          <div class="selector-trigger">
            <span v-if="selectedStyles.length === 0" class="placeholder">选择风格</span>
            <div v-else class="selected-tags">
              <n-tag v-for="s in selectedStyles" :key="s" size="small" type="primary" round closable @close="removeStyle(s)">{{ s }}</n-tag>
            </div>
            <n-icon :component="ChevronDownOutline" class="trigger-icon" />
          </div>
        </template>
        <div class="tag-panel">
          <div class="panel-header">
            <span>风格</span>
            <n-button size="tiny" quaternary @click="showAddStyle = true">
              <template #icon><n-icon :component="AddOutline" /></template>
            </n-button>
          </div>
          <div class="tag-cloud">
            <n-tag
              v-for="tag in allStyleTags"
              :key="tag"
              :type="selectedStyles.includes(tag) ? 'primary' : 'default'"
              :bordered="!selectedStyles.includes(tag)"
              size="small"
              round
              :closable="customTags.styles.includes(tag) && !selectedStyles.includes(tag)"
              @click="selectStyle(tag)"
              @close.stop="removeCustomTag('styles', tag)"
              class="selectable-tag"
            >{{ tag }}</n-tag>
          </div>
        </div>
      </n-popover>
    </div>

    <!-- 题材选择 - 点击显示标签面板 -->
    <div class="selector-row">
      <n-popover trigger="click" placement="bottom-start" width="trigger">
        <template #trigger>
          <div class="selector-trigger">
            <span v-if="selectedGenres.length === 0" class="placeholder">选择题材</span>
            <div v-else class="selected-tags">
              <n-tag v-for="g in selectedGenres.slice(0, 4)" :key="g" size="small" type="success" round closable @close="removeGenre(g)">{{ g }}</n-tag>
              <span v-if="selectedGenres.length > 4" class="more-count">+{{ selectedGenres.length - 4 }}</span>
            </div>
            <n-icon :component="ChevronDownOutline" class="trigger-icon" />
          </div>
        </template>
        <div class="tag-panel">
          <div class="panel-header">
            <span>题材 <span class="hint">(可多选)</span></span>
            <n-button size="tiny" quaternary @click="showAddGenre = true">
              <template #icon><n-icon :component="AddOutline" /></template>
            </n-button>
          </div>
          <div class="tag-cloud">
            <n-tag
              v-for="tag in allGenreTags"
              :key="tag"
              :type="selectedGenres.includes(tag) ? 'success' : 'default'"
              :bordered="!selectedGenres.includes(tag)"
              size="small"
              round
              :closable="customTags.genres.includes(tag) && !selectedGenres.includes(tag)"
              @click="toggleGenre(tag)"
              @close.stop="removeCustomTag('genres', tag)"
              class="selectable-tag"
            >{{ tag }}</n-tag>
          </div>
        </div>
      </n-popover>
    </div>

    <!-- 篇幅建议 -->
    <div class="selector-row length-row">
      <n-radio-group v-model:value="selectedLength" size="small">
        <n-radio-button value="短篇">短篇</n-radio-button>
        <n-radio-button value="中篇">中篇</n-radio-button>
        <n-radio-button value="长篇">长篇</n-radio-button>
      </n-radio-group>
    </div>

    <!-- 添加自定义标签对话框 -->
    <n-modal v-model:show="showAddStyle" preset="dialog" title="添加自定义风格">
      <n-input v-model:value="newStyleTag" placeholder="输入新风格标签" @keyup.enter="addCustomStyle" />
      <template #action>
        <n-button @click="showAddStyle = false">取消</n-button>
        <n-button type="primary" @click="addCustomStyle">添加</n-button>
      </template>
    </n-modal>

    <n-modal v-model:show="showAddGenre" preset="dialog" title="添加自定义题材">
      <n-input v-model:value="newGenreTag" placeholder="输入新题材标签" @keyup.enter="addCustomGenre" />
      <template #action>
        <n-button @click="showAddGenre = false">取消</n-button>
        <n-button type="primary" @click="addCustomGenre">添加</n-button>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { NPopover, NButton, NIcon, NRadioGroup, NRadioButton, NModal, NInput, NTag, useMessage, useDialog } from 'naive-ui';
import { AddOutline, ChevronDownOutline } from '@vicons/ionicons5';
import { fetchWithAuth } from '../../services/api';

const emit = defineEmits(['update:style', 'update:genres', 'update:lengthHint']);

const message = useMessage();
const dialog = useDialog();

// 预设标签
const presetStyles = ['治愈', '悬疑', '恐怖', '奇幻', '科幻', '浪漫', '热血', '致郁', '喜剧', '史诗'];
const presetGenres = ['校园', '都市', '乡村', '末日', '异世界', '穿越', '日常', '冒险', '推理', '战争', '宫廷', '江湖', '赛博朋克'];

// 用户自定义标签
const customTags = ref({ styles: [], genres: [] });

// 合并标签
const allStyleTags = computed(() => [...presetStyles, ...customTags.value.styles]);
const allGenreTags = computed(() => [...presetGenres, ...customTags.value.genres]);

// 选中状态
const selectedStyles = ref([]);
const selectedGenres = ref([]);
const selectedLength = ref(null);

// 添加标签对话框
const showAddStyle = ref(false);
const showAddGenre = ref(false);
const newStyleTag = ref('');
const newGenreTag = ref('');

// 加载用户自定义标签
async function loadCustomTags() {
  try {
    const response = await fetchWithAuth('/api/user/custom-tags');
    if (response.ok) {
      const data = await response.json();
      if (data.success && data.tags) customTags.value = data.tags;
    }
  } catch (e) {
    console.error('Failed to load custom tags:', e);
  }
}

// 保存用户自定义标签
async function saveCustomTags() {
  try {
    await fetchWithAuth('/api/user/custom-tags', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(customTags.value)
    });
  } catch (e) {
    console.error('Failed to save custom tags:', e);
  }
}

function selectStyle(tag) {
  const index = selectedStyles.value.indexOf(tag);
  if (index >= 0) {
    selectedStyles.value.splice(index, 1);
  } else {
    if (selectedStyles.value.length >= 2) {
      dialog.warning({
        title: '风格选择提示',
        content: '同时选中三种或以上风格可能会导致内容倾向混乱，是否继续添加？',
        positiveText: '继续选择',
        negativeText: '取消',
        onPositiveClick: () => { selectedStyles.value.push(tag); }
      });
    } else {
      selectedStyles.value.push(tag);
    }
  }
}

function removeStyle(tag) {
  selectedStyles.value = selectedStyles.value.filter(s => s !== tag);
}

function toggleGenre(tag) {
  const idx = selectedGenres.value.indexOf(tag);
  if (idx >= 0) selectedGenres.value.splice(idx, 1);
  else selectedGenres.value.push(tag);
}

function removeGenre(tag) {
  selectedGenres.value = selectedGenres.value.filter(g => g !== tag);
}

async function addCustomStyle() {
  const tag = newStyleTag.value.trim();
  if (!tag) return;
  if (allStyleTags.value.includes(tag)) { message.warning('标签已存在'); return; }
  customTags.value.styles.push(tag);
  await saveCustomTags();
  newStyleTag.value = '';
  showAddStyle.value = false;
  message.success('已添加自定义风格');
}

async function addCustomGenre() {
  const tag = newGenreTag.value.trim();
  if (!tag) return;
  if (allGenreTags.value.includes(tag)) { message.warning('标签已存在'); return; }
  customTags.value.genres.push(tag);
  await saveCustomTags();
  newGenreTag.value = '';
  showAddGenre.value = false;
  message.success('已添加自定义题材');
}

async function removeCustomTag(type, tag) {
  const idx = customTags.value[type].indexOf(tag);
  if (idx >= 0) {
    customTags.value[type].splice(idx, 1);
    await saveCustomTags();
    if (type === 'styles') selectedStyles.value = selectedStyles.value.filter(s => s !== tag);
    if (type === 'genres') selectedGenres.value = selectedGenres.value.filter(g => g !== tag);
  }
}

// 监听选中状态变化，emit 给父组件
watch(selectedStyles, (val) => emit('update:style', val.length > 0 ? val.join(' + ') : null), { deep: true });
watch(selectedGenres, (val) => emit('update:genres', [...val]), { deep: true });
watch(selectedLength, (val) => emit('update:lengthHint', val));

onMounted(() => { loadCustomTags(); });
</script>

<style scoped>
.inspire-tag-selector {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.selector-row {
  display: flex;
  align-items: center;
}

.selector-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 28px;
  padding: 4px 8px;
  background: var(--spark-input-bg, rgba(255,255,255,0.06));
  border: 1px solid var(--spark-border, rgba(255,255,255,0.1));
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.2s;
}

.selector-trigger:hover {
  border-color: var(--spark-primary, #ffaa40);
}

.selector-trigger .placeholder {
  color: var(--spark-text-muted, #888);
  font-size: 12px;
}

.selector-trigger .selected-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  flex: 1;
}

.selector-trigger .more-count {
  font-size: 11px;
  color: var(--spark-text-muted, #888);
  margin-left: 4px;
}

.selector-trigger .trigger-icon {
  color: var(--spark-text-muted, #888);
  flex-shrink: 0;
  margin-left: 4px;
}

.tag-panel {
  padding: 8px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--spark-text-muted, #888);
}

.panel-header .hint {
  font-size: 10px;
  opacity: 0.7;
}

.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.selectable-tag {
  cursor: pointer;
  transition: all 0.2s ease;
}

.selectable-tag:hover {
  transform: scale(1.05);
}

.length-row {
  margin-top: 4px;
}
</style>
