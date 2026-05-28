<template>
    <div class="settings-section">
        <div class="section-header">
            <div class="header-title-group">
                <h3>{{ t('components.aiManager.title') }}</h3>
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
                            <Info />
                        </n-icon>
                    </template>
                    {{ t('components.aiManager.adminHint') }}
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
                                    <User v-else />
                                </n-icon>
                                <span class="status-text">
                                    {{ systemConfig.llm_auto_key ? t('components.aiManager.status.managed') : t('components.aiManager.status.selfManaged') }}
                                </span>
                            </div>
                        </template>
                        <div class="status-tooltip">
                            <div class="tooltip-title">
                                {{ systemConfig.llm_auto_key ? t('components.aiManager.status.managedInference') : t('components.aiManager.status.selfKeyTitle') }}
                            </div>
                            <div class="tooltip-desc">
                                {{ systemConfig.llm_auto_key
                                    ? t('components.aiManager.status.managedInferenceDesc')
                                    : t('components.aiManager.status.selfKeyDesc')
                                }}
                            </div>
                        </div>
                    </n-tooltip>
                 </div>

                 <div class="status-item">
                    <n-tooltip trigger="hover" placement="top">
                        <template #trigger>
                            <div class="status-icon-wrapper" :class="{ warning: systemConfig.use_sys_llm_config, free: !systemConfig.use_sys_llm_config }">
                                <n-icon size="20">
                                    <Lock v-if="systemConfig.use_sys_llm_config" />
                                    <Unlock v-else />
                                </n-icon>
                                <span class="status-text">
                                    {{ systemConfig.use_sys_llm_config ? t('components.aiManager.status.locked') : t('components.aiManager.status.freeMode') }}
                                    </span>
                                </div>
                            </template>
                            <div class="status-tooltip">
                                <div class="tooltip-title">
                                    {{ systemConfig.use_sys_llm_config ? t('components.aiManager.status.lockedTitle') : t('components.aiManager.status.freeModeTitle') }}
                                </div>
                                <div class="tooltip-desc">
                                    {{ systemConfig.use_sys_llm_config
                                        ? t('components.aiManager.status.lockedDesc')
                                        : t('components.aiManager.status.freeModeDesc')
                                    }}
                                </div>
                            </div>
                        </n-tooltip>
                 </div>

                 <div class="status-item">
                    <n-tooltip trigger="hover" placement="top">
                        <template #trigger>
                            <div class="status-icon-wrapper" :class="{ active: systemConfig.billing_enabled }">
                                <n-icon size="20">
                                    <Zap />
                                </n-icon>
                                <span class="status-text">
                                    {{ systemConfig.billing_enabled ? t('components.aiManager.status.billingOn') : t('components.aiManager.status.billingOff') }}
                                </span>
                                <n-switch
                                    v-if="isAdmin"
                                    size="small"
                                    :value="systemConfig.billing_enabled"
                                    @click.stop
                                    @update:value="toggleBillingEnabled"
                                />
                            </div>
                        </template>
                        <div class="status-tooltip">
                            <div class="tooltip-title">
                                {{ systemConfig.billing_enabled ? t('components.aiManager.status.billingOnTitle') : t('components.aiManager.status.billingOffTitle') }}
                            </div>
                            <div class="tooltip-desc">
                                {{ systemConfig.billing_enabled
                                    ? t('components.aiManager.status.billingOnDesc')
                                    : t('components.aiManager.status.billingOffDesc')
                                }}
                            </div>
                        </div>
                    </n-tooltip>
                 </div>

                 <div class="status-actions">
                    <n-tooltip v-if="isAdmin" trigger="hover">
                        <template #trigger>
                            <n-button size="small" quaternary class="action-btn icon-btn" style="color: var(--spark-text) !important;" @click="downloadSysConfig">
                                <template #icon><n-icon><Download /></n-icon></template>
                            </n-button>
                        </template>
                        {{ t('components.aiManager.actions.exportDownloadHint') }}
                    </n-tooltip>
                    <n-tooltip v-if="isAdmin" trigger="hover">
                        <template #trigger>
                            <n-button size="small" quaternary class="action-btn icon-btn" style="color: var(--spark-text) !important;" @click="confirmSaveToYaml">
                                <template #icon><n-icon><CloudUpload /></n-icon></template>
                            </n-button>
                        </template>
                        {{ t('components.aiManager.actions.overwriteConfigHint') }}
                    </n-tooltip>
                    <n-tooltip v-if="systemConfig.use_sys_llm_config && !isAdmin" trigger="hover">
                        <template #trigger>
                            <n-button size="small" quaternary class="action-btn icon-btn btn-gray" disabled>
                                <template #icon><n-icon><Plus /></n-icon></template>
                            </n-button>
                        </template>
                        {{ t('components.aiManager.actions.addPlatformDisabledHint') }}
                    </n-tooltip>
                    <n-tooltip v-else trigger="hover">
                        <template #trigger>
                            <n-button size="small" quaternary class="action-btn icon-btn btn-blue" @click="showAddPlatformModal = true">
                                <template #icon><n-icon><Plus /></n-icon></template>
                            </n-button>
                        </template>
                        {{ t('components.aiManager.actions.addPlatform') }}
                    </n-tooltip>
                 </div>
             </div>
        </div>
        
        <div v-if="loading" class="loading-state">
            <SparkLoaderAnimation />
        </div>
        
        <div v-else>
            <n-collapse 
                v-if="platforms.length > 0" 
                arrow-placement="left" 
                v-model:expanded-names="expandedNames"
                v-sortable="{ disabled: !isAdmin, onEnd: onPlatformSortEnd }"
            >
                <n-collapse-item 
                    v-for="(plat, platIdx) in platforms" 
                    :key="plat.platform_id"
                    :name="plat.platform_id"
                    :data-id="plat.platform_id"
                    class="plat-draggable-item"
                >
                    <template #header>
                        <div class="platform-row">
                            <!-- 管理员拖拽手柄 -->
                            <n-tooltip v-if="isAdmin" trigger="hover">
                                <template #trigger>
                                    <n-icon
                                        class="drag-handle"
                                        @mousedown.stop
                                    >
                                        <Menu />
                                    </n-icon>
                                </template>
                                {{ t('components.aiManager.tooltips.dragSort') }}
                            </n-tooltip>
                            <div class="platform-left">
                                <n-tooltip v-if="plat.is_sys" trigger="hover">
                                    <template #trigger>
                                        <SparkTag size="small" :type="platKeyTagType(plat)">{{ t('components.aiManager.tags.system') }}</SparkTag>
                                    </template>
                                    <div style="max-width: 220px">
                                        <div>{{ t('components.aiManager.tooltips.systemPlatformReadonly') }}</div>
                                        <div style="margin-top: 6px; font-size: var(--spark-fs-xs); opacity: 0.85">
                                            {{ platKeyTagTip(plat) }}
                                        </div>
                                    </div>
                                </n-tooltip>
                                <SparkTag v-else-if="!plat.is_sys" size="small" type="default">{{ t('components.aiManager.tags.custom') }}</SparkTag>
                                <n-tooltip v-if="plat.is_sys" trigger="hover">
                                    <template #trigger>
                                        <SparkTag size="small" :type="platformCreditTagType(plat)">
                                            {{ platformCreditText(plat) }}<SparkIcon />
                                        </SparkTag>
                                    </template>
                                    {{ platformCreditTagTitle(plat) }}
                                </n-tooltip>
                                <n-tooltip
                                    v-if="editingPlatformId !== plat.platform_id"
                                    trigger="hover"
                                    :disabled="!(!plat.is_sys || isAdmin)"
                                >
                                    <template #trigger>
                                        <span
                                            class="platform-name"
                                            :class="{ 'can-edit': !plat.is_sys || isAdmin }"
                                            @click="(!plat.is_sys || isAdmin) && startEditPlatformName(plat)"
                                        >{{ plat.name }}</span>
                                    </template>
                                    {{ t('components.aiManager.tooltips.clickToEditDisplayName') }}
                                </n-tooltip>
                                <n-input
                                    v-else
                                    v-model:value="editingPlatformNameValue"
                                    size="small"
                                    class="inline-input"
                                    @blur="confirmEditPlatformName(plat)"
                                    @keyup.enter="confirmEditPlatformName(plat)"
                                    @keyup.esc="cancelEditPlatformName"
                                    ref="platformInlineInputRef"
                                    autofocus
                                />
                            </div>
                            <div class="platform-actions" @click.stop>
                                <n-tooltip trigger="hover">
                                    <template #trigger>
                                        <n-button size="tiny" quaternary class="action-btn icon-btn btn-blue" @click="openEditPlatformModal(plat)">
                                            <template #icon><n-icon><SquarePen /></n-icon></template>
                                        </n-button>
                                    </template>
                                    {{ t('components.aiManager.actions.editPlatform') }}
                                </n-tooltip>
                                <n-tooltip v-if="!plat.is_sys" trigger="hover">
                                    <template #trigger>
                                        <n-button size="tiny" quaternary class="action-btn icon-btn btn-red" @click="confirmDeletePlatform(plat)">
                                            <template #icon><n-icon><Trash /></n-icon></template>
                                        </n-button>
                                    </template>
                                    {{ t('components.aiManager.actions.deletePlatform') }}
                                </n-tooltip>
                                <n-tooltip v-if="plat.is_sys && isAdmin" trigger="hover">
                                    <template #trigger>
                                        <n-button size="tiny" quaternary class="action-btn icon-btn btn-red" @click="confirmDeletePlatform(plat)">
                                            <template #icon><n-icon><Trash /></n-icon></template>
                                        </n-button>
                                    </template>
                                    {{ t('components.aiManager.actions.deletePlatform') }}
                                </n-tooltip>
                                <n-tooltip v-if="!plat.is_sys || isAdmin" trigger="hover">
                                    <template #trigger>
                                        <n-button size="tiny" quaternary class="action-btn icon-btn btn-green" @click="openAddModelModal(plat)">
                                            <template #icon><n-icon><Plus /></n-icon></template>
                                        </n-button>
                                    </template>
                                    {{ t('components.aiManager.actions.addModel') }}
                                </n-tooltip>
                            </div>
                        </div>
                    </template>
                    
                    <!-- 模型列表 -->
                    <div class="model-section">
                        <div
                            v-if="plat.models && plat.models.length > 0" 
                            class="model-list"
                            v-sortable="{ disabled: !isAdmin || !plat.is_sys, onEnd: (evt) => onModelSortEnd(evt, plat) }"
                        >
                            <div class="model-row" v-for="(model, modelIdx) in plat.models" :key="model.model_id" :data-id="model.model_id">
                                <div class="model-info">
                                    <!-- 管理员模型拖拽手柄 -->
                                    <n-tooltip v-if="isAdmin && plat.is_sys" trigger="hover">
                                        <template #trigger>
                                            <n-icon
                                                class="drag-handle drag-handle-sm"
                                                @mousedown.stop
                                            >
                                                <Menu />
                                            </n-icon>
                                        </template>
                                        {{ t('components.aiManager.tooltips.dragSort') }}
                                    </n-tooltip>
                                    <!-- 可编辑的模型显示名称 -->
                                    <n-tooltip
                                        v-if="editingDisplayNameModelId !== model.model_id"
                                        trigger="hover"
                                        :disabled="!(!plat.is_sys || isAdmin)"
                                    >
                                        <template #trigger>
                                            <span
                                                class="model-display-name editable-name"
                                                :class="{ 'can-edit': !plat.is_sys || isAdmin }"
                                                @click="(!plat.is_sys || isAdmin) && startEditDisplayName(plat, model)"
                                            >{{ model.display_name }}</span>
                                        </template>
                                        {{ t('components.aiManager.tooltips.clickToEditDisplayName') }}
                                    </n-tooltip>
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
                                    <n-tooltip v-if="model.extra_body" trigger="hover">
                                        <template #trigger>
                                            <SparkTag class="extra-tag-desktop" size="small" type="primary">{{ t('components.aiManager.badges.extraBodyBadge') }}</SparkTag>
                                        </template>
                                        {{ t('components.aiManager.badges.extraBodyTooltip') }}
                                    </n-tooltip>
                                    <n-tooltip v-if="plat.is_sys" trigger="hover">
                                        <template #trigger>
                                            <SparkTag
                                                class="model-credit-tag"
                                                size="small"
                                                :type="modelCreditTagMeta(plat, model).type"
                                            >{{ modelCreditTagMeta(plat, model).text }}<SparkIcon /></SparkTag>
                                        </template>
                                        {{ modelCreditTagMeta(plat, model).title }}
                                    </n-tooltip>
                                </div>
                                <div class="model-actions" @click.stop>
                                    <n-tooltip v-if="model.extra_body" trigger="hover">
                                        <template #trigger>
                                            <SparkTag class="extra-tag-mobile" size="small" type="primary">{{ t('components.aiManager.badges.extraBodyBadge') }}</SparkTag>
                                        </template>
                                        {{ t('components.aiManager.badges.extraBodyTooltip') }}
                                    </n-tooltip>
                                    <n-tooltip v-if="plat.is_sys" trigger="hover">
                                        <template #trigger>
                                            <SparkTag
                                                class="model-credit-tag-mobile"
                                                size="small"
                                                :type="modelCreditTagMeta(plat, model).type"
                                            >{{ modelCreditTagMeta(plat, model).text }}<SparkIcon /></SparkTag>
                                        </template>
                                        {{ modelCreditTagMeta(plat, model).title }}
                                    </n-tooltip>
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
                                        {{ t('components.aiManager.speed.waitingResponse') }}
                                    </n-tag>
                                    
                                    <!-- 测速结果标签 - 有结果时显示，点击可关闭 -->
                                    <n-tooltip v-else-if="speedResults[model.model_id]" trigger="hover">
                                        <template #trigger>
                                            <n-tag
                                                :bordered="false"
                                                type="success"
                                                size="small"
                                                class="speed-tag"
                                                :class="{ 'testing': speedTestingModelIds.has(model.model_id) }"
                                                @click.stop="clearSpeedResult(model.model_id)"
                                            >
                                                <template #icon v-if="speedTestingModelIds.has(model.model_id)">
                                                    <n-spin size="small" stroke="#67c23a" />
                                                </template>
                                                {{ speedResults[model.model_id].speed.toFixed(1) }} token/s
                                            </n-tag>
                                        </template>
                                        <div style="text-align: left">
                                            <div>{{ t('components.aiManager.speed.avgSpeed') }}: {{ speedResults[model.model_id].speed.toFixed(1) }} token/s</div>
                                            <div>{{ t('components.aiManager.speed.firstTokenLatency') }}: {{ speedResults[model.model_id].ftl ? speedResults[model.model_id].ftl.toFixed(0) + 'ms' : t('components.aiManager.speed.waiting') }} <span style="font-size: var(--spark-fs-3xs); opacity: 0.8">({{ t('components.aiManager.speed.withReasoning') }})</span></div>
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
                                                <template #icon><n-icon><Activity /></n-icon></template>
                                            </n-button>
                                        </template>
                                        {{ t('components.aiManager.actions.speedTest') }}
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
                                                <template #icon><n-icon><CircleCheck /></n-icon></template>
                                            </n-button>
                                        </template>
                                        {{ t('components.aiManager.actions.testConnection') }}
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
                                                <template #icon><n-icon><SquarePen /></n-icon></template>
                                            </n-button>
                                        </template>
                                        {{ t('components.aiManager.actions.editModel') }}
                                    </n-tooltip>

                                    <!-- 删除按钮 -->
                                    <n-tooltip v-if="!plat.is_sys || isAdmin" trigger="hover">
                                        <template #trigger>
                                            <n-button
                                                size="tiny"
                                                quaternary
                                                class="action-btn icon-btn btn-red"
                                                @click="confirmDeleteModel(model, plat)"
                                            >
                                                <template #icon><n-icon><Trash /></n-icon></template>
                                            </n-button>
                                        </template>
                                        {{ t('components.aiManager.actions.deleteModel') }}
                                    </n-tooltip>
                                </div>
                            </div>
                        </div>
                        <n-text v-else depth="3" style="font-size: var(--spark-fs-xs);">{{ t('components.aiManager.empty.noModels') }}</n-text>
                    </div>

                    <!-- Embedding 列表（与平台同级展示） -->
                    <div class="model-section" v-if="plat.embeddings">
                        <div v-if="plat.embeddings.length > 0" class="model-list">
                            <div v-for="model in plat.embeddings" :key="model.model_id" class="model-row">
                                <div class="model-info">
                                    <span class="model-display-name">{{ model.display_name }}</span>
                                    <n-tag size="small" :bordered="false" type="error" round>{{ t('components.aiManager.embedding.tag') }}</n-tag>
                                    <n-tooltip v-if="model.extra_body" trigger="hover">
                                        <template #trigger>
                                            <n-tag class="extra-tag-desktop" size="small" :bordered="false" type="info" round>{{ t('components.aiManager.badges.extraBodyBadge') }}</n-tag>
                                        </template>
                                        {{ t('components.aiManager.badges.extraBodyTooltip') }}
                                    </n-tooltip>
                                </div>
                                <div class="model-actions" @click.stop>
                                    <n-tooltip v-if="model.extra_body" trigger="hover">
                                        <template #trigger>
                                            <n-tag class="extra-tag-mobile" size="small" :bordered="false" type="info" round>{{ t('components.aiManager.badges.extraBodyBadge') }}</n-tag>
                                        </template>
                                        {{ t('components.aiManager.badges.extraBodyTooltip') }}
                                    </n-tooltip>
                                    <n-text 
                                        v-if="embeddingSelection.platform_id === plat.platform_id && embeddingSelection.model_id === model.model_id" 
                                        depth="3" 
                                        style="margin-right: 8px; font-size: var(--spark-fs-xs); color: #67c23a; font-weight: bold;"
                                    >
                                        {{ t('components.aiManager.embedding.defaultVector') }}
                                    </n-text>
                                    <n-text 
                                        v-else-if="currentEmbeddingName" 
                                        depth="3" 
                                        style="margin-right: 8px; font-size: var(--spark-fs-2xs); opacity: 0.5;"
                                    >
                                        ({{ t('components.aiManager.embedding.current') }}: {{ currentEmbeddingName }})
                                    </n-text>
                                    <n-tooltip trigger="hover">
                                        <template #trigger>
                                            <n-button
                                                size="tiny"
                                                quaternary
                                                class="action-btn icon-btn btn-green"
                                                @click="saveUserEmbeddingSelection(plat.platform_id, model.model_id)"
                                                :loading="embeddingSaving"
                                                :disabled="embeddingSelection.platform_id === plat.platform_id && embeddingSelection.model_id === model.model_id"
                                            >
                                                <template #icon><n-icon><Zap /></n-icon></template>
                                            </n-button>
                                        </template>
                                        {{ t('components.aiManager.embedding.setDefault') }}
                                    </n-tooltip>
                                    <n-tooltip trigger="hover">
                                        <template #trigger>
                                            <n-button size="tiny" quaternary class="action-btn icon-btn btn-green" @click="testEmbeddingModel(plat, model)">
                                                <template #icon><n-icon><CircleCheck /></n-icon></template>
                                            </n-button>
                                        </template>
                                        {{ t('components.aiManager.actions.testConnection') }}
                                    </n-tooltip>
                                    <n-tooltip v-if="!plat.is_sys || isAdmin" trigger="hover">
                                        <template #trigger>
                                            <n-button size="tiny" quaternary class="action-btn icon-btn btn-blue" @click="openEditEmbeddingModal(plat, model)">
                                                <template #icon><n-icon><SquarePen /></n-icon></template>
                                            </n-button>
                                        </template>
                                        {{ t('views.common.edit') }}
                                    </n-tooltip>
                                    <n-tooltip v-if="!plat.is_sys || isAdmin" trigger="hover">
                                        <template #trigger>
                                            <n-button
                                                size="tiny"
                                                quaternary
                                                class="action-btn icon-btn btn-red"
                                                @click="confirmDeleteEmbedding(model, plat)"
                                            >
                                                <template #icon><n-icon><Trash /></n-icon></template>
                                            </n-button>
                                        </template>
                                        {{ t('views.common.delete') }}
                                    </n-tooltip>
                                </div>
                            </div>
                        </div>
                        <n-text v-else depth="3" style="font-size: var(--spark-fs-xs);">{{ t('components.aiManager.empty.noEmbeddings') }}</n-text>
                    </div>
                </n-collapse-item>
            </n-collapse>
            
            <n-empty v-else :description="t('components.aiManager.empty.noPlatforms')" />
            
        </div>

        <!-- 添加平台弹窗 -->
        <n-modal v-model:show="showAddPlatformModal">
            <n-card 
                style="width: 500px" 
                :title="newPlatform.isSys ? t('components.aiManager.modal.addSystemPlatformTitle') : t('components.aiManager.modal.addCustomPlatformTitle')" 
                :bordered="false" 
                size="huge"
                header-style="padding-bottom: 8px;"
                content-style="padding-top: 0;"
            >
                <n-form>
                    <n-form-item :label="t('components.aiManager.form.platformName')">
                        <n-input v-model:value="newPlatform.name" :placeholder="t('components.aiManager.form.platformNamePlaceholder')" />
                    </n-form-item>
                    <n-form-item label="Base URL">
                        <n-input v-model:value="newPlatform.baseUrl" placeholder="https://api.example.com/v1" :input-props="{ autocomplete: 'off' }" />
                    </n-form-item>
                    <n-form-item :label="t('components.aiManager.form.apiKeyForAll')">
                        <n-input v-model:value="newPlatform.apiKey" type="password" show-password-on="click" :placeholder="t('components.aiManager.form.apiKeyPlaceholder')" :input-props="{ autocomplete: 'new-password' }" />
                    </n-form-item>
                    <n-form-item v-if="isAdmin && newPlatform.isSys" :label="t('components.aiManager.form.platformCreditBalance')">
                        <n-input-number
                            v-model:value="newPlatform.sysCreditBalance"
                            :min="0"
                            :precision="2"
                            :step="10"
                            clearable
                            style="width: 100%"
                            :placeholder="t('components.aiManager.form.platformCreditUnlimited')"
                        />
                    </n-form-item>

                    <!-- 管理员专属：系统平台开关 -->
                    <n-form-item v-if="isAdmin" :show-feedback="false" style="margin-top: 10px;">
                        <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
                            <div style="display: flex; align-items: center; gap: 6px;">
                                <span style="font-weight: 500; font-size: var(--spark-fs-sm); opacity: 0.8;">{{ t('components.aiManager.form.setAsSystemPlatform') }}</span>
                                <n-tooltip trigger="hover" placement="top" :width="240">
                                    <template #trigger>
                                        <n-icon size="16" style="cursor: help; opacity: 0.6; display: flex;">
                                            <Info />
                                        </n-icon>
                                    </template>
                                    {{ t('components.aiManager.form.setAsSystemPlatformHint') }}
                                </n-tooltip>
                            </div>
                            <n-switch size="small" v-model:value="newPlatform.isSys" />
                        </div>
                    </n-form-item>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showAddPlatformModal = false">{{ t('views.common.cancel') }}</n-button>
                        <n-button type="primary" @click="handleAddPlatform" :loading="saving">{{ t('views.common.create') }}</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>

        <!-- 编辑 Embedding 弹窗 -->
        <n-modal v-model:show="showEditEmbeddingModal">
            <n-card style="width: 600px" :title="t('components.aiManager.modal.editEmbeddingTitle')" :bordered="false" size="huge">
                <n-form>
                    <n-form-item :label="t('components.aiManager.form.modelIdentifier')">
                        <n-input :value="editingEmbedding.modelName" disabled />
                    </n-form-item>
                    <n-form-item :label="t('components.aiManager.form.displayName')">
                        <n-input v-model:value="editingEmbedding.displayName" />
                    </n-form-item>
                    <n-form-item :label="t('components.aiManager.form.extraBody')">
                        <n-input
                            v-model:value="editingEmbedding.extraBody"
                            type="textarea"
                            :autosize="{ minRows: 2, maxRows: 10 }"
                        />
                    </n-form-item>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showEditEmbeddingModal = false">{{ t('views.common.cancel') }}</n-button>
                        <n-button type="primary" @click="handleUpdateEmbedding" :loading="embeddingSaving">{{ t('views.common.save') }}</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>

        <!-- 编辑平台弹窗（含密钥配置） -->
        <n-modal v-model:show="showEditPlatformModal">
            <n-card style="width: 500px" :title="t('components.aiManager.modal.editPlatformTitle')" :bordered="false" size="huge">
                <n-form>
                    <SparkAlert
                        v-if="keyAlertMeta(editingPlatform)"
                        style="margin-bottom: 14px"
                        :type="keyAlertMeta(editingPlatform)?.type || 'info'"
                        :title="keyAlertMeta(editingPlatform)?.title || ''"
                    >
                        {{ keyAlertMeta(editingPlatform)?.message || '' }}
                    </SparkAlert>
                    <n-form-item :label="t('components.aiManager.form.platformName')">
                        <n-input v-model:value="editingPlatform.name" :disabled="editingPlatform.is_sys && !isAdmin" />
                    </n-form-item>
                    <n-form-item label="Base URL">
                        <n-input v-model:value="editingPlatform.baseUrl" :input-props="{ autocomplete: 'off' }" :disabled="editingPlatform.is_sys && !isAdmin" />
                    </n-form-item>
                    <n-form-item label="API Key">
                        <n-input v-model:value="editingApiKey" type="password" show-password-on="click" :placeholder="t('components.aiManager.form.enterApiKey')" :input-props="{ autocomplete: 'new-password' }" />
                        <template #feedback>
                            <span v-if="editingPlatform.is_sys && !editingApiKey" style="color: var(--spark-primary); font-size: var(--spark-fs-xs); opacity: 0.8;">
                                {{ t('components.aiManager.form.managedKeyHint') }}
                            </span>
                        </template>
                    </n-form-item>
                    <n-form-item v-if="editingPlatform.is_sys && isAdmin" :label="t('components.aiManager.form.platformCreditBalance')">
                        <n-input-number
                            v-model:value="editingPlatform.sysCreditBalance"
                            :min="0"
                            :precision="2"
                            :step="10"
                            clearable
                            style="width: 100%"
                            :placeholder="t('components.aiManager.form.platformCreditUnlimited')"
                        />
                    </n-form-item>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showEditPlatformModal = false">{{ t('views.common.cancel') }}</n-button>
                        <n-button type="primary" @click="handleUpdatePlatform" :loading="saving">{{ t('views.common.save') }}</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>

        <!-- 添加模型弹窗 -->
        <n-modal v-model:show="showAddModelModal">
            <n-card style="width: 600px" :title="newModel.isEmbedding ? t('components.aiManager.modal.addEmbeddingFor', { platform: currentPlatform?.name || '' }) : t('components.aiManager.modal.addModelFor', { platform: currentPlatform?.name || '' })" :bordered="false" size="huge" header-style="padding-bottom: 8px;" content-style="padding-top: 0;">
                <template #header-extra>
                    <n-tooltip trigger="hover">
                        <template #trigger>
                            <n-button quaternary circle size="small" @click="showAddModelModal = false">
                                <template #icon><n-icon><X /></n-icon></template>
                            </n-button>
                        </template>
                        {{ t('common.close') }}
                    </n-tooltip>
                </template>
                <n-form style="display: flex; flex-direction: column;">
                    <!-- 嵌入模型勾选 -->
                    <n-form-item class="add-model-mode-toggle" :show-feedback="false" style="margin-bottom: 0; order: 99; --n-blank-height: 0px; --n-feedback-height: 0px; --n-feedback-padding: 0;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <n-switch v-model:value="newModel.isEmbedding" />
                            <span style="font-size: var(--spark-fs-sm); opacity: 0.85;">{{ t('components.aiManager.form.isEmbeddingModel') }}</span>
                            <n-tooltip trigger="hover" placement="top">
                                <template #trigger>
                                    <n-icon size="16" style="cursor: help; opacity: 0.5;"><Info /></n-icon>
                                </template>
                                {{ t('components.aiManager.form.isEmbeddingHint') }}
                            </n-tooltip>
                        </div>
                    </n-form-item>
                    <!-- 搜索框 + 探测按钮（仅 LLM 模型显示） -->
                    <n-form-item v-if="!newModel.isEmbedding" :label="t('components.aiManager.form.searchModel')">
                        <n-input-group>
                            <n-input v-model:value="searchKeyword" :placeholder="t('components.aiManager.form.searchModelPlaceholder')" clearable />
                            <n-button @click="fetchRemoteModels(true)" :loading="fetching" type="info" ghost>
                                {{ remoteModels.length > 0 ? t('components.aiManager.actions.refresh') : t('components.aiManager.actions.probeList') }}
                            </n-button>
                        </n-input-group>
                    </n-form-item>
                    
                    <SparkCollapseTransition :show="!newModel.isEmbedding && remoteModels.length > 0">
                        <div class="remote-models-box">
                            <div class="remote-models-header">
                                <n-text depth="3" style="font-size: var(--spark-fs-xs);">
                                    {{ t('components.aiManager.remoteModels.foundCount', { count: remoteModels.length }) }}
                                    <span v-if="searchKeyword && filteredRemoteModels.length !== remoteModels.length">
                                        ({{ t('components.aiManager.remoteModels.matchCount', { count: filteredRemoteModels.length }) }})
                                    </span>
                                </n-text>
                                <n-button size="tiny" text @click="remoteModels = []">{{ t('views.common.close') }}</n-button>
                            </div>
                            <n-space v-if="filteredRemoteModels.length > 0" :size="4" style="flex-wrap: wrap;">
                                <n-tag 
                                    v-for="m in filteredRemoteModels" 
                                    :key="m.id" 
                                    size="small"
                                    clickable 
                                    @click="selectRemoteModel(m)"
                                    :type="newModel.modelName === m.id ? 'primary' : 'default'"
                                >
                                    {{ m.id }}
                                </n-tag>
                            </n-space>
                            <n-text v-else depth="3" style="font-size: var(--spark-fs-xs);">{{ t('components.aiManager.remoteModels.noMatch') }}</n-text>
                        </div>
                    </SparkCollapseTransition>

                    <!-- 模型ID（可编辑） -->
                    <n-form-item :label="t('components.aiManager.form.modelNameLabel')">
                        <n-input 
                            v-model:value="newModel.modelName" 
                            :placeholder="t('components.aiManager.form.modelNamePlaceholder')" 
                        />
                    </n-form-item>

                    <n-form-item :label="t('components.aiManager.form.displayName')">
                        <n-input v-model:value="newModel.displayName" :placeholder="t('components.aiManager.form.displayNamePlaceholder')" />
                    </n-form-item>
                    <n-form-item v-if="currentPlatform?.is_sys && !newModel.isEmbedding" :label="t('components.aiManager.form.modelInputPrice')">
                        <n-input-number v-model:value="newModel.inputPricePerMillion" :min="0" :precision="2" :step="0.01" style="width: 100%" :placeholder="t('components.aiManager.form.zeroIsFree')" :disabled="!systemConfig.billing_enabled" />
                        <template #feedback>
                            <span v-if="!systemConfig.billing_enabled" class="form-hint">{{ t('components.aiManager.form.enableBillingBeforePricing') }}</span>
                        </template>
                    </n-form-item>
                    <n-form-item v-if="currentPlatform?.is_sys && !newModel.isEmbedding" :label="t('components.aiManager.form.modelOutputPrice')">
                        <n-input-number v-model:value="newModel.outputPricePerMillion" :min="0" :precision="2" :step="0.01" style="width: 100%" :placeholder="t('components.aiManager.form.zeroIsFree')" :disabled="!systemConfig.billing_enabled" />
                    </n-form-item>
                    <n-form-item v-if="!newModel.isEmbedding" :label="t('components.aiManager.form.temperatureOptional')">
                        <n-space vertical :size="6" class="temp-setting-block">
                            <div class="temp-setting-row">
                                <n-switch v-model:value="newModel.temperatureEnabled">
                                    <template #checked>{{ t('components.aiManager.form.enabled') }}</template>
                                    <template #unchecked>{{ t('components.aiManager.form.disabled') }}</template>
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
                            <div class="temp-hint-line">
                                <n-icon class="temp-hint-icon"><CircleAlert /></n-icon>
                                <n-text depth="3" class="temp-hint-text">
                                    {{ t('components.aiManager.form.temperatureHint') }}
                                </n-text>
                            </div>
                        </n-space>
                    </n-form-item>
                    <n-form-item v-if="!newModel.isEmbedding" :label="t('components.aiManager.form.maxContextTokens')">
                        <n-input-number v-model:value="newModel.maxContextTokens" :min="0" :step="1000" style="width: 100%" :placeholder="t('components.aiManager.form.maxTokensAutoHint')" clearable />
                    </n-form-item>
                    <n-form-item v-if="!newModel.isEmbedding" :label="t('components.aiManager.form.maxOutputTokens')">
                        <n-input-number v-model:value="newModel.maxOutputTokens" :min="0" :step="1000" style="width: 100%" :placeholder="t('components.aiManager.form.maxTokensAutoHint')" clearable />
                    </n-form-item>
                    <n-form-item class="add-model-extra-body" :show-feedback="false" :label="t('components.aiManager.form.extraBodyOptional')">
                        <n-input 
                            v-model:value="newModel.extraBody" 
                            type="textarea" 
                            :autosize="{ minRows: 2, maxRows: 10 }"
                            :placeholder="newModel.isEmbedding ? t('components.aiManager.form.extraBodyEmbeddingPlaceholder') : t('components.aiManager.form.extraBodyModelPlaceholder')"
                        />
                    </n-form-item>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: space-between;">
                        <n-button @click="testModelConnection" :loading="testing" type="info" secondary :disabled="!newModel.modelName">{{ t('components.aiManager.actions.test') }}</n-button>
                        <div style="display: flex; gap: 10px;">
                            <n-button @click="showAddModelModal = false">{{ t('views.common.cancel') }}</n-button>
                            <n-button type="primary" @click="handleAddModel" :loading="saving">{{ t('views.common.create') }}</n-button>
                        </div>
                    </div>
                </template>
            </n-card>
        </n-modal>

        <!-- 编辑模型弹窗 -->
        <n-modal v-model:show="showEditModelModal">
            <n-card style="width: 600px" :title="t('components.aiManager.modal.editModelTitle')" :bordered="false" size="huge">
                <n-form>
                    <n-form-item :label="t('components.aiManager.form.modelIdentifier')">
                        <n-input :value="editingModel.modelName" disabled />
                    </n-form-item>
                    <n-form-item :label="t('components.aiManager.form.displayName')">
                        <n-input v-model:value="editingModel.displayName" />
                    </n-form-item>
                    <n-form-item v-if="currentPlatform?.is_sys" :label="t('components.aiManager.form.modelInputPrice')">
                        <n-input-number v-model:value="editingModel.inputPricePerMillion" :min="0" :precision="2" :step="0.01" style="width: 100%" :placeholder="t('components.aiManager.form.zeroIsFree')" :disabled="!systemConfig.billing_enabled" />
                        <template #feedback>
                            <span v-if="!systemConfig.billing_enabled" class="form-hint">{{ t('components.aiManager.form.enableBillingBeforePricing') }}</span>
                        </template>
                    </n-form-item>
                    <n-form-item v-if="currentPlatform?.is_sys" :label="t('components.aiManager.form.modelOutputPrice')">
                        <n-input-number v-model:value="editingModel.outputPricePerMillion" :min="0" :precision="2" :step="0.01" style="width: 100%" :placeholder="t('components.aiManager.form.zeroIsFree')" :disabled="!systemConfig.billing_enabled" />
                    </n-form-item>
                    <n-form-item :label="t('components.aiManager.form.temperatureOptional')">
                        <n-space vertical :size="6" class="temp-setting-block">
                            <div class="temp-setting-row">
                                <n-switch v-model:value="editingModel.temperatureEnabled">
                                    <template #checked>{{ t('components.aiManager.form.enabled') }}</template>
                                    <template #unchecked>{{ t('components.aiManager.form.disabled') }}</template>
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
                            <div class="temp-hint-line">
                                <n-icon class="temp-hint-icon"><CircleAlert /></n-icon>
                                <n-text depth="3" class="temp-hint-text">
                                    {{ t('components.aiManager.form.temperatureHint') }}
                                </n-text>
                            </div>
                        </n-space>
                    </n-form-item>
                    <n-form-item :label="t('components.aiManager.form.maxContextTokens')">
                        <n-input-number v-model:value="editingModel.maxContextTokens" :min="0" :step="1000" style="width: 100%" :placeholder="t('components.aiManager.form.maxTokensAutoHint')" clearable />
                    </n-form-item>
                    <n-form-item :label="t('components.aiManager.form.maxOutputTokens')">
                        <n-input-number v-model:value="editingModel.maxOutputTokens" :min="0" :step="1000" style="width: 100%" :placeholder="t('components.aiManager.form.maxTokensAutoHint')" clearable />
                    </n-form-item>
                    <n-form-item :show-feedback="false" :label="t('components.aiManager.form.extraBody')">
                        <n-input 
                            v-model:value="editingModel.extraBody" 
                            type="textarea" 
                            :autosize="{ minRows: 2, maxRows: 10 }"
                            :placeholder="t('components.aiManager.form.extraBodyModelPlaceholder')"
                        />
                    </n-form-item>
                </n-form>
                <template #footer>
                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <n-button @click="showEditModelModal = false">{{ t('views.common.cancel') }}</n-button>
                        <n-button type="primary" @click="handleUpdateModel" :loading="saving">{{ t('views.common.save') }}</n-button>
                    </div>
                </template>
            </n-card>
        </n-modal>
    </div>
