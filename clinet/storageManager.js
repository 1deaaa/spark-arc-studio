// 初始化数据，尝试从 剧本示例.story 加载
async function initSampleData() {
  // 不再默认加载示例文件，直接用空数组初始化
  scriptData = [];
  console.log("编辑器已初始化为空白状态。");

  // 初始化ID管理器
  if (window.idManager) {
    window.idManager.initializeFromScriptData(scriptData);
    
    // 检查并修复重复ID
    const fixedCount = window.idManager.validateAndFixAllScenes(scriptData);
    if (fixedCount > 0) {
      console.log(`已自动修复 ${fixedCount} 个重复ID问题`);
    }
  }

  undoStack = [JSON.stringify(scriptData)]; // 初始状态存入撤销栈
  redoStack = []; // 清空重做栈
  
  // 初始化时标记为已保存状态
  markAsSaved();
  
  renderSceneList();
  // 初始时不选择任何场景或节点
  currentScene = null;
  currentNode = null;
  nodeParent = null;
  renderDialogueTree();
  hideAllEditors();
}

// 递归查找最大对话ID
function findMaxDialogueId(dialogues, maxId, callback) {
  if (!dialogues) return;

  dialogues.forEach(d => {
      // 确保 ID 是数字类型进行比较
      const currentId = parseInt(d.id, 10);
      if (!isNaN(currentId) && currentId > maxId) {
          callback(currentId);
      }

      if (d.opt) {
          d.opt.forEach(o => {
              if (o.dia) {
                  // 递归查找时传递当前的 maxId
                  findMaxDialogueId(o.dia, maxId, callback);
              }
          });
      }
  });
}


// 显示导入模态框
function showImportModal() {
  getElement('import-modal').style.display = 'block';
}

// 导入脚本
async function importScript() {
  // 检查是否有未保存的修改
  const canProceed = await checkAndPromptSave();
  if (!canProceed) {
      return; // 用户取消了导入
  }

  const importText = getElement('import-text').value;

  try {
      const importData = JSON.parse(importText);

      if (!Array.isArray(importData)) {
          throw new Error('导入数据必须是数组格式');
      }

      // 导入时清空撤销/重做栈，并将新数据作为初始状态
      scriptData = importData;
      
      // 重新初始化ID管理器
      if (window.idManager) {
        window.idManager.initializeFromScriptData(scriptData);
        
        // 检查并修复重复ID
        const fixedCount = window.idManager.validateAndFixAllScenes(scriptData);
        if (fixedCount > 0) {
          console.log(`导入时修复了 ${fixedCount} 个重复ID问题`);
          alert(`已自动修复 ${fixedCount} 个重复ID问题`);
        }
      }
      
      undoStack = [JSON.stringify(scriptData)];
      redoStack = [];

      currentScene = null;
      currentNode = null;
      nodeParent = null;

      // 清空当前文件名，因为是手动导入的
      currentFileName = null;
      
      // 标记为已保存状态
      markAsSaved();

      renderSceneList();
      renderDialogueTree();
      hideAllEditors();

      getElement('import-modal').style.display = 'none';
  } catch (error) {
      alert('导入失败: ' + error.message);
  }
}

// 导出脚本
function exportScript() {
  const exportText = JSON.stringify(scriptData, null, 2);

  // 创建一个模态框展示导出内容
  const modal = getElement('modal');
  const modalContent = getElement('modal-content-inner');

  modalContent.innerHTML = '';

  const title = document.createElement('h3');
  title.textContent = '导出对话脚本';
  modalContent.appendChild(title);

  const textarea = document.createElement('textarea');
  textarea.value = exportText;
  textarea.readOnly = true; // 设为只读
  textarea.style.width = '100%';
  textarea.style.height = '300px';
  textarea.style.fontFamily = 'monospace';
  textarea.style.padding = '10px';
  textarea.style.marginBottom = '15px';
  modalContent.appendChild(textarea);

  const copyBtn = document.createElement('button');
  copyBtn.textContent = '复制到剪贴板';
  copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(textarea.value).then(() => {
          alert('已复制到剪贴板');
      }).catch(err => {
          console.error('复制失败: ', err);
          alert('复制失败，请手动复制');
      });
  });
  modalContent.appendChild(copyBtn);

  const downloadBtn = document.createElement('button');
  downloadBtn.textContent = '下载文件';
  downloadBtn.style.marginLeft = '10px';
  downloadBtn.addEventListener('click', () => {      const blob = new Blob([exportText], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'dialogue_script.story';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
  });
  modalContent.appendChild(downloadBtn);

  modal.style.display = 'block';
}

