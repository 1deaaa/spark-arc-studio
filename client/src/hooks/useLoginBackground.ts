/**
 * useLoginBackground - 登录页星云背景 Composable
 * 
 * 设计理念：
 * - 采用"星云"美学，体现 SparkArc 的品牌意象
 * - 动态流动的星云效果
 * - 完全接入主题色系统，响应亮暗模式切换
 * - 亮色模式采用"光雾"效果
 */

import { ref, computed, watch } from 'vue';
import { useThemeStore } from '@/components/stores/themeStore';

type RgbColor = {
    r: number;
    g: number;
    b: number;
};

type ThemeColors = {
    primary: string;
    bg: string;
    accent: string;
    isDark: boolean;
};

type NebulaPaletteEntry = {
    rgb: RgbColor;
    alpha: number;
};

type NebulaCloud = {
    originX: number;
    originY: number;
    x: number;
    y: number;
    move1_offsetX: number;
    move1_offsetY: number;
    move1_speedX: number;
    move1_speedY: number;
    move1_radiusX: number;
    move1_radiusY: number;
    move2_offsetX: number;
    move2_offsetY: number;
    move2_speedX: number;
    move2_speedY: number;
    move2_radiusX: number;
    move2_radiusY: number;
    radius: number;
    phase: number;
    phaseSpeed: number;
    opacity: number;
    paletteIndex: number;
    companionIndex: number;
    highlightIndex: number;
    stretchX: number;
    stretchY: number;
    rotation: number;
    rotationSpeed: number;
    lobePhase: number;
    lobeSpeed: number;
    lobeOffset: number;
    parallax: number;
};

type MouseState = {
    x: number;
    y: number;
    vx: number;
    vy: number;
};

