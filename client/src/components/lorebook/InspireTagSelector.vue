<template>
  <div class="inspire-tag-selector">
    <!-- 收纳入口 -->
    <div class="tags-entry" @click="showTags = !showTags">
      <div class="entry-left">
        <n-icon :component="PricetagOutline" size="18" class="entry-icon" />
        <span class="entry-label">故事主题参数</span>
      </div>
      <div class="entry-right">
        <span class="entry-sub" v-if="totalTagsCount > 0">{{ totalTagsCount }} 个参数</span>
        <span class="entry-sub empty" v-else>未选择</span>
        <n-icon :component="ChevronDownOutline" size="16" class="entry-arrow" :class="{ expanded: showTags }" />
      </div>
    </div>

    <!-- 主体容器 (带折叠动画) -->
    <SparkCollapseTransition :show="showTags">
      <div class="selector-container">
      <!-- 标签四维选择：单列布局 -->
      <div class="selector-grid">
    <!-- 风格选择 - 点击显示标签面板 -->
    <div v-if="showStyle" class="selector-row">
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

    <!-- 基调选择 - 点击显示标签面板 -->
    <div class="selector-row">
      <n-popover trigger="click" placement="bottom-start" width="trigger">
        <template #trigger>
          <div class="selector-trigger">
            <span v-if="selectedTones.length === 0" class="placeholder">选择基调</span>
            <div v-else class="selected-tags">
              <n-tag v-for="t in selectedTones" :key="t" size="small" type="warning" round closable @close="removeTone(t)">{{ t }}</n-tag>
            </div>
            <n-icon :component="ChevronDownOutline" class="trigger-icon" />
          </div>
        </template>
        <div class="tag-panel">
          <div class="panel-header">
            <span>基调 <span class="hint">(流派/氛围)</span></span>
            <n-button size="tiny" quaternary @click="showAddTone = true">
              <template #icon><n-icon :component="AddOutline" /></template>
            </n-button>
          </div>
          <div class="tag-cloud">
            <n-tag
              v-for="tag in allToneTags"
              :key="tag"
              :type="selectedTones.includes(tag) ? 'warning' : 'default'"
              :bordered="!selectedTones.includes(tag)"
              size="small"
              round
              :closable="customTags.tones?.includes(tag) && !selectedTones.includes(tag)"
              @click="toggleTone(tag)"
              @close.stop="removeCustomTag('tones', tag)"
              class="selectable-tag"
            >{{ tag }}</n-tag>
          </div>
        </div>
      </n-popover>
    </div>

    <!-- 世界观选择 - 点击显示标签面板 -->
    <div class="selector-row">
      <n-popover trigger="click" placement="bottom-start" width="trigger">
        <template #trigger>
          <div class="selector-trigger">
            <span v-if="selectedWorldviews.length === 0" class="placeholder">选择世界观</span>
            <div v-else class="selected-tags">
              <n-tag v-for="w in selectedWorldviews" :key="w" size="small" type="info" round closable @close="removeWorldview(w)">{{ w }}</n-tag>
            </div>
            <n-icon :component="ChevronDownOutline" class="trigger-icon" />
          </div>
        </template>
        <div class="tag-panel">
          <div class="panel-header">
            <span>世界观 <span class="hint">(设定/规则)</span></span>
            <n-button size="tiny" quaternary @click="showAddWorldview = true">
              <template #icon><n-icon :component="AddOutline" /></template>
            </n-button>
          </div>
          <div class="tag-cloud">
            <n-tag
              v-for="tag in allWorldviewTags"
              :key="tag"
              :type="selectedWorldviews.includes(tag) ? 'info' : 'default'"
              :bordered="!selectedWorldviews.includes(tag)"
              size="small"
              round
              :closable="customTags.worldviews?.includes(tag) && !selectedWorldviews.includes(tag)"
              @click="toggleWorldview(tag)"
              @close.stop="removeCustomTag('worldviews', tag)"
              class="selectable-tag"
            >{{ tag }}</n-tag>
          </div>
        </div>
      </n-popover>
    </div>
    </div><!-- /selector-grid -->

    <!-- 人称视角 -->
    <div class="selector-row pov-row">
      <SparkSegment
        :model-value="selectedPov || ''"
        :options="[
          {value:'第一人称',label:'第一人称'},
          {value:'第三人称有限',label:'第三人称有限'},
          {value:'第三人称全知',label:'第三人称全知'},
          {value:'第二人称',label:'第二人称'}
        ]"
        size="small"
        :block="true"
        @update:model-value="v => selectedPov = v || null"
      />
    </div>
    <!-- 篇幅建议 -->
    <div v-if="showLength" class="selector-row length-row">
      <SparkSegment
        :model-value="selectedLength || ''"
        :options="[{value:'短篇',label:'短篇'},{value:'中篇',label:'中篇'},{value:'长篇',label:'长篇'}]"
        size="small"
        :block="true"
        @update:model-value="v => selectedLength = v || null"
      />
    </div>
      </div>
    </SparkCollapseTransition>

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

    <n-modal v-model:show="showAddTone" preset="dialog" title="添加自定义基调">
      <n-input v-model:value="newToneTag" placeholder="输入新基调标签" @keyup.enter="addCustomTone" />
      <template #action>
        <n-button @click="showAddTone = false">取消</n-button>
        <n-button type="primary" @click="addCustomTone">添加</n-button>
      </template>
    </n-modal>

    <n-modal v-model:show="showAddWorldview" preset="dialog" title="添加自定义世界观">
      <n-input v-model:value="newWorldviewTag" placeholder="输入新世界观标签" @keyup.enter="addCustomWorldview" />
      <template #action>
        <n-button @click="showAddWorldview = false">取消</n-button>
        <n-button type="primary" @click="addCustomWorldview">添加</n-button>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { NPopover, NButton, NIcon, NModal, NInput, NTag, useMessage, useDialog } from 'naive-ui';
