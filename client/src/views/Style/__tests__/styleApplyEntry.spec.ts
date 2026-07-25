import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe('风格项目应用入口', () => {
  it.each(['StyleDesktop.vue', 'StyleMobile.vue'])(
    '%s 只保留一个项目应用按钮入口',
    (fileName) => {
      const source = readFileSync(
        resolve(process.cwd(), 'src/views/Style', fileName),
        'utf8',
      );

      expect(source.match(/@click\.stop="handleApplyToProject\(style\)"/g)).toHaveLength(1);
      expect(source).not.toContain('@click="handleApplyToProject()"');
      expect(source).toContain("views.style.common.applied");
      expect(source).not.toContain('handleToggleDefault');
      expect(source).not.toContain('defaultStyle');
    },
  );
});
