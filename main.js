// 初始化
document.addEventListener('DOMContentLoaded', () => {
    // 初始化下拉框
    initDropdowns();

    // 添加按钮事件监听
    getElement('new-scene-btn').addEventListener('click', createNewScene);
    getElement('import-btn').addEventListener('click', triggerFileImport);
    getElement('export-btn').addEventListener('click', exportScript);
    getElement('save-btn').addEventListener('click', () => saveCurrentFile(true)); // 手动保存显示成功消息
    getElement('auto-save-btn').addEventListener('click', toggleAutoSave);
    getElement('import-file-input').addEventListener('change', handleFileUpload);
    getElement('undo-btn').addEventListener('click', undo);
    getElement('redo-btn').addEventListener('click', redo); // 添加重做按钮监听    getElement('overview-btn').addEventListener('click', collapseAllNodes);

    getElement('delete-scene-btn').addEventListener('click', deleteScene);
    getElement('add-dialogue-btn').addEventListener('click', addDialogueToScene);

    getElement('delete-dialogue-btn').addEventListener('click', deleteDialogue);
    getElement('add-option-btn').addEventListener('click', addOptionToDialogue);
    getElement('add-action-btn').addEventListener('click', addAction);    getElement('delete-option-btn').addEventListener('click', deleteOption);    getElement('add-option-dialogue-btn').addEventListener('click', addDialogueToOption);
    
    getElement('confirm-import-btn').addEventListener('click', importScript);// 添加编辑框的blur事件监听，实现自动保存 (注意：频繁blur可能导致撤销栈过多)
    // 考虑使用显式的保存按钮或更智能的保存策略
    // 场景编辑器
    getElement('scene-name').addEventListener('blur', () => {
        updateScene();
        autoSave(); // 失焦时自动保存到文件
    });
    getElement('scene-cap').addEventListener('blur', () => {
        updateScene();
        autoSave(); // 失焦时自动保存到文件
    });
    getElement('scene-pgrs').addEventListener('blur', () => {
        updateScene();
        autoSave(); // 失焦时自动保存到文件
    });

    // 对话编辑器
    // getElement('dialogue-id').addEventListener('blur', updateDialogue); // ID 不再编辑
    getElement('dialogue-chr').addEventListener('blur', () => {
        updateDialogue();
        autoSave(); // 失焦时自动保存到文件
    });    getElement('dialogue-txt').addEventListener('blur', () => {
        updateDialogue();
        autoSave(); // 失焦时自动保存到文件
    });
    
    // 为对话文本框添加回车键拦截
    getElement('dialogue-txt').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault(); // 阻止换行
            
            // 1. 先同步数据到编辑器
            updateDialogue();
            
            // 2. 如果启用自动保存，触发保存
            if (autoSaveEnabled && currentFileName) {
                autoSave();
            }
            
            // 3. 在同层级创建新对话
            addDialogueAtSameLevel();
        }
    });
    getElement('dialogue-next').addEventListener('blur', () => {
        updateDialogue();
        autoSave(); // 失焦时自动保存到文件
    });

    // 选项编辑器
    getElement('option-text').addEventListener('blur', () => {
        updateOption();
        autoSave(); // 失焦时自动保存到文件
    });

    // 关闭模态框
    document.querySelector('.close').addEventListener('click', () => {
        getElement('modal').style.display = 'none';
    });
    document.querySelector('.close-import').addEventListener('click', () => {
        getElement('import-modal').style.display = 'none';
    });

    // 点击模态框外部关闭
    window.addEventListener('click', (event) => {
        const modal = getElement('modal');
        if (event.target === modal) {
            modal.style.display = 'none';
        }
        const importModal = getElement('import-modal');        if (event.target === importModal) {
            importModal.style.display = 'none';
        }
    });    const resizerManager = new ResizerManager();
    window.fileManager = new FileManager();    // 初始化自动保存状态
    loadAutoSaveState();

    // 初始化示例数据或加载本地存储的数据
    initSampleData();
    
    // 页面关闭前检查未保存修改
    window.addEventListener('beforeunload', (e) => {
        if (hasUnsavedChanges && currentFileName) {
            e.preventDefault();
            e.returnValue = ''; // 现代浏览器要求设置为空字符串
            return ''; // 某些浏览器需要返回值
        }
    });
});

// 选择下一个对话节点
function selectNextDialogue() {
    if (!currentScene || !currentScene.dia || !currentNode) return;
    
    // 查找当前节点在同层中的位置
    let dialogues = [];
    let currentIndex = -1;
    
    if (nodeParent && nodeParent.dia) {
        // 如果当前节点在选项的子对话中
        dialogues = nodeParent.dia;
        currentIndex = dialogues.findIndex(d => d === currentNode);
    } else {
        // 如果当前节点在场景的顶层对话中
        dialogues = currentScene.dia;
        currentIndex = dialogues.findIndex(d => d === currentNode);
    }
    
    // 如果找到了下一个节点，选中它
    if (currentIndex !== -1 && currentIndex < dialogues.length - 1) {
        const nextDialogue = dialogues[currentIndex + 1];
        selectNode(nextDialogue, 'dialogue', nodeParent);
        // 聚焦到对话文本框
        setTimeout(() => {
            const txtElement = getElement('dialogue-txt');
            if (txtElement) {
                txtElement.focus();            txtElement.select(); // 选中所有文本
            }
        }, 50);
    }
}

// 初始化下拉框功能
function initDropdowns() {
    // 获取所有下拉框
    const dropdowns = document.querySelectorAll('.dropdown');
    
    dropdowns.forEach(dropdown => {
        const btn = dropdown.querySelector('.dropdown-btn');
        const content = dropdown.querySelector('.dropdown-content');
        
        if (btn && content) {
            // 点击按钮切换下拉框显示状态
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                
                // 关闭其他下拉框
                document.querySelectorAll('.dropdown').forEach(other => {
                    if (other !== dropdown) {
                        other.classList.remove('show');
                    }
                });
                
                // 切换当前下拉框
                dropdown.classList.toggle('show');
            });
        }
    });
    
    // 点击其他地方关闭下拉框
    document.addEventListener('click', () => {
        document.querySelectorAll('.dropdown').forEach(dropdown => {
            dropdown.classList.remove('show');
        });
    });
}

// 在同层级添加对话
function addDialogueAtSameLevel() {
    if (!currentNode || !currentScene) return;
    
    saveToUndo();
    
    // 使用ID管理器生成场景内唯一ID
    const newDialogue = {
        id: window.idManager.generateUniqueIdForScene(currentScene),
        chr: 0,
        txt: '新对话内容'
    };
    
    // 找到当前节点所在的数组
    let targetArray = null;
    let insertIndex = -1;
    
    if (nodeParent && nodeParent.dia) {
        // 如果当前节点在选项的子对话中
        targetArray = nodeParent.dia;
        insertIndex = targetArray.findIndex(d => d === currentNode);
    } else {
        // 如果当前节点在场景的顶层对话中
        targetArray = currentScene.dia;
        insertIndex = targetArray.findIndex(d => d === currentNode);
    }
      // 在当前节点后面插入新对话
    if (targetArray && insertIndex !== -1) {
        targetArray.splice(insertIndex + 1, 0, newDialogue);
        selectNode(newDialogue, 'dialogue', nodeParent);
        // selectNode 已经调用了 renderDialogueTree(true)，无需重复调用
    }
}