<template>
    <div class="settings-section notice-board system-notice-board" :class="{ collapsed: isCollapsed }">
        <div class="notice-header">
            <div class="header-left" @click="toggleCollapse">
                <h3>{{ t('components.systemNoticeBoard.title') }}</h3>
            </div>
            <div class="header-right">
                <n-space :size="4">
                    <n-button
                        v-if="isAdmin && !isCollapsed && viewMode === 'latest' && latestNotice?.id"
                        size="tiny"
                        secondary
                        type="primary"
                        @click="enterEditMode(latestNotice)"
                        style="font-size: var(--spark-fs-2xs); padding: 0 6px; height: 20px;"
                    >
                        {{ t('components.systemNoticeBoard.edit') }}
                    </n-button>
                    <n-button v-if="isAdmin && !isCollapsed" size="tiny" secondary type="success" @click="showAddModal = true" style="font-size: var(--spark-fs-2xs); padding: 0 6px; height: 20px;">
                        {{ t('components.systemNoticeBoard.add') }}
                    </n-button>
                    <n-button v-if="!isCollapsed" size="tiny" quaternary @click="toggleViewMode" style="font-size: var(--spark-fs-2xs); padding: 0 6px; height: 20px;">
                        {{ viewMode === 'latest' ? t('components.systemNoticeBoard.history') : t('components.systemNoticeBoard.latest') }}
                    </n-button>
                </n-space>
                <i class="ri-arrow-down-s-line collapse-icon" :class="{ rotated: isCollapsed }" @click="toggleCollapse"></i>
            </div>
        </div>
        
        <div class="notice-content-wrapper" v-show="!isCollapsed">
            <div v-if="isEditing" class="notice-editor">
                <div class="editor-toolbar">
                    <n-button size="tiny" quaternary @click="insertBold">{{ t('components.systemNoticeBoard.toolbar.bold') }}</n-button>
                    <n-button size="tiny" quaternary @click="insertItalic">{{ t('components.systemNoticeBoard.toolbar.italic') }}</n-button>
                    <n-button size="tiny" quaternary @click="insertHeading">{{ t('components.systemNoticeBoard.toolbar.heading') }}</n-button>
                    <n-button size="tiny" quaternary @click="insertList">{{ t('components.systemNoticeBoard.toolbar.list') }}</n-button>
                    <n-button size="tiny" quaternary @click="insertQuote">{{ t('components.systemNoticeBoard.toolbar.quote') }}</n-button>
                    <n-button size="tiny" quaternary @click="insertCode">{{ t('components.systemNoticeBoard.toolbar.code') }}</n-button>
                    <n-button size="tiny" quaternary @click="insertLink">{{ t('components.systemNoticeBoard.toolbar.link') }}</n-button>
                    <n-button size="tiny" quaternary @click="insertHr">{{ t('components.systemNoticeBoard.toolbar.separator') }}</n-button>
                </div>
                <n-form :model="editForm" class="editor-form">
                    <n-form-item :label="t('components.systemNoticeBoard.form.title')">
                        <n-input v-model:value="editForm.title" :placeholder="t('components.systemNoticeBoard.form.titlePlaceholder')" />
                    </n-form-item>
                    <n-form-item :label="t('components.systemNoticeBoard.form.content')">
                        <n-input
                            ref="contentInputRef"
                            v-model:value="editForm.content"
                            type="textarea"
                            :autosize="{ minRows: 8, maxRows: 18 }"
                            :placeholder="t('components.systemNoticeBoard.form.contentPlaceholder')"
                        />
                    </n-form-item>
                </n-form>
                <div class="editor-actions">
                    <n-button size="small" @click="cancelEdit">{{ t('views.common.cancel') }}</n-button>
                    <n-button size="small" type="primary" @click="submitNotice">{{ t('components.systemNoticeBoard.savePublish') }}</n-button>
                </div>
                <div class="editor-preview">
                    <div class="preview-title">{{ t('components.systemNoticeBoard.preview') }}</div>
                    <MarkdownRenderer :content="editForm.content" />
                </div>
            </div>

            <!-- 最新公告视图 -->
            <div v-if="viewMode === 'latest'" class="latest-view" :class="{ 'editing': isEditing }">
                <div v-if="latestNotice" class="notice-item-full">
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
                <n-text v-else depth="3">{{ t('components.systemNoticeBoard.emptyLatest') }}</n-text>
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
                                            {{ t('components.systemNoticeBoard.confirmDelete') }}
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
                    <n-empty v-else :description="t('components.systemNoticeBoard.emptyHistory')" size="small" />
                </n-scrollbar>
            </div>
        </div>

        <!-- 使用同一个 modal 处理新增 -->
        <n-modal
            v-model:show="showAddModal"
            preset="dialog"
            :title="t('components.systemNoticeBoard.newNotice')"
            :positive-text="t('components.systemNoticeBoard.publish')"
            :negative-text="t('views.common.cancel')"
            @positive-click="submitNewNotice"
        >
            <n-form :model="newForm" style="margin-top: 12px">
                <n-form-item :label="t('components.systemNoticeBoard.form.title')">
                    <n-input v-model:value="newForm.title" :placeholder="t('components.systemNoticeBoard.form.titlePlaceholder')" />
                </n-form-item>
                <n-form-item :label="t('components.systemNoticeBoard.form.content')">
                    <n-input
                        v-model:value="newForm.content"
                        type="textarea"
                        :autosize="{ minRows: 5, maxRows: 15 }"
                        :placeholder="t('components.systemNoticeBoard.form.contentPlaceholder')"
                    />
                </n-form-item>
            </n-form>
        </n-modal>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, nextTick } from 'vue';
