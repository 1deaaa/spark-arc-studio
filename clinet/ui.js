// 渲染场景列表
// ---- 全局节点状态（补充）----
// 使用 window.* 避免与其它脚本中 let/const 冲突造成重复声明错误
if (typeof window.currentNode === 'undefined') window.currentNode = null;
if (typeof window.nodeType === 'undefined') window.nodeType = null; // 'dialogue' | 'option'
if (typeof window.nodeParent === 'undefined') window.nodeParent = null; // 当前节点的父（选项的父对话）

// 统一的节点选择函数（如果外部未实现）
if (typeof window.selectNode === 'undefined') {
    window.selectNode = function (node, type, parent = null) {
        window.currentNode = node;
        window.nodeType = type;
        window.nodeParent = parent;

        // 保持展开状态重新渲染，确保选中高亮 & 右侧编辑器同步
        if (typeof renderDialogueTree === 'function') {
            renderDialogueTree(true, true).then(() => {
                if (typeof updateNodeSelection === 'function') updateNodeSelection();
            });
        } else if (typeof updateNodeSelection === 'function') {
            updateNodeSelection();
        }

        if (type === 'dialogue' && typeof showDialogueEditor === 'function') {
            showDialogueEditor();
        } else if (type === 'option' && typeof showOptionEditor === 'function') {
            showOptionEditor();
        } else if (typeof hideAllEditors === 'function') {
            hideAllEditors();
        }
    };
}

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
// 使用序列号避免异步重入造成的重复追加渲染
let dialogueTreeRenderSeq = 0;
async function renderDialogueTree(preserveState = false, defaultExpanded = true) {
    const mySeq = ++dialogueTreeRenderSeq;
    let expandedNodes = new Set();
    
    // 只在需要保持状态时保存当前展开状态
    if (preserveState) {
        document.querySelectorAll('.toggle-btn.expanded').forEach(btn => {
            const wrapper = btn.closest('.tree-node-wrapper');
            const nodeElement = wrapper?.querySelector('.tree-node');
            if (nodeElement) {
                // 使用节点的唯一标识来保存状态
                const nodeId = getNodeUniqueId(nodeElement);
                if (nodeId) {
                    expandedNodes.add(nodeId);
                }
            }
        });
    }
    
    // 注意：不在这里清空，以避免旧的渲染在新渲染之后又写入导致重复
    // 等待数据准备完成后，并且确认当前渲染仍然是最新，再提交到 DOM
    if (!currentScene) {
        if (mySeq === dialogueTreeRenderSeq) {
            dialogueTreeEl.innerHTML = '';
        }
        return;
    }
    
    // 获取角色列表并创建角色映射
    let characterMap = {};
    try {
        const response = await window.authManager.makeAuthenticatedRequest(
            `/api/character-settings/${window.fileManager.currentProject}`
        );
        
        if (response && response.ok) {
            const characters = await response.json();
            characters.forEach(character => {
                characterMap[character.id] = character.name;
            });
        }
    } catch (error) {
        console.error('加载角色列表失败:', error);
    }
    
    // 如在异步等待期间有更新渲染请求，放弃本次渲染，避免重复
    if (mySeq !== dialogueTreeRenderSeq) return;
    
    // 提交渲染（先清空，再插入）
    dialogueTreeEl.innerHTML = '';
    
    // 渲染对话节点
    currentScene.dia.forEach(dialogue => {
        const dialogueElement = createDialogueElement(dialogue, null, defaultExpanded, characterMap);
        dialogueTreeEl.appendChild(dialogueElement);
    });
    
    // 如果需要保持状态，恢复展开状态
    if (preserveState) {
        // 当未收集到任何“已展开”节点时，避免误将整棵树收起，保持初始展开/收起状态
        if (expandedNodes && expandedNodes.size > 0) {
            restoreExpandedState(expandedNodes);
        }
    }
    
    // 添加此行代码启用拖拽排序（仅在当前渲染仍为最新时执行）
    if (mySeq === dialogueTreeRenderSeq) {
        enableDialogueDragSort();
    }
}