</template>


<script setup lang="ts">
/**
 * AI 平台与模型管理
 * 业务逻辑已提取到 3 个 composable：
 * - useAIPlatformManager: 平台 CRUD、系统配置、数据加载
 * - useAIModelManager: 模型 CRUD、测速、远程探测、内联编辑
 * - useAIEmbeddingManager: Embedding CRUD、选择管理
 */
import { ref, onMounted, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';
import {
    NSpin, NCollapse, NCollapseItem, NText, NSpace, NButton, NIcon, NModal, NCard,
    NForm, NFormItem, NInput, NInputGroup, NInputNumber, NEmpty, NTooltip, NPopconfirm,
    NSwitch, NTag, useDialog, useMessage,
} from 'naive-ui';
import SparkAlert from '@/components/share/SparkAlert.vue';
import SparkCollapseTransition from '@/components/share/SparkCollapseTransition.vue';
import { Activity, CircleAlert, CircleCheck, CloudUpload, Download, Info, Key, Lock, Menu, Plus, Server, SquarePen, Trash, Unlock, User, X, Zap } from 'lucide-vue-next';
import SparkTag from '@/components/share/SparkTag.vue';
import SparkIcon from '@/components/share/CreditIcon.vue';
import SparkLoaderAnimation from '@/components/share/SparkLoaderAnimation.vue';

import { useAIPlatformManager } from '@/composables/useAIPlatformManager';
import { useAIModelManager } from '@/composables/useAIModelManager';
import { useAIEmbeddingManager } from '@/composables/useAIEmbeddingManager';
import Sortable from 'sortablejs';
import { useAiStore } from '@/components/stores/aiStore';
import type { AiPlatform, AiModelItem, ApiId } from '@/services/aiContracts';
import { fetchWithAuth } from '@/services/api';

const aiStore = useAiStore();
const { t } = useI18n();
const message = useMessage();

type TagKind = 'default' | 'primary' | 'info' | 'success' | 'warning' | 'error';
type AlertKind = 'info' | 'success' | 'warning' | 'error';

type BadgeMeta = {
    text: string;
    type: TagKind;
};

type AlertMeta = {
    type: AlertKind;
    title: string;
    message: string;
};

type KeyAlertTarget = {
    api_key_message?: string;
    api_key_status?: string;
};

type CreditTagMeta = {
    type: TagKind;
    text: string;
    title: string;
};

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

// === 系统平台密钥状态标签 ===
function platKeyTagType(plat) {
    if (plat.user_key_override) return 'info';
    if (plat.api_key_set) return 'success';
    if (['managed_missing_key', 'managed_needs_reconfigure', 'managed_available_but_locked', 'user_override_missing_key', 'user_override_needs_reconfigure', 'needs_reconfigure', 'missing_key'].includes(plat.api_key_status)) {
        return 'warning';
    }
    return 'error';
}
function platKeyTagTip(plat) {
    if (plat.user_key_override) {
        return plat.user_key_message || t('components.aiManager.messages.usingUserKey');
    }
    if (plat.api_key_set) {
        return plat.api_key_message || t('components.aiManager.messages.usingManagedKey');
    }
    return plat.api_key_message || t('components.aiManager.messages.noAvailableKey');
}

function platformStatusBadge(plat: AiPlatform): BadgeMeta | null {
    if (plat.api_key_set) return null;

    const status = plat.api_key_status || 'missing';
    if (status === 'managed_missing_key' || status === 'user_override_missing_key' || status === 'missing_key') {
        return { text: t('components.aiManager.badges.masterKeyPending'), type: 'warning' };
    }
    if (status === 'managed_needs_reconfigure') {
        return { text: t('components.aiManager.badges.managedPending'), type: 'warning' };
    }
    if (status === 'managed_available_but_locked') {
        return { text: t('components.aiManager.badges.userConfigNeeded'), type: 'warning' };
    }
    if (status === 'user_override_needs_reconfigure' || status === 'user_override_failed' || status === 'failed' || status === 'needs_reconfigure') {
        return { text: t('components.aiManager.badges.reconfigureNeeded'), type: 'warning' };
    }
    return { text: t('components.aiManager.badges.keyMissing'), type: 'warning' };
}

function keyAlertMeta(plat: KeyAlertTarget | null | undefined): AlertMeta | null {
    if (!plat?.api_key_message) return null;

    if (plat.api_key_status === 'managed_missing_key' || plat.api_key_status === 'missing_key' || plat.api_key_status === 'user_override_missing_key') {
        return {
            type: 'warning',
            title: t('components.aiManager.alerts.savedKeyNotReadableTitle'),
            message: plat.api_key_message,
        };
    }

    if (plat.api_key_status === 'managed_needs_reconfigure') {
        return {
            type: 'warning',
            title: t('components.aiManager.alerts.managedNeedsReconfigureTitle'),
            message: plat.api_key_message,
        };
    }

    if (plat.api_key_status === 'user_override_needs_reconfigure' || plat.api_key_status === 'user_override_failed' || plat.api_key_status === 'failed' || plat.api_key_status === 'needs_reconfigure') {
        return {
            type: 'warning',
            title: t('components.aiManager.alerts.savedKeyDecryptFailedTitle'),
            message: plat.api_key_message,
        };
    }

    if (plat.api_key_status === 'managed_available_but_locked') {
        return {
            type: 'info',
            title: t('components.aiManager.alerts.managedLockedTitle'),
            message: plat.api_key_message,
        };
    }

    return null;
}

function formatCreditPriceTag(price) {
    const num = Number(price);
    if (!Number.isFinite(num) || num < 0) return t('components.aiManager.pricing.unpriced');
    if (Number.isInteger(num)) return `${num}/M`;
    return `${num.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')}/M`;
}

function modelCreditTagMeta(plat: AiPlatform, model: AiModelItem): CreditTagMeta {
    const inputPrice = model?.sys_credit_input_price_per_million;
    const outputPrice = model?.sys_credit_output_price_per_million;

    if (inputPrice == null || outputPrice == null) {
        return {
            type: systemConfig.value.billing_enabled ? 'warning' : 'default',
            text: t('components.aiManager.pricing.unpriced'),
            title: systemConfig.value.billing_enabled
                ? t('components.aiManager.pricing.unpricedBlockedHint')
                : t('components.aiManager.pricing.unpricedIgnoredHint'),
        };
    }

    const inputTag = formatCreditPriceTag(inputPrice);
    const outputTag = formatCreditPriceTag(outputPrice);
    if (Number(inputPrice) === 0 && Number(outputPrice) === 0) {
        return {
            type: 'success',
            text: t('components.aiManager.pricing.free'),
            title: t('components.aiManager.pricing.freeHint'),
        };
    }
    return {
        type: 'warning',
        text: `${t('components.aiManager.pricing.inputPrefix')}${inputTag} / ${t('components.aiManager.pricing.outputPrefix')}${outputTag}`,
        title: t('components.aiManager.pricing.modelOverrideTitle'),
    };
}

function platformCreditText(plat: AiPlatform) {
    const balance = plat.sys_credit_balance;
    if (balance === null || balance === undefined) return t('components.aiManager.pricing.unlimited');
    const num = Number(balance);
    if (!Number.isFinite(num)) return t('components.aiManager.pricing.unlimited');
    if (Number.isInteger(num)) return String(num);
    return num.toFixed(2).replace(/0+$/, '').replace(/\.$/, '');
}

function platformCreditTagType(plat: AiPlatform): TagKind {
    const balance = plat.sys_credit_balance;
    if (balance === null || balance === undefined) return 'success';
    return Number(balance) > 0 ? 'warning' : 'error';
}

function platformCreditTagTitle(plat: AiPlatform) {
    const balance = plat.sys_credit_balance;
    if (balance === null || balance === undefined) {
        return t('components.aiManager.pricing.platformUnlimitedHint');
    }
    if (Number(balance) <= 0) {
        return t('components.aiManager.pricing.platformDepletedHint');
    }
    return t('components.aiManager.pricing.platformBalanceHint');
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
    toggleBillingEnabled,
    openKeyModal,
    openEditPlatformModal,
    handleAddPlatform,
    handleUpdatePlatform,
    handleUpdateKey,
    confirmDeletePlatform,
    doDeletePlatform,
    downloadSysConfig,
    saveSysConfigToYaml,
    reorderPlatforms,
    reorderModels
} = useAIPlatformManager({ syncAiStoreSilently });

// === 平台名内联编辑 ===
const editingPlatformId = ref<ApiId | null>(null);
const editingPlatformNameValue = ref('');
const platformInlineInputRef = ref<unknown>(null);

function startEditPlatformName(plat: AiPlatform) {
    editingPlatformId.value = plat.platform_id;
    editingPlatformNameValue.value = plat.name;
    nextTick(() => {
        if (platformInlineInputRef.value) {
            const el = Array.isArray(platformInlineInputRef.value) ? platformInlineInputRef.value[0] : platformInlineInputRef.value;
            if (el && typeof el.focus === 'function') {
                el.focus();
            }
        }
    });
}

function cancelEditPlatformName() {
    editingPlatformId.value = null;
    editingPlatformNameValue.value = '';
}

async function confirmEditPlatformName(plat: AiPlatform) {
    const newName = editingPlatformNameValue.value.trim();
    if (!newName || newName === plat.name) {
        cancelEditPlatformName();
        return;
    }
    const isSysPlatform = Boolean(plat.is_sys && isAdmin.value);
    try {
        const url = isSysPlatform ? '/api/ai/admin/sys-platform' : '/api/ai/platform';
        const payload = isSysPlatform
            ? { platform_id: plat.platform_id, name: newName, base_url: plat.base_url }
            : { id: plat.platform_id, name: newName, base_url: plat.base_url };
        const res = await fetchWithAuth(url, {
            method: 'PUT',
            body: JSON.stringify(payload),
            headers: { 'Content-Type': 'application/json' },
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '更新失败');
        }
        plat.name = newName;
        syncAiStoreSilently();
    } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        message.error(msg);
    } finally {
        cancelEditPlatformName();
    }
}

