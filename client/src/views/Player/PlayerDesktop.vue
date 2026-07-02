<template>
  <div class="player-container" :class="{ 'loading': loading }">
    
    <!-- 0. 常驻免责标签（仅简体中文可见） -->
    <ZhOnlyTag type="disclaimer" class="persistent-disclaimer"><template v-if="disclaimerParts">{{ disclaimerParts.before }}<a :href="SPARKARC_GITHUB_URL" target="_blank" rel="noopener" class="disclaimer-brand-link">SparkArc</a>{{ disclaimerParts.after }}</template><template v-else>{{ t('views.player.desktop.zhDisclaimer') }}</template></ZhOnlyTag>

    <!-- 1. 背景层：氛围动画 -->
    <PlayerAmbient />

    <!-- 2. 加载界面 -->
    <transition name="fade">
      <div v-if="loading" class="screen loading-screen">
        <div class="loader-content">
          <svg class="feather-pen" viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" stroke-width="1" fill="none" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5z"></path>
            <line x1="16" y1="8" x2="2" y2="22"></line>
            <line x1="17.5" y1="15" x2="9" y2="15"></line>
          </svg>
          <p class="loading-text">{{ t('views.player.desktop.loadingStory') }}</p>
        </div>
      </div>
    </transition>

    <!-- 3. 错误界面 -->
    <transition name="fade">
      <div v-if="error" class="screen error-screen">
        <div class="error-content">
          <h3>{{ t('views.player.desktop.loadStoryFailed') }}</h3>
          <p>{{ error }}</p>
          <button class="btn-retry" @click="loadGame">{{ t('views.common.retry') }}</button>
        </div>
      </div>
    </transition>

    <transition name="fade-slow">
      <div v-if="!loading && !error && contentFormat === 'novel'" class="screen novel-screen">
        <div class="novel-shell">
          <div class="novel-header">
            <h1>{{ titleText }}</h1>
            <p>{{ t('views.player.desktop.publicNovelPreview') }}</p>
          </div>
          <div class="novel-body">{{ novelContent }}</div>
        </div>
      </div>
    </transition>

    <!-- 4. 游戏主舞台 -->
    <transition name="fade-slow">
      <div v-if="!loading && !error && contentFormat !== 'novel' && !gameEnded" class="game-stage" @click="handleStageClick">

        <!-- 场景翻页按钮（左上角） -->
        <div class="scene-book-nav" @click.stop>
          <BookNavButton
            :items="sceneNavItems"
            :current-id="sceneNavCurrentId"
            :panel-title="t('views.player.desktop.sceneNav')"
            :empty-hint="t('views.player.desktop.noScenesHint')"
            @select="handleSceneNavSelect"
          />
        </div>

        <!-- 角色层 (预留) -->
        <div class="layer characters">
           <transition name="fade">
              <div v-if="currentCharacter" class="character-sprite">
                  <!-- 角色立绘占位 -->
              </div>
           </transition>
        </div>

        <!-- 章节标题 -->
        <transition name="fade-slide-up">
            <div v-if="showTitle" class="chapter-title-overlay">
                <div class="title-content">
                  <span class="chapter-label">{{ t('views.player.desktop.chapterLabel', { chapter: currentScene?.chapter || '1' }) }}</span>
                    <h1>{{ currentScene?.guide || currentScene?.scene_name }}</h1>
                    <div class="title-divider"></div>
                    <div v-if="currentScene?.intro" class="intro-text">{{ currentScene.intro }}</div>
                </div>
            </div>
        </transition>

        <!-- UI 层 -->
        <div class="layer ui">
          
          <!-- 对话框 -->
          <transition name="slide-up">
            <div class="dialogue-container" v-show="currentDialogue && !showTitle">
              <div class="dialogue-box">
                <!-- 名字标签 -->
                <div class="name-tag-wrapper" v-if="currentSpeakerName">
                  <div class="name-tag">
                    {{ currentSpeakerName }}
                  </div>
                </div>
                
                <!-- 文本内容 -->
                <div class="text-content">
                  {{ displayedText }}<span class="cursor" v-if="isTyping"></span>
                </div>

                <!-- 思维链按钮 -->
                <div v-if="currentDialogue?.thought" class="thought-toggle" @click.stop="showThought = !showThought">
                  <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none">
                    <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
                  </svg>
                </div>

                <!-- 继续指示器 -->
                <div class="next-indicator" v-if="!isTyping && !waitingForChoice">
                  <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" fill="none">
                    <polyline points="6 9 12 15 18 9"></polyline>
                  </svg>
                </div>
              </div>
            </div>
          </transition>

          <!-- 选项层 -->
          <transition name="fade">
            <div class="choices-overlay" v-if="waitingForChoice">
              <div class="choices-container">
                <div 
                  v-for="(opt, idx) in currentChoices" 
                  :key="idx" 
                  class="choice-btn"
                  @click.stop="handleChoice(opt)"
                >
                  <span class="choice-text">{{ opt.optn }}</span>
                  <div class="choice-bg"></div>
                </div>
              </div>
            </div>
          </transition>

          <!-- 思维链弹窗 -->
          <transition name="fade">
            <div class="thought-overlay" v-if="showThought" @click.stop="showThought = false">
              <div class="thought-panel" @click.stop>
                <div class="thought-header">
                  <span>{{ t('views.player.desktop.thoughtProcess') }}</span>
                  <button class="close-btn" @click="showThought = false">×</button>
                </div>
                <div class="thought-body">
                  {{ currentDialogue?.thought }}
                </div>
              </div>
            </div>
          </transition>

        </div>
      </div>
    </transition>

    <!-- 5. 结束界面 -->
    <transition name="fade-slow">
      <div v-if="gameEnded" class="screen end-screen">
        <div class="end-content">
          <div class="end-icon">
            <svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" stroke-width="1" fill="none">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"></path>
            </svg>
          </div>
          <h1>{{ t('views.player.desktop.theEnd') }}</h1>
          <p>{{ t('views.player.desktop.thanksForPlaying') }}</p>
          <button class="btn-restart" @click="restartGame">{{ t('views.player.desktop.restart') }}</button>
        </div>
      </div>
    </transition>

  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { fetchWithAuth } from '@/services/apiClient';
