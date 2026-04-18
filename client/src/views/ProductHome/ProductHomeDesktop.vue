<!--
  ProductHomeDesktop · 桌面端产品主页（九幕叙事 · 文学工业书页风）
  组装入口：统一主题变量 + 背景层 + 九幕 + 顶栏/页脚
-->
<template>
  <Teleport to="body">
    <div class="product-home" ref="rootRef">
      <!-- 全局视觉背景层（纸色 + 蓝图网格 + 星火粒子） -->
      <BlueprintGrid class="bg-grid" />
      <EmberField class="bg-ember" />

      <!-- 顶栏 + 九幕 + 页脚 -->
      <SiteChrome position="top" />

      <main class="stage">
        <ActHero />
        <ActSeed />
        <ActPipeline />
        <ActEnsemble />
        <ActFreedom />
        <ActGuard />
        <ActControl />
        <ActStage />
        <ActFinale />
      </main>

      <SiteChrome position="bottom" />
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue';

// 字体本地打包
import '@fontsource/ma-shan-zheng/400.css';

// 视觉背景层
import BlueprintGrid from './parts/visuals/BlueprintGrid.vue';
import EmberField from './parts/visuals/EmberField.vue';

// 九幕
import ActHero from './parts/ActHero.vue';
import ActSeed from './parts/ActSeed.vue';
import ActPipeline from './parts/ActPipeline.vue';
import ActEnsemble from './parts/ActEnsemble.vue';
import ActFreedom from './parts/ActFreedom.vue';
import ActGuard from './parts/ActGuard.vue';
import ActControl from './parts/ActControl.vue';
import ActStage from './parts/ActStage.vue';
import ActFinale from './parts/ActFinale.vue';

// 顶栏 + 页脚
import SiteChrome from './parts/SiteChrome.vue';

const rootRef = ref<HTMLElement | null>(null);
</script>

<style>
/* ============================================================
   SparkArc · ProductHomeDesktop
   文学工业书页风 · 全局主题变量 · 仅作用于 .product-home 作用域
   ============================================================ */
.product-home {
  /* 书页底色 */
  --paper: #FAF6EE;
  --paper-deep: #F2EBDA;
  --paper-night: #1A1612;

  /* 墨色 */
  --ink: #2A2420;
  --ink-soft: #524943;
  --ink-ghost: rgba(42, 36, 32, 0.08);

  /* 星火系 */
  --ember: #E8854C;
  --ember-deep: #C56733;
  --ember-glow: rgba(232, 133, 76, 0.25);

  /* 温暖金 */
  --gold: #F7D98A;
  --gold-soft: #FBE9BC;

  /* 辅色 */
  --moss: #4A6741;
  --slate: #5C6B80;
  --crimson: #B84A3F;

  /* 蓝图 */
  --blueprint: rgba(74, 103, 65, 0.06);
  --blueprint-k: rgba(74, 103, 65, 0.14);

  /* 字体 */
  --font-display: var(--spark-font);
  --font-hand: var(--spark-font);
  --font-body: var(--spark-font);
  --font-mono: var(--spark-mono);

  /* 框架 */
  position: fixed;
  inset: 0;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--spark-font);
  font-size: 16px;
  line-height: 1.7;
  z-index: 1000;

  /* 强制浅色主题：本页不继承全局暗色变量 */
  color-scheme: light;
}

/* 背景层定位：铺满、不拦截事件 */
.product-home .bg-grid,
.product-home .bg-ember {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}
.product-home .bg-grid { z-index: 0; }
.product-home .bg-ember { z-index: 1; }

.product-home .stage {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
}

/* 每一幕的通用容器样式 */
.product-home .act {
  position: relative;
  width: 100%;
  padding: 8rem 6vw;
  box-sizing: border-box;
}

/* 章节页码印刷感（所有幕复用） */
.product-home .act-chapter-mark {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  letter-spacing: 0.3em;
  color: var(--ink-soft);
  opacity: 0.55;
  text-transform: uppercase;
}

/* 章节大标题 */
.product-home .act-title {
  font-family: var(--font-display);
  font-weight: 400;
  color: var(--ink);
  letter-spacing: 0.04em;
  line-height: 1.25;
}

/* 通用 CTA 印章按钮 */
.product-home .stamp-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.85rem 1.8rem;
  font-family: var(--font-display);
  font-size: 1.05rem;
  letter-spacing: 0.12em;
  color: #fff;
  background: var(--ember);
  border: 1.5px solid var(--ember-deep);
  border-radius: 2px;
  box-shadow: 0 2px 0 var(--ember-deep), 0 6px 16px var(--ember-glow);
  cursor: pointer;
  transition: transform 160ms ease, box-shadow 160ms ease, background 160ms ease;
  text-decoration: none;
  user-select: none;
}
.product-home .stamp-btn:hover {
  background: var(--ember-deep);
  transform: translateY(1px);
  box-shadow: 0 1px 0 var(--ember-deep), 0 4px 10px var(--ember-glow);
}
.product-home .stamp-btn:active {
  transform: translateY(2px);
  box-shadow: 0 0 0 var(--ember-deep), 0 2px 6px var(--ember-glow);
}

.product-home .ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.85rem 1.8rem;
  font-family: var(--font-display);
  font-size: 1.05rem;
  letter-spacing: 0.12em;
  color: var(--ink);
  background: transparent;
  border: 1.5px solid var(--ink);
  border-radius: 2px;
  cursor: pointer;
  transition: background 160ms ease, color 160ms ease;
  text-decoration: none;
  user-select: none;
}
.product-home .ghost-btn:hover {
  background: var(--ink);
  color: var(--paper);
}

/* 入场淡入（IntersectionObserver 接管） */
.product-home .fade-up {
  opacity: 0;
  transform: translateY(32px);
  transition: opacity 900ms cubic-bezier(0.22, 0.61, 0.36, 1),
              transform 900ms cubic-bezier(0.22, 0.61, 0.36, 1);
}
.product-home .fade-up.is-visible {
  opacity: 1;
  transform: translateY(0);
}

/* 降级：尊重 reduce motion */
@media (prefers-reduced-motion: reduce) {
  .product-home .fade-up {
    transition: opacity 200ms ease;
    transform: none;
  }
}

/* 滚动条美化 */
.product-home::-webkit-scrollbar { width: 10px; }
.product-home::-webkit-scrollbar-track { background: var(--paper-deep); }
.product-home::-webkit-scrollbar-thumb {
  background: var(--ink-soft);
  border-radius: 4px;
  border: 2px solid var(--paper-deep);
}
.product-home::-webkit-scrollbar-thumb:hover { background: var(--ink); }

/* 通用选择文本颜色 */
.product-home ::selection {
  background: var(--ember-glow);
  color: var(--ink);
}
</style>
