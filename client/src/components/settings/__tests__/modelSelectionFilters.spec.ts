import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

describe('语言模型选择器', () => {
  it.each([
    'src/components/settings/ModelUsageManager.vue',
    'src/components/lorebook/AiSettingsPanel.vue',
    'src/components/settings/AgentModelCard.vue',
    'src/components/lorebook/AgentFlowBlueprint.vue',
    'src/components/lorebook/AgentModelManager.vue',
  ])('%s 复用统一的语言模型过滤选项', (sourcePath) => {
    const source = readFileSync(resolve(process.cwd(), sourcePath), 'utf8');

    expect(source).toContain('aiStore.languageModelPlatformOptions');
    expect(source).toContain('aiStore.getLanguageModelsForPlatform');
  });
});
