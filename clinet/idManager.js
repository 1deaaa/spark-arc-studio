// ID管理器 - 确保对话ID在单个场景内不重复
class IdManager {
    constructor() {
        this.nextNodeId = 10001; // 全局ID计数器
    }

    // 初始化ID管理器，扫描所有场景找出最大ID
    initializeFromScriptData(scriptData) {
        let maxId = 10000;
        
        if (scriptData && Array.isArray(scriptData)) {
            scriptData.forEach(scene => {
                this.findMaxIdInDialogues(scene.dia, (id) => {
                    if (id > maxId) {
                        maxId = id;
                    }
                });
            });
        }
        
        this.nextNodeId = maxId + 1;
        console.log('ID管理器初始化完成，下一个ID:', this.nextNodeId);
    }

    // 递归查找对话数组中的最大ID
    findMaxIdInDialogues(dialogues, callback) {
        if (!dialogues || !Array.isArray(dialogues)) return;

        dialogues.forEach(dialogue => {
            const currentId = parseInt(dialogue.id, 10);
            if (!isNaN(currentId)) {
                callback(currentId);
            }

            // 递归搜索选项中的对话
            if (dialogue.opt && Array.isArray(dialogue.opt)) {
                dialogue.opt.forEach(option => {
                    if (option.dia && Array.isArray(option.dia)) {
                        this.findMaxIdInDialogues(option.dia, callback);
                    }
                });
            }
        });
    }

    // 生成新的唯一ID
    generateNewId() {
        return this.nextNodeId++;
    }

    // 检查指定场景中是否存在重复ID
    checkDuplicateIdsInScene(scene) {
        const ids = new Set();
        const duplicates = [];

        this.collectIdsFromDialogues(scene.dia, ids, duplicates, scene.scene);
        
        return {
            hasDuplicates: duplicates.length > 0,
            duplicates: duplicates,
            allIds: Array.from(ids)
        };
    }

    // 递归收集对话ID并检测重复
    collectIdsFromDialogues(dialogues, idsSet, duplicates, sceneName) {
        if (!dialogues || !Array.isArray(dialogues)) return;

        dialogues.forEach((dialogue, index) => {
            const id = dialogue.id;
            if (id !== undefined && id !== null) {
                if (idsSet.has(id)) {
                    duplicates.push({
                        id: id,
                        scene: sceneName,
                        dialogue: dialogue,
                        index: index
                    });
                } else {
                    idsSet.add(id);
                }
            }

            // 递归检查选项中的对话
            if (dialogue.opt && Array.isArray(dialogue.opt)) {
                dialogue.opt.forEach(option => {
                    if (option.dia && Array.isArray(option.dia)) {
                        this.collectIdsFromDialogues(option.dia, idsSet, duplicates, sceneName);
                    }
                });
            }
        });
    }

    // 检查所有场景的ID重复情况
    checkAllScenesForDuplicates(scriptData) {
        const results = [];
        
        if (scriptData && Array.isArray(scriptData)) {
            scriptData.forEach(scene => {
                const sceneResult = this.checkDuplicateIdsInScene(scene);
                if (sceneResult.hasDuplicates) {
                    results.push({
                        scene: scene.scene,
                        ...sceneResult
                    });
                }
            });
        }
        
        return results;
    }

    // 自动修复场景中的重复ID
    fixDuplicateIdsInScene(scene) {
        const usedIds = new Set();
        let fixedCount = 0;

        this.fixIdsInDialogues(scene.dia, usedIds, () => {
            fixedCount++;
        });

        return fixedCount;
    }

    // 递归修复对话数组中的重复ID
    fixIdsInDialogues(dialogues, usedIds, onFixed) {
        if (!dialogues || !Array.isArray(dialogues)) return;

        dialogues.forEach(dialogue => {
            const currentId = dialogue.id;
            
            if (currentId !== undefined && currentId !== null) {
                if (usedIds.has(currentId)) {
                    // 发现重复ID，生成新的唯一ID
                    const newId = this.generateNewId();
                    dialogue.id = newId;
                    usedIds.add(newId);
                    onFixed();
                    console.log(`修复重复ID: ${currentId} -> ${newId}`);
                } else {
                    usedIds.add(currentId);
                }
            } else {
                // 如果没有ID，分配一个新的
                const newId = this.generateNewId();
                dialogue.id = newId;
                usedIds.add(newId);
                onFixed();
                console.log(`分配新ID: ${newId}`);
            }

            // 递归处理选项中的对话
            if (dialogue.opt && Array.isArray(dialogue.opt)) {
                dialogue.opt.forEach(option => {
                    if (option.dia && Array.isArray(option.dia)) {
                        this.fixIdsInDialogues(option.dia, usedIds, onFixed);
                    }
                });
            }
        });
    }

    // 为新创建的对话生成场景内唯一ID
    generateUniqueIdForScene(scene) {
        const sceneCheck = this.checkDuplicateIdsInScene(scene);
        const usedIds = new Set(sceneCheck.allIds);
        
        let newId = this.generateNewId();
        while (usedIds.has(newId)) {
            newId = this.generateNewId();
        }
        
        return newId;
    }

    // 验证并修复所有场景的ID问题
    validateAndFixAllScenes(scriptData) {
        let totalFixed = 0;
        
        if (scriptData && Array.isArray(scriptData)) {
            scriptData.forEach(scene => {
                const fixedInScene = this.fixDuplicateIdsInScene(scene);
                totalFixed += fixedInScene;
                
                if (fixedInScene > 0) {
                    console.log(`场景 "${scene.scene}" 修复了 ${fixedInScene} 个重复ID`);
                }
            });
        }
        
        return totalFixed;
    }
}

// 创建全局ID管理器实例
window.idManager = new IdManager();
