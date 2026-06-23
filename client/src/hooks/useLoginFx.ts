/**
 * useLoginFx - 登录页交互特效 Composable
 *
 * 设计理念：
 * - 预渲染星芒粒子（高性能）
 * - 仅保留四角星、五角星与多角星
 * - 去掉多余几何图形与鼠标光晕
 * - 完全接入主题色系统，浅色模式下增强可见性
 */

import { ref, computed } from 'vue';
import { useThemeStore } from '@/components/stores/themeStore';

type RgbColor = {
    r: number;
    g: number;
    b: number;
};

type ThemeColors = {
    primary: string;
    accent: string;
    isDark: boolean;
};

type ParticleSize = 12 | 20 | 32;
type ShapeType = 'star4' | 'star5' | 'star6' | 'star8';

type FxParticle = {
    x: number;
    y: number;
    vx: number;
    vy: number;
    alpha: number;
    alphaT: number;
    scale: number;
    life: number;
    rot: number;
    omega: number;
    shapeType: ShapeType;
    size: ParticleSize;
    colorIdx: number;
};

type ShapeCache = Record<ShapeType, Record<ParticleSize, Record<number, HTMLCanvasElement>>>;

type FxMousePayload = {
    x: number;
    y: number;
    vx: number;
    vy: number;
};

