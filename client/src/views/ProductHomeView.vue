<template>
  <Teleport to="body">
    <div class="product-home">
      <!-- Canvas for Particle Background -->
      <canvas ref="canvasRef" id="sparkCanvas"></canvas>

      <header class="glass-header">
        <div class="logo">SparkArc</div>
        <nav>
          <ul>
            <li><a href="#features" @click.prevent="scrollTo('#features')">核心功能</a></li>
            <li><a href="#workflow" @click.prevent="scrollTo('#workflow')">工作流</a></li>
            <li><a href="#showcase" @click.prevent="scrollTo('#showcase')">全景展示</a></li>
          </ul>
        </nav>
        <a href="/#/login" class="cta-button">进入工作台</a>
      </header>

      <main>
        <!-- Hero Section -->
        <section class="hero">
          <div class="hero-content">
            <h1 class="hero-title">点燃你的世界</h1>
            <p class="hero-subtitle">拥有 <span class="typing-text">{{ typingText }}</span><span class="cursor">|</span></p>
            <p class="hero-desc">专业级多智能体编剧工作流。只需一个灵感的火花，Agent 协作组为你构建完整的世界观、角色与剧本。</p>
            <div class="hero-actions">
              <button class="primary-btn" @click="$router.push('/login')">开始创作</button>
              <button class="secondary-btn" @click="scrollTo('#showcase')">探索功能</button>
            </div>
          </div>
        </section>

        <!-- Feature Grid -->
        <section id="features" class="features">
          <h2 class="section-title">全流程智能辅助</h2>
          <div class="feature-grid">
            <div class="feature-card observer-fade-up">
              <div class="icon-box">
                <svg class="feature-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
                  <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                  <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                  <circle cx="12" cy="7" r="1.5" class="pulse-dot" fill="currentColor" />
                  <circle cx="12" cy="12" r="1.5" class="pulse-dot" fill="currentColor" style="animation-delay: 0.5s" />
                  <circle cx="12" cy="17" r="1.5" class="pulse-dot" fill="currentColor" style="animation-delay: 1s" />
                </svg>
              </div>
              <h3>多智能体协奏</h3>
              <p>大纲编剧、世界观架构师、角色塑造师多Agent协作。告别孤独创作，你的背后是一个团队。</p>
            </div>
            <div class="feature-card observer-fade-up" style="transition-delay: 100ms;">
              <div class="icon-box">
                <svg class="feature-icon spin-slow" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <circle cx="12" cy="12" r="10" stroke-width="1.5" />
                  <path d="M12 2C14.5 2 16.5 6.5 16.5 12C16.5 17.5 14.5 22 12 22" stroke-width="1.5" stroke-linecap="round" />
                  <path d="M12 2C9.5 2 7.5 6.5 7.5 12C7.5 17.5 9.5 22 12 22" stroke-width="1.5" stroke-linecap="round" />
                  <path d="M2 12H22" stroke-width="1.5" stroke-linecap="round" />
                </svg>
              </div>
              <h3>世界观编织者</h3>
              <p>Lorebook 设定集管理动态物品与概念。从宏大历史到微小道具，井井有条，自动关联。</p>
            </div>
            <div class="feature-card observer-fade-up" style="transition-delay: 200ms;">
              <div class="icon-box">
                <svg class="feature-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M12 4C13.5 4 16.5 6 16.5 9C16.5 11.5 15 13 12 11C9 13 7.5 11.5 7.5 9C7.5 6 10.5 4 12 4Z" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                  <path d="M12 14C8 14 3 16 3 19V21H21V19C21 16 16 14 12 14Z" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                  <path d="M18 7L21 4" stroke-width="1.5" stroke-linecap="round" class="float-stroke" />
                  <path d="M6 7L3 4" stroke-width="1.5" stroke-linecap="round" class="float-stroke" style="animation-delay: 0.5s" />
                </svg>
              </div>
              <h3>文风模拟</h3>
              <p>Style Imitation 模块。让 AI 学习并模仿特定作者风格，无论是莎士比亚还是现代极简，随心切换。</p>
            </div>
            <div class="feature-card observer-fade-up" style="transition-delay: 300ms;">
              <div class="icon-box">
                <svg class="feature-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <circle cx="6" cy="18" r="2" stroke-width="1.5" />
                  <circle cx="18" cy="6" r="2" stroke-width="1.5" />
                  <path d="M8 17L16 7" stroke-width="1.5" stroke-linecap="round" class="dash-draw" />
                  <path d="M6 8V5H9" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                  <path d="M18 16V19H15" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
              </div>
              <h3>结构化大纲</h3>
              <p>两点一线，自动补全。设置起点与终点，AI 为你生成中间的过渡剧情与关键转折。</p>
            </div>
            <div class="feature-card observer-fade-up" style="transition-delay: 400ms;">
              <div class="icon-box">
                <svg class="feature-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <rect x="2" y="6" width="20" height="12" rx="4" stroke-width="1.5" />
                  <path d="M6 12H8" stroke-width="1.5" stroke-linecap="round" />
                  <path d="M7 11V13" stroke-width="1.5" stroke-linecap="round" />
                  <circle cx="16" cy="12" r="1.5" fill="currentColor" class="blink-dot" />
                  <circle cx="18" cy="11" r="0.5" fill="currentColor" />
                </svg>
              </div>
              <h3>引擎深度集成</h3>
              <p>Agent 函数映射与 Unity 直连。你的剧本就是游戏的数据，修改即生效，无需繁琐导出。</p>
            </div>
            <div class="feature-card observer-fade-up" style="transition-delay: 500ms;">
              <div class="icon-box">
                <svg class="feature-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M3 12H6L9 5L15 19L18 12H21" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="ekg-anim" />
                </svg>
              </div>
              <h3>情感与节奏</h3>
              <p>可视化情绪曲线控制。拒绝 AI 写作的平淡（AI Flavor），注入人类的情感起伏。</p>
            </div>
          </div>
        </section>

        <!-- Deep Dive / Workflow Section -->
        <section id="workflow" class="workflow">
          <h2 class="section-title">从火花到长虹</h2>
          <div class="workflow-steps">
            <div class="step left observer-slide-in">
              <div class="step-content">
                <h3>1. 灵感乍现</h3>
                <p>哪怕只是一句歌词、一张图片或一个模糊的念头。SparkArc 都能以此为起点。</p>
              </div>
              <div class="step-marker"></div>
            </div>
            <div class="step right observer-slide-in">
              <div class="step-content">
                <h3>2. 智能裂变</h3>
                <p>Agent 团队各司其职。世界观自动填充，角色卡自动生成，初步大纲瞬间成型。</p>
              </div>
              <div class="step-marker"></div>
            </div>
            <div class="step left observer-slide-in">
              <div class="step-content">
                <h3>3. 专业打磨</h3>
                <p>防止“吃书”的全文一致性检查。节点式编辑器让逻辑清晰可见。</p>
              </div>
              <div class="step-marker"></div>
            </div>
            <div class="step right observer-slide-in">
              <div class="step-content">
                <h3>4. 实时演出</h3>
                <p>WEB 端一键分享演出作品。不仅是剧本，更是可以直接体验的互动故事。</p>
              </div>
              <div class="step-marker"></div>
            </div>
          </div>
        </section>

        <!-- All-View Showcase Section -->
        <section id="showcase" class="showcase">
          <h2 class="section-title">全景功能展示</h2>

          <!-- 1. Production View -->
          <div class="showcase-item observer-fade-up">
            <div class="showcase-text">
              <h3>主工作台：灵感的指挥塔</h3>
              <p>这里是您创作的核心。节点式对话树让由于剧情分支一目了然，与 AI 助手的实时协作让文字如泉涌般流出。既有宏观的逻辑掌控，又有微观的字句推敲。</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>[请插入: Production View / 节点编辑与对话树界面截图]</span>
            </div>
          </div>

          <!-- 2. World View -->
          <div class="showcase-item reverse observer-fade-up">
            <div class="showcase-text">
              <h3>世界观：上帝的账本</h3>
              <p>从国家地理到魔法体系，从角色关系到物品设定。Lorebook 万物皆有档，随时供 AI 调用，确保您的世界设定严谨而生动，永不吃书。</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>[请插入: World View / Lorebook 设定集界面截图]</span>
            </div>
          </div>

          <!-- 3. Style View -->
          <div class="showcase-item observer-fade-up">
            <div class="showcase-text">
              <h3>文风模拟：千面作家</h3>
              <p>不仅仅是“写得好”，而是“写得像”。上传参考文本，微调参数，让 Agent 完美复刻特定的叙事风格。无论是严肃史诗还是轻松日常，随心切换。</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>[请插入: Style View / 文风配置界面截图]</span>
            </div>
          </div>

          <!-- 4. Structure View -->
          <div class="showcase-item reverse observer-fade-up">
            <div class="showcase-text">
              <h3>结构蓝图：骨架与灵魂</h3>
              <p>迷失在细节中？退后一步，看清故事的脉络。拖拽节点，规划章节，两点一线间，AI 自动为你填补剧情的血肉。</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>[请插入: Structure View / 结构大纲界面截图]</span>
            </div>
          </div>

          <!-- 5. Synopsis View -->
          <div class="showcase-item observer-fade-up">
            <div class="showcase-text">
              <h3>故事梗概：一句话的宇宙</h3>
              <p>万事开头难？从一句话开始（Logline），扩展成一段简介，再裂变成完整的篇章。这是故事的起点，也是创意的孵化器。</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>[请插入: Synopsis View / 梗概生成界面截图]</span>
            </div>
          </div>

          <!-- 6. Engine View -->
          <div class="showcase-item reverse observer-fade-up">
            <div class="showcase-text">
              <h3>引擎映射：虚实之桥</h3>
              <p>剧本不再是死文字。在这里，将 Agent 的决策直接映射到游戏引擎的函数（Function Calling）。对话触发事件，选择改变世界。</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>[请插入: Engine View / 函数映射界面截图]</span>
            </div>
          </div>

          <!-- 7. Settings View -->
          <div class="showcase-item observer-fade-up">
            <div class="showcase-text">
              <h3>设置：控制中心</h3>
              <p>调整模型参数，管理 API 密钥，配置全局快捷键。打造最顺手的创作环境。</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>[请插入: Settings View / 全局设置界面截图]</span>
            </div>
          </div>
        </section>

        <!-- Philosophy Section -->
        <section class="philosophy">
          <h2>拒绝机械，拥抱<span class="highlight">灵魂</span></h2>
          <p>SparkArc 不是又一个冷冰冰的生成器。在这个算法泛滥的时代，我们捍卫人类灵感的主权。</p>
          <p>情感，必须源于你的脉搏；故事，必须始于你的震颤。</p>
          <p>让 AI 臣服于你的创造力，而非取代它。</p>
        </section>
      </main>

      <footer>
        <div class="footer-content">
          <div class="footer-col">
            <h4>SparkArc</h4>
            <p>点燃你的世界。</p>
          </div>
          <div class="footer-col">
            <h4>产品</h4>
            <a href="#" @click.prevent="scrollTo('#features')">核心功能</a>
            <a href="#">定价</a>
            <a href="#">下载</a>
          </div>
          <div class="footer-col">
            <h4>社区</h4>
            <a href="#">Discord</a>
            <a href="#">Twitter</a>
            <a href="#">GitHub</a>
          </div>
        </div>
        <div class="copyright">
          &copy; 2025 SparkArc Team. 保留所有权利.
        </div>
      </footer>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';

