<template>
    <div class="settings-section">
        <div class="section-header">
            <h3>{{ t('components.adminConfigPanel.title') }}</h3>
        </div>

        <div v-if="loading" class="loading-state">
            <n-spin size="large" />
        </div>

        <div v-else class="config-grid">
            <!-- 全局配置卡片 -->
            <n-card :title="t('components.adminConfigPanel.globalConfigTitle')" size="small">
                <n-form label-placement="left" label-width="auto" :show-feedback="false">
                    <div class="switches-container">
                        <div class="config-item">
                            <div class="item-label-group">
                                <span>{{ t('components.adminConfigPanel.llmAutoKey.label') }}</span>
                                <n-tooltip trigger="hover">
                                    <template #trigger><n-icon class="help-icon"><HelpCircleOutline /></n-icon></template>
                                    {{ t('components.adminConfigPanel.llmAutoKey.help') }}
                                </n-tooltip>
                            </div>
                            <n-switch v-model:value="config.llm_auto_key" @update:value="(val) => updateConfig('llm_auto_key', val)" />
                        </div>

                        <n-divider />

                        <div class="config-item">
                            <div class="item-label-group">
                                <span>{{ t('components.adminConfigPanel.useSysConfig.label') }}</span>
                                <n-tooltip trigger="hover">
                                    <template #trigger><n-icon class="help-icon"><HelpCircleOutline /></n-icon></template>
                                    {{ t('components.adminConfigPanel.useSysConfig.help') }}
                                </n-tooltip>
                            </div>
                            <n-switch v-model:value="config.use_sys_llm_config" @update:value="(val) => updateConfig('use_sys_llm_config', val)" />
                        </div>

                        <n-divider />

                        <div class="config-item">
                            <div class="item-label-group">
                                <span>{{ t('components.adminConfigPanel.disablePublicShare.label') }}</span>
                                <n-tooltip trigger="hover">
                                    <template #trigger><n-icon class="help-icon"><HelpCircleOutline /></n-icon></template>
                                    {{ t('components.adminConfigPanel.disablePublicShare.help') }}
                                </n-tooltip>
                            </div>
                            <n-switch v-model:value="config.disable_public_share" @update:value="(val) => updateConfig('disable_public_share', val)" />
                        </div>
                    </div>
                </n-form>
            </n-card>

            <!-- 安全密钥卡片 -->
            <n-card :title="t('components.adminConfigPanel.securityKeyTitle')" size="small">
                <div class="key-status">
                    <div v-if="config.llm_key_set" class="status-tip success">
                        <n-icon><CheckmarkCircle /></n-icon>
                        <span>{{ t('components.adminConfigPanel.keySet') }}</span>
                    </div>
                    <div v-else class="status-tip warning">
                        <n-icon><AlertCircle /></n-icon>
                        <span>{{ t('components.adminConfigPanel.keyNotSet') }}</span>
                    </div>
                </div>

                <SparkAlert v-if="!config.llm_key_set" type="info" :title="t('components.adminConfigPanel.firstCloneNotice.title')" style="margin-bottom: 14px;">
                    {{ t('components.adminConfigPanel.firstCloneNotice.desc1') }}
                    {{ t('components.adminConfigPanel.firstCloneNotice.desc2') }}
                </SparkAlert>
                
                <div class="key-input-section">
                    <n-input-group>
                        <n-input 
                            v-model:value="newLLMKey" 
                            type="password" 
                            show-password-on="click" 
                            :placeholder="t('components.adminConfigPanel.keyPlaceholder')"
                        />
                        <n-button type="primary" @click="setLLMKey" :loading="keySaving" :disabled="!newLLMKey">
                            {{ t('components.adminConfigPanel.set') }}
                        </n-button>
                    </n-input-group>
                    <div class="key-hint">
                        <n-text depth="3">
                            {{ t('components.adminConfigPanel.keyHint') }}
                        </n-text>
                    </div>
                </div>
            </n-card>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { 
    NCard, NForm, NFormItem, NSwitch, NTooltip, NIcon, NSpin, 
    NInputGroup, NInput, NButton, NText, useMessage,
    NDivider, useDialog
} from 'naive-ui';
import SparkAlert from '../share/SparkAlert.vue';
import { HelpCircleOutline, CheckmarkCircle, AlertCircle } from '@vicons/ionicons5';
import { fetchWithAuth } from '../../services/api';
import { bus } from '../../eventBus';

type GlobalConfig = {
    llm_auto_key: boolean;
    use_sys_llm_config: boolean;
    llm_key_set: boolean;
    disable_public_share: boolean;
};

const message = useMessage();
const dialog = useDialog();
const { t } = useI18n();
const loading = ref(false);
const keySaving = ref(false);
const newLLMKey = ref('');

const config = ref<GlobalConfig>({
    llm_auto_key: false,
    use_sys_llm_config: false,
    llm_key_set: false,
    disable_public_share: true,
});

