/**
 * useLoginFx - 登录页 FX 特效 Composable
 * 
 * 功能：
 * - 几何形状拖尾粒子（星形、三角形、菱形等）
 * - Emoji 爆炸效果
 * - 鼠标拖尾光标
 * - 点击爆发效果
 */

import { ref } from 'vue';

export function useLoginFx() {
    // ========== 响应式状态 ==========
    const fxCanvas = ref(null);

    // ========== 内部状态 ==========
    let fxCtx = null;
    let fxW = 0;
    let fxH = 0;
    let fxRafId = null;
    let sprayEnergy = 0;
    let fxMouseX = -9999;
    let fxMouseY = -9999;
    let mouseVx = 0;
    let mouseVy = 0;

    const trail = [];
    const emojiExplosion = [];
    const EMOJI_LIST = ['💥', '✨', '🌟', '💫', '🚀', '🎉', '🎊', '💡', '🖋️', '📜', '📖', '🎨', '🎭'];
    const MAX_EMOJIS = 80;
    const emojiCache = new Map();

    // ========== 工具函数 ==========
    function randInt(min, max) {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }

    function pick(arr) {
        return arr[Math.floor(Math.random() * arr.length)];
    }

    function hsl(h, s, l, a = 1) {
        return `hsla(${h},${s}%,${l}%,${a})`;
    }

    // ========== 形状绘制 ==========
    function drawStarShape(ctx, rOuter, rInner, points = 5) {
        ctx.beginPath();
        const step = Math.PI / points;
        for (let i = 0; i < 2 * points; i++) {
            const r = i % 2 === 0 ? rOuter : rInner;
            const ang = i * step - Math.PI / 2;
            const x = Math.cos(ang) * r;
            const y = Math.sin(ang) * r;
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.closePath();
    }

    function drawPolygon(ctx, r, sides = 5) {
        ctx.beginPath();
        for (let i = 0; i < sides; i++) {
            const ang = (i / sides) * Math.PI * 2 - Math.PI / 2;
            const x = Math.cos(ang) * r;
            const y = Math.sin(ang) * r;
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.closePath();
    }

    function pathStar(ctx, rOuter, rInner, points = 5) {
        ctx.beginPath();
        const step = Math.PI / points;
        for (let i = 0; i < 2 * points; i++) {
            const r = i % 2 === 0 ? rOuter : rInner;
            const ang = i * step - Math.PI / 2;
            const x = Math.cos(ang) * r;
            const y = Math.sin(ang) * r;
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.closePath();
    }

    function pathTriangle(ctx, r) {
        ctx.beginPath();
        ctx.moveTo(0, -r);
        ctx.lineTo(r * 0.95, r * 0.82);
        ctx.lineTo(-r * 0.95, r * 0.82);
        ctx.closePath();
    }

    // ========== Emoji 预渲染 ==========
    function getPrerenderedEmoji(emoji, size) {
        const sizeKey = Math.round(size);
        const cacheKey = `${emoji}_${sizeKey}`;
        if (emojiCache.has(cacheKey)) {
            return emojiCache.get(cacheKey);
        }

        const canvas = document.createElement('canvas');
        const dpr = window.devicePixelRatio || 1;
        const paddedSize = sizeKey + 4;
        canvas.width = paddedSize * dpr;
        canvas.height = paddedSize * dpr;
        const ctx = canvas.getContext('2d');
        if (!ctx) return null;

        ctx.scale(dpr, dpr);
        ctx.font = `${sizeKey}px "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", system-ui`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(emoji, paddedSize / 2, paddedSize / 2);

        emojiCache.set(cacheKey, canvas);
        if (emojiCache.size > 100) {
            const firstKey = emojiCache.keys().next().value;
            emojiCache.delete(firstKey);
        }
        return canvas;
    }

    // ========== 粒子生成 ==========
    function spawnParticles(cx, cy, vx, vy, n) {
        const palette = [
            '#5ec8ff', '#7aa6ff', '#b086ff', '#ff7ad1', '#ffd166', '#6df2c1', '#9effa3', '#ff9e7a', '#e6eeff'
        ];
        const dir = Math.atan2(vy, vx);
        for (let i = 0; i < n; i++) {
            const ang = dir + (Math.random() - 0.5) * 5;
            const speed = 0.45 + Math.random() * (1.0 + Math.min(4.5, Math.hypot(vx, vy) * 0.04));
            const spread = 3 + Math.random() * 18;
            const ox = Math.cos(ang) * spread + (Math.random() - 0.5) * 10;
            const oy = Math.sin(ang) * spread + (Math.random() - 0.5) * 10;

            const shapeRand = Math.random();
            let shape = 'star';
            if (shapeRand > 0.7 && shapeRand <= 0.8) shape = 'triangle';
            else if (shapeRand > 0.8 && shapeRand <= 0.88) shape = 'triangle-hollow';
            else if (shapeRand > 0.88 && shapeRand <= 0.94) shape = 'diamond';
            else if (shapeRand > 0.94 && shapeRand <= 0.98) shape = 'pentagon';
            else if (shapeRand > 0.98 && shapeRand <= 0.995) shape = 'star-hollow';
            else if (shapeRand > 0.995) shape = 'dot';

            const col = Math.random() < 0.2 ? hsl(randInt(190, 300), randInt(65, 85), randInt(55, 70), 0.9) : pick(palette);
            const size = 6 + Math.random() * 16;
            const life = 48 + Math.floor(Math.random() * 38);
            const omega = (Math.random() - 0.5) * 0.3;
            trail.push({
                x: cx + ox,
                y: cy + oy,
                vx: Math.cos(ang) * speed + (Math.random() - 0.5) * 0.6,
                vy: Math.sin(ang) * speed + (Math.random() - 0.5) * 0.6,
                alpha: 0.0,
                alphaT: 0.85,
                size,
                life,
                rot: Math.random() * Math.PI * 2,
                omega,
                shape,
                color: col,
                points: shape === 'star' ? pick([5, 5, 5, 6, 7]) : undefined,
            });
        }
        const MAX = 130;
        if (trail.length > MAX) trail.splice(0, trail.length - MAX);
    }

    function spawnParticlesRadial(cx, cy, n) {
        const palette = [
            '#5ec8ff', '#7aa6ff', '#b086ff', '#ff7ad1', '#ffd166', '#6df2c1', '#9effa3', '#ff9e7a', '#e6eeff'
        ];
        for (let i = 0; i < n; i++) {
            const ang = Math.random() * Math.PI * 2;
            const speed = 0.55 + Math.random() * 0.9;
            const ox = (Math.random() - 0.5) * 16;
            const oy = (Math.random() - 0.5) * 16;

            const shapeRand = Math.random();
            let shape = 'star';
            if (shapeRand > 0.7 && shapeRand <= 0.8) shape = 'triangle';
            else if (shapeRand > 0.8 && shapeRand <= 0.88) shape = 'triangle-hollow';
            else if (shapeRand > 0.88 && shapeRand <= 0.94) shape = 'diamond';
            else if (shapeRand > 0.94 && shapeRand <= 0.98) shape = 'pentagon';
            else if (shapeRand > 0.98 && shapeRand <= 0.995) shape = 'star-hollow';
            else if (shapeRand > 0.995) shape = 'dot';

            const col = Math.random() < 0.2 ? hsl(randInt(190, 300), randInt(65, 85), randInt(55, 70), 0.9) : pick(palette);
            const size = 6 + Math.random() * 14;
            const life = 42 + Math.floor(Math.random() * 34);
            const omega = (Math.random() - 0.5) * 0.25;
            trail.push({
                x: cx + ox,
                y: cy + oy,
                vx: Math.cos(ang) * speed,
                vy: Math.sin(ang) * speed,
                alpha: 0.0,
                alphaT: 0.75,
                size,
                life,
                rot: Math.random() * Math.PI * 2,
                omega,
                shape,
                color: col,
                points: shape === 'star' ? pick([5, 5, 6]) : undefined,
            });
        }
        const MAX = 120;
        if (trail.length > MAX) trail.splice(0, trail.length - MAX);
    }

    function spawnEmojiExplosion(x, y) {
        const count = 20 + Math.floor(Math.random() * 15);
        for (let i = 0; i < count; i++) {
            const angle = Math.random() * Math.PI * 2;
            const speed = 2 + Math.random() * 5;
            emojiExplosion.push({
                x,
                y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed - 3,
                emoji: pick(EMOJI_LIST),
                size: 16 + Math.random() * 16,
                life: 70 + Math.random() * 50,
                rotation: Math.random() * Math.PI * 2,
                omega: (Math.random() - 0.5) * 0.4
            });
        }
        if (emojiExplosion.length > MAX_EMOJIS) {
            emojiExplosion.splice(0, emojiExplosion.length - MAX_EMOJIS);
        }
    }

    // ========== Emoji 更新与绘制 ==========
    function updateAndDrawEmojis() {
        if (emojiExplosion.length === 0) return;
        const gravity = 0.12;
        const friction = 0.99;
        fxCtx.textAlign = 'center';
        fxCtx.textBaseline = 'middle';
        for (let i = emojiExplosion.length - 1; i >= 0; i--) {
            const p = emojiExplosion[i];
            p.vy += gravity;
            p.vx *= friction;
            p.vy *= friction;
            p.x += p.vx;
            p.y += p.vy;
            p.life--;
            p.rotation += p.omega;
            if (p.life <= 0) {
                emojiExplosion.splice(i, 1);
                continue;
            }
            const alpha = Math.min(1, p.life / 30);
            fxCtx.save();
            fxCtx.translate(p.x, p.y);
            fxCtx.rotate(p.rotation);
            const prerendered = getPrerenderedEmoji(p.emoji, p.size);
            if (prerendered) {
                fxCtx.globalAlpha = alpha;
                const drawSize = p.size;
                fxCtx.drawImage(prerendered, -drawSize / 2, -drawSize / 2, drawSize, drawSize);
            }
            fxCtx.restore();
        }
    }

    // ========== 主绘制循环 ==========
    function drawFx() {
        fxCtx.clearRect(0, 0, fxW, fxH);

        const emitCapPerFrame = 8;
        const emitCount = Math.min(emitCapPerFrame, Math.floor(sprayEnergy));
        if (emitCount > 0 && fxMouseX > -999 && fxMouseY > -999) {
            const spd = Math.hypot(mouseVx, mouseVy);
            if (spd < 0.25) {
                spawnParticlesRadial(fxMouseX, fxMouseY, emitCount);
            } else {
                spawnParticles(fxMouseX, fxMouseY, mouseVx, mouseVy, emitCount);
            }
            sprayEnergy -= emitCount;
        }

        if (fxMouseX > -999 && fxMouseY > -999) {
            sprayEnergy = Math.min(90, sprayEnergy + 0.28);
        }

        // 更新与绘制拖尾
        for (const t of trail) {
            t.life -= 1;
            t.alpha += (t.alphaT - t.alpha) * 0.25;
            t.alphaT *= 0.988;
            t.size *= 0.992;
            t.vx *= 0.970;
            t.vy *= 0.970;
            t.x += t.vx;
            t.y += t.vy;
            t.rot += t.omega;
        }
        while (trail.length && (trail[0].alpha < 0.03 || trail[0].size < 1.5 || trail[0].life <= 0)) trail.shift();

        const prevComp = fxCtx.globalCompositeOperation;
        fxCtx.globalCompositeOperation = 'source-over';

        for (let i = 0; i < trail.length; i++) {
            const t = trail[i];
            fxCtx.save();
            fxCtx.translate(t.x, t.y);
            fxCtx.rotate(t.rot);
            fxCtx.globalAlpha = t.alpha;

            const s = t.size;
            const color = t.color;

            switch (t.shape) {
                case 'star': {
                    fxCtx.fillStyle = color;
                    drawStarShape(fxCtx, s, s * 0.45, t.points || 5);
                    fxCtx.fill();
                    break;
                }
                case 'star-hollow': {
                    fxCtx.strokeStyle = color;
                    fxCtx.lineWidth = Math.max(0.8, Math.min(1.3, s * 0.07));
                    pathStar(fxCtx, s, s * 0.45, t.points || 5);
                    fxCtx.stroke();
                    break;
                }
                case 'triangle': {
                    fxCtx.fillStyle = color;
                    fxCtx.beginPath();
                    fxCtx.moveTo(0, -s);
                    fxCtx.lineTo(s * 0.9, s * 0.8);
                    fxCtx.lineTo(-s * 0.9, s * 0.8);
                    fxCtx.closePath();
                    fxCtx.fill();
                    break;
                }
                case 'triangle-hollow': {
                    fxCtx.strokeStyle = color;
                    fxCtx.lineWidth = Math.max(0.8, Math.min(1.3, s * 0.07));
                    pathTriangle(fxCtx, s);
                    fxCtx.stroke();
                    break;
                }
                case 'diamond': {
                    fxCtx.strokeStyle = color;
                    fxCtx.lineWidth = Math.max(0.8, Math.min(1.2, s * 0.07));
                    fxCtx.beginPath();
                    fxCtx.moveTo(0, -s);
                    fxCtx.lineTo(s, 0);
                    fxCtx.lineTo(0, s);
                    fxCtx.lineTo(-s, 0);
                    fxCtx.closePath();
                    fxCtx.stroke();
                    break;
                }
                case 'pentagon': {
                    fxCtx.fillStyle = color;
                    drawPolygon(fxCtx, s, 5);
                    fxCtx.fill();
                    break;
                }
                default: {
                    fxCtx.fillStyle = color;
                    fxCtx.beginPath();
                    fxCtx.arc(0, 0, s * 0.35, 0, Math.PI * 2);
                    fxCtx.fill();
                }
            }
            fxCtx.restore();
        }

        fxCtx.globalCompositeOperation = prevComp;

        updateAndDrawEmojis();

        // 绘制笔形光标
        if (fxMouseX > -999 && fxMouseY > -999) {
            fxCtx.save();
            fxCtx.translate(fxMouseX, fxMouseY);
            fxCtx.font = '28px "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", system-ui';
            fxCtx.textAlign = 'center';
            fxCtx.textBaseline = 'middle';
            fxCtx.fillText('🖊️', 0, 0);
            fxCtx.restore();
        }

        fxRafId = requestAnimationFrame(drawFx);
    }

    // ========== resize 处理 ==========
    function resizeFx() {
        const c = fxCanvas.value;
        if (!c) return;
        const dpr = Math.min(window.devicePixelRatio || 1, 1.25);
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
        sprayEnergy = Math.min(120, sprayEnergy + Math.min(10, 1.8 + spd * 0.09));
        return { x, y, vx: mouseVx, vy: mouseVy };
    }

    function handleClick(e, cardElement) {
        if (e.target.closest('.card') || (cardElement && cardElement.contains(e.target))) return;
        const fxRect = fxCanvas.value.getBoundingClientRect();
        const x = e.clientX - fxRect.left;
        const y = e.clientY - fxRect.top;
        spawnEmojiExplosion(x, y);
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
