import { fetchWithAuth } from './apiClient';
import { consumeSSEReader, parseSSEEventPayload } from '@/utils/streamingRuntime';
import type {
  ApiMutationResult,
  InspirationEntry,
  InspirationListResponse,
  InspirationScope,
  InspirationStatus,
  InspirationTags,
  JsonObject,
  OutlineData,
  OutlineHistoryEntry,
  StoryCharacter,
  StoryCharacterDetail,
  StoryFileContentResponse,
  StoryFileTreeNode,
  StoryMutationResult,
} from './aiContracts';
import type { ArcDialogueNode, ArcScene } from './arcParser';

type StreamOptions = {
  signal?: AbortSignal;
};

type StoryBindingsPayload = JsonObject[] | JsonObject;

type InspirationUpdatePayload = {
  source?: string;
  content?: string;
  tags?: InspirationTags;
  status?: InspirationStatus;
};

type OutlineExportResult = StoryMutationResult & {
  existing?: string[];
};

type StyleProfileLookupResult = JsonObject | string | { error: true } | null;

type StyleProfileMetaResult = {
  style_profile: JsonObject | string | null;
  style_id: string | null;
  style_name: string | null;
  project_binding: {
    style_id: string;
    style_name: string;
  } | null;
};

async function fetchSSEAndGetResult<T extends Record<string, unknown>>(url: string, body: unknown, options: StreamOptions = {}): Promise<T> {
  const response = await fetchWithAuth(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: options.signal,
  });

  if (!response.ok) {
    let errorMsg = '请求失败';
    try {
      const result = await response.json();
      errorMsg = result.error || errorMsg;
    } catch (e) { }
    throw new Error(errorMsg);
  }

  if (!response.body) {
    throw new Error('浏览器不支持流式响应 (response.body 为空)');
  }

  let finalResult: Record<string, unknown> | null = null;
  await consumeSSEReader(response.body.getReader(), {
    signal: options.signal,
    onEvent: async (evt) => {
      const data = parseSSEEventPayload(evt?.data || '');
      if (evt?.event === 'done') {
        finalResult = data;
        return;
      }
      if (evt?.event === 'error') {
        throw new Error(String(data.error || data.message || data.raw || 'Stream Error'));
      }
    },
  });

  if (!finalResult) {
    // If stream ended without 'done' but also no error, check if we might have missed it or it's empty
    // But since we control the backend, we expect 'done' event.
    // However, if the connection closed early?
    throw new Error("连接断开或未收到结果");
  }

  return finalResult as T;
}

// --- 文件与项目操作 ---
export async function fetchFileTree(projectName: string, format: string | null = null): Promise<StoryFileTreeNode[]> {
  const suffix = format ? `?format=${encodeURIComponent(format)}` : '';
  const response = await fetchWithAuth(`/api/story-files/${projectName}${suffix}`);
  if (!response.ok) throw new Error('无法加载文件树');
  return await response.json() as StoryFileTreeNode[];
}

export async function fetchStoryFile(projectName: string, filePath: string): Promise<StoryFileContentResponse> {
  const encoded = String(filePath).split('/').map(encodeURIComponent).join('/');
  const response = await fetchWithAuth(`/api/file-content/${encodeURIComponent(projectName)}/${encoded}`);
  if (!response.ok) throw new Error('无法加载剧本文件');
  return await response.json() as StoryFileContentResponse;
}

export async function saveStory(projectName: string, filename: string, data: string | ArcScene | ArcScene[]): Promise<StoryMutationResult> {
  const response = await fetchWithAuth('/api/save-story', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, filename, data }),
  });
  const result = await response.json() as StoryMutationResult;
  if (!response.ok || result.success === false) throw new Error(result.message || '保存失败');
  return result;
}

export async function absorbStoryMemory(projectName: string, filename: string): Promise<StoryMutationResult & { queued?: boolean }> {
  const response = await fetchWithAuth('/api/story-memory/absorb-story', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, filename }),
  });
  const result = await response.json() as StoryMutationResult & { queued?: boolean };
  if (!response.ok || result.success === false) throw new Error(result.message || '提交记忆吸收失败');
  return result;
}

