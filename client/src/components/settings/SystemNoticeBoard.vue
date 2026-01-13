<template>
    <div class="settings-section notice-board" :class="{ collapsed: isCollapsed }">
        <div class="notice-header">
            <div class="header-left" @click="toggleCollapse">
                <h3>公告板 / Notice Board</h3>
                <n-tag type="info" size="small" round v-if="!isCollapsed && showNewTag">NEW</n-tag>
            </div>
            <div class="header-right">
                <n-space size="small">
                    <n-button v-if="isAdmin && !isCollapsed && viewMode === 'latest'" size="tiny" secondary type="primary" @click="enterEditMode(latestNotice)">
                        编辑
                    </n-button>
                    <n-button v-if="isAdmin && !isCollapsed" size="tiny" secondary type="success" @click="showAddModal = true">
                        新增
                    </n-button>
                    <n-button v-if="!isCollapsed" size="tiny" quaternary @click="toggleViewMode">
                        {{ viewMode === 'latest' ? '历史公告' : '返回最新' }}
                    </n-button>
                </n-space>
                <i class="ri-arrow-down-s-line collapse-icon" :class="{ rotated: isCollapsed }" @click="toggleCollapse"></i>
            </div>
        </div>
        
        <div class="notice-content-wrapper" v-show="!isCollapsed">
            <!-- 最新公告视图 -->
            <div v-if="viewMode === 'latest'" class="latest-view">
                <div v-if="latestNotice && latestNotice.timestamp" class="notice-item-full">
                    <div class="notice-meta">
                        <span class="notice-title">{{ latestNotice.title }}</span>
                        <span class="notice-time">{{ formatTime(latestNotice.timestamp) }}</span>
                    </div>
                    <div class="notice-body">
                        <MarkdownRenderer :content="latestNotice.content" />
                    </div>
                </div>
                <div v-else-if="loading" class="loading-box" style="padding: 10px 0;">
                    <n-skeleton :repeat="3" text />
                </div>
                <n-text v-else depth="3">暂无最新公告</n-text>
            </div>

            <!-- 公告历史视图 -->
            <div v-else class="history-view">
                <n-scrollbar style="max-height: 400px">
                    <div v-if="history.length > 0" class="history-list">
                        <div v-for="item in history" :key="item.id" class="history-item">
                            <div class="history-item-header">
                                <span class="history-item-title">{{ item.title }}</span>
                                <div class="history-item-actions">
                                    <n-text depth="3" class="history-item-time">{{ formatTime(item.timestamp) }}</n-text>
                                    <n-button-group v-if="isAdmin" size="tiny">
                                        <n-button quaternary circle type="primary" @click="enterEditMode(item)">
                                            <template #icon><i class="ri-edit-line"></i></template>
                                        </n-button>
                                        <n-popconfirm @positive-click="handleDelete(item.id)">
                                            <template #trigger>
                                                <n-button quaternary circle type="error">
                                                    <template #icon><i class="ri-delete-bin-line"></i></template>
                                                </n-button>
                                            </template>
                                            确定删除这条公告吗？
                                        </n-popconfirm>
                                    </n-button-group>
                                </div>
                            </div>
                            <div class="history-item-preview">
                                <n-ellipsis :line-clamp="2" expand-triggered>
                                    {{ item.content }}
                                </n-ellipsis>
                            </div>
                        </div>
                    </div>
                    <n-empty v-else description="暂无历史公告" size="small" />
                </n-scrollbar>
            </div>
        </div>

        <!-- 编辑/新增弹窗 -->
        <n-modal v-model:show="showEditModal" preset="dialog" :title="isEditing ? '编辑公告' : '发布新公告'" 
            positive-text="保存发布" negative-text="取消" @positive-click="submitNotice">
            <n-form :model="editForm" style="margin-top: 12px">
                <n-form-item label="标题">
                    <n-input v-model:value="editForm.title" placeholder="公告标题" />
                </n-form-item>
                <n-form-item label="内容">
                    <n-input v-model:value="editForm.content" type="textarea" :autosize="{ minRows: 5, maxRows: 15 }" placeholder="系统公告内容 (支持 Markdown)" />
                </n-form-item>
            </n-form>
        </n-modal>
        
        <!-- 使用同一个 modal 处理新增 -->
        <n-modal v-model:show="showAddModal" preset="dialog" title="发布新公告" 
            positive-text="发布" negative-text="取消" @positive-click="submitNewNotice">
            <n-form :model="newForm" style="margin-top: 12px">
                <n-form-item label="标题">
                    <n-input v-model:value="newForm.title" placeholder="公告标题" />
                </n-form-item>
                <n-form-item label="内容">
                    <n-input v-model:value="newForm.content" type="textarea" :autosize="{ minRows: 5, maxRows: 15 }" placeholder="系统公告内容 (支持 Markdown)" />
                </n-form-item>
            </n-form>
        </n-modal>
    </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue';
