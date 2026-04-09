<template>
    <div class="settings-section">
        <div class="section-header">
            <h3>模型用途配置</h3>
            <n-button class="rank-link" text tag="a" href="https://openlm.ai/chatbot-arena/" target="_blank" rel="noopener noreferrer" type="primary" size="small">
                <template #icon><n-icon><TrophyOutline /></n-icon></template>

            </n-button>
        </div>
        <p class="section-desc">创建管理用途并分配各自的平台与模型</p>

        <div v-if="loading" class="loading-state">
            <n-spin size="large" />
        </div>

        <div v-else class="usage-list">
            <div v-for="usage in usageSelections" :key="usage.usage_key" class="usage-item">
                <div class="usage-header">
                    <div class="usage-info">
                        <span class="usage-label">{{ usage.usage_label }}</span>
                        <span class="usage-key">{{ usage.usage_key }}</span>
                    </div>
                    <n-space :size="6" class="usage-actions">
                        <n-button class="usage-action-btn" size="tiny" secondary strong @click="openEditUsageModal(usage)" :disabled="isBuiltinUsage(usage.usage_key)">编辑</n-button>
                        <n-button class="usage-action-btn" size="tiny" secondary strong type="error" @click="deleteUsage(usage)" :disabled="isBuiltinUsage(usage.usage_key)">删除</n-button>
                    </n-space>
                </div>

                <div class="usage-controls">
                    <div class="usage-control">
                        <n-select
                            v-model:value="usage.platform_id"
                            :options="platformOptions"
                            placeholder="选择平台"
                            @update:value="(val) => handlePlatformChange(usage, val)"
                            class="platform-select"
                            size="small"
                        />
                    </div>

                    <div class="usage-control">
                        <n-select
                            v-model:value="usage.model_id"
                            :options="getModelsForPlatform(usage.platform_id)"
                            placeholder="选择模型"
                            :disabled="!usage.platform_id"
                            @update:value="(val) => handleModelChange(usage, val)"
                            class="model-select"
                            size="small"
                        />
                    </div>
                </div>
                
                <div v-if="usage.missing_key" class="api-key-warning">
                    <SparkAlert type="warning" title="未配置 API Key" action-text="去配置" @action="scrollToPlatformManager">
                        当前选择的平台尚未配置 API Key，模型可能无法正常工作。
                    </SparkAlert>
                </div>
            </div>

            <!-- 添加新用途 -->
            <div class="add-usage-box">
                <n-button dashed block @click="showAddUsageModal = true">
                    <template #icon><n-icon><Add /></n-icon></template>
                    添加新用途
                </n-button>
            </div>
        </div>

        <n-modal v-model:show="showAddUsageModal">
            <n-card style="width: 600px" title="添加新用途" :bordered="false" size="huge" role="dialog" aria-modal="true">
                <n-form>
                    <n-form-item label="用途标识 (Key)">
                        <n-input v-model:value="newUsage.key" placeholder="例如: translation, coding..." />
                    </n-form-item>
                    <n-form-item label="显示名称 (Label)">
                        <n-input v-model:value="newUsage.label" placeholder="例如: 翻译模型" />
                    </n-form-item>
                    <n-form-item label="默认平台">
                        <n-select 
                            v-model:value="newUsage.platformId" 
                            :options="platformOptions" 
                            @update:value="handleNewUsagePlatformChange"
                        />
                    </n-form-item>
                    <n-form-item label="默认模型">
                        <n-select 
                            v-model:value="newUsage.modelId" 
                            :options="getModelsForPlatform(newUsage.platformId)" 
                            :disabled="!newUsage.platformId"
                        />
                    </n-form-item>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showAddUsageModal = false">取消</n-button>
                        <n-button type="primary" @click="handleAddUsage" :loading="addingUsage">创建</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>

        <!-- 编辑用途弹窗 -->
        <n-modal v-model:show="showEditUsageModal">
            <n-card style="width: 520px" title="编辑用途" :bordered="false" size="huge" role="dialog" aria-modal="true">
                <n-form>
                    <n-form-item label="用途标识 (Key)" description="用途标识不可随意修改，若需替换请新建用途并删除旧用途。">
                        <n-input v-model:value="editingUsage.usage_key" disabled />
                    </n-form-item>
                    <n-form-item label="显示名称 (Label)">
                        <n-input v-model:value="editingUsage.usage_label" />
                    </n-form-item>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showEditUsageModal = false">取消</n-button>
                        <n-button type="primary" @click="handleUpdateUsage">保存</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { NSpin, NButton, NIcon, NSpace, NFormItem, NSelect, NModal, NCard, NForm, NInput, useMessage, useDialog } from 'naive-ui';