// 上传剧本文件到当前项目 stories 目录
export async function uploadStory(projectName: string, file: File): Promise<StoryMutationResult> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('projectName', projectName);

  const response = await fetchWithAuth('/api/upload-story', {
    method: 'POST',
    body: formData,
  });
  const result = await response.json() as StoryMutationResult;
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '上传失败');
  }
  return result;
}

export async function createFileOrFolder(projectName: string, type: 'folder' | 'story', path: string): Promise<StoryMutationResult> {
  const response = await fetchWithAuth('/api/file-operations/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, type, path }),
  });
  if (!response.ok) {
    const result = await response.json() as StoryMutationResult;
    throw new Error(result.message || '创建失败');
  }
  return await response.json() as StoryMutationResult;
}

export async function deleteFileOrFolder(projectName: string, path: string): Promise<StoryMutationResult> {
  const response = await fetchWithAuth('/api/file-operations/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, path }),
  });
  if (!response.ok) {
    const result = await response.json() as StoryMutationResult;
    throw new Error(result.message || '删除失败');
  }
  return await response.json() as StoryMutationResult;
}

export async function renameFileOrFolder(projectName: string, oldPath: string, newPath: string): Promise<StoryMutationResult> {
  const response = await fetchWithAuth('/api/file-operations/rename', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, oldPath, newPath }),
  });
  if (!response.ok) {
    const result = await response.json() as StoryMutationResult;
    throw new Error(result.message || '重命名失败');
  }
  return await response.json() as StoryMutationResult;
}

export async function moveFileOrFolder(projectName: string, sourcePath: string, targetPath: string): Promise<StoryMutationResult> {
  const response = await fetchWithAuth('/api/file-operations/move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, sourcePath, targetPath }),
  });
  const result = await response.json() as StoryMutationResult;
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '移动失败');
  }
  return result;
}

export async function saveStoriesOrder(projectName: string, dirPath: string, order: string[]): Promise<StoryMutationResult> {
  const response = await fetchWithAuth('/api/file-operations/save-order', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, dirPath, order }),
  });
  const result = await response.json() as StoryMutationResult;
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '保存排序失败');
  }
  return result;
}

export const NOVEL_SUBMISSION_PLATFORMS = ['fanqie', 'qidian', 'qimao', 'jinjiang', 'zongheng'] as const;
export type NovelSubmissionPlatform = typeof NOVEL_SUBMISSION_PLATFORMS[number];

function extractDownloadFilename(disposition: string, fallback: string): string {
  const utf8Match = disposition.match(/filename\*=UTF-8''(.+?)(?:;|$)/);
  if (utf8Match) return decodeURIComponent(utf8Match[1]);
  const match = disposition.match(/filename="?([^"]+)"?/);
  return match?.[1] || fallback;
}

async function parseDownloadError(response: Response, fallback: string): Promise<string> {
  try {
    const contentType = response.headers.get('Content-Type') || '';
    if (contentType.includes('application/json')) {
      const result = await response.json() as StoryMutationResult & { error?: string };
      return result.message || result.error || fallback;
    }
    const text = await response.text();
    return text || fallback;
  } catch {
    return fallback;
  }
}

