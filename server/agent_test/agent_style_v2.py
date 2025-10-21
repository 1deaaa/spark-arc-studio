from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import DashScopeEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
import json
import os
import sys
import io
import time
import re
from pathlib import Path
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

# 添加父目录到 Python 路径以支持导入
sys.path.insert(0, str(Path(__file__).parent.parent))
from llm_mgr import AIManager
# 设置stdout编码为UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 初始化模型
llm = AIManager().get_user_llm()
embeddings = DashScopeEmbeddings(
    dashscope_api_key=os.getenv("ALIYUN_API_KEY"),
    model="text-embedding-v4",
)

# 向量库路径配置
VECTOR_STORE_BASE_PATH = Path("author_style_db")
VECTOR_STORE_BASE_PATH.mkdir(exist_ok=True)
STYLE_FILES_PATH = Path("author_styles")
STYLE_FILES_PATH.mkdir(exist_ok=True)


# ==================== 数据类定义 ====================

@dataclass
class ContentChunk:
    """文本块数据类"""
    text: str
    metadata: Dict[str, Any]


@dataclass
class AgentAnalysisResult:
    """Agent分析结果"""
    agent_name: str
    dimensions: List[str]
    analysis: Dict[str, Any]
    examples: List[str]
    success: bool
    error: str = None

# ==================== 智能文本分块器 ====================

class SmartTextChunker:
    """
    语义保持型文本分块器
    策略：
    1. 保持句子完整性（3-5个完整句子为一块）
    2. 合理的chunk大小（300-500字符）
    3. 适当重叠避免上下文丢失
    4. 不做类型预判，让embedding模型自己理解
    """
    
    def __init__(self, chunk_size=400, chunk_overlap=80):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk_text(self, full_text: str, author_id: str) -> List[ContentChunk]:
        """
        基于句子的语义分块
        """
        chunks = []
        
        # 按段落分割
        paragraphs = [p.strip() for p in full_text.split('\n') if p.strip()]
        
        for para_idx, paragraph in enumerate(paragraphs):
            # 按句子分割（保持完整句子，包括标点）
            sentences = re.split(r'([。！？；.!?;])', paragraph)
            sentences = [''.join(sentences[i:i+2]).strip() for i in range(0, len(sentences)-1, 2) if sentences[i].strip()]
            
            current_chunk = ""
            
            for sentence in sentences:
                # 尝试添加句子到当前chunk
                test_chunk = current_chunk + sentence
                
                # 如果超过大小限制，保存当前chunk并开始新chunk
                if len(test_chunk) > self.chunk_size and current_chunk:
                    chunks.append(ContentChunk(
                        text=current_chunk.strip(),
                        metadata={
                            "author_id": author_id,
                            "para_idx": para_idx,
                            "char_count": len(current_chunk),
                            "sentence_count": current_chunk.count('。') + current_chunk.count('！') + current_chunk.count('？')
                        }
                    ))
                    # 保留overlap部分
                    if len(current_chunk) > self.chunk_overlap:
                        overlap_text = current_chunk[-self.chunk_overlap:]
                        # 找到最近的句子边界
                        last_period = max(overlap_text.rfind('。'), overlap_text.rfind('！'), overlap_text.rfind('？'))
                        if last_period > 0:
                            current_chunk = overlap_text[last_period+1:] + sentence
                        else:
                            current_chunk = sentence
                    else:
                        current_chunk = sentence
                else:
                    current_chunk = test_chunk
            
            # 添加剩余内容
            if current_chunk.strip():
                chunks.append(ContentChunk(
                    text=current_chunk.strip(),
                    metadata={
                        "author_id": author_id,
                        "para_idx": para_idx,
                        "char_count": len(current_chunk),
                        "sentence_count": current_chunk.count('。') + current_chunk.count('！') + current_chunk.count('？')
                    }
                ))
        
        print(f"✓ 语义分块完成: {len(chunks)} 个chunks")
        if chunks:
            print(f"  - 平均chunk大小: {sum(c.metadata['char_count'] for c in chunks) // len(chunks)} 字符")
            print(f"  - 平均句子数: {sum(c.metadata['sentence_count'] for c in chunks) / len(chunks):.1f} 句/chunk")
        
        return chunks


# ==================== 工具函数 ====================

def get_style_filepath(author_id: str) -> Path:
    """构建作者风格文件的路径"""
    return STYLE_FILES_PATH / f"{author_id}.json"

def get_vector_store_path(author_id: str) -> Path:
    """获取作者专属向量库路径"""
    return VECTOR_STORE_BASE_PATH / author_id

def load_style_profile_from_file(author_id: str) -> Dict | None:
    """从本地文件加载作者风格内容"""
    filepath = get_style_filepath(author_id)
    if not filepath.exists():
        print(f"风格文件不存在: {filepath}")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"从文件 {filepath} 加载风格失败: {e}")
        return None

def load_author_vector_store(author_id: str) -> FAISS | None:
    """加载作者专属向量库"""
    vs_path = get_vector_store_path(author_id)
    if not vs_path.exists():
        return None
    try:
        return FAISS.load_local(str(vs_path), embeddings, allow_dangerous_deserialization=True)
    except Exception as e:
        print(f"加载向量库失败: {e}")
        return None


# ==================== 专业Agent定义 ====================