import { NSkeleton, NText, NButton, NButtonGroup, NSpace, NScrollbar, NEllipsis, NEmpty, NModal, NForm, NFormItem, NInput, NPopconfirm, useMessage } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import MarkdownRenderer from '../share/MarkdownRenderer.vue';
import { fetchWithAuth, getUserInfo } from '../../services/api';
import { getNoticeHistory, createSystemNotice, updateSystemNotice, deleteSystemNotice } from '../../services/adminService';

type NoticeViewMode = 'latest' | 'history';

type NoticeItem = {
    id: string;
    title: string;
    content: string;
    timestamp: string;
};

type LegacyNoticeItem = Partial<NoticeItem> & {
    notice_id?: string;
};

type NoticeApiResponse = {
    success?: boolean;
    notice?: LegacyNoticeItem | null;
    message?: string;
    detail?: unknown;
};

type SelectionReplaceResult = {
    text: string;
    newStart: number;
    newEnd: number;
};

type SelectionReplacer = (selected: string, start: number, end: number) => SelectionReplaceResult;

type TextareaHost = {
    $el?: {
        querySelector: (selector: string) => HTMLTextAreaElement | null;
    };
};

const message = useMessage();
const { t, locale } = useI18n();

const latestNotice = ref<NoticeItem | null>(null);
const history = ref<NoticeItem[]>([]);
const loading = ref(false);
const isCollapsed = ref(false);
const isAdmin = ref(false);
const viewMode = ref<NoticeViewMode>('latest');

const isEditing = ref(false);
const editForm = reactive({ id: '', title: '', content: '' });
const contentInputRef = ref<TextareaHost | null>(null);

const showAddModal = ref(false);
const newForm = reactive({ title: '', content: '' });

const toggleCollapse = () => {
    isCollapsed.value = !isCollapsed.value;
};

const toggleViewMode = () => {
    viewMode.value = viewMode.value === 'latest' ? 'history' : 'latest';
    if (viewMode.value === 'history') loadHistory();
};

function resolveApiError(data: NoticeApiResponse | null | undefined, fallback: string): string {
    const detail = data?.detail;
    const detailMessage = typeof detail === 'object' && detail !== null
        ? (detail as { message?: string }).message
        : undefined;

    return (
        (typeof data?.message === 'string' ? data.message : undefined)
        || detailMessage
        || (typeof detail === 'string' ? detail : undefined)
        || fallback
    );
}

