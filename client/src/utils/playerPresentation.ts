import type { PresentationAsset } from '@/services/presentationService';

export type PlayerDialogueSpeaker = {
  chr?: number | string | null;
  speaker?: string | null;
};

export type ResolvedCharacterSprite = {
  id: string;
  asset: PresentationAsset;
  characterId: string;
};

function normalizeText(value: unknown): string {
  return String(value ?? '').trim();
}

function normalizeCharacterKey(value: unknown): string {
  const text = normalizeText(value);
  if (/^-?\d+$/.test(text)) return String(Number(text));
  return text;
}

function isNarrator(value: unknown): boolean {
  const text = normalizeCharacterKey(value);
  return !text || text === '-1' || text === '旁白';
}

function normalizedCharacterMap(charMap: Record<string | number, string>): Map<string, string> {
  const result = new Map<string, string>();
  for (const [rawId, rawName] of Object.entries(charMap || {})) {
    const id = normalizeCharacterKey(rawId);
    const name = normalizeText(rawName);
    if (id && name) result.set(id, name);
  }
  return result;
}

/** 将 ARC 节点的数字 ID或角色名统一解析为 manifest 使用的角色 ID。 */
export function resolveDialogueCharacterId(
  dialogue: PlayerDialogueSpeaker | null | undefined,
  charMap: Record<string | number, string> = {},
): string {
  if (!dialogue) return '';

  const rawChr = normalizeText(dialogue.chr);
  const speaker = normalizeText(dialogue.speaker);
  if ((!rawChr && !speaker) || (rawChr && isNarrator(rawChr)) || (speaker && isNarrator(speaker))) {
    return '';
  }

  const idToName = normalizedCharacterMap(charMap);
  const nameToId = new Map<string, string>();
  for (const [id, name] of idToName.entries()) {
    nameToId.set(name, id);
  }

  const rawCandidates = [rawChr, speaker].filter(Boolean);
  for (const rawCandidate of rawCandidates) {
    const candidate = normalizeCharacterKey(rawCandidate);
    if (idToName.has(candidate)) return candidate;
    const mappedId = nameToId.get(rawCandidate);
    if (mappedId) return mappedId;
  }

  // 允许没有角色表的旧项目继续使用名称型 characterId。
  const fallback = rawCandidates.find(candidate => !isNarrator(candidate));
  return fallback ? normalizeCharacterKey(fallback) : '';
}

function isDefaultSprite(asset: PresentationAsset): boolean {
  const expression = normalizeText(asset.expression).toLowerCase();
  return !expression || expression === 'default' || expression === 'base';
}

function compareNewest(
  left: { key: string; asset: PresentationAsset },
  right: { key: string; asset: PresentationAsset },
): number {
  const createdAtOrder = normalizeText(right.asset.createdAt).localeCompare(
    normalizeText(left.asset.createdAt),
  );
  if (createdAtOrder !== 0) return createdAtOrder;
  return right.key.localeCompare(left.key);
}

/** 选择指定角色最新的基础立绘；存在 default 时不让表情变体抢占默认位。 */
export function selectDefaultCharacterSprite(
  assets: Record<string, PresentationAsset> = {},
  characterId: string,
): ResolvedCharacterSprite | null {
  const normalizedId = normalizeCharacterKey(characterId);
  if (!normalizedId) return null;

  const matches = Object.entries(assets || {})
    .filter(([, asset]) => (
      asset?.type === 'character_sprite'
      && normalizeCharacterKey(asset.characterId) === normalizedId
    ))
    .map(([key, asset]) => ({ key, asset }));
  if (matches.length === 0) return null;

  const defaults = matches.filter(({ asset }) => isDefaultSprite(asset));
  const selected = (defaults.length > 0 ? defaults : matches).sort(compareNewest)[0];
  const id = normalizeText(selected.asset.id) || selected.key;
  if (!id) return null;

  return { id, asset: selected.asset, characterId: normalizedId };
}

export function resolveDefaultCharacterSprite(
  dialogue: PlayerDialogueSpeaker | null | undefined,
  charMap: Record<string | number, string> = {},
  assets: Record<string, PresentationAsset> = {},
): ResolvedCharacterSprite | null {
  const characterId = resolveDialogueCharacterId(dialogue, charMap);
  return selectDefaultCharacterSprite(assets, characterId);
}