async function loadConfig() {
    loading.value = true;
    try {
        const res = await fetchWithAuth('/api/admin/config/global');
        if (res.ok) {
            const data = await res.json();
            if (data.success) {
                config.value = {
                    ...config.value,
                    ...data.data,
                    disable_public_share: !!data.data?.disable_public_share,
                };
            }
        } else {
            message.error(t('components.adminConfigPanel.messages.loadFailed'));
        }
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || 'Unknown error');
        message.error(`${t('components.adminConfigPanel.messages.loadError')}: ${errorMessage}`);
    } finally {
        loading.value = false;
    }
}

async function updateConfig(key: keyof GlobalConfig, val: boolean) {
    if (key === 'disable_public_share' && val === false) {
        const confirmed = await confirmPublicShareEnable();
        if (!confirmed) {
            config.value.disable_public_share = true;
            return;
        }
    }

    try {
        const payload = { [key]: val };
        const res = await fetchWithAuth('/api/admin/config/global', {
            method: 'POST',
            body: JSON.stringify(payload),
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (res.ok) {
            const data = await res.json();
            if (data.success) {
                message.success(t('components.adminConfigPanel.messages.updated'));
                bus.emit('system-config-updated', payload);
            } else {
                // 还原状态
                config.value[key] = !val;
                message.error(data.message || t('components.adminConfigPanel.messages.updateFailed'));
            }
        } else {
            config.value[key] = !val;
            message.error(t('components.adminConfigPanel.messages.updateRequestFailed'));
        }
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || 'Unknown error');
        config.value[key] = !val;
        message.error(`${t('components.adminConfigPanel.messages.updateError')}: ${errorMessage}`);
    }
}

function confirmPublicShareEnable(): Promise<boolean> {
    return new Promise((resolve) => {
        dialog.warning({
            title: t('components.adminConfigPanel.publicShareEnableWarning.title'),
            content: t('components.adminConfigPanel.publicShareEnableWarning.content'),
            positiveText: t('components.adminConfigPanel.publicShareEnableWarning.positive'),
            negativeText: t('components.adminConfigPanel.publicShareEnableWarning.negative'),
            onPositiveClick: () => resolve(true),
            onNegativeClick: () => resolve(false),
            onClose: () => resolve(false),
            onEsc: () => resolve(false),
            onMaskClick: () => resolve(false),
        });
    });
}

async function setLLMKey() {
    if (!newLLMKey.value) return;
    
    keySaving.value = true;
    try {
        const res = await fetchWithAuth('/api/admin/config/llm-key', {
            method: 'POST',
            body: JSON.stringify({ key: newLLMKey.value }),
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (res.ok) {
            const data = await res.json();
            if (data.success) {
                message.success(t('components.adminConfigPanel.messages.keySetSuccess'));
                newLLMKey.value = '';
                config.value.llm_key_set = true;
            } else {
                message.error(data.message || t('components.adminConfigPanel.messages.setFailed'));
            }
        } else {
            message.error(t('components.adminConfigPanel.messages.setRequestFailed'));
        }
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || 'Unknown error');
        message.error(`${t('components.adminConfigPanel.messages.setError')}: ${errorMessage}`);
    } finally {
        keySaving.value = false;
    }
}

onMounted(() => {
    void loadConfig();
    bus.on('system-config-updated', handleRemoteUpdate);
});

onUnmounted(() => {
    bus.off('system-config-updated', handleRemoteUpdate);
});

function handleRemoteUpdate(payload: unknown) {
    // 如果是来自其他组件（如 AIManager）的更新，这里也同步一下
    if (payload && typeof payload === 'object') {
        config.value = { ...config.value, ...(payload as Partial<GlobalConfig>) };
    }
}
</script>

<style scoped>
.settings-section {
    background: var(--spark-panel-bg);
    border-radius: 8px;
    padding: var(--spark-panel-padding);
    margin-bottom: 20px;
    min-height: 200px;
    border: 1px solid var(--spark-border);
}

.section-header h3 {
    margin: 0 0 8px 0;
    font-size: 18px;
    color: var(--spark-primary);
}

.section-desc {
    color: var(--spark-text-muted);
    margin-bottom: 20px;
    font-size: 14px;
}

.loading-state {
    display: flex;
    justify-content: center;
    padding: 40px;
}

.config-grid {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.switches-container {
    display: flex;
    flex-direction: column;
    padding: 4px 0;
}

.config-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 0;
}

.item-label-group {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 500;
}

.n-divider {
    margin: 0 !important;
    opacity: 0.6;
}

.status-tip {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 13px;
    line-height: 1;
}

.status-tip.success {
    background-color: rgba(24, 160, 88, 0.1);
    color: #18a058;
}

.status-tip.warning {
    background-color: rgba(240, 160, 32, 0.1);
    color: #f0a020;
}

.status-tip .n-icon {
    font-size: 18px;
    flex-shrink: 0;
}

.key-input-section {
    margin-top: 24px;
}

.key-hint {
    margin-top: 16px;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.key-hint .n-text {
    line-height: 1.5;
    font-size: 12px;
}

.help-icon {
    cursor: help;
    color: var(--spark-text-muted);
    font-size: 16px;
    display: flex;
    align-items: center;
    transition: color 0.2s;
}

.help-icon:hover {
    color: var(--spark-primary);
}
</style>