export function useLoginFx() {
    // ========== 响应式状态 ==========
    const fxCanvas = ref<HTMLCanvasElement | null>(null);
    const themeStore = useThemeStore();
    
    const isDark = computed(() =>
        themeStore.themeMode === 'dark' ||
        (themeStore.themeMode === 'system' && themeStore.prefersDark)
    );

    // ========== 内部状态 ==========
    let fxCtx: CanvasRenderingContext2D | null = null;
    let fxW = 0;
    let fxH = 0;
    let dpr = 1;
    let fxRafId: number | null = null;
    let fxMouseX = -9999;
    let fxMouseY = -9999;
    let mouseVx = 0;
    let mouseVy = 0;
    let sprayEnergy = 0;
    
    // 预渲染图形缓存
    let shapeCache: ShapeCache | null = null;
    let cachedColorKey = '';

    const particles: FxParticle[] = [];     // 星芒粒子
    const MAX_PARTICLES = 72;
    const PARTICLE_SIZES: readonly ParticleSize[] = [12, 20, 32];

    const SHAPE_TYPES: readonly ShapeType[] = [
        'star4', 'star5', 'star6', 'star8'
    ];

    // ========== 主题色获取 ==========
    function getThemeColors(): ThemeColors {
        const style = getComputedStyle(document.body);
        const primary = style.getPropertyValue('--spark-primary').trim() || '#1deaaa';
        const accent = style.getPropertyValue('--spark-accent').trim() || '#bd93f9';
        
        return { primary, accent, isDark: isDark.value };
    }

    function hexToRgb(hex: string): RgbColor {
        const h = hex.replace('#', '');
        const bigint = parseInt(h, 16);
        return {
            r: (bigint >> 16) & 255,
            g: (bigint >> 8) & 255,
            b: bigint & 255
        };
    }

    function mixRgb(a: RgbColor, b: RgbColor, t: number): RgbColor {
        return {
            r: Math.round(a.r + (b.r - a.r) * t),
            g: Math.round(a.g + (b.g - a.g) * t),
            b: Math.round(a.b + (b.b - a.b) * t),
        };
    }

    // RGB 转 HSL
    function rgbToHsl(r: number, g: number, b: number) {
        r /= 255, g /= 255, b /= 255;
        const max = Math.max(r, g, b), min = Math.min(r, g, b);
        let h = 0;
        let s = 0;
        const l = (max + min) / 2;
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
    function hslToRgb(h: number, s: number, l: number): RgbColor {
        let r = l;
        let g = l;
        let b = l;
        if (s === 0) {
            r = g = b = l;
        } else {
            const hue2rgb = (p: number, q: number, t: number) => {
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
    
    function getParticlePalette(colors: ThemeColors): RgbColor[] {
        const primaryRgb = hexToRgb(colors.primary);
        const accentRgb = hexToRgb(colors.accent || colors.primary);
        const themeBlend = mixRgb(primaryRgb, accentRgb, 0.45);

        return [
            mixRgb(themeBlend, { r: 255, g: 104, b: 198 }, colors.isDark ? 0.34 : 0.42),
            mixRgb(primaryRgb, { r: 99, g: 141, b: 255 }, colors.isDark ? 0.4 : 0.52),
            mixRgb(accentRgb, { r: 124, g: 233, b: 255 }, colors.isDark ? 0.44 : 0.56),
        ];
    }

    function rand(min: number, max: number): number {
        return Math.random() * (max - min) + min;
    }

    // ========== 预渲染几何图形 ==========
    function createShapeCache() {
        const colors = getThemeColors();
        const colorKey = `${colors.primary}-${colors.accent}-${colors.isDark}`;
        
        // 如果颜色没变，不需要重新渲染
        if (shapeCache && cachedColorKey === colorKey) return;
        cachedColorKey = colorKey;
        
        const colorVariants = getParticlePalette(colors);
        
        // 每种图形预渲染多个尺寸（小、中、大）
        const sizes = PARTICLE_SIZES;
        
        const nextShapeCache = {} as ShapeCache;
        
        for (const shapeType of SHAPE_TYPES) {
            nextShapeCache[shapeType] = {} as Record<ParticleSize, Record<number, HTMLCanvasElement>>;
            for (const size of sizes) {
                nextShapeCache[shapeType][size] = {};
                for (let ci = 0; ci < colorVariants.length; ci++) {
                    const rgb = colorVariants[ci];
                    const canvas = document.createElement('canvas');
                    const padding = 4;
                    canvas.width = size + padding * 2;
                    canvas.height = size + padding * 2;
                    const ctx = canvas.getContext('2d');
                    if (!ctx) continue;
                    
                    ctx.translate(canvas.width / 2, canvas.height / 2);
                    
                    ctx.shadowColor = `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${colors.isDark ? 0.95 : 0.78})`;
                    ctx.shadowBlur = colors.isDark ? 9 : 6;
                    
                    ctx.fillStyle = `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.96)`;
                    ctx.strokeStyle = `rgba(255, 255, 255, ${colors.isDark ? 0.34 : 0.2})`;
                    ctx.lineWidth = 1.2;
                    
                     ctx.globalCompositeOperation = 'source-over';
                     drawShape(ctx, shapeType, size / 2);
                     
                     ctx.shadowBlur = 0;
                     ctx.fillStyle = colors.isDark ? 'rgba(255, 255, 255, 0.24)' : 'rgba(255, 255, 255, 0.32)';
                     ctx.fill();
                     
                     nextShapeCache[shapeType][size][ci] = canvas;
                }
            }
        }

        shapeCache = nextShapeCache;
    }
    
    // 绘制各种形状
    function drawShape(ctx: CanvasRenderingContext2D, type: ShapeType, r: number) {
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
            default:
                drawStar(ctx, 5, r, r * 0.45);
                break;
        }
        
        ctx.fill();
        ctx.stroke();
    }
    
    function drawStar(ctx: CanvasRenderingContext2D, points: number, outerR: number, innerR: number) {
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
    function spawnParticles(cx: number, cy: number, vx: number, vy: number, n: number) {
        const colors = getThemeColors();
        const dir = Math.atan2(vy, vx);
        const speed = Math.hypot(vx, vy);
        
        // 确保缓存已创建
        createShapeCache();
        
        const sizes = PARTICLE_SIZES;
        
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

    function spawnRadialParticles(cx: number, cy: number, n: number) {
        const colors = getThemeColors();
        createShapeCache();
        
        const sizes = PARTICLE_SIZES;
        
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
        if (!fxCtx) return;
        fxCtx.clearRect(0, 0, fxW, fxH);
        const colors = getThemeColors();

        // 确保图形缓存存在
        createShapeCache();

        // 发射粒子
        const emitCapPerFrame = 3;
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

        fxRafId = requestAnimationFrame(drawFx);
    }

    // ========== resize 处理 ==========
    function resizeFx() {
        const c = fxCanvas.value;
        if (!c || !fxCtx) return;
        dpr = Math.min(window.devicePixelRatio || 1, 1.5);
        fxW = c.clientWidth;
        fxH = c.clientHeight;
        c.width = Math.floor(fxW * dpr);
        c.height = Math.floor(fxH * dpr);
        fxCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    // ========== 事件处理 ==========
    function handleMouseMove(e: MouseEvent, bgCanvasRect: DOMRect | DOMRectReadOnly): FxMousePayload {
        const fxEl = fxCanvas.value;
        if (!fxEl) return { x: e.clientX, y: e.clientY, vx: 0, vy: 0 };
        const fxRect = fxEl.getBoundingClientRect();
        
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

    function handleClick(_e: MouseEvent, _cardElement?: HTMLElement | null) {
        // 点击效果已禁用（性能优化）
    }

    function handleLeave() {
        fxMouseX = -9999;
        fxMouseY = -9999;
        sprayEnergy = 0;
    }

    // ========== 生命周期 ==========
    function init() {
        const c = fxCanvas.value;
        if (!c) return;
        fxCtx = c.getContext('2d');
        if (!fxCtx) return;
        resizeFx();
        window.addEventListener('resize', resizeFx);
        fxRafId = requestAnimationFrame(drawFx);
    }

    function destroy() {
        if (fxRafId !== null) cancelAnimationFrame(fxRafId);
        fxRafId = null;
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
