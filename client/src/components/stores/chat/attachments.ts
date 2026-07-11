export type AnyRecord = Record<string, any>;

export type ChatImportedContext = {
  /** 后端落盘后的附件 id（必填）；前端只持有引用，全文由后端按 id 从磁盘加载。 */
  attachmentId: string;
  filename: string;
  sourceFormat: string;
  totalTokens: number;
  chunkTokens: number;
  isPartial: boolean;
  warnings: Array<{ code: string; message: string }>;
  uploadedAt: number;
};

export type ResolvedMessageContext = {
  activeContext: string;
  activeMeta: AnyRecord | null;
  messageMetadata: AnyRecord | null;
};

export function serializeImportedContext(payload: ChatImportedContext): AnyRecord {
  return {
    attachmentId: payload.attachmentId,
    filename: payload.filename,
    sourceFormat: payload.sourceFormat,
    totalTokens: payload.totalTokens,
    chunkTokens: payload.chunkTokens,
    isPartial: payload.isPartial,
    warnings: (payload.warnings || []).map((item) => ({ ...item })),
    uploadedAt: payload.uploadedAt,
  };
}

export function resolveActiveContext(
  provider: (() => string | { text?: unknown; meta?: unknown } | null | undefined) | null,
  attachments: ChatImportedContext[] | null = null,
) {
  let activeContext = '';
  let activeMeta: AnyRecord | null = null;

  if (provider) {
    try {
      const providedContext = provider();
      if (providedContext && typeof providedContext === 'object' && !Array.isArray(providedContext)) {
        activeContext = 'text' in providedContext ? String(providedContext.text || '') : '';
        const metaValue = 'meta' in providedContext ? providedContext.meta : null;
        activeMeta = metaValue && typeof metaValue === 'object' ? metaValue as AnyRecord : null;
      } else {
        activeContext = String(providedContext || '');
      }
    } catch (e: unknown) {
      console.warn('获取上下文失败', e);
    }
  }

  // 引用制：activeContext 不带全文，仅在 activeMeta.importedFiles 列表上传 attachmentId 引用。
  const validAttachments = (attachments || []).filter(
    (item) => item && String(item.attachmentId || '').trim() && String(item.filename || '').trim(),
  );
  if (validAttachments.length > 0) {
    const importedFiles = validAttachments.map(serializeImportedContext);
    activeMeta = {
      ...(activeMeta || {}),
      importedFiles,
    };
  }

  return { activeContext, activeMeta };
}

export function normalizeRawImportedFile(raw: unknown): AnyRecord | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  const attachment = raw as AnyRecord;
  if (attachment.deleted) return null;
  const attachmentId = String(attachment.attachmentId || '').trim();
  const filename = String(attachment.filename || '').trim();
  if (!attachmentId || !filename) return null;
  return {
    attachmentId,
    filename,
    sourceFormat: String(attachment.sourceFormat || '').trim(),
    totalTokens: Number(attachment.totalTokens || 0) || 0,
    chunkTokens: Number(attachment.chunkTokens || 0) || 0,
    isPartial: Boolean(attachment.isPartial),
    warnings: Array.isArray(attachment.warnings)
      ? attachment.warnings.map((item: AnyRecord = {}) => ({
          code: String(item.code || '').trim(),
          message: String(item.message || '').trim(),
        })).filter((item: AnyRecord) => item.code || item.message)
      : [],
    uploadedAt: Number(attachment.uploadedAt || 0) || 0,
  };
}

export function extractImportedFilesMeta(activeMeta: AnyRecord | null = null): AnyRecord[] {
  if (!activeMeta || typeof activeMeta !== 'object') return [];
  const importedFiles = (activeMeta as AnyRecord).importedFiles;
  if (Array.isArray(importedFiles)) {
    const seen = new Set<string>();
    const result: AnyRecord[] = [];
    for (const item of importedFiles) {
      const normalized = normalizeRawImportedFile(item);
      if (!normalized) continue;
      if (seen.has(normalized.attachmentId)) continue;
      seen.add(normalized.attachmentId);
      result.push(normalized);
    }
    return result;
  }
  return [];
}

export function isDeletedAttachmentContext(value: unknown) {
  return /^\[附件\s+".+"\s+已被删除\]$/.test(String(value || '').trim());
}

export function sameImportedFile(a: AnyRecord | null | undefined, b: AnyRecord | null | undefined) {
  if (!a || !b) return false;
  const aFilename = String(a.filename || '').trim();
  const bFilename = String(b.filename || '').trim();
  if (!aFilename || !bFilename || aFilename !== bFilename) return false;
  const aUploadedAt = Number(a.uploadedAt || 0) || 0;
  const bUploadedAt = Number(b.uploadedAt || 0) || 0;
  if (aUploadedAt && bUploadedAt) return aUploadedAt === bUploadedAt;
  return true;
}