class StyleAnalysisAgent:
    """风格分析Agent基类"""
    
    def __init__(self, name: str, dimensions: List[str]):
        self.name = name
        self.dimensions = dimensions
        self.llm = llm
    
    def retrieve_relevant_chunks(self, vector_store: FAISS, queries: List[str], k: int = 20) -> List[str]:
        """
        从向量库检索相关文本块
        通过精心设计的查询，让embedding模型自己找到相关内容
        
        Args:
            vector_store: FAISS向量库
            queries: 查询列表
            k: 每个查询返回的文档数量（默认20）
        """
        if not vector_store:
            return []
        
        all_docs = []
        seen_texts = set()
        
        print(f"  🔍 检索配置: {len(queries)}个查询 × {k}条/查询 = 理论最多{len(queries)*k}条")
        
        # 对每个查询进行检索
        for idx, query in enumerate(queries, 1):
            docs = vector_store.similarity_search(query, k=k)
            before_count = len(all_docs)
            for doc in docs:
                text = doc.page_content
                # 去重
                if text not in seen_texts:
                    all_docs.append(text)
                    seen_texts.add(text)
            after_count = len(all_docs)
            new_docs = after_count - before_count
            duplicate_docs = k - new_docs
            print(f"    - 查询{idx}: 获取{k}条, 新增{new_docs}条, 重复{duplicate_docs}条")
        
        final_count = len(all_docs[:k * len(queries)])
        print(f"  ✓ 去重后共{len(all_docs)}条, 返回前{final_count}条\n")
        
        return all_docs[:k * len(queries)]  # 返回足够多的样本
    
    def print_retrieved_chunks(self, chunks: List[str], agent_name: str):
        """打印检索到的文本片段"""
        print(f"\n{'='*60}")
        print(f"[{agent_name}] 检索到的RAG片段 (共{len(chunks)}个)")
        print(f"{'='*60}")
        
        # 统计chunk大小
        chunk_sizes = [len(chunk) for chunk in chunks]
        avg_size = sum(chunk_sizes) // len(chunks) if chunks else 0
        min_size = min(chunk_sizes) if chunks else 0
        max_size = max(chunk_sizes) if chunks else 0
        
        print(f"📊 大小统计: 平均{avg_size}字符, 最小{min_size}, 最大{max_size}")
        print(f"{'-'*60}")
        
        for i, chunk in enumerate(chunks, 1):
            # 显示前100个字符作为预览
            preview = chunk[:100].replace('\n', ' ')
            print(f"{i:2d}. {preview}... ({len(chunk)}字符)")
        print(f"{'='*60}\n")
    
    def analyze(self, vector_store: FAISS, author_id: str) -> AgentAnalysisResult:
        """执行分析（子类实现）"""
        raise NotImplementedError


class DialogueAgent(StyleAnalysisAgent):
    """对话系统分析Agent"""
    
    def __init__(self):
        super().__init__(
            name="DialogueAgent",
            dimensions=["dialogue_system"]
        )
    
    def analyze(self, vector_store: FAISS, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] 开始分析...")
            
            # 构造精准的检索查询 - 让embedding找到对话相关的片段
            queries = [
                "角色对话：「」『』\"\" 说道问答讲述",
                "人物说话交流：语气词、口头禅、说话方式",
                "对话场景：你我他她、反问疑问、对话标签",
                "对话动作：点头摇头、笑着说、叹气道、轻声细语",
                "对话情绪：愤怒喊叫、哭泣哽咽、冷笑嘲讽、温柔低语",
                "对话互动：打断插话、沉默不语、追问反问、附和应答",
                "称呼语：你我他她它、先生小姐、名字昵称、敬语谦语",
            ]
            
            # 检索相关片段（每个查询20个）
            all_examples = self.retrieve_relevant_chunks(vector_store, queries, k=20)
            
            # 打印检索到的片段
            self.print_retrieved_chunks(all_examples, self.name)
            
            if not all_examples:
                return AgentAnalysisResult(
                    agent_name=self.name,
                    dimensions=self.dimensions,
                    analysis={},
                    examples=[],
                    success=False,
                    error="未找到足够的对话样本"
                )
            
            # 构造分析prompt
            prompt = f"""
你是对话系统分析专家。基于以下对话样本，深度分析作者的对话风格特征。

【对话样本】
{chr(10).join([f"{i+1}. {ex}" for i, ex in enumerate(all_examples)])}

请从以下维度进行精确分析，输出JSON格式：
{{
  "dialogue_rhythm": "对话节奏特点（一问一答/大段独白/碎片交锋/快速对攻等）",
  "speech_pattern": "说话模式（省略主语/语气词/句尾习惯/口语化程度等）",
  "subtext_technique": "潜台词技巧（话中有话/欲言又止/反讽暗示/答非所问等）",
  "dialogue_tags": "对话标签风格（简洁的'说'/丰富动作描写/表情细节/省略标签等）",
  "tone_variation": "语气变化范围（温和到激烈的跨度/情绪起伏/音量语速标记）",
  "information_delivery": "信息传递方式（直接说明/暗示隐喻/逐步揭示/问答引导等）",
  "character_voice_diff": "角色语言分化度（不同角色是否有明显语言特征差异）",
  "dialogue_examples": ["提取3-5个最典型的对话片段（简短精炼）"]
}}

注意：
1. 所有描述必须具体、可操作、避免泛泛而谈
2. 提取的例句要去除人名等具体信息
3. 关注反复出现的特征模式
"""
            
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            # 提取JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(content)
            
            print(f"[{self.name}] ✓ 分析完成")
            
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis={"dialogue_system": analysis},
                examples=all_examples[:5],
                success=True
            )
            
        except Exception as e:
            print(f"[{self.name}] ✗ 分析失败: {e}")
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis={},
                examples=[],
                success=False,
                error=str(e)
            )


class MonologueAgent(StyleAnalysisAgent):
    """内心独白分析Agent"""
    
    def __init__(self):
        super().__init__(
            name="MonologueAgent",
            dimensions=["inner_monologue"]
        )
    
    def analyze(self, vector_store: FAISS, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] 开始分析...")
            
            # 精准查询：内心活动、思考、心理描写
            queries = [
                "内心想法：想心思、自言自语、心中暗道",
                "心理活动：回忆思考、情绪感受、潜意识",
                "自我对话：犹豫纠结、内心挣扎、心理独白",
                "记忆闪回：想起回忆、往事浮现、脑海中浮现",
                "情绪波动：心跳加速、胸口发闷、浑身颤抖、如释重负",
                "意识流动：恍惚走神、思绪飘远、念头闪过、灵光一现",
                "自我评判：责备自己、安慰自己、怀疑反思、自我认知",
            ]
            
            all_examples = self.retrieve_relevant_chunks(vector_store, queries, k=20)
            
            # 打印检索到的片段
            self.print_retrieved_chunks(all_examples, self.name)
            
            if not all_examples:
                return AgentAnalysisResult(
                    agent_name=self.name,
                    dimensions=self.dimensions,
                    analysis={},
                    examples=[],
                    success=False,
                    error="未找到足够的独白样本"
                )
            
            prompt = f"""
你是内心独白分析专家。基于以下独白样本，深度分析作者的内心独白风格。

【独白样本】
{chr(10).join([f"{i+1}. {ex}" for i, ex in enumerate(all_examples)])}

请从以下维度进行精确分析，输出JSON格式：
{{
  "thought_structure": "思维结构（线性逻辑/跳跃联想/意识流/反刍重复/碎片闪念等）",
  "inner_voice_tone": "内心声音色调（自我审视/安慰/谴责/哲思冥想/焦虑絮叨等）",
  "thought_depth": "思考深度层次（表层反应/深层剖析/潜意识涌现/元认知反思等）",
  "memory_flashback": "记忆闪回方式（突然插入/渐进唤起/片段式/场景重现等）",
  "emotion_thought_ratio": "情感与理性比例（感性主导/理性分析/交织并行等）",
  "self_dialogue": "自我对话模式（与自己争论/内心问答/否定肯定拉锯等）",
  "psychological_time": "心理时间感（时间凝滞/飞速流转/循环往复等）",
  "monologue_examples": ["提取3-5个典型内心独白片段"]
}}

注意：分析要具体、可操作，避免空泛描述。
"""
            
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(content)
            
            print(f"[{self.name}] ✓ 分析完成")
            
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis={"inner_monologue": analysis},
                examples=all_examples[:5],
                success=True
            )
            
        except Exception as e:
            print(f"[{self.name}] ✗ 分析失败: {e}")
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis={},
                examples=[],
                success=False,
                error=str(e)
            )


