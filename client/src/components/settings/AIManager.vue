<template>
    <div class="settings-section">
        <div class="section-header">
            <div>
                <h3>AI 平台与模型管理</h3>
                <p class="section-desc">管理 AI 平台及其模型。系统平台仅可配置 API Key，自定义平台可完全编辑。</p>
            </div>
            <n-tooltip v-if="systemConfig.use_sys_llm_config" trigger="hover">
                <template #trigger>
                    <div style="display: inline-block;">
                        <n-button size="small" quaternary class="action-btn btn-gray" disabled>
                            <template #icon><n-icon><Add /></n-icon></template>
                            添加自定义平台
                        </n-button>
                    </div>
                </template>
                当前模式不允许添加自定义平台
            </n-tooltip>
            <n-button v-else size="small" quaternary class="action-btn btn-blue" @click="showAddPlatformModal = true">
                <template #icon><n-icon><Add /></n-icon></template>
                添加自定义平台
            </n-button>
        </div>
        
        <div v-if="systemConfig.llm_auto_key || systemConfig.use_sys_llm_config || true" style="margin-bottom: 16px;">
             <!-- 显示条件：启用 Auto Key 或 System Lock，或者为了显示开关而总是显示(可调整) -->
             <n-alert type="info" :show-icon="true"  closable>
                <template #icon>
                    <n-icon><InformationCircle /></n-icon>
                </template>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        当前环境: 
                        <span v-if="systemConfig.llm_auto_key" style="margin-right: 12px;">✅ 自动密钥托管 (由服务商提供推理服务)</span>
                        <span v-if="systemConfig.use_sys_llm_config">🔒 锁定系统配置</span>
                        <span v-if="!systemConfig.llm_auto_key && !systemConfig.use_sys_llm_config">标准模式</span>
                    </div>
                </div>
            </n-alert>
        </div>
        
        <div v-if="loading" class="loading-state">
            <n-spin size="large" />
        </div>
        
        <div v-else>
            <n-collapse v-if="platforms.length > 0" arrow-placement="left" :default-expanded-names="defaultExpanded">
                <n-collapse-item v-for="plat in platforms" :key="plat.platform_id" :name="plat.platform_id">
                    <template #header>
                        <div class="platform-row">
                            <div class="platform-left">
                                <n-tooltip v-if="plat.is_sys" trigger="hover">
                                    <template #trigger>
                                        <n-tag size="small" :bordered="false" type="info">系统</n-tag>
                                    </template>
                                    这些模型会对所有用户展示，非管理员无法编辑
                                </n-tooltip>
                                <n-tag v-else size="small" :bordered="false" type="default">自定义</n-tag>
                                <span class="platform-name">{{ plat.name }}</span>
                                <n-text depth="3" class="platform-url">{{ plat.base_url }}</n-text>
                                <n-tag size="small" round :bordered="false" :type="plat.api_key_set ? 'success' : (plat.is_sys && systemConfig.llm_auto_key ? 'info' : 'warning')">
                                    {{ plat.api_key_set ? '已连接' : (plat.is_sys && systemConfig.llm_auto_key ? '服务商托管' : '未配置 Key') }}
                                </n-tag>
                            </div>
                            <div class="platform-actions" @click.stop>
                                <n-button v-if="!plat.is_sys" size="tiny" quaternary class="action-btn btn-blue" @click="openEditPlatformModal(plat)">编辑</n-button>
                                <n-button v-if="!plat.is_sys" size="tiny" quaternary class="action-btn btn-red" @click="confirmDeletePlatform(plat)">删除</n-button>
                                <n-button v-if="!plat.is_sys || isAdmin" size="tiny" quaternary class="action-btn btn-green" @click="openAddModelModal(plat)">添加模型</n-button>
                                <n-button v-if="!plat.is_sys || isAdmin" size="tiny" quaternary class="action-btn btn-green" @click="openAddEmbeddingModal(plat)">添加Embedding</n-button>
                                <n-button size="tiny" type="primary" @click="openKeyModal(plat)">设置密钥</n-button>
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
                                <div class="model-actions" @click.stop>
                                    <!-- 测速结果标签 - 正在测速时显示等待状态 -->
                                    <n-tag
                                        v-if="speedTestingModelIds.has(model.model_id) && !speedResults[model.model_id]?.speed"
                                        :bordered="false"
                                        type="warning"
                                        size="small"
                                        class="speed-tag testing"
                                    >
                                        <template #icon>
                                            <n-spin size="small" stroke="#e6a23c" />
                                        </template>
                                        等待响应...
                                    </n-tag>
                                    
                                    <!-- 测速结果标签 - 有结果时显示 -->
                                    <n-tooltip v-else-if="speedResults[model.model_id]" trigger="hover">
                                        <template #trigger>
                                            <n-tag
                                                :bordered="false"
                                                type="success"
                                                size="small"
                                                class="speed-tag"
                                                :class="{ 'testing': speedTestingModelIds.has(model.model_id) }"
                                            >
                                                <template #icon v-if="speedTestingModelIds.has(model.model_id)">
                                                    <n-spin size="small" stroke="#67c23a" />
                                                </template>
                                                {{ speedResults[model.model_id].speed.toFixed(1) }} char/s
                                            </n-tag>
                                        </template>
                                        <div style="text-align: left">
                                            <div>平均速度: {{ speedResults[model.model_id].speed.toFixed(1) }} char/s</div>
                                            <div>首字延迟: {{ speedResults[model.model_id].ftl ? speedResults[model.model_id].ftl.toFixed(0) + 'ms' : '等待中...' }} <span style="font-size: 10px; opacity: 0.8">(含推理)</span></div>
                                        </div>
                                    </n-tooltip>

                                    <!-- 测速按钮 - 始终显示 -->
                                    <n-button
                                        size="tiny"
                                        quaternary
                                        class="action-btn btn-yellow"
                                        @click="speedTestModel(plat, model)"
                                        :loading="speedTestingModelIds.has(model.model_id)"
                                        :disabled="testingModelId === model.model_id"
                                    >
                                        测速
                                    </n-button>

                                    <!-- 测试按钮 - 测速中禁用 -->
                                    <n-button
                                        size="tiny"
                                        quaternary
                                        class="action-btn btn-green"
                                        @click="testExistingModel(plat, model)"
                                        :loading="testingModelId === model.model_id"
                                        :disabled="speedTestingModelIds.has(model.model_id)"
                                    >
                                        测试
                                    </n-button>
                                    <n-button
                                        v-if="!plat.is_sys || isAdmin"
                                        size="tiny"
                                        quaternary
                                        class="action-btn btn-blue"
                                        @click="openEditModelModal(plat, model)"
                                    >
                                        编辑
                                    </n-button>
                                    <n-popconfirm
                                        v-if="!plat.is_sys || isAdmin"
                                        @positive-click="doDeleteModel(model.model_id, plat.is_sys)"
                                        positive-button-props="type: 'error'"
                                    >
                                        <template #trigger>
                                            <n-button
                                                size="tiny"
                                                quaternary
                                                class="action-btn btn-red"
                                            >
                                                删除
                                            </n-button>
                                        </template>
                                        确定要删除模型「{{ model.display_name }}」吗？
                                    </n-popconfirm>
                                </div>
                            </div>
                        </div>
                        <n-text v-else depth="3" style="font-size: 12px;">暂无模型</n-text>
                    </div>

                    <!-- Embedding 列表（与平台同级展示） -->
                    <div class="model-section" v-if="plat.embeddings">
                        <div v-if="plat.embeddings.length > 0" class="model-list">
                            <div v-for="model in plat.embeddings" :key="model.model_id" class="model-row">
                                <div class="model-info">
                                    <span class="model-display-name">{{ model.display_name }}</span>
                                    <span class="model-id">{{ model.model_name }}</span>
                                    <n-tag size="small" :bordered="false" type="error" round>Embedding</n-tag>
                                    <n-tag v-if="model.extra_body" size="small" :bordered="false" type="info" round>Extra</n-tag>
                                </div>
                                <div class="model-actions" @click.stop>
                                    <n-text 
                                        v-if="embeddingSelection.platform_id === plat.platform_id && embeddingSelection.model_id === model.model_id" 
                                        depth="3" 
                                        style="margin-right: 8px; font-size: 12px; color: #67c23a; font-weight: bold;"
                                    >
                                        当前默认
                                    </n-text>
                                    <n-text 
                                        v-else-if="currentEmbeddingName" 
                                        depth="3" 
                                        style="margin-right: 8px; font-size: 11px; opacity: 0.5;"
                                    >
                                        (当前: {{ currentEmbeddingName }})
                                    </n-text>
                                    <n-button
                                        size="tiny"
                                        quaternary
                                        class="action-btn btn-green"
                                        @click="saveUserEmbeddingSelection(plat.platform_id, model.model_id).then(() => loadData())"
                                        :loading="embeddingSaving"
                                        :disabled="embeddingSelection.platform_id === plat.platform_id && embeddingSelection.model_id === model.model_id"
                                    >
                                        设为默认
                                    </n-button>
                                    <n-button size="tiny" quaternary class="action-btn btn-green" @click="testEmbeddingModel(plat, model)">测试</n-button>
                                    <n-button v-if="!plat.is_sys || isAdmin" size="tiny" quaternary class="action-btn btn-blue" @click="openEditEmbeddingModal(plat, model)">编辑</n-button>
                                    <n-popconfirm
                                        v-if="!plat.is_sys || isAdmin"
                                        @positive-click="doDeleteEmbedding(model.model_id, plat.is_sys)"
                                        positive-button-props="type: 'error'"
                                    >
                                        <template #trigger>
                                            <n-button size="tiny" quaternary class="action-btn btn-red">删除</n-button>
                                        </template>
                                        确定要删除 Embedding「{{ model.display_name }}」吗？
                                    </n-popconfirm>
                                </div>
                            </div>
                        </div>
                        <n-text v-else depth="3" style="font-size: 12px;">暂无 Embedding</n-text>
                    </div>
                </n-collapse-item>
            </n-collapse>
            
            <n-empty v-else description="暂无平台" />
            
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

        <!-- 添加 Embedding 弹窗 -->
        <n-modal v-model:show="showAddEmbeddingModal">
            <n-card style="width: 600px" :title="`为 ${embeddingCurrentPlatform?.name} 添加 Embedding`" :bordered="false" size="huge">
                <n-form>
                    <n-form-item label="模型标识 (Model Name)">
                        <n-input v-model:value="newEmbedding.modelName" placeholder="例如: text-embedding-v4" />
                    </n-form-item>
                    <n-form-item label="显示名称">
                        <n-input v-model:value="newEmbedding.displayName" placeholder="在界面上显示的名称" />
                    </n-form-item>
                    <n-form-item label="Extra Body (可选)">
                        <n-input
                            v-model:value="newEmbedding.extraBody"
                            type="textarea"
                            :autosize="{ minRows: 2, maxRows: 5 }"
                            placeholder='JSON 格式，如: {"input_type": "document"}'
                        />
                    </n-form-item>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showAddEmbeddingModal = false">取消</n-button>
                        <n-button type="primary" @click="handleAddEmbedding" :loading="embeddingSaving">创建</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>

        <!-- 编辑 Embedding 弹窗 -->
        <n-modal v-model:show="showEditEmbeddingModal">
            <n-card style="width: 600px" title="编辑 Embedding" :bordered="false" size="huge">
                <n-form>
                    <n-form-item label="模型标识">
                        <n-input :value="editingEmbedding.modelName" disabled />
                    </n-form-item>
                    <n-form-item label="显示名称">
                        <n-input v-model:value="editingEmbedding.displayName" />
                    </n-form-item>
                    <n-form-item label="Extra Body">
                        <n-input
                            v-model:value="editingEmbedding.extraBody"
                            type="textarea"
                            :autosize="{ minRows: 2, maxRows: 5 }"
                        />
                    </n-form-item>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showEditEmbeddingModal = false">取消</n-button>
                        <n-button type="primary" @click="handleUpdateEmbedding" :loading="embeddingSaving">保存</n-button>
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
                        <n-button @click="testModelConnection" :loading="testing" type="info" secondary :disabled="!newModel.modelName">测试</n-button>
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
import { ref, computed, onMounted, h } from 'vue';
import {
    NSpin, NCollapse, NCollapseItem, NTag, NText, NSpace, NButton, NIcon, NModal, NCard,
    NForm, NFormItem, NInput, NInputGroup, NEmpty, NTooltip, NCollapseTransition, NPopconfirm,
    NAlert, NSwitch,
    useMessage, useDialog
} from 'naive-ui';
import { Add, InformationCircle } from '@vicons/ionicons5';
import {
    fetchWithAuth,
    createModel,
    updateModel,
    deleteModel,
    fetchPlatformsWithEmbeddings,
    fetchUserEmbeddingSelection,
    saveUserEmbeddingSelection,
    createEmbedding,
    updateEmbedding,
    deleteEmbedding,
    testEmbedding,
    adminCreateSysModel,
    adminUpdateSysModel,
    adminDeleteSysModel,
    adminCreateSysEmbedding,
    adminUpdateSysEmbedding,
    adminDeleteSysEmbedding
} from '../../services/api';
import { getUserInfo } from '../../services/authService';

