// 添加选项到对话
function addOptionToDialogue() {
    if (!currentNode) return;
    
    saveToUndo();
    
    if (!currentNode.opt) {
        currentNode.opt = [];
    }
    
    const newOption = {
        optn: '新选项',
        dia: []
    };
    
    // 自动为新选项添加一个子对话
    if (currentScene && window.idManager) {
        const newDialogue = {
            id: window.idManager.generateUniqueIdForScene(currentScene),
            chr: 0,
            txt: '新选项对话内容'
        };
        newOption.dia.push(newDialogue);
    }
    
    currentNode.opt.push(newOption);
    selectNode(newOption, 'option', currentNode);
    
    // 根据自动保存设置决定是否自动保存
    if (typeof autoSave === 'function') {
        autoSave();
    }
    // selectNode 已经调用了 renderDialogueTree(true)，无需重复调用
}

// 更新选项
function updateOption() {
    if (!currentNode || !nodeParent) return;
    
    saveToUndo();
    
    currentNode.optn = getElement('option-text').value;
    
    renderDialogueTree(true); // 保持展开状态
}

// 删除选项
function deleteOption() {
    if (!currentNode || !nodeParent) return;
    
    const confirm = window.confirm('确定要删除这个选项吗？');
    if (!confirm) return;
    
    saveToUndo();
    
    const optIndex = nodeParent.opt.findIndex(o => o === currentNode);
    if (optIndex !== -1) {
        nodeParent.opt.splice(optIndex, 1);
    }
    
    // 如果没有选项了，删除opt属性
    if (nodeParent.opt.length === 0) {
        delete nodeParent.opt;
    }
      currentNode = null;
    renderDialogueTree(true); // 保持展开状态
    hideAllEditors();
}

// 添加对话到选项
function addDialogueToOption() {
    if (!currentNode || !currentScene) return; // 确保当前节点和当前场景都已选中
    
    saveToUndo();
    
    if (!currentNode.dia) {
        currentNode.dia = [];
    }
    
    // 检查ID管理器是否可用
    if (!window.idManager) {
        console.error('ID管理器未初始化');
        return;
    }
    
    // 使用ID管理器生成场景内唯一ID
    const newDialogue = {
        id: window.idManager.generateUniqueIdForScene(currentScene),
        chr: 0,
        txt: '新选项对话内容'
    };
    
    currentNode.dia.push(newDialogue);
    
    // 直接选择新对话，selectNode会自动处理渲染
    selectNode(newDialogue, 'dialogue', currentNode);
    
    // 根据自动保存设置决定是否自动保存
    if (typeof autoSave === 'function') {
        autoSave();
    }
}