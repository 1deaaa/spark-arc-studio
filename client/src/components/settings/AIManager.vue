<template>
    <div class="settings-section">
        <h3>AI 平台与模型管理</h3>
        <p class="section-desc">管理 AI 平台及其模型。系统平台仅可配置 API Key，自定义平台可完全编辑。</p>
        
        <div v-if="loading" class="loading-state">
            <n-spin size="large" />
        </div>
        
        <div v-else>
            <n-collapse v-if="platforms.length > 0" arrow-placement="left" :default-expanded-names="defaultExpanded">
                <n-collapse-item v-for="plat in platforms" :key="plat.platform_id" :name="plat.platform_id">
                    <template #header>
                        <div class="platform-row">
                            <div class="platform-left">
                                <n-tag v-if="plat.is_sys" size="small" :bordered="false" type="info">系统</n-tag>
                                <n-tag v-else size="small" :bordered="false" type="default">自定义</n-tag>
                                <span class="platform-name">{{ plat.name }}</span>
                                <n-text depth="3" class="platform-url">{{ plat.base_url }}</n-text>
                                <n-tag size="small" round :bordered="false" :type="plat.api_key_set ? 'success' : 'warning'">
                                    {{ plat.api_key_set ? '已连接' : '未配置 Key' }}
                                </n-tag>
                            </div>
                            <div class="platform-actions" @click.stop>
                                <n-button v-if="!plat.is_sys" size="tiny" @click="openEditPlatformModal(plat)">编辑</n-button>
                                <n-button v-if="!plat.is_sys" size="tiny" type="error" ghost @click="confirmDeletePlatform(plat)">删除</n-button>
                                <n-button size="tiny" secondary type="primary" @click="openKeyModal(plat)">设置密钥</n-button>
                                <n-button v-if="!plat.is_sys" size="tiny" @click="openAddModelModal(plat)">添加模型</n-button>
                            </div>
                        </div>
                    </template>
                    
                    <!-- 模型列表 -->
                    <div class="model-section">
                        <div v-if="plat.models && plat.models.length > 0" class="model-list">
                            <div v-for="model in plat.models" :key="model.model_id" class="model-row">
                                <div class="model-info">
                                    <span class="model-display-name">{{ model.display_name }}</span>
                                    <span class="model-id">{{ model.model_name }}</span>
                                    <n-tag v-if="model.extra_body" size="small" :bordered="false" type="info" round>Extra</n-tag>
                                </div>
                                <div class="model-actions">
                                    <n-button text size="tiny" type="warning" @click="testExistingModel(plat, model)" :loading="testingModelId === model.model_id">测试</n-button>
                                    <n-button v-if="!plat.is_sys" text size="tiny" @click="openEditModelModal(plat, model)">编辑</n-button>
                                    <n-button v-if="!plat.is_sys" text size="tiny" type="error" @click="confirmDeleteModel(model)">删除</n-button>
                                </div>
                            </div>
                        </div>
                        <n-text v-else depth="3" style="font-size: 12px;">暂无模型</n-text>
                    </div>
                </n-collapse-item>
            </n-collapse>
            
            <n-empty v-else description="暂无平台" />
            
            <n-button dashed block @click="showAddPlatformModal = true" style="margin-top: 16px;">
                <template #icon><n-icon><Add /></n-icon></template>
                添加自定义平台
            </n-button>
        </div>

        <!-- 添加平台弹窗 -->
        <n-modal v-model:show="showAddPlatformModal">
            <n-card style="width: 500px" title="添加自定义平台" :bordered="false" size="huge">
                <n-form>
                    <n-form-item label="平台名称">
                        <n-input v-model:value="newPlatform.name" placeholder="例如: My Custom API" />
                    </n-form-item>
                    <n-form-item label="Base URL">
                        <n-input v-model:value="newPlatform.baseUrl" placeholder="https://api.example.com/v1" />
                    </n-form-item>
                    <n-form-item label="API Key (可选)">
                        <n-input v-model:value="newPlatform.apiKey" type="password" show-password-on="click" placeholder="留空则稍后设置" />
                    </n-form-item>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showAddPlatformModal = false">取消</n-button>
                        <n-button type="primary" @click="handleAddPlatform" :loading="saving">创建</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>

        <!-- 编辑平台弹窗 -->
        <n-modal v-model:show="showEditPlatformModal">
            <n-card style="width: 500px" title="编辑平台" :bordered="false" size="huge">
                <n-form>
                    <n-form-item label="平台名称">
                        <n-input v-model:value="editingPlatform.name" />
                    </n-form-item>
                    <n-form-item label="Base URL">
                        <n-input v-model:value="editingPlatform.baseUrl" />
                    </n-form-item>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showEditPlatformModal = false">取消</n-button>
                        <n-button type="primary" @click="handleUpdatePlatform" :loading="saving">保存</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>

        <!-- 配置 API Key 弹窗 -->
        <n-modal v-model:show="showKeyModal">
            <n-card style="width: 500px" :title="`配置 API Key - ${editingPlatform.name}`" :bordered="false" size="huge">
                <n-form>
                    <n-form-item label="API Key">
                        <n-input v-model:value="editingApiKey" type="password" show-password-on="click" placeholder="输入 API Key" />
                    </n-form-item>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showKeyModal = false">取消</n-button>
                        <n-button type="primary" @click="handleUpdateKey" :loading="saving">保存</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>

        <!-- 添加模型弹窗 -->
        <n-modal v-model:show="showAddModelModal">
            <n-card style="width: 600px" :title="`为 ${currentPlatform?.name} 添加模型`" :bordered="false" size="huge">
                <n-form>
                    <!-- 搜索框 + 探测按钮 -->
                    <n-form-item label="搜索模型">
                        <n-input-group>
                            <n-input v-model:value="searchKeyword" placeholder="输入关键词过滤模型列表..." clearable />
                            <n-button @click="fetchRemoteModels(true)" :loading="fetching" type="info" ghost>
                                {{ remoteModels.length > 0 ? '刷新' : '探测列表' }}
                            </n-button>
                        </n-input-group>
                    </n-form-item>
                    
                    <n-collapse-transition :show="remoteModels.length > 0">
                        <div class="remote-models-box">
                            <div class="remote-models-header">
                                <n-text depth="3" style="font-size: 12px;">
                                    获取到 {{ remoteModels.length }} 个模型
                                    <span v-if="searchKeyword && filteredRemoteModels.length !== remoteModels.length">
                                        (匹配: {{ filteredRemoteModels.length }})
                                    </span>
                                </n-text>
                                <n-button size="tiny" text @click="remoteModels = []">关闭</n-button>
                            </div>
                            <n-space v-if="filteredRemoteModels.length > 0" :size="4" style="flex-wrap: wrap;">
                                <n-tag 
                                    v-for="m in filteredRemoteModels" 
                                    :key="m" 
                                    size="small"
                                    clickable 
                                    @click="selectRemoteModel(m)"
                                    :type="newModel.modelName === m ? 'primary' : 'default'"
                                >
                                    {{ m }}
                                </n-tag>
                            </n-space>
                            <n-text v-else depth="3" style="font-size: 12px;">无匹配模型</n-text>
                        </div>
                    </n-collapse-transition>

                    <!-- 模型ID（可编辑） -->
                    <n-form-item label="模型标识 (Model Name)">
                        <n-input 
                            v-model:value="newModel.modelName" 
                            placeholder="点击上方列表选择，或直接输入模型ID" 
                        />
                    </n-form-item>

                    <n-form-item label="显示名称">
                        <n-input v-model:value="newModel.displayName" placeholder="在界面上显示的名称" />
                    </n-form-item>
                    <n-form-item label="Extra Body (可选)">
                        <n-input 
                            v-model:value="newModel.extraBody" 
                            type="textarea" 
                            :autosize="{ minRows: 2, maxRows: 5 }"
                            placeholder='JSON 格式，如: {"temperature": 0.7}'
                        />
                    </n-form-item>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: space-between;">
                        <n-button @click="testModelConnection" :loading="testing" type="warning" ghost :disabled="!newModel.modelName">测试</n-button>
                        <div style="display: flex; gap: 10px;">
                            <n-button @click="showAddModelModal = false">取消</n-button>
                            <n-button type="primary" @click="handleAddModel" :loading="saving">创建</n-button>
                        </div>
                    </div>
                </template>
            </n-card>
        </n-modal>

        <!-- 编辑模型弹窗 -->
        <n-modal v-model:show="showEditModelModal">
            <n-card style="width: 600px" title="编辑模型" :bordered="false" size="huge">
                <n-form>
                    <n-form-item label="模型标识">
                        <n-input :value="editingModel.modelName" disabled />
                    </n-form-item>
                    <n-form-item label="显示名称">
                        <n-input v-model:value="editingModel.displayName" />
                    </n-form-item>
                    <n-form-item label="Extra Body">
                        <n-input 
                            v-model:value="editingModel.extraBody" 
                            type="textarea" 
                            :autosize="{ minRows: 2, maxRows: 5 }"
                        />
                    </n-form-item>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showEditModelModal = false">取消</n-button>
                        <n-button type="primary" @click="handleUpdateModel" :loading="saving">保存</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>
    </div>
