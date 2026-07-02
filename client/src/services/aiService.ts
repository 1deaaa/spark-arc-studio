import { fetchWithAuth, fetchWithSWR, cache } from './apiClient';
import { consumeSSEReader, consumeTextReader, parseSSEEventPayload } from '@/utils/streamingRuntime';
import type {
  ApiId,
  AiPlatform,
  AiUserSelectionResponse,
  BeatSheetData,
  BeatSheetBeat,
  EmbeddingSelectionCurrent,
  EmbeddingSelectionResponse,
  EmbeddingStatusResponse,
  JsonObject,
  OutlineChapter,
  OutlineData,
  OutlineScene,
  StyleAnalyzeEvent,
  TestModelResponse,
} from './aiContracts';

type MutablePayload = Record<string, unknown>;
type StreamRequestOptions = {
  onChunk?: (chunk: string, fullText?: string) => void | Promise<void>;
  signal?: AbortSignal;
  [key: string]: unknown;
};

/**
 * 将错误信息转换为用户友好的提示文本。
 *
 * 职责边界：
 * - 后端 format_ai_error 已负责 LLM 端点错误码的四语友好提示（401/400/429/404/500/503/context_length/insufficient_quota/connection 等），
 *   前端只做透传，不做重复映射。
 * - 本函数仅处理**后端未触及的纯 HTTP 层兜底**：
 *   Nginx/网关拦截、网络断连等场景（后端进程根本没机会 format）。
 * - JSON body 中的 error/detail 字段由后端写入，同样直接透传。
 */
export function getFriendlyErrorMessage(errorMsg: unknown, statusCode?: number) {
  const msg = String(errorMsg || '');

  // 后端 format_ai_error 返回格式："友好提示 (原始信息: ...)" 或 "[错误: ...]"
  // 两种格式都包含后端已翻译的友好提示，直接透传
  if (msg.includes('[错误:') || msg.includes('原始信息:')) {
    return msg;
  }

  // 尝试解析 JSON body 中的 error / detail 字段（我们自己的服务器返回的结构化错误）
  try {
    const parsed = JSON.parse(msg);
    const serverMsg = parsed.error || parsed.detail || parsed.message;
    if (serverMsg && typeof serverMsg === 'string') {
      // 如果是 FastAPI 默认的 "Internal Server Error" 则继续走状态码映射
      if (serverMsg !== 'Internal Server Error') {
        return serverMsg;
      }
    }
  } catch { /* 不是 JSON，继续走下面的逻辑 */ }

  // 422：是我们服务器主动抛出的业务错误（ValueError），直接展示内容
  if (statusCode === 422) {
    return msg || '请求参数错误';
  }

  // 通用：错误消息中包含 "404" 且涉及模型/端点时，给出模型名/端点提示
  // 后端可能将远程 API 的 404 包装为 400 返回，此时 statusCode 不是 404 但消息中包含 404
  if (/\b404\b/.test(msg) && (msg.includes('model') || msg.includes('模型') || msg.includes('not found') || msg.includes('NOT_FOUND') || msg.includes('chat/completions'))) {
    return '模型不存在或端点不可达 (404) — 可能是模型名称与端点不匹配，或端点地址有误。请通过「探测模型」确认可用模型名称。';
  }

  // 纯 HTTP 层兜底：仅处理后端进程未触及的场景（Nginx 拦截、网关超时等）
  // 这些场景后端根本没机会调用 format_ai_error，所以前端需要自行映射
  if (statusCode === 401) {
    return '鉴权失败 (401) — 可能是会话过期，请刷新页面';
  }
  if (statusCode === 429) {
    return '请求过于频繁 (429) — 服务器限流，请稍后重试';
  }
  if (statusCode === 404) {
    // 远程 API 返回 404 通常是模型名拼写错误或端点地址不对
    if (msg.includes('model') || msg.includes('模型') || msg.includes('not found') || msg.includes('NOT_FOUND')) {
      return '模型不存在或端点不可达 (404) — 可能是模型名称与端点不匹配，或端点地址有误。请通过「探测模型」确认可用模型名称。';
    }
    return '请求资源不存在 (404) — 可能是模型名称拼写错误，或请求端点地址不正确。请通过「探测模型」确认可用模型名称。';
  }
  if (statusCode === 500) {
    if (msg && msg !== 'Internal Server Error') {
      return msg;
    }
    return '服务器内部错误，请稍后重试 (500)';
  }
  if (statusCode === 502 || statusCode === 504) {
    return '网关错误或超时 (502/504) — 后端服务可能未启动';
  }
  if (statusCode === 503) {
    return '服务不可用 (503) — 服务器过载或维护中';
  }

  return msg || '请求失败';
}

