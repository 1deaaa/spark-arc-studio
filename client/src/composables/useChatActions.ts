/**
 * 聊天交互 Composable（通用版）
 * 支持主窗口和额外窗口，均通过统一的 chatStore 管理。
 * 
 * @param {Object} adapter - 适配器对象，定义 store 操作抽象
 * @param {Function} adapter.getSending - 返回当前 sending 状态
 * @param {Function} adapter.getHistory - 返回当前 history 数组
 * @param {Function} adapter.send - 发送消息 (text) => Promise
 * @param {Function} adapter.clear - 清空历史 () => Promise
 * @param {Function} adapter.editMessage - 编辑消息 (id, content) => Promise
 * @param {Function} adapter.deleteMessage - 删除消息 (id) => Promise
 * @param {Object} options - 可选配置
 * @param {Ref} options.listRef - 桌面端消息列表 ref（ChatMessageList 组件 ref）
 * @param {Ref} options.mobileListRef - 移动端消息列表 ref
 */
import { ref, computed, watch, nextTick, onUnmounted, onMounted } from 'vue';
import bus from '@/eventBus';

type MessageId = string | number;

interface ChatLikeMessage {
    id?: MessageId | null;
    clientId?: MessageId | null;
    content?: string;
    role?: string;
}

interface ChatActionsAdapter {
    getSending: () => boolean;
    getHistory?: () => ChatLikeMessage[] | null | undefined;
    send: (text: string) => Promise<unknown>;
    stop?: () => Promise<unknown>;
    clear: () => Promise<unknown>;
    editMessage: (id: MessageId, content: string) => Promise<unknown>;
    deleteMessage: (id: MessageId) => Promise<unknown>;
}

interface RefLike<T> {
    value: T;
}

interface UseChatActionsOptions {
    listRef?: RefLike<unknown>;
    mobileListRef?: RefLike<unknown>;
    getEditScopeKey?: (() => string) | null;
}

function hasPersistedMessageId(messageId: unknown): messageId is MessageId {
    return messageId !== null && messageId !== undefined && String(messageId).trim() !== '';
}

function getMutableMessageId(message: ChatLikeMessage | null | undefined): MessageId | null {
    if (!message || typeof message !== 'object') return null;
    if (hasPersistedMessageId(message.id)) return message.id;
    if (hasPersistedMessageId(message.clientId)) return message.clientId;
    return null;
}

