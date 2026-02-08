/**
 * 聊天交互 Composable
 * 从 GlobalChatFloat.vue 提取的消息操作和思考动画逻辑
 */
import { ref, computed, watch, nextTick, onUnmounted } from 'vue';

export function useChatActions(chatStore, options = {}) {
    const { listEl = ref(null), mobileListEl = ref(null) } = options;

    const draft = ref('');
    const editingMessageId = ref(null);
    const editingContent = ref('');

    // 思考动画
    const thinkingSeconds = ref(0);
    let thinkingTimer = null;

    const lastMessageIsAssistant = computed(() => {
        const history = chatStore.history || [];
        if (history.length === 0) return false;
        return history[history.length - 1].role === 'assistant';
    });

    // 监听发送状态，控制计时器
    watch(() => chatStore.sending, (isSending) => {
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
            if (listEl.value) {
                listEl.value.scrollTop = listEl.value.scrollHeight;
            }
            if (mobileListEl.value) {
                mobileListEl.value.scrollTop = mobileListEl.value.scrollHeight;
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
        await chatStore.send(msg);
        await nextTick();
        scrollToBottom();
    }

    async function clear() {
        await chatStore.clear();
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
        if (!editingContent.value.trim()) return;
        await chatStore.editMessage(id, editingContent.value);
        editingMessageId.value = null;
        editingContent.value = '';
    }

    async function deleteMsg(id) {
        if (!id) return;
        await chatStore.deleteMessage(id);
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