const dialog = useDialog();

function confirmSaveToYaml() {
    dialog.warning({
        title: t('components.aiManager.confirm.overwriteTitle'),
        content: t('components.aiManager.confirm.overwriteContent'),
        positiveText: t('components.aiManager.confirm.overwriteConfirm'),
        negativeText: t('views.common.cancel'),
        maskClosable: false,
        onPositiveClick: () => { saveSysConfigToYaml(); },
    });
}

const vSortable = {
    mounted(el, binding) {
        const opts = binding.value || {};
        el._sortable = Sortable.create(el, {
            animation: 250,
            handle: '.drag-handle',
            ...opts
        });
    },
    updated(el, binding) {
        if (el._sortable && binding.value) {
            el._sortable.option('disabled', !!binding.value.disabled);
        }
    },
    unmounted(el) {
        if (el._sortable) el._sortable.destroy();
    }
};

function revertDOM(evt) {
    if (!evt.from || evt.oldIndex === evt.newIndex) return;
    const itemEl = evt.item;
    const children = (Array.from((evt.from as HTMLElement).children) as HTMLElement[])
        .filter(c => !c.classList.contains('sortable-ghost') && !c.classList.contains('sortable-drag'));
    const referenceNode = evt.oldIndex < evt.newIndex ? children[evt.oldIndex] : children[evt.oldIndex + 1];
    evt.from.insertBefore(itemEl, referenceNode || null);
}