/**
 * 从 !response.ok 的响应中提取友好错误信息。
 * 优先解析 JSON body 中的 error/detail 字段，兜底用状态码映射。
 */
export async function extractResponseError(response: Response, fallback = '请求失败') {
  let rawText = fallback;
  try { rawText = await response.text(); } catch { /* ignore */ }
  return getFriendlyErrorMessage(rawText, response.status);
}

/**
 * Helper to fetch a stream and accumulate the response into a single string/object.
 * Used to migrate blocking calls to streaming endpoints without changing the function signature.
 */
async function fetchStreamAndAccumulateJSON(url: string, body: MutablePayload, options: StreamRequestOptions = {}) {
  const { onChunk, signal } = options;
  const response = await fetchWithAuth(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    throw new Error(await extractResponseError(response, '请求失败'));
  }

  if (!response.body) {
    throw new Error('浏览器不支持流式响应 (response.body 为空)');
  }

  const fullText = await consumeTextReader(response.body.getReader(), {
    signal,
    onChunk,
  });

  // Clean markdown code blocks if present (e.g. ```json ... ```)
  let cleanText = fullText.trim();
  if (cleanText.startsWith('```')) {
    const firstNewline = cleanText.indexOf('\n');
    if (firstNewline !== -1) {
      cleanText = cleanText.substring(firstNewline + 1);
    }
    if (cleanText.endsWith('```')) {
      cleanText = cleanText.substring(0, cleanText.length - 3);
    }
    cleanText = cleanText.trim();
  }

  // Try to parse the accumulated text as JSON
  try {
    return JSON.parse(cleanText) as JsonObject;
  } catch (e) {
    // 后端 format_ai_error 返回格式："友好提示 (原始信息: ...)" 或 "[错误: ...]"
    // 直接透传给 getFriendlyErrorMessage，无需正则拆解
    if (fullText.includes('[错误:') || fullText.includes('原始信息:')) {
      throw new Error(getFriendlyErrorMessage(fullText));
    }
    // If it's not JSON and not an explicit error, it might be a partial response or just text.
    // However, the original functions expected objects (beat_sheet, outline, synopsis).
    throw new Error('无法解析服务器响应: ' + fullText.substring(0, 100));
  }
}

async function fetchStreamAndAccumulateText(url: string, body: MutablePayload, options: StreamRequestOptions = {}) {
  const { onChunk, signal } = options;
  const response = await fetchWithAuth(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    throw new Error(await extractResponseError(response, '请求失败'));
  }

  if (!response.body) {
    throw new Error('浏览器不支持流式响应 (response.body 为空)');
  }

  return consumeTextReader(response.body.getReader(), {
    signal,
    onChunk,
  });
}

function parseBeatSheetMarkup(text: string): BeatSheetData {
  const result: BeatSheetData = {
    global_emotional_arc: '',
    beats: []
  };

  if (!text || typeof text !== 'string') return result;

  const lines = text.split('\n');
  let currentBeat: BeatSheetBeat | null = null;

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (!currentBeat && line.startsWith('@arc')) {
      const arc = line.replace('@arc', '').trim();
      if (arc) {
        result.global_emotional_arc += (result.global_emotional_arc ? '\n' : '') + arc;
      }
      continue;
    }

    const beatMatch = line.match(/^---\s*(?:beat|节拍)\s*(\d+)?(.*)$/i);
    if (beatMatch) {
      const beatId = beatMatch[1] ? Number(beatMatch[1]) : (result.beats.length + 1);
      currentBeat = {
        beat_id: Number.isFinite(beatId) ? beatId : (result.beats.length + 1),
        beat_type: '',
        narrative_action: '',
        emotional_goal: '',
        reader_experience: '',
        tension_level: ''
      };
      result.beats.push(currentBeat);
      continue;
    }

    if (currentBeat && line.startsWith('>')) {
      const parts = line.slice(1).split('|');
      for (const part of parts) {
        const kv = part.split(/:|：/, 2);
        if (kv.length !== 2) continue;
        const key = kv[0].trim().toLowerCase();
        const value = kv[1].trim();

        if (key.includes('类型') || key.includes('type')) {
          currentBeat.beat_type = value;
        } else if (key.includes('情感') || key.includes('emotion') || key.includes('心境')) {
          currentBeat.emotional_goal = value;
        } else if (key.includes('张力') || key.includes('tension')) {
          currentBeat.tension_level = value;
        }
      }
      continue;
    }

    if (line && currentBeat) {
      currentBeat.narrative_action += (currentBeat.narrative_action ? '\n' : '') + line;
    } else if (line && !currentBeat) {
      result.global_emotional_arc += (result.global_emotional_arc ? '\n' : '') + line;
    }
  }

  return result;
}

