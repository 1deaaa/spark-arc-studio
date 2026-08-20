import { describe, expect, it } from 'vitest';

import {
  MODEL_MODALITIES,
  getModelModalities,
  isEmbeddingModel,
  isImageModel,
  isLanguageModel,
  isTextModel,
  modalitiesToModelType,
  normalizeModelModalities,
  supportsImageInput,
} from '@/services/modelModalities';

describe('模型输入输出模态', () => {
  it('默认规范化为文本输入和文本输出', () => {
    expect(normalizeModelModalities()).toEqual({
      inputModalities: [MODEL_MODALITIES.text],
      outputModalities: [MODEL_MODALITIES.text],
    });
  });

  it('同时解析 API 蛇形字段和表单驼峰字段', () => {
    const apiModel = {
      input_modalities: ['text', 'image'],
      output_modalities: ['text', 'image'],
    };
    const formModel = {
      inputModalities: ['text', 'image'],
      outputModalities: ['text', 'image'],
    };

    expect(getModelModalities(apiModel)).toEqual(getModelModalities(formModel));
    expect(supportsImageInput(apiModel)).toBe(true);
    expect(isImageModel(apiModel)).toBe(true);
    expect(isTextModel(apiModel)).toBe(true);
  });

  it('将模型映射为互斥的主模态类型', () => {
    expect(modalitiesToModelType({ output_modalities: ['text'] })).toBe('text');
    expect(modalitiesToModelType({
      input_modalities: ['text', 'image'],
      output_modalities: ['text'],
    })).toBe('vision_text');
    expect(modalitiesToModelType({
      input_modalities: ['text', 'image'],
      output_modalities: ['text', 'image'],
    })).toBe('image_generation');
    expect(modalitiesToModelType({
      input_modalities: ['text'],
      output_modalities: ['embedding'],
    })).toBe('embedding');
  });

  it('向量输出排除文本和图片输出及图片输入', () => {
    const modalities = normalizeModelModalities(
      ['text', 'image'],
      ['text', 'image', 'embedding'],
    );

    expect(modalities).toEqual({
      inputModalities: [MODEL_MODALITIES.text],
      outputModalities: [MODEL_MODALITIES.embedding],
    });
    expect(isEmbeddingModel(modalities)).toBe(true);
    expect(isTextModel(modalities)).toBe(false);
    expect(isImageModel(modalities)).toBe(false);
  });

  it('语言模型排除任何包含图片输出的模型', () => {
    expect(isLanguageModel({ output_modalities: ['text'] })).toBe(true);
    expect(isLanguageModel({
      input_modalities: ['text', 'image'],
      output_modalities: ['text'],
    })).toBe(true);
    expect(isLanguageModel({ output_modalities: ['image'] })).toBe(false);
    expect(isLanguageModel({ output_modalities: ['text', 'image'] })).toBe(false);
  });
});
