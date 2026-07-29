export function normalizeVisitedIndexes(
  values: unknown,
  currentIndex: number,
  itemCount: number,
): number[] {
  if (itemCount <= 0) return [];

  const maxIndex = itemCount - 1;
  const fallbackEnd = Math.min(maxIndex, Math.max(0, Math.trunc(currentIndex)));
  const source = Array.isArray(values)
    ? values
    : Array.from({ length: fallbackEnd + 1 }, (_, index) => index);

  const normalized = source
    .filter((value): value is number => Number.isFinite(value))
    .map(value => Math.trunc(value))
    .filter(value => value >= 0 && value <= maxIndex);

  normalized.push(fallbackEnd);
  return [...new Set(normalized)].sort((left, right) => left - right);
}

export function addVisitedIndex(values: number[], index: number, itemCount: number): number[] {
  return normalizeVisitedIndexes([...values, index], index, itemCount);
}

export function filterItemsByVisited<T>(
  items: T[],
  visitedIndexes: number[],
  showFullDirectory: boolean,
): T[] {
  if (showFullDirectory) return items;
  const visited = new Set(visitedIndexes);
  return items.filter((_, index) => visited.has(index));
}
