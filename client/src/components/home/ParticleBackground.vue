<template>
  <canvas ref="canvasRef" id="sparkCanvas"></canvas>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';

const canvasRef = ref(null);
let particleReqId = null;
let resizeHandler = null; // 保存引用以便清理

// --- Particle System (Original Star Effect + 3D Neural Sphere) ---
// 背景粒子类 - 使用虚拟尺寸而不是canvas尺寸
class Particle {
  constructor(vWidth, vHeight) {
    this.vWidth = vWidth;
    this.vHeight = vHeight;
    this.reset();
    this.y = Math.random() * vHeight;
    this.x = Math.random() * vWidth;
  }
  reset() {
    this.x = Math.random() * this.vWidth;
    this.y = this.vHeight + Math.random() * 100;
    this.speed = Math.random() * 2 + 0.5;
    this.size = Math.random() * 2.5;
    this.color = Math.random() > 0.5 ? '#ffaa40' : '#40c9ff';
    this.opacity = Math.random() * 0.5 + 0.1;
    this.wobble = Math.random() * Math.PI * 2;
    this.wobbleSpeed = Math.random() * 0.05;
  }
  updateBounds(vWidth, vHeight) {
    this.vWidth = vWidth;
    this.vHeight = vHeight;
  }
  update() {
    this.y -= this.speed;
    this.wobble += this.wobbleSpeed;
    this.x += Math.sin(this.wobble) * 0.5;
    if (this.y < this.vHeight * 0.8) this.opacity -= 0.005;
    if (this.y < -50 || this.opacity <= 0) this.reset();
  }
  draw(ctx, scale) {
    ctx.fillStyle = this.color;
    ctx.globalAlpha = this.opacity;
    ctx.beginPath();
    ctx.arc(this.x * scale, this.y * scale, this.size * scale, 0, Math.PI * 2);
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
    // New: Orbit properties for some particles
    this.orbiting = Math.random() > 0.7;
    this.orbitSpeed = (Math.random() - 0.5) * 0.02;
    this.orbitPhase = Math.random() * Math.PI * 2;
    // New: Twinkle properties
    this.twinkleSpeed = 0.01 + Math.random() * 0.03;
    this.twinklePhase = Math.random() * Math.PI * 2;
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
  rotateZ(angle) {
    const cos = Math.cos(angle); const sin = Math.sin(angle);
    const x = this.x * cos - this.y * sin;
    const y = this.x * sin + this.y * cos;
    this.x = x; this.y = y;
  }
}

function initParticles() {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  
  // 保存虚拟尺寸（用于粒子逻辑计算）和渲染缩放因子
  let virtualWidth = window.innerWidth;
  let virtualHeight = window.innerHeight;
  let renderScale = 1;
  
  function resize() {
    virtualWidth = window.innerWidth;
    virtualHeight = window.innerHeight;
    
    // 限制canvas渲染分辨率以提高性能
    // 超大屏幕上，渲染像素太多会导致卡顿（特别是使用lighter混合模式时）
    const maxPixels = 2073600; // 1920 * 1080
    const currentPixels = virtualWidth * virtualHeight;
    
    if (currentPixels > maxPixels) {
      renderScale = Math.sqrt(maxPixels / currentPixels);
    } else {
      renderScale = 1;
    }
    
    canvas.width = Math.floor(virtualWidth * renderScale);
    canvas.height = Math.floor(virtualHeight * renderScale);
  }
  resizeHandler = resize;
  window.addEventListener('resize', resize);
  resize();

  // 1. Background Float Particles (Subtle) - 使用虚拟尺寸
  const bgParticles = Array.from({ length: 120 }, () => new Particle(virtualWidth, virtualHeight));

  // 2. Heartbeat Star Particles (Dense - Increased count)
  const starParticles = Array.from({ length: 1500 }, () => new StarParticle());
  
  // resize时更新背景粒子的边界
  const originalResize = resize;
  resize = function() {
    originalResize();
    bgParticles.forEach(p => p.updateBounds(virtualWidth, virtualHeight));
  };
  resizeHandler = resize;
  
  function drawLightningRing(ctx, centerX, centerY, time, pulseScale, color, width, chaosMod) {
    const numPoints = 360;
    const baseRadius = 350;
    
    // Morph Factor: How much the shape is a "star" vs a "circle"
    const morphFactor = Math.min(1, Math.max(0, (pulseScale - 1) / 0.25));
    
    ctx.beginPath();
    const maxBandWidth = 75 * chaosMod;
    
    for (let i = 0; i <= numPoints; i++) {
        const angle = (i / numPoints) * Math.PI * 2;
        
        // 0. Star Shape Component
        const starWave = Math.pow(Math.abs(Math.cos(angle * 2)), 0.4); 
        const starOffset = starWave * 100 * morphFactor; 
        
        // 1. Random Depth Constraint
        const t = time * 0.0005;
        const depthNoise = Math.sin(angle * 7.23 + t) * Math.cos(angle * 3.14 - t * 0.7) * 0.5 + 0.5;
        const baseChaosFactor = (1 + (1 - morphFactor) * 0.5) * chaosMod;
        const randomDepth = Math.random() * maxBandWidth * depthNoise * baseChaosFactor;
        
        // 2. Chaotic Lightning Component
        const phi = 1.6180339887;
        const sqrt2 = 1.41421356;
        const sqrt3 = 1.73205080;
        
        const wave1 = Math.sin(angle * 17 * phi + t * 0.8) * 12 * baseChaosFactor;
        const wave2 = Math.cos(angle * 23 * sqrt2 - t * 1.2) * 10 * baseChaosFactor;
        const wave3 = Math.sin(angle * 31 * sqrt3 + t * 0.6) * 6 * baseChaosFactor;
        const wave4 = Math.cos(angle * 11 + Math.sin(t * 0.15) * 5) * 7 * baseChaosFactor;
        
        const electric = wave1 + wave2 + wave3 + wave4;
                         
        // Random Jitter
        const flash = Math.sin(time * 0.01) > 0.85 ? 1.5 : 1;
        const jitter = (Math.random() - 0.5) * 18 * flash * baseChaosFactor; 
        
        // Occasional large spikes
        const spike = Math.random() > (0.975 / chaosMod) ? (Math.random() * 45 * chaosMod) : 0;

        // 3. Combine
        const r = (baseRadius * pulseScale) + starOffset - randomDepth + electric + jitter + spike;

        const x = centerX + Math.cos(angle) * r;
        const y = centerY + Math.sin(angle) * r;
        
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.closePath();
    
    // Glowing Stroke
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.lineJoin = 'round';
    ctx.stroke();
  }
  

  
  // --- Draw Sparkle Bursts ---
  function drawSparkleBursts(ctx, centerX, centerY, time, scale) {
    const numSparkles = 12;
    for (let i = 0; i < numSparkles; i++) {
      const angle = (i / numSparkles) * Math.PI * 2 + time * 0.0003;
      const distance = 280 * scale + Math.sin(time * 0.005 + i) * 30;
      const x = centerX + Math.cos(angle) * distance;
      const y = centerY + Math.sin(angle) * distance;
      
      const sparkleAlpha = 0.3 + Math.sin(time * 0.008 + i * 0.5) * 0.3;
      const sparkleSize = 2 + Math.sin(time * 0.01 + i) * 1.5;
      
      if (sparkleAlpha > 0.1) {
        // Draw cross sparkle
        ctx.strokeStyle = `rgba(255, 220, 150, ${sparkleAlpha})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x - sparkleSize * 2, y);
        ctx.lineTo(x + sparkleSize * 2, y);
        ctx.moveTo(x, y - sparkleSize * 2);
        ctx.lineTo(x, y + sparkleSize * 2);
        ctx.stroke();
        
        // Center glow
        ctx.beginPath();
        ctx.arc(x, y, sparkleSize * 0.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 255, 255, ${sparkleAlpha * 0.8})`;
        ctx.fill();
      }
    }
  }

  function drawStar(time) {
    if (window.scrollY > window.innerHeight) return;

    // 使用渲染后的canvas尺寸计算中心点
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2 - 50 * renderScale;
    
    // Heartbeat Pulse Logic
    const pulseRaw = Math.pow(Math.sin(time * 0.003), 40);
    const pulseScale = 1 + pulseRaw * 0.25; 
    const explosionShake = pulseRaw * 15; // Magnitude of the shake effect

    // Global Rotation - Dynamic 3D
    const rotX = 0.001 + Math.sin(time * 0.0005) * 0.002;
    const rotY = 0.003;
    const rotZ = Math.cos(time * 0.0003) * 0.001;
    
    // Additive Blending for Glow
    ctx.globalCompositeOperation = 'lighter';
    
    // Draw Lightning - Gold Main
    drawLightningRing(ctx, centerX, centerY, time, pulseScale, `rgba(255, 200, 100, 0.6)`, 2.5, 1.0);
    
    // Draw Lightning - Orange Hints (Random, chaotic)
    if (Math.random() > 0.2) {
        drawLightningRing(ctx, centerX, centerY, time + 500, pulseScale, `rgba(255, 100, 50, 0.4)`, 1.5, 1.2);
    }

    starParticles.forEach(p => {
      // Rotate 3D
      p.rotateY(rotY);
      p.rotateX(rotX);
      p.rotateZ(rotZ);
      
      // Additional orbit for some particles
      if (p.orbiting) {
        p.orbitPhase += p.orbitSpeed;
      }

      // Pulse with Explosion/Shake Effect
      // Add a random jitter vector based on the pulse strength to simulate explosion turbulence
      const jitterX = (Math.random() - 0.5) * explosionShake;
      const jitterY = (Math.random() - 0.5) * explosionShake;
      const jitterZ = (Math.random() - 0.5) * explosionShake;

      // Apply pulse scale AND jitter
      const currentX = p.x * pulseScale + jitterX;
      const currentY = p.y * pulseScale + jitterY;
      const currentZ = p.z * pulseScale + jitterZ;

      // 3D Projection - Enhanced FOV
      const fov = 350;
      const zOffset = 400;
      const denominator = fov + currentZ + zOffset;
      
      // 修复直线轨迹问题：跳过无效的投影
      // 当denominator接近0时，scale趋向无穷大，粒子会被投影到极端位置
      if (denominator <= 50) return;
      
      const scale3d = fov / denominator;
      
      // 应用渲染缩放因子
      const x2d = currentX * scale3d * renderScale + centerX;
      const y2d = currentY * scale3d * renderScale + centerY;
      
      // 边界检查：跳过屏幕外的粒子（避免直线轨迹问题）
      if (!isFinite(x2d) || !isFinite(y2d) ||
          x2d < -50 || x2d > canvas.width + 50 ||
          y2d < -50 || y2d > canvas.height + 50) {
        return;
      }
      
      // Twinkle effect
      p.twinklePhase += p.twinkleSpeed;
      const twinkle = 0.5 + Math.sin(p.twinklePhase) * 0.5;
      
      // Color Logic with enhanced depth
      const baseAlpha = (currentZ + 200) / 400;
      const alpha = baseAlpha * twinkle;
      if (alpha > 0) {
        ctx.beginPath();
        // Particles also expand slightly more during explosion - 应用渲染缩放
        const size = p.size * scale3d * renderScale * (pulseScale * 1.5 + pulseRaw * 0.5);
        ctx.arc(x2d, y2d, size, 0, Math.PI * 2);
        
        // Enhanced Dynamic Colors with more variety
        if (p.colorType > 0.95) {
          // Bright white sparkle
          ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
        } else if (p.colorType > 0.85) {
          // Blue-White hotspots
          ctx.fillStyle = `rgba(180, 220, 255, ${alpha})`;
        } else if (p.colorType > 0.7) {
          // Cyan accent
          ctx.fillStyle = `rgba(100, 220, 230, ${alpha * 0.9})`;
        } else if (p.colorType > 0.5) {
          // Gold
          ctx.fillStyle = `rgba(255, 200, 100, ${alpha})`;
        } else if (p.colorType > 0.3) {
          // Orange
          ctx.fillStyle = `rgba(255, 140, 50, ${alpha * 0.9})`;
        } else {
          // Deep red-orange core
          ctx.fillStyle = `rgba(255, 80, 30, ${alpha * 0.8})`;
        }
        
        ctx.fill();
        
        // Add glow for brightest particles
        if (p.colorType > 0.9 && size > 1.5 * renderScale) {
          ctx.beginPath();
          ctx.arc(x2d, y2d, size * 2, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(255, 255, 255, ${alpha * 0.15})`;
          ctx.fill();
        }
      }
    });
    
    // Draw Sparkle Bursts (on top)
    drawSparkleBursts(ctx, centerX, centerY, time, pulseScale);

    ctx.globalCompositeOperation = 'source-over'; // Reset blend mode
  }

  function animate(time) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw Background - 应用渲染缩放
    bgParticles.forEach(p => p.update());
    bgParticles.forEach(p => p.draw(ctx, renderScale));

    // Draw Heartbeat Star
    drawStar(time);

    particleReqId = requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
}

onMounted(() => {
  initParticles();
});

onUnmounted(() => {
  if (particleReqId) cancelAnimationFrame(particleReqId);
  if (resizeHandler) window.removeEventListener('resize', resizeHandler);
});
</script>

<style scoped>
#sparkCanvas {
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  z-index: 0;
  pointer-events: none;
}
</style>