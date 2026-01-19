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
                <n-form label-placement="left" label-width="160">
                    <n-form-item label="自动使用默认 Key (LLM_AUTO_KEY)">
                        <template #label>
                            <span>自动使用默认 Key</span>
                            <n-tooltip trigger="hover">
                                <template #trigger><n-icon class="help-icon"><HelpCircleOutline /></n-icon></template>
                                启用后，当用户未配置 API Key 时，将自动使用系统预设的 API Key (LLM_AUTO_KEY=True)
                            </n-tooltip>
                        </template>
                        <n-switch v-model:value="config.llm_auto_key" @update:value="updateConfig('llm_auto_key')" />
                    </n-form-item>
                    
                    <n-form-item label="强制使用系统配置 (USE_SYS_LLM_CONFIG)">
                        <template #label>
                            <span>强制使用系统配置</span>
                            <n-tooltip trigger="hover">
                                <template #trigger><n-icon class="help-icon"><HelpCircleOutline /></n-icon></template>
                                启用后，禁用大部分用户自定义配置，强制统一使用系统预设 (USE_SYS_LLM_CONFIG=True)
                            </n-tooltip>
                        </template>
                        <n-switch v-model:value="config.use_sys_llm_config" @update:value="updateConfig('use_sys_llm_config')" />
                    </n-form-item>
                </n-form>
            </n-card>

            <!-- 安全密钥卡片 -->
            <n-card title="系统安全密钥 (LLM_KEY)" size="small">
                <div class="key-status">
                    <n-alert v-if="config.llm_key_set" type="success" :bordered="false">
                        <template #icon><n-icon><CheckmarkCircle /></n-icon></template>
                        主密钥已设置，API Key 将被加密存储。
                    </n-alert>
                    <n-alert v-else type="warning" :bordered="false">
                        <template #icon><n-icon><AlertCircle /></n-icon></template>
                        主密钥未设置！API Key 可能以明文存储或不可用。
                    </n-alert>
                </div>
                
                <n-input-group style="margin-top: 15px">
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
                <n-text depth="3" style="font-size: 12px; margin-top: 5px; display: block;">
                    注意：修改主密钥可能会导致现有的加密 API Key 无法解密，请谨慎操作。
                    设置后将尝试写入系统环境变量或注册表。
                </n-text>
            </n-card>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { 
    NCard, NForm, NFormItem, NSwitch, NTooltip, NIcon, NSpin, 
    NAlert, NInputGroup, NInput, NButton, NText, useMessage 
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

async function updateConfig(key) {
    try {
        const payload = { [key]: config.value[key] };
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
                config.value[key] = !config.value[key];
                message.error(data.message || '更新失败');
            }
        } else {
            config.value[key] = !config.value[key];
            message.error('更新请求失败');
        }
    } catch (e) {
        config.value[key] = !config.value[key];
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
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
    gap: 20px;
}

.help-icon {
    margin-left: 4px;
    vertical-align: middle;
    cursor: help;
    color: var(--spark-text-muted);
}
</style>