// 创建对话元素
function createDialogueElement(dialogue, parentOption = null, defaultExpanded = true, characterMap = null) {
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
        // 根据 defaultExpanded 参数设置初始状态
        toggleBtn.className = defaultExpanded ? 'toggle-btn expanded' : 'toggle-btn collapsed';
        toggleBtn.innerHTML = defaultExpanded ? '&#9660;' : '&#9654;';
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
    // 如果有角色映射，显示角色名，否则显示角色ID
    const characterName = characterMap && characterMap[dialogue.chr] ? characterMap[dialogue.chr] : dialogue.chr;
    nodeTitle.textContent = `ID: ${dialogue.id}, 角色: ${characterName}`;
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
        // 延迟执行选择，避免与失焦事件冲突
        setTimeout(() => {
            selectNode(dialogue, 'dialogue', parentOption);
        }, 50);
    });
    
    dialogueWrapper.appendChild(dialogueElement);    // 如果有选项，添加选项节点
    if (dialogue.opt && dialogue.opt.length > 0) {
        const childrenContainer = document.createElement('div');
        childrenContainer.className = 'node-children';
        // 根据 defaultExpanded 参数设置初始显示状态
        childrenContainer.style.display = defaultExpanded ? 'block' : 'none';
        
        dialogue.opt.forEach(option => {
            const optionElement = createOptionElement(option, dialogue, defaultExpanded, characterMap);
            childrenContainer.appendChild(optionElement);
        });
        
        dialogueWrapper.appendChild(childrenContainer);
    }
    
    return dialogueWrapper;
}

// 创建选项元素
function createOptionElement(option, parentDialogue, defaultExpanded = true, characterMap = null) {
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
        // 根据 defaultExpanded 参数设置初始状态
        toggleBtn.className = defaultExpanded ? 'toggle-btn expanded' : 'toggle-btn collapsed';
        toggleBtn.innerHTML = defaultExpanded ? '&#9660;' : '&#9654;';
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
        // 延迟执行选择，避免与失焦事件冲突
        setTimeout(() => {
            selectNode(option, 'option', parentDialogue);
        }, 50);
    });
    
    optionWrapper.appendChild(optionElement);    // 如果有子对话，递归添加
    if (option.dia && option.dia.length > 0) {
        const childrenContainer = document.createElement('div');
        childrenContainer.className = 'node-children';
        // 根据 defaultExpanded 参数设置初始显示状态
        childrenContainer.style.display = defaultExpanded ? 'block' : 'none';
        
        option.dia.forEach(dialogue => {
            // 修改这里，传递选项对象作为父对象、defaultExpanded参数和角色映射
            const dialogueElement = createDialogueElement(dialogue, option, defaultExpanded, characterMap);
            childrenContainer.appendChild(dialogueElement);
        });
        
        optionWrapper.appendChild(childrenContainer);
    }
    
    return optionWrapper;
}

// 显示场景编辑器
    function showSceneEditor() {
        // 恢复中间面板到正常状态
        restoreMiddlePanel();
        
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
        hideAiScreenwriter(); // 选中场景时隐藏AI面板
    }

// 显示对话编辑器
    function showDialogueEditor() {
        // 恢复中间面板到正常状态
        restoreMiddlePanel();
        
        // 隐藏所有编辑器表单，但不显示no-selection
        document.querySelectorAll('.editor-form').forEach(form => {
            form.style.display = 'none';
        });
        // 隐藏"请选择一个节点进行编辑"提示
        document.querySelector('.no-selection').style.display = 'none';
        showToolbar();
        
        if (!currentNode) return;
        
        getElement('dialogue-id').value = currentNode.id || '';
        getElement('dialogue-txt').value = currentNode.txt || '';
        getElement('dialogue-next').value = currentNode.next || '';
        
        // 渲染行为列表
        renderActionList();
         
        dialogueEditorEl.style.display = 'block';
        showAiScreenwriter(); // 选中对话节点时显示AI面板
        
        // 填充角色下拉列表并设置当前角色
        populateDialogueCharacterSelector();
    }

