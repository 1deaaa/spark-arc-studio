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
import { ref, computed, watch, nextTick, onUnmounted } from 'vue';

export function useChatActions(adapter, options = {}) {
    const { listRef = ref(null), mobileListRef = ref(null) } = options;

    const draft = ref('');
    const editingMessageId = ref(null);
    const editingContent = ref('');

    // 思考动画
    const thinkingSeconds = ref(0);
    let thinkingTimer = null;

    const lastMessageIsAssistant = computed(() => {
        const history = adapter.getHistory();
        if (!history || history.length === 0) return false;
        return history[history.length - 1].role === 'assistant';
    });

    // 监听发送状态，控制计时器
    watch(() => adapter.getSending(), (isSending) => {
        if (isSending) {
            thinkingSeconds.value = 0;
            thinkingTimer = setInterval(() => {
                thinkingSeconds.value++;
            }, 1000);
            scrollToBottom();
        } else {
            if (thinkingTimer) {
                clearInterval(thinkingTimer);
                thinkingTimer = null;
            }
            thinkingSeconds.value = 0;
        }
    });

    function scrollToBottom() {
        nextTick(() => {
            // 支持多层组件嵌套的 ref 解析:
            // 1. ChatPanel ref -> ChatPanel.listRef (ChatMessageList ref) -> ChatMessageList.listRef (DOM)
            // 2. ChatMessageList ref -> ChatMessageList.listRef (DOM)
            // 3. 直接 DOM 元素
            function resolveEl(ref) {
                let el = ref?.value;
                // 最多穿透两层 .listRef
                if (el && el.listRef) el = el.listRef;
                if (el && el.listRef) el = el.listRef;
                return el;
            }
            const desktopEl = resolveEl(listRef);
            if (desktopEl && desktopEl.scrollHeight !== undefined) {
                desktopEl.scrollTop = desktopEl.scrollHeight;
            }
            const mobileEl = resolveEl(mobileListRef);
            if (mobileEl && mobileEl.scrollHeight !== undefined) {
                mobileEl.scrollTop = mobileEl.scrollHeight;
            }
        });
    }

    function formatObject(v) {
        try {
            return JSON.stringify(v, null, 2);
        } catch {
            return String(v);
        }
    }

    function onDraftKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.altKey && !e.metaKey) {
            e.preventDefault();
            send();
        }
    }

    async function send() {
        const msg = draft.value;
        draft.value = '';
        if (!msg.trim()) return;
        await adapter.send(msg);
        await nextTick();
        scrollToBottom();
    }

    async function clear() {
        await adapter.clear();
    }

    function startEdit(m) {
        editingMessageId.value = m.id;
        editingContent.value = m.content;
    }

    function cancelEdit() {
        editingMessageId.value = null;
        editingContent.value = '';
    }

    function onEditKeydown(e, id) {
        if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.altKey && !e.metaKey) {
            e.preventDefault();
            saveEdit(id);
        } else if (e.key === 'Escape') {
            cancelEdit();
        }
    }

    async function saveEdit(id) {
        const content = editingContent.value;
        if (!content.trim()) return;

        editingMessageId.value = null;
        editingContent.value = '';

        try {
            await adapter.editMessage(id, content);
        } catch (e) {
            // 编辑失败时恢复状态
            editingMessageId.value = id;
            editingContent.value = content;
            throw e;
        }
    }

    async function deleteMsg(id) {
        if (!id) return;
        await adapter.deleteMessage(id);
    }

    onUnmounted(() => {
        if (thinkingTimer) {
            clearInterval(thinkingTimer);
        }
    });

    return {
        draft,
        editingMessageId,
        editingContent,
        thinkingSeconds,
        lastMessageIsAssistant,
        // 方法
        scrollToBottom,
        formatObject,
        onDraftKeydown,
        send,
        clear,
        startEdit,
        cancelEdit,
        onEditKeydown,
        saveEdit,
        deleteMsg
    };
}
