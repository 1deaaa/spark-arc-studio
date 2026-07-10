/**
 * ARC Format Parser
 *
 * 将 .arc 格式的剧本文本解析为内部数据结构。
 *
 * .arc 格式设计为 LLM 友好的创作格式，解析后转换为程序可用的结构化数据。
 */

/**
 * 解析 .arc 文本为场景数组
 * @param {string} arcText - .arc 格式的原始文本
 * @returns {Array} 解析后的场景数组
 */
export type ActValue = string | string[];
export type PresentationCue = {
  bg?: ActValue;
  sprite?: ActValue;
  [key: string]: ActValue | undefined;
};
export type ArcSpeaker = number | string;

export type ArcDialogueNode = {
  id: number;
  chr: ArcSpeaker;
  speaker?: string;
  txt: string;
  thought?: string;
  next?: string;
  presentation?: PresentationCue;
  act?: Record<string, ActValue>;
  opt?: ArcOptionNode[];
};

export type SceneEffectItem = {
  op?: string;
  key?: string;
  value?: unknown;
  [key: string]: unknown;
};

export type ArcOptionNode = {
  optn: string;
  dia: ArcDialogueNode[];
  __oid: string;
};

export type ArcScene = {
  scene: string;
  guide: string;
  intro: string;
  thought: string;
  button_text?: string;
  conditions?: Record<string, unknown> | Array<unknown> | null;
  effects?: SceneEffectItem[] | Record<string, unknown> | null;
  trigger_event?: string;
  priority?: number;
  once_key?: string;
  hiden?: boolean;
  hidden?: boolean;
  dia: ArcDialogueNode[];
  [key: string]: unknown;
};

type ParserState = {
  idCounter: number;
};

const SYSTEM_SPEAKER_ID_TO_NAME: Record<number, string> = {
  [-1]: '旁白',
  [-2]: '?',
};
const SYSTEM_SPEAKER_NAME_TO_ID: Record<string, number> = {
  '旁白': -1,
  '?': -2,
};
const SPEAKER_MARKER_RE = /^\[([^\]\r\n]+)\]$/;
const NUMERIC_MARKER_RE = /^-?\d+$/;

function normalizeChrMap(chrMap: Record<string | number, string> = {}) {
  const normalized: Record<number, string> = {};
  for (const [rawId, rawName] of Object.entries(chrMap || {})) {
    const cid = Number(rawId);
    const name = String(rawName || '').trim();
    if (Number.isFinite(cid) && name) normalized[cid] = name;
  }
  return normalized;
}

function isSpeakerMarkerLine(line: string) {
  return SPEAKER_MARKER_RE.test(String(line || '').trim());
}

function parseSpeakerMarker(line: string, chrMap: Record<string | number, string> = {}): { chr: ArcSpeaker; speaker?: string } {
  const match = String(line || '').trim().match(SPEAKER_MARKER_RE);
  if (!match) return { chr: '旁白', speaker: '旁白' };
  const marker = match[1].trim();
  const idToName = normalizeChrMap(chrMap);
  if (NUMERIC_MARKER_RE.test(marker)) {
    const cid = Number(marker);
    return { chr: cid, speaker: idToName[cid] || SYSTEM_SPEAKER_ID_TO_NAME[cid] };
  }
  if (Object.prototype.hasOwnProperty.call(SYSTEM_SPEAKER_NAME_TO_ID, marker)) {
    return { chr: SYSTEM_SPEAKER_NAME_TO_ID[marker], speaker: marker };
  }
  for (const [rawId, rawName] of Object.entries(idToName)) {
    if (rawName === marker) return { chr: Number(rawId), speaker: marker };
  }
  return { chr: marker, speaker: marker };
}

export function formatSpeakerMarker(chr: ArcSpeaker | null | undefined, speaker = '', chrMap: Record<string | number, string> = {}) {
  const speakerText = String(speaker || '').trim();
  if (speakerText) return `[${speakerText}]`;
  if (typeof chr === 'string') return `[${chr.trim() || '旁白'}]`;
  if (chr === null || chr === undefined) return '[旁白]';
  const idToName = normalizeChrMap(chrMap);
  return `[${idToName[chr] || SYSTEM_SPEAKER_ID_TO_NAME[chr] || chr}]`;
}

