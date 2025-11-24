<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header">
      <h2>Settings / 设置</h2>
      <div class="header-actions">
      </div>
    </div>
    
        <div class="content-area">
            <div class="settings-container">
                <div class="settings-left">
        <!-- Platform Management -->
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
        </div>

        </div>

        <div class="settings-right">
                <!-- Model Usage Configuration -->
                <div class="settings-section">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h3>模型用途配置</h3>
                        <n-button text tag="a" href="https://artificialanalysis.ai/models" target="_blank" rel="noopener noreferrer" type="primary" size="small">
                            <template #icon><n-icon><TrophyOutline /></n-icon></template>
                            查看大模型排行榜
                        </n-button>
                    </div>
                    <p class="section-desc">为不同的用途分配特定的 AI 模型。</p>
          
                    <div v-if="loading" class="loading-state">
                        <n-spin size="large" />
                    </div>
          
                    <div v-else class="usage-list">
                        <div v-for="usage in usageSelections" :key="usage.usage_key" class="usage-item">
                            <div class="usage-header">
                                <div class="usage-info">
                                    <span class="usage-label">{{ usage.usage_label }}</span>
                                    <span class="usage-key">({{ usage.usage_key }})</span>
                                </div>
                                <div>
                                    <n-space>
                                        <n-button size="tiny" @click="openEditUsageModal(usage)" :disabled="isBuiltinUsage(usage.usage_key)">编辑</n-button>
                                        <n-button size="tiny" type="error" @click="deleteUsage(usage)" :disabled="isBuiltinUsage(usage.usage_key)">删除</n-button>
                                    </n-space>
                                </div>
                            </div>

                            <div class="usage-controls">
                                <n-form-item label="选择平台">
                                    <n-select
                                        v-model:value="usage.platform_id"
                                        :options="platformOptions"
                                        placeholder="选择平台"
                                        @update:value="(val) => handlePlatformChange(usage, val)"
                                        class="platform-select"
                                    />
                                </n-form-item>
                
                                <n-form-item label="选择模型">
                                    <n-select
                                        v-model:value="usage.model_id"
                                        :options="getModelsForPlatform(usage.platform_id)"
                                        placeholder="选择模型"
                                        :disabled="!usage.platform_id"
                                        @update:value="(val) => handleModelChange(usage, val)"
                                        class="model-select"
                                    />
                                </n-form-item>
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
                </div>
            </div>
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
                    <n-select v-model:value="newUsage.platformId" :options="platformOptions" />
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
import { ref, onMounted, computed } from 'vue';
import { NSpin, NSelect, NFormItem, NInput, NButton, NTag, NIcon, NModal, NCard, NForm, NTable, NSpace, NText, useMessage, useDialog } from 'naive-ui';
import { Add, TrophyOutline } from '@vicons/ionicons5';
import { fetchWithAuth, fetchUserPlatformsAndModels, fetchUserSelection, saveUserSelection, createUserUsageSlot, deleteUserUsageSlot, renameUserUsageSlot } from '../services/api';

const message = useMessage();
const dialog = useDialog();
const loading = ref(true);
const usageSelections = ref([]);
const allModels = ref([]); // Flat list of all models with platform info
const platforms = ref([]); // For platform management

// Modals
const showAddUsageModal = ref(false);
const showAddPlatformModal = ref(false);
const showEditKeyModal = ref(false);
const showEditPlatformModal = ref(false);

// Loading states
const addingUsage = ref(false);
const addingPlatform = ref(false);
const updatingKey = ref(false);
const updatingPlatform = ref(false);

// Form data
const newUsage = ref({
    key: '',
    label: '',
    platformId: null,
    modelId: null
});

// 编辑用途
const showEditUsageModal = ref(false);
const editingUsage = ref({ usage_key: '', usage_label: '' });

const newPlatform = ref({
    name: '',
    baseUrl: '',
    apiKey: ''
});

const editingPlatform = ref(null);
const editingApiKey = ref('');
const editingPlatformData = ref({ id: null, name: '', baseUrl: '' });

