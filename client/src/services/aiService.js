import { fetchWithAuth, fetchWithSWR, cache } from './apiClient';
import { consumeSSEReader, consumeTextReader, parseSSEEventPayload } from '@/utils/streamingRuntime';

/**
 * Helper to Convert error codes to friendly messages
 */
/**
 * Helper to Convert error codes to friendly messages
 */
/**
 * Helper to Convert error codes to friendly messages
 */
export function getFriendlyErrorMessage(errorMsg, statusCode) {
  const msg = errorMsg || '';

  // 后端已经统一返回了形如 "[错误: ...]" 的中文提示，优先显示
  if (msg.includes('[错误:')) {
    const match = msg.match(/\[错误: (.*?)\]/s);
    if (match) return match[1];
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

  // 兜底：处理非后端业务错误的 HTTP 状态码（比如 Nginx 或网络层面的拦截）
  if (statusCode === 401) {
    return '鉴权失败 (401)';
  }
  if (statusCode === 429) {
    return '请求过于频繁 (429)';
  }
  if (statusCode === 404) {
    return '请求资源不存在 (404)';
  }
  if (statusCode === 500) {
    // 如果 msg 有实际内容且不是标准的空/通用错误，则展示
    if (msg && msg !== '服务器内部错误 (500)') {
      return msg;
    }
    return '服务器内部错误，请稍后重试 (500)';
  }
  if (statusCode === 502 || statusCode === 504) {
    return '网关错误或超时 (502/504)';
  }

  return msg || '请求失败';
}

/**
 * 从 !response.ok 的响应中提取友好错误信息。
 * 优先解析 JSON body 中的 error/detail 字段，兜底用状态码映射。
 */
export async function extractResponseError(response, fallback = '请求失败') {
  let rawText = fallback;
  try { rawText = await response.text(); } catch { /* ignore */ }
  return getFriendlyErrorMessage(rawText, response.status);
}

/**
 * Helper to fetch a stream and accumulate the response into a single string/object.
 * Used to migrate blocking calls to streaming endpoints without changing the function signature.
 */
async function fetchStreamAndAccumulateJSON(url, body, options = {}) {
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
    return JSON.parse(cleanText);
  } catch (e) {
    // Check if the text contains an error message format used by the server
    if (fullText.includes('[错误:')) {
      // Extract the error message
      const match = fullText.match(/\[错误: (.*?)\]/);
      const errMsg = match ? match[1] : fullText;
      throw new Error(getFriendlyErrorMessage(errMsg));
    }
    // If it's not JSON and not an explicit error, it might be a partial response or just text.
    // However, the original functions expected objects (beat_sheet, outline, synopsis).
    throw new Error('无法解析服务器响应: ' + fullText.substring(0, 100));
  }
}

async function fetchStreamAndAccumulateText(url, body, options = {}) {
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

  return consumeTextReader(response.body.getReader(), {
    signal,
    onChunk,
  });
}

