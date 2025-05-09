// 拖拽管理功能

// 启用对话节点的拖拽排序
function enableDialogueDragSort() {
    if (!currentScene) return;
    
    // 选择所有对话节点 - 不再限制只有顶层节点
    const dialogueNodes = document.querySelectorAll('.dialogue-node');
    
    dialogueNodes.forEach(node => {
        node.setAttribute('draggable', 'true');
        node.classList.add('draggable');
        
        // 添加拖拽事件监听器
        node.addEventListener('dragstart', handleDragStart);
        node.addEventListener('dragend', handleDragEnd);
    });
    
    // 为所有节点的父容器添加放置区域 - 不再限制只有顶层节点的父容器
    const wrappers = document.querySelectorAll('.tree-node-wrapper');
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
    
    // 存储被拖拽节点的信息
    const nodeWrapper = this.closest('.tree-node-wrapper');
    const parentContainer = nodeWrapper.parentElement;
    
    // 存储数据：父容器选择器和节点索引
    const parentSelector = getNodePath(parentContainer);
    const nodeIndex = Array.from(parentContainer.children).indexOf(nodeWrapper);
    
    e.dataTransfer.setData('text/plain', JSON.stringify({
        parentSelector: parentSelector,
        nodeIndex: nodeIndex
    }));
    
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
    
    // 获取拖拽数据
    const dragData = JSON.parse(e.dataTransfer.getData('text/plain'));
    const targetParentSelector = getNodePath(this.parentElement);
    
    // 只有在同一父容器内才允许放置
    if (targetParentSelector === dragData.parentSelector) {
        e.dataTransfer.dropEffect = 'move';
    } else {
        e.dataTransfer.dropEffect = 'none';
    }
    
    return false;
}

// 拖拽进入目标区域
function handleDragEnter(e) {
    // 获取拖拽数据
    try {
        const dragData = JSON.parse(e.dataTransfer.getData('text/plain'));
        const targetParentSelector = getNodePath(this.parentElement);
        
        // 只有在同一父容器内才高亮目标区域
        if (targetParentSelector === dragData.parentSelector) {
            this.classList.add('drag-over');
        }
    } catch (err) {
        // 如果还没有设置拖拽数据（例如，在拖拽刚开始时）
        // 可以忽略错误
    }
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
    
    // 获取拖拽数据
    try {
        const dragData = JSON.parse(e.dataTransfer.getData('text/plain'));
        const targetParentSelector = getNodePath(this.parentElement);
        
        // 只在同一父容器内移动节点
        if (targetParentSelector === dragData.parentSelector) {
            const fromIndex = dragData.nodeIndex;
            const toIndex = Array.from(this.parentElement.children).indexOf(this);
            
            // 如果拖拽到自己或节点索引无效，则不处理
            if (fromIndex === toIndex || isNaN(fromIndex) || isNaN(toIndex)) {
                return;
            }
            
            // 保存当前状态到撤销栈
            saveToUndo();
            
            // 重新排序节点
            moveNode(fromIndex, toIndex, dragData.parentSelector);
            
            // 重新渲染对话树
            renderDialogueTree();
        }
    } catch (err) {
        console.error("放置处理出错:", err);
    }
    
    return false;
}

// 获取节点路径，用于唯一标识父容器
function getNodePath(node) {
    // 对于对话树的根节点
    if (node.id === 'dialogue-tree') {
        return '#dialogue-tree';
    }
    
    // 对于选项下的对话容器
    if (node.classList.contains('node-children')) {
        const parentNode = node.closest('.tree-node-wrapper');
        if (!parentNode) return null;
        
        const parentPath = getNodePath(parentNode.parentElement);
        const parentIndex = Array.from(parentNode.parentElement.children).indexOf(parentNode);
        
        return `${parentPath} > :nth-child(${parentIndex + 1}) > .node-children`;
    }
    
    return null;
}

// 移动节点 (根据父容器选择器和索引)
function moveNode(fromIndex, toIndex, parentSelector) {
    // 根节点情况 (顶级对话)
    if (parentSelector === '#dialogue-tree') {
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
        return;
    }
    
    // 处理嵌套节点
    // 解析选择器以找到正确的数组
    const containerPath = parseNodePath(parentSelector);
    if (!containerPath) return;
    
    // 获取相应的数组
    const nodeArray = getNodeArrayByPath(containerPath);
    if (!nodeArray || !Array.isArray(nodeArray)) return;
    
    // 执行移动
    const movedNode = nodeArray[fromIndex];
    if (!movedNode) return;
    
    // 从原位置删除
    nodeArray.splice(fromIndex, 1);
    
    // 计算新位置
    const newIndex = fromIndex < toIndex ? toIndex - 1 : toIndex;
    
    // 插入到新位置
    nodeArray.splice(newIndex, 0, movedNode);
    
    // 如果当前选中节点是被移动的节点，重新选择它
    if (currentNode === movedNode) {
        // 保持选择和编辑器打开
        if (movedNode.optn !== undefined) {
            selectNode(movedNode, 'option', findParentForOption(movedNode));
        } else {
            selectNode(movedNode, 'dialogue', nodeParent);
        }
    }
}

// 解析节点路径
function parseNodePath(selector) {
    // 对于根节点
    if (selector === '#dialogue-tree') {
        return { type: 'root' };
    }
    
    // 对于嵌套节点，格式应该是：
    // "#dialogue-tree > :nth-child(1) > .node-children > :nth-child(2) > .node-children"
    const parts = selector.split(' > ');
    const path = [];
    
    for (let i = 1; i < parts.length; i += 2) {
        if (parts[i].startsWith(':nth-child(') && parts[i+1] === '.node-children') {
            const indexMatch = parts[i].match(/:nth-child\((\d+)\)/);
            if (indexMatch) {
                path.push(parseInt(indexMatch[1]) - 1); // 转为0-based索引
            }
        }
    }
    
    if (path.length > 0) {
        return { type: 'nested', path: path };
    }
    
    return null;
}

// 根据路径获取对应的节点数组
function getNodeArrayByPath(containerPath) {
    if (containerPath.type === 'root') {
        return currentScene.dia;
    } else if (containerPath.type === 'nested') {
        const path = containerPath.path;
        let current = currentScene.dia;
        
        // 遍历路径找到最终的数组
        for (let i = 0; i < path.length; i++) {
            const index = path[i];
            if (i % 2 === 0) {
                // 偶数层级：对话节点，下一层是opt
                if (!current[index] || !current[index].opt) return null;
                current = current[index].opt;
            } else {
                // 奇数层级：选项节点，下一层是dia
                if (!current[index] || !current[index].dia) return null;
                current = current[index].dia;
            }
        }
        
        return current;
    }
    
    return null;
}