// 显示选项编辑器
    function showOptionEditor() {
        // 恢复中间面板到正常状态
        restoreMiddlePanel();
        
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
        hideAiScreenwriter(); // 选中选项节点时隐藏AI面板
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
        // 恢复中间面板到正常状态
        restoreMiddlePanel();
        
        const editors = document.querySelectorAll('.editor-form');
        if (editors.length > 0) {
            editors.forEach(form => {
                form.style.display = 'none';
            });
        }
        
        const noSelection = document.querySelector('.no-selection');
        if (noSelection) {
            noSelection.style.display = 'block';
        }
        
        hideToolbar();
        hideAiScreenwriter(); // 没有选中任何节点时隐藏AI面板
    }

// 显示AI编剧面板
function showAiScreenwriter() {
    const aiPanel = getElement('ai-screenwriter');
    if (aiPanel) {
        aiPanel.style.display = 'block';
    }
}

// 隐藏AI编剧面板
function hideAiScreenwriter() {
    const aiPanel = getElement('ai-screenwriter');
    if (aiPanel) {
        aiPanel.style.display = 'none';
    }
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

// 获取节点的唯一标识
function getNodeUniqueId(nodeElement) {
    if (nodeElement.classList.contains('dialogue-node')) {
        // 对话节点：使用ID
        const titleElement = nodeElement.querySelector('.node-title');
        if (titleElement) {
            const match = titleElement.textContent.match(/ID: (\d+)/);
            return match ? `dialogue-${match[1]}` : null;
        }
    } else if (nodeElement.classList.contains('option-node')) {
        // 选项节点：使用选项文本和父节点ID
        const titleElement = nodeElement.querySelector('.node-title');
        const parentWrapper = nodeElement.closest('.tree-node-wrapper').parentElement.closest('.tree-node-wrapper');
        const parentNode = parentWrapper?.querySelector('.tree-node');
        
        if (titleElement && parentNode) {
            const optionText = titleElement.textContent.replace('选项: ', '');
            const parentTitleElement = parentNode.querySelector('.node-title');
            if (parentTitleElement) {
                const parentMatch = parentTitleElement.textContent.match(/ID: (\d+)/);
                return parentMatch ? `option-${parentMatch[1]}-${optionText}` : null;
            }
        }
    }
    return null;
}

// 恢复展开状态
function restoreExpandedState(expandedNodes) {
    // 递归处理所有节点
    function processNode(wrapper) {
        const nodeElement = wrapper.querySelector('.tree-node');
        const toggleBtn = wrapper.querySelector('.toggle-btn');
        const childrenContainer = wrapper.querySelector('.node-children');
        
        if (nodeElement && toggleBtn && childrenContainer) {
            const nodeId = getNodeUniqueId(nodeElement);
            
            if (nodeId && expandedNodes.has(nodeId)) {
                // 恢复展开状态
                toggleBtn.classList.add('expanded');
                toggleBtn.classList.remove('collapsed');
                toggleBtn.innerHTML = '&#9660;'; // 向下三角形
                childrenContainer.style.display = 'block';
            } else {
                // 默认收起状态
                toggleBtn.classList.remove('expanded');
                toggleBtn.classList.add('collapsed');
                toggleBtn.innerHTML = '&#9654;'; // 向右三角形
                childrenContainer.style.display = 'none';
            }
        }
        
        // 递归处理子节点
        const childWrappers = wrapper.querySelectorAll(':scope > .node-children > .tree-node-wrapper');
        childWrappers.forEach(childWrapper => {
            processNode(childWrapper);
        });
    }
    
    // 处理所有顶级节点
    const topLevelWrappers = dialogueTreeEl.querySelectorAll(':scope > .tree-node-wrapper');
    topLevelWrappers.forEach(wrapper => {
        processNode(wrapper);
    });
}

// 更新节点选中状态（不重新渲染整个树）
function updateNodeSelection() {
    // 清除所有现有的选中状态
    document.querySelectorAll('.tree-node.selected').forEach(node => {
        node.classList.remove('selected');
    });
    
    // 如果有当前选中的节点，找到对应的DOM元素并添加选中状态
    if (currentNode) {
        const allNodes = document.querySelectorAll('.tree-node');
        allNodes.forEach(nodeElement => {
            if (nodeElement.classList.contains('dialogue-node')) {
                // 检查对话节点
                const titleElement = nodeElement.querySelector('.node-title');
                if (titleElement) {
                    const match = titleElement.textContent.match(/ID: (\d+)/);
                    if (match && currentNode.id && parseInt(match[1]) === currentNode.id) {
                        nodeElement.classList.add('selected');
                    }
                }
            } else if (nodeElement.classList.contains('option-node')) {
                // 检查选项节点
                const titleElement = nodeElement.querySelector('.node-title');
                if (titleElement && currentNode.optn) {
                    const optionText = titleElement.textContent.replace('选项: ', '');
                    if (optionText === currentNode.optn) {
                        // 还需要检查父节点是否匹配
                        if (nodeParent && nodeParent.id) {
                            const parentWrapper = nodeElement.closest('.tree-node-wrapper').parentElement.closest('.tree-node-wrapper');
                            const parentNode = parentWrapper?.querySelector('.tree-node.dialogue-node');
                            if (parentNode) {
                                const parentTitleElement = parentNode.querySelector('.node-title');
                                if (parentTitleElement) {
                                    const parentMatch = parentTitleElement.textContent.match(/ID: (\d+)/);
                                    if (parentMatch && parseInt(parentMatch[1]) === nodeParent.id) {
                                        nodeElement.classList.add('selected');
                                    }
                                }
                            }
                        }
                    }
                }
            }
        });
    }
}

// 确保指定的选项节点处于展开状态
function ensureOptionExpanded(optionNode, optionParent) {
    if (!optionNode || !optionNode.optn) return;
    
    // 查找对应的DOM元素
    const allOptionNodes = document.querySelectorAll('.tree-node.option-node');
    allOptionNodes.forEach(nodeElement => {
        const titleElement = nodeElement.querySelector('.node-title');
        if (titleElement) {
            const optionText = titleElement.textContent.replace('选项: ', '');
            if (optionText === optionNode.optn) {
                // 验证父节点是否匹配
                let isCorrectOption = true;
                if (optionParent && optionParent.id) {
                    const parentWrapper = nodeElement.closest('.tree-node-wrapper').parentElement.closest('.tree-node-wrapper');
                    const parentNode = parentWrapper?.querySelector('.tree-node.dialogue-node');
                    if (parentNode) {
                        const parentTitleElement = parentNode.querySelector('.node-title');
                        if (parentTitleElement) {
                            const parentMatch = parentTitleElement.textContent.match(/ID: (\d+)/);
                            isCorrectOption = parentMatch && parseInt(parentMatch[1]) === optionParent.id;
                        }
                    }
                }
                
                if (isCorrectOption) {
                    // 确保该选项展开
                    const wrapper = nodeElement.closest('.tree-node-wrapper');
                    const toggleBtn = wrapper?.querySelector('.toggle-btn');
                    const childrenContainer = wrapper?.querySelector('.node-children');
                    
                    if (toggleBtn && childrenContainer) {
                        toggleBtn.classList.remove('collapsed');
                        toggleBtn.classList.add('expanded');
                        toggleBtn.innerHTML = '&#9660;'; // 向下三角形
                        childrenContainer.style.display = 'block';
                    }
                }
            }
        }
    });
}
// 初始化 AI 编剧面板的交互
function initAiScreenwriter() {
    const aiModeSelect = getElement('ai-mode-select');
    const singleNodeControls = getElement('single-node-controls');
    const multiNodeControls = getElement('multi-node-controls');

    if (aiModeSelect) {
        aiModeSelect.addEventListener('change', () => {
            if (aiModeSelect.value === 'single-node') {
                singleNodeControls.style.display = 'block';
                multiNodeControls.style.display = 'none';
            } else {
                singleNodeControls.style.display = 'none';
                multiNodeControls.style.display = 'block';
                // 当切换到多段续写时，可能需要填充角色列表
                populateCharacterSelector();
            }
        });
    }

    getElement('ai-generate-single-btn').addEventListener('click', handleSingleNodeGeneration);
    getElement('ai-generate-multi-btn').addEventListener('click', handleMultiNodeGeneration);
}

async function handleSingleNodeGeneration() {
    // 允许在未显式设置 nodeType 时，通过属性判断类型
    const isDialogue = window.currentNode && (window.nodeType === 'dialogue' || (window.nodeType == null && typeof window.currentNode.id !== 'undefined' && !('optn' in window.currentNode)));
    if (!isDialogue) {
        alert('请先选择一个对话节点。');
        return;
    }

    const dialogueTxt = getElement('dialogue-txt');
    const context = dialogueTxt.value;
    const length = getElement('ai-single-length').value;
    const btn = getElement('ai-generate-single-btn');

    btn.disabled = true;
    btn.textContent = '生成中...';

    try {
        const response = await fetch('/api/ai/single-node', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                projectName: window.fileManager.currentProject,
                context: context,
                length: parseInt(length, 10),
                character_ids: [currentNode.chr] // 传递当前角色ID
            }),
        });

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value, { stream: true });
            dialogueTxt.value += chunk;
            updateDialogue(); // 实时更新数据模型
        }
    } catch (error) {
        console.error('AI单节点续写失败:', error);
        alert('AI单节点续写失败，请查看控制台。');
    } finally {
        btn.disabled = false;
        btn.textContent = '生成';
        autoSave();
    }
}

