<template>
    <div class="settings-section">
        <h3>模型管理</h3>
        <p class="section-desc">为自定义平台添加、编辑模型。支持设置 extra_body 以传递额外 API 参数。</p>
        
        <div v-if="loading" class="loading-state">
            <n-spin size="large" />
        </div>
        
        <div v-else>
            <n-collapse v-if="userPlatforms.length > 0" arrow-placement="right">
                <n-collapse-item v-for="plat in userPlatforms" :key="plat.platform_id" :name="plat.platform_id">
                    <template #header>
                        <div class="platform-header">
                            <span class="platform-name">{{ plat.name }}</span>
                            <n-tag size="small" :type="plat.api_key_set ? 'success' : 'warning'">
                                {{ plat.models.length }} 个模型
                            </n-tag>
                        </div>
                    </template>
                    
                    <div class="model-list">
                        <div v-for="model in plat.models" :key="model.model_id" class="model-item">
                            <div class="model-info">
                                <span class="model-name">{{ model.display_name }}</span>
                                <n-text depth="3" style="font-size: 12px;">{{ model.model_name }}</n-text>
                                <n-tag v-if="model.extra_body" size="small" type="info" style="margin-left: 8px;">
                                    extra_body
                                </n-tag>
                            </div>
                            <n-space :size="8">
                                <n-button size="tiny" @click="openEditModelModal(plat, model)">编辑</n-button>
                                <n-button size="tiny" type="error" @click="handleDeleteModel(model)">删除</n-button>
                            </n-space>
                        </div>
                        
                        <n-button dashed block size="small" @click="openAddModelModal(plat)" style="margin-top: 12px;">
                            <template #icon><n-icon><Add /></n-icon></template>
                            添加模型
                        </n-button>
                    </div>
                </n-collapse-item>
            </n-collapse>
            
            <n-empty v-else description="暂无自定义平台">
                <template #extra>
                    <n-text depth="3">请先在「平台管理」中添加自定义平台，再添加模型。</n-text>
                </template>
            </n-empty>
        </div>

        <!-- 添加模型弹窗 -->
        <n-modal v-model:show="showAddModelModal">
            <n-card style="width: 600px" :title="`为 ${currentPlatform?.name} 添加模型`" :bordered="false" size="huge" role="dialog" aria-modal="true">
                <n-form>
                    <n-form-item label="模型标识 (Model Name)">
                        <n-input v-model:value="newModel.modelName" placeholder="API 调用时使用的模型名，如 gpt-4o" />
                    </n-form-item>
                    <n-form-item label="显示名称">
                        <n-input v-model:value="newModel.displayName" placeholder="在界面上显示的名称" />
                    </n-form-item>
                    <n-form-item label="Extra Body (可选)">
                        <n-input 
                            v-model:value="newModel.extraBody" 
                            type="textarea" 
                            :autosize="{ minRows: 3, maxRows: 8 }"
                            placeholder='JSON 格式，如: {"temperature": 0.7, "top_p": 0.9}'
                        />
                    </n-form-item>
                    <n-text depth="3" style="font-size: 12px;">
                        提示：Extra Body 用于传递额外的 API 参数，如自定义 temperature、top_p 等。留空则使用默认值。必须是有效的 JSON 格式。
                    </n-text>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showAddModelModal = false">取消</n-button>
                        <n-button type="primary" @click="handleAddModel" :loading="addingModel">创建</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>

        <!-- 编辑模型弹窗 -->
        <n-modal v-model:show="showEditModelModal">
            <n-card style="width: 600px" title="编辑模型" :bordered="false" size="huge" role="dialog" aria-modal="true">
                <n-form>
                    <n-form-item label="模型标识 (Model Name)">
                        <n-input :value="editingModel.modelName" disabled />
                        <template #feedback>
                            <n-text depth="3">模型标识不可修改。如需更换，请删除后重新添加。</n-text>
                        </template>
                    </n-form-item>
                    <n-form-item label="显示名称">
                        <n-input v-model:value="editingModel.displayName" placeholder="在界面上显示的名称" />
                    </n-form-item>
                    <n-form-item label="Extra Body">
                        <n-input 
                            v-model:value="editingModel.extraBody" 
                            type="textarea" 
                            :autosize="{ minRows: 3, maxRows: 8 }"
                            placeholder='JSON 格式，如: {"temperature": 0.7, "top_p": 0.9}'
                        />
                    </n-form-item>
                    <n-text depth="3" style="font-size: 12px;">
                        提示：Extra Body 用于传递额外的 API 参数。常用参数包括 temperature、top_p、max_tokens 等。必须是有效的 JSON 格式。
                    </n-text>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showEditModelModal = false">取消</n-button>
                        <n-button type="primary" @click="handleUpdateModel" :loading="updatingModel">保存</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>
    </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { NSpin, NCollapse, NCollapseItem, NTag, NText, NSpace, NButton, NIcon, NModal, NCard, NForm, NFormItem, NInput, NEmpty, useMessage, useDialog } from 'naive-ui';