export async function downloadNovelSubmissionExport(
  projectName: string,
  platform: NovelSubmissionPlatform,
): Promise<void> {
  const response = await fetchWithAuth(
    `/api/story-novel/${encodeURIComponent(projectName)}/submission-export?platform=${encodeURIComponent(platform)}`,
  );

  if (!response.ok) {
    throw new Error(await parseDownloadError(response, '导出投稿包失败'));
  }

  const filename = extractDownloadFilename(
    response.headers.get('Content-Disposition') || '',
    `${projectName}_${platform}_submission.zip`,
  );
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// --- 角色、蓝图、绑定、注册表 ---

/**
 * 获取角色列表
 * @param {string} projectName - 项目名称
 * @param {boolean} includeContent - 是否包含角色设定内容（编辑器用）
 * @returns {Promise<Array>} 角色数组 [{id, name, desc, content?}]
 */
export async function fetchCharacters(projectName: string, includeContent: true, includeSystem?: boolean): Promise<StoryCharacterDetail[]>;
export async function fetchCharacters(projectName: string, includeContent?: false, includeSystem?: boolean): Promise<StoryCharacter[]>;
export async function fetchCharacters(projectName: string, includeContent = false, includeSystem = false): Promise<StoryCharacter[] | StoryCharacterDetail[]> {
  if (!projectName) return [];
  let url = `/api/characters?projectName=${encodeURIComponent(projectName)}`;
  if (includeContent) url += '&includeContent=true';
  if (includeSystem) url += '&includeSystem=true';

  const response = await fetchWithAuth(url);
  if (!response.ok) {
    let message = '获取角色列表失败';
    try {
      const error = await response.json() as { error?: string; message?: string; detail?: string };
      message = error.error || error.message || error.detail || message;
    } catch {}
    throw new Error(message);
  }

  const result = await response.json() as StoryCharacter[] | StoryCharacterDetail[];
  // 后端直接返回数组
  return Array.isArray(result) ? result : [];
}

/**
 * 创建新角色
 */
export async function createCharacter(projectName: string, name: string, content?: string): Promise<StoryMutationResult> {
  const body: { projectName: string; name: string; content?: string } = { projectName, name };
  if (content !== undefined) body.content = content;
  const response = await fetchWithAuth('/api/characters', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const result = await response.json() as StoryMutationResult;
  if (!response.ok || result.success === false) {
    throw new Error(result.error || result.message || '创建角色失败');
  }
  return result;
}

/**
 * 保存角色设定内容
 */
export async function saveCharacter(projectName: string, id: number | string, content: string): Promise<ApiMutationResult> {
  const response = await fetchWithAuth('/api/characters', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, id, content }),
  });
  const result = await response.json() as ApiMutationResult;
  if (!response.ok || result.success === false) {
    throw new Error(result.error || result.message || '保存角色失败');
  }
  return result;
}

/**
 * 重命名角色
 */
export async function renameCharacter(projectName: string, id: number | string, newName: string): Promise<ApiMutationResult> {
  const response = await fetchWithAuth('/api/characters/rename', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, id, newName }),
  });
  const result = await response.json() as ApiMutationResult;
  if (!response.ok || result.success === false) {
    throw new Error(result.error || result.message || '重命名角色失败');
  }
  return result;
}

/**
 * 删除角色
 */
export async function deleteCharacter(projectName: string, id: number): Promise<ApiMutationResult> {
  const response = await fetchWithAuth(
    `/api/characters?projectName=${encodeURIComponent(projectName)}&id=${id}`,
    { method: 'DELETE' }
  );
  const result = await response.json() as ApiMutationResult;
  if (!response.ok || result.success === false) {
    throw new Error(result.error || result.message || '删除角色失败');
  }
  return result;
}

export interface CharacterRelation {
  id: string;
  source: string;
  target: string;
  relation: string;
  note: string;
  created_at?: string;
  updated_at?: string;
}

export async function fetchCharacterRelations(projectName: string): Promise<CharacterRelation[]> {
  if (!projectName) return [];
  const response = await fetchWithAuth(`/api/character-relations?projectName=${encodeURIComponent(projectName)}`);
  const result = await response.json() as CharacterRelation[] | { error?: string };
  if (!response.ok) throw new Error((result as { error?: string }).error || '获取角色关系失败');
  return Array.isArray(result) ? result : [];
}

export async function createCharacterRelation(
  projectName: string,
  payload: Omit<CharacterRelation, 'id' | 'created_at' | 'updated_at'>,
): Promise<CharacterRelation> {
  const response = await fetchWithAuth('/api/character-relations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, ...payload }),
  });
  const result = await response.json() as { success?: boolean; relation?: CharacterRelation; error?: string };
  if (!response.ok || result.success === false || !result.relation) {
    throw new Error(result.error || '创建角色关系失败');
  }
  return result.relation;
}

