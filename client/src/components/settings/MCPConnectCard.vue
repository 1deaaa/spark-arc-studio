
<template>
  <n-card class="mcp-card" size="small">
    <template #header>
      <div class="card-header" @click="toggleFold">
        <n-icon size="18" :component="Pulse" color="#63e2b7" />
        <span class="title">灵感捕手 (MCP Service)</span>
        <div class="header-controls">
           <n-tag :type="hasKey ? 'success' : 'default'" size="small" round>
             {{ hasKey ? 'Running' : 'Not Configured' }}
           </n-tag>
           <n-icon size="20" :component="ChevronDown" class="fold-icon" :class="{ folded: isFolded }" />
        </div>
      </div>
    </template>

    <n-collapse-transition :show="!isFolded">
        <div class="card-content">
            <n-alert type="info" :show-icon="false" class="desc-alert">
                允许在任何支持MCP的平台（RikkaHub、CherryStudio等）把你在聊天中的灵光一现整理总结发送到 SparkArc，不让灵感因空间而被错过。
            </n-alert>

            <!-- API Key Section -->
            <div class="key-section">
                <div class="section-label">您的 MCP API Key</div>
                <n-input-group>
                    <n-input 
                        :value="displayKey" 
                        readonly 
                        placeholder="未生成 Key" 
                        :style="{ fontFamily: 'monospace' }"
                    />
                    <n-button type="primary" secondary @click="copyKey" :disabled="!hasKey">
                        <template #icon><n-icon :component="CopyOutline" /></template>
                    </n-button>
                    <n-popconfirm @positive-click="resetKey">
                        <template #trigger>
                            <n-button type="error" secondary>
                                <template #icon><n-icon :component="RefreshOutline" /></template>
                            </n-button>
                        </template>
                        确定要重置 Key 吗？这将导致旧 Key 失效。
                    </n-popconfirm>
                </n-input-group>
            </div>

            <!-- Config Guide -->
            <div class="guide-section">
                <n-tabs type="segment" v-model:value="activeTab" size="small" class="config-tabs">
                    <n-tab-pane name="json" tab="JSON">
                        <div class="code-wrapper">
                            <n-code :code="claudeConfigJson" language="json" word-wrap />
                            <n-button size="tiny" secondary class="copy-btn" @click="copyText(claudeConfigJson)">
                                <template #icon><n-icon :component="CopyOutline" /></template>
                                复制
                            </n-button>
                        </div>
                    </n-tab-pane>
                    <n-tab-pane name="cursor" tab="文本配置">
                         <div class="info-block">
                            <n-descriptions label-placement="left" size="small" :column="1" :label-style="{ width: '50px' }">
                                <n-descriptions-item label="Type">
                                    SSE (HTTP Streaming / Server-Sent Events)
                                </n-descriptions-item>
                                <n-descriptions-item label="URL">
                                    <n-input-group style="width: 100%">
                                        <n-input :value="sseUrl" readonly size="small" style="flex: 1; min-width: 300px; font-family: monospace;" />
                                        <n-button size="small" @click="copyText(sseUrl)">
                                            <template #icon><n-icon :component="CopyOutline" /></template>
                                        </n-button>
                                    </n-input-group>
                                </n-descriptions-item>
                            </n-descriptions>
                            <n-alert type="warning" size="small" class="mt-2">
                                部分客户端（如 Cursor）可能需要将 Key 拼接到 URL 参数中 (尚未支持) 或等待更新。
                                <br/>推荐使用 Claude Desktop 或支持 MCP 协议的专用客户端。
                            </n-alert>
                        </div>
                    </n-tab-pane>
                </n-tabs>
            </div>
        </div>
    </n-collapse-transition>
  </n-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { 
    NCard, NIcon, NTag, NCollapseTransition, NAlert, NInput, NInputGroup, 
    NButton, NPopconfirm, NTabs, NTabPane, NCode, NDescriptions, NDescriptionsItem,
    useMessage
} from 'naive-ui';
import { 
    Pulse, ChevronDown, CopyOutline, RefreshOutline 
} from '@vicons/ionicons5';
import { fetchWithAuth } from '../../services/api';

const message = useMessage();
const isFolded = ref(false);
const apiKey = ref('');
const activeTab = ref('json');

const hasKey = computed(() => !!apiKey.value);
const displayKey = computed(() => {
    if (!apiKey.value) return '';
    return apiKey.value.substring(0, 16) + '****************'; // Masked
});

const sseUrl = computed(() => `${window.location.protocol}//${window.location.hostname}:${window.location.port}/api/mcp/sse`);

const claudeConfigJson = computed(() => {
    const keyStr = apiKey.value || "YOUR_API_KEY_HERE";
    return JSON.stringify({
        "mcpServers": {
            "spark-inspiration": {
                "command": "node",
                "args": [], 
                "disabled_note": "Please use SSE configuration if supported, otherwise use transport override",
                "url": sseUrl.value,
                "transport": "sse",
                "headers": {
                    "Authorization": `Bearer ${keyStr}`
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
                message.success('API Key 已重置');
            }
        }
    } catch (e) {
        message.error("重置失败: " + e.message);
    }
}

function copyKey() {
    if (!apiKey.value) return;
    navigator.clipboard.writeText(apiKey.value);
    message.success('Key 已复制');
}

function copyText(text) {
    navigator.clipboard.writeText(text);
    message.success('已复制');
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

.section-label {
    font-size: 12px;
    color: var(--spark-text-muted);
    margin-bottom: 8px;
}

.guide-section {
    border-top: 1px solid var(--spark-border);
    padding-top: 16px;
}

.code-wrapper {
    position: relative;
    background-color: var(--spark-bg); /* Use theme bg instead of black */
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
</style>