export function parseArc(arcText: string, chrMap: Record<string | number, string> = {}): ArcScene[] {
  const scenes: ArcScene[] = [];
  const state: ParserState = { idCounter: 1 };
  
  // 按场景标题分割（# 开头的行）
  const sceneBlocks = splitByScenes(arcText);
  
  for (const block of sceneBlocks) {
    const scene = parseSceneBlock(block, state, chrMap);
    if (scene) {
      scenes.push(scene);
    }
  }

  return normalizeParsedScenes(scenes);
}

function isPlaceholderScene(scene: ArcScene | null | undefined) {
  if (!scene) return true;
  const guide = (scene.guide || '').toString().trim();
  const intro = (scene.intro || '').toString().trim();
  const thought = (scene.thought || '').toString().trim();
  const dia = Array.isArray(scene.dia) ? scene.dia : [];
  return !guide && !intro && !thought && dia.length === 0;
}

function normalizeParsedScenes(scenes: ArcScene[]) {
  const normalized: ArcScene[] = [];
  const firstIndexByName = new Map();

  for (const rawScene of scenes || []) {
    if (!rawScene || typeof rawScene !== 'object') continue;
    const sceneName = (rawScene.scene || '').toString().trim();
    if (!sceneName) continue;

    const scene = {
      ...rawScene,
      scene: sceneName,
      dia: Array.isArray(rawScene.dia) ? rawScene.dia : []
    };

    const existingIndex = firstIndexByName.get(sceneName);
    if (existingIndex === undefined) {
      firstIndexByName.set(sceneName, normalized.length);
      normalized.push(scene);
      continue;
    }

    const existingScene = normalized[existingIndex];
    const existingIsPlaceholder = isPlaceholderScene(existingScene);
    const currentIsPlaceholder = isPlaceholderScene(scene);

    if (existingIsPlaceholder && !currentIsPlaceholder) {
      normalized[existingIndex] = scene;
      continue;
    }
    if (!existingIsPlaceholder && currentIsPlaceholder) {
      continue;
    }

    normalized.push(scene);
  }

  return normalized;
}

/**
 * 将文本按场景标题分割
 */
