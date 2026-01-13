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
    let dpr = 1;
    let fxRafId = null;
    let fxMouseX = -9999;
    let fxMouseY = -9999;
    let mouseVx = 0;
    let mouseVy = 0;
    let sprayEnergy = 0;

    const trail = [];         // 光芒轨迹粒子
    const fallingStars = [];  // 点击爆炸后洒落的星星
    const sparkTrail = [];    // 鼠标拖尾火花
    const MAX_TRAIL = 80;     // 降低粒子上限
    const MAX_FALLING = 40;   // 降低洒落星星上限
    const MAX_SPARKS = 30;

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
            const ang = dir + (Math.random() - 0.5) * 3.5; // 更广的角度
            const s = 0.3 + Math.random() * (0.8 + Math.min(3, speed * 0.04));
            // 大幅扩大初始分布范围，增加洒落感
            const spread = 5 + Math.random() * 25;
            const ox = Math.cos(ang) * spread + (Math.random() - 0.5) * 15;
            const oy = Math.sin(ang) * spread + (Math.random() - 0.5) * 15;
            
            const useAccent = Math.random() < 0.2;
            const rgb = useAccent ? accentRgb : primaryRgb;
            
            const isLine = Math.random() < 0.3;
            
            trail.push({
                x: cx + ox,
                y: cy + oy,
                vx: Math.cos(ang) * s + (Math.random() - 0.5) * 0.5,
                vy: Math.sin(ang) * s + (Math.random() - 0.5) * 0.5,
                alpha: 0,
                alphaT: colors.isDark ? 0.8 : 0.5,
                size: isLine ? rand(8, 24) : rand(2, 7),
                // 增加生命周期
                life: 60 + Math.floor(Math.random() * 40),
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

    // ========== 星星爆炸洒落效果 ==========
    function spawnStarExplosion(x, y) {
        const colors = getThemeColors();
        const primaryRgb = hexToRgb(colors.primary);
        const accentRgb = hexToRgb(colors.accent);
        
        // 减少星星数量以优化性能
        const starCount = 15 + Math.floor(Math.random() * 10);
        for (let i = 0; i < starCount; i++) {
            const angle = Math.random() * Math.PI * 2;
            // 增加速度范围，让爆炸范围更大
            const speed = 4 + Math.random() * 10;
            const useAccent = Math.random() < 0.35; // 稍微增加强调色比例
            const rgb = useAccent ? accentRgb : primaryRgb;
            
            const points = Math.random() < 0.7 ? 4 : (Math.random() < 0.5 ? 5 : 6);
            
            fallingStars.push({
                x,
                y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed - 3, // 初始更强的向上冲力
                size: rand(3, 10), // 略微增大星星
                alpha: colors.isDark ? 0.95 : 0.75,
                life: 100 + Math.random() * 80, // 延长生命周期
                rotation: Math.random() * Math.PI * 2,
                omega: (Math.random() - 0.5) * 0.2,
                color: rgb,
                points,
                twinklePhase: Math.random() * Math.PI * 2
            });
        }
        
        // 动态调整上限以适应瞬间爆发
        if (fallingStars.length > MAX_FALLING * 1.5) {
            fallingStars.splice(0, fallingStars.length - MAX_FALLING * 1.5);
        }
    }
    
    // 绘制星星形状
    function drawStar(ctx, cx, cy, outerR, innerR, points) {
        ctx.beginPath();
        for (let i = 0; i < points * 2; i++) {
            const r = i % 2 === 0 ? outerR : innerR;
            const angle = (i * Math.PI) / points - Math.PI / 2;
            const x = cx + Math.cos(angle) * r;
            const y = cy + Math.sin(angle) * r;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.closePath();
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

            // 优化：避免 save/restore
            fxCtx.globalAlpha = t.alpha;

            if (t.isLine) {
                fxCtx.translate(t.x, t.y);
                fxCtx.rotate(t.rot);
                fxCtx.strokeStyle = `rgba(${t.color.r}, ${t.color.g}, ${t.color.b}, ${t.alpha})`;
                fxCtx.lineWidth = 1.5;
                fxCtx.beginPath();
                fxCtx.moveTo(-t.size / 2, 0);
                fxCtx.lineTo(t.size / 2, 0);
                fxCtx.stroke();
                fxCtx.setTransform(dpr, 0, 0, dpr, 0, 0); // 重置变换
            } else {
                // 圆形不需要旋转，直接绘制
                // 外层光晕
                fxCtx.fillStyle = `rgba(${t.color.r}, ${t.color.g}, ${t.color.b}, 0.2)`;
                fxCtx.beginPath();
                fxCtx.arc(t.x, t.y, t.size * 2, 0, Math.PI * 2);
                fxCtx.fill();

                // 核心亮点
                fxCtx.fillStyle = colors.isDark
                    ? `rgba(255, 255, 255, ${t.alpha})`
                    : `rgba(${t.color.r}, ${t.color.g}, ${t.color.b}, ${t.alpha})`;
                fxCtx.beginPath();
                fxCtx.arc(t.x, t.y, t.size * 0.5, 0, Math.PI * 2);
                fxCtx.fill();
            }
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

            // 移除 save/restore，直接设置状态
            fxCtx.globalAlpha = s.alpha;
            fxCtx.fillStyle = `rgba(${s.color.r}, ${s.color.g}, ${s.color.b}, 1)`;
            fxCtx.beginPath();
            fxCtx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
            fxCtx.fill();
        }
        fxCtx.globalAlpha = 1.0; // 重置透明度

        // 更新并绘制洒落的星星
        for (let i = fallingStars.length - 1; i >= 0; i--) {
            const star = fallingStars[i];
            star.life -= 1;
            star.alpha *= 0.985;
            star.x += star.vx;
            star.y += star.vy;
            star.vy += 0.12; // 重力加速度
            star.vx *= 0.99;  // 空气阻力
            star.rotation += star.omega;
            star.twinklePhase += 0.15;

            if (star.life <= 0 || star.alpha < 0.02 || star.y > fxH + 50) {
                fallingStars.splice(i, 1);
                continue;
            }

            // 闪烁效果
            // 闪烁效果
            const twinkle = 0.7 + Math.sin(star.twinklePhase) * 0.3;
            const currentAlpha = star.alpha * twinkle;

            // 优化：避免 save/restore
            fxCtx.translate(star.x, star.y);
            fxCtx.rotate(star.rotation);
            fxCtx.globalAlpha = currentAlpha;
            
            // 绘制带光晕的星星
            const glowSize = star.size * 2;
            fxCtx.fillStyle = `rgba(${star.color.r}, ${star.color.g}, ${star.color.b}, 0.3)`;
            fxCtx.beginPath();
            fxCtx.arc(0, 0, glowSize, 0, Math.PI * 2);
            fxCtx.fill();
            
            // 绘制星星本体
            fxCtx.fillStyle = colors.isDark
                ? `rgba(255, 255, 255, ${currentAlpha})`
                : `rgba(${star.color.r}, ${star.color.g}, ${star.color.b}, ${currentAlpha})`;
            drawStar(fxCtx, 0, 0, star.size, star.size * 0.4, star.points);
            fxCtx.fill();
            
            fxCtx.setTransform(dpr, 0, 0, dpr, 0, 0); // 重置变换
        }
        fxCtx.globalAlpha = 1.0; // 重置透明度
        // 绘制鼠标光晕指示器（优化版）
        if (fxMouseX > -999 && fxMouseY > -999) {
            // 合并为一个径向渐变，减少绘制次数
            const glow = fxCtx.createRadialGradient(
                fxMouseX, fxMouseY, 0,
                fxMouseX, fxMouseY, 50
            );
            
            const r = primaryRgb.r;
            const g = primaryRgb.g;
            const b = primaryRgb.b;
            
            // 内核 (0-8px / 50px = 0.16)
            glow.addColorStop(0, colors.isDark ? 'rgba(255, 255, 255, 0.95)' : `rgba(${r}, ${g}, ${b}, 0.9)`);
            glow.addColorStop(0.1, `rgba(${r}, ${g}, ${b}, 0.5)`);
            
            // 中层 (8-20px / 50px = 0.16-0.4)
            glow.addColorStop(0.16, `rgba(${r}, ${g}, ${b}, ${colors.isDark ? 0.35 : 0.25})`);
            glow.addColorStop(0.4, `rgba(${r}, ${g}, ${b}, ${colors.isDark ? 0.15 : 0.1})`);
            
            // 外层
            glow.addColorStop(1, 'transparent');

            fxCtx.fillStyle = glow;
            fxCtx.beginPath();
            fxCtx.arc(fxMouseX, fxMouseY, 50, 0, Math.PI * 2);
            fxCtx.fill();
        }

        fxRafId = requestAnimationFrame(drawFx);
    }

    // ========== resize 处理 ==========
    function resizeFx() {
        const c = fxCanvas.value;
        if (!c) return;
        dpr = Math.min(window.devicePixelRatio || 1, 1.5);
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
        if (e.target.closest('.card') || e.target.closest('.auth-card') || (cardElement && cardElement.contains(e.target))) return;
        const fxRect = fxCanvas.value.getBoundingClientRect();
        const x = e.clientX - fxRect.left;
        const y = e.clientY - fxRect.top;
        // 星星爆炸效果
        spawnStarExplosion(x, y);
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