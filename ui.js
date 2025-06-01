// 渲染场景列表
function renderSceneList() {
    sceneListEl.innerHTML = '';
    
    scriptData.forEach(scene => {
        const sceneElement = document.createElement('div');
        sceneElement.className = 'scene-item';
        if (currentScene && currentScene.scene === scene.scene) {
            sceneElement.classList.add('selected');
        }
        sceneElement.textContent = `${scene.scene}`;
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
    
    // 添加此行代码启用拖拽排序
    enableDialogueDragSort();
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
    
    // 创建展开/收缩按钮
    const hasChildren = dialogue.opt && dialogue.opt.length > 0;
    
    if (hasChildren) {
        const toggleBtn = document.createElement('span');
        toggleBtn.className = 'toggle-btn expanded';
        toggleBtn.innerHTML = '&#9660;'; // 向下三角形
        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const childrenContainer = dialogueWrapper.querySelector('.node-children');
            if (childrenContainer) {
                const isExpanded = toggleBtn.classList.contains('expanded');
                if (isExpanded) {
                    toggleBtn.classList.remove('expanded');
                    toggleBtn.classList.add('collapsed');
                    toggleBtn.innerHTML = '&#9654;'; // 向右三角形
                    childrenContainer.style.display = 'none';
                } else {
                    toggleBtn.classList.remove('collapsed');
                    toggleBtn.classList.add('expanded');
                    toggleBtn.innerHTML = '&#9660;'; // 向下三角形
                    childrenContainer.style.display = 'block';
                }
            }
        });
        dialogueElement.appendChild(toggleBtn);
    }
    
    // 节点内容容器
    const nodeContent = document.createElement('div');
    nodeContent.className = 'node-content';
    
    // 节点ID和角色
    const nodeTitle = document.createElement('div');
    nodeTitle.className = 'node-title';
    nodeTitle.textContent = `ID: ${dialogue.id}, 角色: ${dialogue.chr}`;
    nodeContent.appendChild(nodeTitle);
    
    // 对话内容预览
    const preview = document.createElement('div');
    preview.className = 'node-preview';
    preview.textContent = dialogue.txt && dialogue.txt.length > 30 ? 
        dialogue.txt.substring(0, 30) + '...' : 
        dialogue.txt || '(无文本)';
    nodeContent.appendChild(preview);
    
    // 添加标记显示
    const badgesContainer = document.createElement('div');
    badgesContainer.className = 'badges-container';
    badgesContainer.style.marginTop = '4px';
    badgesContainer.style.display = 'flex';
    badgesContainer.style.gap = '4px';
    
    // 行为标记
    if (dialogue.act && Object.keys(dialogue.act).length > 0) {
        const actBadge = document.createElement('span');
        actBadge.className = 'badge act';
        actBadge.textContent = '行为';
        badgesContainer.appendChild(actBadge);
    }
    
    // Next标记
    if (dialogue.next) {
        const nextBadge = document.createElement('span');
        nextBadge.className = 'badge next';
        nextBadge.textContent = `跳转至：${dialogue.next}`;
        badgesContainer.appendChild(nextBadge);
    }
    
    // 选项标记 - 新增
    if (hasChildren) {
        const optionsBadge = document.createElement('span');
        optionsBadge.className = 'badge options';
        optionsBadge.textContent = `选项个数: ${dialogue.opt.length}`;
        badgesContainer.appendChild(optionsBadge);
    }
    
    if (badgesContainer.children.length > 0) {
        nodeContent.appendChild(badgesContainer);
    }
    
    dialogueElement.appendChild(nodeContent);
    
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
    
    // 创建展开/收缩按钮
    const hasChildren = option.dia && option.dia.length > 0;
    
    if (hasChildren) {
        const toggleBtn = document.createElement('span');
        toggleBtn.className = 'toggle-btn expanded';
        toggleBtn.innerHTML = '&#9660;'; // 向下三角形
        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const childrenContainer = optionWrapper.querySelector('.node-children');
            if (childrenContainer) {
                const isExpanded = toggleBtn.classList.contains('expanded');
                if (isExpanded) {
                    toggleBtn.classList.remove('expanded');
                    toggleBtn.classList.add('collapsed');
                    toggleBtn.innerHTML = '&#9654;'; // 向右三角形
                    childrenContainer.style.display = 'none';
                } else {
                    toggleBtn.classList.remove('collapsed');
                    toggleBtn.classList.add('expanded');
                    toggleBtn.innerHTML = '&#9660;'; // 向下三角形
                    childrenContainer.style.display = 'block';
                }
            }
        });
        optionElement.appendChild(toggleBtn);
    }
    
    // 节点内容容器
    const nodeContent = document.createElement('div');
    nodeContent.className = 'node-content';
    
    // 选项文本
    const optionTitle = document.createElement('div');
    optionTitle.className = 'node-title';
    optionTitle.textContent = `选项: ${option.optn || '(无文本)'}`;
    nodeContent.appendChild(optionTitle);
    
    optionElement.appendChild(nodeContent);
    
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
    // 隐藏所有编辑器表单，但不显示no-selection
    document.querySelectorAll('.editor-form').forEach(form => {
        form.style.display = 'none';
    });
    // 隐藏"请选择一个节点进行编辑"提示
    document.querySelector('.no-selection').style.display = 'none';
    showToolbar();
    if (!currentScene) return;
    
    getElement('scene-name').value = currentScene.scene || '';
    getElement('scene-cap').value = currentScene.cap || '';
    getElement('scene-pgrs').value = currentScene.pgrs || 0;
    
    sceneEditorEl.style.display = 'block';
}

