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
  const dict = cue as Record<string, unknown>;
  if (key === 'illustration_prompt') return dict.img ?? dict.illustration_prompt;
  if (key === 'illustration_pending') return dict.pending ?? dict.illustration_pending;
  return dict[key];
}

function hasIllustrationAsset(cue: unknown) {
  return !!normalizedValue(cueValue(cue, 'illustration'));
}

function hasIllustrationPrompt(cue: unknown) {
  return !!normalizedValue(cueValue(cue, 'illustration_prompt'));
}

function hasIllustrationPending(cue: unknown) {
  return normalizedValue(cueValue(cue, 'illustration_pending')).toLowerCase() === 'true';
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
  const pendingIndexes: number[] = [];

  nodes.forEach((node, index) => {
    const cue = getCue(node);
    if (hasIllustrationAsset(cue)) occupiedIndexes.push(index);
    else if (hasIllustrationPending(cue) && !hasIllustrationPrompt(cue)) pendingIndexes.push(index);
  });

  let occupiedCount = occupiedIndexes.length + pendingIndexes.length;
  const acceptedIndexes: number[] = [];
  const candidates: T[] = [];
  if (occupiedCount >= maxPerScene) return candidates;

  nodes.forEach((node, index) => {
    const cue = getCue(node);
    if (!hasIllustrationPrompt(cue) || hasIllustrationAsset(cue)) return;
    const reservedByPending = pendingIndexes.includes(index);
    if (occupiedCount >= maxPerScene && !reservedByPending) return;

    const hasNearbyIllustration = [
      ...occupiedIndexes,
      ...pendingIndexes.filter(existingIndex => existingIndex !== index),
      ...acceptedIndexes,
    ]
      .some(existingIndex => Math.abs(index - existingIndex) <= minNodeGap);
    if (hasNearbyIllustration) return;

    acceptedIndexes.push(index);
    if (!reservedByPending) occupiedCount += 1;
    candidates.push(node);
  });

  return candidates;
}

/**
 * 选择明确预留了 pending 标记、但还没有具体描述或图片资产的节点。
 * pending 是编剧交给 AI 的明确任务，不受普通插图的数量上限和节点间距限制。
 * 保留 policy 参数是为了兼容调用方；视觉节奏策略只约束实际插图生成。
 */
export function selectPresentationIllustrationConceptionCandidates<T>(
  nodes: T[],
  getCue: (node: T) => unknown,
  _policy: PresentationIllustrationPolicy = {},
): T[] {
  return nodes.filter(node => {
    const cue = getCue(node);
    return hasIllustrationPending(cue)
      && !hasIllustrationPrompt(cue)
      && !hasIllustrationAsset(cue);
  });
}