import PlayerAmbient from './PlayerAmbient.vue';
import ZhOnlyTag from '@/components/player/shared/ZhOnlyTag.vue';
import BookNavButton from '@/components/player/shared/BookNavButton.vue';
import type { NavItem } from '@/components/player/shared/SceneNavPanel.vue';
import { ensureAppFontReadyForText, warmupAppFontInBackground } from '@/utils/fontWarmup';
import { SPARKARC_GITHUB_URL } from '@/config';

type PlayerDataResponse = {
  format?: string;
  content?: string;
  stories?: StoryScene[];
  characters?: Record<string, string>;
  registry?: Record<string, unknown>;
};

type StoryChoice = {
  optn?: string;
  dia?: StoryDialogue[];
};

type StoryDialogue = {
  chr?: number | string;
  speaker?: string;
  txt?: string;
  thought?: string;
  opt?: StoryChoice[];
  act?: Record<string, unknown>;
  next?: string;
};

type StoryScene = {
  chapter?: number | string;
  guide?: string;
  scene_name?: string;
  intro?: string;
  dlg?: StoryDialogue[];
};

type DialogueStackItem = {
  list: StoryDialogue[];
  index: number;
};

type ScriptProgressState = {
  sceneIndex: number;
  dialogueIndex: number;
  updatedAt: number;
};

function normalizeQueryValue(value: unknown): string | null {
  if (Array.isArray(value)) {
    const first = value[0];
    return typeof first === 'string' ? first : null;
  }
  return typeof value === 'string' ? value : null;
}

function toOneBasedIndex(value: string | null): number | null {
  if (!value) return null;
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed < 1) return null;
  return parsed - 1;
}

function clampInt(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function parseScriptProgress(raw: string | null): ScriptProgressState | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<ScriptProgressState>;
    const sceneIndex = Number.isFinite(parsed.sceneIndex) ? Number(parsed.sceneIndex) : 0;
    const dialogueIndex = Number.isFinite(parsed.dialogueIndex) ? Number(parsed.dialogueIndex) : 0;
    const updatedAt = Number.isFinite(parsed.updatedAt) ? Number(parsed.updatedAt) : Date.now();
    return { sceneIndex, dialogueIndex, updatedAt };
  } catch {
    return null;
  }
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error || t('views.player.desktop.loadFailed'));
}

