/**
 * Markup 序列化器 / 解析器
 *
 * 职责：
 * 1. 将后端返回的 Markup 纯文本解析为前端结构化数据（供 UI 渲染）
 * 2. 将前端结构化数据序列化为 Markup 文本（供保存/传输）
 * 3. 容错处理：对大模型常见输出错误（多余空行、标签大小写、缺失分隔符等）进行修复
 */

import type { OutlineData, OutlineChapter, OutlineScene, BeatSheetData, BeatSheetBeat } from '../services/aiContracts';

// ==================== 梗概类型 ====================

export interface SynopsisData {
  title: string;
  logline: string;
  synopsis_text: string;
  themes: string[];
  pacing_guide: string;
  estimated_chapters: string;
}

// ==================== 容错工具 ====================

/**
 * 去除 Markdown 代码围栏（大模型有时会包裹 ```markdown ... ```）
 */
function stripMarkdownFence(text: string): string {
  const t = (text || '').trim();
  if (!t.startsWith('```')) return t;
  const lines = t.split('\n');
  if (lines.length >= 2 && lines[0].startsWith('```') && lines[lines.length - 1].trim() === '```') {
    return lines.slice(1, -1).join('\n').trim();
  }
  return t;
}

/**
 * 压缩连续空行（最多保留 2 个空行）
 */
function normalizeBlankLines(text: string): string {
  return text.replace(/\n{3,}/g, '\n\n');
}

// ==================== 梗概解析器 ====================

export function parseSynopsisMarkup(text: string): SynopsisData {
  const result: SynopsisData = {
    title: '',
    logline: '',
    synopsis_text: '',
    themes: [],
    pacing_guide: '',
    estimated_chapters: '',
  };

  if (!text || typeof text !== 'string') return result;

  const cleaned = normalizeBlankLines(stripMarkdownFence(text));
  const bodyLines: string[] = [];

  for (const rawLine of cleaned.split('\n')) {
    const line = rawLine.trim();

    // 提取 @key value 元数据
    if (line.startsWith('@')) {
      const match = line.match(/^@(\w+)\s+(.+)$/);
      if (match) {
        const key = match[1].trim().toLowerCase();
        const val = match[2].trim();
        if (key === 'title') result.title = val;
        else if (key === 'logline') result.logline = val;
        else if (key === 'theme' || key === 'themes') {
          // 容错：支持逗号、顿号分隔
          result.themes = val.split(/[,，、]+/).map(s => s.trim()).filter(Boolean);
        }
        else if (key === 'pacing') result.pacing_guide = val;
        else if (key === 'chapters') result.estimated_chapters = val;
        continue;
      }
    }

    // 非元数据行归入正文
    if (line) {
      bodyLines.push(line);
    }
  }

  result.synopsis_text = bodyLines.join('\n').trim();
  return result;
}

// ==================== 节拍表解析器 ====================

export function parseBeatSheetMarkup(text: string): BeatSheetData {
  const result: BeatSheetData = {
    global_emotional_arc: '',
    beats: [],
  };

  if (!text || typeof text !== 'string') return result;

  const cleaned = normalizeBlankLines(stripMarkdownFence(text));
  let currentBeat: BeatSheetBeat | null = null;

  for (const rawLine of cleaned.split('\n')) {
    const line = rawLine.trim();

    // @arc 全局情感弧光
    if (!currentBeat && line.startsWith('@arc')) {
      const arc = line.replace('@arc', '').trim();
      if (arc) {
        result.global_emotional_arc += (result.global_emotional_arc ? '\n' : '') + arc;
      }
      continue;
    }

    // ---beat N 节拍分隔符
    const beatMatch = line.match(/^---\s*(?:beat|节拍)\s*(\d+)?(.*)$/i);
    if (beatMatch) {
      const beatId = beatMatch[1] ? Number(beatMatch[1]) : (result.beats.length + 1);
      currentBeat = {
        beat_id: Number.isFinite(beatId) ? beatId : (result.beats.length + 1),
        beat_type: '',
        narrative_action: '',
        emotional_goal: '',
        reader_experience: '',
        tension_level: '',
      };
      result.beats.push(currentBeat);
      continue;
    }

    // > 元数据行
    if (currentBeat && line.startsWith('>')) {
      const parts = line.slice(1).split('|');
      for (const part of parts) {
        const kv = part.split(/:|：/, 2);
        if (kv.length !== 2) continue;
        const key = kv[0].trim().toLowerCase();
        const value = kv[1].trim();

        if (key.includes('类型') || key.includes('type')) {
          currentBeat.beat_type = value;
        } else if (key.includes('情感') || key.includes('emotion') || key.includes('心境')) {
          currentBeat.emotional_goal = value;
        } else if (key.includes('体验') || key.includes('experience')) {
          currentBeat.reader_experience = value;
        } else if (key.includes('张力') || key.includes('tension')) {
          currentBeat.tension_level = value;
        }
      }
      continue;
    }

    // 正文
    if (line && currentBeat) {
      currentBeat.narrative_action += (currentBeat.narrative_action ? '\n' : '') + line;
    } else if (line && !currentBeat) {
      result.global_emotional_arc += (result.global_emotional_arc ? '\n' : '') + line;
    }
  }

  return result;
}