</template>


<script setup>
import { ref, computed, onMounted } from 'vue';
import { 
    NSpin, NCollapse, NCollapseItem, NTag, NText, NSpace, NButton, NIcon, NModal, NCard, 
    NForm, NFormItem, NInput, NInputGroup, NEmpty, NTooltip, NCollapseTransition,
    useMessage, useDialog 
} from 'naive-ui';
import { Add } from '@vicons/ionicons5';
import { fetchWithAuth, createModel, updateModel, deleteModel } from '../../services/api';

const message = useMessage();
const dialog = useDialog();

// === 状态 ===
const loading = ref(false);
const saving = ref(false);
const fetching = ref(false);
const testing = ref(false);
const testingModelId = ref(null);
const platforms = ref([]);
const defaultExpanded = ref([]);

// 平台相关
const showAddPlatformModal = ref(false);
const showEditPlatformModal = ref(false);
const showKeyModal = ref(false);
const newPlatform = ref({ name: '', baseUrl: '', apiKey: '' });
const editingPlatform = ref({ id: null, name: '', baseUrl: '' });
const editingApiKey = ref('');

// 模型相关
const showAddModelModal = ref(false);
const showEditModelModal = ref(false);
const currentPlatform = ref(null);
const newModel = ref({ modelName: '', displayName: '', extraBody: '' });
const searchKeyword = ref('');
const editingModel = ref({ id: null, modelName: '', displayName: '', extraBody: '' });
const remoteModels = ref([]);

