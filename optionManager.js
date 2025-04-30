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
    
    currentNode.opt.push(newOption);
    selectNode(newOption, 'option', currentNode);
    renderDialogueTree();
}

// 更新选项
function updateOption() {
    if (!currentNode || !nodeParent) return;
    
    saveToUndo();
    
    currentNode.optn = getElement('option-text').value;
    
    renderDialogueTree();
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
    renderDialogueTree();
    hideAllEditors();
}

// 添加对话到选项
function addDialogueToOption() {
    if (!currentNode) return;
    
    saveToUndo();
    
    if (!currentNode.dia) {
        currentNode.dia = [];
    }
    
    // 生成新的ID
    let maxId = 10000;
    // 遍历所有场景的所有对话查找最大ID
    scriptData.forEach(scene => {
        findMaxDialogueId(scene.dia, maxId, (id) => { maxId = id; });
    });
    
    const newDialogue = {
        id: maxId + 1,
        chr: 0,
        txt: '新选项对话内容'
    };
    
    currentNode.dia.push(newDialogue);
    selectNode(newDialogue, 'dialogue', nodeParent);
    renderDialogueTree();
}