import { Add } from '@vicons/ionicons5';
import { createModel, updateModel, deleteModel } from '../../services/api';
import { useAiStore } from '../stores/aiStore';

const message = useMessage();
const dialog = useDialog();
const aiStore = useAiStore();

const loading = computed(() => aiStore.loading);

// 获取用户自定义平台及其模型
const userPlatforms = computed(() => {
    const platformMap = new Map();
    
    aiStore.allModels.forEach(m => {
        // 只显示非系统平台
        if (m.platform_is_sys) return;
        
        if (!platformMap.has(m.platform_id)) {
            platformMap.set(m.platform_id, {
                platform_id: m.platform_id,
                name: m.platform_name,
                base_url: m.base_url,
                api_key_set: m.api_key_set,
                models: []
            });
        }
        platformMap.get(m.platform_id).models.push({
            model_id: m.model_id,
            model_name: m.model_name,
            display_name: m.display_name,
            extra_body: m.extra_body
        });
    });
    
    return Array.from(platformMap.values());
});

// 添加模型相关
const showAddModelModal = ref(false);
const addingModel = ref(false);
const currentPlatform = ref(null);
const newModel = ref({
    modelName: '',
    displayName: '',
    extraBody: ''
});

function openAddModelModal(plat) {
    currentPlatform.value = plat;
    newModel.value = { modelName: '', displayName: '', extraBody: '' };
    showAddModelModal.value = true;
}

async function handleAddModel() {
    if (!newModel.value.modelName || !newModel.value.displayName) {
        message.warning('请填写模型标识和显示名称');
        return;
    }
    
    // 验证 extra_body JSON 格式
    let extraBody = null;
    if (newModel.value.extraBody.trim()) {
        try {
            JSON.parse(newModel.value.extraBody);
            extraBody = newModel.value.extraBody.trim();
        } catch (e) {
            message.error('Extra Body 格式错误，请输入有效的 JSON');
            return;
        }
    }
    
    addingModel.value = true;
    try {
        await createModel(
            currentPlatform.value.platform_id,
            newModel.value.modelName,
            newModel.value.displayName,
            extraBody
        );
        message.success('模型添加成功');
        showAddModelModal.value = false;
        await aiStore.loadData(true, true);
    } catch (e) {
        message.error(e.message);
    } finally {
        addingModel.value = false;
    }
}

// 编辑模型相关
const showEditModelModal = ref(false);
const updatingModel = ref(false);
const editingModel = ref({
    id: null,
    modelName: '',
    displayName: '',
    extraBody: ''
});

function openEditModelModal(plat, model) {
    editingModel.value = {
        id: model.model_id,
        modelName: model.model_name,
        displayName: model.display_name,
        extraBody: model.extra_body || ''
    };
    showEditModelModal.value = true;
}

async function handleUpdateModel() {
    if (!editingModel.value.displayName) {
        message.warning('请填写显示名称');
        return;
    }
    
    // 验证 extra_body JSON 格式
    let extraBody = null;
    if (editingModel.value.extraBody.trim()) {
        try {
            JSON.parse(editingModel.value.extraBody);
            extraBody = editingModel.value.extraBody.trim();
        } catch (e) {
            message.error('Extra Body 格式错误，请输入有效的 JSON');
            return;
        }
    }
    
    updatingModel.value = true;
    try {
        await updateModel(
            editingModel.value.id,
            editingModel.value.displayName,
            extraBody
        );
        message.success('模型更新成功');
        showEditModelModal.value = false;
        await aiStore.loadData(true, true);
    } catch (e) {
        message.error(e.message);
    } finally {
        updatingModel.value = false;
    }
}

// 删除模型
function handleDeleteModel(model) {
    dialog.error({
        title: '删除模型',
        content: `确定要删除模型 "${model.display_name}" 吗？此操作不可撤销。`,
        positiveText: '删除',
        negativeText: '取消',
        onPositiveClick: async () => {
            try {
                await deleteModel(model.model_id);
                message.success('删除成功');
                await aiStore.loadData(true, true);
            } catch (e) {
                message.error(e.message);
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
    min-height: 150px;
}

.platform-header {
    display: flex;
    align-items: center;
    gap: 12px;
}

.platform-name {
    font-weight: 600;
    color: var(--spark-text);
}

.model-list {
    padding: 8px 0;
}

.model-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 12px;
    background: var(--spark-bg);
    border: 1px solid var(--spark-border);
    border-radius: var(--spark-radius);
    margin-bottom: 8px;
}

.model-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.model-name {
    font-weight: 500;
    color: var(--spark-text);
}
</style>