export function useLoginBackground() {
    // ========== 响应式状态 ==========
    const bgCanvas = ref<HTMLCanvasElement | null>(null);
    const themeStore = useThemeStore();

    const isDark = computed(() =>
        themeStore.themeMode === 'dark' ||
        (themeStore.themeMode === 'system' && themeStore.prefersDark)
    );

    // ========== 内部状态 ==========
    let ctx: CanvasRenderingContext2D | null = null;
    let rafId: number | null = null;
    let nebulaClouds: NebulaCloud[] = [];
    let nebulaPalette: NebulaPaletteEntry[] = [];
    let width = 0;          // canvas 实际渲染尺寸
    let height = 0;
    let displayWidth = 0;   // 显示尺寸（用于计算星云位置）
    let displayHeight = 0;
    let renderScale = 1;    // 渲染缩放因子
    let mouse: MouseState = { x: -9999, y: -9999, vx: 0, vy: 0 };
    let time = 0;
    let themeSignature = '';

    // ========== 主题色获取 ==========
    function getThemeColors(): ThemeColors {
        const style = getComputedStyle(document.body);
        const primary = style.getPropertyValue('--spark-primary').trim() || '#1deaaa';
        const bg = style.getPropertyValue('--spark-bg').trim() || '#090b10';
        const accent = style.getPropertyValue('--spark-accent').trim() || '#bd93f9';

        return { primary, bg, accent, isDark: isDark.value };
    }

    // ========== 工具函数 ==========
    function rand(min: number, max: number) {
        return Math.random() * (max - min) + min;
    }

    function clamp(value: number, min: number, max: number) {
        return Math.min(max, Math.max(min, value));
    }

    function hexToRgb(hex: string): RgbColor {
        const h = hex.replace('#', '');
        const normalized = h.length === 3 ? h.split('').map((v) => v + v).join('') : h;
        if (!/^[0-9a-fA-F]{6}$/.test(normalized)) {
            return { r: 122, g: 162, b: 247 };
        }
        const bigint = parseInt(normalized, 16);
        return {
            r: (bigint >> 16) & 255,
            g: (bigint >> 8) & 255,
            b: bigint & 255
        };
    }

    function rgbaString(rgb: RgbColor, alpha: number) {
        return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
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
        let h, s, l = (max + min) / 2;

        if (max === min) {
            h = s = 0; // achromatic
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
        let r, g, b;
        if (s === 0) {
            r = g = b = l; // achromatic
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

    // 改进的 FBM 噪声函数 (分形布朗运动模拟)
    function noise(x: number, y: number, t: number) {
        // 第一层：大尺度流动
        const n1 = Math.sin(x * 0.002 + t * 0.5) * Math.cos(y * 0.002 + t * 0.3);
        // 第二层：中等细节
        const n2 = Math.sin(x * 0.005 - t * 0.2 + n1 * 2) * Math.cos(y * 0.005 + t * 0.4);
        // 第三层：微小湍流
        const n3 = Math.sin(x * 0.01 + t + n2 * 3) * 0.5;
        return n1 * 0.5 + n2 * 0.3 + n3 * 0.2;
    }

    function buildNebulaPalette(colors: ThemeColors): NebulaPaletteEntry[] {
        const primaryRgb = hexToRgb(colors.primary);
        const accentRgb = hexToRgb(colors.accent || colors.primary);
        const themeBlend = mixRgb(primaryRgb, accentRgb, 0.45);
        const dreamySeeds = [
            { hex: '#ff68c8', mix: 0.42, alpha: colors.isDark ? 0.28 : 0.22 },
            { hex: '#9870ff', mix: 0.5, alpha: colors.isDark ? 0.26 : 0.2 },
            { hex: '#4e8fff', mix: 0.58, alpha: colors.isDark ? 0.24 : 0.18 },
            { hex: '#68e3ff', mix: 0.62, alpha: colors.isDark ? 0.22 : 0.17 },
            { hex: '#ffc1f1', mix: 0.34, alpha: colors.isDark ? 0.17 : 0.13 },
            { hex: '#8c7dff', mix: 0.4, alpha: colors.isDark ? 0.18 : 0.14 },
        ];

        return dreamySeeds.map((seed, index) => {
            const seedRgb = hexToRgb(seed.hex);
            const themeBridge = index % 2 === 0
                ? mixRgb(primaryRgb, themeBlend, 0.4)
                : mixRgb(accentRgb, themeBlend, 0.56);
            return {
                rgb: mixRgb(themeBridge, seedRgb, colors.isDark ? seed.mix : clamp(seed.mix + 0.08, 0, 0.82)),
                alpha: seed.alpha,
            };
        });
    }

    // ========== 星云云层 ==========
    function ensurePalette(colors: ThemeColors) {
        const signature = `${colors.primary}|${colors.accent}|${colors.bg}|${colors.isDark}`;
        if (signature === themeSignature) return;
        themeSignature = signature;
        nebulaPalette = buildNebulaPalette(colors);
        createNebulaClouds();
    }

    function createNebulaClouds() {
        nebulaClouds = [];
        const count = displayWidth > 1600 ? 14 : displayWidth > 1100 ? 12 : 10;
        for (let i = 0; i < count; i++) {
            const layer = i % 3;
            const marginX = displayWidth * 0.28;
            const marginY = displayHeight * 0.26;
            const originX = rand(-marginX, displayWidth + marginX);
            const originY = rand(-marginY, displayHeight + marginY);
            const paletteIndex = i < nebulaPalette.length ? i : Math.floor(rand(0, nebulaPalette.length));
            const companionIndex = (paletteIndex + 1 + Math.floor(rand(0, nebulaPalette.length - 1))) % nebulaPalette.length;
            const highlightIndex = (paletteIndex + 2 + Math.floor(rand(0, nebulaPalette.length - 1))) % nebulaPalette.length;

            nebulaClouds.push({
                originX,
                originY,
                x: originX,
                y: originY,
                move1_offsetX: rand(0, Math.PI * 2),
                move1_offsetY: rand(0, Math.PI * 2),
                move1_speedX: rand(0.05, 0.12),
                move1_speedY: rand(0.04, 0.1),
                move1_radiusX: rand(displayWidth * 0.1, displayWidth * 0.22),
                move1_radiusY: rand(displayHeight * 0.08, displayHeight * 0.2),
                move2_offsetX: rand(0, Math.PI * 2),
                move2_offsetY: rand(0, Math.PI * 2),
                move2_speedX: rand(0.12, 0.24),
                move2_speedY: rand(0.1, 0.22),
                move2_radiusX: rand(displayWidth * 0.03, displayWidth * 0.09),
                move2_radiusY: rand(displayHeight * 0.03, displayHeight * 0.09),
                radius: layer === 0
                    ? rand(180, 320)
                    : layer === 1
                        ? rand(320, 560)
                        : rand(520, 860),
                phase: rand(0, Math.PI * 2),
                phaseSpeed: rand(0.0012, 0.0022),
                opacity: layer === 0 ? rand(0.92, 1.18) : layer === 1 ? rand(0.76, 1.02) : rand(0.58, 0.84),
                paletteIndex,
                companionIndex,
                highlightIndex,
                stretchX: rand(0.78, 1.55),
                stretchY: rand(0.72, 1.46),
                rotation: rand(0, Math.PI * 2),
                rotationSpeed: rand(-0.045, 0.045),
                lobePhase: rand(0, Math.PI * 2),
                lobeSpeed: rand(0.2, 0.52),
                lobeOffset: rand(0.18, 0.34),
                parallax: rand(0.3, 1),
            });
        }
    }

    function resize() {
        const c = bgCanvas.value;
        if (!c) return;
        
        // 保存显示尺寸（用于星云位置计算）
        displayWidth = c.clientWidth;
        displayHeight = c.clientHeight;
        
        const maxPixels = 320000;
        const currentPixels = displayWidth * displayHeight;
        
        if (currentPixels > maxPixels) {
            renderScale = Math.sqrt(maxPixels / currentPixels);
        } else {
            renderScale = 1;
        }
        
        width = Math.floor(displayWidth * renderScale);
        height = Math.floor(displayHeight * renderScale);
        
        c.width = width;
        c.height = height;
        
        ctx?.setTransform(1, 0, 0, 1, 0, 0);
        ensurePalette(getThemeColors());
        createNebulaClouds();
    }

    function drawGlowEllipse(x: number, y: number, radius: number, rgb: RgbColor, alpha: number, stretchX = 1, stretchY = 1, rotation = 0) {
        if (!ctx) return;
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(rotation);
        ctx.scale(stretchX, stretchY);

        const gradient = ctx.createRadialGradient(0, 0, 0, 0, 0, radius);
        gradient.addColorStop(0, rgbaString(rgb, alpha));
        gradient.addColorStop(0.28, rgbaString(rgb, alpha * 0.74));
        gradient.addColorStop(0.62, rgbaString(rgb, alpha * 0.24));
        gradient.addColorStop(1, rgbaString(rgb, 0));

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(0, 0, radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }

    function drawBaseGradient(colors: ThemeColors) {
        if (!ctx) return;
        const bgRgb = hexToRgb(colors.bg);
        const baseGradient = ctx.createLinearGradient(0, 0, width, height);

        if (colors.isDark) {
            baseGradient.addColorStop(0, rgbaString(mixRgb(bgRgb, { r: 8, g: 10, b: 20 }, 0.58), 1));
            baseGradient.addColorStop(0.42, rgbaString(mixRgb(bgRgb, { r: 12, g: 15, b: 28 }, 0.36), 1));
            baseGradient.addColorStop(1, rgbaString(mixRgb(bgRgb, { r: 4, g: 6, b: 14 }, 0.76), 1));
        } else {
            baseGradient.addColorStop(0, 'rgba(249, 243, 252, 1)');
            baseGradient.addColorStop(0.46, 'rgba(245, 240, 251, 1)');
            baseGradient.addColorStop(1, 'rgba(236, 244, 255, 1)');
        }

        ctx.fillStyle = baseGradient;
        ctx.fillRect(0, 0, width, height);

        const washes = [
            {
                x: width * 0.14 + Math.sin(time * 0.06) * width * 0.05,
                y: height * 0.2 + Math.cos(time * 0.05) * height * 0.04,
                radius: Math.max(width, height) * 0.82,
                color: nebulaPalette[0]?.rgb,
                alpha: colors.isDark ? 0.22 : 0.18,
            },
            {
                x: width * 0.78 + Math.cos(time * 0.05) * width * 0.04,
                y: height * 0.22 + Math.sin(time * 0.04) * height * 0.03,
                radius: Math.max(width, height) * 0.74,
                color: nebulaPalette[2]?.rgb,
                alpha: colors.isDark ? 0.18 : 0.14,
            },
            {
                x: width * 0.56 + Math.sin(time * 0.04) * width * 0.03,
                y: height * 0.78 + Math.cos(time * 0.03) * height * 0.03,
                radius: Math.max(width, height) * 0.7,
                color: nebulaPalette[3]?.rgb,
                alpha: colors.isDark ? 0.16 : 0.12,
            },
        ];

        for (const wash of washes) {
            if (!wash.color) continue;
            const gradient = ctx.createRadialGradient(wash.x, wash.y, 0, wash.x, wash.y, wash.radius);
            gradient.addColorStop(0, rgbaString(wash.color, wash.alpha));
            gradient.addColorStop(0.55, rgbaString(wash.color, wash.alpha * 0.26));
            gradient.addColorStop(1, rgbaString(wash.color, 0));
            ctx.fillStyle = gradient;
            ctx.fillRect(0, 0, width, height);
        }
    }

    // ========== 主绘制循环 ==========
    function draw() {
        if (!ctx) return;
        time += 0.026;
        const colors = getThemeColors();
        ensurePalette(colors);
        drawBaseGradient(colors);

        const parallaxX = mouse.x > -999 && displayWidth
            ? ((mouse.x / displayWidth) - 0.5) * width * 0.06
            : 0;
        const parallaxY = mouse.y > -999 && displayHeight
            ? ((mouse.y / displayHeight) - 0.5) * height * 0.06
            : 0;

        const majorRadius = Math.max(width, height);
        ctx.save();
        ctx.globalCompositeOperation = colors.isDark ? 'screen' : 'source-over';
        drawGlowEllipse(
            width * 0.18 + Math.sin(time * 0.18) * width * 0.085 + parallaxX * 0.4,
            height * 0.22 + Math.cos(time * 0.14) * height * 0.075 + parallaxY * 0.4,
            majorRadius * 0.54,
            nebulaPalette[0].rgb,
            colors.isDark ? 0.3 : 0.24,
            1.35,
            1,
            time * 0.07
        );
        drawGlowEllipse(
            width * 0.82 - Math.cos(time * 0.16) * width * 0.095 + parallaxX * 0.34,
            height * 0.18 + Math.sin(time * 0.13) * height * 0.06 + parallaxY * 0.34,
            majorRadius * 0.46,
            nebulaPalette[3].rgb,
            colors.isDark ? 0.28 : 0.21,
            1.12,
            1.32,
            -time * 0.055
        );
        drawGlowEllipse(
            width * 0.54 + Math.sin(time * 0.1) * width * 0.055,
            height * 0.74 + Math.cos(time * 0.11) * height * 0.065,
            majorRadius * 0.4,
            nebulaPalette[4].rgb,
            colors.isDark ? 0.22 : 0.16,
            1.28,
            0.92,
            time * 0.04
        );
        ctx.restore();

        ctx.save();
        ctx.globalCompositeOperation = colors.isDark ? 'screen' : 'source-over';
        for (const cloud of nebulaClouds) {
            cloud.phase += cloud.phaseSpeed;
            const move1_x = Math.sin(time * cloud.move1_speedX + cloud.move1_offsetX) * cloud.move1_radiusX;
            const move1_y = Math.cos(time * cloud.move1_speedY + cloud.move1_offsetY) * cloud.move1_radiusY;
            const move2_x = Math.sin(time * cloud.move2_speedX + cloud.move2_offsetX) * cloud.move2_radiusX;
            const move2_y = Math.cos(time * cloud.move2_speedY + cloud.move2_offsetY) * cloud.move2_radiusY;

            cloud.x = cloud.originX + move1_x + move2_x;
            cloud.y = cloud.originY + move1_y + move2_y;
            const breathScale = 1 + Math.sin(cloud.phase) * 0.18;
            const currentRadius = cloud.radius * breathScale * renderScale;
            const paletteEntry = nebulaPalette[cloud.paletteIndex];
            const companionEntry = nebulaPalette[cloud.companionIndex];
            const highlightEntry = nebulaPalette[cloud.highlightIndex];
            const renderX = cloud.x * renderScale + parallaxX * cloud.parallax;
            const renderY = cloud.y * renderScale + parallaxY * cloud.parallax;
            const swirl = noise(renderX * 0.014, renderY * 0.014, time * 0.9);
            const rotation = cloud.rotation + time * cloud.rotationSpeed;
            const lobeDistance = currentRadius * cloud.lobeOffset;
            const lobeOrbit = time * cloud.lobeSpeed + cloud.lobePhase;
            const offsetAX = Math.cos(lobeOrbit) * lobeDistance + swirl * currentRadius * 0.08;
            const offsetAY = Math.sin(lobeOrbit * 0.92) * lobeDistance * 0.76;
            const offsetBX = Math.cos(-lobeOrbit * 1.08) * lobeDistance * 0.72;
            const offsetBY = Math.sin(-lobeOrbit) * lobeDistance * 0.64;

            drawGlowEllipse(
                renderX,
                renderY,
                currentRadius,
                paletteEntry.rgb,
                cloud.opacity * paletteEntry.alpha,
                cloud.stretchX,
                cloud.stretchY,
                rotation
            );
            drawGlowEllipse(
                renderX + offsetAX,
                renderY + offsetAY,
                currentRadius * 0.72,
                companionEntry.rgb,
                cloud.opacity * companionEntry.alpha * 0.92,
                cloud.stretchY,
                cloud.stretchX,
                -rotation * 0.8
            );
            drawGlowEllipse(
                renderX - offsetBX,
                renderY - offsetBY,
                currentRadius * 0.46,
                highlightEntry.rgb,
                cloud.opacity * highlightEntry.alpha * 0.82,
                cloud.stretchX * 0.92,
                cloud.stretchY * 0.92,
                rotation * 1.12
            );
        }
        ctx.restore();

        rafId = requestAnimationFrame(draw);
    }

    // ========== 鼠标处理 ==========
    function updateMouse(x: number, y: number, vx: number, vy: number) {
        mouse.x = x;
        mouse.y = y;
        mouse.vx = vx;
        mouse.vy = vy;
    }

    function resetMouse() {
        mouse.x = -9999;
        mouse.y = -9999;
    }

    // ========== 生命周期 ==========
    function init() {
        const c = bgCanvas.value;
        if (!c) return;
        ctx = c.getContext('2d');
        themeSignature = '';
        resize();
        window.addEventListener('resize', resize);
        rafId = requestAnimationFrame(draw);
    }

    function destroy() {
        if (rafId) cancelAnimationFrame(rafId);
        window.removeEventListener('resize', resize);
    }

    // 监听主题变化时重新初始化
    watch(isDark, () => {
        if (ctx) {
            themeSignature = '';
            ensurePalette(getThemeColors());
            createNebulaClouds();
        }
    });

    // ========== 导出 ==========
    return {
        bgCanvas,
        init,
        destroy,
        updateMouse,
        resetMouse,
    };
}
