// 渲染场景列表
function renderSceneList() {
    sceneListEl.innerHTML = '';
    
    scriptData.forEach(scene => {
        const sceneElement = document.createElement('div');
        sceneElement.className = 'scene-item';
        if (currentScene && currentScene.scene === scene.scene) {
            sceneElement.classList.add('selected');
        }
        sceneElement.textContent = `${scene.scene} - ${scene.cap}`;
        sceneElement.addEventListener('click', () => {
            selectScene(scene);
        });
        
        sceneListEl.appendChild(sceneElement);
    });
}

// 渲染对话树
function renderDialogueTree() {
    dialogueTreeEl.innerHTML = '';
    
    if (!currentScene) return;
    
    // 渲染对话节点
    currentScene.dia.forEach(dialogue => {
        const dialogueElement = createDialogueElement(dialogue);
        dialogueTreeEl.appendChild(dialogueElement);
    });
}

// 创建对话元素
function createDialogueElement(dialogue, parentOption = null) {
    const dialogueWrapper = document.createElement('div');
    dialogueWrapper.className = 'tree-node-wrapper';
    
    const dialogueElement = document.createElement('div');
    dialogueElement.className = 'tree-node dialogue-node';
    if (currentNode === dialogue) {
        dialogueElement.classList.add('selected');
    }
    
    // 节点ID和角色
    const nodeTitle = document.createElement('div');
    nodeTitle.className = 'node-title';
    nodeTitle.textContent = `ID: ${dialogue.id}, 角色: ${dialogue.chr}`;
    dialogueElement.appendChild(nodeTitle);
    
    // 对话内容预览
    const preview = document.createElement('div');
    preview.className = 'node-preview';
    preview.textContent = dialogue.txt && dialogue.txt.length > 30 ? 
        dialogue.txt.substring(0, 30) + '...' : 
        dialogue.txt || '(无文本)';
    dialogueElement.appendChild(preview);
    
    // 添加标记显示
    const badgesContainer = document.createElement('div');
    badgesContainer.style.marginTop = '4px';
    badgesContainer.style.display = 'flex';
    badgesContainer.style.gap = '4px';
    
    // 行为标记
    if (dialogue.act && Object.keys(dialogue.act).length > 0) {
        const actBadge = document.createElement('span');
        actBadge.className = 'badge';
        actBadge.textContent = '行为';
        actBadge.style.padding = '2px 6px';
        actBadge.style.backgroundColor = '#ffdd57';
        actBadge.style.borderRadius = '10px';
        actBadge.style.fontSize = '12px';
        badgesContainer.appendChild(actBadge);
    }
    
    // Next标记
    if (dialogue.next) {
        const nextBadge = document.createElement('span');
        nextBadge.className = 'badge';
        nextBadge.textContent = `Next: ${dialogue.next}`;
        nextBadge.style.padding = '2px 6px';
        nextBadge.style.backgroundColor = '#57c9ff';
        nextBadge.style.borderRadius = '10px';
        nextBadge.style.fontSize = '12px';
        badgesContainer.appendChild(nextBadge);
    }
    
    if (badgesContainer.children.length > 0) {
        dialogueElement.appendChild(badgesContainer);
    }
    
    // 点击事件 - 修改这里，传递实际的父对象
    dialogueElement.addEventListener('click', (e) => {
        e.stopPropagation();
        selectNode(dialogue, 'dialogue', parentOption);
    });
    
    dialogueWrapper.appendChild(dialogueElement);
    
    // 如果有选项，添加选项节点
    if (dialogue.opt && dialogue.opt.length > 0) {
        const childrenContainer = document.createElement('div');
        childrenContainer.className = 'node-children';
        
        dialogue.opt.forEach(option => {
            const optionElement = createOptionElement(option, dialogue);
            childrenContainer.appendChild(optionElement);
        });
        
        dialogueWrapper.appendChild(childrenContainer);
    }
    
    return dialogueWrapper;
}

// 创建选项元素
function createOptionElement(option, parentDialogue) {
    const optionWrapper = document.createElement('div');
    optionWrapper.className = 'tree-node-wrapper';
    
    const optionElement = document.createElement('div');
    optionElement.className = 'tree-node option-node';
    if (currentNode === option) {
        optionElement.classList.add('selected');
    }
    
    // 选项文本
    const optionTitle = document.createElement('div');
    optionTitle.className = 'node-title';
    optionTitle.textContent = `选项: ${option.optn || '(无文本)'}`;
    optionElement.appendChild(optionTitle);
    
    // 点击事件
    optionElement.addEventListener('click', (e) => {
        e.stopPropagation();
        selectNode(option, 'option', parentDialogue);
    });
    
    optionWrapper.appendChild(optionElement);
    
    // 如果有子对话，递归添加
    if (option.dia && option.dia.length > 0) {
        const childrenContainer = document.createElement('div');
        childrenContainer.className = 'node-children';
        
        option.dia.forEach(dialogue => {
            // 修改这里，传递选项对象作为父对象
            const dialogueElement = createDialogueElement(dialogue, option);
            childrenContainer.appendChild(dialogueElement);
        });
        
        optionWrapper.appendChild(childrenContainer);
    }
    
    return optionWrapper;
}

// 显示场景编辑器
function showSceneEditor() {
    hideAllEditors();
    if (!currentScene) return;
    
    getElement('scene-name').value = currentScene.scene || '';
    getElement('scene-cap').value = currentScene.cap || '';
    getElement('scene-pgrs').value = currentScene.pgrs || 0;
    
    sceneEditorEl.style.display = 'block';
}

// 显示对话编辑器
function showDialogueEditor() {
    hideAllEditors();
    if (!currentNode) return;
    
    getElement('dialogue-id').value = currentNode.id || '';
    getElement('dialogue-chr').value = currentNode.chr || '';
    getElement('dialogue-txt').value = currentNode.txt || '';
    getElement('dialogue-next').value = currentNode.next || '';
    
    // 渲染行为列表
    renderActionList();
    
    dialogueEditorEl.style.display = 'block';
}

// 显示选项编辑器
function showOptionEditor() {
    hideAllEditors();
    if (!currentNode) return;
    
    getElement('option-text').value = currentNode.optn || '';
    
    optionEditorEl.style.display = 'block';
}

// 隐藏所有编辑器
function hideAllEditors() {
    document.querySelectorAll('.editor-form').forEach(form => {
        form.style.display = 'none';
    });
    document.querySelector('.no-selection').style.display = 'block';
}

// 渲染行为列表
function renderActionList() {
    const actionList = getElement('action-list');
    actionList.innerHTML = '';
    
    if (!currentNode.act) {
        currentNode.act = {};
    }
    
    Object.entries(currentNode.act).forEach(([key, value]) => {
        const actionItem = document.createElement('div');
        actionItem.className = 'action-item';
        
        const actionKey = document.createElement('span');
        actionKey.className = 'action-key';
        actionKey.textContent = key;
        
        const actionValue = document.createElement('span');
        actionValue.className = 'action-value';
        actionValue.textContent = value;
        
        const removeBtn = document.createElement('span');
        removeBtn.className = 'remove-action';
        removeBtn.textContent = '×';
        removeBtn.addEventListener('click', () => {
            delete currentNode.act[key];
            renderActionList();
        });
        
        actionItem.appendChild(actionKey);
        actionItem.appendChild(document.createTextNode(': '));
        actionItem.appendChild(actionValue);
        actionItem.appendChild(removeBtn);
        
        actionList.appendChild(actionItem);
    });
}