const canvasRef = ref(null);
const typingText = ref('');
const words = ["智能体协作", "无限灵感", "情感深度", "精准控制"];
let typingTimer = null;
let particleReqId = null;

// --- Scroll Logic ---
function scrollTo(selector) {
  const el = document.querySelector(selector);
  if (el) el.scrollIntoView({ behavior: 'smooth' });
}

// --- Typing Effect ---
function startTypingEffect() {
  let wordIndex = 0;
  
  function type() {
    const currentWord = words[wordIndex];
    let charIndex = 0;
    
    function stepType() {
      if (charIndex <= currentWord.length) {
        typingText.value = currentWord.substring(0, charIndex);
        charIndex++;
        typingTimer = setTimeout(stepType, 100);
      } else {
        typingTimer = setTimeout(stepDelete, 2000);
      }
    }

    function stepDelete() {
      if (charIndex >= 0) {
        typingText.value = currentWord.substring(0, charIndex);
        charIndex--;
        typingTimer = setTimeout(stepDelete, 50);
      } else {
        wordIndex = (wordIndex + 1) % words.length;
        stepType();
      }
    }

    stepType();
  }
  type();
}

// --- Particle System (Original Star Effect) ---
class Particle {
  constructor(canvas) {
    this.canvas = canvas;
    this.reset();
    this.y = Math.random() * canvas.height;
    this.x = Math.random() * canvas.width;
  }
  reset() {
    this.x = Math.random() * this.canvas.width;
    this.y = this.canvas.height + Math.random() * 100;
    this.speed = Math.random() * 2 + 0.5;
    this.size = Math.random() * 3;
    this.color = Math.random() > 0.5 ? '#ffaa40' : '#40c9ff';
    this.opacity = Math.random() * 0.5 + 0.1;
    this.wobble = Math.random() * Math.PI * 2;
    this.wobbleSpeed = Math.random() * 0.05;
  }
  update() {
    this.y -= this.speed;
    this.wobble += this.wobbleSpeed;
    this.x += Math.sin(this.wobble) * 0.5;
    if (this.y < this.canvas.height * 0.8) this.opacity -= 0.005;
    if (this.y < -50 || this.opacity <= 0) this.reset();
  }
  draw(ctx) {
    ctx.fillStyle = this.color;
    ctx.globalAlpha = this.opacity;
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;
  }
}