function parseBeatSheetMarkup(text) {
  const result = {
    global_emotional_arc: '',
    beats: []
  };

  if (!text || typeof text !== 'string') return result;

  const lines = text.split('\n');
  let currentBeat = null;

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

function parseOutlineMarkup(text) {
  const outlineData = {
    title: "未命名故事",
    summary: "",
    mainTheme: "",
    nodes: []
  };

  if (!text || typeof text !== 'string') return outlineData;

  const lines = text.split('\n');
  let currentChapter = null;
  let currentScene = null;

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

export async function fetchUserPlatformsAndModels(options = {}) {
  const { onData, force } = typeof options === 'function' ? { onData: options } : options;
  if (force) invalidatePlatformsModelsCache();
  return fetchWithSWR('/api/ai/user-platforms-models', 'platforms_models', onData);
}

export async function fetchUserSelection(usageKey, options = {}) {
  const { onData, force } = typeof options === 'function' ? { onData: options } : options;
  const key = usageKey || 'null';
  if (force) invalidateUserSelectionCache(usageKey);
  const url = usageKey ? `/api/ai/user-selection?usage_key=${encodeURIComponent(usageKey)}` : '/api/ai/user-selection';
  return fetchWithSWR(url, `selection_${key}`, onData);
}

export async function saveUserSelection(platformId, modelId, usageKey) {
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

export async function createUserUsageSlot(usageKey, usageLabel, platformId, modelId) {
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

export async function deleteUserUsageSlot(usageKey) {
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

export async function renameUserUsageSlot(usageKey, newUsageKey, newLabel) {
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
export async function createModel(platformId, modelName, displayName, extraBody = null, temperature = undefined) {
  const payload = {
    platform_id: platformId,
    model_name: modelName,
    display_name: displayName,
    extra_body: extraBody
  };
  if (temperature !== undefined) {
    payload.temperature = temperature;
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
export async function updateModel(modelId, displayName = null, extraBody = null, options = {}) {
  const payload = {
    id: modelId,
    display_name: displayName,
    extra_body: extraBody
  };
  if (options?.includeTemperature) {
    payload.temperature = options.temperature ?? null;
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
export async function deleteModel(modelId) {
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

export async function fetchPlatformsWithEmbeddings() {
  const response = await fetchWithAuth('/api/ai/platforms-with-embeddings');
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '获取 Embedding 平台失败');
  return result;
}

export async function fetchEmbeddingStatus() {
  const response = await fetchWithAuth('/api/ai/embedding-status');
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '获取 Embedding 状态失败');
  return result;
}

export async function fetchUserEmbeddingSelection() {
  const response = await fetchWithAuth('/api/ai/user-embedding');
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '获取 Embedding 选择失败');
  return result;
}

export async function saveUserEmbeddingSelection(platformId, modelId) {
  const response = await fetchWithAuth('/api/ai/user-embedding', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ platform_id: platformId, model_id: modelId })
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '保存 Embedding 选择失败');
  return result;
}

export async function createEmbedding(platformId, modelName, displayName, extraBody = null) {
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

export async function updateEmbedding(modelId, displayName = null, extraBody = null) {
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

export async function deleteEmbedding(modelId) {
  const response = await fetchWithAuth('/api/ai/embedding/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: modelId })
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '删除 Embedding 失败');
  return result;
}

export async function testEmbedding(platformId, modelName) {
  const response = await fetchWithAuth(`/api/ai/platform/${platformId}/test-embedding`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_name: modelName })
  });
  const result = await response.json();
  if (!response.ok) throw new Error(getFriendlyErrorMessage(result.detail || result.error || '测试 Embedding 失败', response.status));
  return result;
}

export async function analyzeStyleStream(projectName, file, styleName, onProgress, options = {}) {
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

  let finalProfile = null;
  await consumeSSEReader(response.body.getReader(), {
    signal: options.signal,
    onEvent: async (evt) => {
      const data = parseSSEEventPayload(evt?.data || '');
      if (data.raw && !data.step && !data.message && !data.style_profile) {
        throw new Error(`无法解析事件流数据: ${String(data.raw).slice(0, 200)}`);
      }

      if (onProgress) onProgress(data);

      if (data.step === 'error') {
        throw new Error(data.message || '文风分析失败');
      }

      if (data.style_profile) {
        finalProfile = data.style_profile;
      }
    },
  });

  return finalProfile;
}

export async function getStyles() {
  const response = await fetchWithAuth('/api/ai/styles');
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '获取风格列表失败');
  return result.styles;
}

export async function deleteStyle(styleName) {
  const response = await fetchWithAuth(`/api/ai/styles/${encodeURIComponent(styleName)}`, { method: 'DELETE' });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '删除风格失败');
  return result;
}

export async function applyStyle(styleName, projectName) {
  const response = await fetchWithAuth('/api/ai/style-apply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ styleName, projectName }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '应用风格失败');
  return result;
}

export async function refreshPlatformsAndModels() {
  invalidatePlatformsModelsCache();
  return fetchUserPlatformsAndModels({ force: true });
}

export async function refreshUserSelection(usageKey) {
  invalidateUserSelectionCache(usageKey);
  return fetchUserSelection(usageKey, { force: true });
}

// AI Agent 操作
export async function igniteMuse(projectName, inspiration, options = {}) {
  const { style, genres, tones, worldviews, lengthHint, inspirationId, signal } = options;
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

export async function fetchSynopsis(projectName) {
  const response = await fetchWithAuth(`/api/synopsis/${projectName}`);
  const result = await response.json();
  return result.synopsis;
}
export async function saveSynopsis(projectName, synopsis) {
  await fetchWithAuth('/api/synopsis', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, synopsis }),
  });
}

export async function generateSynopsis(projectName, logline, guidance, styleProfile = null, lengthHint = null, options = {}) {
  const synopsis = await fetchStreamAndAccumulateJSON('/api/ai/synopsis-stream', {
    projectName, logline, guidance, style_profile: styleProfile, lengthHint
  }, options);
  return synopsis;
}

export async function generateSynopsisStream(projectName, logline, guidance, styleProfile = null, lengthHint = null, options = {}) {
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

export async function fetchBeatSheet(projectName) {
  const response = await fetchWithAuth(`/api/beat-sheet/${projectName}`);
  const result = await response.json();
  return result.beat_sheet;
}

export async function saveBeatSheet(projectName, beatSheet) {
  await fetchWithAuth('/api/beat-sheet', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, beatSheet }),
  });
}

