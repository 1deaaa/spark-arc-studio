// 精简版 ID 管理器：仅保证“同一场景内”不重复，起始基值 10000
class IdManager {
    constructor(base = 10000) {
        this.base = base; // 场景无任何对话时第一个ID = base
    }

    // 初始化：现在无需全局扫描，保留接口兼容
    initializeFromScriptData(_scriptData) {
        console.log('[IdManager] 初始化（精简版）：按场景独立分配');
    }

    // 收集场景内所有 ID
    collectIdsInScene(scene) {
        const ids = new Set();
        const walkDialogues = (arr) => {
            if (!Array.isArray(arr)) return;
            arr.forEach(d => {
                if (d && d.id !== undefined && d.id !== null && !isNaN(parseInt(d.id, 10))) {
                    ids.add(parseInt(d.id, 10));
                }
                if (d && Array.isArray(d.opt)) {
                    d.opt.forEach(o => o && Array.isArray(o.dia) && walkDialogues(o.dia));
                }
            });
        };
        if (scene && Array.isArray(scene.dia)) walkDialogues(scene.dia);
        return ids;
    }

    // 获取场景内当前最大 ID（若无节点返回 base-1 以便下一个=base）
    getMaxIdInScene(scene) {
        const ids = this.collectIdsInScene(scene);
        if (ids.size === 0) return this.base - 1;
        return Math.max(...ids);
    }

    // 生成场景内唯一 ID（不依赖全局自增）
    generateUniqueIdForScene(scene) {
        const maxId = this.getMaxIdInScene(scene);
        return maxId + 1 < this.base ? this.base : maxId + 1; // 确保不低于 base
    }

    // 修复单个场景的重复 ID：第一次出现的保留，后续重复重新分配
    fixDuplicateIdsInScene(scene) {
        if (!scene || !Array.isArray(scene.dia)) return 0;
        const seen = new Set();
        let fixed = 0;
        const reassign = (arr) => {
            arr.forEach(d => {
                if (!d) return;
                const rawId = parseInt(d.id, 10);
                if (isNaN(rawId)) {
                    d.id = this.generateUniqueIdForScene(scene);
                    seen.add(d.id); fixed++; return;
                }
                if (seen.has(rawId)) {
                    d.id = this.generateUniqueIdForScene(scene);
                    seen.add(d.id); fixed++; 
                } else {
                    seen.add(rawId);
                }
                if (Array.isArray(d.opt)) {
                    d.opt.forEach(o => o && Array.isArray(o.dia) && reassign(o.dia));
                }
            });
        };
        reassign(scene.dia);
        return fixed;
    }

    // 兼容旧接口：仅逐场景调用 fixDuplicateIdsInScene
    validateAndFixAllScenes(scriptData) {
        if (!Array.isArray(scriptData)) return 0;
        let total = 0;
        scriptData.forEach(sc => { total += this.fixDuplicateIdsInScene(sc); });
        if (total > 0) console.log(`[IdManager] 修复重复ID计数: ${total}`);
        return total;
    }
}

window.idManager = new IdManager(10000);
