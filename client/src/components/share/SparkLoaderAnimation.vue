<template>
  <div class="spark-loader-wrapper">
    <div class="spark-loader">
          <!-- 脉冲涟漪：灵感之心的心跳 -->
          <div class="pulse-rings">
            <div class="pulse-ring ring-1"></div>
            <div class="pulse-ring ring-2"></div>
            <div class="pulse-ring ring-3"></div>
          </div>
          
          <svg class="spark-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <!-- 柔和辉光 -->
              <filter id="gl-glow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
              <!-- 核心强辉光 -->
              <filter id="gl-glow-core" x="-100%" y="-100%" width="300%" height="300%">
                <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
              <!-- 核心星星径向渐变 -->
              <radialGradient id="gl-core-grad" cx="50%" cy="50%" r="50%">
                <stop offset="0%" style="stop-color: var(--loader-core-bright); stop-opacity: 1" />
                <stop offset="60%" style="stop-color: var(--loader-primary); stop-opacity: 0.85" />
                <stop offset="100%" style="stop-color: var(--loader-primary); stop-opacity: 0.4" />
              </radialGradient>
            </defs>
            
            <!-- 外圈星河轨道弧 -->
            <circle cx="50" cy="50" r="44" class="orbit orbit-outer" />
            
            <!-- 内圈星河轨道弧 -->
            <circle cx="50" cy="50" r="33" class="orbit orbit-inner" />

            <!-- 外圈轨道能量流光：沿轨道分布的光点依次明灭，让轨道"流动"起来 -->
            <g class="energy-flow flow-outer">
              <circle cx="93" cy="40" r="1.2" class="flow-dot fd1" filter="url(#gl-glow)" />
              <circle cx="80" cy="18" r="1" class="flow-dot fd2" filter="url(#gl-glow)" />
              <circle cx="50" cy="6" r="1.1" class="flow-dot fd3" filter="url(#gl-glow)" />
              <circle cx="20" cy="18" r="0.9" class="flow-dot fd4" filter="url(#gl-glow)" />
              <circle cx="8" cy="42" r="1.2" class="flow-dot fd5" filter="url(#gl-glow)" />
            </g>

            <!-- 内圈轨道能量流光 -->
            <g class="energy-flow flow-inner">
              <circle cx="83" cy="50" r="1" class="flow-dot fd6" filter="url(#gl-glow)" />
              <circle cx="67" cy="73" r="0.9" class="flow-dot fd7" filter="url(#gl-glow)" />
              <circle cx="33" cy="73" r="1" class="flow-dot fd8" filter="url(#gl-glow)" />
              <circle cx="17" cy="50" r="0.8" class="flow-dot fd9" filter="url(#gl-glow)" />
            </g>

            <!-- 星河微尘：散布在轨道间的极小闪烁星点，填充星河气氛 -->
            <g class="stardust">
              <circle cx="25" cy="28" r="0.7" class="dust-dot dd1" />
              <circle cx="76" cy="30" r="0.5" class="dust-dot dd2" />
              <circle cx="78" cy="72" r="0.6" class="dust-dot dd3" />
              <circle cx="22" cy="70" r="0.5" class="dust-dot dd4" />
              <circle cx="50" cy="25" r="0.4" class="dust-dot dd5" />
            </g>

            <!-- 灵感汇聚节点：四个方位的能量点依次脉冲，暗示灵感在汇聚 -->
            <g class="convergence-group">
              <circle cx="35" cy="35" r="1.3" class="conv-dot cv1" filter="url(#gl-glow)" />
              <circle cx="65" cy="35" r="1" class="conv-dot cv2" filter="url(#gl-glow)" />
              <circle cx="65" cy="65" r="1.3" class="conv-dot cv3" filter="url(#gl-glow)" />
              <circle cx="35" cy="65" r="1" class="conv-dot cv4" filter="url(#gl-glow)" />
            </g>
            
            <!-- 外圈卫星 1：主思绪流 -->
            <g class="sat-group sg-outer-1">
              <circle cx="50" cy="6" r="3.5" class="satellite sat-primary" filter="url(#gl-glow-core)" />
              <circle cx="47" cy="9" r="2" class="sat-trail st1" />
              <circle cx="44.5" cy="12.5" r="1.2" class="sat-trail st2" />
              <circle cx="42.5" cy="16.5" r="0.6" class="sat-trail st3" />
            </g>
            
            <!-- 内圈卫星 2：逆向思绪流 -->
            <g class="sat-group sg-inner">
              <circle cx="50" cy="83" r="2.5" class="satellite sat-secondary" filter="url(#gl-glow)" />
              <circle cx="52.5" cy="80.5" r="1.3" class="sat-trail st1" />
              <circle cx="54.5" cy="78" r="0.7" class="sat-trail st2" />
            </g>

            <!-- 外圈卫星 3：灵感碎片 -->
            <g class="sat-group sg-outer-2">
              <circle cx="94" cy="50" r="2" class="satellite sat-accent" filter="url(#gl-glow)" />
              <circle cx="91.5" cy="47.5" r="1" class="sat-trail st1" />
              <circle cx="89" cy="45.5" r="0.5" class="sat-trail st2" />
            </g>

            <!-- 核心辐射光芒：4道极细光线从中心向外延伸，缓慢旋转 -->
            <g class="ray-group">
              <line x1="50" y1="50" x2="50" y2="18" class="core-ray ray1" />
              <line x1="50" y1="50" x2="82" y2="50" class="core-ray ray2" />
              <line x1="50" y1="50" x2="50" y2="82" class="core-ray ray3" />
              <line x1="50" y1="50" x2="18" y2="50" class="core-ray ray4" />
            </g>
            
            <!-- 核心：灵感之心（四角星） -->
            <g class="core-group">
              <!-- 外层光晕呼吸 -->
              <circle cx="50" cy="50" r="12" class="core-halo" />
              <!-- 四角星主体 -->
              <path 
                class="core-star" 
                d="M50 22 L57 43 L78 50 L57 57 L50 78 L43 57 L22 50 L43 43 Z" 
                fill="url(#gl-core-grad)" 
                filter="url(#gl-glow-core)" 
              />
              <!-- 中心高亮点 -->
              <circle cx="50" cy="50" r="4" class="core-center" />
            </g>
          </svg>
        </div>
  </div>
