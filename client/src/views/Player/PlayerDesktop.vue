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
          <p class="loading-text">故事正在生成...</p>
        </div>
      </div>
    </transition>

    <!-- 3. 错误界面 -->
    <transition name="fade">
      <div v-if="error" class="screen error-screen">
        <div class="error-content">
          <h3>无法加载故事</h3>
          <p>{{ error }}</p>
          <button class="btn-retry" @click="loadGame">重试</button>
        </div>
      </div>
    </transition>

    <!-- 4. 游戏主舞台 -->
    <transition name="fade-slow">
      <div v-if="!loading && !error && !gameEnded" class="game-stage" @click="handleStageClick">
        
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
                    <span class="chapter-label">Chapter {{ currentScene?.chapter || '1' }}</span>
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
                  <span>AI 思维链 (Thought Process)</span>
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
          <h1>剧 终</h1>
          <p>感谢您的体验</p>
          <button class="btn-restart" @click="restartGame">重新开始</button>
        </div>
      </div>
    </transition>

  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRoute } from 'vue-router';
import { resolveApiUrl } from '@/services/apiClient';

const route = useRoute();
const shareId = route.params.shareId;

const loading = ref(true);
const error = ref(null);
const gameEnded = ref(false);
const storyData = ref(null);
const charMap = ref({});
const registry = ref({});

// Game State
const currentSceneIndex = ref(0);
const currentDialogueIndex = ref(0);
const dialogueStack = ref([]); // For nested choices
const displayedText = ref('');
const isTyping = ref(false);
const showTitle = ref(false);
const waitingForChoice = ref(false);
const showThought = ref(false);

// Computed
const currentScene = computed(() => {
    if (!storyData.value) return null;
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
    if (chrId === -1 || chrId === '-1') return ''; // Narration
    if (chrId === 0 || chrId === '0') return '我'; // Default protagonist
    return charMap.value[chrId] || '???';
});

const currentChoices = computed(() => {
    if (!currentDialogue.value) return [];
    return currentDialogue.value.opt || [];
});

const currentCharacter = computed(() => {
    // TODO: Determine which character is visible based on speaker
    return null;
});

// Methods
async function loadGame() {
    loading.value = true;
    error.value = null;
    gameEnded.value = false;
    try {
        // 判断是否是版本分享链接
        const isVersionPlay = route.path.includes('/play/v/');
        const apiUrl = isVersionPlay ? `/api/play/v/${shareId}/data` : `/api/play/${shareId}/data`;
        
        const res = await fetch(resolveApiUrl(apiUrl));
        if (!res.ok) throw new Error('无法加载剧本数据，请检查链接是否有效');
        const data = await res.json();
        storyData.value = data.stories;
        charMap.value = data.characters;
        registry.value = data.registry;
        
        startGame();
    } catch (e) {
        error.value = e.message;
    } finally {
        loading.value = false;
    }
}

function startGame() {
    currentSceneIndex.value = 0;
    currentDialogueIndex.value = 0;
    dialogueStack.value = [];
    gameEnded.value = false;
    showTitle.value = true;
    setTimeout(() => {
        showTitle.value = false;
        // 标题消失后开始处理第一个节点
        // 如果第一个节点就是选项，processCurrentNode会处理
    }, 3500);
    processCurrentNode();
}

function restartGame() {
    startGame();
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
}

function executeAction(key, value) {
    console.log(`[Action] ${key}:`, value);
    
    // 简单的内置行为实现
    switch (key.toLowerCase()) {
        case 'bg':
            // 设置背景颜色或图片（示例）
            document.body.style.backgroundColor = Array.isArray(value) ? value[0] : value;
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

function typeText(text) {
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

function handleChoice(opt) {
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
        showTitle.value = true;
        setTimeout(() => showTitle.value = false, 3500);
        processCurrentNode();
    } else {
        // End of Game
        gameEnded.value = true;
    }
}

function jumpToScene(sceneName) {
    const idx = storyData.value.findIndex(s => s.scene_name === sceneName);
    if (idx !== -1) {
        currentSceneIndex.value = idx;
        currentDialogueIndex.value = 0;
        dialogueStack.value = [];
        showTitle.value = true;
        setTimeout(() => showTitle.value = false, 3500);
        processCurrentNode();
    } else {
        console.warn(`Scene ${sceneName} not found`);
        advanceIndex(); // Fallback
        processCurrentNode();
    }
}

onMounted(() => {
    loadGame();
});
</script>

<style scoped src="./PlayerDesktop.scoped.css"></style>
