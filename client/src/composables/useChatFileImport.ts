import { computed, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import bus from '@/eventBus';
import { useChatStore } from '@/components/stores/chatStore';
import { useProjectStore } from '@/components/stores/projectStore';
import {
  getAttachmentChunkTokensSetting,
  FileImportError,
  parseImportFile,
  setAttachmentChunkTokensSetting,
  type AttachmentChunkTokensSetting,
} from '@/services/fileImportService';
import { useDocumentImport } from '@/composables/useDocumentImport';

const ATTACHMENT_CHUNK_TOKENS_FALLBACK: AttachmentChunkTokensSetting = {
  success: true,
  chunkTokens: 64000,
  min: 1000,
  max: 120000,
  default: 64000,
};

function formatTokenCount(value: number) {
  const num = Number(value) || 0;
  if (num >= 1000000) return `${(num / 1000000).toFixed(2)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return `${num}`;
}

export function useChatFileImport(getSessionId: () => number | null | undefined) {
  const { t } = useI18n();
  const chatStore = useChatStore();
  const projectStore = useProjectStore();
  const importing = ref(false);
  const importAbortController = ref<AbortController | null>(null);

  /** 项目级附件分片大小配置（含 min / max / default 边界），用于附件面板 chunk size 设置。 */
  const chunkTokensSetting = ref<AttachmentChunkTokensSetting>({ ...ATTACHMENT_CHUNK_TOKENS_FALLBACK });
  const chunkTokensSettingLoading = ref(false);
  const chunkTokensSettingSaving = ref(false);

  /** 多附件真相源：直接读 session.attachments。 */
  const attachments = computed(() => {
    const sessionId = getSessionId();
    if (sessionId == null) return [];
    return chatStore.getSession(sessionId)?.attachments || [];
  });

  /** 老 API 兼容：旧调用方仍可读"第一个附件"。 */
  const importedContext = computed(() => attachments.value[0] || null);

  function describeAttachment(payload: { sourceFormat: string; totalTokens: number; isPartial: boolean; isOversized?: boolean }) {
    const tokenText = `${formatTokenCount(payload.totalTokens)} tokens`;
    if (payload.isOversized) {
      return `${payload.sourceFormat} · ${tokenText} · ${t('components.chatPanel.importedFileOversized')}`;
    }
    if (payload.isPartial) {
      return `${payload.sourceFormat} · ${tokenText} · ${t('components.chatPanel.importedFilePartial')}`;
    }
    return `${payload.sourceFormat} · ${tokenText}`;
  }

  const importedContextDescription = computed(() => {
    const payload = importedContext.value;
    return payload ? describeAttachment(payload) : '';
  });

  const attachmentDescriptions = computed(() => attachments.value.map(describeAttachment));

  function cancelImport() {
    const ctrl = importAbortController.value;
    if (!ctrl) return;
    try {
      ctrl.abort();
    } catch {
      // 已中止或不可中止，忽略
    }
  }

  function _isAbortError(error: unknown): boolean {
    if (!error) return false;
    if (error instanceof DOMException && error.name === 'AbortError') return true;
    const name = (error as { name?: string } | null)?.name || '';
    return name === 'AbortError' || name === 'CanceledError';
  }

  function openImportPicker() {
    if (importing.value) {
      cancelImport();
      return;
    }
    const projectName = projectStore.currentProject || '';
    if (!projectName) {
      bus.emit('toast', { type: 'warning', message: t('components.chatPanel.fileImportRequiresProject') });
      return;
    }
    triggerFileInput();
  }

  async function importChatFiles(files: File[]) {
    if (!files || files.length === 0) return;
    const sessionId = getSessionId();
    if (sessionId == null) {
      bus.emit('toast', { type: 'warning', message: t('components.chatPanel.noSession') });
      return;
    }
    const projectName = projectStore.currentProject || '';
    if (!projectName) {
      bus.emit('toast', { type: 'warning', message: t('components.chatPanel.fileImportRequiresProject') });
      return;
    }

    // 同会话同时只允许一组导入；新一批开始前先取消上一批。
    cancelImport();
    const controller = new AbortController();
    importAbortController.value = controller;
    importing.value = true;

    try {
      // chunkTokens 不传：让后端按项目级配置取。这样滑动窗口大小由项目配置统一决定。
      for (const file of files) {
        if (controller.signal.aborted) break;
        try {
          const parsed = await parseImportFile(file, undefined, controller.signal, projectName);
          const totalTokens = Number((parsed.chunk_info as { total_tokens_estimated?: unknown } | null)?.total_tokens_estimated || 0);
          // 单附件场景下：超阈值就走 partial（仅注入首片），后端按项目配置切分；否则灌全文。
          // 多附件场景下：partial 标记仅作为元信息保留，实际是否注入由后端"多附件 ≥ 2 仅注入清单"策略决定。
          // 超窗附件（is_oversized）：照常落盘成功，首轮只注入清单、不预注入正文。
          const shouldUsePartialChunk = Boolean(parsed.is_partial);
          const isOversized = Boolean((parsed as { is_oversized?: unknown }).is_oversized);
          const attachmentId = String(parsed.attachment_id || '').trim();
          if (!attachmentId) {
            throw new Error(t('components.chatPanel.fileImportPersistFailed'));
          }

          // 取后端实际切片大小：chunks[0].estimated_tokens 是真实生效值；fallback 到 totalTokens（不超过项目 max）。
          const effectiveChunkTokens = Number(parsed.chunks?.[0]?.estimated_tokens || 0)
            || (shouldUsePartialChunk ? chunkTokensSetting.value.chunkTokens : Math.max(totalTokens, 1));

          chatStore.addSessionAttachment(sessionId, {
            attachmentId,
            filename: parsed.filename || file.name,
            sourceFormat: parsed.source_format,
            totalTokens,
            chunkTokens: effectiveChunkTokens,
            isPartial: shouldUsePartialChunk,
            ...(isOversized ? { isOversized: true } : {}),
            warnings: Array.isArray(parsed.warnings) ? parsed.warnings.map((item) => ({ ...item })) : [],
            uploadedAt: Date.now(),
          });

          if (isOversized) {
            bus.emit('toast', {
              type: 'info',
              message: t('components.chatPanel.oversizedImportNotice', { filename: parsed.filename || file.name }),
            });
          } else if (shouldUsePartialChunk) {
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
        } catch (innerErr: unknown) {
          if (_isAbortError(innerErr)) {
            // 整批被取消，跳出循环；toast 在外层统一发。
            throw innerErr;
          }
          // 单文件失败时继续处理后续文件，避免一个坏文件阻塞其他附件。
          // 超窗不再走 413 拒绝（后端照常落盘 + 清单降级），此处仅保留历史 code 兼容。
          const message = innerErr instanceof Error
            ? innerErr.message
            : String(innerErr || t('components.chatPanel.fileImportFailed'));
          bus.emit('toast', {
            type: 'error',
            message: t('components.chatPanel.singleFileImportFailed', { filename: file.name, message }),
          });
        }
      }
    } catch (error: unknown) {
      if (_isAbortError(error)) {
        bus.emit('toast', { type: 'info', message: t('components.chatPanel.importCancelled') });
      } else {
        const message = error instanceof Error ? error.message : String(error || t('components.chatPanel.fileImportFailed'));
        bus.emit('toast', { type: 'error', message });
      }
    } finally {
      if (importAbortController.value === controller) {
        importAbortController.value = null;
      }
      importing.value = false;
    }
  }

  /** 老调用方兼容：单文件直接走多文件流水线（仅一个元素）。 */
  async function importChatFile(file: File) {
    await importChatFiles([file]);
  }

  function clearImportedContext() {
    const sessionId = getSessionId();
    if (sessionId == null) return;
    chatStore.setSessionAttachments(sessionId, []);
  }

  /** 用户主动从附件面板里删除：同步后端 + 标记历史消息 deleted。 */
  async function removeImportedContext(attachmentId?: string | null) {
    const sessionId = getSessionId();
    if (sessionId == null) return;
    await chatStore.removeSessionImportedContext(sessionId, attachmentId || null);
  }

  // ==================== chunk size 配置（项目级） ====================

  async function loadChunkTokensSetting() {
    if (chunkTokensSettingLoading.value) return;
    chunkTokensSettingLoading.value = true;
    try {
      const projectName = projectStore.currentProject || '';
      const next = await getAttachmentChunkTokensSetting(projectName || undefined);
      chunkTokensSetting.value = { ...next };
    } catch (e) {
      console.warn('[chat-file-import] 读取附件分片配置失败', e);
      // 失败时维持上一次值或 fallback，避免清掉用户刚保存的值。
    } finally {
      chunkTokensSettingLoading.value = false;
    }
  }

  async function saveChunkTokensSetting(value: number) {
    const projectName = projectStore.currentProject || '';
    if (!projectName) {
      bus.emit('toast', { type: 'warning', message: t('components.chatPanel.fileImportRequiresProject') });
      return;
    }
    chunkTokensSettingSaving.value = true;
    try {
      const next = await setAttachmentChunkTokensSetting(value, projectName);
      chunkTokensSetting.value = { ...next };
      bus.emit('toast', {
        type: 'success',
        message: t('components.chatPanel.chunkTokensSaved', { value: formatTokenCount(next.chunkTokens) }),
      });
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e || t('components.chatPanel.chunkTokensSaveFailed'));
      bus.emit('toast', { type: 'error', message });
    } finally {
      chunkTokensSettingSaving.value = false;
    }
  }

  const {
    fileInput,
    accept,
    loadCapabilities,
    handleFileChange,
    triggerFileInput,
  } = useDocumentImport({
    usage: 'general',
    onSelectFiles: importChatFiles,
    onInvalidFile: (message) => {
      bus.emit('toast', { type: 'warning', message });
    },
  });

  onMounted(() => {
    loadCapabilities();
    loadChunkTokensSetting();
  });

  return {
    fileInput,
    accept,
    importing,
    attachments,
    attachmentDescriptions,
    importedContext,
    importedContextDescription,
    handleFileChange,
    triggerFileInput,
    openImportPicker,
    clearImportedContext,
    removeImportedContext,
    cancelImport,
    importChatFile,
    importChatFiles,
    chunkTokensSetting,
    chunkTokensSettingLoading,
    chunkTokensSettingSaving,
    loadChunkTokensSetting,
    saveChunkTokensSetting,
  };
}