class NarrativeAgent(StyleAnalysisAgent):
    """叙事场景分析Agent（视角+场景+细节+时间）"""
    
    def __init__(self):
        super().__init__(
            name="NarrativeAgent",
            dimensions=["perspective_system", "scene_construction", "detail_craftsmanship", "temporal_architecture"]
        )
    
    def analyze(self, vector_store: FAISS, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] 开始分析...")
            
            # 精准查询：场景、环境、动作、细节、时间描写
            queries = [
                "场景描写：环境氛围、空间布局、光影色彩",
                "细节刻画：动作表情、微观细节、感官描写",
                "叙述视角：第一人称第三人称、全知视角、旁白叙述",
                "场景转换：时空变化、镜头切换、氛围营造",
                "环境元素：天气气候、季节时间、自然景观、室内布置",
                "感官体验：视觉听觉、嗅觉触觉、味觉温度、身体感受",
                "动作描写：走跑跳、拿放握、推拉扭、抬低俯仰",
                "微表情：眉眼口鼻、瞳孔嘴角、脸色神情、细微动作",
                "时间处理：回忆往事、闪回插叙、时间跳跃、过去现在",
                "时间标记：多久之前、几年后、那一天、当时此刻",
                "记忆描写：想起回忆、脑海浮现、记忆深处、遗忘铭记",
            ]
            
            all_examples = self.retrieve_relevant_chunks(vector_store, queries, k=20)
            
            # 打印检索到的片段
            self.print_retrieved_chunks(all_examples, self.name)
            
            if not all_examples:
                return AgentAnalysisResult(
                    agent_name=self.name,
                    dimensions=self.dimensions,
                    analysis={},
                    examples=[],
                    success=False,
                    error="未找到足够的叙事样本"
                )
            
            prompt = f"""
你是叙事场景分析专家。基于以下叙事样本，深度分析作者的叙事风格。

【叙事样本】
{chr(10).join([f"{i+1}. {ex}" for i, ex in enumerate(all_examples)])}

请从以下维度进行精确分析，输出JSON格式：
{{
  "perspective_system": {{
    "focalization": "聚焦模式（零聚焦全知/内聚焦单一/外聚焦行为/多重视角等）",
    "narrator_distance": "叙述者距离（亲密贴近/疏离冷静/忽远忽近等）",
    "commentary_style": "评论风格（不加评论/点到为止/深度剖析/戏谑调侃等）",
    "narrator_reliability": "叙述者可靠性（全知可靠/有限认知/主动误导/无意偏见等）"
  }},
  "scene_construction": {{
    "scene_opening": "场景开场方式（环境先行/对话切入/动作开始/氛围渲染等）",
    "atmosphere_building": "氛围营造手法（环境烘托/对话暗示/节奏控制/感官堆叠等）",
    "scene_transition": "场景转换技巧（硬切/淡入淡出/蒙太奇/视角引导/时空跳跃等）",
    "spatial_presentation": "空间呈现（全景到特写/特写到全景/平行空间/空间留白等）",
    "scene_rhythm": "场景节奏变化（紧张-舒缓交替/持续紧张/平稳流动/突然爆发等）"
  }},
  "detail_craftsmanship": {{
    "micro_expression": "微表情捕捉（眼神/嘴角/身体微动/呼吸变化等）",
    "environmental_detail": "环境细节选择（光影/气味声音/温度湿度/物品摆放等）",
    "action_granularity": "动作颗粒度（粗线条/精细分解/关键帧捕捉/慢镜头式等）",
    "sensory_hierarchy": "感官层次（主视觉辅听觉/全感官协同/特定感官强化等）",
    "detail_timing": "细节时机（对话中穿插/情绪转折点/氛围铺垫/悬念制造等）",
    "detail_examples": ["提取5-8个精彩细节描写片段"]
  }},
  "temporal_architecture": {{
    "time_layering": "时间分层（现在/回忆/预感/幻想如何交织/时态切换规律等）",
    "duration_distortion": "时长扭曲（1小时写5章vs10年一笔带过/时间伸缩比例等）",
    "memory_structure": "记忆结构（线性回忆/碎片拼贴/创伤性重复/选择性遗忘等）",
    "temporal_markers": "时间标记（季节变化/物件老化/身体衰老/技术更迭等）",
    "time_consciousness": "时间意识（对时间流逝的敏感度/永恒瞬间/时间焦虑/怀旧倾向等）"
  }}
}}

注意：分析要具体、可操作，体现视觉小说的特点。
"""
            
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(content)
            
            print(f"[{self.name}] ✓ 分析完成")
            
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis=analysis,
                examples=all_examples[:8],
                success=True
            )
            
        except Exception as e:
            print(f"[{self.name}] ✗ 分析失败: {e}")
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis={},
                examples=[],
                success=False,
                error=str(e)
            )


