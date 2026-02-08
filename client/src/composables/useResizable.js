/**
 * 缩放功能 Composable
 * 从 GlobalChatFloat.vue 提取的面板尺寸调整逻辑
 */
import { reactive, ref, onUnmounted } from 'vue';

const SIZE_STORAGE_KEY = 'spark_chat_float_size_v1';
const DEFAULT_PANEL_WIDTH = 640;
const DEFAULT_PANEL_HEIGHT = 500;
const MIN_PANEL_WIDTH = 360;
const MIN_PANEL_HEIGHT = 300;
const MAX_PANEL_WIDTH = 1200;
const MAX_PANEL_HEIGHT = 2000;

export function useResizable(options = {}) {
    const {
        pos = reactive({ right: 16, top: 80 }),
        isMobile = ref(false),
        onResizeEnd = null
    } = options;

    const panelSize = reactive({ width: DEFAULT_PANEL_WIDTH, height: DEFAULT_PANEL_HEIGHT });
    const fitOffset = ref(0);
    const resize = reactive({
        isResizing: false,
        startX: 0,
        startY: 0,
        startWidth: 0,
        startHeight: 0,
        startRight: 0,
        startTop: 0,
    });

    let isAdjustingLayout = false;
    let adjustFitRAF = null;

    function persistSize() {
        try {
            localStorage.setItem(SIZE_STORAGE_KEY, JSON.stringify({ width: panelSize.width, height: panelSize.height }));
        } catch {
            // ignore
        }
    }

    function loadSize() {
        try {
            const raw = localStorage.getItem(SIZE_STORAGE_KEY);
            if (raw) {
                const v = JSON.parse(raw);
                if (typeof v?.width === 'number' && typeof v?.height === 'number') {
                    panelSize.width = Math.min(MAX_PANEL_WIDTH, Math.max(MIN_PANEL_WIDTH, v.width));
                    panelSize.height = Math.min(MAX_PANEL_HEIGHT, Math.max(MIN_PANEL_HEIGHT, v.height));
                    return;
                }
            }
        } catch {
            // ignore
        }
        panelSize.width = DEFAULT_PANEL_WIDTH;
        panelSize.height = DEFAULT_PANEL_HEIGHT;
    }

    function getMaxAvailableHeight() {
        const viewportHeight = window.innerHeight;
        const minTopMargin = 8;
        const bottomMargin = 8;
        return viewportHeight - minTopMargin - bottomMargin;
    }

    function ensurePanelFitsViewport() {
        if (isMobile.value) {
            fitOffset.value = 0;
            return;
        }

        const viewportHeight = window.innerHeight;
        const bottomMargin = 0;
        const topMargin = 0;
        const currentPanelHeight = panelSize.height;

        const panelBottom = pos.top + currentPanelHeight;
        const maxBottom = viewportHeight - bottomMargin;

        if (panelBottom > maxBottom) {
            const overflow = panelBottom - maxBottom;
            const newTop = pos.top - overflow;
            if (newTop >= topMargin) {
                fitOffset.value = -overflow;
            } else {
                const maxPossibleHeight = viewportHeight - topMargin - bottomMargin;
                if (maxPossibleHeight >= MIN_PANEL_HEIGHT) {
                    panelSize.height = Math.max(MIN_PANEL_HEIGHT, maxPossibleHeight);
                    fitOffset.value = topMargin - pos.top;
                } else {
                    panelSize.height = MIN_PANEL_HEIGHT;
                    fitOffset.value = Math.max(topMargin - pos.top, -(viewportHeight - MIN_PANEL_HEIGHT) / 2);
                }
            }
        } else {
            fitOffset.value = 0;
        }
    }

    function computeFitOffset(h) {
        const maxTop = Math.max(0, window.innerHeight - h);
        return pos.top > maxTop ? maxTop - pos.top : 0;
    }

    function adjustFitSync() {
        ensurePanelFitsViewport();
    }

    function adjustFitAsync(isDragging = false) {
        if (isDragging || resize.isResizing || isAdjustingLayout) return;

        if (adjustFitRAF) {
            cancelAnimationFrame(adjustFitRAF);
        }
        adjustFitRAF = requestAnimationFrame(() => {
            adjustFitRAF = null;
            if (isDragging || resize.isResizing || isAdjustingLayout) return;

            isAdjustingLayout = true;
            ensurePanelFitsViewport();
            setTimeout(() => { isAdjustingLayout = false; }, 50);
        });
    }

    function adjustFit(isDragging = false) {
        if (isMobile.value) {
            fitOffset.value = 0;
            return;
        }

        if (isDragging || resize.isResizing) {
            adjustFitSync();
        } else {
            adjustFitAsync(isDragging);
        }
    }

    function startResize(e, direction) {
        if (e.button !== 0) return;
        e.preventDefault();
        e.stopPropagation();

        resize.isResizing = true;
        resize.startX = e.clientX;
        resize.startY = e.clientY;
        resize.startWidth = panelSize.width;
        resize.startHeight = panelSize.height;
        resize.startRight = pos.right;
        resize.startTop = pos.top;

        document.addEventListener('mousemove', onResizeMove);
        document.addEventListener('mouseup', stopResize, { once: true });
        document.body.style.cursor = 'nwse-resize';
        document.body.style.userSelect = 'none';
    }

    function onResizeMove(e) {
        if (!resize.isResizing) return;

        const dx = e.clientX - resize.startX;
        const dy = e.clientY - resize.startY;

        const newWidth = Math.min(MAX_PANEL_WIDTH, Math.max(MIN_PANEL_WIDTH, resize.startWidth - dx));
        const newHeight = Math.min(MAX_PANEL_HEIGHT, Math.max(MIN_PANEL_HEIGHT, resize.startHeight - dy));

        const widthDelta = newWidth - resize.startWidth;
        const heightDelta = newHeight - resize.startHeight;
        const newTop = resize.startTop - heightDelta;

        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const minMargin = 0;

        const leftEdge = viewportWidth - pos.right - newWidth;
        if (leftEdge < minMargin) {
            panelSize.width = viewportWidth - pos.right - minMargin;
        } else {
            panelSize.width = newWidth;
        }

        if (newTop < minMargin) {
            panelSize.height = Math.max(MIN_PANEL_HEIGHT, resize.startHeight + resize.startTop - minMargin);
        } else {
            panelSize.height = newHeight;
            pos.top = newTop;
        }

        ensurePanelFitsViewport();
    }

    function stopResize() {
        resize.isResizing = false;
        document.removeEventListener('mousemove', onResizeMove);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';

        persistSize();
        if (onResizeEnd) onResizeEnd();
    }

    onUnmounted(() => {
        document.removeEventListener('mousemove', onResizeMove);
        if (adjustFitRAF) cancelAnimationFrame(adjustFitRAF);
    });

    return {
        panelSize,
        fitOffset,
        resize,
        // 常量
        MIN_PANEL_WIDTH,
        MIN_PANEL_HEIGHT,
        MAX_PANEL_WIDTH,
        MAX_PANEL_HEIGHT,
        // 方法
        persistSize,
        loadSize,
        ensurePanelFitsViewport,
        computeFitOffset,
        adjustFit,
        startResize,
        stopResize
    };
}