</template>

<style scoped>

.spark-loader-wrapper {
  --loader-primary: var(--spark-primary);
  --loader-core-bright: var(--spark-primary-light);
  --loader-glow: var(--spark-primary-glow);
  --loader-orbit-outer: var(--spark-primary);
  --loader-orbit-inner: var(--spark-harmonious-a);
  --loader-text: var(--spark-text-muted);
}

:root[data-theme="light"] .spark-loader-wrapper,
.light .spark-loader-wrapper {
  --loader-glow: color-mix(in srgb, var(--spark-primary), transparent 55%);
}

/* ===== 加载器容器 ===== */
.spark-loader {
  position: relative;
  width: 110px;
  height: 110px;
  margin-bottom: 28px;
}


/* ===== 第2层：脉冲涟漪（灵感心跳） ===== */
.pulse-rings {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.pulse-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  border: 1px solid var(--loader-glow);
  border-radius: 50%;
  opacity: 0;
  animation: heartbeat-pulse 4s ease-out infinite;
}

.pulse-ring.ring-1 {
  animation-delay: 0s;
}

.pulse-ring.ring-2 {
  animation-delay: 1.33s;
}

.pulse-ring.ring-3 {
  animation-delay: 2.66s;
}

@keyframes heartbeat-pulse {
  0% {
    width: 24px;
    height: 24px;
    opacity: 0.45;
  }

  100% {
    width: 150px;
    height: 150px;
    opacity: 0;
  }
}


/* ===== SVG 画布 ===== */
.spark-svg {
  width: 100%;
  height: 100%;
  overflow: visible;
  position: relative;
  z-index: 2;
}


