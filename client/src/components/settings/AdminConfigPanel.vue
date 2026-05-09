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
                                    <template #trigger><n-icon class="help-icon"><CircleHelp /></n-icon></template>
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
                                    <template #trigger><n-icon class="help-icon"><CircleHelp /></n-icon></template>
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
                                    <template #trigger><n-icon class="help-icon"><CircleHelp /></n-icon></template>
                                    {{ t('components.adminConfigPanel.disablePublicShare.help') }}
                                </n-tooltip>
                            </div>
                            <n-switch :value="!config.disable_public_share" @update:value="(val) => updateConfig('disable_public_share', !val)" />
                        </div>

                        <n-divider v-if="showMainlandComplianceConfig" />

                        <div v-if="showMainlandComplianceConfig" class="config-item">
                            <div class="item-label-group">
                                <span>{{ t('components.adminConfigPanel.forcePublicShareReview.label') }}</span>
                                <n-tooltip trigger="hover">
                                    <template #trigger><n-icon class="help-icon"><CircleHelp /></n-icon></template>
                                    {{ t('components.adminConfigPanel.forcePublicShareReview.help') }}
                                </n-tooltip>
                            </div>
                            <n-switch v-model:value="config.force_public_share_review" @update:value="(val) => updateConfig('force_public_share_review', val)" />
                        </div>
                    </div>
                </n-form>
            </n-card>

            <!-- 安全密钥卡片 -->
            <n-card :title="t('components.adminConfigPanel.securityKeyTitle')" size="small">
                <div class="key-status">
                    <div v-if="config.llm_key_set" class="status-tip success">
                        <n-icon><CircleCheckBig /></n-icon>
                        <span>{{ t('components.adminConfigPanel.keySet') }}</span>
                    </div>
                    <div v-else class="status-tip warning">
                        <n-icon><CircleAlert /></n-icon>
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

                <n-divider style="margin: 24px 0 4px 0;" />

                <div class="config-item">
                    <div class="item-label-group">
                        <span>{{ t('components.adminConfigPanel.registrationVerification.label') }}</span>
                        <n-tooltip trigger="hover">
                            <template #trigger><n-icon class="help-icon"><CircleHelp /></n-icon></template>
                            {{ t('components.adminConfigPanel.registrationVerification.help') }}
                        </n-tooltip>
                    </div>
                    <div class="verification-actions">
                        <n-button
                            text
                            size="small"
                            type="primary"
                            v-if="verification.secret_key_set"
                            @click="openVerificationDialog('edit')"
                        >
                            <n-icon :size="16"><Pencil /></n-icon>
                        </n-button>
                        <n-switch
                            :value="verification.enabled"
                            :loading="verificationToggling"
                            :disabled="verificationToggling"
                            @update:value="handleVerificationToggle"
                        />
                    </div>
                </div>

                <div
                    v-if="verification.secret_key_set"
                    class="status-tip"
                    :class="verification.enabled ? 'success' : 'warning'"
                    style="margin-top: 4px;"
                >
                    <n-icon><CircleCheckBig v-if="verification.enabled" /><CircleAlert v-else /></n-icon>
                    <span>
                        {{
                            verification.enabled
                                ? t('components.adminConfigPanel.registrationVerification.statusEnabled', { provider: verification.provider })
                                : t('components.adminConfigPanel.registrationVerification.statusConfiguredButOff')
                        }}
                    </span>
                </div>
                <div v-else class="status-tip warning" style="margin-top: 4px;">
                    <n-icon><CircleAlert /></n-icon>
                    <span>{{ t('components.adminConfigPanel.registrationVerification.statusUnconfigured') }}</span>
                </div>
            </n-card>
        </div>

        <n-modal
            v-model:show="verificationDialogShow"
            preset="card"
            :title="verificationDialogMode === 'edit'
                ? t('components.adminConfigPanel.registrationVerification.dialog.editTitle')
                : t('components.adminConfigPanel.registrationVerification.dialog.setupTitle')"
            :mask-closable="false"
            :closable="!verificationSaving"
            :style="{ width: '400px', maxWidth: '90vw' }"
        >
            <SparkAlert type="info" style="margin-bottom: 16px;">
                {{ t('components.adminConfigPanel.registrationVerification.dialog.intro') }}
            </SparkAlert>

            <n-form label-placement="top" :show-feedback="false" class="verification-form">
                <n-form-item :label="t('components.adminConfigPanel.registrationVerification.dialog.provider')">
                    <n-select
                        :value="verificationForm.provider"
                        :options="providerOptions"
                        :disabled="providerOptions.length <= 1"
                        @update:value="(v: string) => (verificationForm.provider = v)"
                    />
                </n-form-item>
                <n-form-item :label="t('components.adminConfigPanel.registrationVerification.dialog.siteKey')" required>
                    <n-input
                        v-model:value="verificationForm.site_key"
                        :placeholder="t('components.adminConfigPanel.registrationVerification.dialog.siteKeyPlaceholder')"
                    />
                </n-form-item>
                <n-form-item
                    :label="t('components.adminConfigPanel.registrationVerification.dialog.secretKey')"
                    :required="verificationDialogMode === 'enable' || !verification.secret_key_set"
                >
                    <n-input
                        v-model:value="verificationForm.secret_key"
                        type="password"
                        show-password-on="click"
                        :placeholder="verificationDialogMode === 'edit' && verification.secret_key_set
                            ? t('components.adminConfigPanel.registrationVerification.dialog.secretKeyEditPlaceholder')
                            : t('components.adminConfigPanel.registrationVerification.dialog.secretKeyPlaceholder')"
                    />
                </n-form-item>
            </n-form>

            <div class="verification-modal-hint">
                <n-text depth="3">{{ t('components.adminConfigPanel.registrationVerification.dialog.hint') }}</n-text>
            </div>

            <template #footer>
                <div class="verification-modal-actions">
                    <n-button @click="cancelVerificationDialog" :disabled="verificationSaving">
                        {{ t('components.adminConfigPanel.registrationVerification.dialog.cancel') }}
                    </n-button>
                    <n-button
                        type="primary"
                        @click="saveVerificationDialog"
                        :loading="verificationSaving"
                        :disabled="!canSaveVerification"
                    >
                        {{ t('components.adminConfigPanel.registrationVerification.dialog.save') }}
                    </n-button>
                </div>
            </template>
        </n-modal>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { 
    NCard, NForm, NFormItem, NSwitch, NTooltip, NIcon, NSpin, 
    NInputGroup, NInput, NButton, NText, useMessage,
    NDivider, useDialog, NModal, NSelect
} from 'naive-ui';
import SparkAlert from '../share/SparkAlert.vue';
import { CircleAlert, CircleCheckBig, CircleHelp, Pencil } from 'lucide-vue-next';
import { fetchWithAuth } from '../../services/api';
import { useMainlandComplianceLocale } from '@/i18n/compliance';
import { bus } from '../../eventBus';

