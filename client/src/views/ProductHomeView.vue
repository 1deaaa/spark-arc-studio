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
              <h3>故事蓝图</h3>
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
                <h3>1. 灵感火花 (Spark)</h3>
                <p>一切始于微小的光亮。哪怕只是一句歌词、一段见闻、或是一个模糊的概念，SparkArc 都能捕捉这瞬时的花火，以此为原点启动创作引擎。</p>
              </div>
              <div class="step-marker"></div>
            </div>
            <div class="step right observer-slide-in">
              <div class="step-content">
                <h3>2. 智能裂变 (Fission)</h3>
                <p>拒绝孤军奋战。Agent 团队迅速响应：世界观架构师填充背景，角色塑造师生成人设，大纲编剧搭建骨架。一个人的灵感，瞬间裂变为一个团队的方案。</p>
              </div>
              <div class="step-marker"></div>
            </div>
            <div class="step left observer-slide-in">
              <div class="step-content">
                <h3>3. 结构蓝图 (Blueprint)</h3>
                <p>可视化节点编辑。以“两点一线”的方式规划剧情，设置起点与终点，AI 自动为你填补中间的关键转折与过渡。逻辑可视化，告别烂尾。</p>
              </div>
              <div class="step-marker"></div>
            </div>
            <div class="step right observer-slide-in">
              <div class="step-content">
                <h3>4. 深度撰写 (Drafting)</h3>
                <p>精准控制对话与旁白比例。文风模拟模块确保输出不仅逻辑通顺，更具文学风味。告别“AI味”，保留人类创作的细腻质感。</p>
              </div>
              <div class="step-marker"></div>
            </div>
            <div class="step left observer-slide-in">
              <div class="step-content">
                <h3>5. 全文一致 (Consistency)</h3>
                <p>严谨的逻辑守卫。AI 实时扫描全文，自动检测“吃书”设定冲突，维护时间线与逻辑链的完美闭环。这也是最枯燥的工作，请放心交给它。</p>
              </div>
              <div class="step-marker"></div>
            </div>
             <div class="step right observer-slide-in">
              <div class="step-content">
                <h3>6. 虚实具象 (Arc)</h3>
                <p>终点亦是起点。将剧本一键导出为交互式 Web 作品分享，或直接映射到 Unity 引擎作为游戏数据。你的故事，此刻已触手可及。</p>
              </div>
              <div class="step-marker"></div>
            </div>
          </div>
        </section>

        <!-- All-View Showcase Section -->
        <section id="showcase" class="showcase">
          <h2 class="section-title">全景功能展示</h2>

          <!-- 1. World View -->
          <div class="showcase-item observer-fade-up">
            <div class="showcase-text">
              <h3>世界观：灵感缪斯与设定集</h3>
              <p>输入一个梦境、歌词或瞬间的感觉，点燃灵感（Muse）引擎，自动生成完整的世界观与角色设定。内置 Lorebook 管理器，让万物皆有档，确保设定严谨不吃书。</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>[请插入: World View / 灵感输入与 Lorebook 界面截图]</span>
            </div>
          </div>

          <!-- 2. Synopsis View -->
          <div class="showcase-item reverse observer-fade-up">
            <div class="showcase-text">
              <h3>故事梗概：从 Logline 到节拍表</h3>
              <p>从一句话的核心概念（Logline）出发，扩写成完整梗概。自动生成节拍表（Beat Sheet），并可视化呈现故事的情感曲线与张力起伏。</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>[请插入: Synopsis View / 梗概与节拍表界面截图]</span>
            </div>
          </div>

          <!-- 3. Structure View -->
          <div class="showcase-item observer-fade-up">
            <div class="showcase-text">
              <h3>大纲与节奏：总编剧的规划板</h3>
              <p>设定章节数量，输入导演意图与剧情上下文。AI 自动规划分章大纲，为您搭建故事的骨架，确保起承转合逻辑清晰。</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>[请插入: Structure View / 大纲生成与编辑界面截图]</span>
            </div>
          </div>

          <!-- 4. Production View -->
          <div class="showcase-item reverse observer-fade-up">
            <div class="showcase-text">
              <h3>剧本创作：节点式对话树</h3>
              <p>主工作台采用节点编辑器（Node Editor）构建非线性对话。左侧管理文件与场景，右侧实时预览属性。AI 助手随时待命，辅助生成对话分支。</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>[请插入: Production View / 节点编辑与对话树界面截图]</span>
            </div>
          </div>

          <!-- 5. Style View -->
          <div class="showcase-item observer-fade-up">
            <div class="showcase-text">
              <h3>风格管理：AI 文风克隆</h3>
              <p>上传 txt 或 epub 格式的小说文件，AI 深度分析并提取作者的叙事风格。创建专属的风格档案（Style Profile），让生成的剧本拥有独特的文学质感。</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>[请插入: Style View / 风格分析与管理界面截图]</span>
            </div>
          </div>

          <!-- 6. Blueprint View -->
          <div class="showcase-item reverse observer-fade-up">
            <div class="showcase-text">
              <h3>故事蓝图：全景可视化</h3>
              <p>跳出线性文本，以鸟瞰视角审视项目结构。可视化连接文件与场景节点，直观管理庞大的剧情分支与跳转逻辑。</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>[请插入: Blueprint View / 故事蓝图节点图截图]</span>
            </div>
          </div>

          <!-- 7. Engine View -->
          <div class="showcase-item observer-fade-up">
            <div class="showcase-text">
              <h3>引擎绑定：Agent Flow 与函数映射</h3>
              <p>可视化编排 Agent 工作流（Agent Flow），并将剧本中的事件直接绑定到游戏引擎的函数。实现剧本与游戏逻辑的无缝对接。</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>[请插入: Engine View / Agent Flow 与绑定编辑器截图]</span>
            </div>
          </div>

          <!-- 8. Settings View -->
          <div class="showcase-item reverse observer-fade-up">
            <div class="showcase-text">
              <h3>设置：模型与平台管理</h3>
              <p>集中管理 AI 模型配置、API 密钥与发布平台。查看系统公告，自定义外观设置，打造最舒适的创作环境。</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>[请插入: Settings View / 设置面板截图]</span>
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
const words = [
  "全天候的编剧团队", 
  "无限的灵感火花", 
  "严谨的世界架构", 
  "独特的文学质感", 
  "完美的逻辑闭环", 
  "交互式的游戏灵魂"
];
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
        type();
      }
    }

    stepType();
  }
  type();
}

