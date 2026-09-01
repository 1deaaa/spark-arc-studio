import { fetchWithAuth } from './apiClient';
import { i18n } from '@/i18n';

export type PresentationAsset = {
  id: string;
  type: 'background' | 'character_sprite' | 'style_reference' | 'scene_reference' | 'scene_illustration' | string;
  targets?: string[];
  source?: string;
  title?: string;
  path?: string;
  url?: string;
  mimeType?: string;
  prompt?: string;
  characterId?: string;
  expression?: string;
  position?: string;
  sceneName?: string;
  nodeId?: string;
  createdAt?: string;
  library?: boolean;
  matting?: {
    status?: string;
    mode?: string;
    sourceAssetId?: string;
  };
};

export type PresentationManifest = {
  version?: number;
  targets?: string[];
  assets?: Record<string, PresentationAsset>;
  runtime?: Record<string, unknown>;
};

export type PresentationPayload = {
  manifest?: PresentationManifest;
  assetBaseUrl?: string;
  settings?: PresentationSettings;
};

export type VisualIllustrationSettings = {
  enabled: boolean;
  effectiveEnabled?: boolean;
  max_per_scene?: number;
  min_node_gap?: number;
  require_character_sprite?: boolean;
  sprite_chroma_key?: string;
  sprite_matting?: 'chroma_key' | 'none' | string;
};

export type VisualStyleSettings = {
  seed_prompt: string;
  reference_asset_ids: string[];
};

export type PresentationSettings = {
  visualIllustration?: VisualIllustrationSettings;
  visualStyle?: VisualStyleSettings;
  readiness?: {
    characterSpritesReady?: boolean;
    missingCharacterSprites?: Array<{ id: string; name: string }>;
  };
};

export type PresentationUploadResult = {
  success?: boolean;
  asset: PresentationAsset;
  manifest?: PresentationManifest;
};

export type PresentationImageModel = {
  platform_id: number | string;
  platform_name: string;
  platform_is_sys?: boolean;
  base_url?: string;
  api_key_set?: boolean;
  model_id: number | string;
  model_name: string;
  display_name: string;
  input_modalities: string[];
  output_modalities: string[];
};

export type PresentationImageModelsResult = {
  models: PresentationImageModel[];
  error?: string;
};

export type PresentationReferenceRole = 'style' | 'scene' | 'character' | 'continuity';

export type PresentationReferenceDescriptor = {
  assetId: string;
  role: PresentationReferenceRole;
};

export type PresentationGenerationContext = {
  sceneName?: string;
  sceneIntro?: string;
  sceneConception?: string;
  nodeText?: string;
  nearbyDialogue?: string[];
  characterIds?: string[];
};

export type PresentationGenerateImagePayload = {
  prompt: string;
  title?: string;
  size?: string;
  platformId?: number | string | null;
  modelId?: number | string | null;
  referenceAssetIds?: string[];
  referenceAssets?: PresentationReferenceDescriptor[];
  context?: PresentationGenerationContext;
};

export type PresentationGenerateBackgroundPayload = PresentationGenerateImagePayload & {
  library?: boolean;
};

export type PresentationGenerateSpritePayload = PresentationGenerateImagePayload & {
  characterId?: string | number | null;
  expression?: string;
};

export type PresentationReferenceAssetType = 'style_reference' | 'scene_reference';

export type PresentationGenerateReferencePayload = PresentationGenerateImagePayload & {
  assetType?: PresentationReferenceAssetType;
};

export type PresentationGenerateIllustrationPayload = PresentationGenerateImagePayload & {
  sceneName?: string;
  nodeId?: string;
};

export type PresentationGenerateIllustrationConceptionPayload = {
  sceneName?: string;
  nodeId?: string;
  currentPrompt?: string;
  context?: PresentationGenerationContext;
};

export type PresentationIllustrationConceptionResult = {
  success?: boolean;
  prompt: string;
  sceneName?: string;
  nodeId?: string;
};

export type UpdatePresentationSettingsPayload = {
  visualIllustrationEnabled?: boolean;
  styleSeedPrompt?: string | null;
  styleReferenceAssetIds?: string[];
};

const PRESENTATION_UPSTREAM_BLOCKING_STATUSES = new Set([401, 403, 429, 500]);

export class PresentationRequestError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message || `请求失败 (${status})`);
    this.name = 'PresentationRequestError';
    this.status = status;
  }
}