function normalizeNoticeItem(item: LegacyNoticeItem | null | undefined): NoticeItem | null {
    if (!item) return null;
    const id = (item.id || item.notice_id || '').toString().trim();
    const title = (item.title || '').toString();
    const content = (item.content || '').toString();
    const timestamp = (item.timestamp || '').toString();
    if (!id || !title) return null;
    return { id, title, content, timestamp };
}

const loadLatest = async () => {
    loading.value = true;
    try {
        const res = await fetchWithAuth('/api/system/notice');
        const data = await res.json() as NoticeApiResponse;
        if (!res.ok || data.success === false) {
            throw new Error(resolveApiError(data, t('components.systemNoticeBoard.loadLatestFailed')));
        }

        latestNotice.value = normalizeNoticeItem(data.notice);
    } catch (e: unknown) {
        latestNotice.value = null;
        const errorMessage = e instanceof Error ? e.message : String(e || t('views.common.unknownError'));
        message.error(`${t('components.systemNoticeBoard.loadLatestFailed')}: ${errorMessage}`);
    } finally {
        loading.value = false;
    }
};

const loadHistory = async () => {
    try {
        const data = await getNoticeHistory() as NoticeItem[];
        history.value = data || [];
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || t('views.common.unknownError'));
        message.error(`${t('components.systemNoticeBoard.loadHistoryFailed')}: ${errorMessage}`);
    }
};

const enterEditMode = (item: NoticeItem | null) => {
    if (!item?.id) return;
    isEditing.value = true;
    editForm.id = item.id;
    editForm.title = item.title;
    editForm.content = item.content;
    viewMode.value = 'latest';
    isCollapsed.value = false;
};

const cancelEdit = () => {
    isEditing.value = false;
    editForm.id = '';
    editForm.title = '';
    editForm.content = '';
};

const submitNotice = async () => {
    if (!editForm.id) {
        message.warning(t('components.systemNoticeBoard.errors.selectNoticeFirst'));
        return;
    }
    if (!editForm.title.trim() || !editForm.content.trim()) {
        message.warning(t('components.systemNoticeBoard.errors.titleAndContentRequired'));
        return;
    }

    try {
        await updateSystemNotice(editForm.id, editForm.title, editForm.content);
        message.success(t('components.systemNoticeBoard.noticeUpdated'));
        isEditing.value = false;
        await loadLatest();
        await loadHistory();
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || t('views.common.unknownError'));
        message.error(`${t('components.systemNoticeBoard.updateFailed')}: ${errorMessage}`);
    }
};

function getTextareaEl(): HTMLTextAreaElement | null {
    const host = contentInputRef.value;
    if (!host?.$el) return null;
    return host.$el.querySelector('textarea');
}

function replaceSelection(replacer: SelectionReplacer) {
    const textarea = getTextareaEl();
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = editForm.content.slice(start, end);
    const { text, newStart, newEnd } = replacer(selected, start, end);
    editForm.content = text;
    nextTick(() => {
        textarea.focus();
        textarea.setSelectionRange(newStart, newEnd);
    });
}

function insertWrap(prefix: string, suffix: string, placeholder = '') {
    replaceSelection((selected, start, end) => {
        const content = selected || placeholder;
        const before = editForm.content.slice(0, start);
        const after = editForm.content.slice(end);
        const text = before + prefix + content + suffix + after;
        const cursorStart = start + prefix.length;
        const cursorEnd = cursorStart + content.length;
        return { text, newStart: cursorStart, newEnd: cursorEnd };
    });
}

function insertLinePrefix(prefix: string) {
    replaceSelection((selected, start, end) => {
        const content = selected || '';
        const lines = content ? content.split('\n') : [''];
        const newContent = lines.map(line => prefix + line).join('\n');
        const before = editForm.content.slice(0, start);
        const after = editForm.content.slice(end);
        const text = before + newContent + after;
        const cursorStart = start + prefix.length;
        const cursorEnd = start + newContent.length;
        return { text, newStart: cursorStart, newEnd: cursorEnd };
    });
}