// --- Particle System (Original Star Effect + 3D Neural Sphere) ---
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
    this.size = Math.random() * 2.5; // Slightly smaller for higher density
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

// --- 3D Heartbeat Star System (Enhanced with Creative Outline) ---
class StarParticle {
  constructor() {
    this.reset();
  }
  reset() {
    // Spherical distribution
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos((Math.random() * 2) - 1);
    // Ring inner edge is ~275 (350 - 75 bandWidth)
    // Expand core to nearly fill up to ring edge
    const radius = 50 + Math.random() * 500; // Range: 50-280 (Fills to ring inner edge)

    this.x = radius * Math.sin(phi) * Math.cos(theta);
    this.y = radius * Math.sin(phi) * Math.sin(theta);
    this.z = radius * Math.cos(phi);
    
    this.baseX = this.x; this.baseY = this.y; this.baseZ = this.z;
    this.size = Math.random() * 2.5;
    this.colorType = Math.random(); 
    this.life = Math.random();
    this.decay = 0.005 + Math.random() * 0.01;
  }
  
  rotateY(angle) {
    const cos = Math.cos(angle); const sin = Math.sin(angle);
    const x = this.x * cos - this.z * sin;
    const z = this.x * sin + this.z * cos;
    this.x = x; this.z = z;
  }
  rotateX(angle) {
    const cos = Math.cos(angle); const sin = Math.sin(angle);
    const y = this.y * cos - this.z * sin;
    const z = this.y * sin + this.z * cos;
    this.y = y; this.z = z;
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

  // 1. Background Float Particles (Subtle)
  const bgParticles = Array.from({ length: 120 }, () => new Particle(canvas));

  // 2. Heartbeat Star Particles (Dense)
  const starParticles = Array.from({ length: 500 }, () => new StarParticle());

  function drawCreativeOutline(ctx, centerX, centerY, time, scale) {
    const numPoints = 360; 
    const baseRadius = 350; // Do not pre-scale, we handle morphing ourselves
    
    // Morph Factor: How much the shape is a "star" vs a "circle"
    // scale goes from 1.0 (rest) to ~1.25 (peak)
    // map this to morphFactor: 0 (circle) to 1 (full star)
    const morphFactor = Math.min(1, Math.max(0, (scale - 1) / 0.25));
    
    // Single Lightning Layer with Randomized Height Constraint
    ctx.beginPath();
    const maxBandWidth = 75;
    
    for (let i = 0; i <= numPoints; i++) {
        const angle = (i / numPoints) * Math.PI * 2;
        
        // 0. Star Shape Component (4-pointed)
        // Increased amplitude for more pronounced star
        const starWave = Math.pow(Math.abs(Math.cos(angle * 2)), 0.4); // Sharper peaks
        const starOffset = starWave * 100 * morphFactor; // Up to 100px outward at peaks (doubled)
        
        // 1. Random Depth Constraint (Chaotic Band)
        // Increased base chaos when in circle mode
        const t = time * 0.0005;
        const depthNoise = Math.sin(angle * 7.23 + t) * Math.cos(angle * 3.14 - t * 0.7) * 0.5 + 0.5;
        const baseChaosFactor = 1 + (1 - morphFactor) * 0.5; // More chaos when circle (morphFactor=0)
        const randomDepth = Math.random() * maxBandWidth * depthNoise * baseChaosFactor;
        
        // 2. Chaotic Lightning Component (Non-Periodic)
        const phi = 1.6180339887;
        const sqrt2 = 1.41421356;
        const sqrt3 = 1.73205080;
        
        // Increased amplitudes for more irregularity
        const wave1 = Math.sin(angle * 17 * phi + t * 0.8) * 12 * baseChaosFactor;
        const wave2 = Math.cos(angle * 23 * sqrt2 - t * 1.2) * 10 * baseChaosFactor;
        const wave3 = Math.sin(angle * 31 * sqrt3 + t * 0.6) * 6 * baseChaosFactor;
        const wave4 = Math.cos(angle * 11 + Math.sin(t * 0.15) * 5) * 7 * baseChaosFactor;
        
        const electric = wave1 + wave2 + wave3 + wave4;
                         
        // Random Jitter - increased for more chaos
        const flash = Math.sin(time * 0.01) > 0.85 ? 1.5 : 1;
        const jitter = (Math.random() - 0.5) * 18 * flash * baseChaosFactor; 
        
        // Occasional large spikes - more frequent
        const spike = Math.random() > 0.975 ? (Math.random() * 45) : 0;

        // 3. Combine: baseRadius * scale (breathing) + star morph + noise
        const r = (baseRadius * scale) + starOffset - randomDepth + electric + jitter + spike;

        const x = centerX + Math.cos(angle) * r;
        const y = centerY + Math.sin(angle) * r;
        
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.closePath();
    
    // Glowing Stroke - Organic Gold
    ctx.strokeStyle = `rgba(255, 200, 100, 0.6)`;
    ctx.lineWidth = 2.5;
    ctx.lineJoin = 'round';
    ctx.stroke();
  }


  function drawStar(time) {
    if (window.scrollY > window.innerHeight) return;

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2 - 50; 
    
    // Heartbeat Pulse Logic - SLOW RHYTHM (30 BPM)
    // Decreased speed by 50% (0.006 -> 0.003)
    const pulseScale = 1 + Math.pow(Math.sin(time * 0.003), 40) * 0.25; 

    // Global Rotation
    const rotationSpeed = 0.003;
    
    // Additive Blending for Glow
    ctx.globalCompositeOperation = 'lighter';

    // Draw the Creative Outline
    drawCreativeOutline(ctx, centerX, centerY, time, pulseScale);

    starParticles.forEach(p => {
      // Rotate
      p.rotateY(rotationSpeed);
      p.rotateX(rotationSpeed * 0.3);

      // Pulse
      const currentX = p.x * pulseScale;
      const currentY = p.y * pulseScale;
      const currentZ = p.z * pulseScale;

      // 3D Projection
      const fov = 300;
      const scale = fov / (fov + currentZ + 400); 
      const x2d = currentX * scale + centerX;
      const y2d = currentY * scale + centerY;
      
      // Color Logic
      const alpha = (currentZ + 200) / 400; 
      if (alpha > 0) {
        ctx.beginPath();
        const size = p.size * scale * (pulseScale * 1.5);
        ctx.arc(x2d, y2d, size, 0, Math.PI * 2);
        
        // Dynamic Hot Colors
        if (p.colorType > 0.9) ctx.fillStyle = `rgba(200, 230, 255, ${alpha})`; // Blue-White hotspots
        else if (p.colorType > 0.6) ctx.fillStyle = `rgba(255, 200, 100, ${alpha})`; // Gold
        else ctx.fillStyle = `rgba(255, 100, 50, ${alpha * 0.8})`; // Orange-Red core
        
        ctx.fill();
      }
    });

    ctx.globalCompositeOperation = 'source-over'; // Reset blend mode
  }

  function animate(time) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw Background
    bgParticles.forEach(p => p.update());
    bgParticles.forEach(p => p.draw(ctx));

    // Draw Heartbeat Star
    drawStar(time);

    particleReqId = requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
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
