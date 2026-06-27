import type { ArcScene } from '@/services/arcParser';

export type SceneContentKind = 'mainline' | 'side' | 'panel' | 'system';

export type SceneRuntimeSummary = {
  kind: SceneContentKind;
  hidden: boolean;
  triggerEvent: string;
  buttonText: string;
  onceKey: string;
  priority: number;
  conditionCount: number;
  effectCount: number;
  hasConditions: boolean;
  hasEffects: boolean;
};

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function countStructured(value: unknown): number {
  if (Array.isArray(value)) return value.length;
  if (value && typeof value === 'object') return Object.keys(value).length;
  return 0;
}

export function getSceneRuntimeSummary(scene: Partial<ArcScene> | null | undefined): SceneRuntimeSummary {
  const triggerEvent = text(scene?.trigger_event);
  const buttonText = text(scene?.button_text);
  const onceKey = text(scene?.once_key);
  const conditionCount = countStructured(scene?.conditions);
  const effectCount = countStructured(scene?.effects);
  const hidden = !!(scene?.hiden || scene?.hidden);
  const priority = Number.isFinite(Number(scene?.priority)) ? Number(scene?.priority) : 0;
  let kind: SceneContentKind = 'mainline';

  if (triggerEvent) {
    kind = 'system';
  } else if (buttonText) {
    kind = 'panel';
  } else if (hidden || onceKey || conditionCount > 0) {
    kind = 'side';
  }

  return {
    kind,
    hidden,
    triggerEvent,
    buttonText,
    onceKey,
    priority,
    conditionCount,
    effectCount,
    hasConditions: conditionCount > 0,
    hasEffects: effectCount > 0,
  };
}