type GlobalConfig = {
    llm_auto_key: boolean;
    use_sys_llm_config: boolean;
    llm_key_set: boolean;
    disable_public_share: boolean;
    force_public_share_review: boolean;
};

type RegistrationVerificationView = {
    enabled: boolean;
    provider: string;
    site_key: string;
    secret_key_set: boolean;
    supported_providers: string[];
};

type VerificationDialogMode = 'enable' | 'edit';

const message = useMessage();
const dialog = useDialog();
const { t } = useI18n();
const showMainlandComplianceConfig = useMainlandComplianceLocale();
const loading = ref(false);
const keySaving = ref(false);
const newLLMKey = ref('');

const config = ref<GlobalConfig>({
    llm_auto_key: false,
    use_sys_llm_config: false,
    llm_key_set: false,
    disable_public_share: true,
    force_public_share_review: true,
});

const verification = ref<RegistrationVerificationView>({
    enabled: false,
    provider: 'turnstile',
    site_key: '',
    secret_key_set: false,
    supported_providers: ['turnstile'],
});
const verificationToggling = ref(false);
const verificationSaving = ref(false);
const verificationDialogShow = ref(false);
const verificationDialogMode = ref<VerificationDialogMode>('enable');
const verificationForm = ref({
    provider: 'turnstile',
    site_key: '',
    secret_key: '',
});

const providerOptions = computed(() =>
    (verification.value.supported_providers || ['turnstile']).map((p) => ({ label: p, value: p })),
);

