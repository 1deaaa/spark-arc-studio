/**
 * useLoginFx - 登录页交互特效 Composable
 *
 * 设计理念：
 * - 华丽的预渲染几何图形粒子（高性能）
 * - 多种形状：星星、钻石、六边形、心形、闪电、火花、月牙、螺旋等
 * - 优雅的鼠标光晕指示器
 * - 完全接入主题色系统，浅色模式下增强可见性
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
    
    // 预渲染图形缓存
    let shapeCache = null;
    let cachedColorKey = '';

    const particles = [];     // 华丽的几何粒子
    const MAX_PARTICLES = 80;

    // 图形类型定义
    const SHAPE_TYPES = [
        'star4', 'star5', 'star6', 'star8', // 多角星
        'crescent',                         // 月亮
        'spark', 'kirakira',       // 闪烁/光芒
        'snowflake'                         // 雪花
    ];

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

    // RGB 转 HSL
    function rgbToHsl(r, g, b) {
        r /= 255, g /= 255, b /= 255;
        const max = Math.max(r, g, b), min = Math.min(r, g, b);
        let h, s, l = (max + min) / 2;
        if (max === min) {
            h = s = 0;
        } else {
            const d = max - min;
            s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
            switch (max) {
                case r: h = (g - b) / d + (g < b ? 6 : 0); break;
                case g: h = (b - r) / d + 2; break;
                case b: h = (r - g) / d + 4; break;
            }
            h /= 6;
        }
        return { h: h * 360, s, l };
    }

    // HSL 转 RGB
    function hslToRgb(h, s, l) {
        let r, g, b;
        if (s === 0) {
            r = g = b = l;
        } else {
            const hue2rgb = (p, q, t) => {
                if (t < 0) t += 1;
                if (t > 1) t -= 1;
                if (t < 1/6) return p + (q - p) * 6 * t;
                if (t < 1/2) return q;
                if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
                return p;
            };
            const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
            const p = 2 * l - q;
            r = hue2rgb(p, q, h / 360 + 1/3);
            g = hue2rgb(p, q, h / 360);
            b = hue2rgb(p, q, h / 360 - 1/3);
        }
        return { r: Math.round(r * 255), g: Math.round(g * 255), b: Math.round(b * 255) };
    }
    
    // 获取适应主题的粒子颜色
    function getParticleColor(baseRgb, colors, hueOffset = 0) {
        const hsl = rgbToHsl(baseRgb.r, baseRgb.g, baseRgb.b);
        const h = (hsl.h + hueOffset) % 360; // 应用色相旋转

        if (colors.isDark) {
            // 暗色模式：保持原样，仅旋转色相
            return hslToRgb(h, hsl.s, hsl.l);
        }
        
        // 浅色模式优化：
        // 用户反馈：之前的 90% 饱和度太高导致不像主题色，且单调
        // 调整：降低饱和度下限，放宽亮度范围，还原主题色质感
        return hslToRgb(
            h,
            Math.max(hsl.s, 0.4), // 确保不灰，但不过分艳丽(原0.9)
            Math.min(hsl.l, 0.45) // 略微压暗以在浅色背景保持对比度
        );
    }

    function rand(min, max) {
        return Math.random() * (max - min) + min;
    }

    // ========== 预渲染几何图形 ==========
    function createShapeCache() {
        const colors = getThemeColors();
        const colorKey = `${colors.primary}-${colors.accent}-${colors.isDark}`;
        
        // 如果颜色没变，不需要重新渲染
        if (shapeCache && cachedColorKey === colorKey) return;
        cachedColorKey = colorKey;
        
        // 生成临近色系（Analogous Colors）
        // 基础色 + 向同一方向旋转的2个衍生色 (e.g., +25°, +50°)
        const baseRgb = hexToRgb(colors.primary);
        const colorVariants = [
            getParticleColor(baseRgb, colors, 0),
            getParticleColor(baseRgb, colors, 25),
            getParticleColor(baseRgb, colors, 50)
        ];
        
        // 每种图形预渲染多个尺寸（小、中、大）
        const sizes = [12, 20, 32];
        
        shapeCache = {};
        
        for (const shapeType of SHAPE_TYPES) {
            shapeCache[shapeType] = {};
            for (const size of sizes) {
                shapeCache[shapeType][size] = {};
                for (let ci = 0; ci < colorVariants.length; ci++) {
                    const rgb = colorVariants[ci];
                    const canvas = document.createElement('canvas');
                    const padding = 4;
                    canvas.width = size + padding * 2;
                    canvas.height = size + padding * 2;
                    const ctx = canvas.getContext('2d');
                    
                    ctx.translate(canvas.width / 2, canvas.height / 2);
                    
                    // 增强发光效果
                    ctx.shadowColor = `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 1.0)`;
                    ctx.shadowBlur = 8; // 增加模糊半径
                    
                    // 绘制图形
                    ctx.fillStyle = colors.isDark
                        ? `rgba(255, 255, 255, 0.95)`
                        : `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.95)`;
                    ctx.strokeStyle = `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 1)`;
                    ctx.lineWidth = 1.5;
                    
                    // 双重绘制增强光晕感
                    ctx.globalCompositeOperation = 'source-over';
                    drawShape(ctx, shapeType, size / 2);
                    
                    // 叠加一层高亮核心
                    ctx.shadowBlur = 0;
                    ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
                    ctx.fill();
                    
                    shapeCache[shapeType][size][ci] = canvas;
                }
            }
        }
    }
    
    // 绘制各种形状
    function drawShape(ctx, type, r) {
        ctx.beginPath();
        
        switch (type) {
            case 'star4':
                drawStar(ctx, 4, r, r * 0.4);
                break;
            case 'star5':
                drawStar(ctx, 5, r, r * 0.45);
                break;
            case 'star6':
                drawStar(ctx, 6, r, r * 0.5);
                break;
            case 'star8':
                drawStar(ctx, 8, r, r * 0.4);
                break;
            case 'kirakira':
                // 四角星（内凹菱形）
                ctx.moveTo(0, -r);
                ctx.quadraticCurveTo(0, 0, r, 0);
                ctx.quadraticCurveTo(0, 0, 0, r);
                ctx.quadraticCurveTo(0, 0, -r, 0);
                ctx.quadraticCurveTo(0, 0, 0, -r);
                ctx.closePath();
                break;
            case 'crescent':
                ctx.arc(0, 0, r, 0.3, Math.PI * 2 - 0.3);
                ctx.arc(r * 0.3, 0, r * 0.75, Math.PI * 2 - 0.5, 0.5, true);
                break;
            case 'spark':
                // 四向光芒
                for (let i = 0; i < 4; i++) {
                    const ang = (i / 4) * Math.PI * 2;
                    ctx.moveTo(0, 0);
                    ctx.lineTo(Math.cos(ang) * r, Math.sin(ang) * r);
                }
                ctx.stroke();
                ctx.beginPath();
                ctx.arc(0, 0, r * 0.2, 0, Math.PI * 2);
                break;
            case 'snowflake':
                // 六向雪花
                for (let i = 0; i < 6; i++) {
                    const ang = (i / 6) * Math.PI * 2;
                    ctx.moveTo(0, 0);
                    ctx.lineTo(Math.cos(ang) * r, Math.sin(ang) * r);
                    // 分支
                    const branchLen = r * 0.4;
                    const branchPos = r * 0.6;
                    for (const sign of [-1, 1]) {
                        const bx = Math.cos(ang) * branchPos;
                        const by = Math.sin(ang) * branchPos;
                        const bAng = ang + sign * Math.PI / 4;
                        ctx.moveTo(bx, by);
                        ctx.lineTo(bx + Math.cos(bAng) * branchLen, by + Math.sin(bAng) * branchLen);
                    }
                }
                ctx.stroke();
                return; // 雪花只描边
        }
        
        ctx.fill();
        ctx.stroke();
    }
    
    function drawStar(ctx, points, outerR, innerR) {
        for (let i = 0; i < points * 2; i++) {
            const r = i % 2 === 0 ? outerR : innerR;
            const ang = (i / (points * 2)) * Math.PI * 2 - Math.PI / 2;
            const x = Math.cos(ang) * r;
            const y = Math.sin(ang) * r;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.closePath();
    }

    // ========== 华丽粒子生成 ==========
    function spawnParticles(cx, cy, vx, vy, n) {
        const colors = getThemeColors();
        const dir = Math.atan2(vy, vx);
        const speed = Math.hypot(vx, vy);
        
        // 确保缓存已创建
        createShapeCache();
        
        const sizes = [12, 20, 32];
        
        for (let i = 0; i < n; i++) {
            const ang = dir + (Math.random() - 0.5) * 3.2;
            const s = 0.4 + Math.random() * (0.9 + Math.min(3, speed * 0.05));
            const spread = 8 + Math.random() * 20;
            const ox = Math.cos(ang) * spread + (Math.random() - 0.5) * 12;
            const oy = Math.sin(ang) * spread + (Math.random() - 0.5) * 12;
            
            // 随机选择图形类型
            const shapeType = SHAPE_TYPES[Math.floor(Math.random() * SHAPE_TYPES.length)];
            // 随机选择尺寸
            const size = sizes[Math.floor(Math.random() * sizes.length)];
            // 颜色变体（随机选择临近色）
            const colorIdx = Math.floor(Math.random() * 3);
            
            particles.push({
                x: cx + ox,
                y: cy + oy,
                vx: Math.cos(ang) * s + (Math.random() - 0.5) * 0.4,
                vy: Math.sin(ang) * s + (Math.random() - 0.5) * 0.4,
                alpha: 0,
                alphaT: colors.isDark ? 0.85 : 0.95,
                scale: 0.5 + Math.random() * 0.5,
                life: 100 + Math.floor(Math.random() * 100),
                rot: Math.random() * Math.PI * 2,
                omega: (Math.random() - 0.5) * 0.08,
                shapeType,
                size,
                colorIdx
            });
        }
        
        if (particles.length > MAX_PARTICLES) {
            particles.splice(0, particles.length - MAX_PARTICLES);
        }
    }

    function spawnRadialParticles(cx, cy, n) {
        const colors = getThemeColors();
        createShapeCache();
        
        const sizes = [12, 20, 32];
        
        for (let i = 0; i < n; i++) {
            const ang = Math.random() * Math.PI * 2;
            const s = 0.2 + Math.random() * 0.5;
            const ox = (Math.random() - 0.5) * 8;
            const oy = (Math.random() - 0.5) * 8;
            
            const shapeType = SHAPE_TYPES[Math.floor(Math.random() * SHAPE_TYPES.length)];
            const size = sizes[Math.floor(Math.random() * sizes.length)];
            const colorIdx = Math.floor(Math.random() * 3);
            
            particles.push({
                x: cx + ox,
                y: cy + oy,
                vx: Math.cos(ang) * s,
                vy: Math.sin(ang) * s,
                alpha: 0,
                alphaT: colors.isDark ? 0.75 : 0.85,
                scale: 0.4 + Math.random() * 0.4,
                life: 80 + Math.floor(Math.random() * 60),
                rot: Math.random() * Math.PI * 2,
                omega: (Math.random() - 0.5) * 0.06,
                shapeType,
                size,
                colorIdx
            });
        }
        
        if (particles.length > MAX_PARTICLES) {
            particles.splice(0, particles.length - MAX_PARTICLES);
        }
    }

    // ========== 主绘制循环 ==========
    function drawFx() {
        fxCtx.clearRect(0, 0, fxW, fxH);
        const colors = getThemeColors();
        const primaryRgb = hexToRgb(colors.primary);

        // 确保图形缓存存在
        createShapeCache();

        // 发射粒子
        const emitCapPerFrame = 4;
        const emitCount = Math.min(emitCapPerFrame, Math.floor(sprayEnergy));
        if (emitCount > 0 && fxMouseX > -999 && fxMouseY > -999) {
            const spd = Math.hypot(mouseVx, mouseVy);
            if (spd < 0.3) {
                spawnRadialParticles(fxMouseX, fxMouseY, emitCount);
            } else {
                spawnParticles(fxMouseX, fxMouseY, mouseVx, mouseVy, emitCount);
            }
            sprayEnergy -= emitCount;
        }

        if (fxMouseX > -999 && fxMouseY > -999) {
            sprayEnergy = Math.min(50, sprayEnergy + 0.25);
        }

        // 更新并绘制华丽粒子（使用预渲染图形）
        for (let i = particles.length - 1; i >= 0; i--) {
            const p = particles[i];
            p.life -= 1;
            p.alpha += (p.alphaT - p.alpha) * 0.15;
            p.alphaT *= 0.99;
            p.scale *= 0.997;
            p.vx *= 0.98;
            p.vy *= 0.98;
            p.x += p.vx;
            p.y += p.vy;
            p.rot += p.omega;

            if (p.life <= 0 || p.alpha < 0.02 || p.scale < 0.2) {
                particles.splice(i, 1);
                continue;
            }

            // 获取预渲染的图形
            const cachedShape = shapeCache?.[p.shapeType]?.[p.size]?.[p.colorIdx];
            if (!cachedShape) continue;

            // 使用 drawImage 绘制预渲染图形（高性能）
            fxCtx.globalAlpha = p.alpha;
            fxCtx.translate(p.x, p.y);
            fxCtx.rotate(p.rot);
            fxCtx.scale(p.scale, p.scale);
            
            const halfSize = cachedShape.width / 2;
            fxCtx.drawImage(cachedShape, -halfSize, -halfSize);
            
            fxCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }
        fxCtx.globalAlpha = 1.0;
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
        
        // 修复：统一使用 fx 坐标系计算位置和速度
        // 避免 bg-canvas 的 transform: scale(1.1) 导致坐标系偏差
        const newMouseX = e.clientX - fxRect.left;
        const newMouseY = e.clientY - fxRect.top;
        
        // 计算速度：当前位置 - 上一帧位置（必须使用同一坐标系）
        if (fxMouseX > -999 && fxMouseY > -999) {
            mouseVx = newMouseX - fxMouseX;
            mouseVy = newMouseY - fxMouseY;
        } else {
            mouseVx = 0;
            mouseVy = 0;
        }
        
        fxMouseX = newMouseX;
        fxMouseY = newMouseY;
        
        const spd = Math.hypot(mouseVx, mouseVy);
        sprayEnergy = Math.min(80, sprayEnergy + Math.min(6, 1.2 + spd * 0.06));
        
        // 返回值给 background 使用（bg 坐标系）
        const x = e.clientX - bgCanvasRect.left;
        const y = e.clientY - bgCanvasRect.top;
        return { x, y, vx: mouseVx, vy: mouseVy };
    }

    function handleClick(e, cardElement) {
        // 点击效果已禁用（性能优化）
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