function initParticles() {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  
  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  window.addEventListener('resize', resize);
  resize();

  const particles = Array.from({ length: 80 }, () => new Particle(canvas));

  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    particles.forEach(p => p.update());
    particles.forEach(p => p.draw(ctx));
    particleReqId = requestAnimationFrame(animate);
  }
  animate();
}

// --- Intersection Observer ---
function initObserver() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
      }
    });
  }, { threshold: 0.1, rootMargin: "0px 0px -50px 0px" });

  document.querySelectorAll('.observer-fade-up, .observer-slide-in').forEach(el => observer.observe(el));
}

// --- Lifecycle ---
onMounted(() => {
  startTypingEffect();
  initParticles();
  // Small delay to ensure DOM is ready for observer
  setTimeout(initObserver, 100);
});

onUnmounted(() => {
  if (typingTimer) clearTimeout(typingTimer);
  if (particleReqId) cancelAnimationFrame(particleReqId);
  // Remove event listeners if any were attached to window that aren't auto-cleaned
});

</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Outfit:wght@300;500;700&display=swap');

/* Scoped variables simulation */
.product-home {
  --bg-color: #050505;
  --text-color: #ffffff;
  --text-muted: #888888;
  --primary-color: #ffaa40;
  --secondary-color: #40c9ff;
  --glass-bg: rgba(255, 255, 255, 0.05);
  --glass-border: rgba(255, 255, 255, 0.1);
  --font-heading: 'Outfit', 'Microsoft YaHei', 'PingFang SC', sans-serif;
  --font-body: 'Inter', 'Microsoft YaHei', 'PingFang SC', sans-serif;
  
  background-color: var(--bg-color);
  color: var(--text-color);
  font-family: var(--font-body);
  width: 100vw; /* Force full width */
  height: 100vh;
  position: fixed; /* Break out of the flow */
  top: 0;
  left: 0;
  overflow-y: auto; /* Enable scrolling within this view */
  overflow-x: hidden;
  z-index: 9999; /* Ensure it sits on top if needed */
  display: block; /* Reset display */
}