function splitByScenes(text: string) {
  const lines = text.split('\n');
  const blocks: string[] = [];
  let currentBlock: string[] = [];
  let thoughtDepth = 0;
  
  for (const line of lines) {
    const trimmed = line.trim();
    const openThoughtCount = (trimmed.match(/<conception>/g) || []).length;
    const closeThoughtCount = (trimmed.match(/<\/conception>/g) || []).length;

    const isSceneHeader = thoughtDepth === 0 && line.match(/^#\s+/);
    if (isSceneHeader && currentBlock.length > 0) {
      blocks.push(currentBlock.join('\n'));
      currentBlock = [line];
    } else {
      currentBlock.push(line);
    }

    thoughtDepth += openThoughtCount - closeThoughtCount;
    if (thoughtDepth < 0) thoughtDepth = 0;
  }
  
  if (currentBlock.length > 0) {
    blocks.push(currentBlock.join('\n'));
  }
  
  return blocks;
}

/**
 * 解析单个场景块
 */
function parseSceneBlock(blockText: string, state: ParserState, chrMap: Record<string | number, string> = {}): ArcScene | null {
  // 提取场景名（# 标题）
  const titleMatch = blockText.match(/^#\s+(.+)$/m);
  if (!titleMatch) return null;
  
  const sceneName = titleMatch[1].trim();
  
  // 提取 @guide
  const guideMatch = blockText.match(/^@guide\s+(.+)$/m);
  const guide = guideMatch ? guideMatch[1].trim() : '';
  
  // 提取 <conception> 块（每个场景最多一个）
  const thoughtMatches = [...blockText.matchAll(/<conception>([\s\S]*?)<\/conception>/g)];
  if (thoughtMatches.length > 1) {
    throw new Error(`ARC 格式错误：场景 "${sceneName}" 内包含多个 <conception> 块（每个场景最多一个）。`);
  }
  const thought = thoughtMatches.length === 1 ? (thoughtMatches[0][1] || '').trim() : '';
  
  // 移除 <conception> 块以便后续解析正文
  const cleanedText = blockText.replace(/<conception>[\s\S]*?<\/conception>/g, '');

  // 提取 @intro（场景引言）并从正文中移除
  const { intro, text: withoutIntroText } = extractIntroBlock(cleanedText);
  
  const metadata = extractSceneMetadata(withoutIntroText);
  const contentText = metadata.text;
  const dia = parseDialogueContent(contentText, state, chrMap);

  return {
    scene: sceneName,
    guide: guide,
    intro: intro || '',
    thought: thought || '',
    ...metadata.meta,
    dia: dia
  };
}

/**
 * 提取 @intro 块（支持单行与多行），并返回移除后的文本
 */
function extractIntroBlock(text: string) {
  const lines = text.split('\n');
  const outputLines: string[] = [];
  const introLines: string[] = [];
  let inIntro = false;

  const isNextElementStart = (trimmed) => {
    if (!trimmed) return false;
    if (trimmed.startsWith('#')) return true;
    if (trimmed.startsWith('@guide')) return true;
    if (trimmed.startsWith('<choice')) return true;
    if (trimmed.startsWith('<conception>')) return true;
    if (isSpeakerMarkerLine(trimmed)) return true;
    return false;
  };

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const trimmed = raw.trim();

    if (!inIntro && trimmed.startsWith('@intro')) {
      inIntro = true;
      const rest = trimmed.replace(/^@intro\s*/, '');
      if (rest) introLines.push(rest);
      continue;
    }

    if (inIntro) {
      if (!trimmed) {
        inIntro = false;
        continue;
      }
      if (isNextElementStart(trimmed)) {
        inIntro = false;
        outputLines.push(raw);
        continue;
      }
      introLines.push(raw.trim());
      continue;
    }

    outputLines.push(raw);
  }

  return {
    intro: introLines.join('\n').trim(),
    text: outputLines.join('\n')
  };
}

const SCENE_METADATA_PARSERS: Record<string, (raw: string) => unknown> = {
  button_text: (raw) => raw.trim(),
  trigger_event: (raw) => raw.trim(),
  once_key: (raw) => raw.trim(),
  priority: (raw) => Number.parseInt(raw.trim() || '0', 10) || 0,
  hiden: (raw) => ['1', 'true', 'yes', 'on'].includes(raw.trim().toLowerCase()),
  hidden: (raw) => ['1', 'true', 'yes', 'on'].includes(raw.trim().toLowerCase()),
  conditions: (raw) => JSON.parse(raw),
  effects: (raw) => JSON.parse(raw),
};

function extractSceneMetadata(text: string) {
  const lines = text.split('\n');
  const outputLines: string[] = [];
  const meta: Record<string, unknown> = {};

  for (const raw of lines) {
    const trimmed = raw.trim();
    const match = trimmed.match(/^@meta\s+(\w+)\s*:\s*(.+)$/);
    if (!match) {
      outputLines.push(raw);
      continue;
    }

    const key = match[1].trim();
    const value = match[2].trim();
    const parser = SCENE_METADATA_PARSERS[key];
    if (!parser) {
      outputLines.push(raw);
      continue;
    }

    try {
      const parsed = parser(value);
      if (key === 'hidden') meta.hiden = parsed;
      else meta[key] = parsed;
    } catch {
      outputLines.push(raw);
    }
  }

  return {
    meta,
    text: outputLines.join('\n')
  };
}

/**
 * 解析对话内容（包括选项分支）
 */
function parseDialogueContent(
  text: string,
  state: ParserState = { idCounter: 1 },
  chrMap: Record<string | number, string> = {}
) {
  const dialogues: ArcDialogueNode[] = [];
  
  // 先处理选项块，替换为占位符
  const { processedText, choiceBlocks } = extractChoiceBlocks(text);
  
  // 按行解析
  const lines = processedText.split('\n');
  let i = 0;
  
  while (i < lines.length) {
    const line = lines[i].trim();
    
    // 跳过空行、标题行、@guide行
    if (!line || line.startsWith('#') || line.startsWith('@guide') || line.startsWith('@intro') || line.startsWith('<conception>')) {
      i++;
      continue;
    }
    
    // 检查是否是选项占位符
    const choicePlaceholder = line.match(/^__CHOICE_(\d+)__$/);
    if (choicePlaceholder) {
      const choiceIndex = parseInt(choicePlaceholder[1]);
      const choiceBlock = choiceBlocks[choiceIndex];
      if (choiceBlock) {
        // 解析选项块并附加到上一个对话节点
        const options = parseChoiceBlock(choiceBlock, state, chrMap);
        if (dialogues.length > 0) {
          dialogues[dialogues.length - 1].opt = options.options;
        }
      }
      i++;
      continue;
    }
    
    // 匹配对话/旁白标识符 [说话人]
    const chrMatch = line.match(SPEAKER_MARKER_RE);
    
    if (chrMatch) {
      const { chr, speaker } = parseSpeakerMarker(line, chrMap);
      
      const dialogueLines: string[] = [];
      let nextTarget: string | null = null;
      let actCommands: Record<string, ActValue> = {};
      let presentationCommands: PresentationCue = {};
      let thought = '';
      i++;
      
      while (i < lines.length) {
        const nextLine = lines[i].trim();
        // 遇到下一个命令或新场景时停止
        if (isSpeakerMarkerLine(nextLine) || nextLine.startsWith('__CHOICE_') || nextLine.startsWith('# ')) {
          break;
        }
        // 检查 thought
        const thoughtMatch = nextLine.match(/<conception>([\s\S]*?)<\/conception>/);
        if (thoughtMatch) {
          thought = thoughtMatch[1].trim();
          i++;
          continue;
        }

        // 检查 @next (允许后面跟标签并忽略)
        const nextMatch = nextLine.match(/^@next\s+([^\s<]+)/);
        if (nextMatch) {
          nextTarget = nextMatch[1].trim();
          i++;
          continue;
        }
        
        // 检查 @act。旧视觉键只做容错消费，不再迁移到演出字段。
        const actMatch = nextLine.match(/^@act\s+(\w+):([^<]+)/);
        if (actMatch) {
          const key = actMatch[1].trim();
          let value: ActValue = actMatch[2].trim();
          if (value.includes(',')) {
            value = value.split(',').map(v => v.trim());
          }
          if (!['bg', 'sprite'].includes(key.toLowerCase())) {
            actCommands[key] = value;
          }
          i++;
          continue;
        }

        // Web 专用演出提示使用独立协议，不与 Unity 通用行为节点混用。
        const presentationMatch = nextLine.match(/^@presentation\s+(\w+):([^<]+)/i);
        if (presentationMatch) {
          const key = presentationMatch[1].trim().toLowerCase();
          let value: ActValue = presentationMatch[2].trim();
          if (key !== 'illustration_prompt' && value.includes(',')) {
            value = value.split(',').map(v => v.trim());
          }
          presentationCommands[key] = value;
          i++;
          continue;
        }

        // 未识别或已废弃的指令静默忽略，禁止混入对白正文。
        if (nextLine.startsWith('@')) {
          i++;
          continue;
        }
        
        // 过滤掉行内残留的标签
        const cleanLine = nextLine.replace(/<\/?choice>|<\/?opt(\s+text="[^"]+")?>/g, '').trim();
        if (cleanLine) {
          dialogueLines.push(cleanLine);
        }
        i++;
      }
      
      if (dialogueLines.length > 0) {
        dialogueLines.forEach((lineText, index) => {
          const node: ArcDialogueNode = {
            id: state.idCounter++,
            chr,
            speaker,
            txt: lineText
          };
          
          if (index === 0) {
            if (Object.keys(presentationCommands).length > 0) node.presentation = presentationCommands;
            if (Object.keys(actCommands).length > 0) node.act = actCommands;
            if (thought) node.thought = thought;
          }
          
          if (index === dialogueLines.length - 1) {
            if (nextTarget) node.next = nextTarget;
          }
          
          dialogues.push(node);
        });
      } else if (
        Object.keys(presentationCommands).length > 0 ||
        Object.keys(actCommands).length > 0 ||
        nextTarget ||
        thought
      ) {
        const node: ArcDialogueNode = {
          id: state.idCounter++,
          chr,
          speaker,
          txt: ''
        };
        if (Object.keys(presentationCommands).length > 0) node.presentation = presentationCommands;
        if (Object.keys(actCommands).length > 0) node.act = actCommands;
        if (nextTarget) node.next = nextTarget;
        if (thought) node.thought = thought;
        dialogues.push(node);
      }
      continue;
    }
    
    i++;
  }
  
  return dialogues;
}

/**
 * 提取所有 <choice> 块并用占位符替换
 */
function extractChoiceBlocks(text: string) {
  const choiceBlocks: string[] = [];
  let processedText = text;
  let match;
  
  // 递归提取，处理嵌套
  while ((match = findOutermostChoice(processedText)) !== null) {
    const placeholder = `__CHOICE_${choiceBlocks.length}__`;
    choiceBlocks.push(match.content);
    processedText = processedText.slice(0, match.start) + placeholder + processedText.slice(match.end);
  }
  
  return { processedText, choiceBlocks };
}

/**
 * 查找最外层的 <choice> 块
 */
function findOutermostChoice(text: string) {
  const startTag = '<choice>';
  const endTag = '</choice>';
  
  const startIndex = text.indexOf(startTag);
  if (startIndex === -1) return null;
  
  let depth = 1;
  let pos = startIndex + startTag.length;
  
  while (pos < text.length && depth > 0) {
    const nextStart = text.indexOf(startTag, pos);
    const nextEnd = text.indexOf(endTag, pos);
    
    if (nextEnd === -1) break;
    
    if (nextStart !== -1 && nextStart < nextEnd) {
      depth++;
      pos = nextStart + startTag.length;
    } else {
      depth--;
      if (depth === 0) {
        return {
          start: startIndex,
          end: nextEnd + endTag.length,
          content: text.slice(startIndex + startTag.length, nextEnd)
        };
      }
      pos = nextEnd + endTag.length;
    }
  }
  
  return null;
}

/**
 * 解析选项块内容
 */
function parseChoiceBlock(
  choiceContent: string,
  state: ParserState,
  chrMap: Record<string | number, string> = {}
) {
  const options: ArcOptionNode[] = [];
  
  // 更精确的 opt 匹配
  const optBlocks = extractOptBlocks(choiceContent);
  
  let optSeq = 1;
  for (const opt of optBlocks) {
    const optionNode: ArcOptionNode = {
      optn: opt.text,
      dia: [],
      __oid: `oid-${state.idCounter}-${optSeq++}` // 分配稳定 ID
    };
    
    // 递归解析选项内的内容
    const innerDialogues = parseDialogueContent(opt.content, state, chrMap);
    
    optionNode.dia = innerDialogues;
    options.push(optionNode);
  }
  
  return { options };
}

/**
 * 提取顶层 <opt> 块，忽略嵌套在 <choice> 中的 <opt>
 */
function extractOptBlocks(content) {
  const blocks: Array<{ text: string; content: string }> = [];
  const optStartRegex = /<opt\s+text="([^"]+)">/g;
  let match;
  
  while ((match = optStartRegex.exec(content)) !== null) {
    const startIndex = match.index;
    const text = match[1];
    const contentStart = startIndex + match[0].length;
    
    // 检查此 <opt> 是否嵌套在 <choice> 中
    const prefix = content.slice(0, startIndex);
    const openChoices = (prefix.match(/<choice>/g) || []).length;
    const closeChoices = (prefix.match(/<\/choice>/g) || []).length;
    
    if (openChoices !== closeChoices) {
      // 这是一个嵌套在 <choice> 内部的 <opt>，跳过它
      continue;
    }

    // 寻找匹配的 </opt>，同样需要处理嵌套
    let depth = 1;
    let searchPos = contentStart;
    let contentEnd = content.length;
    
    while (searchPos < content.length) {
      const nextOpen = content.indexOf('<opt', searchPos);
      const nextClose = content.indexOf('</opt>', searchPos);
      
      if (nextClose === -1) break;
      
      // 如果在下一个 </opt> 之前发现了另一个 <opt>，说明有嵌套
      if (nextOpen !== -1 && nextOpen < nextClose) {
        const fullOpenMatch = content.slice(nextOpen).match(/<opt\s+text="[^"]+">/);
        if (fullOpenMatch && content.slice(nextOpen).startsWith(fullOpenMatch[0])) {
          depth++;
          searchPos = nextOpen + fullOpenMatch[0].length;
          continue;
        }
      }
      
      depth--;
      if (depth === 0) {
        contentEnd = nextClose;
        break;
      }
      searchPos = nextClose + '</opt>'.length;
    }
    
    blocks.push({
      text,
      content: content.slice(contentStart, contentEnd).trim()
    });
    
    // 将正则索引移动到此 opt 结束之后，避免找到其内部的嵌套 opt
    optStartRegex.lastIndex = contentEnd + '</opt>'.length;
  }
  
  return blocks;
}