class LanguageAgent(StyleAnalysisAgent):
    """语言修辞分析Agent（语言+修辞+意象）"""
    
    def __init__(self):
        super().__init__(
            name="LanguageAgent",
            dimensions=["linguistic_texture", "language_style", "imagery_system"]
        )
    
    def analyze(self, vector_store: FAISS, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] 开始分析...")
            
            # 精准查询：修辞、意象、语言特色
            queries = [
                "修辞手法：比喻拟人、排比对比、夸张反复",
                "意象符号：光影雨雪、色彩季节、自然物象",
                "语言特色：文言白话、诗意散文、口语书面",
                "句式结构：长句短句、复句单句、特殊句式",
                "词汇风格：形容词动词、古典现代、特色用词",
                "比喻类型：像如同、仿佛好似、恰似犹如、隐喻暗喻",
                "色彩意象：红黄蓝绿、黑白灰、光暗影、色调冷暖",
                "自然意象：风雨雷电、花草树木、日月星辰、山川河流",
                "形容词特色：具体抽象、情感中性、程度强弱、新颖陈旧",
                "动词活力：静态动词、动作动词、心理动词、感官动词",
            ]
            
            all_examples = self.retrieve_relevant_chunks(vector_store, queries, k=20)
            
            # 打印检索到的片段
            self.print_retrieved_chunks(all_examples, self.name)
            
            if not all_examples:
                return AgentAnalysisResult(
                    agent_name=self.name,
                    dimensions=self.dimensions,
                    analysis={},
                    examples=[],
                    success=False,
                    error="未找到足够的语言样本"
                )
            
            prompt = f"""
你是语言修辞分析专家。基于以下语言样本，深度分析作者的语言风格和修辞特征。

【语言样本】
{chr(10).join([f"{i+1}. {ex}" for i, ex in enumerate(all_examples)])}

请从以下维度进行精确分析，输出JSON格式：
{{
  "linguistic_texture": {{
    "sentence_architecture": "句子建筑学（长短句比例/复句类型/排比递进转折等）",
    "lexical_signature": "词汇指纹（文学化/古典意味/现代口语/专业术语等）",
    "rhetoric_devices": "修辞手法库（具体列举：比喻类型/拟人/夸张/反复/对比/通感等）",
    "metaphor_quality": "比喻质量（意象新鲜度/本体喻体距离/避免陈词滥调等）",
    "verb_dynamics": "动词动态性（静态描写/动作捕捉/具体动词偏好等）",
    "language_examples": ["高频特色词汇15-20个", "典型句式5-8个", "独特修辞案例3-5个"]
  }},
  "language_style": {{
    "formality_level": "文白程度（半文半白/现代白话/诗化语言等）",
    "colloquial_degree": "口语化程度（书面语为主/口语化表达/对话感强等）",
    "poetic_quality": "诗意浓度（高度诗化/散文化诗意/质朴平实/理性克制等）",
    "language_innovation": "语言创新（新词创造/旧词新用/语法突破/文体实验等）"
  }},
  "imagery_system": {{
    "core_images": "核心意象群（列举15-20个高频意象：物象/自然/器物/色彩/声音等）",
    "metaphor_types": "比喻类型（自然物象喻情感/器物喻人生/色彩象征/空间隐喻等）",
    "sensory_focus": "感官侧重（视觉主导/听觉细腻/触觉嗅觉/综合通感等）",
    "symbol_system": "象征体系（光暗对比/季节更迭/物件象征/颜色系统等）",
    "imagery_examples": ["提取8-12个意象使用片段"]
  }}
}}

注意：
1. 词汇和意象分析要列举具体的词和意象，不要泛泛而谈
2. 修辞分析要有具体例子
3. 关注反复出现的语言模式
"""
            
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(content)
            
            print(f"[{self.name}] ✓ 分析完成")
            
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis=analysis,
                examples=all_examples[:10],
                success=True
            )
            
        except Exception as e:
            print(f"[{self.name}] ✗ 分析失败: {e}")
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis={},
                examples=[],
                success=False,
                error=str(e)
            )


class StructureAgent(StyleAnalysisAgent):
    """结构节奏分析Agent"""
    
    def __init__(self):
        super().__init__(
            name="StructureAgent",
            dimensions=["structural_breathing", "rhythm_control", "causality_web", "tension_mechanics"]
        )
    
    def analyze(self, vector_store: FAISS, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] 开始分析...")
            
            # 精准查询：结构、节奏、因果、张力
            queries = [
                "叙事节奏：快慢缓急、留白停顿、密度变化",
                "结构特点：倒叙插叙、多线并行、时间跳跃",
                "因果逻辑：伏笔呼应、动机行为、因果关系",
                "张力营造：悬念冲突、期待转折、情绪起伏",
                "时间处理：顺叙倒叙、闪回快进、时间跳跃、平行时空",
                "节奏标志：突然忽然、渐渐慢慢、瞬间刹那、良久许久",
                "转折信号：但是然而、却竟然、不料突然、谁知哪知",
                "悬念设置：疑问未解、神秘线索、预示暗示、故意隐瞒",
                "情绪积累：越来越、更加愈发、逐渐渐渐、一点点",
            ]
            
            all_examples = self.retrieve_relevant_chunks(vector_store, queries, k=20)
            
            # 打印检索到的片段
            self.print_retrieved_chunks(all_examples, self.name)
            
            if not all_examples:
                return AgentAnalysisResult(
                    agent_name=self.name,
                    dimensions=self.dimensions,
                    analysis={},
                    examples=[],
                    success=False,
                    error="未找到足够的结构样本"
                )
            
            prompt = f"""
你是结构节奏分析专家。基于以下文本样本，深度分析作者的结构和节奏特征。

【文本样本】
{chr(10).join([f"{i+1}. {ex}" for i, ex in enumerate(all_examples)])}

请从以下维度进行精确分析，输出JSON格式：
{{
  "structural_breathing": {{
    "information_flow": "信息流动（顺时线性/倒叙/插叙/碎片拼贴/多线交织等）",
    "density_modulation": "密度调制（何时密集轰炸/何时留白沉默/信息节制等）",
    "white_space_use": "留白艺术（大量留白/紧密铺陈/段间呼吸/沉默时刻）",
    "paragraph_rhythm": "段落节奏（短段急促/长段沉浸/长短交错/单句成段等）"
  }},
  "rhythm_control": {{
    "overall_pacing": "整体节奏（舒缓流淌/紧凑急促/张弛有度/前慢后快等）",
    "speed_variation": "节奏变速（何时加速/何时减速/转换标志/速度对比等）",
    "narrative_breath": "叙事呼吸（紧张后舒缓/高潮前压抑/留白节点/喘息时刻）"
  }},
  "causality_web": {{
    "causality_tightness": "因果紧密度（铁律因果/松散偶然/模糊关联/荒诞断裂等）",
    "hidden_causality": "隐性因果（表面巧合实则暗线/不动声色的必然等）",
    "motivation_logic": "动机逻辑（人物行为的内在动机链/欲望-行动-后果的合理性）"
  }},
  "tension_mechanics": {{
    "expectation_management": "期待管理（制造预期/延迟满足/颠覆预期/多重可能性）",
    "tension_release": "张力释放（何时宣泄/何时压抑/反高潮/多级释放）",
    "suspense_vs_surprise": "悬念与惊奇（让读者知道炸弹vs突然爆炸的平衡）"
  }}
}}

注意：分析要基于样本中的具体表现，不要凭空臆测。
"""
            
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(content)
            
            print(f"[{self.name}] ✓ 分析完成")
            
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis=analysis,
                examples=all_examples[:8],
                success=True
            )
            
        except Exception as e:
            print(f"[{self.name}] ✗ 分析失败: {e}")
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis={},
                examples=[],
                success=False,
                error=str(e)
            )


