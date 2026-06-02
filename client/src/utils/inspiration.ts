export function extractLoglineFromInspiration(text: string): string {
  const raw = String(text || '');
  if (!raw.trim()) return '';

  const loglineMatch = raw.match(/(?:(?:\d+\.)?\s*核心概念\s*\(Logline\)|Logline)\s*[:：]?\s*\n?([\s\S]+?)(?=\n+(?:\d+\.)?\s*[\u4e00-\u9fa5]+\s*\(|$)/i);
  if (loglineMatch && loglineMatch[1].trim()) {
    return loglineMatch[1].replace(/[\[\]]/g, '').trim();
  }

  const lines = raw.split('\n').filter(line => line.trim());
  const foundIndex = lines.findIndex(line => line.includes('Logline') || line.includes('核心概念'));
  if (foundIndex !== -1) {
    const foundLine = lines[foundIndex];
    const parts = foundLine.split(/[:：]/);
    if (parts.length > 1 && parts[1].trim()) {
      return parts[1].replace(/[\[\]]/g, '').trim();
    }
    if (foundIndex + 1 < lines.length) {
      return lines[foundIndex + 1].replace(/[\[\]]/g, '').trim();
    }
    return foundLine.trim();
  }

  return lines[lines.length - 1]?.replace(/[\[\]]/g, '').trim() || '';
}

export function buildInspirationGuidance(text: string): string {
  const raw = String(text || '').trim();
  if (!raw) return '';
  return `基于以下灵感扩展：\n${raw}`;
}
