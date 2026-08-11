/**
 * useBlueprintCanvas - 可复用的蓝图画布 Composable
 * 
 * 共享逻辑：
 * - 节点 DOM 引用管理
 * - 端口坐标计算
 * - 贝塞尔曲线路径计算
 * - SVG 渐变 ID 管理
 * - 节点拖拽
 */

import { ref, computed } from 'vue';

type BlueprintNode = {
    id?: string;
    x: number;
    y: number;
    [key: string]: unknown;
};

type BlueprintConnection = {
    sourceId: string;
    targetId: string;
    [key: string]: unknown;
};

type BlueprintCanvasOptions = {
    gradientPrefix?: string;
};

type DragHandlerOptions = {
    onDragEnd?: ((node: BlueprintNode) => void) | null;
    shouldStartDrag?: ((event: MouseEvent, node: BlueprintNode) => boolean) | null;
    getCoordinateScale?: (() => number) | null;
};

/**
 * @param {Object} options
 * @param {string} options.gradientPrefix - 渐变 ID 前缀，用于区分不同蓝图
 */
export function useBlueprintCanvas(options: BlueprintCanvasOptions = {}) {
    const { gradientPrefix = 'bp' } = options;

    // ========== 响应式状态 ==========
    const canvasRef = ref<HTMLElement | null>(null);
    const svgRef = ref<SVGElement | null>(null);
    const nodeEls = ref<Map<string, HTMLElement>>(new Map());
    const layoutTick = ref(0);

    // ========== 节点引用管理 ==========
    /**
     * 设置或移除节点 DOM 引用
     * @param {string} id - 节点 ID
     * @param {HTMLElement|null} el - DOM 元素
     */
    function setNodeRef(id: string, el: HTMLElement | null) {
        if (!nodeEls.value) nodeEls.value = new Map();
        if (el) nodeEls.value.set(id, el);
        else nodeEls.value.delete(id);
    }

    // ========== 坐标计算 ==========
    /**
     * 获取指定端口的中心坐标（相对于画布）
     * @param {string} nodeId - 节点 ID
     * @param {'in'|'out'} type - 端口类型
     * @returns {{x: number, y: number}|null}
     */
    function getPortCenter(nodeId: string, type: 'in' | 'out') {
        const nodeEl = nodeEls.value.get(nodeId);
        const canvasEl = canvasRef.value;
        if (!nodeEl || !canvasEl) return null;

        const portEl = nodeEl.querySelector(type === 'out' ? '.port-out' : '.port-in');
        if (!portEl) return null;

        const portRect = portEl.getBoundingClientRect();
        const canvasRect = canvasEl.getBoundingClientRect();

        const cx = portRect.left + portRect.width / 2 - canvasRect.left + canvasEl.scrollLeft;
        const cy = portRect.top + portRect.height / 2 - canvasRect.top + canvasEl.scrollTop;
        return { x: cx, y: cy };
    }

    /**
     * 计算两个端口之间的贝塞尔曲线路径
     * @param {Object} connection - 连线对象 { sourceId, targetId }
     * @returns {string} SVG path d 属性值
     */
    function calculateConnectionPath(connection: BlueprintConnection): string {
        const s = getPortCenter(connection.sourceId, 'out');
        const t = getPortCenter(connection.targetId, 'in');
        if (!s || !t) return '';

        const midX = (s.x + t.x) / 2;
        return `M ${s.x} ${s.y} C ${midX} ${s.y}, ${midX} ${t.y}, ${t.x} ${t.y}`;
    }

    // ========== SVG ID 工具 ==========
    /**
     * 净化 SVG ID，移除非法字符
     * @param {string} value
     * @returns {string}
     */
    function sanitizeSvgId(value: string): string {
        return String(value).replace(/[^a-zA-Z0-9_-]/g, '_');
    }

    /**
     * 生成连线渐变 ID
     * @param {Object} connection - 连线对象 { sourceId, targetId }
     * @returns {string}
     */
    function gradientId(connection: BlueprintConnection): string {
        return `${gradientPrefix}_grad_${sanitizeSvgId(connection.sourceId)}__${sanitizeSvgId(connection.targetId)}`;
    }

    /**
     * 获取连线端点坐标
     * @param {Object} connection
     * @returns {{s: {x,y}|null, t: {x,y}|null}}
     */
    function getConnectionEndpoints(connection: BlueprintConnection): { s: { x: number; y: number } | null; t: { x: number; y: number } | null } {
        const s = getPortCenter(connection.sourceId, 'out');
        const t = getPortCenter(connection.targetId, 'in');
        return { s, t };
    }

    // ========== 拖拽功能 ==========
    /**
     * 创建节点拖拽处理器
     * @param {Object} options
     * @param {Function} options.onDragEnd - 拖拽结束回调
     * @param {Function} options.shouldStartDrag - 判断是否应该开始拖拽的函数
     * @returns {Function} startDrag 函数
     */
    function createDragHandler(options: DragHandlerOptions = {}) {
        const { onDragEnd, shouldStartDrag, getCoordinateScale } = options;

        return function startDrag(e: MouseEvent, node: BlueprintNode) {
            if (e.button !== 0) return; // 仅左键

            // 可选的自定义判断
            if (shouldStartDrag && !shouldStartDrag(e, node)) return;

            const startX = e.clientX;
            const startY = e.clientY;
            const initialX = node.x;
            const initialY = node.y;
            const rawScale = getCoordinateScale?.() ?? 1;
            const coordinateScale = Number.isFinite(rawScale) && rawScale > 0 ? rawScale : 1;

            const onMouseMove = (moveEvent: MouseEvent) => {
                const dx = moveEvent.clientX - startX;
                const dy = moveEvent.clientY - startY;
                node.x = initialX + dx / coordinateScale;
                node.y = initialY + dy / coordinateScale;
                layoutTick.value++;
            };

            const onMouseUp = () => {
                window.removeEventListener('mousemove', onMouseMove);
                window.removeEventListener('mouseup', onMouseUp);
                if (onDragEnd) onDragEnd(node);
            };

            window.addEventListener('mousemove', onMouseMove);
            window.addEventListener('mouseup', onMouseUp);
        };
    }

    /**
     * 计算渐变定义数组（用于 SVG defs）
     * @param {Array} connections - 连线数组
     * @returns {Array} 渐变定义数组
     */
    function computeGradientDefs(connections: BlueprintConnection[]) {
        const defs: Array<{ id: string; x1: number; y1: number; x2: number; y2: number }> = [];
        for (const c of connections) {
            const { s, t } = getConnectionEndpoints(c);
            if (!s || !t) continue;
            defs.push({ id: gradientId(c), x1: s.x, y1: s.y, x2: t.x, y2: t.y });
        }
        return defs;
    }

    /**
     * 获取连线 stroke 样式
     * @param {Object} connection
     * @returns {string}
     */
    function connectionStroke(connection: BlueprintConnection): string {
        const { s, t } = getConnectionEndpoints(connection);
        if (!s || !t) return 'var(--spark-primary)';
        return `url(#${gradientId(connection)})`;
    }

    // ========== 导出 ==========
    return {
        // 响应式状态
        canvasRef,
        svgRef,
        nodeEls,
        layoutTick,

        // 节点引用
        setNodeRef,

        // 坐标计算
        getPortCenter,
        calculateConnectionPath,
        getConnectionEndpoints,

        // SVG 工具
        sanitizeSvgId,
        gradientId,
        computeGradientDefs,
        connectionStroke,

        // 拖拽
        createDragHandler,
    };
}