const message = useMessage();
const dialog = useDialog();

// === 状态 ===
const loading = ref(false);
const saving = ref(false);
const fetching = ref(false);
const testing = ref(false);
const testingModelId = ref(null);
const speedTestingModelIds = ref(new Set()); // 支持多模型并发测速
const speedResults = ref({}); // { [model_id]: { speed: number, ftl: number } }
const platforms = ref([]);
const defaultExpanded = ref([]);
const systemConfig = ref({ llm_auto_key: false, use_sys_llm_config: false });
const isAdmin = ref(false); // 当前用户是否为管理员

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

// Embedding 相关
const embeddingSelection = ref({ platform_id: null, model_id: null });
const embeddingSaving = ref(false);
const showAddEmbeddingModal = ref(false);
const showEditEmbeddingModal = ref(false);
const embeddingCurrentPlatform = ref(null);
const newEmbedding = ref({ modelName: '', displayName: '', extraBody: '' });
const editingEmbedding = ref({ id: null, modelName: '', displayName: '', extraBody: '' });

const currentEmbeddingName = computed(() => {
    if (!embeddingSelection.value.model_id) return '';
    for (const p of platforms.value) {
        if (!p.embeddings) continue;
        const found = p.embeddings.find(m => m.model_id === embeddingSelection.value.model_id);
        if (found) return found.display_name;
    }
    return '';
});

