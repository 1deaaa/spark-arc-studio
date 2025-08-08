// 选择场景
function selectScene(scene) {
    currentScene = scene;
    currentNode = null;
    
    renderSceneList();
    showSceneEditor();
    renderDialogueTree(); // 直接调用渲染对话树，确保只渲染一次
    
    
    // 移除 sceneSelected 事件派发，避免重复渲染
}

// 创建新场景
function createNewScene() {
    const newSceneId = prompt('请输入新场景的名称：');
    if (!newSceneId) return;
    
    const existingScene = scriptData.find(s => s.scene === newSceneId);
    if (existingScene) {
        alert('场景名称已存在，请使用不同的名称');
        return;
    }
    
    saveToUndo();
    
    const newScene = {
        scene: newSceneId,
        cap: `场景 ${newSceneId}`,
        pgrs: 0,
        dia: []
    };
    
    scriptData.push(newScene);
    selectScene(newScene);
}

// 更新场景
function updateScene() {
    if (!currentScene) return;
    
    saveToUndo();
    
    currentScene.scene = getElement('scene-name').value;
    currentScene.cap = getElement('scene-cap').value;
    currentScene.pgrs = parseFloat(getElement('scene-pgrs').value) || 0;
    
    renderSceneList();
}

// 删除场景
function deleteScene() {
    if (!currentScene) return;
    
    const confirm = window.confirm(`确定要删除场景 "${currentScene.scene}" 吗？`);
    if (!confirm) return;
    
    saveToUndo();
    
    const index = scriptData.findIndex(s => s.scene === currentScene.scene);
    if (index !== -1) {
        scriptData.splice(index, 1);
    }
    
    currentScene = null;
    currentNode = null;
    
    renderSceneList();
    renderDialogueTree();
    hideAllEditors();
}