/* ===== 第3层：星河轨道弧 ===== */
.orbit {
  fill: none;
  stroke-width: 1;
  stroke-linecap: round;
}

/* 外圈轨道：约62%可见弧段，顺时针缓转 */
.orbit-outer {
  stroke: var(--loader-orbit-outer);
  stroke-dasharray: 170 107;
  opacity: 0.35;
  transform-origin: 50px 50px;
  animation: orbit-spin-cw 20s linear infinite;
  filter: drop-shadow(0 0 3px var(--loader-glow));
}

/* 内圈轨道：约48%可见弧段，逆时针缓转 */
.orbit-inner {
  stroke: var(--loader-orbit-inner);
  stroke-dasharray: 100 108;
  opacity: 0.25;
  transform-origin: 50px 50px;
  animation: orbit-spin-ccw 16s linear infinite;
}

@keyframes orbit-spin-cw {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

@keyframes orbit-spin-ccw {
  from {
    transform: rotate(360deg);
  }

  to {
    transform: rotate(0deg);
  }
}


/* ===== 轨道能量流光：沿轨道分布的光点依次呼吸，让轨道看起来在"流淌" ===== */
.energy-flow {
  transform-origin: 50px 50px;
}

/* 外圈流光跟随外轨道旋转 */
.flow-outer {
  animation: orbit-spin-cw 20s linear infinite;
}

/* 内圈流光跟随内轨道旋转 */
.flow-inner {
  animation: orbit-spin-ccw 16s linear infinite;
}

.flow-dot {
  fill: var(--loader-primary);
  opacity: 0;
  animation: flow-pulse 2.5s ease-in-out infinite;
}

/* 沿轨道依次点亮，形成流动感 */
.flow-dot.fd1 {
  animation-delay: 0s;
}

.flow-dot.fd2 {
  animation-delay: 0.5s;
}

.flow-dot.fd3 {
  animation-delay: 1s;
}

.flow-dot.fd4 {
  animation-delay: 1.5s;
}

.flow-dot.fd5 {
  animation-delay: 2s;
}

.flow-dot.fd6 {
  animation-delay: 0.3s;
}

.flow-dot.fd7 {
  animation-delay: 0.9s;
}

.flow-dot.fd8 {
  animation-delay: 1.5s;
}

.flow-dot.fd9 {
  animation-delay: 2.1s;
}

@keyframes flow-pulse {

  0%,
  100% {
    opacity: 0;
    transform: scale(0.6);
  }

  50% {
    opacity: 0.6;
    transform: scale(1.3);
  }
}


/* ===== 星河微尘：轨道间极小的闪烁星点，填充视觉空隙 ===== */
.dust-dot {
  fill: var(--loader-text);
  opacity: 0;
  animation: dust-twinkle 4s ease-in-out infinite;
}

.dust-dot.dd1 {
  animation-delay: 0s;
}

.dust-dot.dd2 {
  animation-delay: 0.8s;
}

.dust-dot.dd3 {
  animation-delay: 1.6s;
}

.dust-dot.dd4 {
  animation-delay: 2.4s;
}

.dust-dot.dd5 {
  animation-delay: 3.2s;
}

@keyframes dust-twinkle {

  0%,
  100% {
    opacity: 0;
    transform: scale(0.7);
  }

  50% {
    opacity: 0.4;
    transform: scale(1.2);
  }
}


/* ===== 第5层：灵感汇聚节点 ===== */
.conv-dot {
  fill: var(--loader-primary);
  opacity: 0;
  animation: convergence-pulse 3s ease-in-out infinite;
}

/* 四个方位依次点亮，像灵感火花轮番闪烁 */
.conv-dot.cv1 {
  animation-delay: 0s;
}

.conv-dot.cv2 {
  animation-delay: 0.75s;
}

.conv-dot.cv3 {
  animation-delay: 1.5s;
}

.conv-dot.cv4 {
  animation-delay: 2.25s;
}

@keyframes convergence-pulse {

  0%,
  100% {
    opacity: 0;
    transform: scale(0.5);
  }

  50% {
    opacity: 0.65;
    transform: scale(1.4);
  }
}


/* ===== 第4层：卫星（思绪流星） ===== */
.sat-group {
  transform-origin: 50px 50px;
}

/* 外圈卫星1 — 主思绪：顺时针，较快 */
.sg-outer-1 {
  animation: orbit-spin-cw 10s linear infinite;
}

/* 内圈卫星2 — 逆向思绪：逆时针，稍慢 */
.sg-inner {
  animation: orbit-spin-ccw 14s linear infinite;
}

/* 外圈卫星3 — 灵感碎片：顺时针，与卫星1同速但偏移 */
.sg-outer-2 {
  animation: orbit-spin-cw 10s linear infinite;
  animation-delay: -3.3s;
}

/* 卫星样式 */
.satellite {
  opacity: 0.95;
}

.sat-primary {
  fill: var(--loader-primary);
}

.sat-secondary {
  fill: var(--loader-orbit-inner);
}

.sat-accent {
  fill: var(--loader-core-bright);
}

/* 卫星尾迹：渐隐 */
.sat-trail {
  fill: var(--loader-primary);
}

.sat-trail.st1 {
  opacity: 0.4;
}

.sat-trail.st2 {
  opacity: 0.18;
}

.sat-trail.st3 {
  opacity: 0.06;
}


/* ===== 核心辐射光芒：极细的光线从中心向外延伸 ===== */
.ray-group {
  transform-origin: 50px 50px;
  animation: ray-rotate 12s linear infinite;
}

.core-ray {
  stroke: var(--loader-primary);
  stroke-width: 0.4;
  stroke-linecap: round;
  opacity: 0;
  animation: ray-breathe 3s ease-in-out infinite;
}

/* 四道光芒依次闪烁，像灵感火花迸射 */
.core-ray.ray1 {
  animation-delay: 0s;
}

.core-ray.ray2 {
  animation-delay: 0.75s;
}

.core-ray.ray3 {
  animation-delay: 1.5s;
}

.core-ray.ray4 {
  animation-delay: 2.25s;
}

/* 光芒缓慢旋转 */
@keyframes ray-rotate {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

/* 光芒呼吸：用dasharray制造从中心向外延伸的效果 */
@keyframes ray-breathe {

  0%,
  100% {
    opacity: 0;
    stroke-dasharray: 0 32;
    stroke-dashoffset: 0;
  }

  50% {
    opacity: 0.3;
    stroke-dasharray: 16 16;
    stroke-dashoffset: -8;
  }
}


/* ===== 第6层：核心四角星（灵感之心） ===== */
.core-group {
  transform-origin: 50px 50px;
  animation: core-breathe 6s ease-in-out infinite;
}

.core-star {
  fill: var(--loader-primary);
  opacity: 0.9;
}

/* 中心高亮 */
.core-center {
  fill: var(--spark-text-inverse);
  opacity: 0.9;
}

/* 外层光晕：与核心呼吸联动但更慢更柔 */
.core-halo {
  fill: var(--loader-glow);
  opacity: 0;
  animation: halo-breathe 3s ease-in-out infinite;
}

/* 核心呼吸：缓慢缩放 + 匀速旋转，一呼一吸暗示"正在思考" */
@keyframes core-breathe {
  0% {
    transform: scale(0.9) rotate(0deg);
    opacity: 0.8;
  }

  50% {
    transform: scale(1.08) rotate(180deg);
    opacity: 1;
  }

  100% {
    transform: scale(0.9) rotate(360deg);
    opacity: 0.8;
  }
}

/* 光晕呼吸：柔和扩缩 */
@keyframes halo-breathe {

  0%,
  100% {
    opacity: 0;
    r: 8;
  }

  50% {
    opacity: 0.3;
    r: 16;
  }
}



</style>