async function readApiError(response: Response, fallback: string): Promise<string> {
  try {
    const data = await response.json() as Record<string, unknown>;
    const detail = data.detail;
    if (typeof data.error === 'string' && data.error) return data.error;
    if (typeof data.message === 'string' && data.message) return data.message;
    if (typeof detail === 'string' && detail) return detail;
    if (detail && typeof detail === 'object' && typeof (detail as { message?: unknown }).message === 'string') {
      return (detail as { message: string }).message;
    }
  } catch {
    // ignore invalid payload
  }
  return fallback;
}

const { t } = useI18n();

const route = useRoute();
const router = useRouter();
const shareId = computed(() => String(route.params.shareId || ''));

/** 将免责声明文本在第一个 "SparkArc" 处拆分，用于插入链接 */
const disclaimerParts = computed(() => {
  const text = t('views.player.desktop.zhDisclaimer');
  const idx = text.indexOf('SparkArc');
  if (idx === -1) return null;
  return { before: text.slice(0, idx), after: text.slice(idx + 'SparkArc'.length) };
});
const isVersionPlay = computed(() => route.path.includes('/play/v/'));
const scriptProgressStorageKey = computed(() => {
  const linkType = isVersionPlay.value ? 'version' : 'share';
  return `spark_player_progress_v2:script:${linkType}:${shareId.value}`;
});

const loading = ref(true);
const error = ref<string | null>(null);
const gameEnded = ref(false);
const storyData = ref<StoryScene[]>([]);
const charMap = ref<Record<string, string>>({});
const registry = ref<Record<string, unknown>>({});
const contentFormat = ref('script');
const novelContent = ref('');
const titleText = ref(t('views.player.desktop.publicContent'));

// Game State
const currentSceneIndex = ref(0);
const currentDialogueIndex = ref(0);
const dialogueStack = ref<DialogueStackItem[]>([]); // For nested choices
const displayedText = ref('');
const isTyping = ref(false);
const showTitle = ref(false);
const waitingForChoice = ref(false);
const showThought = ref(false);
const titleTimerId = ref<number | null>(null);
const typingTimerId = ref<number | null>(null);
const typingJobId = ref(0);

// Computed
const currentScene = computed(() => {
  if (!storyData.value.length) return null;
  return storyData.value[currentSceneIndex.value];
});

/* --- BookNavButton 场景导航数据 --- */
const sceneNavItems = computed<NavItem[]>(() =>
  storyData.value.map((s, idx) => ({
    id: `scene-${idx}`,
    title: s.guide || s.scene_name || t('views.player.desktop.untitledScene', { index: idx + 1 }),
  }))
);

const sceneNavCurrentId = computed(() => `scene-${currentSceneIndex.value}`);

function handleSceneNavSelect(item: NavItem) {
  const idx = Number(String(item.id).replace('scene-', ''));
  if (Number.isFinite(idx) && idx >= 0 && idx < storyData.value.length) {
    currentSceneIndex.value = idx;
    currentDialogueIndex.value = 0;
    dialogueStack.value = [];
    showSceneTitle();
    processCurrentNode();
  }
}

const currentDialogue = computed(() => {
  if (!currentScene.value) return null;

  if (dialogueStack.value.length > 0) {
    const group = dialogueStack.value[dialogueStack.value.length - 1];
    return group.list[group.index];
  }

  const dia = currentScene.value.dlg;
  if (!dia || currentDialogueIndex.value >= dia.length) return null;
  return dia[currentDialogueIndex.value];
});

const currentSpeakerName = computed(() => {
  if (!currentDialogue.value) return '';
  const speaker = String(currentDialogue.value.speaker || '').trim();
  if (speaker && speaker !== '旁白') return speaker;
  const chrId = currentDialogue.value.chr;
  if (chrId === undefined || chrId === null) return '';
  if (chrId === -1 || chrId === '-1' || chrId === '旁白') return '';
  if (typeof chrId === 'string' && Number.isNaN(Number(chrId))) return chrId;
  return charMap.value[chrId] || t('views.player.desktop.unknownSpeaker');
});