export function useChatActions(adapter: ChatActionsAdapter, options: UseChatActionsOptions = {}) {
    const {
        listRef = ref(null),
        mobileListRef = ref(null),
        getEditScopeKey = null,
    } = options;

    const draft = ref('');
    const editingMessageId = ref<MessageId | null>(null);
    const editingContent = ref('');

    const thinkingSeconds = ref(0);
    let thinkingTimer: ReturnType<typeof setInterval> | null = null;

    // 智能自动下滑：用户上滚可打断，AI 新回复时恢复
    const autoScrollEnabled = ref(true);
    const SCROLL_BOTTOM_THRESHOLD = 60; // 距底部多少像素内视为"在底部"
    let scrollListeners: Array<{ el: HTMLElement; handler: () => void }> = [];

    /** 判断元素是否滚动到接近底部 */
    function isNearBottom(el: { scrollTop?: number; scrollHeight?: number; clientHeight?: number }) {
        if (el.scrollTop == null || el.scrollHeight == null || el.clientHeight == null) return true;
        return el.scrollTop + el.clientHeight >= el.scrollHeight - SCROLL_BOTTOM_THRESHOLD;
    }

    /** 为滚动容器绑定 scroll 事件，检测用户上滚 */
    function bindScrollListeners() {
        // 先清理旧监听
        removeScrollListeners();
        const refs = [listRef, mobileListRef];
        for (const sourceRef of refs) {
            const el = resolveEl(sourceRef) as HTMLElement | undefined;
            if (!el) continue;
            const handler = () => {
                if (!autoScrollEnabled.value) return;
                if (!isNearBottom(el)) {
                    autoScrollEnabled.value = false;
                }
            };
            el.addEventListener('scroll', handler, { passive: true });
            scrollListeners.push({ el, handler });
        }
    }

    /** 移除所有 scroll 事件监听 */
    function removeScrollListeners() {
        for (const { el, handler } of scrollListeners) {
            el.removeEventListener('scroll', handler);
        }
        scrollListeners = [];
    }

    // 延迟绑定：等 listRef 对应的 DOM 挂载后再绑定
    onMounted(() => {
        nextTick(() => bindScrollListeners());
    });

    const lastMessageIsAssistant = computed(() => {
        const history = adapter.getHistory?.() || [];
        if (!history.length) return false;
        return history[history.length - 1]?.role === 'assistant';
    });

    function resolveEl(sourceRef: RefLike<unknown>) {
        let el = (sourceRef as { value?: unknown })?.value as { listRef?: unknown; scrollHeight?: number; scrollTop?: number } | undefined;
        if (el && el.listRef) el = el.listRef as typeof el;
        if (el && el.listRef) el = el.listRef as typeof el;
        return el;
    }

    function scrollToBottom(force = false) {
        nextTick(() => {
            if (!force && !autoScrollEnabled.value) return;
            const desktopEl = resolveEl(listRef);
            if (desktopEl && desktopEl.scrollHeight !== undefined && desktopEl.scrollTop !== undefined) {
                desktopEl.scrollTop = desktopEl.scrollHeight;
            }
            const mobileEl = resolveEl(mobileListRef);
            if (mobileEl && mobileEl.scrollHeight !== undefined && mobileEl.scrollTop !== undefined) {
                mobileEl.scrollTop = mobileEl.scrollHeight;
            }
        });
    }

    function formatObject(v: unknown) {
        try {
            return JSON.stringify(v, null, 2);
        } catch {
            return String(v);
        }
    }

    function cancelEdit() {
        editingMessageId.value = null;
        editingContent.value = '';
    }

    watch(() => adapter.getSending(), (isSending) => {
        if (isSending) {
            thinkingSeconds.value = 0;
            thinkingTimer = setInterval(() => {
                thinkingSeconds.value++;
            }, 1000);
            // AI 开始新回复时恢复自动下滑
            autoScrollEnabled.value = true;
            scrollToBottom(true);
            // 延迟重新绑定 scroll 监听（DOM 可能刚挂载）
            nextTick(() => bindScrollListeners());
            return;
        }
        if (thinkingTimer) {
            clearInterval(thinkingTimer);
            thinkingTimer = null;
        }
        thinkingSeconds.value = 0;
    });

    watch(
        () => (typeof getEditScopeKey === 'function' ? String(getEditScopeKey() || '') : ''),
        () => {
            cancelEdit();
        }
    );

    watch(
        () => adapter.getHistory?.(),
        (history) => {
            const editingId = editingMessageId.value;
            if (editingId === null || editingId === undefined) return;
            const list = Array.isArray(history) ? history : [];
            const exists = list.some(item => {
                const itemId = getMutableMessageId(item);
                return hasPersistedMessageId(itemId) && String(itemId) === String(editingId);
            });
            if (!exists) {
                cancelEdit();
            }
        }
    );

    function onDraftKeydown(e: KeyboardEvent) {
        if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.altKey && !e.metaKey) {
            e.preventDefault();
            send();
        }
    }

    async function send() {
        if (adapter.getSending?.()) return;
        const msg = draft.value;
        if (!msg.trim()) return;
        draft.value = '';
        await adapter.send(msg);
        await nextTick();
        scrollToBottom();
    }

    async function stop() {
        if (!adapter.stop) return;
        await adapter.stop();
    }

    async function clear() {
        if (adapter.getSending?.()) {
            bus.emit('toast', { type: 'info', message: '请等待当前回复完成后再清空' });
            return;
        }
        cancelEdit();
        await adapter.clear();
    }

    function startEdit(message: ChatLikeMessage) {
        if (adapter.getSending?.()) {
            bus.emit('toast', { type: 'info', message: '请等待当前回复完成后再编辑' });
            return;
        }
        const messageId = getMutableMessageId(message);
        if (!hasPersistedMessageId(messageId)) {
            bus.emit('toast', { type: 'info', message: '消息标识无效，暂时无法编辑' });
            return;
        }
        editingMessageId.value = messageId;
        editingContent.value = String(message?.content || '');
    }

    function onEditKeydown(e: KeyboardEvent, id: MessageId | null | undefined) {
        if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.altKey && !e.metaKey) {
            e.preventDefault();
            void saveEdit(id);
        } else if (e.key === 'Escape') {
            cancelEdit();
        }
    }

    async function saveEdit(id: MessageId | null | undefined) {
        if (adapter.getSending?.()) {
            bus.emit('toast', { type: 'info', message: '请等待当前回复完成后再保存编辑' });
            return;
        }
        if (!hasPersistedMessageId(id)) {
            bus.emit('toast', { type: 'warning', message: '该消息标识无效，暂时无法编辑' });
            return;
        }

        const content = editingContent.value;
        if (!content.trim()) return;

        editingMessageId.value = null;
        editingContent.value = '';

        try {
            await adapter.editMessage(id, content);
        } catch (error: unknown) {
            editingMessageId.value = id;
            editingContent.value = content;
            throw error;
        }
    }

    async function deleteMsg(id: MessageId | null | undefined) {
        if (!hasPersistedMessageId(id)) {
            bus.emit('toast', { type: 'info', message: '消息标识无效，暂时无法删除' });
            return;
        }
        await adapter.deleteMessage(id);
    }

    /** 重试：用原内容重新发送，触发重新生成 */
    async function retryMsg(id: MessageId | null | undefined, content: string) {
        if (adapter.getSending?.()) {
            bus.emit('toast', { type: 'info', message: '请等待当前回复完成后再重试' });
            return;
        }
        if (!hasPersistedMessageId(id)) {
            bus.emit('toast', { type: 'info', message: '消息标识无效，暂时无法重试' });
            return;
        }
        if (!content?.trim()) return;
        // 通过 editMessage 触发重新生成（保持原内容不变）
        await adapter.editMessage(id, content);
    }

    onUnmounted(() => {
        if (thinkingTimer) {
            clearInterval(thinkingTimer);
        }
        removeScrollListeners();
    });

    return {
        draft,
        editingMessageId,
        editingContent,
        thinkingSeconds,
        lastMessageIsAssistant,
        scrollToBottom,
        formatObject,
        onDraftKeydown,
        send,
        stop,
        clear,
        startEdit,
        cancelEdit,
        onEditKeydown,
        saveEdit,
        deleteMsg,
        retryMsg,
    };
}