import SparkSegment from '../share/SparkSegment.vue';
import SparkCollapseTransition from '../share/SparkCollapseTransition.vue';
import { AddOutline, ChevronDownOutline, PricetagOutline } from '@vicons/ionicons5';
import { fetchWithAuth } from '../../services/api';

const props = defineProps({
  style: { type: String, default: null },
  genres: { type: Array, default: () => [] },
  tones: { type: Array, default: () => [] },
  worldviews: { type: Array, default: () => [] },
  pov: { type: String, default: null },
  lengthHint: { type: String, default: null },
  showLength: { type: Boolean, default: false },
  showStyle: { type: Boolean, default: true }
});

const emit = defineEmits(['update:style', 'update:genres', 'update:tones', 'update:worldviews', 'update:pov', 'update:lengthHint']);

const message = useMessage();
const dialog = useDialog();
const showTags = ref(false);

const totalTagsCount = computed(() => {
  return (props.showStyle ? selectedStyles.value.length : 0) + 
         selectedGenres.value.length + 
         selectedTones.value.length + 
         selectedWorldviews.value.length +
         (selectedPov.value ? 1 : 0);
});

type TagCatalog = {
  styles: string[];
  genres: string[];
  tones: string[];
  worldviews: string[];
};

// 预设标签（由后端统一提供）
const presetTags = ref<TagCatalog>({ styles: [], genres: [], tones: [], worldviews: [] });

// 用户自定义标签
const customTags = ref<TagCatalog>({ styles: [], genres: [], tones: [], worldviews: [] });

// 合并标签
const allStyleTags = computed(() => [...presetTags.value.styles, ...customTags.value.styles]);
const allGenreTags = computed(() => [...presetTags.value.genres, ...customTags.value.genres]);
const allToneTags = computed(() => [...presetTags.value.tones, ...(customTags.value.tones || [])]);
const allWorldviewTags = computed(() => [...presetTags.value.worldviews, ...(customTags.value.worldviews || [])]);

// 选中状态
const selectedStyles = ref<string[]>([]);
const selectedGenres = ref<string[]>([]);
const selectedTones = ref<string[]>([]);
const selectedWorldviews = ref<string[]>([]);
const selectedPov = ref<string | null>(null);
const selectedLength = ref<string | null>(null);

// 添加标签对话框
const showAddStyle = ref(false);
const showAddGenre = ref(false);
const showAddTone = ref(false);
const showAddWorldview = ref(false);
const newStyleTag = ref('');
const newGenreTag = ref('');
const newToneTag = ref('');
const newWorldviewTag = ref('');

// 标签目录缓存
const TAG_CACHE_KEY = 'spark_tag_catalog_v1';
const TAG_CACHE_TTL = 1000 * 60 * 60 * 24 * 7; // 7 天

function readTagCache() {
  try {
    const raw = localStorage.getItem(TAG_CACHE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || !data.ts || !data.presets || !data.custom) return null;
    if (Date.now() - data.ts > TAG_CACHE_TTL) return null;
    return data;
  } catch {
    return null;
  }
}

function writeTagCache(presets, custom) {
  try {
    localStorage.setItem(TAG_CACHE_KEY, JSON.stringify({ ts: Date.now(), presets, custom }));
  } catch {}
}

