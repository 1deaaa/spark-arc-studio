<template>
    <div class="settings-section">
        <h3>平台管理</h3>
        <p class="section-desc">管理自定义 AI 平台。系统平台无法删除或重命名，但可以配置 API Key。</p>
        
        <div v-if="loading" class="loading-state">
            <n-spin size="large" />
        </div>
        
        <div v-else>
            <n-table :bordered="false" :single-line="false">
                <thead>
                    <tr>
                        <th>平台名称</th>
                        <th>Base URL</th>
                        <th>API Key</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="plat in platforms" :key="plat.platform_id">
                        <td>
                            <n-tag v-if="plat.is_sys" type="info" size="small">系统</n-tag>
                            {{ plat.name }}
                        </td>
                        <td><n-text depth="3" style="font-size: 12px;">{{ plat.base_url }}</n-text></td>
                        <td>
                            <n-tag v-if="plat.api_key_set" type="success" size="small">已设置</n-tag>
                            <n-tag v-else type="warning" size="small">未设置</n-tag>
                        </td>
                        <td>
                            <n-space :size="8">
                                <n-button size="tiny" @click="editPlatformKey(plat)">设置 Key</n-button>
                                <n-button v-if="!plat.is_sys" size="tiny" @click="openEditPlatformModal(plat)">编辑</n-button>
                                <n-button v-if="!plat.is_sys" size="tiny" type="error" @click="deletePlatform(plat)">删除</n-button>
                            </n-space>
                        </td>
                    </tr>
                </tbody>
            </n-table>
            
            <n-button dashed block @click="showAddPlatformModal = true" style="margin-top: 16px;">
                <template #icon><n-icon><Add /></n-icon></template>
                添加自定义平台
            </n-button>
        </div>

        <!-- 添加平台弹窗 -->
        <n-modal v-model:show="showAddPlatformModal">
            <n-card style="width: 600px" title="添加自定义平台" :bordered="false" size="huge" role="dialog" aria-modal="true">
                <n-form>
                    <n-form-item label="平台名称">
                        <n-input v-model:value="newPlatform.name" placeholder="例如: My Custom Platform" />
                    </n-form-item>
                    <n-form-item label="Base URL">
                        <n-input v-model:value="newPlatform.baseUrl" placeholder="https://api.example.com/v1" />
                    </n-form-item>
                    <n-form-item label="API Key (可选)">
                        <n-input v-model:value="newPlatform.apiKey" type="password" show-password-on="click" placeholder="留空则稍后设置" />
                    </n-form-item>
                    <n-text depth="3" style="font-size: 12px;">
                        提示：平台 URL 只需要设置到 v1 即可（例如 https://api.example.com/v1），系统会自动补全后面的路径。目前仅支持 OpenAI 协议。
                    </n-text>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showAddPlatformModal = false">取消</n-button>
                        <n-button type="primary" @click="handleAddPlatform" :loading="addingPlatform">创建</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>

        <!-- 编辑平台弹窗 -->
        <n-modal v-model:show="showEditPlatformModal">
            <n-card style="width: 600px" title="编辑平台" :bordered="false" size="huge" role="dialog" aria-modal="true">
                <n-form>
                    <n-form-item label="平台名称">
                        <n-input v-model:value="editingPlatformData.name" placeholder="例如: My Custom Platform" />
                    </n-form-item>
                    <n-form-item label="Base URL">
                        <n-input v-model:value="editingPlatformData.baseUrl" placeholder="https://api.example.com/v1" />
                    </n-form-item>
                    <n-text depth="3" style="font-size: 12px;">
                        提示：平台 URL 只需要设置到 v1 即可（例如 https://api.example.com/v1），系统会自动补全后面的路径。目前仅支持 OpenAI 协议。
                    </n-text>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showEditPlatformModal = false">取消</n-button>
                        <n-button type="primary" @click="handleUpdatePlatform" :loading="updatingPlatform">保存</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>

        <!-- 编辑 API Key 弹窗 -->
        <n-modal v-model:show="showEditKeyModal">
            <n-card style="width: 500px" :title="`设置 ${editingPlatform?.name} 的 API Key`" :bordered="false" size="huge" role="dialog" aria-modal="true">
                <n-form>
                    <n-form-item label="API Key">
                        <n-input v-model:value="editingApiKey" type="password" show-password-on="click" placeholder="输入新的 API Key" />
                    </n-form-item>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showEditKeyModal = false">取消</n-button>
                        <n-button type="primary" @click="handleUpdatePlatformKey" :loading="updatingKey">保存</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>
    </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { NSpin, NTable, NTag, NText, NSpace, NButton, NIcon, NModal, NCard, NForm, NFormItem, NInput, useMessage, useDialog } from 'naive-ui';
import { Add } from '@vicons/ionicons5';
import { fetchWithAuth } from '../../services/api';
import { encryptApiKey } from '../../services/cryptoService';
import { useAiStore } from '../stores/aiStore';