async function handleMultiNodeGeneration() {
    const isDialogue = window.currentNode && (window.nodeType === 'dialogue' || (window.nodeType == null && typeof window.currentNode.id !== 'undefined' && !('optn' in window.currentNode)));
    if (!isDialogue) {
        alert('请先选择一个对话节点。');
        return;
    }

    const context = `场景: ${currentScene.scene}\n当前对话ID: ${currentNode.id}\n对话内容: ${currentNode.txt}`;
    const guidance = getElement('ai-multi-prompt').value;
    const segment_count = getElement('ai-multi-segments').value;
    const charSelector = getElement('ai-multi-chars');
    const character_ids = [...charSelector.selectedOptions].map(opt => opt.value);

    if (character_ids.length === 0 || character_ids.length > 4) {
        alert('请选择1到4个参与角色。');
        return;
    }

    const btn = getElement('ai-generate-multi-btn');
    btn.disabled = true;
    btn.textContent = '生成中...';

    try {
        const response = await fetch('/api/ai/multi-node', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                projectName: window.fileManager.currentProject,
                context: context,
                guidance: guidance,
                character_ids: character_ids,
                segment_count: parseInt(segment_count, 10),
                current_file: currentFileName, // 需要传递当前文件名
                scene_name: currentScene.scene, // 和场景名
                after_node_id: currentNode.id // 以及节点ID，用于后端插入
            }),
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || '多段续写失败');
        }

        alert('多段续写成功！将刷新剧本。');
        // 刷新文件树和对话树
        await window.fileManager.loadFileContent(currentFileName);

    } catch (error) {
        console.error('AI多段续写失败:', error);
        alert(`AI多段续写失败: ${error.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = '生成';
    }
}

// 填充多段续写的角色选择器
function populateCharacterSelector() {
    const selector = getElement('ai-multi-chars');
    if (!selector) return;

    // 这里只是一个示例，你需要根据项目实际情况获取角色列表
    // 可能是从一个全局变量，或者从"角色设定.txt"解析
    const characters = [
        { id: 1, name: '角色A' },
        { id: 2, name: '角色B' },
        { id: 3, name: '角色C' }
    ];

    selector.innerHTML = '';
    characters.forEach(char => {
        const option = document.createElement('option');
        option.value = char.id;
        option.textContent = char.name;
        selector.appendChild(option);
    });
    }

// 填充对话编辑器的角色下拉列表
async function populateDialogueCharacterSelector() {
    const selector = getElement('dialogue-chr');
    if (!selector) return;

    // 清空现有选项
    selector.innerHTML = '';

    // 添加默认选项
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = '请选择角色';
    selector.appendChild(defaultOption);

    try {
        // 从API获取角色列表
        const response = await window.authManager.makeAuthenticatedRequest(
            `/api/character-settings/${window.fileManager.currentProject}`
        );

        if (!response) return;

        if (response.ok) {
            const characters = await response.json();
            // 添加角色选项
            characters.forEach(character => {
                const option = document.createElement('option');
                option.value = character.id;
                option.textContent = character.name;
                selector.appendChild(option);
            });

            // 设置当前选中角色
            if (currentNode && currentNode.chr !== undefined) {
                selector.value = currentNode.chr;
            }
            
            // 初始化Select2
            $(selector).select2({
                placeholder: "请选择角色",
                allowClear: true,
                width: '100%'
            });
        }
    } catch (error) {
        console.error('加载角色列表失败:', error);
    }
}
    
    // 加载世界观
    async function loadWorldView() {
        const worldviewEditor = document.getElementById('worldview-editor');
        if (!worldviewEditor || !window.fileManager || !window.fileManager.currentProject) return;
        
        try {
            const response = await window.authManager.makeAuthenticatedRequest(
                `/api/worldview/${window.fileManager.currentProject}`
            );
            
            if (!response) return;
            
            if (response.ok) {
                const data = await response.json();
                worldviewEditor.value = data.content || '';
            } else if (response.status === 404) {
                worldviewEditor.value = ''; // 文件不存在，清空编辑器
            } else {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        } catch (error) {
            console.error('加载世界观失败:', error);
            alert('加载世界观失败');
        }
    }
    
    // 保存世界观
    async function saveWorldView() {
        const worldviewEditor = document.getElementById('worldview-editor');
        if (!worldviewEditor || !window.fileManager || !window.fileManager.currentProject) return;
        
        try {
            const response = await window.authManager.makeAuthenticatedRequest(
                '/api/worldview',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        projectName: window.fileManager.currentProject,
                        content: worldviewEditor.value
                    })
                }
            );
            
            if (!response) return;
            
            const result = await response.json();
            if (result.success) {
                // 显示保存成功指示器
                if (typeof showSaveSuccessIndicator === 'function') {
                    showSaveSuccessIndicator();
                }
            } else {
                console.error(`保存失败: ${result.message}`);
            }
        } catch (error) {
            console.error('保存世界观失败:', error);
        }
    }
    
    // 加载角色设定
    async function loadCharacterSettings() {
        const characterList = document.getElementById('character-list');
        if (!characterList || !window.fileManager || !window.fileManager.currentProject) return;
        
        try {
            const response = await window.authManager.makeAuthenticatedRequest(
                `/api/character-settings/${window.fileManager.currentProject}`
            );
            
            if (!response) return;
            
            if (response.ok) {
                const characters = await response.json();
                renderCharacterList(characters);
            } else if (response.status === 404) {
                renderCharacterList([]); // 目录不存在，渲染空列表
            } else {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        } catch (error) {
            console.error('加载角色设定失败:', error);
            alert('加载角色设定失败');
        }
    }
    
    // 渲染角色列表
    function renderCharacterList(characters) {
        const characterList = document.getElementById('character-list');
        if (!characterList) return;
        
        characterList.innerHTML = '';
        
        if (characters.length === 0) {
            characterList.innerHTML = '<p>暂无角色设定</p>';
            return;
        }
        
        characters.forEach(character => {
            const characterElement = document.createElement('div');
            characterElement.className = 'character-item';
            
            const title = document.createElement('h5');
            title.textContent = character.name || `角色 ${character.id}`;
            characterElement.appendChild(title);
            
            const textarea = document.createElement('textarea');
            textarea.value = character.content || '';
            textarea.rows = '5';
            textarea.dataset.characterId = character.id;
            characterElement.appendChild(textarea);
            
            const buttonContainer = document.createElement('div');
            buttonContainer.className = 'button-group';
            
            const saveBtn = document.createElement('button');
            saveBtn.textContent = '保存';
            saveBtn.addEventListener('click', () => saveCharacter(character.id, textarea.value));
            buttonContainer.appendChild(saveBtn);
            
            const renameBtn = document.createElement('button');
            renameBtn.className = 'btn-secondary';
            renameBtn.textContent = '重命名';
            renameBtn.addEventListener('click', () => renameCharacter(character.id, character.name));
            buttonContainer.appendChild(renameBtn);
            
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn-danger';
            deleteBtn.textContent = '删除';
            deleteBtn.addEventListener('click', () => deleteCharacter(character.id));
            buttonContainer.appendChild(deleteBtn);
            
            characterElement.appendChild(buttonContainer);
            characterList.appendChild(characterElement);
        });
    }
    
    // 添加角色
    async function addCharacter() {
        const characterName = prompt('请输入角色名称:');
        if (!characterName) return;
        
        try {
            const response = await window.authManager.makeAuthenticatedRequest(
                '/api/character-settings',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        projectName: window.fileManager.currentProject,
                        name: characterName
                    })
                }
            );
            
            if (!response) return;
            
            const result = await response.json();
            if (result.success) {
                // 重新加载角色列表
                loadCharacterSettings();
            } else {
                alert(`创建角色失败: ${result.message}`);
            }
        } catch (error) {
            console.error('创建角色失败:', error);
            alert('创建角色失败');
        }
    }
    
    // 保存角色设定
    async function saveCharacter(characterId, content) {
        try {
            const response = await window.authManager.makeAuthenticatedRequest(
                '/api/character-settings/save',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        projectName: window.fileManager.currentProject,
                        id: characterId,
                        content: content
                    })
                }
            );
            
            if (!response) return;
            
            const result = await response.json();
            if (result.success) {
                // 显示保存成功指示器
                if (typeof showSaveSuccessIndicator === 'function') {
                    showSaveSuccessIndicator();
                }
            } else {
                console.error(`保存失败: ${result.message}`);
            }
        } catch (error) {
            console.error('保存角色设定失败:', error);
        }
    }
    
    // 重命名角色
    async function renameCharacter(characterId, currentName) {
        const newName = prompt('请输入新的角色名称:', currentName);
        if (!newName || newName === currentName) return;
        
        try {
            const response = await window.authManager.makeAuthenticatedRequest(
                '/api/character-settings/rename',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        projectName: window.fileManager.currentProject,
                        id: characterId,
                        newName: newName
                    })
                }
            );
            
            if (!response) return;
            
            const result = await response.json();
            if (result.success) {
                // 重新加载角色列表
                loadCharacterSettings();
            } else {
                alert(`重命名失败: ${result.message}`);
            }
        } catch (error) {
            console.error('重命名角色失败:', error);
            alert('重命名角色失败');
        }
    }
    
    // 删除角色
    async function deleteCharacter(characterId) {
        if (!confirm('确定要删除这个角色吗？')) return;
        
        try {
            const response = await window.authManager.makeAuthenticatedRequest(
                '/api/character-settings/delete',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        projectName: window.fileManager.currentProject,
                        id: characterId
                    })
                }
            );
            
            if (!response) return;
            
            const result = await response.json();
            if (result.success) {
                // 重新加载角色列表
                loadCharacterSettings();
            } else {
                alert(`删除失败: ${result.message}`);
            }
        } catch (error) {
            console.error('删除角色失败:', error);
            alert('删除角色失败');
        }
    }
    
    // 显示设定编辑器
    function showSettingsEditor() {
        // 获取中间面板的设定编辑容器
        const settingsEditorContainer = document.getElementById('settings-editor-container');
        if (!settingsEditorContainer) {
            console.error('settings-editor-container element not found');
            return;
        }
        
        // 获取对话树容器
        const dialogueTree = document.getElementById('dialogue-tree');
        if (!dialogueTree) {
            console.error('dialogue-tree element not found');
            return;
        }
        
        // 获取中间面板标题
        const middlePanelTitle = document.querySelector('.middle-panel h2');
        if (!middlePanelTitle) {
            console.error('middle-panel title element not found');
            return;
        }
        
        // 隐藏对话树
        dialogueTree.style.display = 'none';
        
        // 显示设定编辑容器
        settingsEditorContainer.style.display = 'block';
        
        // 更新中间面板标题
        middlePanelTitle.textContent = '设定编辑';
        
        // 清空设定编辑容器内容
        settingsEditorContainer.innerHTML = '';
        
        // 创建设定编辑器标题
        // -- Worldview Section --
        const worldViewSection = document.createElement('div');
        worldViewSection.className = 'settings-section';
        
        const worldViewTitle = document.createElement('h3');
        worldViewTitle.textContent = '世界观设定';
        worldViewSection.appendChild(worldViewTitle);
        
        const worldViewTextarea = document.createElement('textarea');
        worldViewTextarea.id = 'worldview-editor';
        worldViewTextarea.placeholder = '在这里描述你的故事世界...';
        worldViewSection.appendChild(worldViewTextarea);
        
        const saveWorldViewBtn = document.createElement('button');
        saveWorldViewBtn.id = 'save-worldview-btn';
        saveWorldViewBtn.textContent = '保存世界观';
        saveWorldViewBtn.addEventListener('click', saveWorldView);
        worldViewSection.appendChild(saveWorldViewBtn);
        
        settingsEditorContainer.appendChild(worldViewSection);
        
        // -- Character Settings Section --
        const characterSettingsSection = document.createElement('div');
        characterSettingsSection.className = 'settings-section';
        
        const characterSettingsTitle = document.createElement('h3');
        characterSettingsTitle.textContent = '角色设定';
        characterSettingsSection.appendChild(characterSettingsTitle);
        
        const characterList = document.createElement('div');
        characterList.id = 'character-list';
        characterSettingsSection.appendChild(characterList);
        
        const addCharacterBtn = document.createElement('button');
        addCharacterBtn.id = 'add-character-btn';
        addCharacterBtn.textContent = '添加新角色';
        addCharacterBtn.addEventListener('click', addCharacter);
        characterSettingsSection.appendChild(addCharacterBtn);
        
        settingsEditorContainer.appendChild(characterSettingsContainer);
        
        // 加载世界观和角色设定
        loadWorldView();
        loadCharacterSettings();
        
        // 为世界观编辑器添加自动保存功能
        setTimeout(() => {
            const worldviewEditor = document.getElementById('worldview-editor');
            if (worldviewEditor) {
                // 使用 input 事件实现实时保存
                worldviewEditor.addEventListener('input', () => {
                    // 延迟保存，避免过于频繁的保存操作
                    clearTimeout(worldviewEditor.saveTimeout);
                    worldviewEditor.saveTimeout = setTimeout(() => {
                        saveWorldView();
                        // 如果启用了自动保存，触发自动保存
                        if (autoSaveEnabled && currentFileName) {
                            autoSave();
                        }
                    }, 1000); // 1秒延迟
                });
            }
            
            // 为角色设定编辑器添加自动保存功能
            const characterListContainer = document.getElementById('character-list');
            if (characterListContainer) {
                // 使用事件委托处理动态添加的角色设定文本框
                characterListContainer.addEventListener('input', (e) => {
                    if (e.target.tagName === 'TEXTAREA' && e.target.dataset.characterId) {
                        // 延迟保存，避免过于频繁的保存操作
                        clearTimeout(e.target.saveTimeout);
                        e.target.saveTimeout = setTimeout(() => {
                            saveCharacter(e.target.dataset.characterId, e.target.value);
                            // 如果启用了自动保存，触发自动保存
                            if (autoSaveEnabled && currentFileName) {
                                autoSave();
                            }
                        }, 1000); // 1秒延迟
                    }
                });
            }
        }, 100); // 延迟执行，确保元素已渲染
    }
    
    // 恢复中间面板到正常状态
    function restoreMiddlePanel() {
        // 获取中间面板的设定编辑容器
        const settingsEditorContainer = document.getElementById('settings-editor-container');
        if (!settingsEditorContainer) {
            console.error('settings-editor-container element not found');
            return;
        }
        
        // 获取对话树容器
        const dialogueTree = document.getElementById('dialogue-tree');
        if (!dialogueTree) {
            console.error('dialogue-tree element not found');
            return;
        }
        
        // 获取中间面板标题
        const middlePanelTitle = document.querySelector('.middle-panel h2');
        if (!middlePanelTitle) {
            console.error('middle-panel title element not found');
            return;
        }
        
        // 隐藏设定编辑容器
        settingsEditorContainer.style.display = 'none';
        
        // 显示对话树
        dialogueTree.style.display = 'block';
        
        // 恢复中间面板标题
        middlePanelTitle.textContent = '对话树';
    }

// 暴露关键函数到全局（若未暴露）。避免 main.js 找不到函数
if (typeof window.showSettingsEditor === 'undefined') window.showSettingsEditor = showSettingsEditor;
if (typeof window.collapseAllNodes === 'undefined' && typeof collapseAllNodes === 'function') window.collapseAllNodes = collapseAllNodes;
