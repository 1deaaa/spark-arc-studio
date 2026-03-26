import { fetchWithAuth } from './apiClient';
import { consumeSSEReader, parseSSEEventPayload } from '@/utils/streamingRuntime';
import type {
  ApiMutationResult,
  InspirationEntry,
  InspirationListResponse,
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
  content?: string;
  tags?: InspirationTags;
  status?: InspirationStatus;
};

type OutlineExportResult = StoryMutationResult & {
  existing?: string[];
};

type StyleProfileLookupResult = JsonObject | { error: true } | null;

type StyleProfileMetaResult = {
  style_profile: JsonObject | null;
  style_name: string | null;
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

// --- 角色、蓝图、绑定、注册表 ---

/**
 * 获取角色列表
 * @param {string} projectName - 项目名称
 * @param {boolean} includeContent - 是否包含角色设定内容（编辑器用）
 * @returns {Promise<Array>} 角色数组 [{id, name, desc, content?}]
 */
export async function fetchCharacters(projectName: string, includeContent: true): Promise<StoryCharacterDetail[]>;
export async function fetchCharacters(projectName: string, includeContent?: false): Promise<StoryCharacter[]>;
export async function fetchCharacters(projectName: string, includeContent = false): Promise<StoryCharacter[] | StoryCharacterDetail[]> {
  if (!projectName) return [];
  let url = `/api/characters?projectName=${encodeURIComponent(projectName)}`;
  if (includeContent) url += '&includeContent=true';

  const response = await fetchWithAuth(url);
  if (!response.ok) return [];

  const result = await response.json() as StoryCharacter[] | StoryCharacterDetail[];
  // 后端直接返回数组
  return Array.isArray(result) ? result : [];
}

/**
 * 创建新角色
 */
export async function createCharacter(projectName: string, name: string): Promise<StoryMutationResult> {
  const response = await fetchWithAuth('/api/characters', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, name }),
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
  const result = await response.json() as { success?: boolean; error?: string; outline?: OutlineData };
  if (!response.ok || result.success === false) throw new Error(result.error || '恢复失败');
  return result.outline || { title: '', nodes: [] };
}

// --- 全局灵感系统 (用户级别，非项目级别) ---

/**
 * 获取所有灵感（全局）
 * @returns {Promise<{inspirations: Array, unread_count: number}>}
 */
export async function getInspirations(): Promise<InspirationListResponse> {
  const response = await fetchWithAuth('/api/inspirations');
  const result = await response.json() as { success?: boolean; error?: string; inspirations?: InspirationEntry[]; unread_count?: number };
  if (!response.ok || result.success === false) throw new Error(result.error || '获取灵感失败');
  return {
    inspirations: result.inspirations || [],
    unreadCount: result.unread_count || 0,
  };
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
  const result = await response.json() as { success?: boolean; error?: string; outline?: OutlineData };
  if (!response.ok || result.success === false) throw new Error(result.error || '获取大纲失败');
  return result.outline || { title: '', nodes: [] };
}

export async function saveOutline(projectName: string, outline: OutlineData, saveToHistory = false): Promise<ApiMutationResult> {
  const response = await fetchWithAuth(`/api/outline/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ outline, saveToHistory }),
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
export async function getStyleProfile(projectName: string | null | undefined, styleName: string | null | undefined): Promise<StyleProfileLookupResult> {
  let url = '/api/ai/style-profile?';
  if (styleName) url += `styleName=${encodeURIComponent(styleName)}`;
  else if (projectName) url += `projectName=${encodeURIComponent(projectName)}`;

  const response = await fetchWithAuth(url);
  if (!response.ok) return response.status === 404 ? null : { error: true };
  const result = await response.json() as { style_profile?: JsonObject };
  return result.style_profile ?? null;
}

export async function getStyleProfileMeta(projectName: string | null | undefined, styleName: string | null | undefined): Promise<StyleProfileMetaResult | null> {
  let url = '/api/ai/style-profile?';
  if (styleName) url += `styleName=${encodeURIComponent(styleName)}`;
  else if (projectName) url += `projectName=${encodeURIComponent(projectName)}`;

  const response = await fetchWithAuth(url);
  if (!response.ok) return null;
  const result = await response.json() as { style_profile?: JsonObject | null; style_name?: string | null };
  return {
    style_profile: result?.style_profile || null,
    style_name: result?.style_name || null,
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