const message = useMessage();
const dialog = useDialog();
const aiStore = useAiStore();

const loading = computed(() => aiStore.loading);

const platforms = computed(() => {
    const platformMap = new Map();
    aiStore.allModels.forEach(m => {
        if (!platformMap.has(m.platform_id)) {
            platformMap.set(m.platform_id, {
                platform_id: m.platform_id,
                name: m.platform_name,
                base_url: m.base_url,
                is_sys: m.platform_is_sys,
                api_key_set: m.api_key_set
            });
        }
    });
    return Array.from(platformMap.values());
});

const showAddPlatformModal = ref(false);
const showEditKeyModal = ref(false);
const showEditPlatformModal = ref(false);

const addingPlatform = ref(false);
const updatingKey = ref(false);
const updatingPlatform = ref(false);

const newPlatform = ref({
    name: '',
    baseUrl: '',
    apiKey: ''
});

const editingPlatform = ref(null);
const editingApiKey = ref('');
const editingPlatformData = ref({ id: null, name: '', baseUrl: '' });

async function loadData() {
    await aiStore.loadData(true, true);
}

function editPlatformKey(plat) {
    editingPlatform.value = plat;
    editingApiKey.value = '';
    showEditKeyModal.value = true;
}

async function handleUpdatePlatformKey() {
    if (!editingApiKey.value || !editingPlatform.value) return;
    
    updatingKey.value = true;
    try {
        // 加密 API Key 后传输
        const encryptedKey = await encryptApiKey(editingApiKey.value);
        
        const res = await fetchWithAuth('/api/ai/platform-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                platform_id: editingPlatform.value.platform_id,
                api_key: encryptedKey
            })
        });
        if (!res.ok) throw new Error('更新失败');
        message.success('API Key 已更新');
        showEditKeyModal.value = false;
        await loadData();
    } catch (e) {
        message.error(e.message);
    } finally {
        updatingKey.value = false;
    }
}

function openEditPlatformModal(plat) {
    editingPlatformData.value = {
        id: plat.platform_id,
        name: plat.name,
        baseUrl: plat.base_url
    };
    showEditPlatformModal.value = true;
}

async function handleUpdatePlatform() {
    if (!editingPlatformData.value.name || !editingPlatformData.value.baseUrl) {
        message.warning('请填写平台名称和 Base URL');
        return;
    }

    updatingPlatform.value = true;
    try {
        const res = await fetchWithAuth('/api/ai/platform', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id: editingPlatformData.value.id,
                name: editingPlatformData.value.name,
                base_url: editingPlatformData.value.baseUrl
            })
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.error || '更新失败');
        }
        message.success('更新成功');
        showEditPlatformModal.value = false;
        await loadData();
    } catch (e) {
        message.error(e.message);
    } finally {
        updatingPlatform.value = false;
    }
}

async function deletePlatform(plat) {
    dialog.error({
        title: '删除平台',
        content: `确定要删除平台 "${plat.name}" 吗？此操作不可撤销。`,
        positiveText: '删除',
        negativeText: '取消',
        onPositiveClick: async () => {
            try {
                const res = await fetchWithAuth(`/api/ai/platform?id=${plat.platform_id}`, {
                    method: 'DELETE'
                });
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.error || '删除失败');
                }
                message.success('删除成功');
                await loadData();
            } catch (e) {
                message.error(e.message);
            }
        }
    });
}

async function handleAddPlatform() {
    if (!newPlatform.value.name || !newPlatform.value.baseUrl) {
        message.warning('请填写平台名称和 Base URL');
        return;
    }
    
    addingPlatform.value = true;
    try {
        // 加密 API Key 后传输（如果有的话）
        let apiKey = newPlatform.value.apiKey;
        if (apiKey) {
            apiKey = await encryptApiKey(apiKey);
        }
        
        const res = await fetchWithAuth('/api/ai/platform', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: newPlatform.value.name,
                base_url: newPlatform.value.baseUrl,
                api_key: apiKey || undefined
            })
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.error || '创建失败');
        }
        
        message.success('平台创建成功');
        showAddPlatformModal.value = false;
        newPlatform.value = { name: '', baseUrl: '', apiKey: '' };
        await loadData();
    } catch (e) {
        message.error(e.message);
    } finally {
        addingPlatform.value = false;
    }
}
</script>

<style scoped>
.settings-section {
    background: var(--spark-panel-bg);
    border: 1px solid var(--spark-border);
    border-radius: var(--spark-radius);
    padding: 24px;
    margin-bottom: 24px;
}

.settings-section h3 {
    margin: 0 0 8px 0;
    font-size: 18px;
    color: var(--spark-primary);
    -webkit-user-select: none;
    user-select: none;
    cursor: default;
}

.section-desc {
    color: var(--spark-text-muted);
    margin-bottom: 20px;
    font-size: 14px;
}

.loading-state {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 200px;
}
</style>