/* Reset for this component context */
ul { list-style: none; padding: 0; margin: 0; }
a { text-decoration: none; }
h1, h2, h3, p { margin: 0; }

#sparkCanvas {
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  z-index: 0;
  pointer-events: none;
}

/* Header */
.glass-header {
  position: fixed;
  top: 0; left: 0;
  width: 100%;
  padding: 1rem 5%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(5, 5, 5, 0.7);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--glass-border);
  z-index: 1000;
}

.logo {
  font-family: var(--font-heading);
  font-weight: 700;
  font-size: 1.5rem;
  color: var(--text-color);
  text-transform: uppercase;
  letter-spacing: 2px;
}

nav ul { display: flex; gap: 2rem; }
nav a {
  color: var(--text-muted);
  font-weight: 500;
  transition: color 0.3s;
  cursor: pointer;
}
nav a:hover { color: var(--primary-color); }

.cta-button {
  padding: 0.5rem 1.5rem;
  border: 1px solid var(--primary-color);
  color: var(--primary-color);
  border-radius: 50px;
  transition: all 0.3s;
  font-weight: 600;
  font-size: 0.8rem;
  letter-spacing: 1px;
}
.cta-button:hover {
  background: var(--primary-color);
  color: black;
  box-shadow: 0 0 20px rgba(255, 170, 64, 0.5);
}

