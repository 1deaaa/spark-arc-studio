<template>
    <div class="settings-section">
        <div class="section-header">
            <h3>管理员控制台</h3>
            <p class="section-desc">只有管理员可见的系统级配置项</p>
        </div>

        <div v-if="loading" class="loading-state">
            <n-spin size="large" />
        </div>

        <div v-else class="config-grid">
            <!-- 全局配置卡片 -->
            <n-card title="全局变量配置" size="small">
                <n-form label-placement="left" label-width="auto" :show-feedback="false">
                    <div class="switches-container">
                        <div class="config-item">
                            <div class="item-label-group">
                                <span>为全体用户提供推理服务</span>
                                <n-tooltip trigger="hover">
                                    <template #trigger><n-icon class="help-icon"><HelpCircleOutline /></n-icon></template>
                                    启用后，当用户未配置 API Key 时，将自动使用系统预设的 API Key (LLM_AUTO_KEY=True)
                                </n-tooltip>
                            </div>
                            <n-switch v-model:value="config.llm_auto_key" @update:value="(val) => updateConfig('llm_auto_key', val)" />
                        </div>

                        <n-divider />

                        <div class="config-item">
                            <div class="item-label-group">
                                <span>强制启用系统配置</span>
                                <n-tooltip trigger="hover">
                                    <template #trigger><n-icon class="help-icon"><HelpCircleOutline /></n-icon></template>
                                    启用后，所有用户将强制使用管理员配置的默认 AI 模型及密钥，不允许个人修改。
                                </n-tooltip>
                            </div>
                            <n-switch v-model:value="config.use_sys_llm_config" @update:value="(val) => updateConfig('use_sys_llm_config', val)" />
                        </div>
                    </div>
                </n-form>
            </n-card>

            <!-- 安全密钥卡片 -->
            <n-card title="系统安全密钥 (LLM_KEY)" size="small">
                <div class="key-status">
                    <div v-if="config.llm_key_set" class="status-tip success">
                        <n-icon><CheckmarkCircle /></n-icon>
                        <span>主密钥已设置，API Key 将被加密存储。</span>
                    </div>
                    <div v-else class="status-tip warning">
                        <n-icon><AlertCircle /></n-icon>
                        <span>主密钥未设置！API Key 可能以明文存储或不可用。</span>
                    </div>
                </div>
                
                <div class="key-input-section">
                    <n-input-group>
                        <n-input 
                            v-model:value="newLLMKey" 
                            type="password" 
                            show-password-on="click" 
                            placeholder="输入新的主密钥 (LLM_KEY)"
                        />
                        <n-button type="primary" @click="setLLMKey" :loading="keySaving" :disabled="!newLLMKey">
                            设置密钥
                        </n-button>
                    </n-input-group>
                    <div class="key-hint">
                        <n-text depth="3">
                            修改主密钥会导致现有的 API Key 无法使用。
                        </n-text>
                    </div>
                </div>
            </n-card>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { 
    NCard, NForm, NFormItem, NSwitch, NTooltip, NIcon, NSpin, 
    NAlert, NInputGroup, NInput, NButton, NText, useMessage,
    NGrid, NFormItemGi, NDivider
} from 'naive-ui';
import { HelpCircleOutline, CheckmarkCircle, AlertCircle } from '@vicons/ionicons5';
import { fetchWithAuth } from '../../services/api';

const message = useMessage();
const loading = ref(false);
const keySaving = ref(false);
const newLLMKey = ref('');

const config = ref({
    llm_auto_key: false,
    use_sys_llm_config: false,
    llm_key_set: false
});

async function loadConfig() {
    loading.value = true;
    try {
        const res = await fetchWithAuth('/api/admin/config/global');
        if (res.ok) {
            const data = await res.json();
            if (data.success) {
                config.value = data.data;
            }
        } else {
            message.error('加载配置失败');
        }
    } catch (e) {
        message.error('加载配置出错: ' + e.message);
    } finally {
        loading.value = false;
    }
}

async function updateConfig(key, val) {
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
                message.success('配置已更新');
            } else {
                // 还原状态
                config.value[key] = !val;
                message.error(data.message || '更新失败');
            }
        } else {
            config.value[key] = !val;
            message.error('更新请求失败');
        }
    } catch (e) {
        config.value[key] = !val;
        message.error('更新出错: ' + e.message);
    }
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
                message.success('主密钥设置成功');
                newLLMKey.value = '';
                config.value.llm_key_set = true;
            } else {
                message.error(data.message || '设置失败');
            }
        } else {
            message.error('设置请求失败');
        }
    } catch (e) {
        message.error('设置出错: ' + e.message);
    } finally {
        keySaving.value = false;
    }
}

onMounted(() => {
    loadConfig();
});
</script>

<style scoped>
.settings-section {
    background: var(--spark-panel-bg);
    border-radius: 8px;
    padding: 24px;
    margin-bottom: 24px;
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