class EmotionThemeAgent(StyleAnalysisAgent):
    """情感主题分析Agent"""
    
    def __init__(self):
        super().__init__(
            name="EmotionThemeAgent",
            dimensions=["emotional_progression", "theme_tendency", "subtext_layer"]
        )
    
    def analyze(self, vector_store: FAISS, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] 开始分析...")
            
            # 精准查询：情感、主题、潜台词
            queries = [
                "情感表达：喜怒哀乐、情绪变化、感情描写",
                "主题思想：人生哲理、价值观念、核心主题",
                "潜台词：话外之音、言不由衷、弦外之音",
                "情感层次：真实虚假、压抑爆发、情感积累",
                "具体情绪：喜悦快乐、悲伤难过、愤怒生气、恐惧害怕、厌恶反感",
                "复杂情感：矛盾纠结、五味杂陈、百感交集、爱恨交织",
                "哲学主题：存在意义、时间记忆、身份认同、生死孤独",
                "潜台词标志：停顿沉默、转移话题、答非所问、欲言又止",
                "情感矛盾：表面内心、言行不一、真实掩饰、伪装真诚",
            ]
            
            all_examples = self.retrieve_relevant_chunks(vector_store, queries, k=20)
            
            # 打印检索到的片段
            self.print_retrieved_chunks(all_examples, self.name)
            
            if not all_examples:
                return AgentAnalysisResult(
                    agent_name=self.name,
                    dimensions=self.dimensions,
                    analysis={},
                    examples=[],
                    success=False,
                    error="未找到足够的情感主题样本"
                )
            
            prompt = f"""
你是情感主题分析专家。基于以下文本样本，深度分析作者的情感处理和主题倾向。

【文本样本】
{chr(10).join([f"{i+1}. {ex}" for i, ex in enumerate(all_examples)])}

请从以下维度进行精确分析，输出JSON格式：
{{
  "emotional_progression": {{
    "emotion_accumulation": "情绪积累方式（缓慢升温/压抑后爆发/波浪式起伏/持续高压等）",
    "emotional_peak": "情感高潮处理（克制收束/极致爆发/留白余韵/反高潮等）",
    "emotion_transition": "情绪转换（自然过渡/急转直下/复杂交织/延迟反应等）",
    "empathy_technique": "共情技巧（细节代入/身体感受描写/内心独白/普世情感等）",
    "emotional_authenticity": "情感真实性（避免过度煽情/符合人物逻辑/情绪复杂性等）"
  }},
  "theme_tendency": {{
    "main_themes": "核心主题（列举5-8个：存在焦虑/身份认同/时间记忆/孤独/成长等）",
    "value_orientation": "价值取向（个体主义/人文关怀/存在主义/理想主义等）",
    "life_attitude": "人生态度（悲观怀旧/积极向上/虚无飘渺/现实清醒/悲喜交织）",
    "moral_complexity": "道德复杂度（非黑即白/多元立场/处境伦理/价值冲突等）"
  }},
  "subtext_layer": {{
    "what_unsaid": "未说之言（故意省略的信息/留给读者推断的空间）",
    "contradictory_signals": "矛盾信号（言行不一/表里不符/微表情泄露）",
    "silence_eloquence": "沉默的雄辩（何时用沉默代替对话/对话中的停顿）",
    "irony_layers": "反讽层次（戏剧性反讽/语言反讽/情境反讽）",
    "subtext_examples": ["提取5-8个潜台词丰富的场景片段"]
  }}
}}

注意：情感和主题分析要基于文本实际表现，不要过度解读。
"""
            
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(content)
            
            print(f"[{self.name}] ✓ 分析完成")
            
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis=analysis,
                examples=all_examples[:8],
                success=True
            )
            
        except Exception as e:
            print(f"[{self.name}] ✗ 分析失败: {e}")
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis={},
                examples=[],
                success=False,
                error=str(e)
            )


class CharacterPlotAgent(StyleAnalysisAgent):
    """角色情节分析Agent"""
    
    def __init__(self):
        super().__init__(
            name="CharacterPlotAgent",
            dimensions=["character_portrayal", "plot_technique"]
        )
    
    def analyze(self, vector_store: FAISS, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] 开始分析...")
            
            # 精准查询：角色塑造和情节技巧
            queries = [
                "角色描写：外貌特征、性格特点、人物形象",
                "角色成长：变化发展、心理成长、性格转变",
                "角色关系：互动交流、关系变化、情感纠葛",
                "角色行为：动机目的、选择决定、行动反应",
                "情节转折：意外突变、反转惊喜、转机变化",
                "伏笔铺垫：暗示线索、前后呼应、埋伏笔",
                "冲突矛盾：对立冲突、内心挣扎、矛盾纠结",
                "悬念设置：疑问未解、神秘悬疑、引人入胜",
                "副线情节：支线剧情、次要情节、辅助线索",
            ]
            
            all_examples = self.retrieve_relevant_chunks(vector_store, queries, k=20)
            
            # 打印检索到的片段
            self.print_retrieved_chunks(all_examples, self.name)
            
            if not all_examples:
                return AgentAnalysisResult(
                    agent_name=self.name,
                    dimensions=self.dimensions,
                    analysis={},
                    examples=[],
                    success=False,
                    error="未找到足够的角色情节样本"
                )
            
            prompt = f"""
你是角色情节分析专家。基于以下文本样本，深度分析作者的角色塑造和情节技巧。

【文本样本】
{chr(10).join([f"{i+1}. {ex}" for i, ex in enumerate(all_examples)])}

请从以下维度进行精确分析，输出JSON格式：
{{
  "character_portrayal": {{
    "appearance_intro": "外貌介绍方式（集中描述/零散分布/他者视角/自我观察/不描写等）",
    "personality_reveal": "性格展现途径（行动展示为主/对话透露/内心独白/他人评价等）",
    "growth_tracking": "成长轨迹呈现（突变式/渐进式/循环反复/多线并行等）",
    "relationship_dynamics": "关系动态描写（对话中的张力/权力关系流转/亲密度变化等）",
    "character_consistency": "角色一致性（高度统一/复杂多面/前后矛盾作为特色等）",
    "backstory_reveal": "背景揭示策略（前置交代/逐步揭秘/对话中自然流露/关键时刻闪回等）",
    "character_examples": ["提取5-8个角色塑造片段"]
  }},
  "plot_technique": {{
    "foreshadowing_method": "伏笔布置（显性暗示/隐性埋伏/细节伏笔/对话伏笔/重复强化等）",
    "suspense_creation": "悬念制造（信息延迟/视角限制/误导/制造疑问/时间倒计时等）",
    "conflict_escalation": "冲突升级（层层递进/突然爆发/多线交织/内外冲突交替等）",
    "plot_point_handling": "情节点处理（突转/铺垫充分/意料之外情理之中/刻意反转等）",
    "subplot_weaving": "副线编织（与主线交织/平行发展/呼应对比/独立后汇合等）",
    "reversal_technique": "反转技巧（信息差反转/人物反转/价值反转/视角反转等）",
    "plot_examples": ["提取5-8个情节技巧运用片段"]
  }}
}}

注意：分析要基于样本中的具体表现，提供可操作的技巧描述。
"""
            
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(content)
            
            print(f"[{self.name}] ✓ 分析完成")
            
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis=analysis,
                examples=all_examples[:10],
                success=True
            )
            
        except Exception as e:
            print(f"[{self.name}] ✗ 分析失败: {e}")
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis={},
                examples=[],
                success=False,
                error=str(e)
            )


