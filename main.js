// 初始化
document.addEventListener('DOMContentLoaded', () => {    // 添加按钮事件监听
    getElement('new-scene-btn').addEventListener('click', createNewScene);
    getElement('import-btn').addEventListener('click', triggerFileImport);    getElement('export-btn').addEventListener('click', exportScript);
    getElement('save-btn').addEventListener('click', saveCurrentFile);
    getElement('auto-save-btn').addEventListener('click', toggleAutoSave);
    getElement('import-file-input').addEventListener('change', handleFileUpload);
    getElement('undo-btn').addEventListener('click', undo);
    getElement('redo-btn').addEventListener('click', redo); // 添加重做按钮监听
    getElement('overview-btn').addEventListener('click', collapseAllNodes);

    getElement('delete-scene-btn').addEventListener('click', deleteScene);
    getElement('add-dialogue-btn').addEventListener('click', addDialogueToScene);

    getElement('delete-dialogue-btn').addEventListener('click', deleteDialogue);
    getElement('add-option-btn').addEventListener('click', addOptionToDialogue);
    getElement('add-action-btn').addEventListener('click', addAction);

    getElement('delete-option-btn').addEventListener('click', deleteOption);
    getElement('add-option-dialogue-btn').addEventListener('click', addDialogueToOption);

    getElement('confirm-import-btn').addEventListener('click', importScript);

    // 添加编辑框的blur事件监听，实现自动保存 (注意：频繁blur可能导致撤销栈过多)
    // 考虑使用显式的保存按钮或更智能的保存策略
    // 场景编辑器
    getElement('scene-name').addEventListener('blur', updateScene);
    getElement('scene-cap').addEventListener('blur', updateScene);
    getElement('scene-pgrs').addEventListener('blur', updateScene);

    // 对话编辑器
    // getElement('dialogue-id').addEventListener('blur', updateDialogue); // ID 不再编辑
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