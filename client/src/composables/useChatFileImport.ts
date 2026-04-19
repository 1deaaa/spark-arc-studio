import { computed, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import bus from '@/eventBus';
import { useChatStore } from '@/components/stores/chatStore';
import { parseImportFile } from '@/services/fileImportService';
import { useDocumentImport } from '@/composables/useDocumentImport';

const CHAT_DIRECT_UPLOAD_MAX_TOKENS = 100000;
const CHAT_PARTIAL_CHUNK_TOKENS = 64000;

function formatTokenCount(value: number) {
  const num = Number(value) || 0;
  if (num >= 1000000) return `${(num / 1000000).toFixed(2)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return `${num}`;
}

export function useChatFileImport(getSessionId: () => number | null | undefined) {
  const { t } = useI18n();
  const chatStore = useChatStore();
  const importing = ref(false);

  const importedContext = computed(() => {
    const sessionId = getSessionId();
    if (sessionId == null) return null;
    return chatStore.getSession(sessionId)?.importedContext || null;
  });

  const importedContextDescription = computed(() => {
    const payload = importedContext.value;
    if (!payload) return '';
    const tokenText = `${formatTokenCount(payload.totalTokens)} tokens`;
    if (payload.isPartial) {
      return `${payload.sourceFormat} · ${tokenText} · ${t('components.chatPanel.importedFilePartial')}`;
    }
    return `${payload.sourceFormat} · ${tokenText}`;
  });

  async function importChatFile(file: File) {
    const sessionId = getSessionId();
    if (sessionId == null) {
      bus.emit('toast', { type: 'warning', message: t('components.chatPanel.noSession') });
      return;
    }

    importing.value = true;
    try {
      const parsed = await parseImportFile(file, CHAT_PARTIAL_CHUNK_TOKENS);
      const totalTokens = Number((parsed.chunk_info as { total_tokens_estimated?: unknown } | null)?.total_tokens_estimated || 0);
      const shouldUsePartialChunk = totalTokens > CHAT_DIRECT_UPLOAD_MAX_TOKENS;
      const firstChunk = parsed.chunks?.[0] || null;
      const selectedText = shouldUsePartialChunk ? String(firstChunk?.text || '').trim() : String(parsed.full_text || '').trim();
      if (!selectedText) {
        throw new Error(t('components.chatPanel.fileImportEmpty'));
      }

      chatStore.setSessionImportedContext(sessionId, {
        filename: parsed.filename || file.name,
        sourceFormat: parsed.source_format,
        text: selectedText,
        totalTokens,
        chunkTokens: shouldUsePartialChunk ? CHAT_PARTIAL_CHUNK_TOKENS : Math.max(totalTokens, 1),
        isPartial: shouldUsePartialChunk,
        warnings: Array.isArray(parsed.warnings) ? parsed.warnings.map((item) => ({ ...item })) : [],
        uploadedAt: Date.now(),
      });

      // TODO：后续应使用方法妥善处理分片。
      if (shouldUsePartialChunk) {
        bus.emit('toast', {
          type: 'info',
          message: t('components.chatPanel.partialImportNotice', { filename: parsed.filename || file.name }),
        });
      } else {
        bus.emit('toast', {
          type: 'success',
          message: t('components.chatPanel.importSuccess', { filename: parsed.filename || file.name }),
        });
      }

      const firstWarning = Array.isArray(parsed.warnings) ? parsed.warnings[0] : null;
      if (firstWarning?.message) {
        bus.emit('toast', { type: 'info', message: firstWarning.message });
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error || t('components.chatPanel.fileImportFailed'));
      bus.emit('toast', { type: 'error', message });
    } finally {
      importing.value = false;
    }
  }

  function clearImportedContext() {
    const sessionId = getSessionId();
    if (sessionId == null) return;
    chatStore.clearSessionImportedContext(sessionId);
  }

  const {
    fileInput,
    accept,
    loadCapabilities,
    handleFileChange,
    triggerFileInput,
  } = useDocumentImport({
    usage: 'general',
    onSelectFile: importChatFile,
    onInvalidFile: (message) => {
      bus.emit('toast', { type: 'warning', message });
    },
  });

  onMounted(() => {
    loadCapabilities();
  });

  return {
    fileInput,
    accept,
    importing,
    importedContext,
    importedContextDescription,
    handleFileChange,
    triggerFileInput,
    clearImportedContext,
  };
}
