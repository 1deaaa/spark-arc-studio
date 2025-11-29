<template>
  <div class="player-container" :class="{ 'loading': loading }">
    <div v-if="loading" class="loading-screen">
      <div class="spinner"></div>
      <p>正在加载剧本...</p>
    </div>

    <div v-else-if="error" class="error-screen">
      <p>{{ error }}</p>
    </div>

    <div v-else class="game-stage" @click="handleStageClick">
      <!-- Background Layer -->
      <div class="layer background" :style="backgroundStyle"></div>

      <!-- Character Layer -->
      <div class="layer characters">
        <!-- Placeholder for character sprites -->
        <transition name="fade">
            <div v-if="currentCharacter" class="character-sprite">
                <!-- If we had images, they would go here. For now, a silhouette or just name -->
            </div>
        </transition>
      </div>

      <!-- UI Layer -->
      <div class="layer ui">
        
        <!-- Title / Chapter Info (Fade out after start) -->
        <transition name="fade-slow">
            <div v-if="showTitle" class="chapter-title">
                <h1>{{ currentScene?.caption || currentScene?.scene_name }}</h1>
            </div>
        </transition>

        <!-- Dialogue Box -->
        <div class="dialogue-box" v-show="currentDialogue">
          <div class="name-tag" v-if="currentSpeakerName">
            {{ currentSpeakerName }}
          </div>
          <div class="text-content">
            {{ displayedText }}<span class="cursor" v-if="isTyping">|</span>
          </div>
          <div class="next-indicator" v-if="!isTyping && !waitingForChoice">
            ▼
          </div>
        </div>

        <!-- Choices Overlay -->
        <div class="choices-overlay" v-if="waitingForChoice">
          <div 
            v-for="(opt, idx) in currentChoices" 
            :key="idx" 
            class="choice-btn"
            @click.stop="handleChoice(opt)"
          >
            {{ opt.optn }}
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const shareId = route.params.shareId;

const loading = ref(true);
const error = ref(null);
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
    if (chrId === 0 || chrId === '0') return '我'; // Default protagonist
    if (chrId === -1 || chrId === '-1') return ''; // Narration
    return charMap.value[chrId] || '???';
});

const currentChoices = computed(() => {
    if (!currentDialogue.value) return [];
    return currentDialogue.value.opt || [];
});

const backgroundStyle = computed(() => {
    // TODO: Use registry or act commands to set background
    return { backgroundColor: '#1a1a1a' };
});

const currentCharacter = computed(() => {
    // TODO: Determine which character is visible based on speaker
    return null;
});

// Methods
async function loadGame() {
    try {
        const res = await fetch(`/api/play/${shareId}/data`);
        if (!res.ok) throw new Error('无法加载剧本数据');
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
    showTitle.value = true;
    setTimeout(() => showTitle.value = false, 3000);
    processCurrentNode();
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

    // Check for choices
    if (node.opt && node.opt.length > 0) {
        waitingForChoice.value = true;
        typeText(node.txt || '');
    } else {
        waitingForChoice.value = false;
        typeText(node.txt || '');
    }
    
    // Handle @next (Jump)
    if (node.next) {
        // We will handle jump after click if it's a dialogue, 
        // but if it's purely a jump node (no text), we might jump immediately?
        // For now, assume jump happens after reading text.
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
    if (loading.value || error.value || waitingForChoice.value) return;

    if (isTyping.value) {
        // Instant finish typing
        // We need to stop the timeout loop - simplified here by just setting full text
        // In a real robust impl, we'd clear timeout. 
        // For this simple version, let's just let it finish or implement a proper cancel.
        // A simple hack: set i to length in typeText scope? 
        // Let's just ignore click during typing for MVP or make it instant.
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
        setTimeout(() => showTitle.value = false, 3000);
        processCurrentNode();
    } else {
        // End of Game
        alert("剧本结束");
    }
}

function jumpToScene(sceneName) {
    const idx = storyData.value.findIndex(s => s.scene_name === sceneName);
    if (idx !== -1) {
        currentSceneIndex.value = idx;
        currentDialogueIndex.value = 0;
        dialogueStack.value = [];
        showTitle.value = true;
        setTimeout(() => showTitle.value = false, 3000);
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
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;700&display=swap');

.player-container {
    width: 100vw;
    height: 100vh;
    background: #000;
    color: #fff;
    font-family: 'Noto Serif SC', serif;
    overflow: hidden;
    user-select: none;
}

.loading-screen, .error-screen {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
}

.spinner {
    width: 40px;
    height: 40px;
    border: 4px solid rgba(255,255,255,0.3);
    border-radius: 50%;
    border-top-color: #fff;
    animation: spin 1s ease-in-out infinite;
    margin-bottom: 20px;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.game-stage {
    position: relative;
    width: 100%;
    height: 100%;
    cursor: pointer;
}

.layer {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none; /* Let clicks pass through to stage */
}

.layer.ui {
    pointer-events: none;
}

.dialogue-box {
    position: absolute;
    bottom: 5%;
    left: 10%;
    width: 80%;
    height: 25vh;
    background: rgba(0, 0, 0, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 4px;
    padding: 20px 40px;
    box-sizing: border-box;
    backdrop-filter: blur(5px);
    pointer-events: auto;
    display: flex;
    flex-direction: column;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
}

.name-tag {
    font-size: 1.2rem;
    font-weight: bold;
    color: #ffd700;
    margin-bottom: 10px;
    text-shadow: 0 2px 4px rgba(0,0,0,0.5);
}

.text-content {
    font-size: 1.1rem;
    line-height: 1.6;
    flex: 1;
    color: #eee;
}

.next-indicator {
    position: absolute;
    bottom: 15px;
    right: 20px;
    animation: bounce 1s infinite;
}

@keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(5px); }
}

.choices-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.4);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 20px;
    pointer-events: auto;
    z-index: 100;
}

.choice-btn {
    background: rgba(255, 255, 255, 0.9);
    color: #000;
    padding: 15px 40px;
    min-width: 300px;
    text-align: center;
    border-radius: 2px;
    cursor: pointer;
    font-size: 1.1rem;
    transition: all 0.2s;
    box-shadow: 0 4px 10px rgba(0,0,0,0.3);
}

.choice-btn:hover {
    transform: scale(1.05);
    background: #fff;
    box-shadow: 0 6px 15px rgba(0,0,0,0.4);
}

.chapter-title {
    position: absolute;
    top: 30%;
    width: 100%;
    text-align: center;
    color: #fff;
    text-shadow: 0 0 10px rgba(0,0,0,0.8);
    z-index: 50;
}

.chapter-title h1 {
    font-size: 3rem;
    font-weight: 300;
    letter-spacing: 5px;
}

/* Transitions */
.fade-enter-active, .fade-leave-active {
    transition: opacity 0.5s;
}
.fade-enter-from, .fade-leave-to {
    opacity: 0;
}

.fade-slow-enter-active, .fade-slow-leave-active {
    transition: opacity 2s;
}
.fade-slow-enter-from, .fade-slow-leave-to {
    opacity: 0;
}

.cursor {
    display: inline-block;
    animation: blink 1s infinite;
}

@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}
</style>