const canSaveVerification = computed(() => {
    if (!verificationForm.value.site_key.trim()) return false;
    if (verificationDialogMode.value === 'enable' && !verificationForm.value.secret_key.trim()) return false;
    if (verificationDialogMode.value === 'edit' && !verification.value.secret_key_set && !verificationForm.value.secret_key.trim()) return false;
    return true;
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

    if (key === 'use_sys_llm_config' && val === false) {
        const confirmed = await confirmSysConfigUnlock();
        if (!confirmed) {
            config.value.use_sys_llm_config = true;
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
                config.value[key] = val;
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

function confirmSysConfigUnlock(): Promise<boolean> {
    return new Promise((resolve) => {
        dialog.warning({
            title: t('components.adminConfigPanel.sysConfigUnlockWarning.title'),
            content: t('components.adminConfigPanel.sysConfigUnlockWarning.content'),
            positiveText: t('components.adminConfigPanel.sysConfigUnlockWarning.positive'),
            negativeText: t('components.adminConfigPanel.sysConfigUnlockWarning.negative'),
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

async function loadVerification() {
    try {
        const res = await fetchWithAuth('/api/admin/config/registration-verification');
        if (!res.ok) return;
        const data = await res.json();
        if (data.success && data.data) {
            verification.value = {
                enabled: !!data.data.enabled,
                provider: data.data.provider || 'turnstile',
                site_key: data.data.site_key || '',
                secret_key_set: !!data.data.secret_key_set,
                supported_providers: Array.isArray(data.data.supported_providers) && data.data.supported_providers.length
                    ? data.data.supported_providers
                    : ['turnstile'],
            };
        }
    } catch {
        // silent failure: UI will show defaults; admin can retry by editing
    }
}

function openVerificationDialog(mode: VerificationDialogMode) {
    verificationDialogMode.value = mode;
    verificationForm.value = {
        provider: verification.value.provider || 'turnstile',
        site_key: verification.value.site_key || '',
        secret_key: '',
    };
    verificationDialogShow.value = true;
}

function cancelVerificationDialog() {
    if (verificationSaving.value) return;
    verificationDialogShow.value = false;
}

type VerificationPersistPayload = {
    enabled: boolean;
    provider?: string;
    site_key?: string;
    secret_key?: string;
};

async function persistVerification(payload: VerificationPersistPayload): Promise<boolean> {
    try {
        const res = await fetchWithAuth('/api/admin/config/registration-verification', {
            method: 'POST',
            body: JSON.stringify(payload),
            headers: { 'Content-Type': 'application/json' },
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.success === false) {
            const detail = data?.message || data?.detail || t('components.adminConfigPanel.registrationVerification.messages.updateFailed');
            message.error(detail);
            return false;
        }
        if (data.data) {
            verification.value = {
                enabled: !!data.data.enabled,
                provider: data.data.provider || 'turnstile',
                site_key: data.data.site_key || '',
                secret_key_set: !!data.data.secret_key_set,
                supported_providers: Array.isArray(data.data.supported_providers) && data.data.supported_providers.length
                    ? data.data.supported_providers
                    : ['turnstile'],
            };
        }
        message.success(t('components.adminConfigPanel.registrationVerification.messages.updated'));
        return true;
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || 'Unknown error');
        message.error(`${t('components.adminConfigPanel.registrationVerification.messages.updateFailed')}: ${errorMessage}`);
        return false;
    }
}

async function handleVerificationToggle(val: boolean) {
    if (val) {
        if (!verification.value.secret_key_set) {
            // 首次开启 -> 弹窗收集站点/密钥
            openVerificationDialog('enable');
            return;
        }
        // 已有密钥 -> 直接启用
        verificationToggling.value = true;
        try {
            await persistVerification({ enabled: true });
        } finally {
            verificationToggling.value = false;
        }
    } else {
        verificationToggling.value = true;
        try {
            await persistVerification({ enabled: false });
        } finally {
            verificationToggling.value = false;
        }
    }
}

async function saveVerificationDialog() {
    if (!canSaveVerification.value) return;
    verificationSaving.value = true;
    try {
        const payload: VerificationPersistPayload = {
            enabled: true,
            provider: verificationForm.value.provider || 'turnstile',
            site_key: verificationForm.value.site_key.trim(),
        };
        // 仅当用户实际输入了新的 secret 时才发送，避免编辑模式下意外覆盖。
        if (verificationForm.value.secret_key.trim()) {
            payload.secret_key = verificationForm.value.secret_key.trim();
        }
        const ok = await persistVerification(payload);
        if (ok) {
            verificationDialogShow.value = false;
        }
    } finally {
        verificationSaving.value = false;
    }
}

onMounted(() => {
    void loadConfig();
    void loadVerification();
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
    font-size: var(--spark-fs-h3);
    color: var(--spark-primary);
}

.section-desc {
    color: var(--spark-text-muted);
    margin-bottom: 20px;
    font-size: var(--spark-fs-base);
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
    font-size: var(--spark-fs-base);
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
    font-size: var(--spark-fs-sm);
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
    font-size: var(--spark-fs-h3);
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
    font-size: var(--spark-fs-xs);
}

.help-icon {
    cursor: help;
    color: var(--spark-text-muted);
    font-size: var(--spark-fs-lg);
    display: flex;
    align-items: center;
    transition: color 0.2s;
}

.help-icon:hover {
    color: var(--spark-primary);
}

.verification-actions {
    display: flex;
    align-items: center;
    gap: 12px;
}

.verification-form {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.verification-modal-hint {
    margin-top: 12px;
    line-height: 1.5;
    font-size: var(--spark-fs-xs);
}

.verification-modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
}
</style>