// 保存当前状态到撤销栈
function saveToUndo() {
  const currentState = JSON.stringify(scriptData);
  // 避免重复保存完全相同的状态
  if (undoStack.length > 0 && undoStack[undoStack.length - 1] === currentState) {
      return;
  }
  undoStack.push(currentState);
  redoStack = []; // 任何新的操作都会清空重做栈
  console.log('撤销栈:', undoStack);
  // 限制撤销栈大小
  if (undoStack.length > 50) {
      undoStack.shift();
  }
  
  // 标记有未保存的修改（但不直接自动保存）
  markAsModified();
}

// ================= 新的统一快照与内容变更防抖机制 =================
// 说明：
// 1. 旧的 saveToUndo 在大量调用（尤其在修改前调用）会导致撤销逻辑不一致。
// 2. 新增 commitUndoSnapshot：始终在“修改完成后”保存当前状态作为最新可撤销点。
// 3. 文本/细粒度内容使用 scheduleContentUndo() 防抖聚合，避免每次敲字都入栈耗尽容量。
// 4. 撤销逻辑已调整，需要保证 init / 打开文件后有首个状态快照。

// 直接提交当前状态到撤销栈（修改之后调用）
function commitUndoSnapshot() {
    const currentState = JSON.stringify(scriptData);
    if (undoStack.length === 0 || undoStack[undoStack.length - 1] !== currentState) {
        undoStack.push(currentState);
        if (undoStack.length > 50) undoStack.shift();
    }
    // 内容发生变化后清空重做栈
    redoStack = [];
    markAsModified();
    console.log('[Undo] 快照提交，栈长度:', undoStack.length);
}

// 文本/细粒度输入的防抖撤销快照
let contentUndoTimer = null;
const CONTENT_UNDO_DELAY = 1000; // ms
function scheduleContentUndo() {
    if (contentUndoTimer) {
        clearTimeout(contentUndoTimer);
    }
    contentUndoTimer = setTimeout(() => {
        contentUndoTimer = null;
        commitUndoSnapshot();
    }, CONTENT_UNDO_DELAY);
}

// 通用修改后触发（结构性直接快照 + 自动保存）
function onStructuralChange() {
    commitUndoSnapshot();
    autoSave();
}

// 文本类修改（高频）触发：仅标记修改 + 延迟快照 + 自动保存
function onContentChange() {
    markAsModified();
    scheduleContentUndo();
    autoSave();
}

// 暴露到全局（供其它文件调用）
window.commitUndoSnapshot = commitUndoSnapshot;
window.onStructuralChange = onStructuralChange;
window.onContentChange = onContentChange;
window.scheduleContentUndo = scheduleContentUndo;