// 模型列表缓存: { [platform_id]: { models: [...], timestamp: number } }
const modelCache = ref({});
const CACHE_TTL_MS = 5 * 60 * 1000; // 5分钟过期

const filteredRemoteModels = computed(() => {
    if (!searchKeyword.value) return remoteModels.value;
    const keyword = searchKeyword.value.toLowerCase();
    return remoteModels.value.filter(m => m.toLowerCase().includes(keyword));
});

// === 数据加载 ===
async function loadData() {
    loading.value = true;
    try {
        // 获取所有平台（系统+自定义）及其模型
        const res = await fetchWithAuth('/api/ai/platforms-with-models');
        if (res.ok) {
            platforms.value = await res.json();
            // 默认展开第一个自定义平台
            const firstCustom = platforms.value.find(p => !p.is_sys);
            if (firstCustom) {
                defaultExpanded.value = [firstCustom.platform_id];
            }
        }
    } catch (e) {
        console.error('加载平台数据失败:', e);
    } finally {
        loading.value = false;
    }
}

onMounted(loadData);

// === 平台操作 ===
function openKeyModal(plat) {
    editingPlatform.value = { id: plat.platform_id, name: plat.name, baseUrl: plat.base_url };
    editingApiKey.value = '';
    showKeyModal.value = true;
}

function openEditPlatformModal(plat) {
    editingPlatform.value = { id: plat.platform_id, name: plat.name, baseUrl: plat.base_url };
    showEditPlatformModal.value = true;
}