# ==================== 协调Agent ====================

class CoordinatorAgent:
    """协调Agent，整合各专业Agent的分析结果"""
    
    def __init__(self):
        self.llm = llm
    
    def integrate_results(self, results: List[AgentAnalysisResult]) -> Dict:
        """整合多个Agent的分析结果"""
        print("\n[CoordinatorAgent] 开始整合分析结果...")
        
        # 收集所有成功的分析
        successful_analyses = [r for r in results if r.success]
        
        if not successful_analyses:
            print("✗ 所有Agent均分析失败")
            return {}
        
        # 合并所有分析结果
        integrated = {
            "writing_style_analysis_framework": {},
            "_meta": {
                "framework_version": "3.0_multi_agent",
                "agents_used": [r.agent_name for r in successful_analyses],
                "analysis_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "applicable_genres": ["视觉小说", "游戏剧本", "互动叙事"],
                "usage_notes": [
                    "基于多Agent并行分析生成",
                    "每个维度由专业Agent独立分析",
                    "特别优化for视觉小说：对话+独白+旁白",
                    "避免AI通病：工业糖精/空降设定/情感快进"
                ]
            }
        }
        
        # 合并各Agent的分析
        for result in successful_analyses:
            integrated["writing_style_analysis_framework"].update(result.analysis)
        
        # 生成distinctive_features（总结性分析）
        print("\n[CoordinatorAgent] 生成总结性特征分析...")
        distinctive_features = self._synthesize_distinctive_features(results, integrated)
        if distinctive_features:
            integrated["writing_style_analysis_framework"]["distinctive_features"] = distinctive_features
        
        print(f"✓ 整合完成，包含 {len(successful_analyses)}/{len(results)} 个Agent的分析")
        
        return integrated
    
    def _synthesize_distinctive_features(self, results: List[AgentAnalysisResult], integrated_data: Dict) -> Dict:
        """基于所有Agent结果，综合生成作者的独特特征分析"""
        try:
            # 收集所有成功分析的examples
            all_examples = []
            for result in results:
                if result.success and result.examples:
                    all_examples.extend(result.examples[:3])  # 每个Agent取3个例子
            
            if not all_examples:
                return None
            
            # 构造综合分析prompt
            prompt = f"""
你是文学风格元分析专家。现在给你一份已经完成的多维度风格分析结果，请基于这些分析，提炼出作者最核心、最独特的风格特征。

【已完成的分析维度】
{json.dumps(integrated_data['writing_style_analysis_framework'], ensure_ascii=False, indent=2)[:3000]}
...(部分省略)

【代表性文本片段】
{chr(10).join([f"{i+1}. {ex[:150]}..." for i, ex in enumerate(all_examples[:15])])}

请从以下维度进行元分析，输出JSON格式：
{{
  "signature_style": "标志性特征（最能代表作者的10-15个独特风格要素：如特定句式癖好/偏爱意象/叙事习惯/语言标记等）",
  "influence_trace": "风格来源（如：可能受某流派/作家影响的痕迹/致敬/化用/反叛等，基于分析推测）",
  "innovation_point": "创新之处（如：独特的表达方式/新颖的结构尝试/突破性元素/实验性手法等）",
  "style_coherence": "风格一致性（如：各维度之间的协调度/是否形成统一风格/风格冲突点等）",
  "adaptability": "适应性分析（该风格最适合的题材/体裁/受众/创作场景等）",
  "potential_risks": "潜在风险（可能的重复套路/过度依赖/需要警惕的舒适区/易陷阱等）",
  "distinctive_summary": "独特性总结（用3-5句话概括这位作者最与众不同的地方）"
}}

注意：
1. 基于已有分析进行提炼，不要凭空创造
2. 要具体，避免"文笔优美""情感真挚"等空泛描述
3. 关注模式而非偶然
4. 给出可操作的风格指引
"""
            
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            distinctive = json.loads(content)
            
            print(f"[CoordinatorAgent] ✓ 独特特征分析完成")
            
            return distinctive
            
        except Exception as e:
            print(f"[CoordinatorAgent] ⚠ 独特特征分析失败: {e}")
            return None


# ==================== 核心功能函数 ====================