const currentChoices = computed(() => {
  if (!currentDialogue.value) return [];
  return currentDialogue.value.opt || [];
});

const currentCharacter = computed(() => {
  // TODO: Determine which character is visible based on speaker
  return null;
});

function clearTitleTimer() {
  if (titleTimerId.value !== null) {
    window.clearTimeout(titleTimerId.value);
    titleTimerId.value = null;
  }
}

function collectSceneText(scene: StoryScene | null): string {
  if (!scene) return '';
  const parts: string[] = [];
  if (scene.guide) parts.push(scene.guide);
  if (scene.scene_name) parts.push(scene.scene_name);
  for (const d of scene.dlg || []) {
    if (d.txt) parts.push(d.txt);
    if (d.thought) parts.push(d.thought);
    for (const o of d.opt || []) {
      if (o.optn) parts.push(o.optn);
    }
  }
  return parts.join('');
}

// 场景预热已注释：LXGW WenKai Lite CDN 加载 + font-display:swap 已保证非阻塞
// function warmupSceneFonts(sceneIndex: number) {
//   const scene = storyData.value[sceneIndex];
//   if (!scene) return;
//   const text = collectSceneText(scene);
//   if (!text) return;
//   warmupAppFontInBackground(text, { maxChars: 500, timeoutMs: 5000 });
// }

function showSceneTitle() {
  clearTitleTimer();
  showTitle.value = true;
  // 有场景引言时不自动消失，等用户点击关闭；无引言时保持原 3.5s 自动消失
  if (!currentScene.value?.intro) {
    titleTimerId.value = window.setTimeout(() => {
      showTitle.value = false;
      titleTimerId.value = null;
    }, 3500);
  }
}

function clearTypingTimer() {
  if (typingTimerId.value !== null) {
    window.clearTimeout(typingTimerId.value);
    typingTimerId.value = null;
  }
}

function invalidateTypingJob() {
  typingJobId.value++;
  clearTypingTimer();
  isTyping.value = false;
}

async function presentNodeText(text: string) {
  invalidateTypingJob();
  const jobId = typingJobId.value;
  displayedText.value = '';
  if (!text) {
    return;
  }
  isTyping.value = true;
  // 字体预热已注释：CDN font-display:swap 保证非阻塞，不再 await
  // await ensureAppFontReadyForText(`${currentSpeakerName.value}${text}`, {
  //   timeoutMs: 150,
  //   maxChars: 140,
  // });
  if (jobId !== typingJobId.value) {
    return;
  }
  typeText(text, jobId);
}

function readScriptProgressFromStorage(): ScriptProgressState | null {
  try {
    const raw = localStorage.getItem(scriptProgressStorageKey.value);
    return parseScriptProgress(raw);
  } catch {
    return null;
  }
}

function writeScriptProgressToStorage(progress: ScriptProgressState) {
  try {
    localStorage.setItem(scriptProgressStorageKey.value, JSON.stringify(progress));
  } catch {
    // ignore storage errors
  }
}

function clampScriptProgress(progress: ScriptProgressState): ScriptProgressState {
  const maxScene = Math.max(storyData.value.length - 1, 0);
  const sceneIndex = clampInt(progress.sceneIndex, 0, maxScene);
  const scene = storyData.value[sceneIndex];
  const maxDialogue = Math.max((scene?.dlg?.length || 1) - 1, 0);
  const dialogueIndex = clampInt(progress.dialogueIndex, 0, maxDialogue);
  return {
    sceneIndex,
    dialogueIndex,
    updatedAt: progress.updatedAt || Date.now(),
  };
}

function resolveInitialScriptProgress(): ScriptProgressState {
  const querySceneIndex = toOneBasedIndex(normalizeQueryValue(route.query.scene));
  const queryDialogueIndex = toOneBasedIndex(normalizeQueryValue(route.query.dia));

  const queryProgress: ScriptProgressState | null =
    querySceneIndex !== null || queryDialogueIndex !== null
      ? {
          sceneIndex: querySceneIndex ?? 0,
          dialogueIndex: queryDialogueIndex ?? 0,
          updatedAt: Date.now(),
        }
      : null;

  const storedProgress = readScriptProgressFromStorage();
  const base = queryProgress || storedProgress || { sceneIndex: 0, dialogueIndex: 0, updatedAt: Date.now() };
  return clampScriptProgress(base);
}