// 撤销操作
function undo() {
    if (undoStack.length < 1) { // 如果撤销栈中只有一个或零个元素（初始状态或空），则无法撤销
        alert('没有可撤销的操作');
        return;
    }

    // 1. 存储当前场景名称（如果存在）
    const previousSceneName = currentScene ? currentScene.scene : null;

    // 将当前状态移到重做栈 (当前状态是 undoStack 的最后一个元素)
    const currentStateToRedo = undoStack.pop();
    redoStack.push(currentStateToRedo);

    // 获取上一个状态 (现在 undoStack 的最后一个元素是我们要恢复的状态)
    // 如果 pop 后 undoStack 为空，说明我们回到了“加载文件前”的状态，这不应该发生，因为我们总是在加载后 push 一个状态
    // 但为了保险起见，检查一下
    if (undoStack.length === 0) {
        // 理论上不应该到这里，因为 initSampleData 会 push 初始状态
        // 如果真的到了这里，可能需要重新加载初始数据或置为空
        console.error("撤销栈为空，无法恢复上一个状态。");
        // 将移到重做栈的状态放回去，因为撤销失败
        undoStack.push(currentStateToRedo);
        redoStack.pop();
        alert('撤销失败：无法恢复到上一个有效状态。');
        return;
    }
    const previousState = undoStack[undoStack.length - 1];
    scriptData = JSON.parse(previousState);
    console.log("撤销到状态", scriptData);


    // 2. 尝试恢复场景选择
    currentScene = null; // 先重置
    if (previousSceneName) {
        currentScene = scriptData.find(s => s.scene === previousSceneName) || null;
    }
    // 重置节点选择 (恢复节点选择比较复杂，暂时先只恢复场景)
    currentNode = null;
    nodeParent = null;

    renderSceneList(); // 更新场景列表高亮
    renderDialogueTree(); // 重新渲染对话树 (现在 currentScene 可能已恢复)
    // 根据是否恢复了场景来决定显示哪个编辑器
    if (currentScene) {
        showSceneEditor(); // 如果场景恢复了，显示场景编辑器
    } else {
        hideAllEditors(); // 否则隐藏所有编辑器
    }
}

// 重做操作
function redo() {
    if (redoStack.length === 0) {
        alert('没有可重做的操作');
        return;
    }

    // 1. 存储当前场景名称（如果存在）
    const previousSceneName = currentScene ? currentScene.scene : null;

    // 从重做栈取出状态
    const nextStateString = redoStack.pop();
    undoStack.push(nextStateString); // 放回撤销栈

    scriptData = JSON.parse(nextStateString);
    console.log("重做到状态", scriptData);

    // 2. 尝试恢复场景选择
    currentScene = null; // 先重置
    if (previousSceneName) {
        currentScene = scriptData.find(s => s.scene === previousSceneName) || null;
    }

    // 重置节点选择
    currentNode = null;
    nodeParent = null;

    renderSceneList(); // 更新场景列表高亮
    renderDialogueTree(); // 重新渲染对话树
    // 根据是否恢复了场景来决定显示哪个编辑器
    if (currentScene) {
        showSceneEditor(); // 如果场景恢复了，显示场景编辑器
    } else {
        hideAllEditors(); // 否则隐藏所有编辑器
    }
}

// 全局变量
let currentFileName = null; // 当前打开的文件名
let autoSaveEnabled = false; // 自动保存开关
let hasUnsavedChanges = false; // 是否有未保存的修改
let lastSavedState = null; // 上次保存的状态（用于比较）
let isCheckingUnsaved = false; // 防止重复弹出保存确认

// 触发文件导入
function triggerFileImport() {
    const fileInput = getElement('import-file-input');
    fileInput.click();
}

