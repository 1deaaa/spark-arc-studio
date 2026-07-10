import { fetchWithAuth } from './apiClient';

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
  sceneName?: string;
  nodeId?: string;
  createdAt?: string;
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
  reference_asset_id?: string | null;
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

export type PresentationGenerateBackgroundPayload = PresentationGenerateImagePayload;

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
  nodeId?: string | number;
};

export type UpdatePresentationSettingsPayload = {
  visualIllustrationEnabled?: boolean;
  styleSeedPrompt?: string | null;
  styleReferenceAssetId?: string | null;
};

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

export async function uploadPresentationBackground(projectName: string, file: File, title = ''): Promise<PresentationUploadResult> {
  const form = new FormData();
  form.append('file', file);
  if (title) form.append('title', title);

  const response = await fetchWithAuth(`/api/presentation/${encodeURIComponent(projectName)}/backgrounds/upload`, {
    method: 'POST',
    body: form,
  });
  if (!response.ok) {
    throw new Error(await readPresentationError(response));
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
    throw new Error(await readPresentationError(response));
  }
  return await response.json() as PresentationUploadResult;
}

export async function uploadPresentationSprite(
  projectName: string,
  file: File,
  options: { title?: string; characterId?: string | number | null; expression?: string } = {},
): Promise<PresentationUploadResult> {
  const form = new FormData();
  form.append('file', file);
  if (options.title) form.append('title', options.title);
  if (options.characterId !== undefined && options.characterId !== null) form.append('characterId', String(options.characterId));
  if (options.expression) form.append('expression', options.expression);

  const response = await fetchWithAuth(`/api/presentation/${encodeURIComponent(projectName)}/sprites/upload`, {
    method: 'POST',
    body: form,
  });
  if (!response.ok) {
    throw new Error(await readPresentationError(response));
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
    throw new Error(await readPresentationError(response));
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
    throw new Error(await readPresentationError(response));
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
    throw new Error(await readPresentationError(response));
  }
  return await response.json() as PresentationUploadResult;
}

export async function fetchPresentationManifest(projectName: string): Promise<PresentationPayload> {
  const response = await fetchWithAuth(`/api/presentation/${encodeURIComponent(projectName)}`);
  if (!response.ok) {
    throw new Error(await readPresentationError(response));
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
    throw new Error(await readPresentationError(response));
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
    throw new Error(await readPresentationError(response));
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
    throw new Error(await readPresentationError(response));
  }
  return await response.json() as PresentationUploadResult;
}

export async function fetchPresentationImageModels(): Promise<PresentationImageModelsResult> {
  const response = await fetchWithAuth('/api/presentation/image-models');
  if (!response.ok) {
    throw new Error(await readPresentationError(response));
  }
  return await response.json() as PresentationImageModelsResult;
}