function syncScriptProgressToQuery(progress: ScriptProgressState) {
  const nextScene = String(progress.sceneIndex + 1);
  const nextDialogue = String(progress.dialogueIndex + 1);

  const currentScene = normalizeQueryValue(route.query.scene);
  const currentDialogue = normalizeQueryValue(route.query.dia);
  if (currentScene === nextScene && currentDialogue === nextDialogue) {
    return;
  }

  const nextQuery: Record<string, string> = {};
  for (const [key, value] of Object.entries(route.query)) {
    const text = normalizeQueryValue(value);
    if (text !== null && key !== 'scene' && key !== 'dia') {
      nextQuery[key] = text;
    }
  }
  nextQuery.scene = nextScene;
  nextQuery.dia = nextDialogue;

  void router.replace({ query: nextQuery }).catch(() => {
    // ignore duplicated navigation
  });
}

function persistScriptProgress() {
  if (loading.value || error.value || contentFormat.value !== 'script' || storyData.value.length === 0) {
    return;
  }
  const progress = clampScriptProgress({
    sceneIndex: currentSceneIndex.value,
    dialogueIndex: currentDialogueIndex.value,
    updatedAt: Date.now(),
  });
  writeScriptProgressToStorage(progress);
  syncScriptProgressToQuery(progress);
}

// Methods
async function loadGame() {
  loading.value = true;
  error.value = null;
  invalidateTypingJob();
  displayedText.value = '';
  waitingForChoice.value = false;
  showThought.value = false;
  gameEnded.value = false;
  try {
    const apiUrl = isVersionPlay.value ? `/api/play/v/${shareId.value}/data` : `/api/play/${shareId.value}/data`;

    const res = await fetchWithAuth(apiUrl);
    if (!res.ok) {
      throw new Error(await readApiError(res, t('views.player.desktop.invalidLinkError')));
    }
    const data = await res.json() as PlayerDataResponse;
    contentFormat.value = data.format || 'script';
    if (contentFormat.value === 'novel') {
      novelContent.value = data.content || '';
      storyData.value = [];
      charMap.value = {};
      registry.value = {};
      titleText.value = t('views.player.desktop.publicNovel');
      return;
    }
    storyData.value = data.stories || [];
    charMap.value = data.characters || {};
    registry.value = data.registry || {};

    const initialProgress = resolveInitialScriptProgress();
    startGame(initialProgress);
  } catch (e: unknown) {
    error.value = getErrorMessage(e);
  } finally {
    loading.value = false;
  }
}

function startGame(initialProgress: ScriptProgressState | null = null) {
  const progress = initialProgress
    ? clampScriptProgress(initialProgress)
    : { sceneIndex: 0, dialogueIndex: 0, updatedAt: Date.now() };

  currentSceneIndex.value = progress.sceneIndex;
  currentDialogueIndex.value = progress.dialogueIndex;
  dialogueStack.value = [];
  invalidateTypingJob();
  displayedText.value = '';
  waitingForChoice.value = false;
  showThought.value = false;
  gameEnded.value = false;
  showSceneTitle();
  processCurrentNode();
}

function restartGame() {
  startGame(null);
}

function processCurrentNode() {
  const node = currentDialogue.value;
  if (!node) {
    if (dialogueStack.value.length > 0) {
      dialogueStack.value.pop();
      advanceIndex();
      processCurrentNode();
    } else {
      nextScene();
    }
    return;
  }

  if (node.act) {
    for (const [key, value] of Object.entries(node.act)) {
      executeAction(key, value);
    }
  }

  if (node.opt && node.opt.length > 0) {
    waitingForChoice.value = true;
    void presentNodeText(node.txt || '');
  } else {
    waitingForChoice.value = false;
    void presentNodeText(node.txt || '');
  }

  persistScriptProgress();
}

