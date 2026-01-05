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
export function parseArc(arcText) {
  const scenes = [];
  const state = { idCounter: 1 };
  
  // 按场景标题分割（# 开头的行）
  const sceneBlocks = splitByScenes(arcText);
  
  for (const block of sceneBlocks) {
    const scene = parseSceneBlock(block, state);
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
function parseSceneBlock(blockText, state) {
  // 提取场景名（# 标题）
  const titleMatch = blockText.match(/^#\s+(.+)$/m);
  if (!titleMatch) return null;
  
  const sceneName = titleMatch[1].trim();
  
  // 提取 @guide
  const guideMatch = blockText.match(/^@guide\s+(.+)$/m);
  const guide = guideMatch ? guideMatch[1].trim() : '';
  
  // 提取 <thought> 块（每个场景最多一个）
  const thoughtMatches = [...blockText.matchAll(/<thought>([\s\S]*?)<\/thought>/g)];
  if (thoughtMatches.length > 1) {
    throw new Error(`ARC 格式错误：场景 "${sceneName}" 内包含多个 <thought> 块（每个场景最多一个）。`);
  }
  const thought = thoughtMatches.length === 1 ? (thoughtMatches[0][1] || '').trim() : '';
  
  // 移除 <thought> 块以便后续解析正文
  const cleanedText = blockText.replace(/<thought>[\s\S]*?<\/thought>/g, '');

  // 提取 @intro（场景引言）并从正文中移除
  const { intro, text: withoutIntroText } = extractIntroBlock(cleanedText);
  
  // 解析对话内容
  const dia = parseDialogueContent(withoutIntroText, state);
  
  return {
    scene: sceneName,
    guide: guide,
    intro: intro || '',
    thought: thought || '',
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
    if (trimmed.startsWith('@guide')) return true;
    if (trimmed.startsWith('<choice')) return true;
    if (trimmed.startsWith('<thought>')) return true;
    // 仅支持 [ID] 格式，旁白统一为 [-1]
    if (trimmed.match(/^\[-?\d+\]$/)) return true;
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
function parseDialogueContent(text, state = { idCounter: 1 }) {
  const dialogues = [];
  
  // 先处理选项块，替换为占位符
  const { processedText, choiceBlocks } = extractChoiceBlocks(text);
  
  // 按行解析
  const lines = processedText.split('\n');
  let i = 0;
  
  while (i < lines.length) {
    const line = lines[i].trim();
    
    // 跳过空行、标题行、@guide行
    if (!line || line.startsWith('#') || line.startsWith('@guide') || line.startsWith('@intro') || line.startsWith('<thought>')) {
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
        const options = parseChoiceBlock(choiceBlock, state);
        if (dialogues.length > 0) {
          dialogues[dialogues.length - 1].opt = options.options;
        }
      }
      i++;
      continue;
    }
    
    // 匹配对话/旁白标识符 [ID]
    const chrMatch = line.match(/^\[(-?\d+)\]$/);
    
    if (chrMatch) {
      let chrId = parseInt(chrMatch[1]);
      
      const dialogueLines = [];
      let nextTarget = null;
      let actCommands = {};
      let thought = '';
      i++;
      
      while (i < lines.length) {
        const nextLine = lines[i].trim();
        // 遇到下一个命令或新场景时停止
        if (nextLine.match(/^\[-?\d+\]$/) || nextLine.startsWith('__CHOICE_') || nextLine.startsWith('# ')) {
          break;
        }
        // 检查 thought
        const thoughtMatch = nextLine.match(/<thought>([\s\S]*?)<\/thought>/);
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
        
        // 检查 @act (允许后面跟标签并忽略)
        const actMatch = nextLine.match(/^@act\s+(\w+):([^<]+)/);
        if (actMatch) {
          const key = actMatch[1].trim();
          let value = actMatch[2].trim();
          if (value.includes(',')) {
            value = value.split(',').map(v => v.trim());
          }
          actCommands[key] = value;
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
          const node = {
            id: state.idCounter++,
            chr: chrId,
            txt: lineText
          };
          
          if (index === 0) {
            if (Object.keys(actCommands).length > 0) node.act = actCommands;
            if (thought) node.thought = thought;
          }
          
          if (index === dialogueLines.length - 1) {
            if (nextTarget) node.next = nextTarget;
          }
          
          dialogues.push(node);
        });
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
function parseChoiceBlock(choiceContent, state) {
  const options = [];
  
  // 更精确的 opt 匹配
  const optBlocks = extractOptBlocks(choiceContent);
  
  let optSeq = 1;
  for (const opt of optBlocks) {
    const optionNode = {
      optn: opt.text,
      dia: [],
      __oid: `oid-${state.idCounter}-${optSeq++}` // 分配稳定 ID
    };
    
    // 递归解析选项内的内容
    const innerDialogues = parseDialogueContent(opt.content, state);
    
    optionNode.dia = innerDialogues;
    options.push(optionNode);
  }
  
  return { options };
}

/**
 * 提取顶层 <opt> 块，忽略嵌套在 <choice> 中的 <opt>
 */
function extractOptBlocks(content) {
  const blocks = [];
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
 * @param {Object} chrMap - 角色ID到名称的映射（可选，用于注释）
 * @returns {string} .arc 格式文本
 */
export function serializeToArc(scenes, chrMap = {}) {
  const lines = [];
  
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
      lines.push(`<thought>`);
      lines.push(scene.thought);
      lines.push(`</thought>`);
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
    // 旁白 (统一使用 [-1])
    if (d.chr === -1 || d.chr === null || d.chr === undefined) {
      lines.push(`${indentStr}[-1]`);
      if (d.thought) {
        lines.push(`${indentStr}<thought>${d.thought}</thought>`);
      }
      lines.push(`${indentStr}${d.txt}`);
      lines.push('');
    } else {
      // 角色对话
      lines.push(`${indentStr}[${d.chr}]`);
      if (d.thought) {
        lines.push(`${indentStr}<thought>${d.thought}</thought>`);
      }
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
