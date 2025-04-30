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
                              "id": 100010,
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
              "id": 10003,
              "chr": 0,
              "txt": "新对话内容",
              "act": {
                "exit": ""
              },
              "next": "ggg"
            }
          ]
        }
    ];
    
    scriptData = sampleData;
    saveToUndo();
    renderSceneList();
}

// 递归查找最大对话ID
function findMaxDialogueId(dialogues, maxId, callback) {
    if (!dialogues) return;
    
    dialogues.forEach(d => {
        if (d.id > maxId) {
            callback(d.id);
        }
        
        if (d.opt) {
            d.opt.forEach(o => {
                if (o.dia) {
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
        
        saveToUndo();
        scriptData = importData;
        currentScene = null;
        currentNode = null;
        
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
    const modalContent = getElement('modal-content');
    
    modalContent.innerHTML = '';
    
    const title = document.createElement('h3');
    title.textContent = '导出对话脚本';
    modalContent.appendChild(title);
    
    const textarea = document.createElement('textarea');
    textarea.value = exportText;
    textarea.style.width = '100%';
    textarea.style.height = '300px';
    textarea.style.fontFamily = 'monospace';
    textarea.style.padding = '10px';
    textarea.style.marginBottom = '15px';
    modalContent.appendChild(textarea);
    
    const copyBtn = document.createElement('button');
    copyBtn.textContent = '复制到剪贴板';
    copyBtn.addEventListener('click', () => {
        textarea.select();
        document.execCommand('copy');
        alert('已复制到剪贴板');
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
    undoStack.push(currentState);
    
    // 限制撤销栈大小
    if (undoStack.length > 50) {
        undoStack.shift();
    }
}

// 撤销操作
function undo() {
    if (undoStack.length <= 1) {
        alert('没有可撤销的操作');
        return;
    }
    
    // 移除当前状态
    undoStack.pop();
    
    // 获取上一个状态
    const previousState = undoStack[undoStack.length - 1];
    scriptData = JSON.parse(previousState);
    
    // 重置选择
    currentScene = null;
    currentNode = null;
    
    renderSceneList();
    renderDialogueTree();
    hideAllEditors();
}