export async function updateCharacterRelation(
  projectName: string,
  relationId: string,
  payload: Omit<CharacterRelation, 'id' | 'created_at' | 'updated_at'>,
): Promise<CharacterRelation> {
  const response = await fetchWithAuth(`/api/character-relations/${encodeURIComponent(relationId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, ...payload }),
  });
  const result = await response.json() as { success?: boolean; relation?: CharacterRelation; error?: string };
  if (!response.ok || result.success === false || !result.relation) {
    throw new Error(result.error || '保存角色关系失败');
  }
  return result.relation;
}

export async function deleteCharacterRelation(projectName: string, relationId: string): Promise<ApiMutationResult> {
  const response = await fetchWithAuth(
    `/api/character-relations/${encodeURIComponent(relationId)}?projectName=${encodeURIComponent(projectName)}`,
    { method: 'DELETE' },
  );
  const result = await response.json() as ApiMutationResult;
  if (!response.ok || result.success === false) throw new Error(result.error || '删除角色关系失败');
  return result;
}

export async function fetchBlueprint(projectName: string): Promise<JsonObject> {
  const response = await fetchWithAuth(`/api/blueprint/${encodeURIComponent(projectName)}`);
  if (!response.ok) {
    if (response.status === 404) return {};
    throw new Error('无法加载蓝图数据');
  }
  return await response.json() as JsonObject;
}

export async function saveBlueprint(projectName: string, data: JsonObject): Promise<StoryMutationResult> {
  const response = await fetchWithAuth(`/api/blueprint/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  const result = await response.json() as StoryMutationResult;
  if (!response.ok || result.success === false) throw new Error(result.message || '保存蓝图失败');
  return result;
}

export async function fetchBindings(projectName: string): Promise<JsonObject[]> {
  const response = await fetchWithAuth(`/api/bindings/${encodeURIComponent(projectName)}`);
  return response.ok ? await response.json() as JsonObject[] : [];
}

export async function saveBindings(projectName: string, data: StoryBindingsPayload): Promise<StoryMutationResult> {
  const response = await fetchWithAuth(`/api/bindings/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return await response.json() as StoryMutationResult;
}

export async function fetchActionBindings(projectName: string): Promise<JsonObject[]> {
  const response = await fetchWithAuth(`/api/action-bindings/${encodeURIComponent(projectName)}`);
  return response.ok ? await response.json() as JsonObject[] : [];
}

export async function saveActionBindings(projectName: string, data: StoryBindingsPayload): Promise<StoryMutationResult> {
  const response = await fetchWithAuth(`/api/action-bindings/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  const result = await response.json() as StoryMutationResult;
  if (!response.ok || result.success === false) throw new Error(result.message || '保存行为函数绑定失败');
  return result;
}

export async function fetchRegistries(projectName: string): Promise<JsonObject[]> {
  const response = await fetchWithAuth(`/api/registries/${encodeURIComponent(projectName)}`);
  return response.ok ? await response.json() as JsonObject[] : [];
}

export async function saveRegistries(projectName: string, data: StoryBindingsPayload): Promise<StoryMutationResult> {
  const response = await fetchWithAuth(`/api/registries/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  const result = await response.json() as StoryMutationResult;
  if (!response.ok || result.success === false) throw new Error(result.message || '保存注册表失败');
  return result;
}

// --- 历史记录 ---
export async function getOutlineHistory(projectName: string): Promise<OutlineHistoryEntry[]> {
  const response = await fetchWithAuth(`/api/history/outline/${encodeURIComponent(projectName)}`);
  const result = await response.json() as { success?: boolean; error?: string; history?: OutlineHistoryEntry[] };
  if (!response.ok || result.success === false) throw new Error(result.error || '获取历史失败');
  return result.history || [];
}

export async function deleteOutlineHistory(projectName: string, entryId: number): Promise<ApiMutationResult> {
  const response = await fetchWithAuth(`/api/history/outline/${encodeURIComponent(projectName)}/${entryId}`, {
    method: 'DELETE',
  });
  const result = await response.json() as ApiMutationResult;
  if (!response.ok || result.success === false) throw new Error(result.error || '删除历史失败');
  return result;
}

export async function restoreOutlineFromHistory(projectName: string, entryId: number): Promise<OutlineData> {
  const response = await fetchWithAuth(`/api/history/outline/${encodeURIComponent(projectName)}/${entryId}/restore`, {
    method: 'POST',
  });
  const result = await response.json() as { success?: boolean; error?: string; markup?: string; outline?: OutlineData };
  if (!response.ok || result.success === false) throw new Error(result.error || '恢复失败');
  // 优先使用 markup 字段（新格式），回退到 outline 字段（旧格式）
  if (result.markup) {
    const { parseOutlineMarkup } = await import('../utils/markupSerializer');
    return parseOutlineMarkup(result.markup);
  }
  return result.outline || { title: '', nodes: [] } as OutlineData;
}

// --- 全局灵感系统 (用户级别，非项目级别) ---

/**
 * 灵感列表查询参数。
 * - scope=all （默认）返回全部，保持向后兼容；
 * - scope=project 需同时传 project；
 * - scope=drafts 仅返回未绑定任何项目的草稿。
 */
export type InspirationListQuery = {
  scope?: InspirationScope;
  project?: string | null;
};

/**
 * 获取灵感列表（全局）。按 query 传入可选过滤。
 * @returns {Promise<InspirationListResponse>}
 */
export async function getInspirations(query?: InspirationListQuery): Promise<InspirationListResponse> {
  const params = new URLSearchParams();
  if (query?.scope) params.set('scope', query.scope);
  if (query?.project) params.set('project', query.project);
  const suffix = params.toString();
  const url = suffix ? `/api/inspirations?${suffix}` : '/api/inspirations';
  const response = await fetchWithAuth(url);
  const result = await response.json() as {
    success?: boolean;
    error?: string;
    inspirations?: InspirationEntry[];
    unread_count?: number;
    scope?: InspirationScope;
    project?: string | null;
  };
  if (!response.ok || result.success === false) throw new Error(result.error || '获取灵感失败');
  return {
    inspirations: result.inspirations || [],
    unreadCount: result.unread_count || 0,
    scope: result.scope,
    project: result.project ?? null,
  };
}

/**
 * 将灵感设为指定项目的当前灵感。
 * 一条灵感可以属于多个项目，但每个项目只保留一条当前灵感。
 */
export async function bindInspiration(
  entryId: string,
  projectName: string,
): Promise<ApiMutationResult> {
  const response = await fetchWithAuth(`/api/inspirations/${entryId}/bind`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, activate: true }),
  });
  const result = await response.json() as ApiMutationResult;
  if (!response.ok || result.success === false) throw new Error(result.error || '绑定灵感失败');
  return result;
}

/**
 * 从指定项目解绑灵感（解绑后仍存在，可能变成草稿或仍属于其他项目）。
 */
export async function unbindInspiration(entryId: string, projectName: string): Promise<ApiMutationResult> {
  const response = await fetchWithAuth(`/api/inspirations/${entryId}/unbind`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName }),
  });
  const result = await response.json() as ApiMutationResult;
  if (!response.ok || result.success === false) throw new Error(result.error || '解绑灵感失败');
  return result;
}

/**
 * 获取未读灵感数量
 */
export async function getInspirationUnreadCount(): Promise<number> {
  const response = await fetchWithAuth('/api/inspirations/unread-count');
  const result = await response.json() as { success?: boolean; error?: string; count?: number };
  if (!response.ok || result.success === false) throw new Error(result.error || '获取未读数失败');
  return result.count || 0;
}

/**
 * 创建新灵感
 * @param {string} source - 灵感原始文本
 * @param {string} content - 扩展内容（可选）
 * @param {Object} tags - 四维标签 {styles, genres, tones, worldviews}
 */
export async function createInspiration(source: string, content = '', tags: Partial<InspirationTags> | null = null): Promise<StoryMutationResult> {
  const response = await fetchWithAuth('/api/inspirations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source, content, tags }),
  });
  const result = await response.json() as StoryMutationResult;
  if (!response.ok || result.success === false) throw new Error(result.error || '创建灵感失败');
  return result;
}

/**
 * 更新灵感
 * @param {string} entryId - 灵感ID
 * @param {Object} updates - {content?, tags?, status?}
 */
export async function updateInspiration(entryId: string, updates: InspirationUpdatePayload): Promise<ApiMutationResult> {
  const response = await fetchWithAuth(`/api/inspirations/${entryId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  const result = await response.json() as ApiMutationResult;
  if (!response.ok || result.success === false) throw new Error(result.error || '更新灵感失败');
  return result;
}

/**
 * 标记灵感为已读
 */
export async function markInspirationRead(entryId: string): Promise<ApiMutationResult> {
  const response = await fetchWithAuth(`/api/inspirations/${entryId}/read`, {
    method: 'POST',
  });
  const result = await response.json() as ApiMutationResult;
  if (!response.ok || result.success === false) throw new Error(result.error || '标记已读失败');
  return result;
}

/**
 * 删除灵感
 */
export async function deleteInspiration(entryId: string): Promise<ApiMutationResult> {
  const response = await fetchWithAuth(`/api/inspirations/${entryId}`, {
    method: 'DELETE',
  });
  const result = await response.json() as ApiMutationResult;
  if (!response.ok || result.success === false) throw new Error(result.error || '删除失败');
  return result;
}


export async function getOutline(projectName: string): Promise<OutlineData> {
  const response = await fetchWithAuth(`/api/outline/${encodeURIComponent(projectName)}`);
  const result = await response.json() as { success?: boolean; error?: string; markup?: string };
  if (!response.ok || result.success === false) throw new Error(result.error || '获取大纲失败');
  if (!result.markup) return { title: '', nodes: [] } as OutlineData;
  // 解析 Markup 文本为结构化数据
  const { parseOutlineMarkup } = await import('../utils/markupSerializer');
  return parseOutlineMarkup(result.markup);
}

export async function saveOutline(projectName: string, outline: OutlineData, saveToHistory = false): Promise<ApiMutationResult> {
  // 序列化为 Markup 文本再传输
  const { serializeOutlineToMarkup } = await import('../utils/markupSerializer');
  const markup = serializeOutlineToMarkup(outline);
  const response = await fetchWithAuth(`/api/outline/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ markup, saveToHistory }),
  });
  const result = await response.json() as ApiMutationResult;
  if (!response.ok || result.success === false) throw new Error(result.error || '保存大纲失败');
  return result;
}

export async function exportOutlineToFiles(projectName: string, options: Record<string, unknown> = {}): Promise<OutlineExportResult> {
  const response = await fetchWithAuth(`/api/outline/${encodeURIComponent(projectName)}/export-to-files`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options),
  });
  const result = await response.json() as OutlineExportResult;
  if (response.status === 409) return { success: false, error: 'CONFLICT', existing: result.existing };
  if (!response.ok || result.success === false) throw new Error(result.error || '导出失败');
  return result;
}

// --- 文风与衔接 ---
export async function getStyleProfile(projectName: string | null | undefined, styleId: string | null | undefined): Promise<StyleProfileLookupResult> {
  let url = '/api/ai/style-profile?';
  if (styleId) url += `styleId=${encodeURIComponent(styleId)}`;
  else if (projectName) url += `projectName=${encodeURIComponent(projectName)}`;

  const response = await fetchWithAuth(url);
  if (!response.ok) return response.status === 404 ? null : { error: true };
  const result = await response.json() as { style_profile?: JsonObject | string };
  return result.style_profile ?? null;
}

export async function getStyleProfileMeta(projectName: string | null | undefined, styleId: string | null | undefined): Promise<StyleProfileMetaResult | null> {
  let url = '/api/ai/style-profile?';
  if (styleId) url += `styleId=${encodeURIComponent(styleId)}`;
  else if (projectName) url += `projectName=${encodeURIComponent(projectName)}`;

  const response = await fetchWithAuth(url);
  if (!response.ok) return null;
  const result = await response.json() as {
    style_profile?: JsonObject | string | null;
    style_id?: string | null;
    style_name?: string | null;
    project_binding?: StyleProfileMetaResult['project_binding'];
  };
  return {
    style_profile: result?.style_profile ?? null,
    style_id: result?.style_id || null,
    style_name: result?.style_name || null,
    project_binding: result?.project_binding || null,
  };
}

export async function generateBridge(projectName: string, prevScene: unknown, nextScene: unknown, options: {
  signal?: AbortSignal;
  pacing?: string;
  mood?: string;
  guidance?: string;
  characters?: unknown;
} = {}) {
  const result = await fetchSSEAndGetResult<{
    dialogues?: ArcDialogueNode[];
    transition?: ArcDialogueNode[];
  }>('/api/scriptwriter/compose/stream', {
    operation: 'bridge',
    mode: 'bridge',
    projectName,
    prevScene,
    nextScene,
    pacing: options.pacing || 'Normal',
    mood: options.mood,
    guidance: options.guidance,
    characters: options.characters
  }, options);
  return result.dialogues || result.transition || [];
}

// ==================== 项目级创作模式 ====================

export async function getProjectWorkspaceMode(projectName: string): Promise<'script' | 'novel'> {
  const resp = await fetchWithAuth(`/api/project/story-tags?projectName=${encodeURIComponent(projectName)}`);
  const data = await resp.json();
  return data?.tags?.workspace_mode === 'novel' ? 'novel' : 'script';
}
