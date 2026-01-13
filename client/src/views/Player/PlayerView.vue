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
        
        const res = await fetch(apiUrl);
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

<style scoped>
/* --- 全局变量与基础设置 --- */
.player-container {
    --bg-color: #0f1115;
    --text-color: #e0e0e0;
    --accent-color: #d4af37; /* 优雅的金色 */
    --accent-glow: rgba(212, 175, 55, 0.3);
    --dialogue-bg: rgba(20, 22, 26, 0.85);
    --font-main: var(--spark-font);
    
    width: 100vw;
    height: 100vh;
    background: var(--bg-color);
    color: var(--text-color);
    font-family: var(--font-main);
    overflow: hidden;
    user-select: none;
    position: relative;
}

/* --- 背景层 --- */
.layer {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
}

.layer.background {
    z-index: 0;
}

.bg-gradient {
    width: 100%;
    height: 100%;
    background: radial-gradient(circle at 50% 30%, #1a1d24 0%, #0f1115 80%);
}

.ambient-particles {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    opacity: 0.6;
}

/* --- 屏幕状态 (Loading, Error, End) --- */
.screen {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    background: var(--bg-color);
}

.loader-content, .error-content, .end-content {
    text-align: center;
    animation: float 3s ease-in-out infinite;
}

.loading-text {
    margin-top: 20px;
    font-size: 1.1rem;
    letter-spacing: 2px;
    color: rgba(255,255,255,0.7);
}

.feather-pen {
    color: var(--accent-color);
    filter: drop-shadow(0 0 5px var(--accent-glow));
}

.btn-retry, .btn-restart {
    margin-top: 30px;
    padding: 10px 30px;
    background: transparent;
    border: 1px solid var(--accent-color);
    color: var(--accent-color);
    font-family: var(--font-main);
    font-size: 1rem;
    cursor: pointer;
    transition: all 0.3s;
}

.btn-retry:hover, .btn-restart:hover {
    background: var(--accent-color);
    color: #000;
    box-shadow: 0 0 15px var(--accent-glow);
}

.end-content h1 {
    font-size: 3rem;
    font-weight: 300;
    letter-spacing: 10px;
    margin-bottom: 10px;
    color: var(--accent-color);
}

.end-content p {
    color: rgba(255,255,255,0.5);
    font-size: 1.2rem;
}

/* --- 游戏舞台 --- */
.game-stage {
    position: relative;
    width: 100%;
    height: 100%;
    cursor: pointer;
    z-index: 10;
}

/* --- 章节标题 --- */
.chapter-title-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(15, 17, 21, 0.6);
    backdrop-filter: blur(2px);
    z-index: 50;
}

.title-content {
    text-align: center;
    color: #fff;
}

.chapter-label {
    display: block;
    font-size: 1rem;
    letter-spacing: 4px;
    color: var(--accent-color);
    margin-bottom: 10px;
    text-transform: uppercase;
}

.title-content h1 {
    font-size: 3.5rem;
    font-weight: 300;
    letter-spacing: 5px;
    margin: 0;
    text-shadow: 0 2px 10px rgba(0,0,0,0.5);
}

.title-divider {
    width: 60px;
    height: 2px;
    background: var(--accent-color);
    margin: 20px auto 0;
    box-shadow: 0 0 5px var(--accent-glow);
}

/* --- UI 层 --- */
.layer.ui {
    z-index: 20;
    pointer-events: none; /* 让点击穿透到 stage */
}

/* --- 对话框 --- */
.dialogue-container {
    position: absolute;
    bottom: 0;
    left: 0;
    width: 100%;
    padding: 0 0 40px 0;
    display: flex;
    justify-content: center;
    pointer-events: auto;
}

.dialogue-box {
    width: 90%;
    max-width: 800px;
    min-height: 180px;
    background: var(--dialogue-bg);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 30px 40px;
    box-sizing: border-box;
    backdrop-filter: blur(10px);
    box-shadow: 0 -5px 30px rgba(0,0,0,0.5);
    position: relative;
    display: flex;
    flex-direction: column;
}

.name-tag-wrapper {
    position: absolute;
    top: -15px;
    left: 30px;
}

.name-tag {
    background: var(--accent-color);
    color: #1a1a1a;
    padding: 4px 15px;
    font-size: 1rem;
    font-weight: bold;
    border-radius: 2px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
    letter-spacing: 1px;
}

