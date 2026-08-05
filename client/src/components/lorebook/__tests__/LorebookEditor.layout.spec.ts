import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';


describe('角色页面纵向布局契约', () => {
  it('角色嵌入模式覆盖通用的自动高度，保证画布拥有可用高度', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'src/components/lorebook/LorebookEditor.vue'),
      'utf-8',
    );

    expect(source).toContain("'is-character-mode': isCharacterAtlas");
    expect(source).toMatch(
      /\.settings-editor-container\.is-embedded\.is-character-mode\s*\{[^}]*height:\s*100%/s,
    );
  });
});
