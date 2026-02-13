<template>
    <div class="settings-section">
        <div class="section-header">
            <div class="header-title-group">
                <h3>AI 平台与模型管理</h3>
                <n-tooltip 
                    trigger="manual" 
                    placement="top" 
                    :show="showHeaderHint"
                    :show-arrow="true"
                >
                    <template #trigger>
                        <n-icon 
                            class="info-icon"
                            @mouseenter="onHeaderHintEnter"
                            @mouseleave="onHeaderHintLeave"
                            @click.stop="toggleHeaderHint"
                        >
                            <InformationCircleOutline />
                        </n-icon>
                    </template>
                    仅管理员用户可以修改系统平台设置。注意，这会立即对全体用户生效！普通用户可以给系统平台使用自己对应提供商的密钥。
                </n-tooltip>
            </div>
        </div>
        
        <div style="margin-bottom: 16px;">
             <!-- 状态指示栏 -->
             <div class="status-bar">
                 <div class="status-item">
                    <n-tooltip trigger="hover" placement="top">
                        <template #trigger>
                            <div class="status-icon-wrapper" :class="{ active: systemConfig.llm_auto_key }">
                                <n-icon size="20">
                                    <Server v-if="systemConfig.llm_auto_key" />
                                    <Person v-else />
                                </n-icon>
                                <span class="status-text">
                                    {{ systemConfig.llm_auto_key ? '站长托管' : '自主配置' }}
                                </span>
                            </div>
                        </template>
                        <div class="status-tooltip">
                            <div class="tooltip-title">
                                {{ systemConfig.llm_auto_key ? '站长托管推理' : '自主配置密钥' }}
                            </div>
                            <div class="tooltip-desc">
                                {{ systemConfig.llm_auto_key
                                    ? '推理服务由站长统一提供，无需您配置 API Key。'
                                    : '您需要为使用的 AI 平台配置自己的 API Key。'
                                }}
                            </div>
                        </div>
                    </n-tooltip>
                 </div>

                 <div class="status-item">
                    <n-tooltip trigger="hover" placement="top">
                        <template #trigger>
                            <div class="status-icon-wrapper" :class="{ warning: systemConfig.use_sys_llm_config }">
                                <n-icon size="20">
                                    <LockClosed v-if="systemConfig.use_sys_llm_config" />
                                    <LockOpenOutline v-else />
                                </n-icon>
                                <span class="status-text">
                                    {{ systemConfig.use_sys_llm_config ? '平台锁定' : '自由模式' }}
                                    </span>
                                </div>
                            </template>
                            <div class="status-tooltip">
                                <div class="tooltip-title">
                                    {{ systemConfig.use_sys_llm_config ? '平台配置已锁定' : '自由配置模式' }}
                                </div>
                                <div class="tooltip-desc">
                                    {{ systemConfig.use_sys_llm_config
                                        ? '管理员锁定了配置，仅允许使用系统预设平台。'
                                        : '您可以自由添加和管理第三方 AI 平台。'
                                    }}
                                </div>
                            </div>
                        </n-tooltip>
                 </div>

                 <div class="status-actions">
                    <n-tooltip v-if="systemConfig.use_sys_llm_config && !isAdmin" trigger="hover">
                        <template #trigger>
                            <div style="display: inline-block;">
                                <n-button size="small" quaternary class="action-btn btn-gray" disabled>
                                    <template #icon><n-icon><Add /></n-icon></template>
                                    添加平台
                                </n-button>
                            </div>
                        </template>
                        当前模式不允许添加自定义平台
                    </n-tooltip>
                    <n-button v-else size="small" quaternary class="action-btn btn-blue" @click="showAddPlatformModal = true">
                        <template #icon><n-icon><Add /></n-icon></template>
                        添加平台
                    </n-button>
                 </div>
             </div>
        </div>
        
        <div v-if="loading" class="loading-state">
            <n-spin size="large" />
        </div>
        
        <div v-else>
            <n-collapse v-if="platforms.length > 0" arrow-placement="left" v-model:expanded-names="expandedNames">
                <n-collapse-item v-for="plat in platforms" :key="plat.platform_id" :name="plat.platform_id">
                    <template #header>
                        <div class="platform-row">
                            <div class="platform-left">
                                <n-tooltip v-if="plat.is_sys" trigger="hover">
                                    <template #trigger>
                                        <n-tag size="small" :bordered="false" :type="plat.user_key_override ? 'info' : 'success'">系统</n-tag>
                                    </template>
                                    <div style="max-width: 200px">
                                        <div>这些模型会对所有用户展示，非管理员无法编辑</div>
                                        <div style="margin-top: 6px; font-size: 12px; opacity: 0.8">
                                            {{ plat.user_key_override ? '💳 当前使用您自己的密钥' : '🏠 当前使用站长托管密钥' }}
                                        </div>
                                    </div>
                                </n-tooltip>
                                <n-tag v-else-if="!plat.is_sys" size="small" :bordered="false" type="default">自定义</n-tag>
                                <span class="platform-name">{{ plat.name }}</span>
                                <n-text depth="3" class="platform-url">{{ plat.base_url }}</n-text>
                                <n-tag v-if="!plat.is_sys && !plat.api_key_set" size="small" round :bordered="false" type="warning">未配置 Key</n-tag>
                            </div>
                            <div class="platform-actions" @click.stop>
                                <n-tooltip v-if="!plat.is_sys" trigger="hover">
                                    <template #trigger>
                                        <n-button size="tiny" quaternary class="action-btn icon-btn btn-blue" @click="openEditPlatformModal(plat)">
                                            <template #icon><n-icon><CreateOutline /></n-icon></template>
                                        </n-button>
                                    </template>
                                    编辑平台
                                </n-tooltip>
                                <n-tooltip v-if="!plat.is_sys" trigger="hover">
                                    <template #trigger>
                                        <n-button size="tiny" quaternary class="action-btn icon-btn btn-red" @click="confirmDeletePlatform(plat)">
                                            <template #icon><n-icon><TrashOutline /></n-icon></template>
                                        </n-button>
                                    </template>
                                    删除平台
                                </n-tooltip>
                                <n-tooltip v-if="plat.is_sys && isAdmin" trigger="hover">
                                    <template #trigger>
                                        <n-button size="tiny" quaternary class="action-btn icon-btn btn-red" @click="confirmDeletePlatform(plat)">
                                            <template #icon><n-icon><TrashOutline /></n-icon></template>
                                        </n-button>
                                    </template>
                                    删除平台
                                </n-tooltip>
                                <n-tooltip v-if="!plat.is_sys || isAdmin" trigger="hover">
                                    <template #trigger>
                                        <n-button size="tiny" quaternary class="action-btn icon-btn btn-green" @click="openAddModelModal(plat)">
                                            <template #icon><n-icon><Add /></n-icon></template>
                                        </n-button>
                                    </template>
                                    添加模型
                                </n-tooltip>
                                <n-tooltip v-if="!plat.is_sys || isAdmin" trigger="hover">
                                    <template #trigger>
                                        <n-button size="tiny" quaternary class="action-btn icon-btn btn-yellow" @click="openAddEmbeddingModal(plat)">
                                            <template #icon><n-icon><CubeOutline /></n-icon></template>
                                        </n-button>
                                    </template>
                                    嵌入模型
                                </n-tooltip>
                                <n-tooltip trigger="hover">
                                    <template #trigger>
                                        <n-button size="tiny" quaternary class="action-btn icon-btn btn-primary" @click="openKeyModal(plat)">
                                            <template #icon><n-icon><KeyOutline /></n-icon></template>
                                        </n-button>
                                    </template>
                                    设置密钥
                                </n-tooltip>
                            </div>
                        </div>
                    </template>
                    
                    <!-- 模型列表 -->
                    <div class="model-section">
                        <div v-if="plat.models && plat.models.length > 0" class="model-list">
                            <div v-for="model in plat.models" :key="model.model_id" class="model-row">
                                <div class="model-info">
                                    <!-- 可编辑的模型显示名称 -->
                                    <span 
                                        v-if="editingDisplayNameModelId !== model.model_id"
                                        class="model-display-name editable-name"
                                        :class="{ 'can-edit': !plat.is_sys || isAdmin }"
                                        @click="(!plat.is_sys || isAdmin) && startEditDisplayName(plat, model)"
                                        :title="(!plat.is_sys || isAdmin) ? '点击编辑显示名称' : ''"
                                    >{{ model.display_name }}</span>
                                    <n-input
                                        v-else
                                        v-model:value="editingDisplayNameValue"
                                        size="small"
                                        class="inline-input"
                                        @blur="confirmEditDisplayName(plat, model)"
                                        @keyup.enter="confirmEditDisplayName(plat, model)"
                                        @keyup.esc="cancelEditDisplayName"
                                        ref="inlineInputRef"
                                        autofocus
                                    />
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

                                    <!-- 测速按钮 -->
                                    <n-tooltip trigger="hover">
                                        <template #trigger>
                                            <n-button
                                                size="tiny"
                                                quaternary
                                                class="action-btn icon-btn btn-yellow"
                                                @click="speedTestModel(plat, model)"
                                                :loading="speedTestingModelIds.has(model.model_id)"
                                                :disabled="testingModelId === model.model_id"
                                            >
                                                <template #icon><n-icon><PulseOutline /></n-icon></template>
                                            </n-button>
                                        </template>
                                        测速
                                    </n-tooltip>

                                    <!-- 测试按钮 -->
                                    <n-tooltip trigger="hover">
                                        <template #trigger>
                                            <n-button
                                                size="tiny"
                                                quaternary
                                                class="action-btn icon-btn btn-green"
                                                @click="testExistingModel(plat, model)"
                                                :loading="testingModelId === model.model_id"
                                                :disabled="speedTestingModelIds.has(model.model_id)"
                                            >
                                                <template #icon><n-icon><CheckmarkCircleOutline /></n-icon></template>
                                            </n-button>
                                        </template>
                                        测试连接
                                    </n-tooltip>

                                    <!-- 编辑按钮 -->
                                    <n-tooltip v-if="!plat.is_sys || isAdmin" trigger="hover">
                                        <template #trigger>
                                            <n-button
                                                size="tiny"
                                                quaternary
                                                class="action-btn icon-btn btn-blue"
                                                @click="openEditModelModal(plat, model)"
                                            >
                                                <template #icon><n-icon><CreateOutline /></n-icon></template>
                                            </n-button>
                                        </template>
                                        编辑模型
                                    </n-tooltip>

                                    <!-- 删除按钮 -->
                                    <n-popconfirm
                                        v-if="!plat.is_sys || isAdmin"
                                        @positive-click="doDeleteModel(model.model_id, plat.is_sys)"
                                        :positive-button-props="{ type: 'error' }"
                                    >
                                        <template #trigger>
                                            <n-tooltip trigger="hover">
                                                <template #trigger>
                                                    <n-button
                                                        size="tiny"
                                                        quaternary
                                                        class="action-btn icon-btn btn-red"
                                                    >
                                                        <template #icon><n-icon><TrashOutline /></n-icon></template>
                                                    </n-button>
                                                </template>
                                                删除模型
                                            </n-tooltip>
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
                                    <n-tooltip trigger="hover">
                                        <template #trigger>
                                            <n-button
                                                size="tiny"
                                                quaternary
                                                class="action-btn icon-btn btn-green"
                                                @click="saveUserEmbeddingSelection(plat.platform_id, model.model_id).then(() => loadData())"
                                                :loading="embeddingSaving"
                                                :disabled="embeddingSelection.platform_id === plat.platform_id && embeddingSelection.model_id === model.model_id"
                                            >
                                                <template #icon><n-icon><FlashOutline /></n-icon></template>
                                            </n-button>
                                        </template>
                                        设为默认
                                    </n-tooltip>
                                    <n-tooltip trigger="hover">
                                        <template #trigger>
                                            <n-button size="tiny" quaternary class="action-btn icon-btn btn-green" @click="testEmbeddingModel(plat, model)">
                                                <template #icon><n-icon><CheckmarkCircleOutline /></n-icon></template>
                                            </n-button>
                                        </template>
                                        测试连接
                                    </n-tooltip>
                                    <n-tooltip v-if="!plat.is_sys || isAdmin" trigger="hover">
                                        <template #trigger>
                                            <n-button size="tiny" quaternary class="action-btn icon-btn btn-blue" @click="openEditEmbeddingModal(plat, model)">
                                                <template #icon><n-icon><CreateOutline /></n-icon></template>
                                            </n-button>
                                        </template>
                                        编辑
                                    </n-tooltip>
                                    <n-popconfirm
                                        v-if="!plat.is_sys || isAdmin"
                                        @positive-click="doDeleteEmbedding(model.model_id, plat.is_sys)"
                                        :positive-button-props="{ type: 'error' }"
                                    >
                                        <template #trigger>
                                            <n-tooltip trigger="hover">
                                                <template #trigger>
                                                    <n-button size="tiny" quaternary class="action-btn icon-btn btn-red">
                                                        <template #icon><n-icon><TrashOutline /></n-icon></template>
                                                    </n-button>
                                                </template>
                                                删除
                                            </n-tooltip>
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
            <n-card 
                style="width: 500px" 
                :title="newPlatform.isSys ? '添加系统平台' : '添加自定义平台'" 
                :bordered="false" 
                size="huge"
                header-style="padding-bottom: 8px;"
                content-style="padding-top: 0;"
            >
                <n-form>
                    <n-form-item label="平台名称">
                        <n-input v-model:value="newPlatform.name" placeholder="例如: My Custom API" />
                    </n-form-item>
                    <n-form-item label="Base URL">
                        <n-input v-model:value="newPlatform.baseUrl" placeholder="https://api.example.com/v1" :input-props="{ autocomplete: 'off' }" />
                    </n-form-item>
                    <n-form-item label="API Key (为全体用户提供推理)">
                        <n-input v-model:value="newPlatform.apiKey" type="password" show-password-on="click" placeholder="留空则稍后设置" :input-props="{ autocomplete: 'new-password' }" />
                    </n-form-item>

                    <!-- 管理员专属：系统平台开关 -->
                    <n-form-item v-if="isAdmin" :show-feedback="false" style="margin-top: 10px;">
                        <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
                            <div style="display: flex; align-items: center; gap: 6px;">
                                <span style="font-weight: 500; font-size: 13px; opacity: 0.8;">设为系统平台</span>
                                <n-tooltip trigger="hover" placement="top" :width="240">
                                    <template #trigger>
                                        <n-icon size="16" style="cursor: help; opacity: 0.6; display: flex;">
                                            <InformationCircleOutline />
                                        </n-icon>
                                    </template>
                                    系统平台会<strong>立即对全体用户生效</strong>，且普通用户无法编辑或删除。管理员可以统一管理全站的 AI 资源。
                                </n-tooltip>
                            </div>
                            <n-switch size="small" v-model:value="newPlatform.isSys" />
                        </div>
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
                        <n-input v-model:value="editingPlatform.baseUrl" :input-props="{ autocomplete: 'off' }" />
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
                        <n-input v-model:value="editingApiKey" type="password" show-password-on="click" placeholder="输入 API Key" :input-props="{ autocomplete: 'new-password' }" />
                        <template #feedback>
                            <span v-if="editingPlatform.is_sys && !editingApiKey" style="color: var(--spark-primary); font-size: 12px; opacity: 0.8;">
                                💡 留空将尝试使用站长提供的托管推理服务。请确保站长已开启该功能。
                            </span>
                        </template>
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
                    <n-form-item label="Temperature (可选)">
                        <n-space vertical :size="6" class="temp-setting-block">
                            <div class="temp-setting-row">
                                <n-switch v-model:value="newModel.temperatureEnabled">
                                    <template #checked>已启用</template>
                                    <template #unchecked>未启用</template>
                                </n-switch>
                                <n-space align="center" :size="8" class="temp-input-group">
                                    <n-input-number
                                        v-model:value="newModel.temperature"
                                        :min="TEMP_MIN"
                                        :max="TEMP_MAX"
                                        :step="0.1"
                                        :disabled="!newModel.temperatureEnabled"
                                        placeholder="Temperature"
                                        style="width: 160px"
                                    />
                                    <n-text depth="3" class="temp-range-text">{{ TEMP_MIN }} - {{ TEMP_MAX }}</n-text>
                                </n-space>
                            </div>
                            <n-space align="start" :size="6" class="temp-hint-line">
                                <n-icon class="temp-hint-icon"><AlertCircleOutline /></n-icon>
                                <n-text depth="3" class="temp-hint-text">
                                    控制创意发散程度；部分模型在温度设置错误时会直接报错，不清楚用途时请保持默认关闭。
                                </n-text>
                            </n-space>
                        </n-space>
                    </n-form-item>
                    <n-form-item label="Extra Body (可选)">
                        <n-input 
                            v-model:value="newModel.extraBody" 
                            type="textarea" 
                            :autosize="{ minRows: 2, maxRows: 5 }"
                            placeholder='JSON 格式，如: {"top_k": 40}'
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
                    <n-form-item label="Temperature (可选)">
                        <n-space vertical :size="6" class="temp-setting-block">
                            <div class="temp-setting-row">
                                <n-switch v-model:value="editingModel.temperatureEnabled">
                                    <template #checked>已启用</template>
                                    <template #unchecked>未启用（将重置为默认）</template>
                                </n-switch>
                                <n-space align="center" :size="8" class="temp-input-group">
                                    <n-input-number
                                        v-model:value="editingModel.temperature"
                                        :min="TEMP_MIN"
                                        :max="TEMP_MAX"
                                        :step="0.1"
                                        :disabled="!editingModel.temperatureEnabled"
                                        placeholder="Temperature"
                                        style="width: 160px"
                                    />
                                    <n-text depth="3" class="temp-range-text">{{ TEMP_MIN }} - {{ TEMP_MAX }}</n-text>
                                </n-space>
                            </div>
                            <n-space align="start" :size="6" class="temp-hint-line">
                                <n-icon class="temp-hint-icon"><AlertCircleOutline /></n-icon>
                                <n-text depth="3" class="temp-hint-text">
                                    控制创意发散程度；部分模型在温度设置错误时会直接报错，不清楚用途时请保持默认关闭。
                                </n-text>
                            </n-space>
                        </n-space>
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
/**
 * AI 平台与模型管理
 * 业务逻辑已提取到 3 个 composable：
 * - useAIPlatformManager: 平台 CRUD、系统配置、数据加载
 * - useAIModelManager: 模型 CRUD、测速、远程探测、内联编辑
 * - useAIEmbeddingManager: Embedding CRUD、选择管理
 */