export function markMessageImportedFileDeleted(message: AnyRecord | null | undefined, reference: AnyRecord | null | undefined, deletedAt = Math.floor(Date.now() / 1000)) {
  if (!message) return false;
  const metadata = message.metadata && typeof message.metadata === 'object' ? message.metadata as AnyRecord : null;
  if (!metadata) return false;

  const importedFiles = Array.isArray(metadata.importedFiles) ? metadata.importedFiles as AnyRecord[] : null;
  let touched = false;
  let matchedFilename = '';

  if (importedFiles && importedFiles.length > 0) {
    const nextList = importedFiles.map((entry) => {
      if (!entry || typeof entry !== 'object') return entry;
      const sameByRef = !reference || sameImportedFile(entry as AnyRecord, reference);
      if (!sameByRef) return entry;
      touched = true;
      matchedFilename = String((entry as AnyRecord).filename || '').trim() || matchedFilename;
      return { ...(entry as AnyRecord), deleted: true, deletedAt };
    });
    if (touched) {
      metadata.importedFiles = nextList;
    }
  }

  if (!touched) return false;
  const filename = matchedFilename || '未知文件';
  if (typeof metadata.active_context === 'string') {
    metadata.active_context = `[附件 "${filename}" 已被删除]`;
  }
  return true;
}

export function markSessionImportedFileDeleted(session: { history: AnyRecord[] }, reference: AnyRecord | null | undefined, deletedAt = Math.floor(Date.now() / 1000)) {
  if (!session || !reference) return;
  session.history = (session.history || []).map((message) => {
    if (!markMessageImportedFileDeleted(message, reference, deletedAt)) return message;
    return { ...message, metadata: { ...(message.metadata || {}) } };
  });
}

export function toChatImportedContext(payload: AnyRecord): ChatImportedContext {
  return {
    attachmentId: String(payload.attachmentId || '').trim(),
    filename: String(payload.filename || '').trim(),
    sourceFormat: String(payload.sourceFormat || '').trim(),
    totalTokens: Number(payload.totalTokens || 0) || 0,
    chunkTokens: Number(payload.chunkTokens || 0) || 0,
    isPartial: Boolean(payload.isPartial),
    warnings: Array.isArray(payload.warnings)
      ? (payload.warnings as AnyRecord[]).map((item) => ({
          code: String((item as AnyRecord)?.code || ''),
          message: String((item as AnyRecord)?.message || ''),
        }))
      : [],
    uploadedAt: Number(payload.uploadedAt || 0) || 0,
  };
}

export function findLatestImportedContexts(history: AnyRecord[] = []): ChatImportedContext[] {
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const message = history[i];
    if (message?.role !== 'user') continue;
    const list = extractImportedFilesMeta(message?.metadata || null);
    if (list.length > 0) {
      return list.map(toChatImportedContext);
    }
  }
  return [];
}

export function findLatestImportedContext(history: AnyRecord[] = []): ChatImportedContext | null {
  return findLatestImportedContexts(history)[0] || null;
}

export function buildUserMessageMetadata(activeContext: unknown, activeMeta: AnyRecord | null = null) {
  const metadata: AnyRecord = {};
  const normalizedContext = typeof activeContext === 'string' ? activeContext.trim() : String(activeContext || '').trim();
  const importedFiles = extractImportedFilesMeta(activeMeta);
  if (normalizedContext) {
    metadata.active_context = normalizedContext;
  }
  if (importedFiles.length > 0) {
    metadata.importedFiles = importedFiles.map((item) => ({ ...item }));
  }
  return Object.keys(metadata).length ? metadata : null;
}

export function resolveMessageContextForEdit(
  provider: (() => string | { text?: unknown; meta?: unknown } | null | undefined) | null,
  message: AnyRecord | null | undefined,
): ResolvedMessageContext {
  const { activeContext: providerContext, activeMeta: providerMeta } = resolveActiveContext(provider, []);
  const messageMetadata = message?.metadata && typeof message.metadata === 'object' ? message.metadata as AnyRecord : null;
  const storedRawContext = typeof messageMetadata?.active_context === 'string' ? messageMetadata.active_context.trim() : '';
  const storedContext = isDeletedAttachmentContext(storedRawContext) ? '' : storedRawContext;
  const importedFiles = extractImportedFilesMeta(messageMetadata);
  const activeContext = storedContext || providerContext;
  const activeMeta = importedFiles.length > 0
    ? { ...(providerMeta || {}), importedFiles }
    : (providerMeta || null);

  return {
    activeContext,
    activeMeta,
    messageMetadata: buildUserMessageMetadata(activeContext, activeMeta),
  };
}