const platformOptions = computed(() => {
    const platforms = new Map();
    allModels.value.forEach(m => {
        if (!platforms.has(m.platform_id)) {
            platforms.set(m.platform_id, {
                label: m.platform_name + (m.platform_is_sys ? ' (系统)' : ''),
                value: m.platform_id
            });
        }
    });
    return Array.from(platforms.values());
});

function getModelsForPlatform(platformId) {
    if (!platformId) return [];
    return allModels.value
        .filter(m => m.platform_id === platformId)
        .map(m => ({
            label: m.display_name || m.model_name,
            value: m.model_id
        }));
}

function getSelectedPlatform(platformId) {
    return allModels.value.find(m => m.platform_id === platformId);
}

async function loadData() {
    loading.value = true;
    try {
        // 1. Get all available models (SWR)
        await fetchUserPlatformsAndModels((data) => {
            allModels.value = data;
            
            // Build platforms list
            const platformMap = new Map();
            data.forEach(m => {
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
            platforms.value = Array.from(platformMap.values());
            if (data && data.length > 0) loading.value = false;
        });

        // 2. Get current usage selections (SWR) - fetch ALL usages
        await fetchUserSelection(null, (data) => {
            if (data.usage_selections) {
                usageSelections.value = data.usage_selections;
                if (usageSelections.value.length > 0) loading.value = false;
            }
        });
    } catch (e) {
        message.error('加载配置失败: ' + e.message);
    } finally {
        loading.value = false;
    }
}

async function handlePlatformChange(usage, platformId) {
    usage.platform_id = platformId;
    usage.model_id = null; // Reset model when platform changes
    // Don't save yet, wait for model selection
}

async function handleModelChange(usage, modelId) {
    usage.model_id = modelId;
    await saveSelection(usage);
}

async function saveSelection(usage) {
    try {
        await saveUserSelection(usage.platform_id, usage.model_id, usage.usage_key);
        message.success(`已更新 ${usage.usage_label} 的模型设置`);
        // saveUserSelection already invalidates cache
        await loadData();
    } catch (e) {
        message.error(e.message);
    }
}

// Platform Management Functions
function editPlatformKey(plat) {
    editingPlatform.value = plat;
    editingApiKey.value = '';
    showEditKeyModal.value = true;
}

async function handleUpdatePlatformKey() {
    if (!editingApiKey.value || !editingPlatform.value) return;
    
    updatingKey.value = true;
    try {
        const res = await fetchWithAuth('/api/ai/platform-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                platform_id: editingPlatform.value.platform_id,
                api_key: editingApiKey.value
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
        const res = await fetchWithAuth('/api/ai/platform', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: newPlatform.value.name,
                base_url: newPlatform.value.baseUrl,
                api_key: newPlatform.value.apiKey || undefined
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

// Usage Management Functions
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
        // refresh UI
        await loadData();
    } catch (e) {
        message.error(e.message);
    } finally {
        addingUsage.value = false;
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
    } catch (e) {
        message.error(e.message);
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
            } catch (e) {
                message.error(e.message);
            }
        }
    });
}

onMounted(loadData);
</script>

<style scoped>
.view-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--spark-bg);
}

.panel-header {
  height: 50px;
  border-bottom: 1px solid var(--spark-border);
  display: flex;
  align-items: center;
  padding: 0 20px;
  background-color: var(--spark-panel-bg);
}

.panel-header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--spark-text);
  -webkit-user-select: none;
  user-select: none;
  cursor: default;
}

.content-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.settings-container {
    display: grid;
    grid-template-columns: 720px 1fr;
    gap: 24px;
    max-width: 1400px;
    margin: 0 auto;
}

@media (max-width: 1100px) {
    .settings-container {
        grid-template-columns: 1fr;
    }
    .usage-list {
      grid-template-columns: 1fr;
    }
}

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

.usage-list {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}

.usage-item {
    background: var(--spark-bg);
    border: 1px solid var(--spark-border);
    border-radius: var(--spark-radius);
    padding: 16px;
    min-height: 180px;
}

.usage-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.usage-info {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.usage-label {
  font-weight: 600;
  font-size: 15px;
  color: var(--spark-text);
}

.usage-key {
  font-family: var(--spark-mono);
  font-size: 12px;
  color: var(--spark-text-muted);
}

.usage-controls {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.add-usage-box {
    margin-top: 10px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.loading-state {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
}
</style>