const filteredRemoteModels = computed(() => {
    if (!searchKeyword.value) return remoteModels.value;
    const keyword = searchKeyword.value.toLowerCase();
    return remoteModels.value.filter(m => m.toLowerCase().includes(keyword));
});

async function toggleSystemConfigLock(val) {
    try {
        const res = await fetchWithAuth('/api/ai/system-config', {
            method: 'POST',
            body: JSON.stringify({ use_sys_llm_config: val }),
            headers: { 'Content-Type': 'application/json' }
        });
        if (!res.ok) {
            throw new Error('操作失败');
        }
        systemConfig.value.use_sys_llm_config = val;
        message.success(val ? '已开启强制系统配置模式' : '已关闭强制系统配置模式');
    } catch (e) {
        message.error('切换配置失败: ' + e.message);
    }
}

// === 数据加载 ===
async function loadData() {
    loading.value = true;
    try {
        // 获取所有平台（系统+自定义）及其模型
        const [res, configRes, userInfoRes] = await Promise.all([
            fetchWithAuth('/api/ai/platforms-with-models'),
            fetchWithAuth('/api/ai/system-config'),
            getUserInfo()
        ]);
        
        // 获取管理员状态
        isAdmin.value = userInfoRes?.is_admin || false;
        
        if (configRes.ok) {
            systemConfig.value = await configRes.json();
        }

        if (res.ok) {
            platforms.value = await res.json();
            // 默认展开第一个自定义平台
            const firstCustom = platforms.value.find(p => !p.is_sys);
            if (firstCustom) {
                defaultExpanded.value = [firstCustom.platform_id];
            }
        }

        const [embeddingPlatforms, embeddingSelectionRes] = await Promise.all([
            fetchPlatformsWithEmbeddings(),
            fetchUserEmbeddingSelection()
        ]);

        const platformMap = new Map(platforms.value.map(p => [p.platform_id, p]));
        embeddingPlatforms.forEach(ep => {
            if (platformMap.has(ep.platform_id)) {
                platformMap.get(ep.platform_id).embeddings = ep.embeddings || [];
            } else {
                platformMap.set(ep.platform_id, {
                    ...ep,
                    models: [],
                    embeddings: ep.embeddings || []
                });
            }
        });
        platforms.value = Array.from(platformMap.values());

        if (embeddingSelectionRes && embeddingSelectionRes.current) {
            embeddingSelection.value = {
                platform_id: embeddingSelectionRes.current.platform_id,
                model_id: embeddingSelectionRes.current.model_id
            };
        }
    } catch (e) {
        console.error('加载平台数据失败:', e);
    } finally {
        loading.value = false;
    }
}

