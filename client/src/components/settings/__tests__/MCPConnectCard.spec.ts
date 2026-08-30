import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const readSource = (relativePath: string) =>
  readFileSync(resolve(process.cwd(), relativePath), 'utf8');

describe('MCP 连接配置契约', () => {
  it('共享配置卡生成一个统一的 Streamable HTTP 端点', () => {
    const source = readSource('src/components/settings/MCPConnectCard.vue');

    expect(source).toContain('/api/mcp/');
    expect(source).toContain('/api/mcp/control/');
    expect(source).toContain('"spark-arc"');
    expect(source).not.toContain('"spark-inspiration"');
    expect(source).not.toContain('"spark-control"');
    expect(source).toContain('mcpLegacyControlUrl');
    expect(source.match(/"type": "http"/g)).toHaveLength(1);
    expect(source).not.toContain('"type": "sse"');
  });

  it('桌面仪表盘与移动端 AI 管理复用同一配置卡', () => {
    const dashboard = readSource('src/views/Dashboard/DashboardDesktop.vue');
    const mobileEngine = readSource('src/views/Engine/EngineMobile.vue');

    expect(dashboard).toContain('<MCPConnectCard />');
    expect(mobileEngine).toContain('<MCPConnectCard />');
  });
});
