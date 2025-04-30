// 初始化
document.addEventListener('DOMContentLoaded', () => {
    // 添加按钮事件监听
    getElement('new-scene-btn').addEventListener('click', createNewScene);
    getElement('import-btn').addEventListener('click', showImportModal);
    getElement('export-btn').addEventListener('click', exportScript);
    getElement('undo-btn').addEventListener('click', undo);
    
    getElement('delete-scene-btn').addEventListener('click', deleteScene);
    getElement('add-dialogue-btn').addEventListener('click', addDialogueToScene);
    
    getElement('delete-dialogue-btn').addEventListener('click', deleteDialogue);
    getElement('add-option-btn').addEventListener('click', addOptionToDialogue);
    getElement('add-action-btn').addEventListener('click', addAction);
    
    getElement('delete-option-btn').addEventListener('click', deleteOption);
    getElement('add-option-dialogue-btn').addEventListener('click', addDialogueToOption);
    
    getElement('confirm-import-btn').addEventListener('click', importScript);
    
    // 添加编辑框的blur事件监听，实现自动保存
    // 场景编辑器
    getElement('scene-name').addEventListener('blur', updateScene);
    getElement('scene-cap').addEventListener('blur', updateScene);
    getElement('scene-pgrs').addEventListener('blur', updateScene);
    
    // 对话编辑器
    getElement('dialogue-id').addEventListener('blur', updateDialogue);
    getElement('dialogue-chr').addEventListener('blur', updateDialogue);
    getElement('dialogue-txt').addEventListener('blur', updateDialogue);
    getElement('dialogue-next').addEventListener('blur', updateDialogue);
    
    // 选项编辑器
    getElement('option-text').addEventListener('blur', updateOption);
    
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
        const importModal = getElement('import-modal');
        if (event.target === importModal) {
            importModal.style.display = 'none';
        }
    });
    
    // 为所有鼠标事件添加阻止冒泡
    document.querySelectorAll('button').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    });
    
    // 创建一些示例数据
    initSampleData();
});