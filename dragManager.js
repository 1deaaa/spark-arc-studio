// 拖拽管理功能

// 启用对话节点的拖拽排序
function enableDialogueDragSort() {
    if (!currentScene) return;
    
    // 为每个可能的容器应用 Sortable
    initSortableForContainer(document.getElementById('dialogue-tree'));
    
    // 查找所有嵌套的节点容器并应用 Sortable
    document.querySelectorAll('.node-children').forEach(container => {
        initSortableForContainer(container);
    });
}

// 为容器初始化 Sortable
function initSortableForContainer(container) {
    if (!container) return;
    
    // 获取容器路径，用于识别数据位置
    const containerPath = getNodePath(container);
    
    Sortable.create(container, {
        group: {
            name: `container-${containerPath}`, // 为每个容器创建唯一的组名
            pull: false, // 不允许将节点拖出当前容器
            put: false  // 不允许将其他容器的节点拖入当前容器
        },
        animation: 150, // 动画时间
        ghostClass: 'dragging', // 拖动时应用的类
        chosenClass: 'chosen', // 被选中时应用的类
        dragClass: 'drag-item', // 拖动时的元素类
        forceFallback: false, // 使用原生HTML5拖放
        handle: '.tree-node', // 只能通过节点本身拖动
        fallbackOnBody: true,
        swapThreshold: 0.65,
        
        // 开始拖动时自动收起节点
        onStart: function(evt) {
            const draggedEl = evt.item;
            const nodeChildren = draggedEl.querySelector('.node-children');
            const toggleBtn = draggedEl.querySelector('.toggle-btn');
            
            // 判断如果节点有子节点且是展开状态，自动折叠
            if (nodeChildren && toggleBtn && toggleBtn.classList.contains('expanded')) {
                // 标记这个节点是被自动折叠的，以便拖动结束后可以识别
                draggedEl.dataset.wasExpanded = 'true';
                // 执行折叠
                toggleBtn.classList.remove('expanded');
                toggleBtn.classList.add('collapsed');
                toggleBtn.innerHTML = '&#9654;'; // 向右三角形
                nodeChildren.style.display = 'none';
            }
        },
        
        // 当排序完成时触发
        onEnd: function(evt) {
            // 保存到撤销栈
            saveToUndo();
            
            // 获取元素移动的起始和目标容器、位置
            const fromContainer = evt.from;
            const toContainer = evt.to;
            const fromIndex = evt.oldIndex;
            const toIndex = evt.newIndex;
            
            // 获取起始容器和目标容器的路径
            const fromContainerPath = getNodePath(fromContainer);
            const toContainerPath = getNodePath(toContainer);
            
            // 由于我们限制了只能同容器内移动，这里 fromContainer 和 toContainer 应该是同一个容器
            // 但为了代码健壮性，我们仍然使用通用的移动函数
            moveNodeBetweenContainers(fromIndex, toIndex, fromContainerPath, toContainerPath);
            
            // 记录当前所有展开的节点
            const expandedNodes = [];
            document.querySelectorAll('.toggle-btn.expanded').forEach(btn => {
                const nodePath = getNodePath(btn.closest('.tree-node-wrapper'));
                if (nodePath) expandedNodes.push(nodePath);
            });
            
            // 重新渲染对话树
            renderDialogueTree();
            
            // 恢复展开状态
            expandedNodes.forEach(path => {
                const node = document.querySelector(`[data-path="${path}"]`);
                if (node) {
                    const toggleBtn = node.querySelector('.toggle-btn');
                    const nodeChildren = node.querySelector('.node-children');
                    if (toggleBtn && nodeChildren) {
                        toggleBtn.classList.add('expanded');
                        toggleBtn.classList.remove('collapsed');
                        toggleBtn.innerHTML = '&#9660;'; 
                        nodeChildren.style.display = 'block';
                    }
                }
            });
        }
    });
}

// 跨容器移动节点
function moveNodeBetweenContainers(fromIndex, toIndex, fromContainerPath, toContainerPath) {
    // 解析容器路径
    const fromPath = parseNodePath(fromContainerPath);
    const toPath = parseNodePath(toContainerPath);
    
    if (!fromPath || !toPath) return;
    
    // 获取源数组和目标数组
    const fromArray = getNodeArrayByPath(fromPath);
    const toArray = getNodeArrayByPath(toPath);
    
    if (!fromArray || !toArray || !Array.isArray(fromArray) || !Array.isArray(toArray)) return;
    
    // 获取需要移动的节点
    const movedNode = fromArray[fromIndex];
    if (!movedNode) return;
    
    // 1. 从源数组中删除节点
    fromArray.splice(fromIndex, 1);
    
    // 2. 插入到目标数组
    toArray.splice(toIndex, 0, movedNode);
    
    // 3. 如果当前选中的节点是被移动的节点，保持选择状态
    if (currentNode === movedNode) {
        if (movedNode.optn !== undefined) {
            // 是选项节点
            selectNode(movedNode, 'option', findParentForOption(movedNode));
        } else {
            // 是对话节点
            selectNode(movedNode, 'dialogue', findParentForDialogue(movedNode));
        }
    }
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

// 查找对话节点的父节点（跨层级移动后可能变化）
function findParentForDialogue(dialogueNode) {
    // 在整个数据结构中搜索包含此对话节点的选项节点
    if (!currentScene || !currentScene.dia) return null;
    
    // 搜索函数
    function findParentInOptions(options, targetNode) {
        for (let i = 0; i < options.length; i++) {
            const option = options[i];
            if (option.dia) {
                if (option.dia.includes(targetNode)) {
                    return option;
                }
                
                // 递归搜索更深层次
                for (let j = 0; j < option.dia.length; j++) {
                    const childDialogue = option.dia[j];
                    if (childDialogue.opt) {
                        const result = findParentInOptions(childDialogue.opt, targetNode);
                        if (result) return result;
                    }
                }
            }
        }
        return null;
    }
    
    // 搜索顶级对话中的选项
    for (let i = 0; i < currentScene.dia.length; i++) {
        const dialogue = currentScene.dia[i];
        if (dialogue.opt) {
            const result = findParentInOptions(dialogue.opt, dialogueNode);
            if (result) return result;
        }
    }
    
    return null;
}

// 增强版的找到选项节点的父节点
function findParentForOption(optionNode) {
    // 在整个数据结构中搜索包含此选项节点的对话节点
    if (!currentScene || !currentScene.dia) return null;
    
    // 搜索函数
    function findParentInDialogues(dialogues, targetNode) {
        for (let i = 0; i < dialogues.length; i++) {
            const dialogue = dialogues[i];
            if (dialogue.opt) {
                if (dialogue.opt.includes(targetNode)) {
                    return dialogue;
                }
            }
            
            // 检查这个对话节点下所有选项的子对话
            if (dialogue.opt) {
                for (let j = 0; j < dialogue.opt.length; j++) {
                    const option = dialogue.opt[j];
                    if (option.dia) {
                        const result = findParentInDialogues(option.dia, targetNode);
                        if (result) return result;
                    }
                }
            }
        }
        return null;
    }
    
    // 从顶层对话开始搜索
    return findParentInDialogues(currentScene.dia, optionNode);
}