/**
 * 将内部数据结构序列化为 .arc 格式
 * @param {Array} scenes - 场景数组
 * @param {Object} chrMap - 角色卡隐藏绑定表（仅用于把运行时旧字段渲染成可读说话人）
 * @returns {string} .arc 格式文本
 */
export function serializeToArc(scenes: ArcScene[], chrMap: Record<string | number, string> = {}) {
  const lines: string[] = [];
  
  for (const scene of scenes) {
    // 场景标题
    lines.push(`# ${scene.scene}`);
    
    // @guide
    if (scene.guide) {
      lines.push(`@guide ${scene.guide}`);
    }

    // @intro（场景引言）
    if (scene.intro) {
      const introText = String(scene.intro).trim();
      if (introText) {
        const introLines = introText.split('\n');
        if (introLines.length === 1) {
          lines.push(`@intro ${introLines[0]}`);
        } else {
          lines.push(`@intro`);
          lines.push(...introLines);
        }
      }
    }

    // thought
    if (scene.thought) {
      lines.push(`<conception>`);
      lines.push(scene.thought);
      lines.push(`</conception>`);
    }

    if (scene.button_text) {
      lines.push(`@meta button_text:${scene.button_text}`);
    }
    if (scene.trigger_event) {
      lines.push(`@meta trigger_event:${scene.trigger_event}`);
    }
    if (scene.priority) {
      lines.push(`@meta priority:${scene.priority}`);
    }
    if (scene.once_key) {
      lines.push(`@meta once_key:${scene.once_key}`);
    }
    if (scene.conditions !== undefined && scene.conditions !== null) {
      lines.push(`@meta conditions:${JSON.stringify(scene.conditions)}`);
    }
    if (scene.effects !== undefined && scene.effects !== null) {
      lines.push(`@meta effects:${JSON.stringify(scene.effects)}`);
    }
    if (scene.hiden !== undefined) {
      lines.push(`@meta hiden:${String(!!scene.hiden)}`);
    }
    
    lines.push('');
    
    // 对话内容
    if (scene.dia && scene.dia.length > 0) {
      const diaLines = serializeDialogues(scene.dia, chrMap, 0);
      lines.push(...diaLines);
    }
    
    lines.push('');
  }
  
  return lines.join('\n');
}

