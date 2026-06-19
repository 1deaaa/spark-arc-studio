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

export function isLocalEmbeddingSwitchOn(status: LocalEmbeddingStatus | null | undefined): boolean {
  if (!status) {
    return false;
  }
  if (status.alive || status.running) {
    return true;
  }
  return isLocalEmbeddingStartupActive(status);
}