export function getPresentationErrorStatus(error: unknown): number | null {
  if (error && typeof error === 'object') {
    const status = (error as { status?: unknown }).status;
    const parsedStatus = Number(status);
    if (Number.isInteger(parsedStatus) && parsedStatus >= 400 && parsedStatus <= 599) {
      return parsedStatus;
    }
  }
  const message = error instanceof Error ? error.message : String(error || '');
  const statusMatch = message.match(/\b(?:http\s*)?(400|401|403|404|408|409|413|429|500|502|503|504)\b/i)
    || message.match(/\b(?:status|status_code|code)\s*[:=]\s*(400|401|403|404|408|409|413|429|500|502|503|504)\b/i);
  return statusMatch ? Number(statusMatch[1]) : null;
}

export function isPresentationUpstream500Error(error: unknown): boolean {
  return getPresentationErrorStatus(error) === 500
    || /internal server error/i.test(error instanceof Error ? error.message : String(error || ''));
}

export function isPresentationEndpointNotFoundError(error: unknown): boolean {
  return getPresentationErrorStatus(error) === 404;
}

export function isPresentationUpstreamBlockingError(error: unknown): boolean {
  return PRESENTATION_UPSTREAM_BLOCKING_STATUSES.has(getPresentationErrorStatus(error) || 0);
}

export function getPresentationErrorMessage(error: unknown, fallback: string): string {
  if (isPresentationUpstream500Error(error)) {
    return i18n.global.t('nodeEditor.presentation.upstream500Hint');
  }
  if (isPresentationUpstreamBlockingError(error)) {
    return i18n.global.t('nodeEditor.presentation.upstreamNodeHint', {
      status: getPresentationErrorStatus(error) || '',
    });
  }
  if (isPresentationEndpointNotFoundError(error)) {
    return i18n.global.t('nodeEditor.presentation.endpoint404Hint');
  }
  if (error instanceof Error && error.message.trim()) return error.message;
  const raw = String(error || '').trim();
  return raw || fallback;
}

async function readPresentationError(response: Response): Promise<string> {
  try {
    const data = await response.json() as Record<string, unknown>;
    if (typeof data.error === 'string' && data.error) return data.error;
    if (typeof data.message === 'string' && data.message) return data.message;
    if (typeof data.detail === 'string' && data.detail) return data.detail;
  } catch {
    // 忽略无法解析的错误响应体。
  }
  return '';
}

export async function uploadPresentationBackground(projectName: string, file: File, title = '', library = false): Promise<PresentationUploadResult> {
  const form = new FormData();
  form.append('file', file);
  if (title) form.append('title', title);
  if (library) form.append('library', 'true');

  const response = await fetchWithAuth(`/api/presentation/${encodeURIComponent(projectName)}/backgrounds/upload`, {
    method: 'POST',
    body: form,
  });
  if (!response.ok) {
    throw new PresentationRequestError(await readPresentationError(response), response.status);
  }
  return await response.json() as PresentationUploadResult;
}

export async function generatePresentationBackground(
  projectName: string,
  payload: PresentationGenerateBackgroundPayload,
  signal?: AbortSignal,
): Promise<PresentationUploadResult> {
  const response = await fetchWithAuth(`/api/presentation/${encodeURIComponent(projectName)}/backgrounds/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    throw new PresentationRequestError(await readPresentationError(response), response.status);
  }
  return await response.json() as PresentationUploadResult;
}

export async function uploadPresentationSprite(
  projectName: string,
  file: File,
  options: {
    title?: string;
    characterId?: string | number | null;
    expression?: string;
    matting?: { mode?: string; sourceAssetId?: string };
  } = {},
): Promise<PresentationUploadResult> {
  const form = new FormData();
  form.append('file', file);
  if (options.title) form.append('title', options.title);
  if (options.characterId !== undefined && options.characterId !== null) form.append('characterId', String(options.characterId));
  if (options.expression) form.append('expression', options.expression);
  if (options.matting?.mode) form.append('mattingMode', String(options.matting.mode));
  if (options.matting?.sourceAssetId) form.append('mattingSourceAssetId', String(options.matting.sourceAssetId));

  const response = await fetchWithAuth(`/api/presentation/${encodeURIComponent(projectName)}/sprites/upload`, {
    method: 'POST',
    body: form,
  });
  if (!response.ok) {
    throw new PresentationRequestError(await readPresentationError(response), response.status);
  }
  return await response.json() as PresentationUploadResult;
}

export async function generatePresentationSprite(
  projectName: string,
  payload: PresentationGenerateSpritePayload,
  signal?: AbortSignal,
): Promise<PresentationUploadResult> {
  const response = await fetchWithAuth(`/api/presentation/${encodeURIComponent(projectName)}/sprites/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    throw new PresentationRequestError(await readPresentationError(response), response.status);
  }
  return await response.json() as PresentationUploadResult;
}