def _run_agent_analysis(author_id: str, vector_store: FAISS, style_filepath: Path, parallel: bool = False) -> Dict:
    """
    执行Agent分析并保存结果（内部函数）
    
    Args:
        author_id: 作者ID
        vector_store: FAISS向量库
        style_filepath: 风格文件保存路径
        parallel: 是否并行执行Agent（默认False，串行执行）
    """
    print("=" * 60)
    print(f"步骤: 多Agent {'并行' if parallel else '串行'}风格分析")
    print("=" * 60)
    
    # 初始化所有Agent
    agents = [
        DialogueAgent(),
        MonologueAgent(),
        NarrativeAgent(),
        CharacterPlotAgent(),
        LanguageAgent(),
        StructureAgent(),
        EmotionThemeAgent(),
    ]
    
    total_agents = len(agents)
    results = []
    
    if parallel:
        # 并行执行分析
        print(f"\n🚀 启动 {total_agents} 个Agent并行分析...\n")
        
        with ThreadPoolExecutor(max_workers=7) as executor:
            future_to_agent = {
                executor.submit(agent.analyze, vector_store, author_id): agent
                for agent in agents
            }
            
            completed = 0
            for future in as_completed(future_to_agent):
                agent = future_to_agent[future]
                completed += 1
                try:
                    print(f"\n[进度 {completed}/{total_agents}] {agent.name} 分析已启动...")
                    result = future.result()
                    results.append(result)
                    status = "✓ 完成" if result.success else "✗ 失败"
                    print(f"[进度 {completed}/{total_agents}] {agent.name} 分析已完成 {status}")
                except Exception as e:
                    print(f"[进度 {completed}/{total_agents}] {agent.name} ✗ 执行异常: {e}")
                    results.append(AgentAnalysisResult(
                        agent_name=agent.name,
                        dimensions=agent.dimensions,
                        analysis={},
                        examples=[],
                        success=False,
                        error=str(e)
                    ))
    else:
        # 串行执行分析
        print(f"\n📋 启动 {total_agents} 个Agent串行分析...\n")
        
        for idx, agent in enumerate(agents, 1):
            try:
                print(f"\n{'='*60}")
                print(f"[进度 {idx}/{total_agents}] {agent.name} 分析已启动...")
                print(f"{'='*60}")
                
                result = agent.analyze(vector_store, author_id)
                results.append(result)
                
                status = "✓ 完成" if result.success else "✗ 失败"
                print(f"\n[进度 {idx}/{total_agents}] {agent.name} 分析已完成 {status}\n")
                
            except Exception as e:
                print(f"\n[进度 {idx}/{total_agents}] {agent.name} ✗ 执行异常: {e}\n")
                results.append(AgentAnalysisResult(
                    agent_name=agent.name,
                    dimensions=agent.dimensions,
                    analysis={},
                    examples=[],
                    success=False,
                    error=str(e)
                ))
    
    # 整合结果
    coordinator = CoordinatorAgent()
    final_style = coordinator.integrate_results(results)
    
    if not final_style:
        print("\n✗ 风格分析失败")
        return None
    
    # 保存风格文件
    print(f"\n💾 保存风格档案到: {style_filepath}")
    try:
        with open(style_filepath, 'w', encoding='utf-8') as f:
            json.dump(final_style, f, ensure_ascii=False, indent=2)
        print("✓ 风格档案保存成功\n")
    except Exception as e:
        print(f"✗ 保存风格文件失败: {e}")
        return None
    
    # 打印摘要
    print("=" * 60)
    print("✅ 风格提取完成摘要")
    print("=" * 60)
    print(f"  - 作者ID: {author_id}")
    print(f"  - 成功Agent: {len([r for r in results if r.success])}/{len(agents)}")
    print(f"  - 分析维度: {len(final_style['writing_style_analysis_framework'])}")
    print("=" * 60 + "\n")
    
    return final_style


def save_style_profile(author_id: str, chapter_texts: List[str], force_regenerate: bool = False, interactive: bool = True, parallel: bool = False) -> Dict:
    """
    使用多Agent架构提取并保存作者风格
    
    Args:
        author_id: 作者ID
        chapter_texts: 章节文本列表
        force_regenerate: 是否强制重新生成
        interactive: 是否交互式询问用户
        parallel: 是否并行执行Agent（默认False，串行执行更稳定）
    
    Returns:
        提取的作者风格字典
    """
    # 检查是否已存在风格文件和向量库
    style_filepath = get_style_filepath(author_id)
    vs_path = get_vector_store_path(author_id)
    
    has_style = style_filepath.exists()
    has_vector = vs_path.exists()
    
    # 如果已存在且不强制重新生成
    if (has_style or has_vector) and not force_regenerate:
        print("\n" + "=" * 60)
        print("📋 检测到已有数据")
        print("=" * 60)
        if has_style:
            print(f"✓ 风格文件: {style_filepath}")
        if has_vector:
            print(f"✓ 向量库: {vs_path}")
        
        if interactive:
            print("\n请选择操作:")
            print("  1. 使用现有向量库进行风格提取 (快速)")
            print("  2. 完全重新生成 (重新分块+重建向量库+风格提取)")
            print("  3. 加载已有风格档案 (最快)")
            
            choice = input("\n请输入选择 (1/2/3): ").strip()
            
            if choice == "3":
                existing_style = load_style_profile_from_file(author_id)
                if existing_style:
                    print(f"✓ 已加载现有风格档案")
                    return existing_style
                else:
                    print("✗ 加载失败，将重新生成")
                    force_regenerate = True
            elif choice == "2":
                print("✓ 将完全重新生成")
                force_regenerate = True
            elif choice == "1":
                print("✓ 使用现有向量库进行风格提取")
                if has_vector:
                    vector_store = load_author_vector_store(author_id)
                    if vector_store:
                        print(f"✓ 向量库加载成功\n")
                        return _run_agent_analysis(author_id, vector_store, style_filepath, parallel=parallel)
                print("✗ 向量库加载失败，将重新生成")
                force_regenerate = True
            else:
                print("无效选择，将加载现有数据")
                existing_style = load_style_profile_from_file(author_id)
                if existing_style:
                    return existing_style
        else:
            # 非交互模式，直接加载现有数据
            existing_style = load_style_profile_from_file(author_id)
            if existing_style:
                print(f"✓ 加载已有风格数据")
                print(f"ℹ 如需重新生成，请设置 force_regenerate=True 或 interactive=True")
                return existing_style
    
    # 过滤有效章节
    valid_chapters = [text for text in chapter_texts if len(text.strip()) >= 50]
    if not valid_chapters:
        print("✗ 没有有效的章节文本")
        return None
    
    print(f"\n📚 有效章节数: {len(valid_chapters)}")
    print(f"📏 总字符数: {sum(len(ch) for ch in valid_chapters):,}\n")
    
    # 合并文本
    full_text = "\n\n".join(valid_chapters)
    
    # ==================== 步骤1: 智能分块 ====================
    print("=" * 60)
    print("步骤 1/3: 智能文本分块")
    print("=" * 60)
    chunker = SmartTextChunker(chunk_size=400, chunk_overlap=80)
    chunks = chunker.chunk_text(full_text, author_id)
    
    if not chunks:
        print("✗ 文本分块失败")
        return None
    
    # ==================== 步骤2: 构建向量库 ====================
    print("\n" + "=" * 60)
    print("步骤 2/3: 构建向量库")
    print("=" * 60)
    
    # 创建Document对象
    documents = [
        Document(
            page_content=chunk.text,
            metadata=chunk.metadata
        )
        for chunk in chunks
    ]
    
    # 分批构建向量库（DashScope限制每批最多10个文档）
    batch_size = 10
    total_docs = len(documents)
    print(f"正在向量化 {total_docs} 个文本块（每批{batch_size}个）...")
    
    vector_store = None
    for i in range(0, total_docs, batch_size):
        batch = documents[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total_docs + batch_size - 1) // batch_size
        
        print(f"  处理批次 {batch_num}/{total_batches} ({len(batch)} 个文档)...", end='', flush=True)
        
        if vector_store is None:
            # 第一批：创建向量库
            vector_store = FAISS.from_documents(batch, embeddings)
        else:
            # 后续批次：添加到现有向量库
            batch_vs = FAISS.from_documents(batch, embeddings)
            vector_store.merge_from(batch_vs)
        
        print(" ✓")
    
    # 保存向量库
    vs_path = get_vector_store_path(author_id)
    vs_path.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(vs_path))
    print(f"✓ 向量库已保存到: {vs_path}\n")
    
    # ==================== 步骤3: 多Agent分析 ====================
    return _run_agent_analysis(author_id, vector_store, style_filepath, parallel=parallel)


