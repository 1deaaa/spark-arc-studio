export type PresentationIllustrationPolicy = {
  maxPerScene?: number;
  minNodeGap?: number;
};

function normalizeBoundedInteger(value: unknown, fallback: number, minimum: number, maximum: number) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(minimum, Math.min(maximum, Math.trunc(parsed)));
}

function normalizedValue(value: unknown) {
  const raw = Array.isArray(value) ? value[0] : value;
  return typeof raw === 'string' ? raw.trim() : '';
}

function cueValue(cue: unknown, key: string) {
  if (!cue || typeof cue !== 'object') return undefined;
  return (cue as Record<string, unknown>)[key];
}

/**
 * 选择当前仍缺少图片资产、且不会新增视觉节奏违规的插图节点。
 * 已经有插图资产的节点只占用名额，不会被此函数修改或删除。
 */
export function selectPresentationIllustrationCandidates<T>(
  nodes: T[],
  getCue: (node: T) => unknown,
  policy: PresentationIllustrationPolicy = {},
): T[] {
  const maxPerScene = normalizeBoundedInteger(policy.maxPerScene, 2, 1, 4);
  const minNodeGap = normalizeBoundedInteger(policy.minNodeGap, 1, 0, 4);
  const occupiedIndexes: number[] = [];

  nodes.forEach((node, index) => {
    if (normalizedValue(cueValue(getCue(node), 'illustration'))) occupiedIndexes.push(index);
  });

  let occupiedCount = occupiedIndexes.length;
  const acceptedIndexes: number[] = [];
  const candidates: T[] = [];
  if (occupiedCount >= maxPerScene) return candidates;

  nodes.forEach((node, index) => {
    const cue = getCue(node);
    if (!normalizedValue(cueValue(cue, 'illustration_prompt')) || normalizedValue(cueValue(cue, 'illustration'))) return;
    if (occupiedCount >= maxPerScene) return;

    const hasNearbyIllustration = [...occupiedIndexes, ...acceptedIndexes]
      .some(existingIndex => Math.abs(index - existingIndex) <= minNodeGap);
    if (hasNearbyIllustration) return;

    acceptedIndexes.push(index);
    occupiedCount += 1;
    candidates.push(node);
  });

  return candidates;
}