export async function uploadPresentationReference(
  projectName: string,
  file: File,
  options: { title?: string; assetType?: PresentationReferenceAssetType } = {},
): Promise<PresentationUploadResult> {
  const form = new FormData();
  form.append('file', file);
  if (options.title) form.append('title', options.title);
  form.append('assetType', options.assetType || 'style_reference');

  const response = await fetchWithAuth(`/api/presentation/${encodeURIComponent(projectName)}/references/upload`, {
    method: 'POST',
    body: form,
  });
  if (!response.ok) {
    throw new PresentationRequestError(await readPresentationError(response), response.status);
  }
  return await response.json() as PresentationUploadResult;
}

export async function generatePresentationReference(
  projectName: string,
  payload: PresentationGenerateReferencePayload,
  signal?: AbortSignal,
): Promise<PresentationUploadResult> {
  const response = await fetchWithAuth(`/api/presentation/${encodeURIComponent(projectName)}/references/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    throw new PresentationRequestError(await readPresentationError(response), response.status);
  }
  return await response.json() as PresentationUploadResult;
}

export async function fetchPresentationManifest(projectName: string): Promise<PresentationPayload> {
  const response = await fetchWithAuth(`/api/presentation/${encodeURIComponent(projectName)}`);
  if (!response.ok) {
    throw new PresentationRequestError(await readPresentationError(response), response.status);
  }
  return await response.json() as PresentationPayload;
}

export async function updatePresentationSettings(
  projectName: string,
  payload: UpdatePresentationSettingsPayload,
): Promise<{ success?: boolean; settings?: PresentationSettings }> {
  const response = await fetchWithAuth(`/api/presentation/${encodeURIComponent(projectName)}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new PresentationRequestError(await readPresentationError(response), response.status);
  }
  return await response.json() as { success?: boolean; settings?: PresentationSettings };
}

export async function uploadPresentationIllustration(
  projectName: string,
  file: File,
  options: { title?: string; sceneName?: string; nodeId?: string | number } = {},
): Promise<PresentationUploadResult> {
  const form = new FormData();
  form.append('file', file);
  if (options.title) form.append('title', options.title);
  if (options.sceneName) form.append('sceneName', options.sceneName);
  if (options.nodeId !== undefined && options.nodeId !== null) form.append('nodeId', String(options.nodeId));
  const response = await fetchWithAuth(`/api/presentation/${encodeURIComponent(projectName)}/illustrations/upload`, {
    method: 'POST',
    body: form,
  });
  if (!response.ok) {
    throw new PresentationRequestError(await readPresentationError(response), response.status);
  }
  return await response.json() as PresentationUploadResult;
}

export async function generatePresentationIllustration(
  projectName: string,
  payload: PresentationGenerateIllustrationPayload,
  signal?: AbortSignal,
): Promise<PresentationUploadResult> {
  const response = await fetchWithAuth(`/api/presentation/${encodeURIComponent(projectName)}/illustrations/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    throw new PresentationRequestError(await readPresentationError(response), response.status);
  }
  return await response.json() as PresentationUploadResult;
}

export async function generatePresentationIllustrationConception(
  projectName: string,
  payload: PresentationGenerateIllustrationConceptionPayload,
  signal?: AbortSignal,
): Promise<PresentationIllustrationConceptionResult> {
  const response = await fetchWithAuth(`/api/presentation/${encodeURIComponent(projectName)}/illustrations/conception`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    throw new PresentationRequestError(await readPresentationError(response), response.status);
  }
  return await response.json() as PresentationIllustrationConceptionResult;
}

export async function fetchPresentationImageModels(): Promise<PresentationImageModelsResult> {
  const response = await fetchWithAuth('/api/presentation/image-models');
  if (!response.ok) {
    throw new PresentationRequestError(await readPresentationError(response), response.status);
  }
  return await response.json() as PresentationImageModelsResult;
}