import { ref, onMounted } from 'vue';
import {
    NSpin, NCollapse, NCollapseItem, NTag, NText, NSpace, NButton, NIcon, NModal, NCard,
    NForm, NFormItem, NInput, NInputGroup, NInputNumber, NEmpty, NTooltip, NCollapseTransition, NPopconfirm,
    NSwitch,
} from 'naive-ui';
import { Add, InformationCircleOutline, LockClosed, LockOpenOutline, Server, Person, TrashOutline, CreateOutline, KeyOutline, PulseOutline, CheckmarkCircleOutline, FlashOutline, CubeOutline, AlertCircleOutline } from '@vicons/ionicons5';

import { useAIPlatformManager } from '@/composables/useAIPlatformManager';
import { useAIModelManager } from '@/composables/useAIModelManager';
import { useAIEmbeddingManager } from '@/composables/useAIEmbeddingManager';

// === Header 提示 ===
const showHeaderHint = ref(false);
const pinHeaderHint = ref(false);

function onHeaderHintEnter() {
    showHeaderHint.value = true;
}
function onHeaderHintLeave() {
    if (!pinHeaderHint.value) showHeaderHint.value = false;
}
function toggleHeaderHint() {
    pinHeaderHint.value = !pinHeaderHint.value;
    showHeaderHint.value = pinHeaderHint.value;
}