function parseOutlineMarkup(text: string): OutlineData {
  const outlineData: OutlineData = {
    title: "未命名故事",
    summary: "",
    mainTheme: "",
    nodes: [],
    totalChapters: 0,
    estimatedScenes: 0,
  };

  if (!text || typeof text !== 'string') return outlineData;

  const lines = text.split('\n');
  let currentChapter: OutlineChapter | null = null;
  let currentScene: OutlineScene | null = null;

  let idCounter = 0;
  const generateId = (prefix) => `${prefix}_${Date.now()}_${++idCounter}`;

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue;

    // 全局 Meta 标签，例如 @title 故事大标题
    if (!currentChapter && !currentScene && line.startsWith('@')) {
      const match = line.match(/^@(\w+)\s+(.+)$/);
      if (match) {
        const key = match[1].trim();
        const val = match[2].trim();
        if (key === 'title') outlineData.title = val;
        else if (key === 'summary') outlineData.summary = val;
        else if (key === 'theme') outlineData.mainTheme = val;
      }
      continue;
    }

    // 章节处理 (##)
    const chapterMatch = line.match(/^##\s+(?:Chapter\s*\d*:?\s*)?(.+)$/i);
    if (chapterMatch) {
      const title = chapterMatch[1].trim();
      currentChapter = {
        id: generateId("chap"),
        name: title,
        title: title, // 兼容前端 title 字段
        type: "chapter",
        chapter: outlineData.nodes.length + 1,
        description: "",
        children: []
      };
      outlineData.nodes.push(currentChapter);
      currentScene = null;
      continue;
    }

    // 场景处理 (###)
    const sceneMatch = line.match(/^###\s+(?!Scene)(.+)$|^###\s+(?:Scene\s*\d*:?\s*)?(.+)$/i);
    if (sceneMatch) {
      const title = (sceneMatch[1] || sceneMatch[2]).trim();

      if (!currentChapter) {
        currentChapter = {
          id: generateId("chap"),
          name: "未归类章节",
          title: "未归类章节",
          type: "chapter",
          chapter: outlineData.nodes.length + 1,
          description: "",
          children: []
        };
        outlineData.nodes.push(currentChapter);
      }

      currentScene = {
        id: generateId("scene"),
        name: title,
        title: title,
        type: "scene",
        description: "",
        mood: "",
        tension: "Medium",
        characters: [],
        mapped_beats: []
      };
      currentChapter.children.push(currentScene);
      continue;
    }

    // 场景元数据层 (>)
    if (currentScene && line.startsWith('>')) {
      const metaStr = line.slice(1).trim();
      const parts = metaStr.split('|');
      for (const part of parts) {
        if (part.includes(':') || part.includes('：')) {
          const kv = part.split(/:|：/, 2);
          if (kv.length !== 2) continue;
          const k = kv[0].trim().toLowerCase();
          const v = kv[1].trim();

          if (k.includes('情绪') || k.includes('mood')) currentScene.mood = v;
          else if (k.includes('张力') || k.includes('tension')) {
            if (v.toLowerCase().includes('low') || v.includes('低')) currentScene.tension = 'Low';
            else if (v.toLowerCase().includes('high') || v.includes('高')) currentScene.tension = 'High';
            else currentScene.tension = 'Medium';
          }
          else if (k.includes('登场') || k.includes('角色') || k.includes('character')) {
            currentScene.characters = v.split(/[,，、]+/).map(s => s.trim()).filter(Boolean);
          }
          else if (k.includes('节拍') || k.includes('beat')) {
            currentScene.mapped_beats = v.split(/[,，、]+/)
              .map(s => parseInt(s.replace(/\D/g, '')))
              .filter(n => !isNaN(n));
          }
        }
      }
      continue;
    }

    // 散文推演长文本归入描述
    if (line) {
      if (currentScene) {
        currentScene.description += (currentScene.description ? "\n" : "") + line;
      } else if (currentChapter) {
        currentChapter.description += (currentChapter.description ? "\n" : "") + line;
      } else {
        outlineData.summary += (outlineData.summary ? "\n" : "") + line;
      }
    }
  }

  // 计算统记信息
  outlineData.totalChapters = outlineData.nodes.length;
  outlineData.estimatedScenes = outlineData.nodes.reduce((acc, c) => acc + (c.children?.length || 0), 0);

  return outlineData;
}

export const invalidatePlatformsModelsCache = () => cache.clear('platforms_models');

export const invalidateUserSelectionCache = (usageKey) => {
  const key = usageKey || 'null';
  cache.clear(`selection_${key}`);
  if (!usageKey) {
    cache.clear('selection_main');
  }
};

export async function fetchUserPlatformsAndModels(options: ((data: AiPlatform[]) => void) | { onData?: (data: AiPlatform[]) => void; force?: boolean } = {}) {
  const { onData, force } = typeof options === 'function' ? { onData: options } : options;
  if (force) invalidatePlatformsModelsCache();
  return fetchWithSWR('/api/ai/user-platforms-models', 'platforms_models', onData);
}

export async function fetchUserSelection(usageKey: string | null | undefined, options: ((data: AiUserSelectionResponse) => void) | { onData?: (data: AiUserSelectionResponse) => void; force?: boolean } = {}) {
  const { onData, force } = typeof options === 'function' ? { onData: options } : options;
  const key = usageKey || 'null';
  if (force) invalidateUserSelectionCache(usageKey);
  const url = usageKey ? `/api/ai/user-selection?usage_key=${encodeURIComponent(usageKey)}` : '/api/ai/user-selection';
  return fetchWithSWR(url, `selection_${key}`, onData);
}

export async function saveUserSelection(platformId: ApiId, modelId: ApiId, usageKey: string) {
  const response = await fetchWithAuth('/api/ai/user-selection', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ platform_id: platformId, model_id: modelId, usage_key: usageKey }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '保存失败');
  invalidateUserSelectionCache(usageKey);
  return result;
}