// 显示对话编辑器
function showDialogueEditor() {
    // 隐藏所有编辑器表单，但不显示no-selection
    document.querySelectorAll('.editor-form').forEach(form => {
        form.style.display = 'none';
    });
    // 隐藏"请选择一个节点进行编辑"提示
    document.querySelector('.no-selection').style.display = 'none';
    showToolbar();
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
    // 隐藏所有编辑器表单，但不显示no-selection
    document.querySelectorAll('.editor-form').forEach(form => {
        form.style.display = 'none';
    });
    // 隐藏"请选择一个节点进行编辑"提示
    document.querySelector('.no-selection').style.display = 'none';
    showToolbar();
    if (!currentNode) return;
    
    getElement('option-text').value = currentNode.optn || '';
    
    optionEditorEl.style.display = 'block';
}

// 显示工具栏
function showToolbar() {
    const toolbar = getElement('editor-toolbar');
    if (toolbar) {
        toolbar.style.display = 'flex';
    }
}

// 隐藏工具栏
function hideToolbar() {
    const toolbar = getElement('editor-toolbar');
    if (toolbar) {
        toolbar.style.display = 'none';
    }
}

// 隐藏所有编辑器
function hideAllEditors() {
    document.querySelectorAll('.editor-form').forEach(form => {
        form.style.display = 'none';
    });
    document.querySelector('.no-selection').style.display = 'block';
    hideToolbar();
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

// 收起所有节点（总览功能）
function collapseAllNodes() {
    // 找到所有展开的切换按钮并收起它们
    const toggleButtons = document.querySelectorAll('.toggle-btn.expanded');
    
    toggleButtons.forEach(btn => {
        // 触发点击事件来收起节点
        btn.click();
    });
    
    console.log(`已收起 ${toggleButtons.length} 个节点`);
    const expandedButtons = document.querySelectorAll('#dialogue-tree .toggle-btn.expanded');
    
    expandedButtons.forEach(toggleBtn => {
        // 找到对应的子节点容器
        const nodeWrapper = toggleBtn.closest('.tree-node-wrapper');
        if (nodeWrapper) {
            const childrenContainer = nodeWrapper.querySelector('.node-children');
            if (childrenContainer) {
                // 收起节点
                toggleBtn.classList.remove('expanded');
                toggleBtn.classList.add('collapsed');
                toggleBtn.innerHTML = '&#9654;'; // 向右三角形
                childrenContainer.style.display = 'none';
            }
        }
    });
    
    console.log('已收起所有对话节点');
}