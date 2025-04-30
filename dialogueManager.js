// 选择节点
function selectNode(node, type, parent = null) {
    currentNode = node;
    nodeParent = parent;
    
    renderDialogueTree();
    
    if (type === 'dialogue') {
        showDialogueEditor();
    } else if (type === 'option') {
        showOptionEditor();
    }
}

// 添加对话到场景
function addDialogueToScene() {
    if (!currentScene) return;
    
    saveToUndo();
    
    // 生成新的ID
    let maxId = 10000;
    currentScene.dia.forEach(d => {
        if (d.id > maxId) maxId = d.id;
    });
    
    const newDialogue = {
        id: maxId + 1,
        chr: 0,
        txt: '新对话内容'
    };
    
    currentScene.dia.push(newDialogue);
    selectNode(newDialogue, 'dialogue');
    renderDialogueTree();
}

// 更新对话
function updateDialogue() {
    if (!currentNode) return;
    
    saveToUndo();
    
    currentNode.id = parseInt(getElement('dialogue-id').value) || 0;
    currentNode.chr = parseInt(getElement('dialogue-chr').value) || 0;
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
    
    renderDialogueTree();
}

// 删除对话
function deleteDialogue() {
    if (!currentNode) return;
    saveToUndo();
    
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
                
                currentNode = nodeParent;
                nodeParent = null;
                
                renderDialogueTree();
                showOptionEditor();
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
            
            renderDialogueTree();
            hideAllEditors();
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
    
    saveToUndo();
    
    if (!currentNode.act) {
        currentNode.act = {};
    }
    
    currentNode.act[key] = value;
    renderActionList();
    
    // 清空输入框
    getElement('action-key').value = '';
    getElement('action-value').value = '';
}