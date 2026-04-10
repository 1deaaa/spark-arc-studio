<template>
  <div class="player-container" :class="{ 'loading': loading }">
    
    <!-- 1. 背景层：常驻氛围动画 -->
    <div class="layer background">
      <div class="bg-gradient"></div>
      <!-- SVG 粒子动画 -->
      <svg class="ambient-particles" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice">
        <g fill="#ffffff" fill-opacity="0.1">
          <circle cx="10" cy="10" r="0.5">
            <animate attributeName="cy" values="10;0;10" dur="10s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.1;0.5;0.1" dur="10s" repeatCount="indefinite" />
          </circle>
          <circle cx="50" cy="50" r="0.8">
            <animate attributeName="cy" values="50;40;50" dur="15s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.1;0.4;0.1" dur="15s" repeatCount="indefinite" />
          </circle>
          <circle cx="80" cy="20" r="0.3">
            <animate attributeName="cy" values="20;10;20" dur="12s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.1;0.6;0.1" dur="12s" repeatCount="indefinite" />
          </circle>
          <circle cx="20" cy="80" r="0.6">
            <animate attributeName="cy" values="80;70;80" dur="18s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.1;0.3;0.1" dur="18s" repeatCount="indefinite" />
          </circle>
          <circle cx="90" cy="90" r="0.4">
            <animate attributeName="cy" values="90;80;90" dur="20s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.1;0.5;0.1" dur="20s" repeatCount="indefinite" />
          </circle>
        </g>
      </svg>
    </div>

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
                    <h1>{{ currentScene?.caption || currentScene?.scene_name }}</h1>
                    <div class="title-divider"></div>
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
  txt?: string;
  thought?: string;
  opt?: StoryChoice[];
  act?: Record<string, unknown>;
  next?: string;
};

type StoryScene = {
  chapter?: number | string;
  caption?: string;
  scene_name?: string;
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

// Computed
const currentScene = computed(() => {
  if (!storyData.value.length) return null;
    return storyData.value[currentSceneIndex.value];
});

const currentDialogue = computed(() => {
    if (!currentScene.value) return null;
    
    // If we are in a nested stack (from choices)
    if (dialogueStack.value.length > 0) {
        const group = dialogueStack.value[dialogueStack.value.length - 1];
        return group.list[group.index];
    }

    // Main scene flow
    const dia = currentScene.value.dlg;
    if (!dia || currentDialogueIndex.value >= dia.length) return null;
    return dia[currentDialogueIndex.value];
});

const currentSpeakerName = computed(() => {
    if (!currentDialogue.value) return '';
    const chrId = currentDialogue.value.chr;
  if (chrId === undefined || chrId === null) return '';
    if (chrId === -1 || chrId === '-1') return ''; // Narration
    if (chrId === 0 || chrId === '0') return t('views.player.desktop.defaultSpeaker'); // Default protagonist
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

function showSceneTitle() {
  clearTitleTimer();
  showTitle.value = true;
  titleTimerId.value = window.setTimeout(() => {
    showTitle.value = false;
    titleTimerId.value = null;
  }, 3500);
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
    gameEnded.value = false;
    try {
        // 判断是否是版本分享链接
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
      displayedText.value = '';
      waitingForChoice.value = false;
      isTyping.value = false;
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
        // End of current list
        if (dialogueStack.value.length > 0) {
            // Pop stack
            dialogueStack.value.pop();
            // Move to next in the parent list
            advanceIndex();
            processCurrentNode();
        } else {
            // End of scene, go to next scene
            nextScene();
        }
        return;
    }

    // Execute actions
    if (node.act) {
        for (const [key, value] of Object.entries(node.act)) {
            executeAction(key, value);
        }
    }

    // Check for choices
    if (node.opt && node.opt.length > 0) {
        waitingForChoice.value = true;
        typeText(node.txt || '');
    } else {
        waitingForChoice.value = false;
        typeText(node.txt || '');
    }

    persistScriptProgress();
}

function executeAction(key: string, value: unknown) {
    console.log(`[Action] ${key}:`, value);
    
    // 简单的内置行为实现
    switch (key.toLowerCase()) {
        case 'bg':
            // 设置背景颜色或图片（示例）
        {
          const colorValue = Array.isArray(value) ? value[0] : value;
          if (typeof colorValue === 'string') {
            document.body.style.backgroundColor = colorValue;
          }
        }
            break;
        case 'shake':
            // 屏幕抖动
            const stage = document.querySelector('.game-stage');
            if (stage) {
                stage.classList.add('shake-anim');
                setTimeout(() => stage.classList.remove('shake-anim'), 500);
            }
            break;
        case 'sound':
            // 播放音效（占位）
            console.log('Playing sound:', value);
            break;
    }
}

function typeText(text: string) {
    displayedText.value = '';
    isTyping.value = true;
    let i = 0;
    const speed = 30; 
    
    function type() {
        if (i < text.length) {
            displayedText.value += text.charAt(i);
            i++;
            setTimeout(type, speed);
        } else {
            isTyping.value = false;
        }
    }
    type();
}

function handleStageClick() {
    if (loading.value || error.value || waitingForChoice.value || showTitle.value) return;

    if (isTyping.value) {
        // Instant finish typing (simple implementation)
        // In a real app, we would clear the timeout loop
        return; 
    }

    // Go to next node
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
        // Push new stack
        dialogueStack.value.push({
            list: opt.dia,
            index: 0
        });
        waitingForChoice.value = false;
        processCurrentNode();
    } else {
        // Empty choice, just continue
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
        // End of Game
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
        advanceIndex(); // Fallback
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
  font-size: 28px;
}

.novel-header p {
  margin: 0;
  opacity: 0.72;
}

.novel-body {
  white-space: pre-wrap;
  line-height: 1.95;
  font-size: 16px;
}
</style>

<style scoped src="./PlayerDesktop.scoped.css"></style>