export async function createUserUsageSlot(usageKey: string, usageLabel: string, platformId: ApiId, modelId: ApiId) {
  const response = await fetchWithAuth('/api/ai/user-selection/usage', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ usage_key: usageKey, usage_label: usageLabel, platform_id: platformId, model_id: modelId }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '创建用途失败');
  invalidateUserSelectionCache(null);
  invalidatePlatformsModelsCache();
  return result;
}

export async function deleteUserUsageSlot(usageKey: string) {
  const response = await fetchWithAuth('/api/ai/user-selection/usage', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ usage_key: usageKey }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '删除失败');
  invalidateUserSelectionCache(null);
  return result;
}

export async function renameUserUsageSlot(usageKey: string, newUsageKey: string | null, newLabel: string | null) {
  const response = await fetchWithAuth('/api/ai/user-selection/usage', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ usage_key: usageKey, new_usage_key: newUsageKey, new_usage_label: newLabel }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '编辑用途失败');
  invalidateUserSelectionCache(null);
  invalidatePlatformsModelsCache();
  return result;
}

// ==================== Model Management ====================

/**
 * 添加自定义模型
 * @param {number} platformId - 平台 ID
 * @param {string} modelName - 模型标识 (API 使用的名称)
 * @param {string} displayName - 显示名称
 * @param {string|null} extraBody - extra_body JSON 字符串 (可选)
 */
export async function createModel(platformId: ApiId, modelName: string, displayName: string, extraBody: string | null = null, temperature: number | undefined = undefined, maxContextTokens?: number | null, maxOutputTokens?: number | null, capabilities?: string[], imageGenerationAdapter?: string | null) {
  const payload: MutablePayload = {
    platform_id: platformId,
    model_name: modelName,
    display_name: displayName,
    extra_body: extraBody
  };
  if (temperature !== undefined) {
    payload.temperature = temperature;
  }
  if (maxContextTokens != null) {
    payload.max_context_tokens = maxContextTokens;
  }
  if (maxOutputTokens != null) {
    payload.max_output_tokens = maxOutputTokens;
  }
  if (capabilities && capabilities.length > 0) {
    payload.capabilities = capabilities;
  }
  if (imageGenerationAdapter) {
    payload.image_generation_adapter = imageGenerationAdapter;
  }
  const response = await fetchWithAuth('/api/ai/model', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '添加模型失败');
  invalidatePlatformsModelsCache();
  return result;
}

/**
 * 更新模型 (显示名称和 extra_body)
 * @param {number} modelId - 模型 ID
 * @param {string|null} displayName - 新的显示名称 (可选)
 * @param {string|null} extraBody - extra_body JSON 字符串 (可选)
 */
