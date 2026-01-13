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

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { NPopover, NButton, NIcon, NRadioGroup, NRadioButton, NModal, NInput, NTag, useMessage, useDialog } from 'naive-ui';
import { AddOutline, ChevronDownOutline } from '@vicons/ionicons5';
import { fetchWithAuth } from '../../services/api';

const props = defineProps({
  style: { type: String, default: null },
  genres: { type: Array, default: () => [] },
  tones: { type: Array, default: () => [] },
  worldviews: { type: Array, default: () => [] },
  lengthHint: { type: String, default: null }
});

const emit = defineEmits(['update:style', 'update:genres', 'update:tones', 'update:worldviews', 'update:lengthHint']);

const message = useMessage();
const dialog = useDialog();

// 预设标签
const presetStyles = ['治愈', '致郁', '悬疑', '恐怖', '奇幻', '科幻', '浪漫', '热血', '喜剧', '悲剧', '正剧', '史诗', '讽刺', '哥特', '爽文', '甜宠', '虐恋', '沙雕', '群像', '极简'];
const presetGenres = ['校园', '都市', '乡村', '日常', '冒险', '推理', '战争', '宫廷', '江湖', '职场', '仙侠', '玄幻', '魔法', '历史', '民国', '刑侦', '医疗', '商战', '娱乐圈', '电竞'];
const presetTones = ['现实主义', '魔幻现实主义', '梦核', '怪核', '旧核', '蒸汽波', '网络抽象', '青春伤痛', '黑色幽默', '意识流', '荒诞', '唯美', '暗黑', '虚无主义', '迷幻', '故障艺术', '童话', '硬汉'];
const presetWorldviews = ['现实', '架空', '阈限空间', '规则怪谈', '后室', '模拟宇宙', '时间循环', '平行时空', '伪人', '基金会', '穿越', '重生', '系统', '无限流', '末世', '废土', '赛博朋克', '克苏鲁', '西幻', '修真', '星际', '异能'];

// 用户自定义标签
const customTags = ref({ styles: [], genres: [], tones: [], worldviews: [] });

// 合并标签
const allStyleTags = computed(() => [...presetStyles, ...customTags.value.styles]);
const allGenreTags = computed(() => [...presetGenres, ...customTags.value.genres]);
const allToneTags = computed(() => [...presetTones, ...(customTags.value.tones || [])]);
const allWorldviewTags = computed(() => [...presetWorldviews, ...(customTags.value.worldviews || [])]);

// 选中状态
const selectedStyles = ref([]);
const selectedGenres = ref([]);
const selectedTones = ref([]);
const selectedWorldviews = ref([]);
const selectedLength = ref(null);

// 添加标签对话框
const showAddStyle = ref(false);
const showAddGenre = ref(false);
const showAddTone = ref(false);
const showAddWorldview = ref(false);
const newStyleTag = ref('');
const newGenreTag = ref('');
const newToneTag = ref('');
const newWorldviewTag = ref('');

// 加载用户自定义标签
async function loadCustomTags() {
  try {
    const response = await fetchWithAuth('/api/user/custom-tags');
    if (response.ok) {
      const data = await response.json();
      if (data.success && data.tags) {
        customTags.value = {
          styles: data.tags.styles || [],
          genres: data.tags.genres || [],
          tones: data.tags.tones || [],
          worldviews: data.tags.worldviews || []
        };
      }
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
    selectedGenres.value = [...(val || [])];
  }
}, { immediate: true, deep: true });

watch(() => props.tones, (val) => {
  if (JSON.stringify(val) !== JSON.stringify(selectedTones.value)) {
    selectedTones.value = [...(val || [])];
  }
}, { immediate: true, deep: true });

watch(() => props.worldviews, (val) => {
  if (JSON.stringify(val) !== JSON.stringify(selectedWorldviews.value)) {
    selectedWorldviews.value = [...(val || [])];
  }
}, { immediate: true, deep: true });

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

watch(selectedLength, (val) => {
  if (val !== props.lengthHint) emit('update:lengthHint', val);
});

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
