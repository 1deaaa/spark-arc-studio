<template>
    <div class="settings-section">
        <div class="section-header">
            <h3>管理员控制台</h3>
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
                        <span>主密钥未设置。首次通过 Git 拉取项目时，YAML 中同步下来的历史 ENC 密钥无法直接解开属于正常现象，并不表示配置损坏。</span>
                    </div>
                </div>

                <n-alert v-if="!config.llm_key_set" type="info" title="首次拉取项目时的说明" style="margin-bottom: 14px;">
                    仓库里的 YAML 主要用于同步系统平台和模型列表。若其中带有历史 <code>ENC:</code> 密钥，新站点第一次启动时通常无法直接复用，这是正常现象。
                    请先设置本机的 LLM_KEY，再到 AI 管理页为需要托管的系统平台重新填写 API Key。
                </n-alert>
                
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
                            修改主密钥会导致现有的 API Key 无法直接使用；若这些密钥来自仓库同步或旧环境，请在换密后重新配置或迁移。
                        </n-text>
                    </div>
                </div>
            </n-card>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { 
    NCard, NForm, NFormItem, NSwitch, NTooltip, NIcon, NSpin, 
    NAlert, NInputGroup, NInput, NButton, NText, useMessage,
    NGrid, NFormItemGi, NDivider
} from 'naive-ui';
import { HelpCircleOutline, CheckmarkCircle, AlertCircle } from '@vicons/ionicons5';
import { fetchWithAuth } from '../../services/api';
import { bus } from '../../eventBus';

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
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
        message.error('加载配置出错: ' + errorMessage);
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
                bus.emit('system-config-updated', payload);
            } else {
                // 还原状态
                config.value[key] = !val;
                message.error(data.message || '更新失败');
            }
        } else {
            config.value[key] = !val;
            message.error('更新请求失败');
        }
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
        config.value[key] = !val;
        message.error('更新出错: ' + errorMessage);
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
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
        message.error('设置出错: ' + errorMessage);
    } finally {
        keySaving.value = false;
    }
}

onMounted(() => {
    loadConfig();
    bus.on('system-config-updated', handleRemoteUpdate);
});

onUnmounted(() => {
    bus.off('system-config-updated', handleRemoteUpdate);
});

function handleRemoteUpdate(payload) {
    // 如果是来自其他组件（如 AIManager）的更新，这里也同步一下
    if (payload) {
        config.value = { ...config.value, ...payload };
    }
}
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