export async function updateModel(modelId: ApiId, displayName: string | null = null, extraBody: string | null = null, options: { includeTemperature?: boolean; temperature?: number | null; includeMaxTokens?: boolean; maxContextTokens?: number | null; maxOutputTokens?: number | null; includeCapabilities?: boolean; capabilities?: string[]; includeImageGenerationAdapter?: boolean; imageGenerationAdapter?: string | null } = {}) {
  const payload: MutablePayload = {
    id: modelId,
    display_name: displayName,
    extra_body: extraBody
  };
  if (options?.includeTemperature) {
    payload.temperature = options.temperature ?? null;
  }
  if (options?.includeMaxTokens) {
    payload.max_context_tokens = options.maxContextTokens ?? null;
    payload.max_output_tokens = options.maxOutputTokens ?? null;
  }
  if (options?.includeCapabilities) {
    payload.capabilities = options.capabilities ?? [];
  }
  if (options?.includeImageGenerationAdapter) {
    payload.image_generation_adapter = options.imageGenerationAdapter ?? null;
  }
  const response = await fetchWithAuth('/api/ai/model', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '更新模型失败');
  invalidatePlatformsModelsCache();
  return result;
}

/**
 * 删除模型
 * @param {number} modelId - 模型 ID
 */
export async function deleteModel(modelId: ApiId) {
  const response = await fetchWithAuth('/api/ai/model/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: modelId })
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '删除模型失败');
  invalidatePlatformsModelsCache();
  return result;
}

// ==================== Embedding Management ====================

export async function fetchPlatformsWithEmbeddings(): Promise<AiPlatform[]> {
  const response = await fetchWithAuth('/api/ai/platforms-with-embeddings');
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '获取 Embedding 平台失败');
  return result;
}

export async function fetchEmbeddingStatus(): Promise<EmbeddingStatusResponse> {
  const response = await fetchWithAuth('/api/ai/embedding-status');
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '获取 Embedding 状态失败');
  return result;
}

export async function fetchUserEmbeddingSelection(): Promise<EmbeddingSelectionResponse> {
  const response = await fetchWithAuth('/api/ai/user-embedding');
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '获取 Embedding 选择失败');
  return result;
}

export async function saveUserEmbeddingSelection(platformId: ApiId, modelId: ApiId): Promise<EmbeddingSelectionCurrent> {
  const response = await fetchWithAuth('/api/ai/user-embedding', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ platform_id: platformId, model_id: modelId })
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '保存 Embedding 选择失败');
  return result;
}

export async function createEmbedding(platformId: ApiId, modelName: string, displayName: string, extraBody: string | null = null) {
  const response = await fetchWithAuth('/api/ai/embedding', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      platform_id: platformId,
      model_name: modelName,
      display_name: displayName,
      extra_body: extraBody
    })
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '添加 Embedding 失败');
  return result;
}

export async function updateEmbedding(modelId: ApiId, displayName: string | null = null, extraBody: string | null = null) {
  const response = await fetchWithAuth('/api/ai/embedding', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      id: modelId,
      display_name: displayName,
      extra_body: extraBody
    })
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '更新 Embedding 失败');
  return result;
}

export async function deleteEmbedding(modelId: ApiId) {
  const response = await fetchWithAuth('/api/ai/embedding/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: modelId })
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '删除 Embedding 失败');
  return result;
}

export async function testEmbedding(platformId: ApiId, modelName: string): Promise<TestModelResponse> {
  const response = await fetchWithAuth(`/api/ai/platform/${platformId}/test-embedding`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_name: modelName })
  });
  const result = await response.json();
  if (!response.ok) throw new Error(getFriendlyErrorMessage(result.detail || result.error || '测试 Embedding 失败', response.status));
  return result;
}

export async function analyzeStyleStream(
  projectName: string | null,
  file: Blob | File,
  styleName: string | null,
  onProgress: ((event: StyleAnalyzeEvent) => void) | null,
  options: StreamRequestOptions = {}
) {
  const formData = new FormData();
  formData.append('file', file);
  if (projectName) formData.append('projectName', projectName);
  if (styleName) formData.append('styleName', styleName);

  const response = await fetchWithAuth('/api/ai/style-analyze-stream', {
    method: 'POST',
    body: formData,
    signal: options.signal,
  });

  const contentType = (response.headers.get('content-type') || '').toLowerCase();

  if (!response.ok) {
    let errorMsg = '文风分析失败';
    try {
      const result = await response.json();
      errorMsg = result.error || errorMsg;
    } catch (e) { }
    throw new Error(getFriendlyErrorMessage(errorMsg, response.status));
  }

  // SSE is required here; if the backend/proxy returns HTML/JSON, surface it clearly.
  if (!contentType.includes('text/event-stream')) {
    let details = '';
    try {
      details = await response.text();
    } catch (e) { }
    throw new Error(`服务未返回事件流 (content-type: ${contentType || 'unknown'})${details ? `: ${details.slice(0, 200)}` : ''}`);
  }

  if (!response.body) {
    throw new Error('浏览器不支持流式响应 (response.body 为空)');
  }

  let finalProfile: JsonObject | string | null = null;
  await consumeSSEReader(response.body.getReader(), {
    signal: options.signal,
    onEvent: async (evt) => {
      const data = parseSSEEventPayload(evt?.data || '') as StyleAnalyzeEvent;
      if (data.raw && !data.step && !data.message && !data.style_profile) {
        throw new Error(`无法解析事件流数据: ${String(data.raw).slice(0, 200)}`);
      }

      if (onProgress) onProgress(data);

      if (data.step === 'error') {
        throw new Error(String(data.message || '文风分析失败'));
      }

      if (data.style_profile) {
        finalProfile = data.style_profile;
      }
    },
  });

  return finalProfile;
}

