/**
 * useLoginFx - 登录页交互特效 Composable
 * 
 * 设计理念：
 * - 专业高级的光芒轨迹效果，替代玩具化的 emoji
 * - 点击时产生能量波纹扩散
 * - 优雅的鼠标光晕指示器
 * - 完全接入主题色系统
 */

import { ref, computed, watch } from 'vue';
import { useThemeStore } from '@/components/stores/themeStore';

export function useLoginFx() {
    // ========== 响应式状态 ==========
    const fxCanvas = ref(null);
    const themeStore = useThemeStore();
    
    const isDark = computed(() => 
        themeStore.themeMode === 'dark' || 
        (themeStore.themeMode === 'system' && themeStore.prefersDark)
    );

    // ========== 内部状态 ==========
    let fxCtx = null;
    let fxW = 0;
    let fxH = 0;
    let fxRafId = null;
    let fxMouseX = -9999;
    let fxMouseY = -9999;
    let mouseVx = 0;
    let mouseVy = 0;
    let sprayEnergy = 0;

    const trail = [];         // 光芒轨迹粒子
    const ripples = [];       // 点击波纹
    const sparkTrail = [];    // 鼠标拖尾火花
    const MAX_TRAIL = 100;
    const MAX_RIPPLES = 8;
    const MAX_SPARKS = 50;

    // ========== 主题色获取 ==========
    function getThemeColors() {
        const style = getComputedStyle(document.body);
        const primary = style.getPropertyValue('--spark-primary').trim() || '#7aa2f7';
        const accent = style.getPropertyValue('--spark-accent').trim() || '#bd93f9';
        
        return { primary, accent, isDark: isDark.value };
    }

    function hexToRgb(hex) {
        const h = hex.replace('#', '');
        const bigint = parseInt(h, 16);
        return {
            r: (bigint >> 16) & 255,
            g: (bigint >> 8) & 255,
            b: bigint & 255
        };
    }

    // ========== 工具函数 ==========
    function rand(min, max) {
        return Math.random() * (max - min) + min;
    }

    function pick(arr) {
        return arr[Math.floor(Math.random() * arr.length)];
    }

    // ========== 光芒粒子生成 ==========
    function spawnLightParticles(cx, cy, vx, vy, n) {
        const colors = getThemeColors();
        const primaryRgb = hexToRgb(colors.primary);
        const accentRgb = hexToRgb(colors.accent);
        
        const dir = Math.atan2(vy, vx);
        const speed = Math.hypot(vx, vy);
        
        for (let i = 0; i < n; i++) {
            const ang = dir + (Math.random() - 0.5) * 2.5;
            const s = 0.3 + Math.random() * (0.8 + Math.min(3, speed * 0.03));
            const spread = 2 + Math.random() * 12;
            const ox = Math.cos(ang) * spread + (Math.random() - 0.5) * 6;
            const oy = Math.sin(ang) * spread + (Math.random() - 0.5) * 6;
            
            // 选择颜色 - 主色为主，偶尔混入强调色
            const useAccent = Math.random() < 0.2;
            const rgb = useAccent ? accentRgb : primaryRgb;
            
            // 粒子形态：圆形光点或细长光线
            const isLine = Math.random() < 0.3;
            
            trail.push({
                x: cx + ox,
                y: cy + oy,
                vx: Math.cos(ang) * s + (Math.random() - 0.5) * 0.3,
                vy: Math.sin(ang) * s + (Math.random() - 0.5) * 0.3,
                alpha: 0,
                alphaT: colors.isDark ? 0.8 : 0.5,
                size: isLine ? rand(8, 20) : rand(2, 6),
                life: 40 + Math.floor(Math.random() * 30),
                rot: ang,
                omega: (Math.random() - 0.5) * 0.1,
                isLine,
                color: rgb
            });
        }
        
        if (trail.length > MAX_TRAIL) trail.splice(0, trail.length - MAX_TRAIL);
    }

    function spawnRadialParticles(cx, cy, n) {
        const colors = getThemeColors();
        const primaryRgb = hexToRgb(colors.primary);
        const accentRgb = hexToRgb(colors.accent);
        
        for (let i = 0; i < n; i++) {
            const ang = Math.random() * Math.PI * 2;
            const s = 0.3 + Math.random() * 0.6;
            const ox = (Math.random() - 0.5) * 10;
            const oy = (Math.random() - 0.5) * 10;
            
            const useAccent = Math.random() < 0.15;
            const rgb = useAccent ? accentRgb : primaryRgb;
            const isLine = Math.random() < 0.25;
            
            trail.push({
                x: cx + ox,
                y: cy + oy,
                vx: Math.cos(ang) * s,
                vy: Math.sin(ang) * s,
                alpha: 0,
                alphaT: colors.isDark ? 0.7 : 0.4,
                size: isLine ? rand(6, 15) : rand(1.5, 4),
                life: 35 + Math.floor(Math.random() * 25),
                rot: ang,
                omega: (Math.random() - 0.5) * 0.08,
                isLine,
                color: rgb
            });
        }
        
        if (trail.length > MAX_TRAIL) trail.splice(0, trail.length - MAX_TRAIL);
    }

    // ========== 波纹效果 ==========
    function spawnRipple(x, y) {
        const colors = getThemeColors();
        const rgb = hexToRgb(colors.primary);
        
        ripples.push({
            x,
            y,
            radius: 0,
            maxRadius: 80 + Math.random() * 40,
            alpha: colors.isDark ? 0.6 : 0.4,
            lineWidth: 2,
            color: rgb,
            speed: 3 + Math.random() * 2
        });
        
        // 额外添加一圈延迟波纹
        setTimeout(() => {
            if (ripples.length < MAX_RIPPLES) {
                ripples.push({
                    x,
                    y,
                    radius: 0,
                    maxRadius: 60 + Math.random() * 30,
                    alpha: colors.isDark ? 0.4 : 0.25,
                    lineWidth: 1.5,
                    color: rgb,
                    speed: 2.5 + Math.random() * 1.5
                });
            }
        }, 100);
        
        if (ripples.length > MAX_RIPPLES) ripples.splice(0, ripples.length - MAX_RIPPLES);
    }

    // ========== 鼠标拖尾火花 ==========
    function spawnSpark(x, y, vx, vy) {
        const colors = getThemeColors();
        const rgb = hexToRgb(colors.primary);
        
        sparkTrail.push({
            x,
            y,
            vx: vx * 0.1 + (Math.random() - 0.5) * 0.5,
            vy: vy * 0.1 + (Math.random() - 0.5) * 0.5,
            size: rand(1, 3),
            alpha: colors.isDark ? 0.8 : 0.5,
            life: 20 + Math.random() * 15,
            color: rgb
        });
        
        if (sparkTrail.length > MAX_SPARKS) sparkTrail.splice(0, sparkTrail.length - MAX_SPARKS);
    }

    // ========== 主绘制循环 ==========
    function drawFx() {
        fxCtx.clearRect(0, 0, fxW, fxH);
        const colors = getThemeColors();
        const primaryRgb = hexToRgb(colors.primary);

        // 发射粒子
        const emitCapPerFrame = 5;
        const emitCount = Math.min(emitCapPerFrame, Math.floor(sprayEnergy));
        if (emitCount > 0 && fxMouseX > -999 && fxMouseY > -999) {
            const spd = Math.hypot(mouseVx, mouseVy);
            if (spd < 0.3) {
                spawnRadialParticles(fxMouseX, fxMouseY, emitCount);
            } else {
                spawnLightParticles(fxMouseX, fxMouseY, mouseVx, mouseVy, emitCount);
                // 高速移动时添加火花
                if (spd > 2 && Math.random() < 0.4) {
                    spawnSpark(fxMouseX, fxMouseY, mouseVx, mouseVy);
                }
            }
            sprayEnergy -= emitCount;
        }

        if (fxMouseX > -999 && fxMouseY > -999) {
            sprayEnergy = Math.min(60, sprayEnergy + 0.2);
        }

        // 更新并绘制光芒轨迹
        for (let i = trail.length - 1; i >= 0; i--) {
            const t = trail[i];
            t.life -= 1;
            t.alpha += (t.alphaT - t.alpha) * 0.2;
            t.alphaT *= 0.985;
            t.size *= 0.995;
            t.vx *= 0.98;
            t.vy *= 0.98;
            t.x += t.vx;
            t.y += t.vy;
            t.rot += t.omega;

            if (t.life <= 0 || t.alpha < 0.02 || t.size < 0.5) {
                trail.splice(i, 1);
                continue;
            }

            fxCtx.save();
            fxCtx.translate(t.x, t.y);
            fxCtx.rotate(t.rot);
            fxCtx.globalAlpha = t.alpha;

            if (t.isLine) {
                // 细长光线
                const grad = fxCtx.createLinearGradient(-t.size / 2, 0, t.size / 2, 0);
                grad.addColorStop(0, 'transparent');
                grad.addColorStop(0.5, `rgba(${t.color.r}, ${t.color.g}, ${t.color.b}, 1)`);
                grad.addColorStop(1, 'transparent');
                fxCtx.strokeStyle = grad;
                fxCtx.lineWidth = 1.5;
                fxCtx.beginPath();
                fxCtx.moveTo(-t.size / 2, 0);
                fxCtx.lineTo(t.size / 2, 0);
                fxCtx.stroke();
            } else {
                // 圆形光点带光晕
                const glow = fxCtx.createRadialGradient(0, 0, 0, 0, 0, t.size * 2);
                glow.addColorStop(0, `rgba(${t.color.r}, ${t.color.g}, ${t.color.b}, 0.8)`);
                glow.addColorStop(0.4, `rgba(${t.color.r}, ${t.color.g}, ${t.color.b}, 0.3)`);
                glow.addColorStop(1, 'transparent');
                fxCtx.fillStyle = glow;
                fxCtx.beginPath();
                fxCtx.arc(0, 0, t.size * 2, 0, Math.PI * 2);
                fxCtx.fill();

                // 核心亮点
                fxCtx.fillStyle = colors.isDark 
                    ? `rgba(255, 255, 255, ${t.alpha})` 
                    : `rgba(${t.color.r}, ${t.color.g}, ${t.color.b}, ${t.alpha})`;
                fxCtx.beginPath();
                fxCtx.arc(0, 0, t.size * 0.5, 0, Math.PI * 2);
                fxCtx.fill();
            }

            fxCtx.restore();
        }

        // 更新并绘制火花拖尾
        for (let i = sparkTrail.length - 1; i >= 0; i--) {
            const s = sparkTrail[i];
            s.life -= 1;
            s.alpha *= 0.92;
            s.x += s.vx;
            s.y += s.vy;
            s.vy += 0.02; // 轻微重力

            if (s.life <= 0 || s.alpha < 0.02) {
                sparkTrail.splice(i, 1);
                continue;
            }

            fxCtx.save();
            fxCtx.globalAlpha = s.alpha;
            fxCtx.fillStyle = `rgba(${s.color.r}, ${s.color.g}, ${s.color.b}, 1)`;
            fxCtx.beginPath();
            fxCtx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
            fxCtx.fill();
            fxCtx.restore();
        }

        // 更新并绘制波纹
        for (let i = ripples.length - 1; i >= 0; i--) {
            const r = ripples[i];
            r.radius += r.speed;
            r.alpha *= 0.96;
            r.lineWidth *= 0.98;

            if (r.radius >= r.maxRadius || r.alpha < 0.02) {
                ripples.splice(i, 1);
                continue;
            }

            fxCtx.save();
            fxCtx.globalAlpha = r.alpha;
            fxCtx.strokeStyle = `rgba(${r.color.r}, ${r.color.g}, ${r.color.b}, 1)`;
            fxCtx.lineWidth = r.lineWidth;
            fxCtx.beginPath();
            fxCtx.arc(r.x, r.y, r.radius, 0, Math.PI * 2);
            fxCtx.stroke();
            fxCtx.restore();
        }

        // 绘制鼠标光晕指示器（替代 emoji 光标）
        if (fxMouseX > -999 && fxMouseY > -999) {
            fxCtx.save();
            
            // 外圈柔和光晕
            const outerGlow = fxCtx.createRadialGradient(
                fxMouseX, fxMouseY, 0,
                fxMouseX, fxMouseY, 24
            );
            outerGlow.addColorStop(0, `rgba(${primaryRgb.r}, ${primaryRgb.g}, ${primaryRgb.b}, ${colors.isDark ? 0.3 : 0.2})`);
            outerGlow.addColorStop(0.5, `rgba(${primaryRgb.r}, ${primaryRgb.g}, ${primaryRgb.b}, ${colors.isDark ? 0.15 : 0.1})`);
            outerGlow.addColorStop(1, 'transparent');
            fxCtx.fillStyle = outerGlow;
            fxCtx.beginPath();
            fxCtx.arc(fxMouseX, fxMouseY, 24, 0, Math.PI * 2);
            fxCtx.fill();

            // 内圈亮点
            const innerGlow = fxCtx.createRadialGradient(
                fxMouseX, fxMouseY, 0,
                fxMouseX, fxMouseY, 6
            );
            innerGlow.addColorStop(0, colors.isDark ? 'rgba(255, 255, 255, 0.9)' : `rgba(${primaryRgb.r}, ${primaryRgb.g}, ${primaryRgb.b}, 0.8)`);
            innerGlow.addColorStop(0.5, `rgba(${primaryRgb.r}, ${primaryRgb.g}, ${primaryRgb.b}, 0.4)`);
            innerGlow.addColorStop(1, 'transparent');
            fxCtx.fillStyle = innerGlow;
            fxCtx.beginPath();
            fxCtx.arc(fxMouseX, fxMouseY, 6, 0, Math.PI * 2);
            fxCtx.fill();

            fxCtx.restore();
        }

        fxRafId = requestAnimationFrame(drawFx);
    }

    // ========== resize 处理 ==========
    function resizeFx() {
        const c = fxCanvas.value;
        if (!c) return;
        const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
        fxW = c.clientWidth;
        fxH = c.clientHeight;
        c.width = Math.floor(fxW * dpr);
        c.height = Math.floor(fxH * dpr);
        fxCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    // ========== 事件处理 ==========
    function handleMouseMove(e, bgCanvasRect) {
        const fxRect = fxCanvas.value.getBoundingClientRect();
        const x = e.clientX - bgCanvasRect.left;
        const y = e.clientY - bgCanvasRect.top;
        mouseVx = x - fxMouseX;
        mouseVy = y - fxMouseY;
        fxMouseX = e.clientX - fxRect.left;
        fxMouseY = e.clientY - fxRect.top;
        const spd = Math.hypot(mouseVx, mouseVy);
        sprayEnergy = Math.min(80, sprayEnergy + Math.min(6, 1.2 + spd * 0.06));
        return { x, y, vx: mouseVx, vy: mouseVy };
    }

    function handleClick(e, cardElement) {
        if (e.target.closest('.card') || (cardElement && cardElement.contains(e.target))) return;
        const fxRect = fxCanvas.value.getBoundingClientRect();
        const x = e.clientX - fxRect.left;
        const y = e.clientY - fxRect.top;
        spawnRipple(x, y);
        // 点击时额外喷发一些粒子
        spawnRadialParticles(x, y, 8);
    }

    function handleLeave() {
        fxMouseX = -9999;
        fxMouseY = -9999;
    }

    // ========== 生命周期 ==========
    function init() {
        const c = fxCanvas.value;
        if (!c) return;
        fxCtx = c.getContext('2d');
        resizeFx();
        window.addEventListener('resize', resizeFx);
        fxRafId = requestAnimationFrame(drawFx);
    }

    function destroy() {
        if (fxRafId) cancelAnimationFrame(fxRafId);
        window.removeEventListener('resize', resizeFx);
    }

    // ========== 导出 ==========
    return {
        fxCanvas,
        init,
        destroy,
        handleMouseMove,
        handleClick,
        handleLeave,
    };
}