// 处理文件上传
async function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;    if (!file.name.endsWith('.story')) {
        alert('请选择STORY文件');
        return;
    }

    // 检查是否有未保存的修改
    const canProceed = await checkAndPromptSave();
    if (!canProceed) {
        // 清空文件选择
        event.target.value = '';
        return; // 用户取消了上传
    }

    try {
        // 读取文件内容
        const fileContent = await readFileContent(file);
        const importData = JSON.parse(fileContent);

        if (!Array.isArray(importData)) {
            throw new Error('导入数据必须是数组格式');
        }

        // 上传文件到stories目录
        const formData = new FormData();
        formData.append('file', file);        const response = window.authManager ? 
            await window.authManager.makeAuthenticatedRequest('/api/upload-story', {
                method: 'POST',
                body: formData
            }) :
            await fetch('/api/upload-story', {
                method: 'POST',
                body: formData
            });

        if (!response) {
            // 认证失败，authManager已经处理重定向
            return;
        }

        const result = await response.json();
        if (result.success) {            // 更新当前文件名
            currentFileName = result.filename;
            
            // 导入数据到编辑器
            scriptData = importData;
            
            // 重新初始化ID管理器
            if (window.idManager) {
                window.idManager.initializeFromScriptData(scriptData);
                
                // 检查并修复重复ID
                const fixedCount = window.idManager.validateAndFixAllScenes(scriptData);
                if (fixedCount > 0) {
                    console.log(`文件上传时修复了 ${fixedCount} 个重复ID问题`);
                }
            }
            
            undoStack = [JSON.stringify(scriptData)];
            redoStack = [];
duxi
            currentScene = null;
            currentNode = null;
            nodeParent = null;

            // 标记为已保存状态
            markAsSaved();

            renderSceneList();
            renderDialogueTree();
            hideAllEditors();            // 刷新文件管理器
            if (window.fileManager) {
                await window.fileManager.loadStoryFiles();
            }

            console.log(`文件已上传并打开: ${result.filename}`);
            alert(`文件已上传到stories目录并打开: ${result.filename}`);
        } else {
            throw new Error(result.message || '上传失败');
        }
    } catch (error) {
        console.error('导入失败:', error);
        alert('导入失败: ' + error.message);
    }

    // 清空文件选择
    event.target.value = '';
}

// 读取文件内容
function readFileContent(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = (e) => reject(new Error('文件读取失败'));
        reader.readAsText(file);
    });
}

// 保存当前文件
async function saveCurrentFile(showSuccessMessage = false) {
    if (!currentFileName) {
        alert('没有打开的文件，请先导入或创建文件');
        return;
    }

    try {
        // 使用认证管理器的请求方法
        const response = window.authManager ? 
            await window.authManager.makeAuthenticatedRequest('/api/save-story', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    filename: currentFileName,
                    data: scriptData,
                    projectName: window.fileManager.currentProject
                })
            }) :
            await fetch('/api/save-story', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    filename: currentFileName,
                    data: scriptData,
                    projectName: window.fileManager.currentProject
                })
            });

        if (!response) {
            // 认证失败，authManager已经处理重定向
            return;
        }

        const result = await response.json();
        if (result.success) {
            console.log(`文件已保存: ${currentFileName}`);
            markAsSaved(); // 标记为已保存
            
            // 根据参数决定是否显示成功消息
            if (showSuccessMessage) {
                alert(`文件已保存: ${currentFileName}`);
            }
        } else {
            throw new Error(result.message || '保存失败');
        }
    } catch (error) {
        console.error('保存失败:', error);
        alert('保存失败: ' + error.message);
        throw error; // 重新抛出错误，让调用者知道保存失败
    }
}

// 处理自动保存切换
function toggleAutoSave() {
    autoSaveEnabled = !autoSaveEnabled;
    updateAutoSaveButton();
    saveAutoSaveState();
    
    console.log('自动保存', autoSaveEnabled ? '已开启' : '已关闭');
    
    if (autoSaveEnabled && currentFileName) {
        // 如果开启自动保存且有当前文件，立即保存一次
        saveCurrentFile();
    }
}

// 更新自动保存按钮显示
function updateAutoSaveButton() {
    const btn = getElement('auto-save-btn');
    if (autoSaveEnabled) {
        btn.textContent = '✅自动保存-ON';
    } else {
        btn.textContent = '🚫自动保存-OFF';
    }
}

// 保存自动保存状态到本地缓存
function saveAutoSaveState() {
    localStorage.setItem('autoSaveEnabled', autoSaveEnabled.toString());
}

