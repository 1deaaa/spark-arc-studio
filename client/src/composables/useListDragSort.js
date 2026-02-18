/**
 * 列表拖拽排序 Composable
 * 使用原生 HTML5 Drag and Drop API 实现列表项的拖拽重排序
 * 支持平台列表和模型列表的排序
 */
import { ref } from 'vue';

/**
 * 创建一个列表拖拽排序实例
 * @param {Function} onReorder - 排序完成后的回调，接收新顺序的 ID 数组
 * @param {Function} getItemId - 从列表项获取 ID 的函数，默认取 .id
 * @returns 拖拽相关的状态和事件处理函数
 */
export function useListDragSort(onReorder, getItemId = (item) => item.id) {
    // 当前正在拖拽的项索引
    const draggingIndex = ref(null);
    // 当前悬停的目标索引（用于高亮显示）
    const dragOverIndex = ref(null);

    /**
     * 拖拽开始
     * @param {DragEvent} e
     * @param {number} index - 被拖拽项的索引
     */
    function onDragStart(e, index) {
        draggingIndex.value = index;
        // 设置拖拽数据（必须，否则 Firefox 不允许拖拽）
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', String(index));
    }

    /**
     * 拖拽经过某项时
     * @param {DragEvent} e
     * @param {number} index - 目标项的索引
     */
    function onDragOver(e, index) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        dragOverIndex.value = index;
    }

    /**
     * 拖拽离开某项时
     */
    function onDragLeave() {
        dragOverIndex.value = null;
    }

    /**
     * 放置（完成排序）
     * @param {DragEvent} e
     * @param {number} toIndex - 目标位置索引
     * @param {Array} list - 当前列表数据
     */
    function onDrop(e, toIndex, list) {
        e.preventDefault();
        const fromIndex = draggingIndex.value;
        if (fromIndex === null || fromIndex === toIndex) {
            draggingIndex.value = null;
            dragOverIndex.value = null;
            return;
        }

        // 重排列表
        const newList = [...list];
        const [moved] = newList.splice(fromIndex, 1);
        newList.splice(toIndex, 0, moved);

        // 提取新顺序的 ID 列表
        const orderedIds = newList.map(getItemId);

        draggingIndex.value = null;
        dragOverIndex.value = null;

        // 调用回调
        onReorder(orderedIds, newList);
    }

    /**
     * 拖拽结束（无论是否成功放置）
     */
    function onDragEnd() {
        draggingIndex.value = null;
        dragOverIndex.value = null;
    }

    return {
        draggingIndex,
        dragOverIndex,
        onDragStart,
        onDragOver,
        onDragLeave,
        onDrop,
        onDragEnd,
    };
}