/* Hero */
main {
  position: relative;
  z-index: 1;
  display: block !important; /* Override global layout.css "display: flex" */
  width: 100%;
  height: auto;
  overflow: visible;
}
.hero {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 0 1rem;
}
.hero-content { max-width: 800px; }
.hero-title {
  font-family: var(--font-heading);
  font-size: 4rem;
  margin-bottom: 1rem;
  background: linear-gradient(to right, #ffffff, #888888);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: fadeUp 1s ease-out;
}
.hero-subtitle {
  font-size: 1.5rem;
  color: var(--primary-color);
  margin-bottom: 2rem;
  height: 2rem;
  animation: fadeUp 1s ease-out 0.2s backwards;
}
.cursor { animation: blink 1s step-end infinite; color: var(--text-muted); margin-left: 2px;}
@keyframes blink { 50% { opacity: 0; } }

.hero-desc {
  font-size: 1.1rem;
  color: var(--text-muted);
  margin-bottom: 3rem;
  max-width: 600px;
  margin-left: auto; margin-right: auto;
  animation: fadeUp 1s ease-out 0.4s backwards;
}
.hero-actions {
  display: flex; justify-content: center; gap: 1.5rem;
  animation: fadeUp 1s ease-out 0.6s backwards;
}
.primary-btn, .secondary-btn {
  padding: 1rem 2rem;
  border-radius: 50px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  border: none;
  font-size: 1rem;
}
.primary-btn { background: var(--primary-color); color: black; }
.primary-btn:hover { transform: translateY(-2px); box-shadow: 0 0 30px rgba(255, 170, 64, 0.6); }
.secondary-btn { background: transparent; border: 1px solid var(--glass-border); color: white; }
.secondary-btn:hover { background: var(--glass-bg); border-color: white; }

/* Sections */
section { padding: 8rem 5%; }
.section-title {
  font-family: var(--font-heading);
  font-size: 2.5rem;
  text-align: center;
  margin-bottom: 4rem;
  color: white;
}

/* Features */
.features { background: radial-gradient(circle at center, rgba(64, 201, 255, 0.05) 0%, transparent 70%); }
.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 2rem;
}
/* Feature Card & Icons */
.feature-card {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  padding: 2rem;
  border-radius: 16px;
  transition: transform 0.3s, box-shadow 0.3s;
  backdrop-filter: blur(5px);
  display: flex; flex-direction: column; align-items: flex-start;
}
.feature-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
  border-color: var(--secondary-color);
}
.icon-box {
  width: 50px; height: 50px;
  margin-bottom: 1.5rem;
  color: var(--primary-color);
  display: flex; align-items: center; justifyContent: center;
}

.feature-icon {
  width: 100%; height: 100%;
}

/* SVG Animations */
.pulse-dot { animation: pulseOpacity 2s infinite; }
@keyframes pulseOpacity { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }

.spin-slow { animation: spin 10s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.dash-draw {
  stroke-dasharray: 20; stroke-dashoffset: 20;
  animation: drawLine 3s ease-in-out infinite alternate;
}
@keyframes drawLine { to { stroke-dashoffset: 0; } }

.ekg-anim {
  stroke-dasharray: 30; stroke-dashoffset: 30;
  animation: heartBeat 2s linear infinite;
}
@keyframes heartBeat {
  0% { stroke-dashoffset: 30; }
  15% { stroke-dashoffset: 0; }
  85% { stroke-dashoffset: 0; }
  100% { stroke-dashoffset: -30; }
}

.blink-dot { animation: blink 1s step-end infinite; }
.float-stroke { animation: floatStroke 3s ease-in-out infinite; }
@keyframes floatStroke { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-3px); } }

.feature-card h3 { margin-bottom: 1rem; font-family: var(--font-heading); }
.feature-card p { color: var(--text-muted); font-size: 0.95rem; }