// === 平台管理 ===
const {
    loading,
    saving,
    platforms,
    expandedNames,
    systemConfig,
    isAdmin,
    showAddPlatformModal,
    showEditPlatformModal,
    showKeyModal,
    newPlatform,
    editingPlatform,
    editingApiKey,
    loadPlatforms,
    toggleSystemConfigLock,
    openKeyModal,
    openEditPlatformModal,
    handleAddPlatform,
    handleUpdatePlatform,
    handleUpdateKey,
    confirmDeletePlatform,
    doDeletePlatform,
} = useAIPlatformManager();

// === 统一数据加载回调 ===
// 平台 composable 只加载平台+模型，需要额外加载 embedding 数据
async function loadData() {
    await loadPlatforms();
    await embedding.loadEmbeddings();
}

// === 模型管理 ===
const {
    saving: modelSaving,
    fetching,
    testing,
    testingModelId,
    speedTestingModelIds,
    speedResults,
    showAddModelModal,
    showEditModelModal,
    currentPlatform,
    newModel,
    editingModel,
    searchKeyword,
    remoteModels,
    filteredRemoteModels,
    TEMP_MIN,
    TEMP_MAX,
    editingDisplayNameModelId,
    editingDisplayNameValue,
    editingDisplayNamePlatform,
    inlineInputRef,
    openAddModelModal,
    openEditModelModal,
    fetchRemoteModels,
    selectRemoteModel,
    testModelConnection,
    speedTestModel,
    testExistingModel,
    handleAddModel,
    handleUpdateModel,
    doDeleteModel,
    startEditDisplayName,
    cancelEditDisplayName,
    confirmEditDisplayName,
} = useAIModelManager(loadData);

// === Embedding 管理 ===
const embedding = useAIEmbeddingManager(platforms, loadData);
const {
    embeddingSelection,
    embeddingSaving,
    showAddEmbeddingModal,
    showEditEmbeddingModal,
    embeddingCurrentPlatform,
    newEmbedding,
    editingEmbedding,
    currentEmbeddingName,
    openAddEmbeddingModal,
    openEditEmbeddingModal,
    handleAddEmbedding,
    handleUpdateEmbedding,
    doDeleteEmbedding,
    testEmbeddingModel,
    saveUserEmbeddingSelection,
} = embedding;

// === 初始化 ===
onMounted(() => {
    loadData();
});
</script>


<style scoped src="./AIManager.scoped.css"></style>
