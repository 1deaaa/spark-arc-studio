<template>
  <Teleport to="body">
    <div class="product-home">
      <!-- Canvas for Particle Background -->
      <ParticleBackground />

      <header class="glass-header">
        <div class="logo">SparkArc</div>
        <nav>
          <ul>
            <li><a href="#features" @click.prevent="scrollTo('#features')">{{ t('productHomeDesktop.nav.features') }}</a></li>
            <li><a href="#workflow" @click.prevent="scrollTo('#workflow')">{{ t('productHomeDesktop.nav.workflow') }}</a></li>
            <li><a href="#showcase" @click.prevent="scrollTo('#showcase')">{{ t('productHomeDesktop.nav.showcase') }}</a></li>
          </ul>
        </nav>
        <a href="#/login" class="cta-button">{{ t('productHomeDesktop.nav.enterWorkspace') }}</a>
      </header>

      <main>
        <!-- Hero Section -->
        <section class="hero">
          <div class="hero-content">
            <h1 class="hero-title">{{ t('productHomeDesktop.hero.title') }}</h1>
            <p class="hero-subtitle">{{ t('productHomeDesktop.hero.subtitlePrefix') }} <span class="typing-text">{{ typingText }}</span><span class="cursor">|</span></p>
            <p class="hero-desc">{{ t('productHomeDesktop.hero.desc') }}</p>
            <div class="hero-actions">
              <button class="primary-btn" @click="$router.push('/login')">{{ t('productHomeDesktop.hero.start') }}</button>
              <button class="secondary-btn" @click="scrollTo('#showcase')">{{ t('productHomeDesktop.hero.explore') }}</button>
            </div>
          </div>
        </section>

        <!-- Feature Grid -->
        <section id="features" class="features">
          <h2 class="section-title">{{ t('productHomeDesktop.features.title') }}</h2>
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
              <h3>{{ t('productHomeDesktop.features.items.collab.title') }}</h3>
              <p>{{ t('productHomeDesktop.features.items.collab.desc') }}</p>
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
              <h3>{{ t('productHomeDesktop.features.items.world.title') }}</h3>
              <p>{{ t('productHomeDesktop.features.items.world.desc') }}</p>
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
              <h3>{{ t('productHomeDesktop.features.items.style.title') }}</h3>
              <p>{{ t('productHomeDesktop.features.items.style.desc') }}</p>
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
              <h3>{{ t('productHomeDesktop.features.items.blueprint.title') }}</h3>
              <p>{{ t('productHomeDesktop.features.items.blueprint.desc') }}</p>
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
              <h3>{{ t('productHomeDesktop.features.items.engine.title') }}</h3>
              <p>{{ t('productHomeDesktop.features.items.engine.desc') }}</p>
            </div>
            <div class="feature-card observer-fade-up" style="transition-delay: 500ms;">
              <div class="icon-box">
                <svg class="feature-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M3 12H6L9 5L15 19L18 12H21" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="ekg-anim" />
                </svg>
              </div>
              <h3>{{ t('productHomeDesktop.features.items.emotion.title') }}</h3>
              <p>{{ t('productHomeDesktop.features.items.emotion.desc') }}</p>
            </div>
          </div>
        </section>

        <!-- Deep Dive / Workflow Section -->
        <section id="workflow" class="workflow">
          <h2 class="section-title">{{ t('productHomeDesktop.workflow.title') }}</h2>
          <div class="workflow-steps">
            <div class="step left observer-slide-in">
              <div class="step-content">
                <h3>{{ t('productHomeDesktop.workflow.steps.spark.title') }}</h3>
                <p>{{ t('productHomeDesktop.workflow.steps.spark.desc') }}</p>
              </div>
              <div class="step-marker"></div>
            </div>
            <div class="step right observer-slide-in">
              <div class="step-content">
                <h3>{{ t('productHomeDesktop.workflow.steps.fission.title') }}</h3>
                <p>{{ t('productHomeDesktop.workflow.steps.fission.desc') }}</p>
              </div>
              <div class="step-marker"></div>
            </div>
            <div class="step left observer-slide-in">
              <div class="step-content">
                <h3>{{ t('productHomeDesktop.workflow.steps.blueprint.title') }}</h3>
                <p>{{ t('productHomeDesktop.workflow.steps.blueprint.desc') }}</p>
              </div>
              <div class="step-marker"></div>
            </div>
            <div class="step right observer-slide-in">
              <div class="step-content">
                <h3>{{ t('productHomeDesktop.workflow.steps.drafting.title') }}</h3>
                <p>{{ t('productHomeDesktop.workflow.steps.drafting.desc') }}</p>
              </div>
              <div class="step-marker"></div>
            </div>
            <div class="step left observer-slide-in">
              <div class="step-content">
                <h3>{{ t('productHomeDesktop.workflow.steps.consistency.title') }}</h3>
                <p>{{ t('productHomeDesktop.workflow.steps.consistency.desc') }}</p>
              </div>
              <div class="step-marker"></div>
            </div>
             <div class="step right observer-slide-in">
              <div class="step-content">
                <h3>{{ t('productHomeDesktop.workflow.steps.arc.title') }}</h3>
                <p>{{ t('productHomeDesktop.workflow.steps.arc.desc') }}</p>
              </div>
              <div class="step-marker"></div>
            </div>
          </div>
        </section>

        <!-- All-View Showcase Section -->
        <section id="showcase" class="showcase">
          <h2 class="section-title">{{ t('productHomeDesktop.showcase.title') }}</h2>

          <!-- 1. World View -->
          <div class="showcase-item observer-fade-up">
            <div class="showcase-text">
              <h3>{{ t('productHomeDesktop.showcase.items.world.title') }}</h3>
              <p>{{ t('productHomeDesktop.showcase.items.world.desc') }}</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>{{ t('productHomeDesktop.showcase.items.world.placeholder') }}</span>
            </div>
          </div>

          <!-- 2. Synopsis View -->
          <div class="showcase-item reverse observer-fade-up">
            <div class="showcase-text">
              <h3>{{ t('productHomeDesktop.showcase.items.synopsis.title') }}</h3>
              <p>{{ t('productHomeDesktop.showcase.items.synopsis.desc') }}</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>{{ t('productHomeDesktop.showcase.items.synopsis.placeholder') }}</span>
            </div>
          </div>

          <!-- 3. Structure View -->
          <div class="showcase-item observer-fade-up">
            <div class="showcase-text">
              <h3>{{ t('productHomeDesktop.showcase.items.structure.title') }}</h3>
              <p>{{ t('productHomeDesktop.showcase.items.structure.desc') }}</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>{{ t('productHomeDesktop.showcase.items.structure.placeholder') }}</span>
            </div>
          </div>

          <!-- 4. Production View -->
          <div class="showcase-item reverse observer-fade-up">
            <div class="showcase-text">
              <h3>{{ t('productHomeDesktop.showcase.items.production.title') }}</h3>
              <p>{{ t('productHomeDesktop.showcase.items.production.desc') }}</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>{{ t('productHomeDesktop.showcase.items.production.placeholder') }}</span>
            </div>
          </div>

          <!-- 5. Style View -->
          <div class="showcase-item observer-fade-up">
            <div class="showcase-text">
              <h3>{{ t('productHomeDesktop.showcase.items.style.title') }}</h3>
              <p>{{ t('productHomeDesktop.showcase.items.style.desc') }}</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>{{ t('productHomeDesktop.showcase.items.style.placeholder') }}</span>
            </div>
          </div>

          <!-- 6. Blueprint View -->
          <div class="showcase-item reverse observer-fade-up">
            <div class="showcase-text">
              <h3>{{ t('productHomeDesktop.showcase.items.blueprint.title') }}</h3>
              <p>{{ t('productHomeDesktop.showcase.items.blueprint.desc') }}</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>{{ t('productHomeDesktop.showcase.items.blueprint.placeholder') }}</span>
            </div>
          </div>

          <!-- 7. Engine View -->
          <div class="showcase-item observer-fade-up">
            <div class="showcase-text">
              <h3>{{ t('productHomeDesktop.showcase.items.engine.title') }}</h3>
              <p>{{ t('productHomeDesktop.showcase.items.engine.desc') }}</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>{{ t('productHomeDesktop.showcase.items.engine.placeholder') }}</span>
            </div>
          </div>

          <!-- 8. Settings View -->
          <div class="showcase-item reverse observer-fade-up">
            <div class="showcase-text">
              <h3>{{ t('productHomeDesktop.showcase.items.settings.title') }}</h3>
              <p>{{ t('productHomeDesktop.showcase.items.settings.desc') }}</p>
            </div>
            <div class="showcase-image-placeholder">
              <span>{{ t('productHomeDesktop.showcase.items.settings.placeholder') }}</span>
            </div>
          </div>
        </section>

        <!-- Philosophy Section -->
        <section class="philosophy">
          <h2>{{ t('productHomeDesktop.philosophy.titlePrefix') }}<span class="highlight">{{ t('productHomeDesktop.philosophy.titleHighlight') }}</span></h2>
          <p>{{ t('productHomeDesktop.philosophy.line1') }}</p>
          <p>{{ t('productHomeDesktop.philosophy.line2') }}</p>
          <p>{{ t('productHomeDesktop.philosophy.line3') }}</p>
        </section>
      </main>

      <footer>
        <div class="footer-content">
          <div class="footer-col">
            <h4>SparkArc</h4>
            <p>{{ t('productHomeDesktop.footer.brandTagline') }}</p>
          </div>
          <div class="footer-col">
            <h4>{{ t('productHomeDesktop.footer.product') }}</h4>
            <a href="#" @click.prevent="scrollTo('#features')">{{ t('productHomeDesktop.footer.features') }}</a>
            <a href="#">{{ t('productHomeDesktop.footer.pricing') }}</a>
            <a href="#">{{ t('productHomeDesktop.footer.download') }}</a>
          </div>
          <div class="footer-col">
            <h4>{{ t('productHomeDesktop.footer.community') }}</h4>
            <a href="#">Discord</a>
            <a href="#">Twitter</a>
            <a href="#">GitHub</a>
          </div>
        </div>
        <div class="copyright">
          &copy; 2025 SparkArc Team. {{ t('productHomeDesktop.footer.copyright') }}
          <p class="instance-disclaimer">{{ t('productHomeDesktop.footer.instanceDisclaimer') }}</p>
        </div>
      </footer>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue';