export async function getStyles(): Promise<{ styles: JsonObject[]; default_style_name: string }> {
  const response = await fetchWithAuth('/api/ai/styles');
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '获取风格列表失败');
  return { styles: result.styles, default_style_name: result.default_style_name || '' };
}

export async function deleteStyle(styleName: string) {
  const response = await fetchWithAuth(`/api/ai/styles/${encodeURIComponent(styleName)}`, { method: 'DELETE' });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '删除风格失败');
  return result;
}

export async function exportStyleProfile(styleName: string): Promise<void> {
  const response = await fetchWithAuth(`/api/ai/styles/${encodeURIComponent(styleName)}/export`);
  if (!response.ok) {
    const result = await response.json().catch(() => ({ error: '导出风格失败' }));
    throw new Error(result.error || result.message || '导出风格失败');
  }

  const disposition = response.headers.get('Content-Disposition') || '';
  let filename = `${styleName}.sparkarc-style.json`;
  const utf8Match = disposition.match(/filename\*=UTF-8''(.+?)(?:;|$)/);
  if (utf8Match) {
    filename = decodeURIComponent(utf8Match[1]);
  } else {
    const match = disposition.match(/filename="?([^"]+)"?/);
    if (match) filename = match[1];
  }

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

export async function importStyleProfile(file: File, styleName?: string): Promise<{ style_name: string }> {
  const formData = new FormData();
  formData.append('file', file);
  if (styleName) formData.append('styleName', styleName);

  const response = await fetchWithAuth('/api/ai/styles/import', {
    method: 'POST',
    body: formData,
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || result.message || '导入风格失败');
  return { style_name: result.style_name || '' };
}

export async function applyStyle(styleName: string, projectName: string) {
  const response = await fetchWithAuth('/api/ai/style-apply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ styleName, projectName }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '应用风格失败');
  return result;
}

export async function getDefaultStyle(): Promise<string> {
  const response = await fetchWithAuth('/api/ai/style-default');
  const result = await response.json();
  if (!response.ok || result.success === false) return '';
  return result.default_style_name || '';
}

export async function setDefaultStyle(styleName: string | null): Promise<string> {
  const response = await fetchWithAuth('/api/ai/style-set-default', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ styleName: styleName || '' }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '设置默认风格失败');
  return result.default_style_name || '';
}

export async function refreshPlatformsAndModels() {
  invalidatePlatformsModelsCache();
  return fetchUserPlatformsAndModels({ force: true });
}

export async function refreshUserSelection(usageKey: string | null | undefined) {
  invalidateUserSelectionCache(usageKey);
  return fetchUserSelection(usageKey, { force: true });
}

// AI Agent 操作
export async function igniteMuse(projectName, inspiration, options: {
  style?: unknown;
  genres?: unknown;
  tones?: unknown;
  worldviews?: unknown;
  pov?: unknown;
  lengthHint?: unknown;
  inspirationId?: unknown;
  signal?: AbortSignal;
} = {}) {
  const { style, genres, tones, worldviews, pov, lengthHint, inspirationId, signal } = options;
  const response = await fetchWithAuth('/api/ai/muse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      projectName,
      inspiration,
      style: style || null,
      genres: genres || null,
      tones: tones || null,
      worldviews: worldviews || null,
      pov: pov || null,
      lengthHint: lengthHint || null,
      inspirationId: inspirationId || null  // 关联的灵感ID，用于更新已有灵感的 content
    }),
    signal,
  });
  if (!response.ok) {
    throw new Error(await extractResponseError(response, '灵感服务响应失败'));
  }
  if (!response.body) {
    throw new Error('灵感流无响应体');
  }
  return response.body.getReader();
}

