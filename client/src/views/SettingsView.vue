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
                    <h3>外观设置</h3>
                    <p class="section-desc">自定义主题主色与全局字体（字号与具体风格仍由各处样式控制）。</p>

                    <n-form label-placement="left" label-width="90">
                        <div class="appearance-grid">
                            <n-form-item label="暗色主色">
                                <n-color-picker v-model:value="themePrimaryColorDark" :show-alpha="false" :modes="['hex']" />
                            </n-form-item>
                            <n-form-item label="亮色主色">
                                <n-color-picker v-model:value="themePrimaryColorLight" :show-alpha="false" :modes="['hex']" />
                            </n-form-item>
                                                        <n-form-item label="全局字体" class="appearance-font">
                                                                <n-select
                                                                    v-model:value="fontFamily"
                                                                    :options="fontOptions"
                                                                    :render-label="renderFontOptionLabel"
                                                                    filterable
                                                                    tag
                                                                    :on-create="handleCreateFontOption"
                                                                    placeholder="选择或输入字体正式名称"
                                                                />
                                                                <div class="hint-text">
                                                                    提示：Windows 可在“设置 → 个性化 → 字体”里获取正式字体名称；移动端请在系统字体列表/中查正式名。
                                                                </div>
                                                        </n-form-item>
                        </div>

                        <div class="appearance-preview">
                            <n-text depth="3">预览：</n-text>
                            <div class="preview-text">春江花月夜 · The quick brown fox jumps over the lazy dog · 1234567890</div>
                        </div>
                    </n-form>
                </div>

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
                        <n-button text tag="a" href="https://openlm.ai/chatbot-arena/" target="_blank" rel="noopener noreferrer" type="primary" size="small">
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
                    <n-select 
                        v-model:value="newUsage.platformId" 
                        :options="platformOptions" 
                        @update:value="handleNewUsagePlatformChange"
                    />
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
import { ref, onMounted, computed, watch, nextTick, h } from 'vue';
import { NSpin, NSelect, NFormItem, NInput, NButton, NTag, NIcon, NModal, NCard, NForm, NTable, NSpace, NText, NColorPicker, useMessage, useDialog } from 'naive-ui';
import { Add, TrophyOutline } from '@vicons/ionicons5';
import { fetchWithAuth, fetchUserPlatformsAndModels, createUserUsageSlot, deleteUserUsageSlot, renameUserUsageSlot } from '../services/api';
import { useAiStore } from '../components/stores/aiStore';
import { useThemeStore } from '../components/stores/themeStore';

const message = useMessage();
const dialog = useDialog();
const aiStore = useAiStore();
const themeStore = useThemeStore();

const PLATFORM = {
    windows: 'windows',
    android: 'android',
    ios: 'ios',
    linux: 'linux',
};

const platformEmoji = (p) => {
    if (p === PLATFORM.windows) return '💻';
    if (p === PLATFORM.android) return '📱';
    if (p === PLATFORM.ios) return '🍎';
    if (p === PLATFORM.linux) return '🐧';
    return '';
};

const PlatformIcon = (p) => {
    const emoji = platformEmoji(p);
    if (!emoji) return null;
    return h('span', { class: 'platform-emoji', title: emoji }, emoji);
};

const makeFontOption = (label, value, platforms) => ({
    label,
    value,
    platforms,
});

