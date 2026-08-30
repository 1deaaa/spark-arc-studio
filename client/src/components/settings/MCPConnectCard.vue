
<template>
  <n-card class="mcp-card" size="small">
    <template #header>
      <div class="card-header" @click="toggleFold">
        <n-icon size="18" :component="Activity" color="#63e2b7" />
        <span class="title">{{ t('components.mcpConnectCard.title') }}</span>
        <div class="header-controls">
           <SparkTag :type="hasKey ? 'success' : 'default'" size="small">
             {{ hasKey ? t('components.mcpConnectCard.running') : t('components.mcpConnectCard.notConfigured') }}
           </SparkTag>
           <n-icon size="20" :component="ChevronDown" class="fold-icon" :class="{ folded: isFolded }" />
        </div>
      </div>
    </template>

    <SparkCollapseTransition :show="!isFolded">
        <div class="card-content">
            <SparkAlert type="info" :show-icon="false" class="desc-alert">
                {{ t('components.mcpConnectCard.description') }}
            </SparkAlert>

            <!-- API Key 区域 -->
            <div class="key-section">
                <div class="section-label">{{ t('components.mcpConnectCard.yourApiKey') }}</div>
                <n-input-group class="key-input-group">
                    <n-input 
                        :value="displayKey" 
                        readonly 
                        :placeholder="t('components.mcpConnectCard.noKeyGenerated')"
                        :style="{ fontFamily: 'var(--spark-mono)' }"
                    />
                    <n-button type="primary" secondary @click="copyKey" :disabled="!hasKey">
                        <template #icon><n-icon :component="Copy" /></template>
                    </n-button>
                    <n-popconfirm @positive-click="resetKey">
                        <template #trigger>
                            <n-button type="error" secondary>
                                <template #icon><n-icon :component="RefreshCw" /></template>
                            </n-button>
                        </template>
                        {{ t('components.mcpConnectCard.confirmResetKey') }}
                    </n-popconfirm>
                </n-input-group>
            </div>

            <!-- 配置指南 -->
            <div class="guide-section">
                <n-tabs type="segment" v-model:value="activeTab" size="small" class="config-tabs spark-segment-tabs">
                    <n-tab-pane name="json" :tab="t('components.mcpConnectCard.jsonConfig')">
                        <div class="code-wrapper">
                            <n-code :code="claudeConfigJson" language="json" word-wrap />
                            <n-button size="tiny" secondary class="copy-btn" @click="copyText(claudeConfigJson)">
                                <template #icon><n-icon :component="Copy" /></template>
                                {{ t('components.mcpConnectCard.copy') }}
                            </n-button>
                        </div>
                    </n-tab-pane>
                    <n-tab-pane name="cursor" :tab="t('components.mcpConnectCard.textConfig')">
                         <div class="info-block">
                            <n-descriptions label-placement="left" size="small" :column="1" :label-style="{ width: '50px' }">
                                <n-descriptions-item :label="t('components.mcpConnectCard.typeLabel')">
                                    {{ t('components.mcpConnectCard.streamableHttp') }}
                                </n-descriptions-item>
                                <n-descriptions-item :label="t('components.mcpConnectCard.unifiedUrlLabel')">
                                    <n-input-group style="width: 100%">
                                        <n-input :value="mcpUnifiedUrl" readonly size="small" class="mcp-config-input" />
                                        <n-button size="small" @click="copyText(mcpUnifiedUrl)">
                                            <template #icon><n-icon :component="Copy" /></template>
                                        </n-button>
                                    </n-input-group>
                                </n-descriptions-item>
                                <n-descriptions-item :label="t('components.mcpConnectCard.legacyControlUrlLabel')">
                                    <n-input-group style="width: 100%">
                                        <n-input :value="mcpLegacyControlUrl" readonly size="small" class="mcp-config-input" />
                                        <n-button size="small" @click="copyText(mcpLegacyControlUrl)">
                                            <template #icon><n-icon :component="Copy" /></template>
                                        </n-button>
                                    </n-input-group>
                                </n-descriptions-item>
                                <n-descriptions-item :label="t('components.mcpConnectCard.headersLabel')">
                                    <n-input-group style="width: 100%">
                                        <n-input
                                            type="textarea"
                                            :autosize="{ minRows: 3, maxRows: 5 }"
                                            :value="mcpHeaderText"
                                            readonly
                                            size="small"
                                            class="mcp-config-input"
                                        />
                                        <n-button size="small" style="height: auto" @click="copyText(mcpHeaderText)">
                                            <template #icon><n-icon :component="Copy" /></template>
                                        </n-button>
                                    </n-input-group>
                                </n-descriptions-item>
                            </n-descriptions>
                            <SparkAlert type="warning" style="margin-top: 8px;">
                                {{ t('components.mcpConnectCard.cursorWarning') }}
                            </SparkAlert>
                        </div>
                    </n-tab-pane>
                </n-tabs>
            </div>
        </div>
    </SparkCollapseTransition>
  </n-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import {
    NCard, NIcon, NInput, NInputGroup, 
    NButton, NPopconfirm, NTabs, NTabPane, NCode, NDescriptions, NDescriptionsItem,
    useMessage
} from 'naive-ui';
import SparkCollapseTransition from '../share/SparkCollapseTransition.vue';
import SparkTag from '../share/SparkTag.vue';
import SparkAlert from '../share/SparkAlert.vue';
import { Activity, ChevronDown, Copy, RefreshCw } from '@lucide/vue';
import { fetchWithAuth } from '../../services/api';