export async function fetchSynopsis(projectName: string): Promise<string> {
  const response = await fetchWithAuth(`/api/synopsis/${projectName}`);
  const result = await response.json() as { success?: boolean; markup?: string };
  return result.markup ?? '';
}
export async function saveSynopsis(projectName: string, markup: string) {
  await fetchWithAuth('/api/synopsis', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, markup }),
  });
}

export async function generateSynopsis(projectName: string, logline: string, guidance: string, styleProfile: unknown = null, lengthHint: unknown = null, options: StreamRequestOptions = {}) {
  const fullText = await fetchStreamAndAccumulateText('/api/ai/synopsis-stream', {
    projectName, logline, guidance, style_profile: styleProfile, lengthHint
  }, options);
  // 后端现在直接返回 Markup 文本
  return fullText || '';
}

export async function generateSynopsisStream(projectName: string, logline: string, guidance: string, styleProfile: unknown = null, lengthHint: unknown = null, options: StreamRequestOptions = {}) {
  const response = await fetchWithAuth('/api/ai/synopsis-stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, logline, guidance, style_profile: styleProfile, lengthHint }),
    signal: options.signal,
  });

  if (!response.ok) {
    throw new Error(await extractResponseError(response, '概要流响应失败'));
  }

  if (!response.body) {
    throw new Error('梗概流无响应体');
  }

  return response.body.getReader();
}

export async function fetchBeatSheet(projectName: string): Promise<string> {
  const response = await fetchWithAuth(`/api/beat-sheet/${projectName}`);
  const result = await response.json() as { success?: boolean; markup?: string };
  return result.markup ?? '';
}
export async function saveBeatSheet(projectName: string, markup: string) {
  await fetchWithAuth('/api/beat-sheet', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, markup }),
  });
}

export async function generateBeatSheet(projectName: string, synopsis: string, guidance: string, styleProfile: unknown = null, lengthHint: unknown = null, options: StreamRequestOptions = {}) {
  const fullText = await fetchStreamAndAccumulateText('/api/ai/beat-sheet-stream', {
    projectName, synopsis, guidance, style_profile: styleProfile, lengthHint
  }, options);

  const cleanText = (fullText || '').trim().replace(/^```(?:json)?\\s*/i, '').replace(/```$/, '').trim();

  const beatSheet = parseBeatSheetMarkup(cleanText);
  if (beatSheet.beats.length > 0) return beatSheet;

  if (fullText.includes('[错误:') || fullText.includes('原始信息:')) {
    throw new Error(getFriendlyErrorMessage(fullText));
  }

  throw new Error('节奏表生成结果格式无法解析，请检查模型输出格式');
}

export async function generateOutline(projectName: string, context: string, guidance: string, options: StreamRequestOptions & {
  beatSheet?: unknown;
  chapterCount?: number | string;
  sceneCountPerChapter?: number | string;
  saveToProject?: boolean;
  saveToHistory?: boolean;
  styleProfile?: unknown;
} = {}) {
  const fullText = await fetchStreamAndAccumulateText('/api/ai/outline-stream', {
    projectName,
    context,
    guidance,
    beatSheet: options.beatSheet,
    chapterCount: options.chapterCount ?? 5,
    sceneCountPerChapter: options.sceneCountPerChapter ?? 3,
    saveToProject: options.saveToProject ?? true,
    saveToHistory: options.saveToHistory ?? true,
    style_profile: options.styleProfile || null,
  }, options);

  const cleanText = (fullText || '').trim().replace(/^```(?:markdown|json)?\\s*/i, '').replace(/```$/, '').trim();
  const outline = parseOutlineMarkup(cleanText);

  if (outline.nodes.length === 0) {
    if (fullText.includes('[错误:') || fullText.includes('原始信息:')) {
      throw new Error(getFriendlyErrorMessage(fullText));
    }
    throw new Error('大纲生成结果格式无法解析，请检查模型输出内容');
  }

  return outline;
}

// ==================== Admin: System Model Management ====================

/**
 * 管理员专用：添加系统模型
 */
