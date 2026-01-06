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

export function useLoginBackground() {
    // ========== 响应式状态 ==========
    const bgCanvas = ref(null);
    const themeStore = useThemeStore();

    const isDark = computed(() =>
        themeStore.themeMode === 'dark' ||
        (themeStore.themeMode === 'system' && themeStore.prefersDark)
    );

    // ========== 内部状态 ==========
    let ctx = null;
    let rafId = null;
    let nebulaClouds = [];
    let width = 0;
    let height = 0;
    let mouse = { x: -9999, y: -9999, vx: 0, vy: 0 };
    let time = 0;
    let noisePattern = null; // 噪声纹理用于消除色阶

    // ========== 主题色获取 ==========
    function getThemeColors() {
        const style = getComputedStyle(document.body);
        const primary = style.getPropertyValue('--spark-primary').trim() || '#7aa2f7';
        const bg = style.getPropertyValue('--spark-bg').trim() || '#090b10';
        const accent = style.getPropertyValue('--spark-accent').trim() || '#bd93f9';

        return { primary, bg, accent, isDark: isDark.value };
    }

    // ========== 工具函数 ==========
    function rand(min, max) {
        return Math.random() * (max - min) + min;
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
    function hslToRgb(h, s, l) {
        let r, g, b;
        if (s === 0) {
            r = g = b = l; // achromatic
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

    // 改进的 FBM 噪声函数 (分形布朗运动模拟)
    function noise(x, y, t) {
        // 第一层：大尺度流动
        const n1 = Math.sin(x * 0.002 + t * 0.5) * Math.cos(y * 0.002 + t * 0.3);
        // 第二层：中等细节
        const n2 = Math.sin(x * 0.005 - t * 0.2 + n1 * 2) * Math.cos(y * 0.005 + t * 0.4);
        // 第三层：微小湍流
        const n3 = Math.sin(x * 0.01 + t + n2 * 3) * 0.5;
        return n1 * 0.5 + n2 * 0.3 + n3 * 0.2;
    }

    // 生成噪声纹理防止色阶
    function createNoisePattern() {
        const pCanvas = document.createElement('canvas');
        pCanvas.width = 128;
        pCanvas.height = 128;
        const pCtx = pCanvas.getContext('2d');
        const imgData = pCtx.createImageData(128, 128);
        const data = imgData.data;

        for (let i = 0; i < data.length; i += 4) {
            const v = Math.floor(Math.random() * 255);
            data[i] = v;     // R
            data[i + 1] = v; // G
            data[i + 2] = v; // B
            data[i + 3] = 8; // Alpha (非常低，约3%)
        }

        pCtx.putImageData(imgData, 0, 0);
        // 创建 pattern
        if (ctx) {
            noisePattern = ctx.createPattern(pCanvas, 'repeat');
        }
    }

    // ========== 星云云层 ==========
    function createNebulaClouds() {
        nebulaClouds = [];
        // 性能优化：减少云团数量
        const count = 6 + Math.floor(Math.random() * 4);
        for (let i = 0; i < count; i++) {
            // 扩大分布范围，让星云从更外侧开始，能够穿越边缘
            const marginX = width * 0.5;  // 从边缘外 50% 开始
            const marginY = height * 0.5;

            // 基础坐标 - 对称分布，覆盖整个屏幕加上边缘外区域
            const originX = rand(-marginX, width + marginX);
            const originY = rand(-marginY, height + marginY);

            nebulaClouds.push({
                originX,
                originY,
                x: originX,
                y: originY,

                // ===== 增强随机来回运动参数 =====
                // 多层运动，叠加不同频率实现更自然的漫游
                // 第一层：主运动 - 超大范围慢速漂移（让星云能穿越边缘）
                move1_offsetX: rand(0, Math.PI * 2),
                move1_offsetY: rand(0, Math.PI * 2),
                move1_speedX: rand(0.15, 0.25),   // 适中的速度
                move1_speedY: rand(0.12, 0.22),
                move1_radiusX: rand(400, 800),    // 大幅增加运动范围
                move1_radiusY: rand(400, 800),

                // 第二层：次运动 - 大范围中速漂移
                move2_offsetX: rand(0, Math.PI * 2),
                move2_offsetY: rand(0, Math.PI * 2),
                move2_speedX: rand(0.35, 0.60),   // 稍快的速度
                move2_speedY: rand(0.30, 0.55),
                move2_radiusX: rand(150, 300),    // 大幅增加运动范围
                move2_radiusY: rand(150, 300),

                // 第三层：微运动 - 中等范围快速波动
                move3_offsetX: rand(0, Math.PI * 2),
                move3_offsetY: rand(0, Math.PI * 2),
                move3_speedX: rand(0.8, 1.2),     // 较快速度
                move3_speedY: rand(0.7, 1.1),
                move3_radiusX: rand(40, 80),      // 中等范围
                move3_radiusY: rand(40, 80),

                // 更大的半径
                radius: rand(350, 700),
                // 呼吸相位
                phase: rand(0, Math.PI * 2),
                phaseSpeed: rand(0.0006, 0.0015),
                // 大幅提高透明度，让星云在整个画布都清晰可见
                opacity: rand(0.20, 0.35),
                // 颜色混合
                colorMixBase: rand(0, 1),
                colorMixSpeed: rand(0.002, 0.008)
            });
        }
    }

    function resize() {
        const c = bgCanvas.value;
        if (!c) return;
        // 性能优化：强制使用 DPR=1，显著降低像素处理量
        const dpr = 1;
        width = c.clientWidth;
        height = c.clientHeight;
        c.width = Math.floor(width * dpr);
        c.height = Math.floor(height * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        // createNoisePattern(); // 移除未使用的噪声生成
        // 性能优化：背景已模糊，移除不可见的微小粒子绘制
        createNebulaClouds();
    }

    // ========== 主绘制循环 ==========
    function draw() {
        time += 0.016; // 增加时间增速，让星云运动更明显
        const colors = getThemeColors();
        const primaryRgb = hexToRgb(colors.primary);
        // const accentRgb = hexToRgb(colors.accent || colors.primary); // 移除：不再使用强调色混合，避免脏色

        // 计算主色的 HSL，用于生成和谐色
        const primaryHsl = rgbToHsl(primaryRgb.r, primaryRgb.g, primaryRgb.b);

        // 背景渐变 - 统一使用动态光晕背景
        // 让背景光晕中心缓慢游走，打破静止感
        const bgX = width * 0.5 + Math.sin(time * 0.15) * (width * 0.2);
        const bgY = height * 0.5 + Math.cos(time * 0.12) * (height * 0.15);

        const g = ctx.createRadialGradient(
            bgX, bgY, 0,  // 动态中心点
            bgX, bgY, Math.max(width, height) * 0.9
        );

        if (colors.isDark) {
            // 暗色模式：深邃星空
            g.addColorStop(0, `rgba(${Math.min(255, primaryRgb.r + 10)}, ${Math.min(255, primaryRgb.g + 10)}, ${Math.min(255, primaryRgb.b + 10)}, 0.12)`);
            g.addColorStop(0.6, 'rgba(12, 14, 22, 1)');
            g.addColorStop(1, 'rgba(10, 12, 18, 1)');
        } else {
            // 亮色模式：清透白底 + 主题色微光
            // 中心是淡淡的主题色光晕
            g.addColorStop(0, `rgba(${primaryRgb.r}, ${primaryRgb.g}, ${primaryRgb.b}, 0.08)`);
            // 中间过渡到近白色
            g.addColorStop(0.6, 'rgba(249, 251, 249, 1)');
            // 边缘纯白
            g.addColorStop(1, 'rgba(255, 255, 255, 1)');
        }
        
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, width, height);

        // ===== 绘制真正漫游的星云云层 =====
        for (const cloud of nebulaClouds) {
            cloud.phase += cloud.phaseSpeed;

            // ===== 多层随机来回运动：三层正弦波叠加实现自然漫游 =====
            // 第一层：大范围慢速漂移
            const move1_x = Math.sin(time * cloud.move1_speedX + cloud.move1_offsetX) * cloud.move1_radiusX;
            const move1_y = Math.cos(time * cloud.move1_speedY + cloud.move1_offsetY) * cloud.move1_radiusY;

            // 第二层：中等范围中速漂移（增加随机感）
            const move2_x = Math.sin(time * cloud.move2_speedX + cloud.move2_offsetX) * cloud.move2_radiusX;
            const move2_y = Math.cos(time * cloud.move2_speedY + cloud.move2_offsetY) * cloud.move2_radiusY;

            // 第三层：小范围快速波动（增加活力）
            const move3_x = Math.sin(time * cloud.move3_speedX + cloud.move3_offsetX) * cloud.move3_radiusX;
            const move3_y = Math.cos(time * cloud.move3_speedY + cloud.move3_offsetY) * cloud.move3_radiusY;

            // 叠加三层运动
            cloud.x = cloud.originX + move1_x + move2_x + move3_x;
            cloud.y = cloud.originY + move1_y + move2_y + move3_y;

            // 动态半径：呼吸效果
            const breathScale = 1 + Math.sin(cloud.phase) * 0.15;
            const currentRadius = cloud.radius * breathScale;

            // 动态颜色混合 - 使用 HSL 和谐旋转
            // 调整：邻近色取值向右旋转 (正向偏移)，范围控制在 0-45 度，避免产生对比色感
            const wave1 = Math.sin(time * cloud.colorMixSpeed + cloud.colorMixBase * Math.PI * 2);
            const wave2 = Math.cos(time * cloud.colorMixSpeed * 0.7 + cloud.phase); // 引入不同频率和相位
            
            const rawWave = wave1 * 0.6 + wave2 * 0.4; // 约 -1 到 1
            const hueShift = (rawWave * 0.5 + 0.5) * 45; // 归一化后映射到 0 到 45 度 (向右旋转)

            const targetH = (primaryHsl.h + hueShift + 360) % 360;
            // 稍微提升一点亮色模式下的饱和度，让颜色更通透
            const targetS = colors.isDark ? primaryHsl.s : Math.min(1, primaryHsl.s * 1.2);
            
            const cloudRgb = hslToRgb(targetH, targetS, primaryHsl.l);
            const r = cloudRgb.r;
            const g = cloudRgb.g;
            const b = cloudRgb.b;

            // 动态透明度
            const breathOpacity = 0.7 + Math.sin(cloud.phase * 1.5) * 0.3;
            const dynamicOpacity = cloud.opacity * breathOpacity;

            // 统一渲染逻辑：使用指数衰减生成超平滑渐变
            const nebula = ctx.createRadialGradient(
                cloud.x, cloud.y, 0,
                cloud.x, cloud.y, currentRadius
            );

            // 根据模式调整透明度因子
            // 亮色模式下，云层稍微淡一点，避免看起来脏
            const opacityMultiplier = colors.isDark ? 1.0 : 0.6;
            const finalOpacity = dynamicOpacity * opacityMultiplier;

            // 性能优化：大幅减少渐变色阶数量 (40 -> 6)
            const numStops = 6;
            for (let i = 0; i <= numStops; i++) {
                const t = i / numStops; // 0 到 1
                // 指数衰减：alpha = e^(-k*t^2) 产生柔和的高斯式衰减
                const falloff = Math.exp(-4 * t * t);
                const alpha = finalOpacity * falloff;
                nebula.addColorStop(t, `rgba(${r}, ${g}, ${b}, ${alpha})`);
            }

            ctx.fillStyle = nebula;
            ctx.fillRect(0, 0, width, height);
        }

        // 性能优化：移除背景粒子与连线绘制，因为背景已被高斯模糊，细节不可见

        // 噪声层已移除 - 原本会造成"抹布/磨砂"效果

        rafId = requestAnimationFrame(draw);
    }

    // ========== 鼠标处理 ==========
    function updateMouse(x, y, vx, vy) {
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