import { NTag, NSkeleton, NText, NButton, NButtonGroup, NSpace, NScrollbar, NEllipsis, NEmpty, NModal, NForm, NFormItem, NInput, NPopconfirm, useMessage } from 'naive-ui';
import MarkdownRenderer from '../share/MarkdownRenderer.vue';
import { fetchWithAuth, getUserInfo } from '../../services/api';
import { getNoticeHistory, createSystemNotice, updateSystemNotice, deleteSystemNotice } from '../../services/adminService';

const message = useMessage();
const latestNotice = ref(null);
const history = ref([]);
const loading = ref(false);
const isCollapsed = ref(false);
const isAdmin = ref(false);
const viewMode = ref('latest'); // latest | history
const showNewTag = ref(true);

const showEditModal = ref(false);
const isEditing = ref(false);
const editForm = reactive({ id: '', title: '', content: '' });

const showAddModal = ref(false);
const newForm = reactive({ title: '', content: '' });

const toggleCollapse = () => {
    isCollapsed.value = !isCollapsed.value;
    if (!isCollapsed.value) showNewTag.value = false;
};

const toggleViewMode = () => {
    viewMode.value = viewMode.value === 'latest' ? 'history' : 'latest';
    if (viewMode.value === 'history') loadHistory();
};

const loadLatest = async () => {
    loading.value = true;
    try {
        const res = await fetchWithAuth('/api/system/notice');
        const data = await res.json();
        if (data.success && data.notice) {
            latestNotice.value = data.notice;
        }
    } catch (e) {
        console.error('Fetch notice failed:', e);
    } finally {
        loading.value = false;
    }
};

const loadHistory = async () => {
    try {
        const data = await getNoticeHistory();
        history.value = data || [];
    } catch (e) {
        message.error('加载历史记录失败');
    }
};

const enterEditMode = (item) => {
    if (!item) return;
    isEditing.value = true;
    editForm.id = item.id;
    editForm.title = item.title;
    editForm.content = item.content;
    showEditModal.value = true;
};

const submitNotice = async () => {
    try {
        await updateSystemNotice(editForm.id, editForm.title, editForm.content);
        message.success('公告已更新');
        loadLatest();
        if (viewMode.value === 'history') loadHistory();
    } catch (e) {
        message.error('更新失败: ' + e.message);
    }
};

const submitNewNotice = async () => {
    try {
        await createSystemNotice(newForm.title, newForm.content);
        message.success('公告已发布');
        newForm.title = '';
        newForm.content = '';
        loadLatest();
        if (viewMode.value === 'history') loadHistory();
    } catch (e) {
        message.error('发布失败: ' + e.message);
    }
};

const handleDelete = async (id) => {
    try {
        await deleteSystemNotice(id);
        message.success('公告已删除');
        loadLatest();
        if (viewMode.value === 'history') loadHistory();
    } catch (e) {
        message.error('删除失败');
    }
};

function formatTime(isoString) {
    if (!isoString) return '';
    try {
        const date = new Date(isoString);
        return date.toLocaleString('zh-CN', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (e) { return isoString; }
}

onMounted(async () => {
    loadLatest();
    try {
        const user = await getUserInfo();
        isAdmin.value = user?.is_admin || false;
    } catch (e) {}
});
</script>

<style scoped>
.settings-section {
    background: var(--spark-panel-bg);
    border: 1px solid var(--spark-border);
    border-radius: var(--spark-radius);
    margin-bottom: 24px;
    display: flex;
    flex-direction: column;
    transition: all 0.3s ease;
    overflow: hidden;
}

.notice-board {
    background: linear-gradient(to bottom right, var(--spark-panel-bg), color-mix(in srgb, var(--spark-panel-bg), var(--spark-primary) 5%));
    border-left: 4px solid var(--spark-primary);
}

.notice-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    user-select: none;
    flex-shrink: 0;
}

.header-left {
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
}

.header-right {
    display: flex;
    align-items: center;
    gap: 12px;
}

.settings-section h3 {
    margin: 0;
    font-size: 16px;
    color: var(--spark-primary);
}

.collapse-icon {
    font-size: 20px;
    color: var(--spark-text-muted);
    transition: transform 0.3s;
    cursor: pointer;
}

.collapse-icon.rotated {
    transform: rotate(-90deg);
}

.notice-content-wrapper {
    flex: 1;
    overflow-y: hidden;
    color: var(--spark-text);
    padding: 0 24px 16px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    margin-top: 4px;
    padding-top: 12px;
}

.notice-meta {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px dashed var(--spark-border);
}

.notice-title {
    font-weight: 600;
    color: var(--spark-primary);
}

.notice-time {
    font-size: 12px;
    color: var(--spark-text-muted);
}

.history-item {
    padding: 12px;
    border-bottom: 1px solid var(--spark-border);
    transition: background 0.2s;
}

.history-item:hover {
    background: rgba(255, 255, 255, 0.02);
}

.history-item-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
}

.history-item-title {
    font-weight: 500;
    color: var(--spark-text);
}

.history-item-actions {
    display: flex;
    align-items: center;
    gap: 8px;
}

.history-item-time {
    font-size: 11px;
}

.history-item-preview {
    font-size: 13px;
    color: var(--spark-text-muted);
    opacity: 0.8;
}

:deep(.n-form-item-blank) {
    display: block;
}
</style>