import SparkAlert from '../share/SparkAlert.vue';
import { Add, TrophyOutline } from '@vicons/ionicons5';
import { createUserUsageSlot, deleteUserUsageSlot, renameUserUsageSlot } from '../../services/api';
import { useAiStore } from '../stores/aiStore';

const message = useMessage();
const dialog = useDialog();
const aiStore = useAiStore();

const loading = computed(() => aiStore.loading);

watch(loading, (isLoading) => {
    if (!isLoading) {
        checkAndFixUsages();
    }
}, { immediate: true });

async function checkAndFixUsages() {
    const usages = aiStore.usageSelections;
    const pOptions = platformOptions.value;
    
    if (!usages || usages.length === 0) return;
    
    for (const usage of usages) {
        let pId = usage.platform_id;
        let mId = usage.model_id;

        const platformExists = pId ? pOptions.some(p => p.value === pId) : false;
        let models = platformExists ? getModelsForPlatform(pId) : null;
        const modelExists = mId && models ? models.some(m => m.value === mId) : false;

        const needFix = (pId && !platformExists) || (platformExists && (!mId || !modelExists));
        
        if (needFix) {
            if (!pId || !platformExists) {
                if (pOptions.length > 0) {
                    pId = pOptions[0].value;
                    const fallbackModels = getModelsForPlatform(pId);
                    mId = fallbackModels && fallbackModels.length > 0 ? fallbackModels[0].value : null;
                } else {
                    pId = null;
                    mId = null;
                }
            } else {
                mId = models && models.length > 0 ? models[0].value : null;
            }

            if (pId !== usage.platform_id || mId !== usage.model_id) {
                const updateUsage = { ...usage, platform_id: pId, model_id: mId };
                try {
                    await aiStore.updateSelection(updateUsage.usage_key, updateUsage.platform_id ?? '', updateUsage.model_id ?? '');
                } catch (e) {
                    console.error('Failed to auto-fix usage:', e);
                }
            }
        }
    }
}

function scrollToPlatformManager() {
    const container = document.querySelector('.content-area');
    if (container) container.scrollTop = 0;
}

const usageSelections = computed(() => aiStore.usageSelections);
const platformOptions = computed(() => aiStore.platformOptions);

const showAddUsageModal = ref(false);
const showEditUsageModal = ref(false);
const addingUsage = ref(false);

const newUsage = ref<{ key: string; label: string; platformId: string | null; modelId: string | null }>({
    key: '',
    label: '',
    platformId: null,
    modelId: null
});

const editingUsage = ref({ usage_key: '', usage_label: '' });

function getModelsForPlatform(platformId: string | null) {
    return aiStore.getModelsForPlatform(platformId || '');
}

async function loadData() {
    await aiStore.loadData(true, true);
}

async function handlePlatformChange(usage, platformId: string | null) {
    usage.platform_id = platformId;
    const models = aiStore.getModelsForPlatform(platformId || '');
    
    if (models && models.length > 0) {
        usage.model_id = models[0].value;
        await saveSelection(usage);
    } else {
        usage.model_id = null;
    }
}

async function handleModelChange(usage, modelId) {
    usage.model_id = modelId;
    await saveSelection(usage);
}

async function saveSelection(usage) {
    try {
        await aiStore.updateSelection(usage.usage_key, usage.platform_id, usage.model_id);
        message.success(`已更新 ${usage.usage_label} 的模型设置`);
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
        message.error(errorMessage);
    }
}

async function handleAddUsage() {
    if (!newUsage.value.key || !newUsage.value.platformId || !newUsage.value.modelId) {
        message.warning('请填写完整信息');
        return;
    }
    
    addingUsage.value = true;
    try {
        await createUserUsageSlot(newUsage.value.key, newUsage.value.label, newUsage.value.platformId, newUsage.value.modelId);
        message.success('创建成功');
        showAddUsageModal.value = false;
        newUsage.value = { key: '', label: '', platformId: null, modelId: null };
        await loadData();
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
        message.error(errorMessage);
    } finally {
        addingUsage.value = false;
    }
}

