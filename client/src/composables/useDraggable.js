/**
 * 拖拽功能 Composable
 * 从 GlobalChatFloat.vue 提取的拖拽逻辑（支持桌面端和移动端长按拖拽）
 */
import { reactive, ref, onMounted, onUnmounted } from 'vue';

const POS_STORAGE_KEY = 'spark_chat_float_pos_v2';
const LONG_PRESS_DELAY = 200;

export function useDraggable(options = {}) {
    const {
        isMobile = ref(false),
        onDragEnd = null,
        getExpanded = () => false,
        getPanelHeight = () => 64
    } = options;

    const rootEl = ref(null);
    const pos = reactive({ right: 16, top: 80 });
    const drag = reactive({
        isDragging: false,
        startX: 0,
        startY: 0,
        startLeft: 0,
        startTop: 0,
        moved: false,
    });

    const isLongPressing = ref(false);
    let longPressTimer = null;
    let touchCancelMoveHandler = null;

    function getCurrentSize() {
        const el = rootEl.value;
        if (!el) return { w: 52, h: 52 };
        const rect = el.getBoundingClientRect();
        return { w: rect.width || 52, h: rect.height || 52 };
    }

    function persistPos() {
        try {
            localStorage.setItem(POS_STORAGE_KEY, JSON.stringify({ right: pos.right, top: pos.top }));
        } catch {
            // ignore
        }
    }

    function loadPos() {
        try {
            const raw = localStorage.getItem(POS_STORAGE_KEY);
            if (raw) {
                const v = JSON.parse(raw);
                if (typeof v?.right === 'number' && typeof v?.top === 'number') {
                    pos.right = v.right;
                    pos.top = v.top;
                    return;
                }
            }
        } catch {
            // ignore
        }

        pos.right = 16;
        if (isMobile.value) {
            pos.top = Math.round(window.innerHeight * 0.68);
        } else {
            pos.top = 80;
        }
    }

    function startDrag(e) {
        if (e.type === 'mousedown' && e.button !== 0) return;

        const clientX = e.type.startsWith('touch') ? e.touches[0].clientX : e.clientX;
        const clientY = e.type.startsWith('touch') ? e.touches[0].clientY : e.clientY;

        drag.startX = clientX;
        drag.startY = clientY;
        drag.startLeft = 0;
        drag.startTop = 0;
        drag.moved = false;

        const el = rootEl.value;
        if (el) {
            const rect = el.getBoundingClientRect();
            drag.startLeft = rect.left;
            drag.startTop = rect.top;
        }

        if (e.type === 'mousedown') {
            drag.isDragging = true;
            document.addEventListener('mousemove', onDragMove);
            document.addEventListener('mouseup', stopDrag, { once: true });
        } else {
            drag.isDragging = false;
            isLongPressing.value = false;

            if (longPressTimer) {
                clearTimeout(longPressTimer);
                longPressTimer = null;
            }

            const cancelLongPress = (ev) => {
                const t = ev.touches?.[0];
                if (!t) return;
                const dx = t.clientX - drag.startX;
                const dy = t.clientY - drag.startY;
                if (Math.abs(dx) > 6 || Math.abs(dy) > 6) {
                    if (longPressTimer) {
                        clearTimeout(longPressTimer);
                        longPressTimer = null;
                    }
                    isLongPressing.value = false;
                    if (touchCancelMoveHandler) {
                        document.removeEventListener('touchmove', touchCancelMoveHandler);
                        touchCancelMoveHandler = null;
                    }
                }
            };
            touchCancelMoveHandler = cancelLongPress;
            document.addEventListener('touchmove', cancelLongPress, { passive: true });
            document.addEventListener('touchend', stopDrag, { once: true });
            document.addEventListener('touchcancel', stopDrag, { once: true });

            longPressTimer = setTimeout(() => {
                longPressTimer = null;
                isLongPressing.value = true;
                drag.isDragging = true;
                if (navigator.vibrate) navigator.vibrate(10);
                if (touchCancelMoveHandler) {
                    document.removeEventListener('touchmove', touchCancelMoveHandler);
                    touchCancelMoveHandler = null;
                }
                document.addEventListener('touchmove', onDragMove, { passive: false });
            }, LONG_PRESS_DELAY);
        }
    }

    function onDragMove(e) {
        const clientX = e.type.startsWith('touch') ? e.touches[0].clientX : e.clientX;
        const clientY = e.type.startsWith('touch') ? e.touches[0].clientY : e.clientY;

        const dx = clientX - drag.startX;
        const dy = clientY - drag.startY;

        if (!drag.isDragging) return;

        if (!drag.moved && (Math.abs(dx) > 3 || Math.abs(dy) > 3)) {
            drag.moved = true;
        }

        if (drag.moved && e.cancelable) {
            e.preventDefault();
        }

        const el = rootEl.value;
        const rect = el ? el.getBoundingClientRect() : { width: 52, height: 52 };
        const nextLeft = drag.startLeft + dx;
        const nextRight = window.innerWidth - (nextLeft + (rect.width || 52));
        pos.right = nextRight;

        let newTop = drag.startTop + dy;
        const minTop = 0;
        newTop = Math.max(minTop, newTop);

        const currentHeight = getExpanded() ? getPanelHeight() : 64;
        const maxTop = Math.max(minTop, window.innerHeight - currentHeight);
        newTop = Math.min(maxTop, newTop);

        pos.top = newTop;

        // 水平边界限制
        const { w, h } = getCurrentSize();
        const maxRight = Math.max(8, window.innerWidth - w - 8);
        pos.right = Math.min(Math.max(8, pos.right), maxRight);
    }

    function stopDrag(e) {
        if (longPressTimer) {
            clearTimeout(longPressTimer);
            longPressTimer = null;
        }
        isLongPressing.value = false;
        if (touchCancelMoveHandler) {
            document.removeEventListener('touchmove', touchCancelMoveHandler);
            touchCancelMoveHandler = null;
        }

        const wasDragging = drag.isDragging;
        drag.isDragging = false;

        if (e.type === 'mouseup') {
            document.removeEventListener('mousemove', onDragMove);
        } else {
            document.removeEventListener('touchmove', onDragMove);
            document.removeEventListener('touchcancel', stopDrag);
        }

        if (wasDragging) {
            persistPos();
            if (onDragEnd) onDragEnd();
        }

        setTimeout(() => { drag.moved = false; }, 0);
    }

    function clampIntoViewport() {
        const { w, h } = getCurrentSize();
        const maxRight = Math.max(8, window.innerWidth - w - 8);
        pos.right = Math.min(Math.max(8, pos.right), maxRight);
    }

    onMounted(() => {
        loadPos();
    });

    onUnmounted(() => {
        document.removeEventListener('mousemove', onDragMove);
        if (longPressTimer) clearTimeout(longPressTimer);
    });

    return {
        rootEl,
        pos,
        drag,
        isLongPressing,
        startDrag,
        stopDrag,
        persistPos,
        loadPos,
        clampIntoViewport,
        getCurrentSize
    };
}