// === 缓存处理 ===
const CACHE_KEY = 'sparkarc_speed_test_results';

function saveSpeedResultsToCache() {
    localStorage.setItem(CACHE_KEY, JSON.stringify(speedResults.value));
}

function loadSpeedResultsFromCache() {
    try {
        const cached = localStorage.getItem(CACHE_KEY);
        if (cached) {
            speedResults.value = JSON.parse(cached);
        }
    } catch (e) {
        console.error('加载测速缓存失败:', e);
    }
}

onMounted(() => {
    loadData();
    loadSpeedResultsFromCache();
});

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
        const res = await fetchWithAuth(`/api/ai/platform-config`, {
            method: 'POST',
            body: JSON.stringify({
                platform_id: editingPlatform.value.id,
                api_key: editingApiKey.value
            }),
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
            body: JSON.stringify({
                model_name: newModel.value.modelName,
                extra_body: newModel.value.extraBody || null
            }),
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

async function speedTestModel(plat, model) {
    if (speedTestingModelIds.value.has(model.model_id)) return; // Prevent double click
    
    speedTestingModelIds.value.add(model.model_id);
    // 重置当前模型测速结果（否则等待状态不会显示）
    speedResults.value[model.model_id] = { speed: 0, ftl: 0 };
    
    try {
        const response = await fetchWithAuth(`/api/ai/platform/${plat.platform_id}/speed-test`, {
            method: 'POST',
            body: JSON.stringify({ model_name: model.model_name }),
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '测速启动失败');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.slice(6));
                    if (data.error) throw new Error(data.error);
                    
                    // 确保对象存在（防止被中途删除）
                    if (!speedResults.value[model.model_id]) {
                        speedResults.value[model.model_id] = { speed: 0, ftl: 0 };
                    }

                    if (data.type === 'first_token') {
                        speedResults.value[model.model_id].ftl = data.ftl;
                    } else if (data.type === 'update') {
                        speedResults.value[model.model_id].speed = data.speed;
                        saveSpeedResultsToCache(); // 更新时也保存，防止意外中断丢失数据
                    } else if (data.type === 'final') {
                        speedResults.value[model.model_id] = {
                            speed: data.speed,
                            ftl: data.ftl
                        };
                        saveSpeedResultsToCache(); // 最终结算时保存缓存
                    }
                }
            }
        }
        if (speedResults.value[model.model_id]?.speed > 0) {
            message.success(`${model.display_name} 测速完成: ${speedResults.value[model.model_id].speed.toFixed(1)} char/s`);
        }
    } catch (e) {
        message.error(`${model.display_name} 测速失败: ${e.message}`);
        // Reset only on error, otherwise keep the last result
        if (speedResults.value[model.model_id]?.speed === 0) {
            delete speedResults.value[model.model_id];
        }
    } finally {
        speedTestingModelIds.value.delete(model.model_id);
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
        // 系统平台使用管理员API
        if (currentPlatform.value.is_sys) {
            await adminCreateSysModel(
                currentPlatform.value.platform_id,
                newModel.value.modelName,
                newModel.value.displayName || newModel.value.modelName,
                newModel.value.extraBody || null
            );
        } else {
            await createModel(
                currentPlatform.value.platform_id,
                newModel.value.modelName,
                newModel.value.displayName || newModel.value.modelName,
                newModel.value.extraBody || null
            );
        }
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
        // 系统平台使用管理员API
        if (currentPlatform.value?.is_sys) {
            await adminUpdateSysModel(
                editingModel.value.id,
                editingModel.value.displayName,
                editingModel.value.extraBody || null
            );
        } else {
            await updateModel(
                editingModel.value.id,
                editingModel.value.displayName,
                editingModel.value.extraBody || null
            );
        }
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
        content: `确定要删除模型「${model.display_name}」吗？此操作不可恢复。`,
        positiveText: '删除',
        negativeText: '取消',
        onPositive: () => doDeleteModel(model.model_id)
    });
}

