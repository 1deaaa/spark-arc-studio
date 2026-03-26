import { defineStore } from 'pinia';
import { fetchBlueprint, saveBlueprint } from '@/services/api';
import bus from '@/eventBus';
import type { JsonObject } from '@/services/aiContracts';

type BlueprintNodePosition = {
  x: number;
  y: number;
};

type BlueprintConnection = {
  sourceId: string;
  targetId: string;
};

type BlueprintPayload = {
  nodePositions: Record<string, BlueprintNodePosition>;
  connections: BlueprintConnection[];
};

type BlueprintState = BlueprintPayload & {
  isLoading: boolean;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function normalizeNodePositions(value: unknown): Record<string, BlueprintNodePosition> {
  if (!isRecord(value)) return {};
  const entries = Object.entries(value)
    .map(([key, item]) => {
      if (!isRecord(item)) return null;
      const x = Number(item.x);
      const y = Number(item.y);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
      return [key, { x, y }] as const;
    })
    .filter((entry): entry is readonly [string, BlueprintNodePosition] => entry !== null);
  return Object.fromEntries(entries);
}

function normalizeConnections(value: unknown): BlueprintConnection[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      if (!isRecord(item)) return null;
      const sourceId = String(item.sourceId || '').trim();
      const targetId = String(item.targetId || '').trim();
      if (!sourceId || !targetId) return null;
      return { sourceId, targetId };
    })
    .filter((item): item is BlueprintConnection => item !== null);
}

function isBlueprintPayload(value: JsonObject): value is JsonObject & { nodePositions?: unknown; connections?: unknown } {
  return 'nodePositions' in value || 'connections' in value;
}

export const useBlueprintStore = defineStore('blueprint', {
  state: (): BlueprintState => ({
    nodePositions: {}, // { [nodeId]: { x, y } }
    connections: [],   // [{ sourceId, targetId }]
    isLoading: false,
  }),
  actions: {
    async loadBlueprint(projectName: string | null | undefined) {
      if (!projectName) {
        this.nodePositions = {};
        this.connections = [];
        return;
      }
      this.isLoading = true;
      try {
        const data = await fetchBlueprint(projectName);
        // 兼容旧数据：若直接是 positions 映射，则按旧格式处理
        if (isBlueprintPayload(data)) {
          this.nodePositions = normalizeNodePositions(data.nodePositions);
          this.connections = normalizeConnections(data.connections);
        } else {
          this.nodePositions = normalizeNodePositions(data);
          this.connections = [];
        }
      } catch (error: unknown) {
        console.error('加载蓝图失败:', error);
        this.nodePositions = {};
        this.connections = [];
      } finally {
        this.isLoading = false;
      }
    },
    async saveBlueprint(projectName: string | null | undefined) {
      if (!projectName || this.isLoading) {
        return;
      }
      try {
        const payload = {
          nodePositions: this.nodePositions,
          connections: this.connections,
        };
        await saveBlueprint(projectName, payload);
        // Optional: show a success toast
        // bus.emit('toast', { type: 'success', message: '蓝图已自动保存' });
      } catch (error: unknown) {
        const errorMessage = error instanceof Error ? error.message : String(error || '未知错误');
        console.error('保存蓝图失败:', error);
        bus.emit('toast', { type: 'error', message: `保存蓝图失败: ${errorMessage}` });
      }
    },
    updateNodePosition(nodeId: string, x: number, y: number) {
      if (!this.nodePositions[nodeId]) {
        this.nodePositions[nodeId] = { x: 0, y: 0 };
      }
      this.nodePositions[nodeId] = { x, y };
    },
    addConnection(sourceId: string, targetId: string) {
      if (!sourceId || !targetId || sourceId === targetId) return false;
      const exists = this.connections.some((c) => c.sourceId === sourceId && c.targetId === targetId);
      if (exists) return false;
      this.connections.push({ sourceId, targetId });
      return true;
    },
    removeConnection(sourceId: string, targetId: string) {
      const before = this.connections.length;
      this.connections = this.connections.filter((c) => !(c.sourceId === sourceId && c.targetId === targetId));
      return this.connections.length !== before;
    },
  },
});