/**
 * 序列化对话数组
 */
function serializeDialogues(dialogues: ArcDialogueNode[], chrMap: Record<string | number, string>, indent: number) {
  const lines: string[] = [];
  const indentStr = '  '.repeat(indent);
  
  for (const d of dialogues) {
    lines.push(`${indentStr}${formatSpeakerMarker(d.chr, d.speaker, chrMap)}`);
    if (d.thought) {
      lines.push(`${indentStr}<conception>${d.thought}</conception>`);
    }
    lines.push(`${indentStr}${d.txt}`);

    // Web 专用演出提示与通用行为分离，Unity SDK 会统一忽略该节点字段。
    if (d.presentation && Object.keys(d.presentation).length > 0) {
      for (const [key, value] of Object.entries(d.presentation)) {
        if (value === undefined || value === null || value === '') continue;
        const valStr = Array.isArray(value) ? value.join(',') : value;
        lines.push(`${indentStr}@presentation ${key}:${valStr}`);
      }
    }

    // @next
    if (d.next) {
      lines.push(`${indentStr}@next ${d.next}`);
    }

    // @act
    if (d.act && Object.keys(d.act).length > 0) {
      for (const [key, value] of Object.entries(d.act)) {
        if (['bg', 'sprite'].includes(key.toLowerCase())) continue;
        const valStr = Array.isArray(value) ? value.join(',') : value;
        lines.push(`${indentStr}@act ${key}:${valStr}`);
      }
    }

    lines.push('');
    
    // 选项
    if (d.opt && d.opt.length > 0) {
      lines.push(`${indentStr}<choice>`);
      for (const opt of d.opt) {
        lines.push(`${indentStr}  <opt text="${opt.optn}">`);
        if (opt.dia && opt.dia.length > 0) {
          const optLines = serializeDialogues(opt.dia, chrMap, indent + 2);
          lines.push(...optLines);
        }
        lines.push(`${indentStr}  </opt>`);
      }
      lines.push(`${indentStr}</choice>`);
      lines.push('');
    }
  }
  
  return lines;
}
