// 选择节点（统一唯一实现）
function selectNode(node, type, parent = null) {
    // 统一写入全局状态 (同时写 window.* 与同名全局 let 变量)
    window.currentNode = node;
    window.nodeParent = parent;
    window.nodeType = type; // 'dialogue' | 'option'
    try { currentNode = node; } catch(_) {}
    try { nodeParent = parent; } catch(_) {}
    try { nodeType = type; } catch(_) {}

    // 渲染并保持展开状态
    if (typeof renderDialogueTree === 'function') {
        renderDialogueTree(true);
    }

    // 更新高亮
    if (typeof updateNodeSelection === 'function') {
        updateNodeSelection();
    }

    // 显示对应编辑器
    if (type === 'dialogue') {
        if (typeof showDialogueEditor === 'function') showDialogueEditor();
    } else if (type === 'option') {
        if (typeof showOptionEditor === 'function') showOptionEditor();
    }

    // 广播事件（供其他模块监听）
    document.dispatchEvent(new CustomEvent('nodeSelected', {
        detail: { node, type, parent }
    }));
    // 确保全局函数引用的是此实现
    window.selectNode = selectNode;
}

// 添加对话到场景
function addDialogueToScene() {
    if (!currentScene) return;
    // 结构修改：创建新对话（延后统一快照）

    // 使用ID管理器生成场景内唯一ID（如果可用）
    let newId = 10001; // 默认ID
    
    if (window.idManager && typeof window.idManager.generateUniqueIdForScene === 'function') {
        newId = window.idManager.generateUniqueIdForScene(currentScene);
    } else {
        // 如果ID管理器不可用，使用全局计数器
        if (typeof nextNodeId !== 'undefined') {
            newId = nextNodeId++;
        } else {
            // 如果nextNodeId也未定义，生成一个随机ID
            newId = Math.floor(Math.random() * 100000) + 10000;
        }
    }
    
    const newDialogue = {
        id: newId,
        chr: 0,
        txt: '新对话内容'
    };    currentScene.dia.push(newDialogue);
    selectNode(newDialogue, 'dialogue');
    if (typeof onStructuralChange === 'function') onStructuralChange();
    // selectNode 已经调用了 renderDialogueTree(true)，无需重复调用
}

// 更新对话
function updateDialogue() {
    if (!currentNode) return;
    // 内容修改 -> 使用防抖快照

    const chrValue = getElement('dialogue-chr').value;
    currentNode.chr = chrValue !== '' ? parseInt(chrValue) : 0;
    currentNode.txt = getElement('dialogue-txt').value;

    const nextValue = getElement('dialogue-next').value.trim();
    if (nextValue) {
        currentNode.next = nextValue;
    } else if (currentNode.next) {
        delete currentNode.next;
    }

    // 如果act为空对象，删除act属性
    if (currentNode.act && Object.keys(currentNode.act).length === 0) {
        delete currentNode.act;
    }

    renderDialogueTree(true); // 保持展开状态
    if (typeof onContentChange === 'function') onContentChange();
}

// 删除对话
function deleteDialogue() {
    if (!currentNode) return;
    // 删除对话属于结构变更

    // 如果有父节点（针对选项中的对话），从父节点的dia数组中删除
    if (nodeParent) {
        if (nodeParent.dia) {
            const index = nodeParent.dia.findIndex(d => d === currentNode);
            if (index !== -1) {
                nodeParent.dia.splice(index, 1);

                // 如果对话数组为空，删除dia属性
                if (nodeParent.dia.length === 0) {
                    delete nodeParent.dia;
                }

                currentNode = nodeParent; // 选择父选项
                nodeParent = findParentForOption(currentNode); // 重新查找父对话

                renderDialogueTree(true); // 保持展开状态
                showOptionEditor();
                if (typeof onStructuralChange === 'function') onStructuralChange();
                return;
            }
        }
    }

    // 从场景的对话数组中删除
    if (currentScene && currentScene.dia) {
        const index = currentScene.dia.findIndex(d => d === currentNode);
        if (index !== -1) {
            currentScene.dia.splice(index, 1);
            currentNode = null;
            nodeParent = null; // 清除父节点

            renderDialogueTree(true); // 保持展开状态
            hideAllEditors();
            if (typeof onStructuralChange === 'function') onStructuralChange();
        }
    }
}

// 添加行为
function addAction() {
    const key = getElement('action-key').value.trim();
    const value = getElement('action-value').value.trim();

    if (!key) {
        alert('函数名不能为空');
        return;
    }

    // 行为增删属于结构修改

    if (!currentNode.act) {
        currentNode.act = {};
    }

    currentNode.act[key] = value;
    renderActionList();
    renderDialogueTree(true); // 保持展开状态 更新树节点上的标记
    if (typeof onStructuralChange === 'function') onStructuralChange();

    // 清空输入框
    getElement('action-key').value = '';
    getElement('action-value').value = '';
}

// 辅助函数：为选项查找其父对话节点 (如果需要更复杂的查找逻辑，可以扩展)
function findParentForOption(optionNode) {
    if (!currentScene) return null;
    let parentDialogue = null;

    function findRecursively(dialogues) {
        if (!dialogues) return;
        for (const d of dialogues) {
            if (d.opt && d.opt.includes(optionNode)) {
                parentDialogue = d;
                return;
            }
            if (d.opt) {
                for (const o of d.opt) {
                    if (o.dia) {
                        findRecursively(o.dia);
                        if (parentDialogue) return; // 找到后停止
                    }
                }
            }
        }
    }

    findRecursively(currentScene.dia);
    return parentDialogue;
}