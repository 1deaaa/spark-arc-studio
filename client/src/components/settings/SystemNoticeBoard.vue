
<template>
    <div class="settings-section notice-board" :class="{ collapsed: isCollapsed }">
        <div class="notice-header">
            <div class="header-left" @click="toggleCollapse" style="cursor: pointer; flex: 1;">
                <h3>公告板 / Notice Board</h3>
                <n-tag type="info" size="small" round v-if="!isCollapsed">NEW</n-tag>
            </div>
            <div class="header-right">
                <n-space v-if="isAdmin && !isCollapsed">
                    <n-button v-if="!isEditMode" size="tiny" secondary type="primary" @click.stop="enterEditMode">
                        <template #icon><i class="ri-edit-line"></i></template>
                        编辑
                    </n-button>
                </n-space>
                <i class="ri-arrow-down-s-line collapse-icon" :class="{ rotated: isCollapsed }" @click="toggleCollapse" style="cursor: pointer; margin-left: 8px;"></i>
            </div>
        </div>
        
        <div class="notice-content-wrapper" v-show="!isCollapsed">
            <template v-if="isEditMode">
                <n-input
                    v-model:value="editingContent"
                    type="textarea"
                    placeholder="请输入公告内容 (支持 Markdown)"
                    :autosize="{ minRows: 5, maxRows: 20 }"
                    style="margin-bottom: 12px;"
                />
                <n-space justify="end">
                    <n-button size="small" @click="cancelEdit">取消</n-button>
                    <n-button size="small" type="primary" :loading="saving" @click="saveNotice">保存公告</n-button>
                </n-space>
            </template>
            <template v-else>
                <MarkdownRenderer v-if="noticeContent" :content="noticeContent" />
                <n-skeleton v-else-if="loadingNotice" :repeat="3" text />
                <n-text v-else depth="3">暂无最新公告</n-text>
            </template>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { NTag, NSkeleton, NText, NButton, NInput, NSpace, useMessage } from 'naive-ui';
import MarkdownRenderer from '../share/MarkdownRenderer.vue';
import { fetchWithAuth, getUserInfo } from '../../services/api';
import { updateSystemNotice } from '../../services/adminService';

const message = useMessage();
const noticeContent = ref('');
const editingContent = ref('');
const loadingNotice = ref(false);
const isCollapsed = ref(false); // Default to expanded now
const isAdmin = ref(false);
const isEditMode = ref(false);
const saving = ref(false);

const toggleCollapse = () => {
    if (isEditMode.value) return; // 编辑模式下不允许折叠，或者先退出编辑
    isCollapsed.value = !isCollapsed.value;
};

const enterEditMode = () => {
    editingContent.value = noticeContent.value;
    isEditMode.value = true;
};

const cancelEdit = () => {
    isEditMode.value = false;
};

const saveNotice = async () => {
    if (!editingContent.value.trim()) {
        message.warning('请输入公告内容');
        return;
    }
    saving.value = true;
    try {
        await updateSystemNotice(editingContent.value);
        noticeContent.value = editingContent.value;
        isEditMode.value = false;
        message.success('公告已更新');
    } catch (e) {
        message.error('保存失败: ' + e.message);
    } finally {
        saving.value = false;
    }
};

const fetchNotice = async () => {
    loadingNotice.value = true;
    try {
        const res = await fetchWithAuth('/api/system/notice');
        if (res.ok) {
            const data = await res.json();
            noticeContent.value = data.content;
        }
    } catch (e) {
        console.error('Failed to fetch notice:', e);
    } finally {
        loadingNotice.value = false;
    }
};

onMounted(async () => {
    fetchNotice();
    // 检查权限
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

.settings-section.collapsed {
    height: auto;
}

.settings-section:not(.collapsed) {
    height: 100%;
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
    cursor: pointer;
    user-select: none;
    flex-shrink: 0;
}

.notice-header:hover {
    background: rgba(255, 255, 255, 0.02);
}

.header-left {
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
}

.collapse-icon.rotated {
    transform: rotate(-90deg);
}

.notice-content-wrapper {
    flex: 1;
    overflow-y: auto;
    font-size: 14px;
    line-height: 1.4;
    color: var(--spark-text);
    padding: 0 24px 16px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    margin-top: 4px;
    padding-top: 12px;
}

/* Markdown Styles */
.notice-content-wrapper :deep(h1),
.notice-content-wrapper :deep(h2),
.notice-content-wrapper :deep(h3) {
    color: var(--spark-primary);
    margin-top: 12px;
    margin-bottom: 6px;
}

.notice-content-wrapper :deep(ul),
.notice-content-wrapper :deep(ol) {
    padding-left: 20px;
}

.notice-content-wrapper :deep(li) {
    margin-bottom: 4px;
}

.notice-content-wrapper :deep(p) {
    margin-bottom: 12px;
}
</style>
