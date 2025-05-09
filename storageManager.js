// 初始化示例数据
function initSampleData() {
  const sampleData = [
      {
        "scene": "序章-医院",
        "cap": "前往那未知的死亡...",
        "pgrs": 0,
        "dia": [
          {
            "id": 10001,
            "chr": 1,
            "txt": "我这是...死了吗..."
          },
          {
            "id": 10002,
            "chr": 0,
            "txt": "我究竟在哪里",
            "opt": [
              {
                "optn": "去死的路上",
                "dia": [
                  {
                    "id": 10003,
                    "chr": 0,
                    "txt": "啊 果然还是到了这一天吗",
                    "act": {}
                  },
                  {
                    "id": 10004,
                    "chr": 0,
                    "txt": "真是遗憾啊",
                    "opt": [
                      {
                        "optn": "其实也没什么遗憾",
                        "dia": [
                          {
                            "id": 100010,
                            "chr": 0,
                            "txt": "毕竟我就一NPC"
                          }
                        ]
                      },
                      {
                        "optn": "确实有好多遗憾啊",
                        "dia": [
                          {
                            "id": 100011, // 修复示例数据中的重复ID
                            "chr": 0,
                            "txt": "我还有未竟之事"
                          }
                        ]
                      }
                    ],
                    "act": {}
                  }
                ]
              },
              {
                "optn": "已经死了",
                "dia": [
                  {
                    "id": 10005,
                    "chr": 0,
                    "txt": "好吧 已经死了"
                  },
                  {
                    "id": 10006,
                    "chr": 0,
                    "txt": "那我的故事结束了"
                  }
                ]
              }
            ]
          },
          {
            "id": 10007, // 修复示例数据中的重复ID
            "chr": 0,
            "txt": "另一个顶层对话",
            "act": {
              "exit": ""
            },
            "next": "ggg"
          }
        ]
      }
  ];

  scriptData = sampleData;
  undoStack = [];
  redoStack = []; // 清空重做栈
  renderSceneList();
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
    if (undoStack.length < 1) {
        alert('没有可撤销的操作');
        return;
    }

    // 1. 存储当前场景名称（如果存在）
    const previousSceneName = currentScene ? currentScene.scene : null;

    // 获取上一个状态
    const previousState = undoStack[undoStack.length-1];
    scriptData = JSON.parse(previousState);
    console.log("撤销到状态",scriptData);

    // 将当前状态移到重做栈
    const currentState = undoStack.pop();
    redoStack.push(currentState);
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
    const nextState = redoStack.pop();
    undoStack.push(nextState); // 放回撤销栈

    scriptData = JSON.parse(nextState);

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