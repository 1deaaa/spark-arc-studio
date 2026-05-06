import { fetchWithAuth } from './apiClient';
import { getFriendlyErrorMessage } from './aiService';

export type ImportUsage = 'general' | 'style_analysis';

export type ImportWarning = {
  code: string;
  message: string;
};

export type ImportSectionSummary = {
  section_type: string;
  title: string;
  estimated_tokens: number;
};

export type ParsedImportChunk = {
  text: string;
  index: number;
  total: number;
  char_count: number;
  estimated_tokens: number;
  previous_tail: string;
};

export type ParsedImportResponse = {
  success: boolean;
  /** 后端落盘后的附件 id（基于内容 sha256 前 16 位）。成功响应下必有值。 */
  attachment_id: string;
  filename: string;
  source_format: string;
  full_text: string;
  sections: ImportSectionSummary[];
  warnings: ImportWarning[];
  metadata: Record<string, unknown>;
  chunks: ParsedImportChunk[];
  chunk_info: Record<string, unknown>;
};

export type ImportCapabilitiesResponse = {
  success: boolean;
  formats: Record<string, string[]>;
  accept: Record<string, string>;
  notes: Record<string, string>;
};

export const FALLBACK_IMPORT_CAPABILITIES: ImportCapabilitiesResponse = {
  success: true,
  formats: {
    general: ['.txt', '.md', '.docx', '.epub', '.pdf'],
    style_analysis: ['.txt', '.md', '.docx', '.epub', '.pdf'],
  },
  accept: {
    general: '.txt,.md,.docx,.epub,.pdf',
    style_analysis: '.txt,.md,.docx,.epub,.pdf',
  },
  notes: {
    '.pdf': '仅支持带文本层的 PDF，暂不支持扫描件 OCR',
    '.txt': '自动识别常见中文编码',
  },
};

export async function getImportCapabilities(): Promise<ImportCapabilitiesResponse> {
  const response = await fetchWithAuth('/api/import/capabilities');
  const result = await response.json().catch(() => null);
  if (!response.ok || !result?.success) {
    throw new Error(getFriendlyErrorMessage(result?.error || '获取文件导入能力失败', response.status));
  }
  return result as ImportCapabilitiesResponse;
}

export async function parseImportFile(
  file: Blob | File,
  chunkTokens = 30000,
  signal?: AbortSignal,
  projectName?: string | null,
): Promise<ParsedImportResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('chunkTokens', String(chunkTokens));
  if (projectName) {
    formData.append('projectName', projectName);
  }

  const response = await fetchWithAuth('/api/import/parse', {
    method: 'POST',
    body: formData,
    signal,
  });
  const result = await response.json().catch(() => null);
  if (!response.ok || !result?.success) {
    throw new Error(getFriendlyErrorMessage(result?.error || '解析导入文件失败', response.status));
  }
  return result as ParsedImportResponse;
}
