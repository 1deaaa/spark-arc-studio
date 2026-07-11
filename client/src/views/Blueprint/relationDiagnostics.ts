export type RelationJump = {
  target: string;
  type: 'direct' | 'option';
};

export type RelationScene = {
  scene?: string;
  dia?: unknown[];
  guide?: string;
  intro?: string;
  [key: string]: unknown;
};

export type RelationDiagnostic = {
  scene: RelationScene;
  index: number;
  name: string;
  jumps: RelationJump[];
  incoming: string[];
  brokenTargets: string[];
  isolated: boolean;
  duplicateName: boolean;
  hasIssue: boolean;
};

export type RelationDiagnosticSummary = {
  items: RelationDiagnostic[];
  sceneCount: number;
  jumpCount: number;
  issueCount: number;
  isolatedCount: number;
  brokenJumpCount: number;
  duplicateCount: number;
};

function collectDialogueJumps(value: unknown, inheritedType: RelationJump['type'], output: RelationJump[]): void {
  if (!value || typeof value !== 'object') return;
  if (Array.isArray(value)) {
    value.forEach(item => collectDialogueJumps(item, inheritedType, output));
    return;
  }

  const record = value as Record<string, unknown>;
  const target = typeof record.next === 'string' ? record.next.trim() : '';
  if (target) output.push({ target, type: inheritedType });

  if (Array.isArray(record.opt)) {
    record.opt.forEach(option => collectDialogueJumps(option, 'option', output));
  }
  if (Array.isArray(record.dia)) {
    record.dia.forEach(dialogue => collectDialogueJumps(dialogue, inheritedType, output));
  }
}

export function getRelationJumps(scene: RelationScene): RelationJump[] {
  const jumps: RelationJump[] = [];
  collectDialogueJumps(scene.dia, 'direct', jumps);
  const seen = new Set<string>();
  return jumps.filter(jump => {
    const key = `${jump.target}:${jump.type}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function buildRelationDiagnostics(scenes: RelationScene[]): RelationDiagnosticSummary {
  const normalizedScenes = Array.isArray(scenes) ? scenes : [];
  const names = normalizedScenes.map(scene => String(scene.scene || '').trim());
  const validNames = new Set(names.filter(Boolean));
  const nameCounts = names.reduce((counts, name) => {
    if (name) counts.set(name, (counts.get(name) || 0) + 1);
    return counts;
  }, new Map<string, number>());
  const jumpsByIndex = normalizedScenes.map(getRelationJumps);

  const items = normalizedScenes.map((scene, index): RelationDiagnostic => {
    const name = names[index];
    const jumps = jumpsByIndex[index];
    const incoming = normalizedScenes
      .map((source, sourceIndex) => ({
        name: names[sourceIndex],
        reachesTarget: !!name && jumpsByIndex[sourceIndex].some(jump => jump.target === name),
      }))
      .filter(source => source.reachesTarget && source.name)
      .map(source => source.name);
    const brokenTargets = jumps
      .map(jump => jump.target)
      .filter(target => !validNames.has(target));
    const isolated = incoming.length === 0 && jumps.length === 0;
    const duplicateName = !!name && (nameCounts.get(name) || 0) > 1;
    return {
      scene,
      index,
      name,
      jumps,
      incoming,
      brokenTargets: [...new Set(brokenTargets)],
      isolated,
      duplicateName,
      hasIssue: isolated || duplicateName || brokenTargets.length > 0,
    };
  });

  return {
    items,
    sceneCount: items.length,
    jumpCount: items.reduce((total, item) => total + item.jumps.length, 0),
    issueCount: items.filter(item => item.hasIssue).length,
    isolatedCount: items.filter(item => item.isolated).length,
    brokenJumpCount: items.reduce((total, item) => total + item.brokenTargets.length, 0),
    duplicateCount: items.filter(item => item.duplicateName).length,
  };
}
