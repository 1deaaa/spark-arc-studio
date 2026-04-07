<template>
  <div class="product-home-mobile">
    <header class="mobile-header">
      <div class="logo">SparkArc</div>
      <a href="#/login" class="cta-button">进入工作台</a>
    </header>

    <main class="mobile-main">
      <section class="hero-section">
        <h1 class="hero-title">点燃你的世界</h1>
        <p class="hero-desc">多智能体编剧工作流，只需一个火花，为你构建世界、角色与剧本。</p>
        <button class="primary-btn" @click="$router.push('/login')">开始创作</button>
      </section>

      <section class="features-section">
        <h2 class="section-title">核心功能</h2>
        <div class="feature-card">
          <h3>多智能体协奏</h3>
          <p>大纲编剧、世界观架构、角色塑造多Agent协作。</p>
        </div>
        <div class="feature-card">
          <h3>世界观编织</h3>
          <p>设定集管理动态物品与概念，井井有条。</p>
        </div>
        <div class="feature-card">
          <h3>引擎集成</h3>
          <p>剧本就是游戏数据，导出或映射至游戏引擎。</p>
        </div>
      </section>
    </main>

    <footer class="mobile-footer">
      <p>&copy; 2025 SparkArc Team</p>
    </footer>
  </div>
</template>

<script setup lang="ts">
// 精简移动端Landing
</script>

<style scoped>
.product-home-mobile {
  min-height: 100vh;
  background: #050505;
  color: #fff;
  font-family: sans-serif;
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
}
</style>