function onPlatformSortEnd(evt) {
    if (evt.oldIndex === evt.newIndex) return;
    revertDOM(evt);
    
    const moved = platforms.value.splice(evt.oldIndex, 1)[0];
    platforms.value.splice(evt.newIndex, 0, moved);
    
    reorderPlatforms(platforms.value.map(p => p.platform_id));
}

function onModelSortEnd(evt, plat) {
    if (evt.oldIndex === evt.newIndex) return;
    revertDOM(evt);
    
    const moved = plat.models.splice(evt.oldIndex, 1)[0];
    plat.models.splice(evt.newIndex, 0, moved);
    
    if (plat.is_sys) {
        reorderModels(plat.platform_id, plat.models.map(m => m.model_id));
    }
}



// === 统一数据加载回调 ===
// 平台 composable 只加载平台+模型，需要额外加载 embedding 数据
async function loadData() {
    await loadPlatforms();
    await embedding.loadEmbeddings();
    await aiStore.loadData(true, true);
}

function syncAiStoreSilently() {
    aiStore.loadData(true, true).catch((e) => {
        console.warn('AI 缓存静默同步失败:', e);
    });
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
    clearSpeedResult,
    testExistingModel,
    handleAddModel,
    handleUpdateModel,
    confirmDeleteModel,
    doDeleteModel,
    startEditDisplayName,
    cancelEditDisplayName,
    confirmEditDisplayName,
} = useAIModelManager(platforms, syncAiStoreSilently, systemConfig);

// === Embedding 管理 ===
const embedding = useAIEmbeddingManager(platforms, syncAiStoreSilently);
const {
    embeddingSelection,
    embeddingSaving,
    showEditEmbeddingModal,
    editingEmbedding,
    currentEmbeddingName,
    openEditEmbeddingModal,
    handleUpdateEmbedding,
    confirmDeleteEmbedding,
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