async function handleAddPlatform() {
    if (!newPlatform.value.name || !newPlatform.value.baseUrl) {
        message.warning('请填写平台名称和 Base URL');
        return;
    }
    saving.value = true;
    try {
        const res = await fetchWithAuth('/api/ai/platform', {
            method: 'POST',
            body: JSON.stringify({
                name: newPlatform.value.name,
                base_url: newPlatform.value.baseUrl,
                api_key: newPlatform.value.apiKey || null
            }),
            headers: { 'Content-Type': 'application/json' }
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '创建失败');
        }
        message.success('平台创建成功');
        showAddPlatformModal.value = false;
        newPlatform.value = { name: '', baseUrl: '', apiKey: '' };
        await loadData();
    } catch (e) {
        message.error(e.message);
    } finally {
        saving.value = false;
    }
}

async function handleUpdatePlatform() {
    saving.value = true;
    try {
        const res = await fetchWithAuth(`/api/ai/platform/${editingPlatform.value.id}`, {
            method: 'PUT',
            body: JSON.stringify({
                name: editingPlatform.value.name,
                base_url: editingPlatform.value.baseUrl
            }),
            headers: { 'Content-Type': 'application/json' }
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '更新失败');
        }
        message.success('平台更新成功');
        showEditPlatformModal.value = false;
        await loadData();
    } catch (e) {
        message.error(e.message);
    } finally {
        saving.value = false;
    }
}

async function handleUpdateKey() {
    if (!editingApiKey.value) {
        message.warning('请输入 API Key');
        return;
    }
    saving.value = true;
    try {
        const res = await fetchWithAuth(`/api/ai/platform/${editingPlatform.value.id}/key`, {
            method: 'PUT',
            body: JSON.stringify({ api_key: editingApiKey.value }),
            headers: { 'Content-Type': 'application/json' }
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '更新失败');
        }
        message.success('API Key 更新成功');
        showKeyModal.value = false;
        await loadData();
    } catch (e) {
        message.error(e.message);
    } finally {
        saving.value = false;
    }
}

function confirmDeletePlatform(plat) {
    dialog.warning({
        title: '确认删除',
        content: `确定要删除平台「${plat.name}」及其所有模型吗？`,
        positiveText: '删除',
        negativeText: '取消',
        onPositive: () => doDeletePlatform(plat.platform_id)
    });
}

async function doDeletePlatform(platformId) {
    try {
        const res = await fetchWithAuth(`/api/ai/platform/${platformId}`, { method: 'DELETE' });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '删除失败');
        }
        message.success('平台已删除');
        await loadData();
    } catch (e) {
        message.error(e.message);
    }
}

// === 模型操作 ===
function openAddModelModal(plat) {
    currentPlatform.value = plat;
    newModel.value = { modelName: '', displayName: '', extraBody: '' };
    searchKeyword.value = '';
    showAddModelModal.value = true;
    
    // 有缓存则立刻显示
    const cached = modelCache.value[plat.platform_id];
    remoteModels.value = cached ? cached.models : [];
    
    // 一律后台静默更新
    fetchRemoteModels(false);
}

function openEditModelModal(plat, model) {
    currentPlatform.value = plat;
    editingModel.value = {
        id: model.model_id,
        modelName: model.model_name,
        displayName: model.display_name,
        extraBody: model.extra_body || ''
    };
    showEditModelModal.value = true;
}

async function fetchRemoteModels(showError = true) {
    if (!currentPlatform.value) return;
    fetching.value = true;
    try {
        const res = await fetchWithAuth(`/api/ai/platform/${currentPlatform.value.platform_id}/list-models`, {
            method: 'POST'
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '探测失败');
        }
        const data = await res.json();
        const models = data.models || [];
        remoteModels.value = models;
        
        // 更新缓存
        modelCache.value[currentPlatform.value.platform_id] = {
            models: models,
            timestamp: Date.now()
        };
        
        if (models.length === 0 && showError) {
            message.info('未能获取到模型列表');
        }
    } catch (e) {
        if (showError) {
            message.error(e.message);
        }
    } finally {
        fetching.value = false;
    }
}

function selectRemoteModel(modelName) {
    newModel.value.modelName = modelName;
    newModel.value.displayName = modelName;
    // searchKeyword 保持不变，方便用户继续筛选
}