async function doDeleteModel(modelId, isSys = false) {
    try {
        if (isSys) {
            await adminDeleteSysModel(modelId);
        } else {
            await deleteModel(modelId);
        }
        message.success('模型已删除');
        await loadData();
    } catch (e) {
        message.error(e.message || '删除失败');
    }
}

// === Embedding 操作 ===
function openAddEmbeddingModal(plat) {
    embeddingCurrentPlatform.value = plat;
    newEmbedding.value = { modelName: '', displayName: '', extraBody: '' };
    showAddEmbeddingModal.value = true;
}

function openEditEmbeddingModal(plat, model) {
    embeddingCurrentPlatform.value = plat;
    editingEmbedding.value = {
        id: model.model_id,
        modelName: model.model_name,
        displayName: model.display_name,
        extraBody: model.extra_body || ''
    };
    showEditEmbeddingModal.value = true;
}

async function handleAddEmbedding() {
    if (!newEmbedding.value.modelName) {
        message.warning('请填写 Embedding 模型标识');
        return;
    }
    embeddingSaving.value = true;
    try {
        // 系统平台使用管理员API
        if (embeddingCurrentPlatform.value?.is_sys) {
            await adminCreateSysEmbedding(
                embeddingCurrentPlatform.value.platform_id,
                newEmbedding.value.modelName,
                newEmbedding.value.displayName || newEmbedding.value.modelName,
                newEmbedding.value.extraBody || null
            );
        } else {
            await createEmbedding(
                embeddingCurrentPlatform.value.platform_id,
                newEmbedding.value.modelName,
                newEmbedding.value.displayName || newEmbedding.value.modelName,
                newEmbedding.value.extraBody || null
            );
        }
        message.success('Embedding 添加成功');
        showAddEmbeddingModal.value = false;
        await loadData();
    } catch (e) {
        message.error(e.message || '添加失败');
    } finally {
        embeddingSaving.value = false;
    }
}

