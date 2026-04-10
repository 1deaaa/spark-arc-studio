<template>
    <div class="settings-section">
        <div class="section-header">
            <h3>{{ t('components.modelUsageManager.title') }}</h3>
            <n-button class="rank-link" text tag="a" href="https://openlm.ai/chatbot-arena/" target="_blank" rel="noopener noreferrer" type="primary" size="small">
                <template #icon><n-icon><TrophyOutline /></n-icon></template>

            </n-button>
        </div>
        <p class="section-desc">{{ t('components.modelUsageManager.subtitle') }}</p>

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
                        <n-button class="usage-action-btn" size="tiny" secondary strong @click="openEditUsageModal(usage)" :disabled="isBuiltinUsage(usage.usage_key)">{{ t('components.modelUsageManager.edit') }}</n-button>
                        <n-button class="usage-action-btn" size="tiny" secondary strong type="error" @click="deleteUsage(usage)" :disabled="isBuiltinUsage(usage.usage_key)">{{ t('views.common.delete') }}</n-button>
                    </n-space>
                </div>

                <div class="usage-controls">
                    <div class="usage-control">
                        <n-select
                            v-model:value="usage.platform_id"
                            :options="platformOptions"
                            :placeholder="t('components.modelUsageManager.selectPlatform')"
                            @update:value="(val) => handlePlatformChange(usage, val)"
                            class="platform-select"
                            size="small"
                        />
                    </div>

                    <div class="usage-control">
                        <n-select
                            v-model:value="usage.model_id"
                            :options="getModelsForPlatform(usage.platform_id)"
                            :placeholder="t('components.modelUsageManager.selectModel')"
                            :disabled="!usage.platform_id"
                            @update:value="(val) => handleModelChange(usage, val)"
                            class="model-select"
                            size="small"
                        />
                    </div>
                </div>
                
                <div v-if="usage.missing_key" class="api-key-warning">
                    <SparkAlert type="warning" :title="t('components.modelUsageManager.apiKeyMissingTitle')">
                        {{ t('components.modelUsageManager.apiKeyMissingDesc') }}
                    </SparkAlert>
                </div>
            </div>

            <!-- 添加新用途 -->
            <div class="add-usage-box">
                <n-button dashed block @click="showAddUsageModal = true">
                    <template #icon><n-icon><Add /></n-icon></template>
                    {{ t('components.modelUsageManager.addUsage') }}
                </n-button>
            </div>
        </div>

        <n-modal v-model:show="showAddUsageModal">
            <n-card style="width: 600px" :title="t('components.modelUsageManager.addUsage')" :bordered="false" size="huge" role="dialog" aria-modal="true">
                <n-form>
                    <n-form-item :label="t('components.modelUsageManager.usageKey')">
                        <n-input v-model:value="newUsage.key" :placeholder="t('components.modelUsageManager.usageKeyPlaceholder')" />
                    </n-form-item>
                    <n-form-item :label="t('components.modelUsageManager.usageLabel')">
                        <n-input v-model:value="newUsage.label" :placeholder="t('components.modelUsageManager.usageLabelPlaceholder')" />
                    </n-form-item>
                    <n-form-item :label="t('components.modelUsageManager.defaultPlatform')">
                        <n-select 
                            v-model:value="newUsage.platformId" 
                            :options="platformOptions" 
                            @update:value="handleNewUsagePlatformChange"
                        />
                    </n-form-item>
                    <n-form-item :label="t('components.modelUsageManager.defaultModel')">
                        <n-select 
                            v-model:value="newUsage.modelId" 
                            :options="getModelsForPlatform(newUsage.platformId)" 
                            :disabled="!newUsage.platformId"
                        />
                    </n-form-item>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showAddUsageModal = false">{{ t('views.common.cancel') }}</n-button>
                        <n-button type="primary" @click="handleAddUsage" :loading="addingUsage">{{ t('views.common.create') }}</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>

        <!-- 编辑用途弹窗 -->
        <n-modal v-model:show="showEditUsageModal">
            <n-card style="width: 520px" :title="t('components.modelUsageManager.editUsage')" :bordered="false" size="huge" role="dialog" aria-modal="true">
                <n-form>
                    <n-form-item :label="t('components.modelUsageManager.usageKey')" :description="t('components.modelUsageManager.usageKeyImmutable')">
                        <n-input v-model:value="editingUsage.usage_key" disabled />
                    </n-form-item>
                    <n-form-item :label="t('components.modelUsageManager.usageLabel')">
                        <n-input v-model:value="editingUsage.usage_label" />
                    </n-form-item>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showEditUsageModal = false">{{ t('views.common.cancel') }}</n-button>
                        <n-button type="primary" @click="handleUpdateUsage">{{ t('views.common.save') }}</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { NSpin, NButton, NIcon, NSpace, NFormItem, NSelect, NModal, NCard, NForm, NInput, useMessage, useDialog } from 'naive-ui';
import SparkAlert from '../share/SparkAlert.vue';
import { Add, TrophyOutline } from '@vicons/ionicons5';
import { createUserUsageSlot, deleteUserUsageSlot, renameUserUsageSlot } from '../../services/api';
import { useAiStore } from '../stores/aiStore';

const message = useMessage();
const dialog = useDialog();
const { t } = useI18n();
const aiStore = useAiStore();

const loading = computed(() => aiStore.loading);

watch(loading, (isLoading) => {
    if (!isLoading) {
        checkAndFixUsages();
    }
}, { immediate: true });

async function checkAndFixUsages() {
    const usages = aiStore.usageSelections;
    const pOptions = aiStore.platformOptions;
    
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
        message.success(t('components.modelUsageManager.modelUpdated', { label: usage.usage_label }));
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || t('views.common.unknownError'));
        message.error(errorMessage);
    }
}

async function handleAddUsage() {
    if (!newUsage.value.key || !newUsage.value.platformId || !newUsage.value.modelId) {
        message.warning(t('components.modelUsageManager.fillAllFields'));
        return;
    }
    
    addingUsage.value = true;
    try {
        await createUserUsageSlot(newUsage.value.key, newUsage.value.label, newUsage.value.platformId, newUsage.value.modelId);
        message.success(t('components.modelUsageManager.created'));
        showAddUsageModal.value = false;
        newUsage.value = { key: '', label: '', platformId: null, modelId: null };
        await loadData();
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || t('views.common.unknownError'));
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
        message.success(t('components.modelUsageManager.usageUpdated'));
        showEditUsageModal.value = false;
        await loadData();
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || t('views.common.unknownError'));
        message.error(errorMessage);
    }
}

async function deleteUsage(usage) {
    if (isBuiltinUsage(usage.usage_key)) {
        message.warning(t('components.modelUsageManager.builtinCannotDelete'));
        return;
    }
    dialog.error({
        title: t('components.modelUsageManager.deleteUsageTitle'),
        content: t('components.modelUsageManager.deleteUsageConfirm', { label: usage.usage_label, key: usage.usage_key }),
        positiveText: t('views.common.delete'),
        negativeText: t('views.common.cancel'),
        onPositiveClick: async () => {
            try {
                await deleteUserUsageSlot(usage.usage_key);
                message.success(t('views.common.deleted'));
                await loadData();
            } catch (e: unknown) {
                const errorMessage = e instanceof Error ? e.message : String(e || t('views.common.unknownError'));
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

.api-key-warning {
    margin-top: 8px;
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
