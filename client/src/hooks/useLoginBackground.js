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
    let particles = [];
    let nebulaClouds = [];
    let width = 0;
    let height = 0;
    let mouse = { x: -9999, y: -9999, vx: 0, vy: 0 };
    let time = 0;

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

    // ========== 星云云层 ==========
    function createNebulaClouds() {
        nebulaClouds = [];
        const count = 5 + Math.floor(Math.random() * 3);
        for (let i = 0; i < count; i++) {
            nebulaClouds.push({
                // 当前位置（会真正漂移）
                x: rand(-200, width + 200),
                y: rand(-200, height + 200),
                // 漂移速度（非常缓慢）
                driftVx: rand(-0.15, 0.15),
                driftVy: rand(-0.12, 0.12),
                // 更大的半径，让融合更自然
                radius: rand(400, 700),
                // 呼吸相位
                phase: rand(0, Math.PI * 2),
                phaseSpeed: rand(0.0008, 0.002),
                // 更低的透明度，避免明显边缘
                opacity: rand(0.012, 0.03),
                // 颜色混合
                colorMixBase: rand(0, 1),
                colorMixSpeed: rand(0.003, 0.01)
            });
        }
    }

    // ========== 星辰粒子 ==========
    function createParticles(count) {
        particles = Array.from({ length: count }, () => ({
            x: rand(0, width),
            y: rand(0, height),
            vx: rand(-0.06, 0.06),
            vy: rand(-0.06, 0.06),
            r: rand(0.6, 2.0),
            alpha: rand(0.3, 0.8),
            twinklePhase: rand(0, Math.PI * 2),
            twinkleSpeed: rand(0.015, 0.04)
        }));
    }

    function resize() {
        const c = bgCanvas.value;
        if (!c) return;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        width = c.clientWidth;
        height = c.clientHeight;
        c.width = Math.floor(width * dpr);
        c.height = Math.floor(height * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        createParticles(Math.floor((width * height) / 20000));
        createNebulaClouds();
    }

    // ========== 主绘制循环 ==========
    function draw() {
        time += 0.008;
        const colors = getThemeColors();
        const primaryRgb = hexToRgb(colors.primary);
        const accentRgb = hexToRgb(colors.accent || colors.primary);
        
        // 背景渐变 - 根据亮暗模式调整
        if (colors.isDark) {
            // 暗色模式：深邃的星空渐变
            const g = ctx.createRadialGradient(
                width * 0.3, height * 0.3, 0,
                width * 0.5, height * 0.5, Math.max(width, height)
            );
            g.addColorStop(0, `rgba(${primaryRgb.r}, ${primaryRgb.g}, ${primaryRgb.b}, 0.06)`);
            g.addColorStop(0.4, 'rgba(9, 11, 16, 1)');
            g.addColorStop(1, 'rgba(5, 7, 12, 1)');
            ctx.fillStyle = g;
        } else {
            // 亮色模式：柔和的晨曦渐变
            const g = ctx.createLinearGradient(0, 0, width, height);
            g.addColorStop(0, `rgba(${primaryRgb.r}, ${primaryRgb.g}, ${primaryRgb.b}, 0.05)`);
            g.addColorStop(0.5, '#f9fbf9');
            g.addColorStop(1, '#f2f7f2');
            ctx.fillStyle = g;
        }
        ctx.fillRect(0, 0, width, height);

        // ===== 绘制真正漫游的星云云层 =====
        for (const cloud of nebulaClouds) {
            cloud.phase += cloud.phaseSpeed;
            
            // ===== 真正的漂移：更新位置 =====
            cloud.x += cloud.driftVx;
            cloud.y += cloud.driftVy;
            
            // 边界循环：云团离开屏幕后从另一侧重新进入
            const margin = cloud.radius * 0.8;
            if (cloud.x < -margin) {
                cloud.x = width + margin * 0.5;
                cloud.y = rand(0, height);
            }
            if (cloud.x > width + margin) {
                cloud.x = -margin * 0.5;
                cloud.y = rand(0, height);
            }
            if (cloud.y < -margin) {
                cloud.y = height + margin * 0.5;
                cloud.x = rand(0, width);
            }
            if (cloud.y > height + margin) {
                cloud.y = -margin * 0.5;
                cloud.x = rand(0, width);
            }
            
            // 动态半径：呼吸效果
            const breathScale = 1 + Math.sin(cloud.phase) * 0.15;
            const currentRadius = cloud.radius * breathScale;
            
            // 动态颜色混合
            const colorMix = 0.5 + 0.5 * Math.sin(time * cloud.colorMixSpeed + cloud.colorMixBase * Math.PI * 2);
            const r = Math.round(primaryRgb.r * (1 - colorMix) + accentRgb.r * colorMix);
            const g = Math.round(primaryRgb.g * (1 - colorMix) + accentRgb.g * colorMix);
            const b = Math.round(primaryRgb.b * (1 - colorMix) + accentRgb.b * colorMix);
            
            // 动态透明度
            const breathOpacity = 0.7 + Math.sin(cloud.phase * 1.5) * 0.3;
            const dynamicOpacity = cloud.opacity * breathOpacity;
            
            if (colors.isDark) {
                // 暗色模式：超柔和渐变（更多色阶，避免边缘可见）
                const nebula = ctx.createRadialGradient(
                    cloud.x, cloud.y, 0,
                    cloud.x, cloud.y, currentRadius
                );
                // 更多色阶实现超平滑过渡
                nebula.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${dynamicOpacity * 0.9})`);
                nebula.addColorStop(0.1, `rgba(${r}, ${g}, ${b}, ${dynamicOpacity * 0.7})`);
                nebula.addColorStop(0.25, `rgba(${r}, ${g}, ${b}, ${dynamicOpacity * 0.5})`);
                nebula.addColorStop(0.4, `rgba(${r}, ${g}, ${b}, ${dynamicOpacity * 0.3})`);
                nebula.addColorStop(0.55, `rgba(${r}, ${g}, ${b}, ${dynamicOpacity * 0.18})`);
                nebula.addColorStop(0.7, `rgba(${r}, ${g}, ${b}, ${dynamicOpacity * 0.08})`);
                nebula.addColorStop(0.85, `rgba(${r}, ${g}, ${b}, ${dynamicOpacity * 0.02})`);
                nebula.addColorStop(1, 'transparent');
                
                ctx.fillStyle = nebula;
                ctx.fillRect(0, 0, width, height);
            } else {
                // 亮色模式：光雾
                const lightFog = ctx.createRadialGradient(
                    cloud.x, cloud.y, 0,
                    cloud.x, cloud.y, currentRadius * 1.2
                );
                const lightOpacity = dynamicOpacity * 0.6;
                lightFog.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${lightOpacity * 0.8})`);
                lightFog.addColorStop(0.2, `rgba(${r}, ${g}, ${b}, ${lightOpacity * 0.5})`);
                lightFog.addColorStop(0.4, `rgba(${r}, ${g}, ${b}, ${lightOpacity * 0.25})`);
                lightFog.addColorStop(0.6, `rgba(${r}, ${g}, ${b}, ${lightOpacity * 0.1})`);
                lightFog.addColorStop(0.8, `rgba(${r}, ${g}, ${b}, ${lightOpacity * 0.03})`);
                lightFog.addColorStop(1, 'transparent');
                
                ctx.fillStyle = lightFog;
                ctx.fillRect(0, 0, width, height);
            }
        }

        // ===== 绘制星辰粒子 =====
        for (const p of particles) {
            // 鼠标交互 - 微妙的斥力
            const dx = p.x - mouse.x;
            const dy = p.y - mouse.y;
            const dist2 = dx * dx + dy * dy;
            if (dist2 < 100 * 100) {
                const f = 50 / (dist2 + 80);
                p.vx += dx * f * 0.006;
                p.vy += dy * f * 0.006;
            }
            
            p.x += p.vx;
            p.y += p.vy;
            p.vx *= 0.996;
            p.vy *= 0.996;
            
            // 边界循环
            if (p.x < -5) p.x = width + 5;
            if (p.x > width + 5) p.x = -5;
            if (p.y < -5) p.y = height + 5;
            if (p.y > height + 5) p.y = -5;
            
            // 闪烁效果
            p.twinklePhase += p.twinkleSpeed;
            const twinkle = 0.5 + Math.sin(p.twinklePhase) * 0.5;
            const currentAlpha = p.alpha * twinkle;
            
            if (colors.isDark) {
                // 暗色模式：带光晕的星辰
                const starGlow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 3);
                starGlow.addColorStop(0, `rgba(${primaryRgb.r}, ${primaryRgb.g}, ${primaryRgb.b}, ${currentAlpha * 0.8})`);
                starGlow.addColorStop(0.4, `rgba(${primaryRgb.r}, ${primaryRgb.g}, ${primaryRgb.b}, ${currentAlpha * 0.2})`);
                starGlow.addColorStop(1, 'transparent');
                ctx.fillStyle = starGlow;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r * 3, 0, Math.PI * 2);
                ctx.fill();
                
                // 核心亮点
                ctx.fillStyle = `rgba(255, 255, 255, ${currentAlpha * 0.95})`;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r * 0.5, 0, Math.PI * 2);
                ctx.fill();
            } else {
                // 亮色模式：柔和的光点
                const dotGlow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 2);
                dotGlow.addColorStop(0, `rgba(${primaryRgb.r}, ${primaryRgb.g}, ${primaryRgb.b}, ${currentAlpha * 0.5})`);
                dotGlow.addColorStop(1, 'transparent');
                ctx.fillStyle = dotGlow;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r * 2, 0, Math.PI * 2);
                ctx.fill();
            }
        }

        // ===== 粒子连线（更微妙） =====
        if (colors.isDark) {
            ctx.strokeStyle = `rgba(${primaryRgb.r}, ${primaryRgb.g}, ${primaryRgb.b}, 0.06)`;
            ctx.lineWidth = 0.5;
            for (let i = 0; i < particles.length; i++) {
                for (let j = i + 1; j < particles.length; j++) {
                    const a = particles[i], b = particles[j];
                    const dx = a.x - b.x, dy = a.y - b.y;
                    const d2 = dx * dx + dy * dy;
                    if (d2 < 70 * 70) {
                        ctx.globalAlpha = (1 - d2 / (70 * 70)) * 0.4;
                        ctx.beginPath();
                        ctx.moveTo(a.x, a.y);
                        ctx.lineTo(b.x, b.y);
                        ctx.stroke();
                    }
                }
            }
            ctx.globalAlpha = 1;
        }

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
            createParticles(Math.floor((width * height) / 20000));
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