// 简易设计：列出常见/主流系统自带字体 + 允许用户输入其它字体正式名称
const fontOptions = [
    makeFontOption('跟随主题（默认：微软雅黑等回退）', '', [PLATFORM.windows, PLATFORM.android, PLATFORM.ios, PLATFORM.linux]),

    // Windows 10+ 常见系统字体
    makeFontOption('Segoe UI', 'Segoe UI', [PLATFORM.windows]),
    makeFontOption('Segoe UI Emoji', 'Segoe UI Emoji', [PLATFORM.windows]),
    makeFontOption('Segoe UI Symbol', 'Segoe UI Symbol', [PLATFORM.windows]),
    makeFontOption('Microsoft YaHei / 微软雅黑', 'Microsoft YaHei', [PLATFORM.windows]),
    makeFontOption('Microsoft YaHei UI', 'Microsoft YaHei UI', [PLATFORM.windows]),
    makeFontOption('SimSun / 宋体', 'SimSun', [PLATFORM.windows]),
    makeFontOption('SimHei / 黑体', 'SimHei', [PLATFORM.windows]),
    makeFontOption('KaiTi / 楷体', 'KaiTi', [PLATFORM.windows]),
    makeFontOption('FangSong / 仿宋', 'FangSong', [PLATFORM.windows]),
    makeFontOption('Yu Gothic', 'Yu Gothic', [PLATFORM.windows]),
    makeFontOption('Arial', 'Arial', [PLATFORM.windows, PLATFORM.android, PLATFORM.ios]),
    makeFontOption('Times New Roman', 'Times New Roman', [PLATFORM.windows, PLATFORM.ios]),
    makeFontOption('Courier New', 'Courier New', [PLATFORM.windows, PLATFORM.ios]),
    makeFontOption('Consolas', 'Consolas', [PLATFORM.windows]),
    makeFontOption('Tahoma', 'Tahoma', [PLATFORM.windows]),
    makeFontOption('Verdana', 'Verdana', [PLATFORM.windows, PLATFORM.ios]),

    // Linux 桌面环境常见（多发行版默认/常见依赖包中自带）
    makeFontOption('DejaVu Sans', 'DejaVu Sans', [PLATFORM.linux]),
    makeFontOption('DejaVu Serif', 'DejaVu Serif', [PLATFORM.linux]),
    makeFontOption('DejaVu Sans Mono', 'DejaVu Sans Mono', [PLATFORM.linux]),
    makeFontOption('Liberation Sans', 'Liberation Sans', [PLATFORM.linux]),
    makeFontOption('Liberation Serif', 'Liberation Serif', [PLATFORM.linux]),
    makeFontOption('Liberation Mono', 'Liberation Mono', [PLATFORM.linux]),
    makeFontOption('Cantarell', 'Cantarell', [PLATFORM.linux]),
    makeFontOption('Ubuntu', 'Ubuntu', [PLATFORM.linux]),

    // Android 12+（AOSP/常见）
    makeFontOption('Roboto', 'Roboto', [PLATFORM.android]),
    makeFontOption('Roboto Condensed', 'Roboto Condensed', [PLATFORM.android]),
    makeFontOption('Noto Sans', 'Noto Sans', [PLATFORM.android, PLATFORM.linux]),
    makeFontOption('Noto Sans CJK SC', 'Noto Sans CJK SC', [PLATFORM.android]),
    makeFontOption('Noto Serif', 'Noto Serif', [PLATFORM.android]),

    // iOS 9+（常见系统字体）
    makeFontOption('PingFang SC / 苹方', 'PingFang SC', [PLATFORM.ios]),
    makeFontOption('Heiti SC / 黑体-简', 'Heiti SC', [PLATFORM.ios]),
    makeFontOption('Hiragino Sans GB', 'Hiragino Sans GB', [PLATFORM.ios]),
    makeFontOption('Helvetica Neue', 'Helvetica Neue', [PLATFORM.ios]),
    makeFontOption('Menlo', 'Menlo', [PLATFORM.ios]),
];

const themePrimaryColorDark = ref('');
const themePrimaryColorLight = ref('');
const fontFamily = ref('');

const syncAppearanceFromStore = async () => {
    fontFamily.value = themeStore.fontFamily || '';

    if (themeStore.primaryColorDark) themePrimaryColorDark.value = themeStore.primaryColorDark;
    if (themeStore.primaryColorLight) themePrimaryColorLight.value = themeStore.primaryColorLight;

    await nextTick();
    const current = getComputedStyle(document.documentElement).getPropertyValue('--spark-primary').trim();
    if (!themePrimaryColorDark.value) themePrimaryColorDark.value = current || '#7aa2f7';
    if (!themePrimaryColorLight.value) themePrimaryColorLight.value = '#6b9080';
};