/* Workflow */
.workflow { position: relative; max-width: 1000px; margin: 0 auto; }
.workflow-steps { display: flex; flex-direction: column; position: relative; }
.workflow-steps::before {
  content: ''; position: absolute; left: 50%; top: 0; bottom: 0; width: 2px;
  background: linear-gradient(to bottom, transparent, var(--primary-color), transparent);
  transform: translateX(-50%);
}
.step {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 4rem; position: relative;
}
.step-marker {
  width: 20px; height: 20px; background: var(--primary-color);
  border-radius: 50%; position: absolute; left: 50%;
  transform: translateX(-50%); box-shadow: 0 0 20px var(--primary-color); z-index: 2;
}
.step-content {
  width: 45%; background: var(--glass-bg);
  padding: 2rem; border-radius: 12px;
  border: 1px solid var(--glass-border);
}
.step.left .step-content { margin-right: auto; text-align: right; }
.step.right .step-content { margin-left: auto; text-align: left; }

/* Showcase */
.showcase-item {
  display: flex; align-items: center; gap: 4rem; margin-bottom: 6rem;
}
.showcase-item.reverse { flex-direction: row-reverse; }
.showcase-text { flex: 1; }
.showcase-text h3 {
  font-size: 2rem; margin-bottom: 1rem;
  font-family: var(--font-heading); color: var(--secondary-color);
}
.showcase-image-placeholder {
  flex: 1.5; height: 350px;
  background: #111;
  border: 1px dashed var(--text-muted);
  display: flex; align-items: center; justify-content: center;
  border-radius: 12px;
  color: var(--text-muted);
  text-align: center; padding: 2rem;
  position: relative; overflow: hidden;
}
.showcase-image-placeholder::after {
  content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
  background: linear-gradient(45deg, transparent 40%, rgba(255,255,255,0.05) 50%, transparent 60%);
  transition: transform 0.5s; transform: translateX(-100%);
}
.showcase-image-placeholder:hover::after { transform: translateX(100%); }

/* Philosophy */
.philosophy {
  text-align: center; padding: 10rem 5%;
  background: radial-gradient(circle at center, rgba(255, 170, 64, 0.05) 0%, transparent 60%);
  position: relative; overflow: hidden;
}
.philosophy h2 {
  font-size: 3.5rem; font-family: var(--font-heading);
  margin-bottom: 2rem; color: white;
  text-shadow: 0 0 20px rgba(255, 170, 64, 0.3);
  animation: pulseGlow 4s infinite ease-in-out;
}
.philosophy p {
  font-size: 1.25rem; max-width: 800px;
  margin: 0 auto 1rem; color: var(--text-muted);
}
.philosophy .highlight { color: var(--primary-color); font-weight: 700; }

/* Footer */
footer {
  background: #020202; padding: 4rem 5% 2rem;
  border-top: 1px solid var(--glass-border);
}
.footer-content {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 3rem; margin-bottom: 3rem;
}
.footer-col h4 { margin-bottom: 1.5rem; color: white; }
.footer-col a {
  display: block; color: var(--text-muted);
  text-decoration: none; margin-bottom: 0.8rem;
  transition: color 0.3s;
}
.footer-col a:hover { color: var(--primary-color); }
.copyright {
  text-align: center; color: #444;
  padding-top: 2rem; border-top: 1px solid #111;
}

/* Animations & Observer States */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes pulseGlow {
  0% { transform: scale(1); text-shadow: 0 0 20px rgba(255, 170, 64, 0.3); }
  50% { transform: scale(1.02); text-shadow: 0 0 40px rgba(255, 170, 64, 0.6); }
  100% { transform: scale(1); text-shadow: 0 0 20px rgba(255, 170, 64, 0.3); }
}

.observer-fade-up { opacity: 0; transform: translateY(30px); transition: all 0.8s ease-out; }
.observer-fade-up.visible { opacity: 1; transform: translateY(0); }

.observer-slide-in { opacity: 0; transform: translateX(-30px); transition: all 0.8s ease-out; }
.step.right.observer-slide-in { transform: translateX(30px); }
.observer-slide-in.visible { opacity: 1; transform: translateX(0); }

/* Responsive */
@media (max-width: 768px) {
  .hero-title { font-size: 2.5rem; }
  .workflow-steps::before { left: 20px; }
  .step-marker { left: 20px; }
  .step { flex-direction: column; align-items: flex-start; padding-left: 50px; }
  .step-content { width: 100%; text-align: left !important; }
  .showcase-item, .showcase-item.reverse { flex-direction: column; gap: 2rem; }
}
</style>