const insertBold = () => insertWrap('**', '**', t('components.systemNoticeBoard.toolbar.placeholderBold'));
const insertItalic = () => insertWrap('*', '*', t('components.systemNoticeBoard.toolbar.placeholderItalic'));
const insertCode = () => insertWrap('`', '`', 'code');
const insertLink = () => insertWrap('[', '](url)', t('components.systemNoticeBoard.toolbar.placeholderLink'));
const insertHeading = () => insertLinePrefix('# ');
const insertList = () => insertLinePrefix('- ');
const insertQuote = () => insertLinePrefix('> ');
const insertHr = () => insertWrap('\n---\n', '', '');

const submitNewNotice = async () => {
    if (!newForm.title.trim() || !newForm.content.trim()) {
        message.warning(t('components.systemNoticeBoard.errors.titleAndContentRequired'));
        return;
    }

    try {
        await createSystemNotice(newForm.title, newForm.content);
        message.success(t('components.systemNoticeBoard.noticePublished'));
        newForm.title = '';
        newForm.content = '';
        await loadLatest();
        await loadHistory();
        showAddModal.value = false;
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || t('views.common.unknownError'));
        message.error(`${t('components.systemNoticeBoard.publishFailed')}: ${errorMessage}`);
    }
};

const handleDelete = async (id: string) => {
    try {
        await deleteSystemNotice(id);
        message.success(t('components.systemNoticeBoard.noticeDeleted'));
        await loadLatest();
        await loadHistory();
    } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : String(e || t('views.common.unknownError'));
        message.error(`${t('views.common.deleteFailed')}: ${errorMessage}`);
    }
};

function formatTime(isoString: string): string {
    if (!isoString) return '';
    try {
        const date = new Date(isoString);
        const localeCode = ['zh-CN', 'en-US', 'ja-JP', 'ko-KR'].includes(locale.value) ? locale.value : 'zh-CN';
        return date.toLocaleString(localeCode, {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch {
        return isoString;
    }
}

onMounted(async () => {
    await loadLatest();
    try {
        const user = await getUserInfo();
        isAdmin.value = user?.is_admin || false;
    } catch {
        isAdmin.value = false;
    }
});
</script>

<style scoped>
.settings-section {
    background: var(--spark-panel-bg);
    border: 1px solid var(--spark-border);
    border-radius: var(--spark-radius);
    margin-bottom: 20px;
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
    padding: var(--spark-panel-padding);
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
    font-size: var(--spark-fs-lg);
    color: var(--spark-primary);
}

.collapse-icon {
    font-size: var(--spark-fs-h2);
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
    padding: 0 var(--spark-panel-padding) var(--spark-panel-padding);
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    margin-top: 4px;
    padding-top: 12px;
}

.notice-editor {
    background: var(--spark-bg-layer1);
    border: 1px solid var(--spark-border);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 12px;
}

.editor-toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 10px;
}

.editor-form :deep(.n-form-item) {
    margin-bottom: 8px;
}

.editor-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 8px;
}

.editor-preview {
    margin-top: 12px;
    padding: 10px 12px;
    border: 1px dashed var(--spark-border);
    border-radius: 6px;
    background: var(--spark-bg);
}

.preview-title {
    font-size: var(--spark-fs-xs);
    color: var(--spark-text-muted);
    margin-bottom: 6px;
}

.latest-view.editing {
    opacity: 0.5;
    pointer-events: none;
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
    font-size: var(--spark-fs-xs);
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
    font-size: var(--spark-fs-2xs);
}

.history-item-preview {
    font-size: var(--spark-fs-sm);
    color: var(--spark-text-muted);
    opacity: 0.8;
}

:deep(.n-form-item-blank) {
    display: block;
}

:global(html.viewport-mobile .system-notice-board.settings-section) {
    margin-bottom: 8px;
    border: none;
    border-radius: var(--spark-radius);
    background: transparent;
}

:global(html.viewport-mobile .system-notice-board.notice-board) {
    border-left: none;
    border-top: 2px solid var(--spark-primary);
}

:global(html.viewport-mobile .system-notice-board .notice-header) {
    padding: 8px 6px;
}

:global(html.viewport-mobile .system-notice-board .notice-content-wrapper) {
    padding: 0 6px 12px;
}

@media (max-width: 480px) {
    .notice-header {
        padding: 8px 4px;
    }
    .notice-content-wrapper {
        padding: 0 4px 10px;
    }
}
</style>