function handleNewUsagePlatformChange(platformId) {
    newUsage.value.platformId = platformId;
    const models = getModelsForPlatform(platformId);
    if (models && models.length > 0) {
        newUsage.value.modelId = models[0].value;
    } else {
        newUsage.value.modelId = null;
    }
}

function isBuiltinUsage(key) {
    const builtin = ['main', 'fast', 'reason'];
    return builtin.includes((key || '').toString().trim().toLowerCase());
}

function openEditUsageModal(usage) {
    editingUsage.value = { usage_key: usage.usage_key, usage_label: usage.usage_label };
    showEditUsageModal.value = true;
}

async function handleUpdateUsage() {
    if (!editingUsage.value.usage_key) return;
    try {
        await renameUserUsageSlot(editingUsage.value.usage_key, null, editingUsage.value.usage_label);
        message.success('用途已更新');
        showEditUsageModal.value = false;
        await loadData();
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
        message.error(errorMessage);
    }
}

async function deleteUsage(usage) {
    if (isBuiltinUsage(usage.usage_key)) {
        message.warning('内置用途无法删除');
        return;
    }
    dialog.error({
        title: '删除用途',
        content: `确定要删除用途 "${usage.usage_label}" (${usage.usage_key}) 吗？此操作会移除该用途的模型绑定。`,
        positiveText: '删除',
        negativeText: '取消',
        onPositiveClick: async () => {
            try {
                await deleteUserUsageSlot(usage.usage_key);
                message.success('删除成功');
                await loadData();
            } catch (e: unknown) {
                const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
                message.error(errorMessage);
            }
        }
    });
}
</script>

<style scoped>
.settings-section {
    background: var(--spark-panel-bg);
    border: 1px solid var(--spark-border);
    border-radius: var(--spark-radius);
    padding: var(--spark-panel-padding);
    margin-bottom: 20px;
}

.section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 8px;
}

.rank-link {
    height: 28px;
    display: inline-flex;
    align-items: center;
    padding: 0 10px;
    line-height: 28px;
    align-self: center;
    transform: translateY(-5px);
}

.settings-section h3 {
    margin: 0;
    font-size: 18px;
    color: var(--spark-primary);
    line-height: 28px;
    display: inline-flex;
    align-items: center;
    -webkit-user-select: none;
    user-select: none;
    cursor: default;
}

.section-desc {
    color: var(--spark-text-muted);
    margin-bottom: 14px;
    font-size: 14px;
}

.usage-list {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0;
}

.usage-item {
    padding: 12px 0 14px;
}

.usage-item + .usage-item {
    border-top: 1px solid color-mix(in srgb, var(--spark-border), transparent 10%);
}

.usage-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 10px;
}

.usage-info {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    min-width: 0;
}

.usage-label {
    display: inline-flex;
    align-items: center;
    min-height: 24px;
    padding: 0 10px;
    border-radius: 999px;
    background: var(--spark-primary-container);
    color: var(--spark-primary);
    font-weight: 700;
    font-size: 13px;
    line-height: 1;
}

.usage-key {
    display: inline-flex;
    align-items: center;
    min-height: 22px;
    padding: 0 8px;
    border-radius: 999px;
    border: 1px dashed var(--spark-border);
    background: color-mix(in srgb, var(--spark-bg), transparent 12%);
    font-family: var(--spark-mono);
    font-size: 11px;
    color: var(--spark-text-muted);
}

.usage-actions {
    margin-left: auto;
    flex-shrink: 0;
}

.usage-action-btn {
    font-size: 11px;
    height: 24px;
    padding: 0 8px;
}

.usage-controls {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.usage-control {
    min-width: 0;
}

.usage-control :deep(.n-base-selection) {
    width: 100%;
    font-size: 12px;
    min-height: 30px;
}

.usage-control :deep(.n-base-selection-label) {
    height: 30px;
    line-height: 30px;
}

.add-usage-box {
    margin-top: 12px;
}

.loading-state {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 200px;
}

@media (max-width: 768px) {
    .settings-section {
        padding: 4px 12px;
        margin-bottom: 8px;
        background: transparent;
        border: none;
        border-radius: 0;
    }

    .usage-header {
        flex-direction: column;
        align-items: stretch;
    }

    .usage-actions {
        margin-left: 0;
    }

}
</style>