export async function adminCreateSysModel(
  platformId: ApiId,
  modelName: string,
  displayName: string,
  extraBody: string | null = null,
  temperature: number | undefined = undefined,
  inputPricePerMillion: number | undefined = undefined,
  cachedInputPricePerMillion: number | undefined = undefined,
  outputPricePerMillion: number | undefined = undefined,
  maxContextTokens?: number | null,
  maxOutputTokens?: number | null,
  capabilities?: string[],
  imageGenerationAdapter?: string | null,
) {
  const payload: MutablePayload = {
    platform_id: platformId,
    model_name: modelName,
    display_name: displayName,
    extra_body: extraBody
  };
  if (temperature !== undefined) {
    payload.temperature = temperature;
  }
  if (inputPricePerMillion !== undefined) {
    payload.sys_credit_input_price_per_million = inputPricePerMillion;
  }
  if (cachedInputPricePerMillion !== undefined) {
    payload.sys_credit_cached_input_price_per_million = cachedInputPricePerMillion;
  }
  if (outputPricePerMillion !== undefined) {
    payload.sys_credit_output_price_per_million = outputPricePerMillion;
  }
  if (maxContextTokens != null) {
    payload.max_context_tokens = maxContextTokens;
  }
  if (maxOutputTokens != null) {
    payload.max_output_tokens = maxOutputTokens;
  }
  if (capabilities && capabilities.length > 0) {
    payload.capabilities = capabilities;
  }
  if (imageGenerationAdapter) {
    payload.image_generation_adapter = imageGenerationAdapter;
  }
  const response = await fetchWithAuth('/api/ai/admin/sys-model', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '添加系统模型失败');
  invalidatePlatformsModelsCache();
  return result;
}

/**
 * 管理员专用：更新系统模型
 */
export async function adminUpdateSysModel(modelId: ApiId, displayName: string | null = null, extraBody: string | null = null, options: {
  includeTemperature?: boolean;
  temperature?: number | null;
  includeSysCreditPrices?: boolean;
  inputPricePerMillion?: number | null;
  cachedInputPricePerMillion?: number | null;
  outputPricePerMillion?: number | null;
  includeMaxTokens?: boolean;
  maxContextTokens?: number | null;
  maxOutputTokens?: number | null;
  includeCapabilities?: boolean;
  capabilities?: string[];
  includeImageGenerationAdapter?: boolean;
  imageGenerationAdapter?: string | null;
} = {}) {
  const payload: MutablePayload = {
    id: modelId,
    display_name: displayName,
    extra_body: extraBody
  };
  if (options?.includeTemperature) {
    payload.temperature = options.temperature ?? null;
  }
  if (options?.includeSysCreditPrices) {
    payload.sys_credit_input_price_per_million = options.inputPricePerMillion ?? null;
    payload.sys_credit_cached_input_price_per_million = options.cachedInputPricePerMillion ?? null;
    payload.sys_credit_output_price_per_million = options.outputPricePerMillion ?? null;
  }
  if (options?.includeMaxTokens) {
    payload.max_context_tokens = options.maxContextTokens ?? null;
    payload.max_output_tokens = options.maxOutputTokens ?? null;
  }
  if (options?.includeCapabilities) {
    payload.capabilities = options.capabilities ?? [];
  }
  if (options?.includeImageGenerationAdapter) {
    payload.image_generation_adapter = options.imageGenerationAdapter ?? null;
  }
  const response = await fetchWithAuth('/api/ai/admin/sys-model', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '更新系统模型失败');
  invalidatePlatformsModelsCache();
  return result;
}

/**
 * 管理员专用：删除系统模型
 */
export async function adminDeleteSysModel(modelId: ApiId) {
  const response = await fetchWithAuth('/api/ai/admin/sys-model/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: modelId })
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '删除系统模型失败');
  invalidatePlatformsModelsCache();
  return result;
}

/**
 * 管理员专用：添加系统 Embedding
 */
export async function adminCreateSysEmbedding(platformId: ApiId, modelName: string, displayName: string, extraBody: string | null = null) {
  const response = await fetchWithAuth('/api/ai/admin/sys-embedding', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      platform_id: platformId,
      model_name: modelName,
      display_name: displayName,
      extra_body: extraBody
    }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '添加系统 Embedding 失败');
  invalidatePlatformsModelsCache();
  return result;
}

/**
 * 管理员专用：更新系统 Embedding
 */
export async function adminUpdateSysEmbedding(modelId: ApiId, displayName: string | null = null, extraBody: string | null = null) {
  const response = await fetchWithAuth('/api/ai/admin/sys-embedding', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      id: modelId,
      display_name: displayName,
      extra_body: extraBody
    }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '更新系统 Embedding 失败');
  invalidatePlatformsModelsCache();
  return result;
}

/**
 * 管理员专用：删除系统 Embedding
 */
export async function adminDeleteSysEmbedding(modelId: ApiId) {
  const response = await fetchWithAuth('/api/ai/admin/sys-embedding/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: modelId })
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '删除系统 Embedding 失败');
  invalidatePlatformsModelsCache();
  return result;
}

