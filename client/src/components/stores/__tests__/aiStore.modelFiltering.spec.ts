import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';

import { useAiStore } from '@/components/stores/aiStore';

describe('AI 模型选项过滤', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('语言模型选项排除生图模型和仅含生图模型的平台', () => {
    const store = useAiStore();
    store.allModels = [
      {
        platform_id: 'language-platform',
        platform_name: '语言平台',
        model_id: 'text-model',
        model_name: 'text-model',
        input_modalities: ['text'],
        output_modalities: ['text'],
      },
      {
        platform_id: 'language-platform',
        platform_name: '语言平台',
        model_id: 'unified-image-model',
        model_name: 'unified-image-model',
        input_modalities: ['text', 'image'],
        output_modalities: ['text', 'image'],
      },
      {
        platform_id: 'image-platform',
        platform_name: '生图平台',
        model_id: 'image-model',
        model_name: 'image-model',
        input_modalities: ['text'],
        output_modalities: ['image'],
      },
    ];

    expect(store.languageModelPlatformOptions).toEqual([
      { label: '语言平台', value: 'language-platform' },
    ]);
    expect(store.getLanguageModelsForPlatform('language-platform')).toEqual([
      { label: 'text-model', value: 'text-model' },
    ]);
    expect(store.getLanguageModelsForPlatform('image-platform')).toEqual([]);
  });
});
