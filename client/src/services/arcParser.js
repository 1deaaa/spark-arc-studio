/**
 * ARC Format Parser
 * 
 * 将 .arc 格式的剧本文本解析为内部数据结构（兼容现有 .story JSON 格式）
 * 
 * .arc 格式设计为 LLM 友好的创作格式，解析后转换为程序可用的结构化数据
 */

/**
 * 解析 .arc 文本为场景数组
 * @param {string} arcText - .arc 格式的原始文本
 * @returns {Array} 解析后的场景数组，兼容 .story JSON 格式
 */
export function parseArc(arcText) {
  const scenes = [];
  
  // 按场景标题分割（# 开头的行）
  const sceneBlocks = splitByScenes(arcText);
  
  for (const block of sceneBlocks) {
    const scene = parseSceneBlock(block);
    if (scene) {
      scenes.push(scene);
    }
  }
  
  return scenes;
}

/**
 * 将文本按场景标题分割
 */
function splitByScenes(text) {
  const lines = text.split('\n');
  const blocks = [];
  let currentBlock = [];
  
  for (const line of lines) {
    if (line.match(/^#\s+/) && currentBlock.length > 0) {
      blocks.push(currentBlock.join('\n'));
      currentBlock = [line];
    } else {
      currentBlock.push(line);
    }
  }
  
  if (currentBlock.length > 0) {
    blocks.push(currentBlock.join('\n'));
  }
  
  return blocks;
}

/**
 * 解析单个场景块
 */
function parseSceneBlock(blockText) {
  const lines = blockText.split('\n');
  
  // 提取场景名（# 标题）
  const titleMatch = blockText.match(/^#\s+(.+)$/m);
  if (!titleMatch) return null;
  
  const sceneName = titleMatch[1].trim();
  
  // 提取 @cap
  const capMatch = blockText.match(/^@cap\s+(.+)$/m);
  const cap = capMatch ? capMatch[1].trim() : '';
  
  // 移除 <thought> 块（AI思维链，不进入最终数据）
  const cleanedText = blockText.replace(/<thought>[\s\S]*?<\/thought>/g, '');

  // 提取 @intro（场景引言）并从正文中移除，避免被当成对话文本
  const { intro, text: withoutIntroText } = extractIntroBlock(cleanedText);
  
  // 解析对话内容
  const dia = parseDialogueContent(withoutIntroText);
  
  return {
    scene: sceneName,
    cap: cap,
    intro: intro || '',
    dia: dia
  };
}

/**
 * 提取 @intro 块（支持单行与多行），并返回移除后的文本
 */
function extractIntroBlock(text) {
  const lines = text.split('\n');
  const outputLines = [];
  const introLines = [];
  let inIntro = false;

  const isNextElementStart = (trimmed) => {
    if (!trimmed) return false;
    if (trimmed.startsWith('#')) return true;
    if (trimmed.startsWith('@cap')) return true;
    if (trimmed.startsWith('<choice')) return true;
    if (trimmed.startsWith('<thought>')) return true;
    if (trimmed === '(旁白)') return true;
    if (trimmed.match(/^\[\d+\]$/)) return true;
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

/**
 * 解析对话内容（包括选项分支）
 */
function parseDialogueContent(text) {
  const dialogues = [];
  let idCounter = 1;
  
  // 先处理选项块，替换为占位符
  const { processedText, choiceBlocks } = extractChoiceBlocks(text);
  
  // 按行解析
  const lines = processedText.split('\n');
  let i = 0;
  
  while (i < lines.length) {
    const line = lines[i].trim();
    
    // 跳过空行、标题行、@cap行
    if (!line || line.startsWith('#') || line.startsWith('@cap') || line.startsWith('@intro') || line.startsWith('<thought>')) {
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
        const options = parseChoiceBlock(choiceBlock, idCounter);
        if (dialogues.length > 0) {
          dialogues[dialogues.length - 1].opt = options.options;
          idCounter = options.nextId;
        }
      }
      i++;
      continue;
    }
    
    // 旁白
    if (line === '(旁白)') {
      const narrationLines = [];
      i++;
      while (i < lines.length) {
        const nextLine = lines[i].trim();
        if (!nextLine || nextLine.match(/^\[\d+\]$/) || nextLine === '(旁白)' || nextLine.startsWith('__CHOICE_')) {
          break;
        }
        narrationLines.push(nextLine);
        i++;
      }
      if (narrationLines.length > 0) {
        dialogues.push({
          id: idCounter++,
          chr: -1, // -1 表示旁白
          txt: narrationLines.join('\n')
        });
      }
      continue;
    }
    
    // 角色对话 [数字]
    const chrMatch = line.match(/^\[(\d+)\]$/);
    if (chrMatch) {
      const chrId = parseInt(chrMatch[1]);
      const dialogueLines = [];
      let nextTarget = null;
      let actCommands = {};
      i++;
      
      while (i < lines.length) {
        const nextLine = lines[i].trim();
        if (!nextLine || nextLine.match(/^\[\d+\]$/) || nextLine === '(旁白)' || nextLine.startsWith('__CHOICE_')) {
          break;
        }
        
        // 检查 @next
        const nextMatch = nextLine.match(/^@next\s+(.+)$/);
        if (nextMatch) {
          nextTarget = nextMatch[1].trim();
          i++;
          continue;
        }
        
        // 检查 @act（虽然AI不生成，但解析器要支持人工添加的）
        const actMatch = nextLine.match(/^@act\s+(\w+):(.+)$/);
        if (actMatch) {
          const key = actMatch[1].trim();
          let value = actMatch[2].trim();
          // 尝试解析为数组或保持字符串
          if (value.includes(',')) {
            value = value.split(',').map(v => v.trim());
          }
          actCommands[key] = value;
          i++;
          continue;
        }
        
        dialogueLines.push(nextLine);
        i++;
      }
      
      if (dialogueLines.length > 0) {
        const node = {
          id: idCounter++,
          chr: chrId,
          txt: dialogueLines.join('\n')
        };
        if (nextTarget) {
          node.next = nextTarget;
        }
        if (Object.keys(actCommands).length > 0) {
          node.act = actCommands;
        }
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
function extractChoiceBlocks(text) {
  const choiceBlocks = [];
  let processedText = text;
  let match;
  
  // 使用非贪婪匹配提取最外层 choice（需要处理嵌套）
  const regex = /<choice>([\s\S]*?)<\/choice>/g;
  
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
function findOutermostChoice(text) {
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
function parseChoiceBlock(choiceContent, startId) {
  const options = [];
  let idCounter = startId;
  
  // 提取所有 <opt> 块
  const optRegex = /<opt\s+text="([^"]+)">([\s\S]*?)(?=<opt\s|$)/g;
  let match;
  
  // 更精确的 opt 匹配
  const optBlocks = extractOptBlocks(choiceContent);
  
  for (const opt of optBlocks) {
    const optionNode = {
      optn: opt.text,
      dia: []
    };
    
    // 递归解析选项内的内容
    const innerDialogues = parseDialogueContent(opt.content);
    
    // 更新 ID
    for (const d of innerDialogues) {
      d.id = idCounter++;
    }
    
    optionNode.dia = innerDialogues;
    options.push(optionNode);
  }
  
  return { options, nextId: idCounter };
}

/**
 * 提取 <opt> 块
 */
function extractOptBlocks(content) {
  const blocks = [];
  const optStartRegex = /<opt\s+text="([^"]+)">/g;
  const matches = [...content.matchAll(optStartRegex)];
  
  for (let i = 0; i < matches.length; i++) {
    const match = matches[i];
    const text = match[1];
    const startPos = match.index + match[0].length;
    
    // 找到对应的结束位置（下一个 <opt> 或 </choice>）
    let endPos;
    if (i < matches.length - 1) {
      endPos = matches[i + 1].index;
    } else {
      // 最后一个 opt，找到末尾
      endPos = content.length;
    }
    
    // 移除末尾的 </opt> 如果存在
    let optContent = content.slice(startPos, endPos);
    const closeOptIndex = optContent.lastIndexOf('</opt>');
    if (closeOptIndex !== -1) {
      optContent = optContent.slice(0, closeOptIndex);
    }
    
    blocks.push({ text, content: optContent.trim() });
  }
  
  return blocks;
}

/**
 * 将内部数据结构序列化为 .arc 格式
 * @param {Array} scenes - 场景数组
 * @param {Object} chrMap - 角色ID到名称的映射（可选，用于注释）
 * @returns {string} .arc 格式文本
 */
export function serializeToArc(scenes, chrMap = {}) {
  const lines = [];
  
  for (const scene of scenes) {
    // 场景标题
    lines.push(`# ${scene.scene}`);
    
    // @cap
    if (scene.cap) {
      lines.push(`@cap ${scene.cap}`);
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
function serializeDialogues(dialogues, chrMap, indent) {
  const lines = [];
  const indentStr = '  '.repeat(indent);
  
  for (const d of dialogues) {
    // 旁白
    if (d.chr === -1 || d.chr === null || d.chr === undefined) {
      lines.push(`${indentStr}(旁白)`);
      lines.push(`${indentStr}${d.txt}`);
      lines.push('');
    } else {
      // 角色对话
      lines.push(`${indentStr}[${d.chr}]`);
      lines.push(`${indentStr}${d.txt}`);
      
      // @next
      if (d.next) {
        lines.push(`${indentStr}@next ${d.next}`);
      }
      
      // @act
      if (d.act && Object.keys(d.act).length > 0) {
        for (const [key, value] of Object.entries(d.act)) {
          const valStr = Array.isArray(value) ? value.join(',') : value;
          lines.push(`${indentStr}@act ${key}:${valStr}`);
        }
      }
      
      lines.push('');
    }
    
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

/**
 * 检测文件内容是 .arc 还是 .story (JSON)
 * @param {string} content - 文件内容
 * @returns {'arc' | 'json' | 'unknown'}
 */
export function detectFormat(content) {
  const trimmed = content.trim();
  
  // JSON 格式以 [ 或 { 开头
  if (trimmed.startsWith('[') || trimmed.startsWith('{')) {
    try {
      JSON.parse(trimmed);
      return 'json';
    } catch {
      // 不是有效 JSON，可能是 arc
    }
  }
  
  // ARC 格式以 # 开头或包含特征标记
  if (trimmed.startsWith('#') || trimmed.includes('(旁白)') || trimmed.match(/^\[\d+\]/m)) {
    return 'arc';
  }
  
  return 'unknown';
}

export default {
  parseArc,
  serializeToArc,
  detectFormat
};
