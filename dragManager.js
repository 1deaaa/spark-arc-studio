// 拖拽管理功能

// 启用对话节点的拖拽排序
function enableDialogueDragSort() {
    if (!currentScene) return;
    
    // 仅对顶层对话节点添加拖拽功能
    const dialogueNodes = document.querySelectorAll('#dialogue-tree > .tree-node-wrapper > .dialogue-node');
    
    dialogueNodes.forEach(node => {
        node.setAttribute('draggable', 'true');
        node.classList.add('draggable');
        
        // 添加拖拽事件监听器
        node.addEventListener('dragstart', handleDragStart);
        node.addEventListener('dragend', handleDragEnd);
    });
    
    // 为每个节点的父容器添加放置区域
    const wrappers = document.querySelectorAll('#dialogue-tree > .tree-node-wrapper');
    wrappers.forEach(wrapper => {
        wrapper.addEventListener('dragover', handleDragOver);
        wrapper.addEventListener('dragenter', handleDragEnter);
        wrapper.addEventListener('dragleave', handleDragLeave);
        wrapper.addEventListener('drop', handleDrop);
    });
}

// 拖拽开始
function handleDragStart(e) {
    // 添加拖拽中的样式
    this.classList.add('dragging');
    // 存储被拖拽节点的索引
    e.dataTransfer.setData('text/plain', getNodeIndex(this));
    // 设置拖拽效果
    e.dataTransfer.effectAllowed = 'move';
}

// 拖拽结束
function handleDragEnd() {
    this.classList.remove('dragging');
    // 移除所有放置区域的高亮
    document.querySelectorAll('.drag-over').forEach(el => {
        el.classList.remove('drag-over');
    });
}

// 拖拽经过目标区域时
function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault(); // 允许放置
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

// 拖拽进入目标区域
function handleDragEnter() {
    this.classList.add('drag-over');
}

// 拖拽离开目标区域
function handleDragLeave() {
    this.classList.remove('drag-over');
}

// 放置被拖拽的节点
function handleDrop(e) {
    e.stopPropagation(); // 阻止冒泡
    e.preventDefault();
    
    // 清除目标区域的高亮样式
    this.classList.remove('drag-over');
    
    // 获取拖拽的节点索引和目标节点索引
    const fromIndex = parseInt(e.dataTransfer.getData('text/plain'));
    const toIndex = getNodeIndex(this);
    
    // 如果拖拽到自己或节点索引无效，则不处理
    if (fromIndex === toIndex || isNaN(fromIndex) || isNaN(toIndex)) {
        return;
    }
    
    // 保存当前状态到撤销栈
    saveToUndo();
    
    // 重新排序对话节点
    moveDialogueNode(fromIndex, toIndex);
    
    // 重新渲染对话树
    renderDialogueTree();
    
    return false;
}

// 获取节点的索引
function getNodeIndex(node) {
    // 获取所有顶级对话节点
    const wrappers = Array.from(document.querySelectorAll('#dialogue-tree > .tree-node-wrapper'));
    return wrappers.indexOf(node.closest('.tree-node-wrapper'));
}

// 移动对话节点
function moveDialogueNode(fromIndex, toIndex) {
    // 确保场景存在
    if (!currentScene || !currentScene.dia) return;
    
    // 获取需要移动的对话节点
    const movedNode = currentScene.dia[fromIndex];
    if (!movedNode) return;
    
    // 从原位置删除
    currentScene.dia.splice(fromIndex, 1);
    
    // 计算新位置（需要考虑删除后的索引变化）
    const newIndex = fromIndex < toIndex ? toIndex - 1 : toIndex;
    
    // 插入到新位置
    currentScene.dia.splice(newIndex, 0, movedNode);
    
    // 如果当前选中节点是被移动的节点，重新选择它
    if (currentNode === movedNode) {
        selectNode(movedNode, 'dialogue');
    }
}