watch(themePrimaryColorDark, (val) => {
    const v = (val || '').toString().trim();
    themeStore.setPrimaryColorDark(v);
});

watch(themePrimaryColorLight, (val) => {
    const v = (val || '').toString().trim();
    themeStore.setPrimaryColorLight(v);
});

watch(fontFamily, (val) => {
    themeStore.setFontFamily(val);
});

const loading = computed(() => aiStore.loading);
const usageSelections = computed(() => aiStore.usageSelections);
const platforms = computed(() => {
    // Build platforms list from allModels in store
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

const platformOptions = computed(() => aiStore.platformOptions);

function getModelsForPlatform(platformId) {
    return aiStore.getModelsForPlatform(platformId);
}

async function loadData(silent = false) {
    await aiStore.loadData(true, silent);
}

async function handlePlatformChange(usage, platformId) {
    usage.platform_id = platformId;
    const models = aiStore.getModelsForPlatform(platformId);
    
    if (models && models.length > 0) {
        usage.model_id = models[0].value;
        await saveSelection(usage);
    } else {
        usage.model_id = null;
    }
}

async function handleModelChange(usage, modelId) {
    usage.model_id = modelId;
    await saveSelection(usage);
}

async function saveSelection(usage) {
    try {
        await aiStore.updateSelection(usage.usage_key, usage.platform_id, usage.model_id);
        message.success(`已更新 ${usage.usage_label} 的模型设置`);
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
        await loadData(true);
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
        await loadData(true);
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
                await loadData(true);
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
        await loadData(true);
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
        await loadData(true);
    } catch (e) {
        message.error(e.message);
    } finally {
        addingUsage.value = false;
    }
}

function handleNewUsagePlatformChange(platformId) {
    newUsage.value.platformId = platformId;
    const models = getModelsForPlatform(platformId);
    if (models && models.length > 0) {
        newUsage.value.modelId = models[0].value;
    } else {
        newUsage.value.modelId = null;
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
        await loadData(true);
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
                await loadData(true);
            } catch (e) {
                message.error(e.message);
            }
        }
    });
}

onMounted(async () => {
    await syncAppearanceFromStore();
    await loadData();
});

watch(
    () => [themeStore.themeMode, themeStore.prefersDark, themeStore.primaryColorDark, themeStore.primaryColorLight, themeStore.fontFamily, themeStore.fontKey],
    () => {
        // 当主题明暗切换且没有自定义主色时，让颜色选择器跟随当前主色
        syncAppearanceFromStore();
    }
);

const handleCreateFontOption = (label) => {
    const v = (label || '').toString().trim();
    if (!v) return null;
    return makeFontOption(v, v, []);
};

const renderFontOptionLabel = (option) => {
    const platforms = Array.isArray(option?.platforms) ? option.platforms : [];
    return h('div', { class: 'font-option' }, [
        h('span', { class: 'font-option-name' }, option.label),
        h('span', { class: 'font-option-platforms' }, platforms.map(p => PlatformIcon(p)).filter(Boolean)),
    ]);
};
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

.appearance-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}

.appearance-font {
    grid-column: 1 / -1;
}

.hint-text {
    margin-top: 6px;
    font-size: 12px;
    color: var(--spark-text-muted);
}

.font-option {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    width: 100%;
}

.font-option-name {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.font-option-platforms {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: color-mix(in srgb, var(--spark-text-muted), var(--spark-primary) 18%);
}

.platform-emoji {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 1px solid color-mix(in srgb, var(--spark-border), transparent 10%);
    background: color-mix(in srgb, var(--spark-panel-bg), transparent 18%);
    font-size: 13px;
    line-height: 1;
}

@media (max-width: 1100px) {
    .appearance-grid {
        grid-template-columns: 1fr;
    }
}

.appearance-preview {
    margin-top: 8px;
}

.preview-text {
    margin-top: 8px;
    padding: 10px 12px;
    border-radius: var(--spark-radius-sm);
    border: 1px solid var(--spark-border);
    background: var(--spark-bg);
    color: var(--spark-text);
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
