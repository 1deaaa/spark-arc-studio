<template>
  <div class="product-home-mobile">
    <header class="mobile-header">
      <AppBrand class="logo" :size="28" />
      <a href="#/login" class="cta-button">{{ t('productHomeMobile.header.enterWorkspace') }}</a>
    </header>

    <main class="mobile-main">
      <section class="hero-section">
        <h1 class="hero-title">{{ t('productHomeMobile.hero.title') }}</h1>
        <p class="hero-desc">{{ t('productHomeMobile.hero.desc') }}</p>
        <button class="primary-btn" @click="$router.push('/login')">{{ t('productHomeMobile.hero.start') }}</button>
      </section>

      <section class="features-section">
        <h2 class="section-title">{{ t('productHomeMobile.features.title') }}</h2>
        <div class="feature-card">
          <h3>{{ t('productHomeMobile.features.items.collab.title') }}</h3>
          <p>{{ t('productHomeMobile.features.items.collab.desc') }}</p>
        </div>
        <div class="feature-card">
          <h3>{{ t('productHomeMobile.features.items.world.title') }}</h3>
          <p>{{ t('productHomeMobile.features.items.world.desc') }}</p>
        </div>
        <div class="feature-card">
          <h3>{{ t('productHomeMobile.features.items.engine.title') }}</h3>
          <p>{{ t('productHomeMobile.features.items.engine.desc') }}</p>
        </div>
      </section>
    </main>

    <footer class="mobile-footer">
      <p><a :href="SPARKARC_GITHUB_URL" target="_blank" rel="noopener" class="mobile-footer-link">&copy; 2025 SparkArc Team</a></p>
      <p class="instance-disclaimer">{{ t('productHomeMobile.footer.instanceDisclaimer') }}</p>
    </footer>
  </div>
</template>

<script setup lang="ts">
// 精简移动端Landing
import AppBrand from '@/components/share/AppBrand.vue';
import { useI18n } from 'vue-i18n';
import { SPARKARC_GITHUB_URL } from '@/config';

const { t } = useI18n();
</script>

<style scoped>
.product-home-mobile {
  min-height: 100vh;
  background: #050505;
  color: #fff;
  font-family: var(--spark-font), sans-serif;
  overflow-x: hidden;
  padding-bottom: 24px;
}

.mobile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: rgba(5,5,5,0.8);
  backdrop-filter: blur(10px);
  position: sticky;
  top: 0;
  z-index: 100;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}

.logo {
  display: inline-flex;
  align-items: center;
  font-size: 1.2rem;
  font-weight: 700;
  color: #fff;
}

.cta-button {
  padding: 6px 12px;
  border: 1px solid #ffaa40;
  color: #ffaa40;
  border-radius: 20px;
  font-size: 0.8rem;
  text-decoration: none;
}

.mobile-main {
  padding: 32px 20px;
  display: flex;
  flex-direction: column;
  gap: 40px;
}

.hero-section {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.hero-title {
  font-size: 2.2rem;
  background: linear-gradient(to right, #fff, #888);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0;
}

.hero-desc {
  font-size: 0.95rem;
  color: #888;
  line-height: 1.5;
  margin: 0;
}

.primary-btn {
  margin-top: 10px;
  padding: 10px 24px;
  background: #ffaa40;
  color: #000;
  border: none;
  border-radius: 24px;
  font-weight: 600;
  font-size: 1rem;
}

.section-title {
  font-size: 1.5rem;
  margin-bottom: 20px;
  text-align: center;
}

.features-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.feature-card {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  padding: 16px;
}

.feature-card h3 {
  margin: 0 0 8px;
  color: #ffaa40;
  font-size: 1.1rem;
}

.feature-card p {
  margin: 0;
  color: #aaa;
  font-size: 0.9rem;
  line-height: 1.4;
}

.mobile-footer {
  text-align: center;
  color: #555;
  font-size: 0.8rem;
  margin-top: 40px;
  padding: 0 18px;
}
.mobile-footer-link {
  color: inherit;
  text-decoration: none;
  transition: opacity 0.2s;
}
.mobile-footer-link:hover {
  opacity: 0.7;
  text-decoration: underline;
}

.instance-disclaimer {
  max-width: 340px;
  margin: 8px auto 0;
  color: #777;
  line-height: 1.5;
}
</style>