export async function generateBeatSheet(projectName, synopsis, guidance, styleProfile = null, lengthHint = null, options = {}) {
  const fullText = await fetchStreamAndAccumulateText('/api/ai/beat-sheet-stream', {
    projectName, synopsis, guidance, style_profile: styleProfile, lengthHint
  }, options);

  const cleanText = (fullText || '').trim().replace(/^```(?:json)?\\s*/i, '').replace(/```$/, '').trim();

  const beatSheet = parseBeatSheetMarkup(cleanText);
  if (beatSheet.beats.length > 0) return beatSheet;

  if (fullText.includes('[错误:')) {
    const match = fullText.match(/\[错误: (.*?)\]/);
    const errMsg = match ? match[1] : fullText;
    throw new Error(getFriendlyErrorMessage(errMsg));
  }

  throw new Error('节拍表生成结果格式无法解析，请检查模型输出格式');
}

export async function generateOutline(projectName, context, guidance, options = {}) {
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
    if (fullText.includes('[错误:')) {
      const match = fullText.match(/\\[错误: (.*?)\\]/);
      const errMsg = match ? match[1] : fullText;
      throw new Error(getFriendlyErrorMessage(errMsg));
    }
    throw new Error('大纲生成结果格式无法解析，请检查模型输出内容');
  }

  return outline;
}

// ==================== Admin: System Model Management ====================

/**
 * 管理员专用：添加系统模型
 */
export async function adminCreateSysModel(platformId, modelName, displayName, extraBody = null, temperature = undefined, sysCreditPricePerMillionTokens = undefined) {
  const payload = {
    platform_id: platformId,
    model_name: modelName,
    display_name: displayName,
    extra_body: extraBody
  };
  if (temperature !== undefined) {
    payload.temperature = temperature;
  }
  if (sysCreditPricePerMillionTokens !== undefined) {
    payload.sys_credit_price_per_million_tokens = sysCreditPricePerMillionTokens;
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
export async function adminUpdateSysModel(modelId, displayName = null, extraBody = null, options = {}) {
  const payload = {
    id: modelId,
    display_name: displayName,
    extra_body: extraBody
  };
  if (options?.includeTemperature) {
    payload.temperature = options.temperature ?? null;
  }
  if (options?.includeSysCreditPrice) {
    payload.sys_credit_price_per_million_tokens = options.sysCreditPricePerMillionTokens ?? null;
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
export async function adminDeleteSysModel(modelId) {
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
export async function adminCreateSysEmbedding(platformId, modelName, displayName, extraBody = null) {
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
export async function adminUpdateSysEmbedding(modelId, displayName = null, extraBody = null) {
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
export async function adminDeleteSysEmbedding(modelId) {
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