async function handleUpdateEmbedding() {
    embeddingSaving.value = true;
    try {
        // 系统平台使用管理员API
        if (embeddingCurrentPlatform.value?.is_sys) {
            await adminUpdateSysEmbedding(
                editingEmbedding.value.id,
                editingEmbedding.value.displayName,
                editingEmbedding.value.extraBody || null
            );
        } else {
            await updateEmbedding(
                editingEmbedding.value.id,
                editingEmbedding.value.displayName,
                editingEmbedding.value.extraBody || null
            );
        }
        message.success('Embedding 更新成功');
        showEditEmbeddingModal.value = false;
        await loadData();
    } catch (e) {
        message.error(e.message || '更新失败');
    } finally {
        embeddingSaving.value = false;
    }
}

function confirmDeleteEmbedding(model) {
    dialog.warning({
        title: '确认删除',
        content: `确定要删除 Embedding「${model.display_name}」吗？此操作不可恢复。`,
        positiveText: '删除',
        negativeText: '取消',
        onPositive: () => doDeleteEmbedding(model.model_id)
    });
}

async function doDeleteEmbedding(modelId, isSys = false) {
    try {
        if (isSys) {
            await adminDeleteSysEmbedding(modelId);
        } else {
            await deleteEmbedding(modelId);
        }
        message.success('Embedding 已删除');
        await loadData();
    } catch (e) {
        message.error(e.message || '删除失败');
    }
}


