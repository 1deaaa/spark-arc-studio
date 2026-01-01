/**
 * useLoginBackground - 登录页背景动画 Composable
 * 
 * 功能：
 * - 背景粒子物理模拟
 * - 流星生成与渲染
 * - 背景渐变绘制
 * - resize 处理
 */

import { ref, onMounted, onBeforeUnmount } from 'vue';

export function useLoginBackground() {
    // ========== 响应式状态 ==========
    const bgCanvas = ref(null);

    // ========== 内部状态 ==========
    let ctx = null;
    let rafId = null;
    let particles = [];
    let width = 0;
    let height = 0;
    let mouse = { x: -9999, y: -9999, vx: 0, vy: 0 };
    let meteors = [];

    // ========== 工具函数 ==========
    function rand(min, max) {
        return Math.random() * (max - min) + min;
    }

    function createParticles(count) {
        particles = Array.from({ length: count }, () => ({
            x: rand(0, width),
            y: rand(0, height),
            vx: rand(-0.3, 0.3),
            vy: rand(-0.3, 0.3),
            r: rand(1.2, 2.8),
            alpha: rand(0.3, 0.9)
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
        createParticles(Math.floor((width * height) / 14000));
    }

    // ========== 流星功能 ==========
    function spawnMeteor() {
        let x = width * (0.55 + Math.random() * 0.4);
        let y = -40 - Math.random() * 60;
        const speed = 2.8 + Math.random() * 2.4;
        const dir = (Math.PI / 2) + 0.35 + (Math.random() - 0.5) * 0.3;
        const vx = Math.cos(dir) * speed;
        const vy = Math.sin(dir) * speed;
        const len = 100 + Math.random() * 160;
        const life = Math.ceil((height + 140) / Math.abs(vy)) + 40;
        const thickness = 1.6 + Math.random() * 2.0;
        const hue = 210 + Math.random() * 40;
        meteors.push({ x, y, vx, vy, len, life, thickness, hue });
    }

    function drawMeteors() {
        if (meteors.length < 24 && Math.random() < 0.1) spawnMeteor();
        const toRemove = [];
        for (let i = 0; i < meteors.length; i++) {
            const m = meteors[i];
            m.x += m.vx;
            m.y += m.vy;
            m.life--;

            ctx.save();
            const speed = Math.hypot(m.vx, m.vy) || 1;
            const tailX = m.x - m.vx * (m.len / speed);
            const tailY = m.y - m.vy * (m.len / speed);
            const grd = ctx.createLinearGradient(m.x, m.y, tailX, tailY);
            grd.addColorStop(0, `hsla(${m.hue}, 90%, 75%, 0.9)`);
            grd.addColorStop(1, 'rgba(255,255,255,0)');
            ctx.strokeStyle = grd;
            ctx.lineWidth = m.thickness;
            ctx.beginPath();
            ctx.moveTo(m.x, m.y);
            ctx.lineTo(tailX, tailY);
            ctx.stroke();

            const head = ctx.createRadialGradient(m.x, m.y, 0, m.x, m.y, 6);
            head.addColorStop(0, `hsla(${m.hue}, 90%, 75%, 0.6)`);
            head.addColorStop(1, 'rgba(255,255,255,0)');
            ctx.fillStyle = head;
            ctx.beginPath();
            ctx.arc(m.x, m.y, 6, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();

            if (m.life <= 0 || m.x < -200 || m.y > height + 200) toRemove.push(i);
        }
        for (let i = toRemove.length - 1; i >= 0; i--) meteors.splice(toRemove[i], 1);
    }

    // ========== 主绘制循环 ==========
    function draw() {
        // 背景渐变
        const g = ctx.createLinearGradient(0, 0, width, height);
        g.addColorStop(0, '#eef3fb');
        g.addColorStop(1, '#f8fbff');
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, width, height);

        // 粒子
        for (const p of particles) {
            const dx = p.x - mouse.x, dy = p.y - mouse.y;
            const dist2 = dx * dx + dy * dy;
            if (dist2 < 160 * 160) {
                const f = 120 / (dist2 + 40);
                p.vx += dx * f * 0.02;
                p.vy += dy * f * 0.02;
            }
            p.x += p.vx;
            p.y += p.vy;
            p.vx *= 0.985;
            p.vy *= 0.985;
            if (p.x < -10) p.x = width + 10;
            if (p.x > width + 10) p.x = -10;
            if (p.y < -10) p.y = height + 10;
            if (p.y > height + 10) p.y = -10;

            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(69, 131, 229, ${p.alpha})`;
            ctx.fill();
        }

        // 粒子连线
        ctx.strokeStyle = 'rgba(74,144,226,0.18)';
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const a = particles[i], b = particles[j];
                const dx = a.x - b.x, dy = a.y - b.y;
                const d2 = dx * dx + dy * dy;
                if (d2 < 120 * 120) {
                    ctx.globalAlpha = 1 - d2 / (120 * 120);
                    ctx.beginPath();
                    ctx.moveTo(a.x, a.y);
                    ctx.lineTo(b.x, b.y);
                    ctx.stroke();
                }
            }
        }
        ctx.globalAlpha = 1;

        // 流星
        drawMeteors();

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

    // ========== 导出 ==========
    return {
        bgCanvas,
        init,
        destroy,
        updateMouse,
        resetMouse,
    };
}