const { t } = useI18n();
const message = useMessage();
const isFolded = ref(false);
const apiKey = ref('');
const activeTab = ref('json');

const hasKey = computed(() => !!apiKey.value);
const displayKey = computed(() => {
    if (!apiKey.value) return '';
    return apiKey.value;
});

const mcpBaseUrl = computed(() => `${window.location.protocol}//${window.location.host}`);
const mcpUnifiedUrl = computed(() => `${mcpBaseUrl.value}/api/mcp/`);
const mcpLegacyControlUrl = computed(() => `${mcpBaseUrl.value}/api/mcp/control/`);
const mcpHeaderText = computed(() => `Authorization=${apiKey.value || 'YOUR_KEY'}`);

const claudeConfigJson = computed(() => {
    const keyStr = apiKey.value || "YOUR_API_KEY_HERE";
    return JSON.stringify({
        "mcpServers": {
            "spark-arc": {
                "type": "http",
                "url": mcpUnifiedUrl.value,
                "headers": {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "Authorization": `${keyStr}`
                }
            }
        }
    }, null, 2);
});

function toggleFold() {
    isFolded.value = !isFolded.value;
}

async function loadKey() {
    try {
        const res = await fetchWithAuth('/api/user/mcp-key');
        if (res.ok) {
            const data = await res.json();
            if (data.success && data.key) {
                apiKey.value = data.key;
            }
        }
    } catch (e) {
        console.error("Failed to load MCP key", e);
    }
}

async function resetKey() {
    try {
        const res = await fetchWithAuth('/api/user/mcp-key/reset', { method: 'POST' });
        if (res.ok) {
            const data = await res.json();
            if (data.success) {
                apiKey.value = data.key;
                message.success(t('components.mcpConnectCard.keyResetSuccess'));
            }
        }
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || t('common.unknownError'));
        message.error(t('components.mcpConnectCard.resetFailed') + ': ' + errorMessage);
    }
}

function copyKey() {
    if (!apiKey.value) return;
    navigator.clipboard.writeText(apiKey.value);
    message.success(t('components.mcpConnectCard.keyCopied'));
}

function copyText(text: string) {
    navigator.clipboard.writeText(text);
    message.success(t('components.mcpConnectCard.copied'));
}

onMounted(() => {
    loadKey();
});
</script>

<style scoped>
.mcp-card {
    margin-bottom: 20px;
    border-color: var(--spark-border);
    background-color: var(--spark-panel-bg);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  width: 100%;
}

.card-header .title {
    margin-left: 8px;
    font-weight: 600;
    color: var(--spark-text-highlight);
    flex: 1;
}

.header-controls {
    display: flex;
    align-items: center;
    gap: 12px;
}

.fold-icon {
    transition: transform 0.3s;
    color: var(--spark-text-muted);
}
.fold-icon.folded {
    transform: rotate(-90deg);
}

.card-content {
    padding-top: 12px;
}

.desc-alert {
    margin-bottom: 16px;
    background-color: rgba(var(--spark-primary-rgb), 0.05);
    border: none;
}

.key-section {
    margin-bottom: 20px;
}

.key-input-group {
    width: 100%;
}

.section-label {
    font-size: var(--spark-fs-xs);
    color: var(--spark-text-muted);
    margin-bottom: 8px;
}

.guide-section {
    border-top: 1px solid var(--spark-border);
    padding-top: 16px;
}

.code-wrapper {
    position: relative;
    background-color: var(--spark-bg); /* 使用主题背景色 */
    border: 1px solid var(--spark-border);
    border-radius: 4px;
    padding: 12px;
}

.copy-btn {
    position: absolute;
    top: 8px;
    right: 8px;
}

.mt-2 {
    margin-top: 8px;
}

.mcp-config-input {
    flex: 1;
    min-width: 0;
    font-family: var(--spark-mono);
}

@media (max-width: 720px) {
    .mcp-card {
        margin-bottom: 0;
    }

    .card-header {
        gap: 8px;
    }

    .card-header .title {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .header-controls {
        gap: 8px;
        flex-shrink: 0;
    }

    .card-content {
        padding-top: 8px;
    }

    .desc-alert {
        margin-bottom: 12px;
    }

    .key-section {
        margin-bottom: 14px;
    }

    .key-input-group :deep(.n-input) {
        min-width: 0;
    }

    .key-input-group :deep(.n-button) {
        width: 40px;
        padding: 0;
        flex: 0 0 40px;
    }

    .guide-section {
        padding-top: 12px;
    }

    .code-wrapper {
        padding: 10px;
        max-height: 260px;
        overflow: auto;
    }

    .copy-btn {
        position: sticky;
        top: 0;
        float: right;
        margin-left: 8px;
    }

    .info-block :deep(.n-descriptions-table-wrapper) {
        overflow: visible;
    }
}
</style>