async function testEmbeddingModel(plat, model) {
    try {
        const res = await testEmbedding(plat.platform_id, model.model_name);
        dialog.success({
            title: `Embedding 测试成功: ${model.display_name}`,
            content: `向量维度: ${res.response?.dims ?? res.dims ?? '未知'}`,
            positiveText: '确定'
        });
    } catch (e) {
        dialog.error({
            title: 'Embedding 测试失败',
            content: e.message,
            positiveText: '关闭'
        });
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

.section-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
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
    align-items: center;
    gap: 8px;
}

.speed-tag {
    cursor: pointer;
    font-family: monospace;
    font-weight: bold;
    transition: all 0.2s;
}
.speed-tag:hover {
    opacity: 0.8;
}
.speed-tag.testing {
    opacity: 0.7;
}

.action-btn {
    min-width: 48px;
    border-radius: 12px;
    border: 1px solid currentColor !important;
    background: transparent !important;
}

/* 按钮颜色类 */
.btn-gray {
    color: #909399 !important;
}
.btn-gray:hover {
    color: #a2a4a9 !important;
    background: rgba(144, 147, 153, 0.1) !important;
}

.btn-blue {
    color: #409eff !important;
}
.btn-blue:hover {
    color: #5faeff !important;
    background: rgba(64, 158, 255, 0.1) !important;
}

.btn-green {
    color: #67c23a !important;
}
.btn-green:hover {
    color: #85ce61 !important;
    background: rgba(103, 194, 58, 0.1) !important;
}

.btn-yellow {
    color: #e6a23c !important;
}
.btn-yellow:hover {
    color: #ebb563 !important;
    background: rgba(230, 162, 60, 0.1) !important;
}

.btn-red {
    color: #f56c6c !important;
}
.btn-red:hover {
    color: #f89898 !important;
    background: rgba(245, 108, 108, 0.1) !important;
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

/* ==================== 响应式布局 ==================== */

/* 中等宽度断点 */
@media (max-width: 900px) {
    .platform-url {
        max-width: 160px;
    }
    
    .platform-actions {
        flex-wrap: wrap;
        gap: 4px;
    }
}

/* 窄宽度断点 - 移动端/窄窗口 */
@media (max-width: 768px) {
    /* 整体卡片减小外边距 */
    .settings-section {
        padding: 12px;
        margin-bottom: 16px;
    }
    
    .section-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 8px;
    }
    
    .section-desc {
        margin-bottom: 12px;
        font-size: 13px;
    }
    
    /* 平台行 - 垂直堆叠 */
    .platform-row {
        flex-direction: column;
        align-items: flex-start;
        gap: 8px;
        padding-right: 0;
    }
    
    .platform-left {
        flex-wrap: wrap;
        gap: 6px;
        width: 100%;
    }
    
    .platform-name {
        font-size: 14px;
    }
    
    .platform-url {
        display: none; /* 窄宽度下隐藏URL */
    }
    
    .platform-actions {
        width: 100%;
        flex-wrap: wrap;
        gap: 4px;
        justify-content: flex-start;
    }
    
    .platform-actions .n-button {
        flex: 0 0 auto;
    }
    
    /* 模型区域 */
    .model-section {
        padding: 6px 0 6px 8px;
    }
    
    /* 模型行 - 垂直堆叠 */
    .model-row {
        flex-direction: column;
        align-items: flex-start;
        gap: 8px;
        padding: 10px;
    }
    
    .model-info {
        width: 100%;
        gap: 6px;
    }
    
    .model-display-name {
        font-size: 14px;
    }
    
    .model-id {
        font-size: 11px;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    
    .model-actions {
        width: 100%;
        flex-wrap: wrap;
        gap: 4px;
        justify-content: flex-start;
    }
    
    .action-btn {
        min-width: 42px;
        font-size: 12px;
        padding: 0 8px;
    }
    
    .speed-tag {
        font-size: 11px;
    }
    
    /* 弹窗响应式 */
    :deep(.n-modal) .n-card {
        width: calc(100vw - 32px) !important;
        max-width: 500px;
    }
}

/* 超窄宽度 - 小屏手机 */
@media (max-width: 480px) {
    .settings-section {
        padding: 10px;
    }
    
    .section-header h3 {
        font-size: 16px;
    }
    
    .platform-name {
        font-size: 13px;
    }
    
    .model-display-name {
        font-size: 13px;
    }
    
    .action-btn {
        min-width: 36px;
        font-size: 11px;
        padding: 0 6px;
    }
}
</style>
