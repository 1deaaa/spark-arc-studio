export const MODEL_CAPABILITIES = {
  textGeneration: 'text_generation',
  visionInput: 'vision_input',
  embedding: 'embedding',
  imageGeneration: 'image_generation',
  imageReferenceInput: 'image_reference_input',
  imageEdit: 'image_edit',
} as const;

export type ModelCapability = typeof MODEL_CAPABILITIES[keyof typeof MODEL_CAPABILITIES];

export type ModelTypeKey =
  | 'text'
  | 'vision_text'
  | 'embedding'
  | 'image_generation'
  | 'image_reference';

const CAPABILITY_ORDER: ModelCapability[] = [
  MODEL_CAPABILITIES.textGeneration,
  MODEL_CAPABILITIES.visionInput,
  MODEL_CAPABILITIES.embedding,
  MODEL_CAPABILITIES.imageGeneration,
  MODEL_CAPABILITIES.imageReferenceInput,
  MODEL_CAPABILITIES.imageEdit,
];

const MODEL_TYPE_CAPABILITIES: Record<ModelTypeKey, ModelCapability[]> = {
  text: [MODEL_CAPABILITIES.textGeneration],
  vision_text: [MODEL_CAPABILITIES.textGeneration, MODEL_CAPABILITIES.visionInput],
  embedding: [MODEL_CAPABILITIES.embedding],
  image_generation: [
    MODEL_CAPABILITIES.imageGeneration,
    MODEL_CAPABILITIES.imageReferenceInput,
    MODEL_CAPABILITIES.imageEdit,
  ],
  image_reference: [
    MODEL_CAPABILITIES.imageGeneration,
    MODEL_CAPABILITIES.imageReferenceInput,
    MODEL_CAPABILITIES.imageEdit,
  ],
};

export function normalizeModelCapabilities(raw: unknown): ModelCapability[] {
  const values = Array.isArray(raw) ? raw : [];
  const set = new Set<ModelCapability>();
  values.forEach((item) => {
    if (typeof item !== 'string') return;
    if ((CAPABILITY_ORDER as string[]).includes(item)) {
      set.add(item as ModelCapability);
    }
  });

  if (set.has(MODEL_CAPABILITIES.embedding)) {
    return [MODEL_CAPABILITIES.embedding];
  }
  if (set.has(MODEL_CAPABILITIES.imageEdit)) {
    set.add(MODEL_CAPABILITIES.imageGeneration);
    set.add(MODEL_CAPABILITIES.imageReferenceInput);
  }
  if (set.has(MODEL_CAPABILITIES.imageReferenceInput)) {
    set.add(MODEL_CAPABILITIES.imageGeneration);
  }
  if (set.has(MODEL_CAPABILITIES.visionInput)) {
    set.add(MODEL_CAPABILITIES.textGeneration);
  }
  if (set.size === 0) {
    set.add(MODEL_CAPABILITIES.textGeneration);
  }
  return CAPABILITY_ORDER.filter(capability => set.has(capability));
}

export function modelTypeToCapabilities(type: ModelTypeKey): ModelCapability[] {
  return [...MODEL_TYPE_CAPABILITIES[type]];
}

export function capabilitiesToModelType(raw: unknown): ModelTypeKey {
  const capabilities = normalizeModelCapabilities(raw);
  if (capabilities.includes(MODEL_CAPABILITIES.embedding)) return 'embedding';
  if (capabilities.includes(MODEL_CAPABILITIES.imageGeneration)) return 'image_generation';
  if (capabilities.includes(MODEL_CAPABILITIES.visionInput)) return 'vision_text';
  return 'text';
}

export function isTextModel(raw: unknown): boolean {
  return normalizeModelCapabilities(raw).includes(MODEL_CAPABILITIES.textGeneration);
}

export function isEmbeddingModel(raw: unknown): boolean {
  return normalizeModelCapabilities(raw).includes(MODEL_CAPABILITIES.embedding);
}

export function isImageModel(raw: unknown): boolean {
  return normalizeModelCapabilities(raw).includes(MODEL_CAPABILITIES.imageGeneration);
}
