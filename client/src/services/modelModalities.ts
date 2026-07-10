export const MODEL_MODALITIES = {
  text: 'text',
  image: 'image',
  embedding: 'embedding',
} as const;

export type ModelModality = typeof MODEL_MODALITIES[keyof typeof MODEL_MODALITIES];
export type ModelTypeKey = 'text' | 'vision_text' | 'embedding' | 'image_generation';

export type ModelModalitiesLike = {
  input_modalities?: unknown;
  output_modalities?: unknown;
  inputModalities?: unknown;
  outputModalities?: unknown;
};

const INPUT_ORDER: ModelModality[] = [MODEL_MODALITIES.text, MODEL_MODALITIES.image];
const OUTPUT_ORDER: ModelModality[] = [MODEL_MODALITIES.text, MODEL_MODALITIES.image, MODEL_MODALITIES.embedding];

function normalize(raw: unknown, order: ModelModality[]): ModelModality[] {
  const values = Array.isArray(raw) ? raw : [];
  const allowed = new Set(order);
  const selected = new Set<ModelModality>();
  values.forEach((value) => {
    if (typeof value === 'string' && allowed.has(value as ModelModality)) {
      selected.add(value as ModelModality);
    }
  });
  return order.filter(modality => selected.has(modality));
}

export function normalizeInputModalities(raw: unknown): ModelModality[] {
  const modalities = normalize(raw, INPUT_ORDER);
  if (!modalities.includes(MODEL_MODALITIES.text)) {
    modalities.unshift(MODEL_MODALITIES.text);
  }
  return modalities;
}

export function normalizeOutputModalities(raw: unknown): ModelModality[] {
  const modalities = normalize(raw, OUTPUT_ORDER);
  if (modalities.includes(MODEL_MODALITIES.embedding)) {
    return [MODEL_MODALITIES.embedding];
  }
  return modalities.length > 0 ? modalities : [MODEL_MODALITIES.text];
}

export function normalizeModelModalities(
  inputModalities: unknown = undefined,
  outputModalities: unknown = undefined,
) {
  const normalizedOutput = normalizeOutputModalities(outputModalities);
  if (normalizedOutput.includes(MODEL_MODALITIES.embedding)) {
    return {
      inputModalities: [MODEL_MODALITIES.text] as ModelModality[],
      outputModalities: normalizedOutput,
    };
  }
  return {
    inputModalities: normalizeInputModalities(inputModalities),
    outputModalities: normalizedOutput,
  };
}

export function getModelModalities(model: ModelModalitiesLike | null | undefined) {
  return normalizeModelModalities(
    model?.inputModalities ?? model?.input_modalities,
    model?.outputModalities ?? model?.output_modalities,
  );
}

export function modelAccepts(model: ModelModalitiesLike | null | undefined, modality: ModelModality): boolean {
  return getModelModalities(model).inputModalities.includes(modality);
}

export function modelOutputs(model: ModelModalitiesLike | null | undefined, modality: ModelModality): boolean {
  return getModelModalities(model).outputModalities.includes(modality);
}

export function isTextModel(model: ModelModalitiesLike | null | undefined): boolean {
  return modelOutputs(model, MODEL_MODALITIES.text);
}

export function isEmbeddingModel(model: ModelModalitiesLike | null | undefined): boolean {
  return modelOutputs(model, MODEL_MODALITIES.embedding);
}

export function isImageModel(model: ModelModalitiesLike | null | undefined): boolean {
  return modelOutputs(model, MODEL_MODALITIES.image);
}

export function supportsImageInput(model: ModelModalitiesLike | null | undefined): boolean {
  return modelAccepts(model, MODEL_MODALITIES.image);
}

export function modalitiesToModelType(model: ModelModalitiesLike | null | undefined): ModelTypeKey {
  if (isEmbeddingModel(model)) return 'embedding';
  if (isImageModel(model)) return 'image_generation';
  if (supportsImageInput(model)) return 'vision_text';
  return 'text';
}