function executeAction(key: string, value: unknown) {
  console.log(`[Action] ${key}:`, value);

  switch (key.toLowerCase()) {
    case 'bg': {
      const colorValue = Array.isArray(value) ? value[0] : value;
      if (typeof colorValue === 'string') {
        document.body.style.backgroundColor = colorValue;
      }
      break;
    }
    case 'shake': {
      const stage = document.querySelector('.game-stage');
      if (stage) {
        stage.classList.add('shake-anim');
        setTimeout(() => stage.classList.remove('shake-anim'), 500);
      }
      break;
    }
    case 'sound':
      console.log('Playing sound:', value);
      break;
  }
}

function typeText(text: string, jobId: number) {
  displayedText.value = '';
  isTyping.value = true;
  let i = 0;
  const speed = 30;

  function type() {
    if (jobId !== typingJobId.value) {
      return;
    }
    if (i < text.length) {
      displayedText.value += text.charAt(i);
      i++;
      typingTimerId.value = window.setTimeout(type, speed);
    } else {
      isTyping.value = false;
      typingTimerId.value = null;
    }
  }

  type();
}

function skipTyping() {
  invalidateTypingJob();
  const node = currentDialogue.value;
  displayedText.value = node ? node.txt || '' : '';
}

function handleStageClick() {
  if (loading.value || error.value || waitingForChoice.value) return;

  if (showTitle.value) {
    clearTitleTimer();
    showTitle.value = false;
    return;
  }

  if (isTyping.value) {
    skipTyping();
    return;
  }

  const node = currentDialogue.value;
  if (node && node.next) {
    jumpToScene(node.next);
  } else {
    advanceIndex();
    processCurrentNode();
  }
}

function advanceIndex() {
  if (dialogueStack.value.length > 0) {
    const group = dialogueStack.value[dialogueStack.value.length - 1];
    group.index++;
  } else {
    currentDialogueIndex.value++;
  }
}

function handleChoice(opt: StoryChoice) {
  if (opt.dia && opt.dia.length > 0) {
    dialogueStack.value.push({
      list: opt.dia,
      index: 0,
    });
    waitingForChoice.value = false;
    processCurrentNode();
  } else {
    waitingForChoice.value = false;
    advanceIndex();
    processCurrentNode();
  }
}

function nextScene() {
  if (currentSceneIndex.value < storyData.value.length - 1) {
    currentSceneIndex.value++;
    currentDialogueIndex.value = 0;
    dialogueStack.value = [];
    showSceneTitle();
    processCurrentNode();
  } else {
    gameEnded.value = true;
    persistScriptProgress();
  }
}

function jumpToScene(sceneName: string) {
  const idx = storyData.value.findIndex(s => s.scene_name === sceneName);
  if (idx !== -1) {
    currentSceneIndex.value = idx;
    currentDialogueIndex.value = 0;
    dialogueStack.value = [];
    showSceneTitle();
    processCurrentNode();
  } else {
    console.warn(`Scene ${sceneName} not found`);
    advanceIndex();
    processCurrentNode();
  }
}

watch(
  () => [currentSceneIndex.value, currentDialogueIndex.value],
  () => {
    persistScriptProgress();
  }
);

watch(
  () => [route.params.shareId, route.path],
  (nextVal, prevVal) => {
    const nextKey = `${String(nextVal[0] || '')}|${String(nextVal[1] || '')}`;
    const prevKey = `${String(prevVal?.[0] || '')}|${String(prevVal?.[1] || '')}`;
    if (nextKey !== prevKey) {
      loadGame();
    }
  }
);

onMounted(() => {
  loadGame();
});

onBeforeUnmount(() => {
  clearTitleTimer();
  invalidateTypingJob();
});
</script>

<style scoped>
.novel-screen {
  display: flex;
  align-items: stretch;
  justify-content: center;
  padding: 32px 20px;
}

.novel-shell {
  width: min(920px, 100%);
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 24px 28px 36px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(10, 14, 24, 0.56);
  backdrop-filter: blur(10px);
  border-radius: 18px;
  box-shadow: 0 12px 40px rgba(0,0,0,0.28);
}

.novel-header h1 {
  margin: 0 0 8px;
  font-size: var(--spark-fs-display);
}

.novel-header p {
  margin: 0;
  opacity: 0.72;
}

.novel-body {
  white-space: pre-wrap;
  line-height: 1.95;
  font-size: var(--spark-fs-lg);
}
</style>

<style scoped src="./PlayerDesktop.scoped.css"></style>