.text-content {
    font-size: 1.2rem;
    line-height: 1.8;
    color: #eee;
    flex: 1;
    white-space: pre-wrap;
}

.cursor {
    display: inline-block;
    width: 2px;
    height: 1.2em;
    background: var(--accent-color);
    margin-left: 4px;
    vertical-align: middle;
    animation: blink 1s infinite;
}

.next-indicator {
    position: absolute;
    bottom: 15px;
    right: 20px;
    color: var(--accent-color);
    animation: bounce 1.5s infinite;
    opacity: 0.8;
}

/* --- 选项层 --- */
.choices-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.6);
    backdrop-filter: blur(3px);
    display: flex;
    align-items: center;
    justify-content: center;
    pointer-events: auto;
    z-index: 100;
}

.choices-container {
    display: flex;
    flex-direction: column;
    gap: 20px;
    width: 100%;
    max-width: 500px;
    padding: 20px;
}

.choice-btn {
    position: relative;
    padding: 18px 30px;
    text-align: center;
    cursor: pointer;
    border: 1px solid rgba(255,255,255,0.2);
    background: rgba(20, 22, 26, 0.9);
    transition: all 0.3s ease;
    overflow: hidden;
}

.choice-text {
    position: relative;
    z-index: 2;
    font-size: 1.1rem;
    letter-spacing: 1px;
    color: #fff;
    transition: color 0.3s;
}

.choice-bg {
    position: absolute;
    top: 0;
    left: 0;
    width: 0%;
    height: 100%;
    background: var(--accent-color);
    z-index: 1;
    transition: width 0.3s ease;
}

.choice-btn:hover {
    border-color: var(--accent-color);
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(0,0,0,0.3);
}

.choice-btn:hover .choice-bg {
    width: 100%;
}

.choice-btn:hover .choice-text {
    color: #1a1a1a;
    font-weight: bold;
}

/* --- 动画定义 --- */
@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}

@keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(5px); }
}

@keyframes float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
}

.thought-toggle {
    position: absolute;
    right: 20px;
    top: 20px;
    color: rgba(255, 255, 255, 0.4);
    cursor: pointer;
    transition: color 0.3s;
    z-index: 10;
}

.thought-toggle:hover {
    color: var(--spark-primary, #42b983);
}

.thought-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.thought-panel {
    width: 80%;
    max-width: 600px;
    background: #1e1e1e;
    border: 1px solid #333;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 20px 50px rgba(0,0,0,0.5);
}

.thought-header {
    padding: 15px 20px;
    background: #252525;
    border-bottom: 1px solid #333;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: bold;
    color: #aaa;
}

.thought-body {
    padding: 20px;
    max-height: 400px;
    overflow-y: auto;
    line-height: 1.6;
    color: #ddd;
    font-family: var(--spark-mono);
    font-size: 0.9rem;
    white-space: pre-wrap;
}

.close-btn {
    background: none;
    border: none;
    color: #666;
    font-size: 24px;
    cursor: pointer;
}

.close-btn:hover {
    color: #fff;
}

/* Vue Transitions */
.fade-enter-active, .fade-leave-active {
    transition: opacity 0.5s ease;
}
.fade-enter-from, .fade-leave-to {
    opacity: 0;
}

.fade-slow-enter-active, .fade-slow-leave-active {
    transition: opacity 1.5s ease;
}
.fade-slow-enter-from, .fade-slow-leave-to {
    opacity: 0;
}

.slide-up-enter-active, .slide-up-leave-active {
    transition: all 0.5s cubic-bezier(0.25, 0.8, 0.25, 1);
}
.slide-up-enter-from, .slide-up-leave-to {
    transform: translateY(50px);
    opacity: 0;
}

.fade-slide-up-enter-active, .fade-slide-up-leave-active {
    transition: all 1s ease;
}
.fade-slide-up-enter-from, .fade-slide-up-leave-to {
    opacity: 0;
    transform: translateY(20px);
}

/* --- 移动端适配 --- */
@media (max-width: 768px) {
    .title-content h1 {
        font-size: 2rem;
    }
    
    .dialogue-box {
        width: 95%;
        padding: 20px 25px;
        min-height: 220px; /* 手机上留更多空间给文字 */
    }

    .text-content {
        font-size: 1.1rem;
    }

    .choice-btn {
        padding: 15px 20px;
    }
    
    .name-tag-wrapper {
        left: 20px;
    }
}
</style>