async function testModelConnection() {
    if (!currentPlatform.value || !newModel.value.modelName) return;
    testing.value = true;
    try {
        const res = await fetchWithAuth(`/api/ai/platform/${currentPlatform.value.platform_id}/test-model`, {
            method: 'POST',
            body: JSON.stringify({ model_name: newModel.value.modelName }),
            headers: { 'Content-Type': 'application/json' }
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '测试失败');
        }
        const data = await res.json();
        dialog.success({
            title: '连接测试成功',
            content: `模型响应: ${data.response}`,
            positiveText: '确定'
        });
    } catch (e) {
        dialog.error({
            title: '测试失败',
            content: e.message,
            positiveText: '关闭'
        });
    } finally {
        testing.value = false;
    }
}

async function testExistingModel(plat, model) {
    testingModelId.value = model.model_id;
    try {
        const res = await fetchWithAuth(`/api/ai/platform/${plat.platform_id}/test-model`, {
            method: 'POST',
            body: JSON.stringify({ model_name: model.model_name }),
            headers: { 'Content-Type': 'application/json' }
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '测试失败');
        }
        const data = await res.json();
        dialog.success({
            title: `测试成功: ${model.display_name}`,
            content: `模型响应: ${data.response}`,
            positiveText: '确定'
        });
    } catch (e) {
        dialog.error({
            title: '测试失败',
            content: e.message,
            positiveText: '关闭'
        });
    } finally {
        testingModelId.value = null;
    }
}

async function handleAddModel() {
    if (!newModel.value.modelName) {
        message.warning('请填写模型标识');
        return;
    }
    saving.value = true;
    try {
        await createModel(
            currentPlatform.value.platform_id,
            newModel.value.modelName,
            newModel.value.displayName || newModel.value.modelName,
            newModel.value.extraBody || null
        );
        message.success('模型添加成功');
        showAddModelModal.value = false;
        await loadData();
    } catch (e) {
        message.error(e.message || '添加失败');
    } finally {
        saving.value = false;
    }
}

async function handleUpdateModel() {
    saving.value = true;
    try {
        await updateModel(
            editingModel.value.id,
            editingModel.value.displayName,
            editingModel.value.extraBody || null
        );
        message.success('模型更新成功');
        showEditModelModal.value = false;
        await loadData();
    } catch (e) {
        message.error(e.message || '更新失败');
    } finally {
        saving.value = false;
    }
}

function confirmDeleteModel(model) {
    dialog.warning({
        title: '确认删除',
        content: `确定要删除模型「${model.display_name}」吗？`,
        positiveText: '删除',
        negativeText: '取消',
        onPositive: () => doDeleteModel(model.model_id)
    });
}

async function doDeleteModel(modelId) {
    try {
        await deleteModel(modelId);
        message.success('模型已删除');
        await loadData();
    } catch (e) {
        message.error(e.message || '删除失败');
    }
}
</script>


<style scoped>
.settings-section {
    background: var(--spark-panel-bg);
    border-radius: 8px;
    padding: 24px;
    margin-bottom: 24px;
}

.settings-section h3 {
    margin: 0 0 8px 0;
    font-size: 18px;
    color: var(--spark-primary);
    user-select: none;
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
    min-height: 150px;
}

.platform-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    padding-right: 8px;
}

.platform-left {
    display: flex;
    align-items: center;
    gap: 8px;
}

.platform-name {
    font-weight: 600;
    cursor: default;
}

.platform-url {
    font-family: monospace;
    font-size: 11px;
    margin-left: 8px;
    max-width: 260px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.platform-actions {
    display: flex;
    gap: 8px;
}

.model-section {
    padding: 8px 0 8px 16px;
}

.model-list {
    margin-bottom: 8px;
}

.model-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background: var(--spark-bg-layer1);
    border: 1px solid var(--spark-border);
    border-radius: 4px;
    margin-bottom: 6px;
}

.model-info {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
}

.model-display-name {
    font-weight: 500;
}

.model-id {
    font-family: monospace;
    font-size: 12px;
    color: var(--spark-text-muted);
    background: rgba(255,255,255,0.05);
    padding: 2px 6px;
    border-radius: 3px;
}

.model-actions {
    display: flex;
    gap: 8px;
    opacity: 0.6;
}
.model-row:hover .model-actions {
    opacity: 1;
}

.remote-models-box {
    margin-bottom: 16px;
    border: 1px solid var(--spark-border);
    border-radius: 4px;
    padding: 12px;
    max-height: 180px;
    overflow-y: auto;
}

.remote-models-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}
</style>
