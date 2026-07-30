import type { LocalEmbeddingStatus } from '../../services/api';

const ACTIVE_STARTUP_PHASES = new Set([
  'starting',
  'downloading_model',
  'model_ready',
  'downloading_server',
  'server_ready',
  'loading',
]);

export function isLocalEmbeddingStartupActive(status: LocalEmbeddingStatus | null | undefined): boolean {
  const phase = status?.startup?.phase;
  return typeof phase === 'string' && ACTIVE_STARTUP_PHASES.has(phase);
}

export function isLocalEmbeddingSwitchOn(enabled: boolean | null | undefined): boolean {
  return enabled === true;
}

export function getLocalEmbeddingErrorSummary(
  status: LocalEmbeddingStatus | null | undefined,
  fallback: string,
): string | null {
  return status?.startup?.phase === 'error' ? fallback : null;
}