def delete_author_style(author_id: str) -> bool:
    """删除指定作者的风格数据"""
    import shutil
    
    success = True
    
    # 删除风格文件
    style_file = get_style_filepath(author_id)
    if style_file.exists():
        try:
            os.remove(style_file)
            print(f"✓ 已删除风格文件: {style_file}")
        except Exception as e:
            print(f"✗ 删除风格文件失败: {e}")
            success = False
    
    # 删除向量库
    vs_path = get_vector_store_path(author_id)
    if vs_path.exists():
        try:
            shutil.rmtree(vs_path)
            print(f"✓ 已删除向量库: {vs_path}")
        except Exception as e:
            print(f"✗ 删除向量库失败: {e}")
            success = False
    
    return success


def list_all_authors() -> List[str]:
    """列出所有已保存的作者"""
    authors = []
    
    # 从风格文件目录获取
    if STYLE_FILES_PATH.exists():
        for file in STYLE_FILES_PATH.glob("*.json"):
            authors.append(file.stem)
    
    if authors:
        print(f"\n已保存的作者列表:")
        for i, author_id in enumerate(authors, 1):
            print(f"  {i}. {author_id}")
        print()
    else:
        print("暂无已保存的作者风格")
    
    return authors


# ==================== EPUB文本提取函数 ====================

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

def extract_text_from_epub(epub_path: str, merge_short_chapters=True, min_chunk_size=3000):
    """从epub中提取文本"""
    book = epub.read_epub(epub_path)
    raw_chapters = []

    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text = soup.get_text()
            text = text.strip()
            if text:
                raw_chapters.append(text)
    
    if not merge_short_chapters:
        return raw_chapters
    
    # 合并短章节
    merged_chapters = []
    current_chunk = ""
    
    for chapter in raw_chapters:
        current_chunk += chapter + "\n\n"
        
        if len(current_chunk) >= min_chunk_size:
            merged_chapters.append(current_chunk.strip())
            current_chunk = ""
    
    if current_chunk.strip():
        merged_chapters.append(current_chunk.strip())
    
    return merged_chapters


# ==================== 测试函数 ====================

def test_style_extraction(parallel: bool = False):
    """
    测试风格提取流程 - 使用完整EPUB小说
    
    Args:
        parallel: 是否并行执行Agent（默认False，串行执行）
    """
    print("=" * 80)
    print(f"🧪 测试多Agent风格提取系统 ({'并行模式' if parallel else '串行模式'})")
    print("=" * 80 + "\n")
    
    # 从EPUB文件读取完整小说
    epub_path = Path(__file__).parent / "1.epub"
    
    if not epub_path.exists():
        print(f"✗ 找不到测试EPUB文件: {epub_path}")
        print("请确保 1.epub 文件存在于 agent_test 目录下")
        return
    
    print(f"📖 正在读取EPUB文件: {epub_path.name}")
    try:
        # 提取章节文本（合并短章节，每块至少3000字符）
        chapters = extract_text_from_epub(str(epub_path), merge_short_chapters=True, min_chunk_size=3000)
        
        if not chapters:
            print("✗ 未能从EPUB中提取到有效文本")
            return
        
        print(f"✓ 成功提取 {len(chapters)} 个文本块")
        print(f"✓ 总字符数: {sum(len(ch) for ch in chapters):,}")
        
        # 显示前3章的摘要
        print(f"\n📄 章节预览:")
        for i, ch in enumerate(chapters[:3], 1):
            preview = ch[:100].replace('\n', ' ')
            print(f"  {i}. {preview}... ({len(ch)} 字符)")
        if len(chapters) > 3:
            print(f"  ... 还有 {len(chapters) - 3} 个章节")
        
        print()
        
    except Exception as e:
        print(f"✗ 读取EPUB失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 执行风格提取（interactive=True 会询问用户选择）
    author_id = "test_author"
    result = save_style_profile(author_id, chapters, force_regenerate=False, interactive=True, parallel=parallel)
    
    if result:
        print("\n✅ 测试成功!")
        print("\n📊 风格档案示例（前1000字符）:")
        print(json.dumps(result, ensure_ascii=False, indent=2)[:1000] + "...")
        
        # 显示文件位置
        print(f"\n📁 生成的文件:")
        print(f"  - 风格档案: {get_style_filepath(author_id)}")
        print(f"  - 向量库: {get_vector_store_path(author_id)}")
    else:
        print("\n✗ 测试失败")


if __name__ == "__main__":
    import sys
    
    # 支持命令行参数控制并行模式
    # 用法: python agent_style_v2.py --parallel
    parallel_mode = "--parallel" in sys.argv
    
    test_style_extraction(parallel=parallel_mode)
