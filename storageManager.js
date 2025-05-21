// 初始化数据，尝试从 对话.json 加载
async function initSampleData() {
  try {
    const response = await fetch('对话.json');
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const jsonData = await response.json();
    scriptData = jsonData;
    console.log("成功加载 对话.json");
  } catch (error) {
    console.error("无法加载 对话.json，将使用空数据初始化:", error);
    // 如果加载失败，使用空数组初始化或提供一个最小化的默认结构
    scriptData = [];
    // 你也可以在这里选择加载一个内置的最小化示例数据，以防文件不存在或格式错误
    // scriptData = [ { scene: "默认场景", cap: "这是一个默认场景", pgrs: 0, dia: [] } ];
    alert("无法加载 对话.json 文件。请确保文件存在于应用根目录且格式正确。\n将使用空数据进行初始化。");
  }

  undoStack = [JSON.stringify(scriptData)]; // 初始状态存入撤销栈
  redoStack = []; // 清空重做栈
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
function importScript() {
  const importText = getElement('import-text').value;

  try {
      const importData = JSON.parse(importText);

      if (!Array.isArray(importData)) {
          throw new Error('导入数据必须是数组格式');
      }

      // 导入时清空撤销/重做栈，并将新数据作为初始状态
      scriptData = importData;
      undoStack = [JSON.stringify(scriptData)];
      redoStack = [];

      currentScene = null;
      currentNode = null;
      nodeParent = null;

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
  downloadBtn.addEventListener('click', () => {
      const blob = new Blob([exportText], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'dialogue_script.json';
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
}

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