// 加载标签目录（预置 + 自定义）
async function loadTagCatalog() {
  const cached = readTagCache();
  if (cached) {
    presetTags.value = cached.presets;
    customTags.value = cached.custom;
  }
  try {
    const response = await fetchWithAuth('/api/tags/catalog');
    if (response.ok) {
      const data = await response.json();
      if (data.success) {
        presetTags.value = data.presets || { styles: [], genres: [], tones: [], worldviews: [] };
        customTags.value = data.custom || { styles: [], genres: [], tones: [], worldviews: [] };
        writeTagCache(presetTags.value, customTags.value);
      }
    }
  } catch (e) {
    console.error('Failed to load tag catalog:', e);
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
    writeTagCache(presetTags.value, customTags.value);
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

function toggleTone(tag) {
  const idx = selectedTones.value.indexOf(tag);
  if (idx >= 0) selectedTones.value.splice(idx, 1);
  else selectedTones.value.push(tag);
}

function removeTone(tag) {
  selectedTones.value = selectedTones.value.filter(t => t !== tag);
}

function toggleWorldview(tag) {
  const idx = selectedWorldviews.value.indexOf(tag);
  if (idx >= 0) selectedWorldviews.value.splice(idx, 1);
  else selectedWorldviews.value.push(tag);
}

function removeWorldview(tag) {
  selectedWorldviews.value = selectedWorldviews.value.filter(w => w !== tag);
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

async function addCustomTone() {
  const tag = newToneTag.value.trim();
  if (!tag) return;
  if (allToneTags.value.includes(tag)) { message.warning('标签已存在'); return; }
  if (!customTags.value.tones) customTags.value.tones = [];
  customTags.value.tones.push(tag);
  await saveCustomTags();
  newToneTag.value = '';
  showAddTone.value = false;
  message.success('已添加自定义基调');
}

async function addCustomWorldview() {
  const tag = newWorldviewTag.value.trim();
  if (!tag) return;
  if (allWorldviewTags.value.includes(tag)) { message.warning('标签已存在'); return; }
  if (!customTags.value.worldviews) customTags.value.worldviews = [];
  customTags.value.worldviews.push(tag);
  await saveCustomTags();
  newWorldviewTag.value = '';
  showAddWorldview.value = false;
  message.success('已添加自定义世界观');
}

async function removeCustomTag(type, tag) {
  const idx = customTags.value[type].indexOf(tag);
  if (idx >= 0) {
    customTags.value[type].splice(idx, 1);
    await saveCustomTags();
    if (type === 'styles') selectedStyles.value = selectedStyles.value.filter(s => s !== tag);
    if (type === 'genres') selectedGenres.value = selectedGenres.value.filter(g => g !== tag);
    if (type === 'tones') selectedTones.value = selectedTones.value.filter(t => t !== tag);
    if (type === 'worldviews') selectedWorldviews.value = selectedWorldviews.value.filter(w => w !== tag);
  }
}

// 监听 props 变化，同步到内部状态
watch(() => props.style, (val) => {
  const tags = val ? val.split(' + ') : [];
  if (JSON.stringify(tags) !== JSON.stringify(selectedStyles.value)) {
    selectedStyles.value = tags;
  }
}, { immediate: true });

watch(() => props.genres, (val) => {
  if (JSON.stringify(val) !== JSON.stringify(selectedGenres.value)) {
    selectedGenres.value = Array.isArray(val) ? val.map(v => String(v)) : [];
  }
}, { immediate: true, deep: true });

watch(() => props.tones, (val) => {
  if (JSON.stringify(val) !== JSON.stringify(selectedTones.value)) {
    selectedTones.value = Array.isArray(val) ? val.map(v => String(v)) : [];
  }
}, { immediate: true, deep: true });

watch(() => props.worldviews, (val) => {
  if (JSON.stringify(val) !== JSON.stringify(selectedWorldviews.value)) {
    selectedWorldviews.value = Array.isArray(val) ? val.map(v => String(v)) : [];
  }
}, { immediate: true, deep: true });

watch(() => props.pov, (val) => {
  if (val !== selectedPov.value) {
    selectedPov.value = val;
  }
}, { immediate: true });

watch(() => props.lengthHint, (val) => {
  if (val !== selectedLength.value) {
    selectedLength.value = val;
  }
}, { immediate: true });

// 监听选中状态变化，emit 给父组件
watch(selectedStyles, (val) => {
  const joined = val.length > 0 ? val.join(' + ') : null;
  if (joined !== props.style) emit('update:style', joined);
}, { deep: true });

watch(selectedGenres, (val) => {
  if (JSON.stringify(val) !== JSON.stringify(props.genres)) emit('update:genres', [...val]);
}, { deep: true });

watch(selectedTones, (val) => {
  if (JSON.stringify(val) !== JSON.stringify(props.tones)) emit('update:tones', [...val]);
}, { deep: true });

watch(selectedWorldviews, (val) => {
  if (JSON.stringify(val) !== JSON.stringify(props.worldviews)) emit('update:worldviews', [...val]);
}, { deep: true });

watch(selectedPov, (val) => {
  if (val !== props.pov) emit('update:pov', val);
});

watch(selectedLength, (val) => {
  if (val !== props.lengthHint) emit('update:lengthHint', val);
});

onMounted(() => { loadTagCatalog(); });
</script>

<style scoped>
.inspire-tag-selector {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* 单列网格布局，增加内边距 */
.selector-grid {
  display: grid;
  grid-template-columns: 1fr;
  background: rgba(var(--spark-primary-rgb, 128, 128, 128), 0.03);
  border: 1px solid var(--spark-border);
  padding: 14px;
  border-radius: 10px;
  margin-top: 8px;
  gap: 12px;
}

/* 折叠容器专属样式 */
.tags-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}
.tags-entry:hover {
  border-color: var(--spark-primary);
}
.tags-entry:active {
  background: rgba(var(--spark-primary-rgb), 0.05);
}
.entry-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.entry-left .entry-icon {
  color: var(--spark-primary);
}
.entry-label {
  font-size: var(--spark-fs-base);
  font-weight: 600;
  color: var(--spark-text);
}
.entry-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.entry-sub {
  font-size: var(--spark-fs-sm);
  color: var(--spark-primary);
  font-weight: 500;
}
.entry-sub.empty {
  color: var(--spark-text-muted);
  font-weight: normal;
}
.entry-arrow {
  color: var(--spark-text-muted);
  transition: transform 0.3s;
}
.entry-arrow.expanded {
  transform: rotate(180deg);
}

.pov-row {
  padding: 0 4px;
  margin-top: 4px;
}

.length-row {
  padding: 0 4px;
  margin-top: 8px;
}

.selector-row {
  display: flex;
  align-items: center;
  min-width: 0; /* 防止内容溢出 */
}

.selector-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-width: 0;
  min-height: 28px;
  padding: 4px 8px;
  background: var(--spark-input-bg, rgba(255,255,255,0.06));
  border: 1px solid var(--spark-border, rgba(255,255,255,0.1));
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.2s;
  overflow: hidden;
}

.selector-trigger:hover {
  border-color: var(--spark-primary, #ffaa40);
}

.selector-trigger .placeholder {
  color: var(--spark-text-muted, #888);
  font-size: var(--spark-fs-xs);
}

.selector-trigger .selected-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  flex: 1;
}

.selector-trigger .more-count {
  font-size: var(--spark-fs-2xs);
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
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-muted, #888);
}

.panel-header .hint {
  font-size: var(--spark-fs-3xs);
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
  margin-top: 0;
}

/* 标签关闭按钮样式 - 缩小并使用红色 */
/* 标签关闭按钮样式 - 背景透明，红色圆形图标 */
.selected-tags :deep(.n-tag__close) {
  /* 核心修正：清除所有干扰样式 */
  background-color: transparent !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
  padding: 0 !important; /* 关键：去除内边距防止变成椭圆 */
  
  color: #ff4d4f !important; /* 鲜艳红色 */
  
  /* 强制正圆尺寸 */
  width: 16px !important;
  height: 16px !important;
  min-width: 16px !important;
  min-height: 16px !important;
  border-radius: 50% !important;
  
  /* 居中对齐 */
  display: flex !important;
  align-items: center;
  justify-content: center;

  font-size: var(--spark-fs-base) !important; /* 图标稍大一点 */
  margin-left: 2px; /* 与文字的间距 */

  opacity: 0.6;
  transition: all 0.2s ease;
  transform: none; /* 防止意外变形 */
}

.selected-tags :deep(.n-tag__close:hover) {
  opacity: 1;
  background-color: rgba(255, 77, 79, 0.1) !important; /* 悬停时显示极淡红色背景 */
  transform: scale(1.1);
}

/* 标签整体调整 */
.selected-tags :deep(.n-tag) {
  font-size: var(--spark-fs-xs);
  padding: 0 8px; /* 稍微增加水平内边距 */
  height: 22px;
  line-height: 20px;
  border-radius: 12px; /* 增加圆角，让标签更圆润 */
}
</style>