// 从本地缓存加载自动保存状态
function loadAutoSaveState() {
    const saved = localStorage.getItem('autoSaveEnabled');
    if (saved !== null) {
        autoSaveEnabled = saved === 'true';
    }
    updateAutoSaveButton();
}

// 自动保存（在编辑框失焦时调用）
function autoSave() {
    if (!currentFileName) {
        return; // 没有当前文件，不保存
    }
    
    if (autoSaveEnabled) {
        saveCurrentFile().then(() => {
            // 显示保存成功指示器
            showSaveSuccessIndicator();
        }).catch(error => {
            console.error('自动保存失败:', error);
        });
    }
}

// 显示保存成功指示器
function showSaveSuccessIndicator() {
    // 检查是否已存在指示器，避免重复创建
    let existingIndicator = document.querySelector('.save-success-indicator');
    if (existingIndicator) {
        existingIndicator.remove();
    }
    
    const saveIndicator = document.createElement('div');
    saveIndicator.className = 'save-success-indicator';
    saveIndicator.textContent = '✅ 已保存到文件';
    saveIndicator.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background-color: #4CAF50;
        color: white;
        padding: 10px 15px;
        border-radius: 4px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        z-index: 1000;
        font-size: 14px;
        animation: fadeInOut 3s forwards;
    `;
    
    // 添加CSS动画样式（如果不存在）
    if (!document.querySelector('#save-indicator-styles')) {
        const style = document.createElement('style');
        style.id = 'save-indicator-styles';
        style.textContent = `
            @keyframes fadeInOut {
                0% { opacity: 0; transform: translateY(20px); }
                15% { opacity: 1; transform: translateY(0); }
                85% { opacity: 1; transform: translateY(0); }
                100% { opacity: 0; transform: translateY(-20px); }
            }
        `;
        document.head.appendChild(style);
    }
    
    document.body.appendChild(saveIndicator);
    
    // 3秒后移除指示器
    setTimeout(() => {
        if (saveIndicator.parentNode) {
            saveIndicator.parentNode.removeChild(saveIndicator);
        }
    }, 3000);
}

// 设置当前文件名（在文件管理器中选择文件时调用）
function setCurrentFileName(filename) {
    currentFileName = filename;
    console.log('当前文件:', currentFileName);
}

// 标记数据为已修改
function markAsModified() {
    if (!hasUnsavedChanges) {
        hasUnsavedChanges = true;
        updateWindowTitle();
    }
}

// 标记数据为已保存
function markAsSaved() {
    hasUnsavedChanges = false;
    lastSavedState = JSON.stringify(scriptData);
    updateWindowTitle();
}

// 检查是否有未保存的修改
function checkUnsavedChanges() {
    if (!lastSavedState) return false;
    const currentState = JSON.stringify(scriptData);
    return currentState !== lastSavedState;
}

// 更新窗口标题显示修改状态
function updateWindowTitle() {
    const baseTitle = '对话编辑器';
    if (currentFileName) {
        document.title = `${baseTitle} - ${currentFileName}${hasUnsavedChanges ? ' *' : ''}`;
    } else {
        document.title = baseTitle;
    }
}

// 检查并提示保存未保存的修改
async function checkAndPromptSave() {
    if (!hasUnsavedChanges || !currentFileName) {
        return true; // 没有未保存修改或没有当前文件，允许继续
    }
    
    if (isCheckingUnsaved) {
        return false; // 已经在检查中，防止重复弹出
    }
    
    isCheckingUnsaved = true;
    
    try {
        const result = confirm(`文件 "${currentFileName}" 有未保存的修改。\n\n是否要保存？\n\n点击"确定"保存，点击"取消"放弃修改。`);
        
        if (result) {
            try {
                await saveCurrentFile();
                return true; // 保存成功，允许继续
            } catch (error) {
                alert('保存失败，请重试');
                return false; // 保存失败，阻止切换
            }
        } else {
            // 用户选择不保存，直接继续
            return true;
        }
    } finally {
        isCheckingUnsaved = false;
    }
}