import { useI18n } from 'vue-i18n';
import ParticleBackground from '../../components/home/ParticleBackground.vue';

const { t } = useI18n();
const typingText = ref('');
const words = computed(() => [
  t('productHomeDesktop.hero.typingWords.team'),
  t('productHomeDesktop.hero.typingWords.spark'),
  t('productHomeDesktop.hero.typingWords.world'),
  t('productHomeDesktop.hero.typingWords.style'),
  t('productHomeDesktop.hero.typingWords.logic'),
  t('productHomeDesktop.hero.typingWords.game'),
]);
let typingTimer: ReturnType<typeof setTimeout> | null = null;
let particleReqId: number | null = null;

// --- Scroll Logic ---
function scrollTo(selector: string) {
  const el = document.querySelector(selector);
  if (el) el.scrollIntoView({ behavior: 'smooth' });
}

// --- Typing Effect ---
function startTypingEffect() {
  let wordIndex = 0;
  const getWordList = () => words.value;
  
  function type() {
    const currentWords = getWordList();
    const currentWord = currentWords[wordIndex] || '';
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
        const len = getWordList().length || 1;
        wordIndex = (wordIndex + 1) % len;
        type();
      }
    }

    stepType();
  }
  type();
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
  // Small delay to ensure DOM is ready for observer
  setTimeout(initObserver, 100);
});

onUnmounted(() => {
  if (typingTimer) clearTimeout(typingTimer);
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
  background-clip: text;
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
  display: flex; align-items: center; justify-content: center;
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
.instance-disclaimer {
  max-width: 860px;
  margin: 0.8rem auto 0;
  color: #666;
  line-height: 1.6;
  font-size: 0.85rem;
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