// ==================== 大纲解析器 ====================

let _idCounter = 0;
function generateId(prefix: string): string {
  return `${prefix}_${Date.now()}_${++_idCounter}`;
}

export function parseOutlineMarkup(text: string): OutlineData {
  const outlineData: OutlineData = {
    title: '未命名故事',
    summary: '',
    mainTheme: '',
    nodes: [],
    totalChapters: 0,
    estimatedScenes: 0,
  };

  if (!text || typeof text !== 'string') return outlineData;

  const cleaned = normalizeBlankLines(stripMarkdownFence(text));
  let currentChapter: OutlineChapter | null = null;
  let currentScene: OutlineScene | null = null;

  for (const rawLine of cleaned.split('\n')) {
    const line = rawLine.trim();
    if (!line) continue;

    // 全局 Meta 标签
    if (!currentChapter && !currentScene && line.startsWith('@')) {
      const match = line.match(/^@(\w+)\s+(.+)$/);
      if (match) {
        const key = match[1].trim();
        const val = match[2].trim();
        if (key === 'title') outlineData.title = val;
        else if (key === 'summary') outlineData.summary = val;
        else if (key === 'theme') outlineData.mainTheme = val;
      }
      continue;
    }

    // 章节处理 (##)
    const chapterMatch = line.match(/^##\s+(?:Chapter\s*\d*:?\s*)?(.+)$/i);
    if (chapterMatch) {
      const title = chapterMatch[1].trim();
      currentChapter = {
        id: generateId('chap'),
        name: title,
        title: title,
        type: 'chapter',
        chapter: outlineData.nodes.length + 1,
        description: '',
        children: [],
      };
      outlineData.nodes.push(currentChapter);
      currentScene = null;
      continue;
    }

    // 场景处理 (###)
    const sceneMatch = line.match(/^###\s+(?!Scene)(.+)$|^###\s+(?:Scene\s*\d*:?\s*)?(.+)$/i);
    if (sceneMatch) {
      const title = (sceneMatch[1] || sceneMatch[2]).trim();

      if (!currentChapter) {
        currentChapter = {
          id: generateId('chap'),
          name: '未归类章节',
          title: '未归类章节',
          type: 'chapter',
          chapter: outlineData.nodes.length + 1,
          description: '',
          children: [],
        };
        outlineData.nodes.push(currentChapter);
      }

      currentScene = {
        id: generateId('scene'),
        name: title,
        title: title,
        type: 'scene',
        description: '',
        mood: '',
        tension: 'Medium',
        characters: [],
        mapped_beats: [],
      };
      currentChapter.children.push(currentScene);
      continue;
    }

    // 场景元数据层 (>)
    if (currentScene && line.startsWith('>')) {
      const metaStr = line.slice(1).trim();
      const parts = metaStr.split('|');
      for (const part of parts) {
        if (part.includes(':') || part.includes('：')) {
          const kv = part.split(/:|：/, 2);
          if (kv.length !== 2) continue;
          const k = kv[0].trim().toLowerCase();
          const v = kv[1].trim();

          if (k.includes('情绪') || k.includes('mood')) currentScene.mood = v;
          else if (k.includes('张力') || k.includes('tension')) {
            if (v.toLowerCase().includes('low') || v.includes('低')) currentScene.tension = 'Low';
            else if (v.toLowerCase().includes('high') || v.includes('高')) currentScene.tension = 'High';
            else currentScene.tension = 'Medium';
          }
          else if (k.includes('登场') || k.includes('角色') || k.includes('character')) {
            currentScene.characters = v.split(/[,，、]+/).map(s => s.trim()).filter(Boolean);
          }
          else if (k.includes('节拍') || k.includes('beat')) {
            currentScene.mapped_beats = v.split(/[,，、]+/)
              .map(s => parseInt(s.replace(/\D/g, '')))
              .filter(n => !isNaN(n));
          }
        }
      }
      continue;
    }

    // @key_dialogue 行 — 跳过，前端类型不含此字段
    if (currentScene && line.startsWith('@key_dialogue')) {
      continue;
    }

    // 散文推演长文本归入描述
    if (line) {
      if (currentScene) {
        currentScene.description += (currentScene.description ? '\n' : '') + line;
      } else if (currentChapter) {
        currentChapter.description += (currentChapter.description ? '\n' : '') + line;
      } else {
        outlineData.summary += (outlineData.summary ? '\n' : '') + line;
      }
    }
  }

  // 计算统计信息
  outlineData.totalChapters = outlineData.nodes.length;
  outlineData.estimatedScenes = outlineData.nodes.reduce((acc, c) => acc + (c.children?.length || 0), 0);

  return outlineData;
}

// ==================== 序列化器（容错） ====================

/**
 * 将大纲结构化数据序列化为 Outline Markup 文本
 * 容错：缺失字段使用默认值，空数组跳过
 */
export function serializeOutlineToMarkup(outline: OutlineData): string {
  const lines: string[] = [];

  const title = outline.title || '';
  if (title) lines.push(`@title ${title}`);

  const summary = outline.summary || '';
  if (summary) lines.push(`@summary ${summary}`);

  const mainTheme = outline.mainTheme || '';
  if (mainTheme) lines.push(`@theme ${mainTheme}`);

  if (lines.length > 0) lines.push('');

  for (let ci = 0; ci < (outline.nodes || []).length; ci++) {
    const chapter = outline.nodes[ci];
    if (chapter.type !== 'chapter') continue;
    const chTitle = chapter.title || chapter.name || `章节${ci + 1}`;
    const chNum = ci + 1;
    lines.push(`## Chapter ${chNum}: ${chTitle}`);

    const chDesc = (chapter.description || '').trim();
    if (chDesc) lines.push(chDesc);

    for (const scene of chapter.children || []) {
      const scTitle = scene.title || scene.name || '未命名场景';
      lines.push(`### ${scTitle}`);

      // 场景元数据
      const metaParts: string[] = [];
      if (scene.mood) metaParts.push(`情绪：${scene.mood}`);
      if (scene.tension) metaParts.push(`张力：${scene.tension}`);
      if (scene.characters && scene.characters.length > 0) {
        metaParts.push(`登场：${scene.characters.join(', ')}`);
      }
      if (metaParts.length > 0) lines.push('> ' + metaParts.join(' | '));

      const scDesc = (scene.description || '').trim();
      if (scDesc) lines.push(scDesc);

      // key_dialogues 不在前端类型中，跳过
    }

    lines.push('');
  }

  return lines.join('\n').trim();
}

/**
 * 将节拍表结构化数据序列化为 Beat Sheet Markup 文本
 */
export function serializeBeatSheetToMarkup(beatsData: BeatSheetData): string {
  const lines: string[] = [];

  const arc = beatsData.global_emotional_arc || '';
  if (arc) {
    lines.push(`@arc ${arc}`);
    lines.push('');
  }

  for (const beat of beatsData.beats || []) {
    const beatId = beat.beat_id || 0;
    lines.push(`---beat ${beatId}`);

    const metaParts: string[] = [];
    if (beat.beat_type) metaParts.push(`类型：${beat.beat_type}`);
    if (beat.emotional_goal) metaParts.push(`情感目标：${beat.emotional_goal}`);
    if (beat.tension_level) metaParts.push(`张力：${beat.tension_level}`);
    if (metaParts.length > 0) lines.push('> ' + metaParts.join(' | '));

    const narrative = (beat.narrative_action || '').trim();
    if (narrative) lines.push(narrative);

    lines.push('');
  }

  return lines.join('\n').trim();
}

/**
 * 将梗概结构化数据序列化为 Synopsis Markup 文本
 */
export function serializeSynopsisToMarkup(synopsis: SynopsisData): string {
  const lines: string[] = [];

  const title = synopsis.title || '';
  if (title) lines.push(`@title ${title}`);

  const logline = synopsis.logline || '';
  if (logline) lines.push(`@logline ${logline}`);

  const themes = synopsis.themes || [];
  if (themes.length > 0) lines.push(`@theme ${themes.join(', ')}`);

  const pacing = synopsis.pacing_guide || '';
  if (pacing) lines.push(`@pacing ${pacing}`);

  const chapters = synopsis.estimated_chapters || '';
  if (chapters) lines.push(`@chapters ${chapters}`);

  // 元数据和正文之间加空行
  if (lines.length > 0) lines.push('');

  const synopsisText = (synopsis.synopsis_text || '').trim();
  if (synopsisText) lines.push(synopsisText);

  return lines.join('\n').trim();
}
