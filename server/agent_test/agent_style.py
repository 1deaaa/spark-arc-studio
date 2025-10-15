from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import DashScopeEmbeddings
import json
import os
import sys
import io
import time
from pathlib import Path

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

# 初始化向量库
vector_store_path = "author_style_db"
vector_store = None
if os.path.exists(vector_store_path):
    try:
        vector_store = FAISS.load_local(vector_store_path, embeddings, allow_dangerous_deserialization=True)
    except Exception as e:
        print(f"加载向量库失败: {e}")
        vector_store = None


STYLE_FILES_PATH = Path("author_styles")
STYLE_FILES_PATH.mkdir(exist_ok=True)

def get_style_filepath(author_id: str) -> Path:
   """构建作者风格文件的路径"""
   return STYLE_FILES_PATH / f"{author_id}.txt"  # 改为txt文件

def load_style_profile_from_file(author_id: str) -> str | None:
   """从本地文件加载作者风格内容"""
   filepath = get_style_filepath(author_id)
   if not filepath.exists():
       print(f"风格文件不存在: {filepath}")
       return None
   try:
       with open(filepath, 'r', encoding='utf-8') as f:
           return f.read()  # 直接读取文本内容
   except Exception as e:
       print(f"从文件 {filepath} 加载风格失败: {e}")
       return None


# ==================== 核心功能函数 ====================

# 基于完整文本提取作者风格
def extract_author_style_from_full_text(full_text: str) -> dict:
    """
    直接基于完整的多章节文本提取作者整体风格
    这比逐章提取再合并更高效、更准确
    """
    # 限制文本长度避免超出token限制
    # 根据模型调整：一般中文约2-3字符=1token，留足够空间给返回
    max_chars = 80000  # 约10k-15k tokens
    
    if len(full_text) > max_chars:
        sample_text = full_text[:max_chars] + "\n\n...(后续内容略)"
        print(f"文本过长,使用前{max_chars:,}字符作为样本")
    else:
        sample_text = full_text
    
    print(f"正在分析完整文本的作者风格 (样本长度: {len(sample_text):,} 字符)...")
    
    author_style_prompt = PromptTemplate.from_template("""
你是一位专业的文学风格分析师和游戏剧本顾问。现在给你提供一位作者的多个章节文本，请深度分析该作者的整体风格特征。

【分析原则】
1. 关注反复出现的特征（这些是作者的核心风格DNA）
2. 忽略偶然性、非代表性的表达
3. 提供精准、可操作、可量化的风格描述
4. 避免提及具体情节和人物名字
5. **重点关注游戏剧本创作的核心要素：对话、旁白、心声**
6. 提取具体例句作为风格参考（去除人名等具体信息）

【深度分析维度】
请从以下维度进行详细分析，每个维度都要深入挖掘：

输出JSON格式：
{
  "writing_style_analysis_framework": {
    "dialogue_system": {
      "dialogue_rhythm": "对话节奏（如：一问一答式/大段独白/碎片化交锋/沉默留白的运用/快速对攻）",
      "speech_pattern": "说话模式（如：省略主语、语气词使用、句尾习惯、口语化程度、方言色彩）",
      "subtext_technique": "潜台词技巧（如：话中有话、欲言又止、声东击西、反讽暗示、答非所问）",
      "dialogue_tags": "对话标签风格（如：简洁的'说'、丰富的动作描写、表情细节、环境穿插、省略标签）",
      "interruption_overlap": "打断与重叠（如：经常打断彼此、完整表达、思考停顿的处理、抢话时机）",
      "tone_variation": "语气变化（如：从温和到激烈的跨度、情绪起伏的细腻度、音量/语速标记）",
      "information_delivery": "信息传递方式（如：直接说明、暗示隐喻、逐步揭示、故弄玄虚、问答引导）",
      "character_voice_diff": "角色语言分化度（如：不同角色有明显语言特征差异/教育背景体现/职业习惯/较为统一）",
      "dialogue_examples": ["提取3-5个典型对话片段（去人名），展示风格特点"]
    },
    
    "inner_monologue": {
      "thought_structure": "思维结构（如：线性逻辑/跳跃联想/意识流/反刍重复/碎片闪念/问答辩驳）",
      "inner_voice_tone": "内心声音色调（如：自我审视/自我安慰/自我谴责/哲思冥想/焦虑絮叨/冷静分析）",
      "thought_depth": "思考深度层次（如：表层反应/深层剖析/潜意识涌现/元认知反思/身体记忆）",
      "memory_flashback": "记忆闪回方式（如：突然插入/渐进唤起/片段式/场景重现/感官触发/情绪链接）",
      "emotion_thought_ratio": "情感与理性比例（如：感性主导/理性分析为主/交织并行/理性崩溃点）",
      "self_dialogue": "自我对话模式（如：与自己争论、内心问答、否定与肯定的拉锯、多重人格式）",
      "psychological_time": "心理时间感（如：时间凝滞/飞速流转/循环往复/过去侵入现在）",
      "thought_fragmentation": "思绪破碎度（如：完整思考链/频繁中断/零散意象流/强迫性重复）",
      "monologue_examples": ["提取3-5个典型内心独白片段，展示风格"]
    },
    
    "perspective_system": {
      "focalization": "聚焦模式（如：零聚焦全知/内聚焦单一/外聚焦行为/多重视角切换/镜头式客观）",
      "narrator_reliability": "叙述者可靠性（如：全知可靠/有限认知/主动误导/无意偏见/精神失常）",
      "narrator_distance": "叙述者距离（如：亲密贴近/疏离冷静/忽远忽近/完全融入角色/上帝俯瞰）",
      "character_filter": "角色滤镜（如何通过角色的认知局限/偏见/情绪状态/文化背景过滤信息）",
      "meta_awareness": "元叙事意识（如：叙述者介入评论/打破第四堵墙/自我反思/与读者对话）",
      "temporal_perspective": "时间视角（如：当下进行/事后回顾/预知未来/时间游移/多时间线并行）",
      "perspective_shift_trigger": "视角转换触发（如：章节切换/场景转换/情绪驱动/悬念需要/对比需要）",
      "commentary_style": "评论风格（如：不加评论/点到为止/深度剖析/戏谑调侃/诗意升华）",
      "perspective_examples": ["提取3-5个典型视角运用段落"]
    },
    
    "detail_craftsmanship": {
      "micro_expression": "微表情捕捉（如：眼神细节、嘴角变化、身体微动、呼吸变化、瞳孔/脸色）",
      "environmental_detail": "环境细节选择（如：光影变化/气味声音/温度湿度/物品摆放/空间质感）",
      "action_granularity": "动作颗粒度（如：粗线条/精细分解/关键帧捕捉/慢镜头式/武术分解）",
      "sensory_hierarchy": "感官层次（如：主视觉辅听觉/全感官协同/特定感官强化/通感转换）",
      "detail_timing": "细节时机（如：对话中穿插/情绪转折点/环境氛围铺垫/悬念制造/高潮前静止）",
      "symbolic_details": "象征性细节（如：反复出现的物件、颜色、气味、动作、场景元素）",
      "detail_authenticity": "细节真实性（如：专业领域细节准确度/生活化细节/避免常识错误/质感营造）",
      "detail_selection_principle": "细节筛选原则（如：服务情绪/推动情节/揭示性格/营造氛围/制造对比）",
      "detail_examples": ["提取5-8个精彩细节描写片段"]
    },
    
    "scene_construction": {
      "scene_opening": "场景开场方式（如：环境先行/对话切入/动作开始/氛围渲染/意识流入场）",
      "spatial_presentation": "空间呈现（如：全景到特写/特写到全景/平行空间/空间留白/运动镜头）",
      "atmosphere_building": "氛围营造手法（如：环境烘托/对话暗示/节奏控制/感官堆叠/象征物布置）",
      "scene_transition": "场景转换技巧（如：硬切/淡入淡出/蒙太奇/角色视角引导/时空跳跃/物件过渡）",
      "time_in_scene": "场景内时间流动（如：实时流动/压缩跳跃/时间膨胀/倒流闪回/时间静止）",
      "scene_rhythm": "场景节奏变化（如：紧张-舒缓交替/持续紧张/平稳流动/突然爆发）",
      "scene_ending": "场景收尾方式（如：悬念钩子/情绪余韵/突然中断/自然过渡/象征性结束）",
      "scene_density": "场景信息密度（如：密集事件/单一焦点/多线并行/留白沉默）"
    },
    
    "character_portrayal": {
      "appearance_intro": "外貌介绍方式（如：集中描述/零散分布/他者视角/自我观察/不描写/特征化）",
      "personality_reveal": "性格展现途径（如：行动展示为主/对话透露/内心独白/他人评价/矛盾行为）",
      "growth_tracking": "成长轨迹呈现（如：突变式/渐进式/循环反复/多线并行/否定之否定）",
      "relationship_dynamics": "关系动态描写（如：对话中的张力/权力关系流转/亲密度变化/依赖与背叛）",
      "character_consistency": "角色一致性（如：高度统一/复杂多面/前后矛盾作为特色/创伤后变化）",
      "character_agency": "角色能动性（如：主动推动情节/被动承受/在困境中挣扎/命运摆弄）",
      "backstory_reveal": "背景揭示策略（如：前置交代/逐步揭秘/对话中自然流露/关键时刻闪回）"
    },
    
    "plot_technique": {
      "foreshadowing_method": "伏笔布置（如：显性暗示/隐性埋伏/细节伏笔/对话伏笔/重复强化/反向伏笔）",
      "suspense_creation": "悬念制造（如：信息延迟/视角限制/误导/制造疑问/时间倒计时/多重可能）",
      "conflict_escalation": "冲突升级（如：层层递进/突然爆发/多线交织/内外冲突交替/假性和解）",
      "plot_point_handling": "情节点处理（如：突转/铺垫充分/意料之外情理之中/刻意反转/反高潮）",
      "causality_chain": "因果链条（如：紧密因果/松散关联/巧合偶然/多因多果/蝴蝶效应）",
      "subplot_weaving": "副线编织（如：与主线交织/平行发展/呼应对比/独立后汇合/反衬主题）",
      "plot_density": "情节密度（如：事件密集/舒缓叙述/关键点集中/平铺直叙）",
      "reversal_technique": "反转技巧（如：信息差反转/人物反转/价值反转/视角反转）"
    },
    
    "emotional_progression": {
      "emotion_accumulation": "情绪积累方式（如：缓慢升温/压抑后爆发/波浪式起伏/持续高压/多情绪交织）",
      "emotional_peak": "情感高潮处理（如：克制收束/极致爆发/留白余韵/反高潮/转移宣泄）",
      "emotion_transition": "情绪转换（如：自然过渡/急转直下/复杂交织/延迟反应/情绪惯性）",
      "empathy_technique": "共情技巧（如：细节代入/身体感受描写/内心独白/普世情感/避免说教）",
      "catharsis_method": "情感宣泄（如：行动宣泄/对话释放/内心崩溃/诗意升华/沉默爆发）",
      "emotional_authenticity": "情感真实性（如：避免过度煽情/符合人物逻辑/情绪复杂性/矛盾情感并存）",
      "emotional_restraint": "情感克制度（如：点到即止/充分释放/压抑美学/情感节制）"
    },
    
    "linguistic_texture": {
      "sentence_architecture": "句子建筑学（如：长短句比例/复句类型偏好/排比递进转折/单句vs复句）",
      "lexical_signature": "词汇指纹（如：文学化/古典意味/现代口语/专业术语/方言俚语/新词创造）",
      "rhetoric_devices": "修辞手法库（具体列举：比喻类型/拟人方式/夸张度/反复模式/对比手法/通感用法）",
      "metaphor_quality": "比喻质量标准（如：意象新鲜度/本体喻体距离/感官具体性/避免陈词滥调/文化适配）",
      "adjective_style": "形容词使用（如：细腻感官/抽象情感/具体量词/色彩偏好/避免堆砌/精准选择）",
      "verb_dynamics": "动词动态性（如：静态描写/动作捕捉/具体动词偏好/避免'是'类系词）",
      "syntactic_deviation": "句法偏离（如：倒装/省略/破格/重复/跳跃/诗化句式）",
      "punctuation_rhythm": "标点节奏（如：分号营造舒缓/破折号突转/省略号悬念/顿号密集/句号断裂）",
      "phonetic_music": "语音音乐性（如：韵律感/重复音节/拟声词/平仄考量/朗读节奏）",
      "special_terms": "特色用语（如：口头禅/固定搭配/创造性用词/时代烙印/亚文化黑话）",
      "language_examples": ["高频特色词汇20-30个", "典型句式5-8个", "独特修辞案例3-5个"]
    },
    
    "imagery_system": {
      "core_images": "核心意象群（列举15-25个高频意象：物象/自然/器物/色彩/声音/气味等）",
      "image_frequency": "意象频次分析（如：某意象在全文出现频率/分布位置/演变轨迹）",
      "metaphor_types": "比喻类型（如：自然物象喻情感/器物喻人生/色彩象征/身体隐喻/空间隐喻）",
      "metaphor_originality": "比喻原创性（如：避免'时间如流水'式陈词/建立独特联系/文化创新）",
      "sensory_focus": "感官侧重（如：视觉主导比例/听觉细腻度/触觉嗅觉/综合通感/冷暖感官）",
      "symbol_system": "象征体系（如：光暗对比/季节更迭/旅途意象/物件象征/颜色系统/反复母题）",
      "image_evolution": "意象演化（如：同一意象在不同情境下的意义变化/生长轨迹）",
      "cultural_imagery": "文化意象层（如：古典文学意象/宗教象征/民俗符号/现代工业意象）",
      "imagery_examples": ["提取10-15个意象使用片段，含上下文"]
    },
    
    "theme_tendency": {
      "main_themes": "核心主题（列举6-10个：存在焦虑/代际冲突/身份认同/权力关系/时间记忆等）",
      "value_orientation": "价值取向（如：个体主义/集体关怀/存在主义/理想主义/虚无主义/人文关怀）",
      "philosophical_depth": "哲思深度（如：日常生活哲学/形而上思考/禅意顿悟/荒诞意识/存在追问）",
      "life_attitude": "人生态度（如：悲观怀旧/积极向上/虚无飘渺/现实清醒/悲喜交织）",
      "conflict_worldview": "冲突观与世界观（如：善恶对立/灰色复杂/荒诞世界/理想与现实/秩序与混沌）",
      "moral_complexity": "道德复杂度（如：非黑即白/多元立场/处境伦理/价值冲突/反英雄）",
      "social_critique": "社会批判性（如：直接批判/隐喻讽刺/温和反思/逃避现实/沉浸个体）",
      "existential_questions": "存在追问（如：生命意义/死亡意识/自由意志/孤独本质/荒诞体验）"
    },
    
    "language_style": {
      "formality_level": "文白程度（如：半文半白占比/现代白话/古典文言/诗化语言/方言混杂）",
      "colloquial_degree": "口语化程度（如：书面语为主/口语化表达/对话感强/网络用语/语境差异）",
      "poetic_quality": "诗意浓度（如：高度诗化/散文化诗意/质朴平实/理性克制/抒情时刻）",
      "literary_references": "文学引用（如：诗词引用频率/典故使用/互文性/致敬痕迹/文化源流）",
      "language_innovation": "语言创新（如：新词创造/旧词新用/语法突破/文体实验/混搭风格）",
      "register_shift": "语域切换（如：正式-非正式/书面-口语/雅-俗转换的时机与功能）",
      "archaism_modernism": "古今平衡（如：古典韵味如何融入现代叙事/时代感营造）"
    },
    
    "structural_breathing": {
      "information_flow": "信息流动（如：顺时线性/倒叙/插叙/碎片拼贴/意识流漂移/多线交织）",
      "density_modulation": "密度调制（如：何时密集轰炸/何时留白沉默/信息节制/关键点聚焦）",
      "chapter_connectivity": "章节连接（如：硬切/淡出/悬念钩子/时空跳跃/情绪过渡/对比并置）",
      "recursive_motifs": "递归母题（如：反复场景/对话回声/意象回旋/结构对称/首尾呼应）",
      "white_space_use": "留白艺术（如：大量留白营造余韵/紧密铺陈/段间呼吸/沉默时刻）",
      "paragraph_rhythm": "段落节奏（如：短段急促/长段沉浸/长短交错/单句成段/密集分段）",
      "structural_pattern": "结构模式（如：起承转合/散点透视/回环往复/镜像对称/螺旋上升）",
      "narrative_layers": "叙事层次（如：单线/双线/多线/框架故事/套层结构/现实-回忆-幻想）"
    },
    
    "rhythm_control": {
      "overall_pacing": "整体节奏（如：舒缓流淌/紧凑急促/张弛有度/变化多端/前慢后快）",
      "speed_variation": "节奏变速（如：何时加速/何时减速/转换标志/速度对比/节奏断点）",
      "narrative_breath": "叙事呼吸（如：紧张后的舒缓/高潮前的压抑/留白节点/喘息时刻）",
      "reader_engagement": "读者卷入（如：持续紧张/沉浸冥想/情绪过山车/认知挑战/舒适阅读）",
      "rhythm_signature": "节奏指纹（如：作者独特的快慢组合/标志性的节奏模式）",
      "scene_chapter_rhythm": "场景章节节奏（如：短场景快切/长场景沉浸/章节长度策略）"
    },
    
    "causality_web": {
      "causality_tightness": "因果紧密度（如：铁律因果/松散偶然/模糊关联/荒诞断裂/命定论）",
      "hidden_causality": "隐性因果（如：表面巧合实则早埋暗线/不动声色的必然/读者二刷发现）",
      "causality_delay": "因果延迟（如：种因与得果的时间跨度/长程记忆/跨章节呼应）",
      "multi_causality": "多因多果（如：单一事件多重原因/复杂后果/蝴蝶效应/避免单线因果）",
      "anti_causality": "反因果（如：刻意打破因果逻辑/荒诞派/魔幻现实/无意义感）",
      "causality_reveal": "因果揭示（如：顺序揭示/逆向推理/谜题拼图/突然顿悟）",
      "motivation_logic": "动机逻辑（如：人物行为的内在动机链/欲望-行动-后果的合理性）"
    },
    
    "subtext_layer": {
      "what_unsaid": "未说之言（如：故意省略的信息/留给读者推断的空间/不言而喻的默契）",
      "contradictory_signals": "矛盾信号（如：言行不一/表里不符/微表情泄露/无意识暴露）",
      "symbolic_action": "象征性行动（如：表面做A实际意味B/仪式化行为/替代性满足）",
      "silence_eloquence": "沉默的雄辩（如：何时用沉默代替对话/对话中的停顿/拒绝回答）",
      "irony_layers": "反讽层次（如：戏剧性反讽/语言反讽/情境反讽/悲剧性反讽）",
      "double_meaning": "双重意义（如：对话的表层与深层/一语双关/隐喻对话）",
      "subtext_examples": ["提取5-8个潜台词丰富的场景，含解读"]
    },
    
    "temporal_architecture": {
      "time_layering": "时间分层（如：现在时/回忆/预感/幻想如何交织/时态切换规律）",
      "duration_distortion": "时长扭曲（如：1小时写5章vs10年一笔带过/时间伸缩比例/重要性决定时长）",
      "temporal_anchors": "时间锚点（如：关键时间点标记/历史事件/季节/纪念日/年龄）",
      "time_loops": "时间循环（如：季节轮回/纪念日重复/重复场景制造宿命感/螺旋时间）",
      "historical_depth": "历史纵深（如：个人命运与时代背景勾连/代际传承/历史阴影/时代烙印）",
      "memory_structure": "记忆结构（如：线性回忆/碎片拼贴/创伤性重复/选择性遗忘/记忆不可靠）",
      "temporal_markers": "时间标记（如：季节变化/物件老化/身体衰老/技术更迭/语言时代性）",
      "time_consciousness": "时间意识（如：对时间流逝的敏感度/永恒瞬间/时间焦虑/怀旧倾向）"
    },
    
    "tension_mechanics": {
      "expectation_management": "期待管理（如：制造预期/延迟满足/颠覆预期/多重可能性）",
      "stakes_escalation": "赌注升级（如：从个人到集体/从物质到精神/生存-尊严-意义的递进）",
      "ticking_clock": "滴答时钟（如：deadline压力植入/倒计时/时间限制的强化与提醒）",
      "false_relief": "虚假缓解（如：短暂放松后更大危机/假性高潮/喘息后的重击）",
      "tension_release": "张力释放（如：何时宣泄/何时压抑/反高潮/延迟满足/多级释放）",
      "obstacle_progression": "障碍递进（如：一波未平一波又起/解决一个制造三个/困境升级逻辑）",
      "tension_sources": "张力来源（如：外部冲突/内心挣扎/时间压力/道德困境/信息不对称）",
      "suspense_vs_surprise": "悬念与惊奇（如：让读者知道炸弹vs突然爆炸/希区柯克理论应用）"
    },
    
    "distinctive_features": {
      "signature_style": "标志性特征（最能代表作者的10-15个独特风格要素：句式癖/意象偏好/叙事癖好等）",
      "influence_trace": "风格来源（如：受某流派/作家影响的痕迹/致敬/化用/反叛）",
      "innovation_point": "创新之处（如：独特的表达方式/新颖的结构尝试/突破性元素/实验性）",
      "weakness_awareness": "风格局限（如：重复套路/刻板模式/过度依赖/需要警惕的舒适区）",
      "evolution_potential": "演化潜力（如：风格发展趋势/可能的突破方向/未开发领域/成长空间）",
      "genre_adaptation": "体裁适配性（如：该风格在小说/剧本/散文中的差异化表现）",
      "readability_balance": "可读性平衡（如：文学性与可读性的权衡/受众定位/难度曲线）"
    }
  },
  
  "_meta": {
    "framework_version": "2.0",
    "applicable_genres": ["小说", "剧本", "散文", "非虚构叙事", "诗歌（部分维度）"],
    "usage_notes": [
      "每个维度提供具体案例而非抽象描述",
      "关注'为什么这样写'而非'写了什么'",
      "识别模式但避免僵化标签",
      "分析风格的有机生长逻辑而非参数堆砌",
      "特别关注对抗AI常见缺陷：工业糖精/空降设定/情感快进/强行修辞/模板化"
    ],
    "analysis_depth": "每个子维度需提供3-5个具体观察点，避免泛泛而谈",
    "cross_validation": "多个维度应相互印证，形成一致的风格画像"
  }
}

【作者文本样本】
{sample_text}

请输出该作者的深度风格分析（完整JSON，务必详尽）：
""")
    
    prompt = author_style_prompt.format(sample_text=sample_text)
    
    # 添加重试机制
    max_retries = 3
    retry_delay = 5  # 秒
    
    for attempt in range(max_retries):
        try:
            print(f"正在调用LLM... (尝试 {attempt + 1}/{max_retries})")
            response = llm.invoke(prompt)
            
            # 提取内容（去除markdown代码块标记）
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # 不再强制解析JSON，直接返回原始内容字符串
            # 保持JSON格式的字符串，但不做结构验证
            print(f"✓ 风格分析完成 (内容长度: {len(content)} 字符)")
            return content  # 返回字符串而非dict
            
        except (Exception) as e:
            error_msg = str(e)
            print(f"✗ 第 {attempt + 1} 次尝试失败: {error_msg[:100]}")
            
            if attempt < max_retries - 1:
                print(f"等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
            else:
                print(f"✗ 所有重试均失败，放弃提取风格")
                return None

# 保存风格到向量库 - 优化版
def save_style_profile(author_id: str, chapter_texts: list[str], force_regenerate: bool = False):
    """
    直接基于所有章节的完整文本提取并保存作者风格
    
    Args:
        author_id: 作者ID
        chapter_texts: 章节文本列表
        force_regenerate: 是否强制重新生成（忽略已存在的文件）
    
    Returns:
        提取的作者风格字符串
    """
    global vector_store
    
    # 检查风格文件是否已存在
    style_filepath = get_style_filepath(author_id)
    if style_filepath.exists() and not force_regenerate:
        print(f"✓ 检测到已存在的风格文件: {style_filepath}")
        try:
            existing_style = load_style_profile_from_file(author_id)
            if existing_style and len(existing_style.strip()) >= 100:
                print(f"✓ 加载已有风格数据 (长度: {len(existing_style):,} 字符)")
                print(f"ℹ 如需重新生成，请设置 force_regenerate=True")
                return existing_style
            else:
                print(f"⚠ 已有风格文件内容过短，将重新生成")
        except Exception as e:
            print(f"⚠ 加载已有风格文件失败: {e}，将重新生成")
    
    # 过滤掉太短的章节
    valid_chapters = [text for text in chapter_texts if len(text.strip()) >= 50]
    
    if not valid_chapters:
        print("警告: 没有有效的章节文本")
        return None
    
    print(f"有效章节数: {len(valid_chapters)}")
    print(f"总字符数: {sum(len(ch) for ch in valid_chapters):,}")
    
    # 合并所有章节为一个完整文本
    full_text = "\n\n".join(valid_chapters)
    
    # 直接基于完整文本提取作者风格(只需1次LLM调用!)
    print(f"\n正在分析作者整体风格...")
    author_style = extract_author_style_from_full_text(full_text)
    
    if not author_style or len(author_style.strip()) < 100:
        print(f"✗ 风格提取失败或内容过短 (长度: {len(author_style) if author_style else 0})")
        return None
    
    print(f"✓ 风格提取完成 (内容长度: {len(author_style):,} 字符)\n")
    
   # 保存风格到本地txt文件（保持JSON格式字符串，但不做结构验证）
    style_filepath = get_style_filepath(author_id)
    try:
        with open(style_filepath, 'w', encoding='utf-8') as f:
           f.write(author_style)  # 直接写入字符串内容
        print(f"✓ 风格已保存到本地文件: {style_filepath}")
    except Exception as e:
       print(f"✗ 保存风格到文件失败: {e}")
       return None

   # 创建一个简单的文档用于在向量库中索引
    doc = Document(
       page_content=f"作者风格档案: {author_id}",
       metadata={
           "author_id": author_id,
           "chapter_count": len(valid_chapters),
           "total_chars": len(full_text),
           "type": "author_style"
       }
   )
   
   # 保存到向量库
    print(f"保存作者索引到向量库...")
    if vector_store is None:
       vector_store = FAISS.from_documents([doc], embeddings)
    else:
       vector_store.add_documents([doc])
   
    vector_store.save_local(vector_store_path)
    print(f"✓ 成功保存作者风格档案")
    print(f"  - 基于 {len(valid_chapters)} 个章节")
    print(f"  - 共 {len(full_text):,} 字符")
    
    return author_style

def delete_author_style(author_id: str) -> bool:
    """
    从向量库中删除指定作者的风格数据,并删除本地文件
    
    Args:
        author_id: 要删除的作者ID
    
    Returns:
        是否删除成功
    """
    global vector_store
    
    if vector_store is None:
        print("向量存储未初始化")
        return False
    
    try:
        # 获取所有文档及其ID
        # FAISS的docstore存储了所有文档
        all_docs = []
        docs_to_keep = []
        ids_to_keep = []
        
        # 遍历所有文档
        for idx, doc_id in enumerate(vector_store.index_to_docstore_id.values()):
            doc = vector_store.docstore.search(doc_id)
            if doc and doc.metadata.get("author_id") != author_id:
                docs_to_keep.append(doc)
                ids_to_keep.append(idx)
        
        deleted_count = len(vector_store.index_to_docstore_id) - len(docs_to_keep)
        
        if deleted_count == 0:
            print(f"未找到作者 '{author_id}' 的风格数据")
            return False
        
        # 重建向量库（只保留不需要删除的文档）
        if len(docs_to_keep) == 0:
            # 如果删除后没有文档了，创建空的向量库
            print(f"删除后向量库为空，清空向量库...")
            vector_store = None
            # 删除本地文件
            import shutil
            if os.path.exists(vector_store_path):
                shutil.rmtree(vector_store_path)
        else:
            # 用剩余文档重建向量库
            print(f"正在重建向量库...")
            vector_store = FAISS.from_documents(docs_to_keep, embeddings)
            vector_store.save_local(vector_store_path)
        
        print(f"✓ 成功删除作者 '{author_id}' 的 {deleted_count} 条风格数据")
        print(f"  剩余文档数: {len(docs_to_keep)}")

        # 删除关联的风格文件
        style_filepath = get_style_filepath(author_id)
        if style_filepath.exists():
            try:
                os.remove(style_filepath)
                print(f"✓ 成功删除本地风格文件: {style_filepath}")
            except OSError as e:
                print(f"✗ 删除本地风格文件失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"✗ 删除失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def list_all_authors() -> list:
    """
    列出向量库中所有作者及其信息
    
    Returns:
        作者列表，每个作者包含 author_id, chapter_count, total_chars
    """
    global vector_store
    
    if vector_store is None:
        print("向量存储未初始化")
        return []
    
    authors = {}
    
    try:
        # 遍历所有文档
        for doc_id in vector_store.index_to_docstore_id.values():
            doc = vector_store.docstore.search(doc_id)
            if doc:
                author_id = doc.metadata.get("author_id", "unknown")
                if author_id not in authors:
                    authors[author_id] = {
                        "author_id": author_id,
                        "chapter_count": doc.metadata.get("chapter_count", 0),
                        "total_chars": doc.metadata.get("total_chars", 0),
                        "type": doc.metadata.get("type", "unknown")
                    }
        
        author_list = list(authors.values())
        
        if author_list:
            print(f"\n向量库中的作者列表:")
            print(f"{'作者ID':<20} {'章节数':<10} {'字符数':<15} {'类型':<15}")
            print("-" * 65)
            for author in author_list:
                print(f"{author['author_id']:<20} {author['chapter_count']:<10} {author['total_chars']:<15,} {author['type']:<15}")
        else:
            print("向量库为空")
        
        return author_list
        
    except Exception as e:
        print(f"获取作者列表失败: {e}")
        return []


# ==================== 续写生成函数 ====================

def generate_continuation(author_id: str, scene: str, content_type: str = "mixed"):
    """
    基于作者风格生成续写（游戏剧本专用）
    
    Args:
        author_id: 作者ID（用于检索风格档案）
        scene: 场景描述或上文
        content_type: 内容类型 - "dialogue"(对话), "monologue"(内心独白), "narrative"(旁白), "mixed"(混合)
    
    Returns:
        生成的续写文本
    """
    global vector_store
    
    if vector_store is None:
        raise ValueError("向量存储未初始化,请先调用 save_style_profile 保存风格数据")
    
   # 从本地文件加载风格数据（现在是字符串格式）
    style_data_str = load_style_profile_from_file(author_id)
   
    if not style_data_str:
       raise ValueError(f"未找到作者 '{author_id}' 的风格数据文件")
    
    # 尝试解析为JSON以提取特定字段（如果失败就使用完整字符串）
    try:
        style_data = json.loads(style_data_str)
        is_json_valid = True
    except:
        is_json_valid = False
        print("风格数据非标准JSON格式，将使用完整内容")
    
    # 根据内容类型提取相关风格特征
    if is_json_valid and content_type == "dialogue":
        focus_prompt = """
【对话创作重点】
- 对话节奏：{dialogue_rhythm}
- 说话模式：{speech_pattern}
- 潜台词技巧：{subtext_technique}
- 语气变化：{tone_variation}
- 信息传递：{information_delivery}

参考例句：
{dialogue_examples}

请创作符合上述风格的对话场景。
"""
        focus_features = focus_prompt.format(
            dialogue_rhythm=style_data.get("dialogue_system", {}).get("dialogue_rhythm", ""),
            speech_pattern=style_data.get("dialogue_system", {}).get("speech_pattern", ""),
            subtext_technique=style_data.get("dialogue_system", {}).get("subtext_technique", ""),
            tone_variation=style_data.get("dialogue_system", {}).get("tone_variation", ""),
            information_delivery=style_data.get("dialogue_system", {}).get("information_delivery", ""),
            dialogue_examples="\n".join(style_data.get("dialogue_system", {}).get("dialogue_examples", []))
        )
    elif is_json_valid and content_type == "monologue":
        focus_prompt = """
【内心独白创作重点】
- 思维结构：{thought_structure}
- 内心声音：{inner_voice_tone}
- 思考深度：{thought_depth}
- 情感理性比：{emotion_thought_ratio}
- 心理时间感：{psychological_time}

参考例句：
{monologue_examples}

请创作符合上述风格的内心独白。
"""
        focus_features = focus_prompt.format(
            thought_structure=style_data.get("inner_monologue", {}).get("thought_structure", ""),
            inner_voice_tone=style_data.get("inner_monologue", {}).get("inner_voice_tone", ""),
            thought_depth=style_data.get("inner_monologue", {}).get("thought_depth", ""),
            emotion_thought_ratio=style_data.get("inner_monologue", {}).get("emotion_thought_ratio", ""),
            psychological_time=style_data.get("inner_monologue", {}).get("psychological_time", ""),
            monologue_examples="\n".join(style_data.get("inner_monologue", {}).get("monologue_examples", []))
        )
    elif is_json_valid and content_type == "narrative":
        focus_prompt = """
【旁白创作重点】
- 叙述者距离：{narrator_distance}
- 评论风格：{commentary_style}
- 细节捕捉：{micro_expression}, {environmental_detail}
- 氛围营造：{atmosphere_building}
- 节奏控制：{overall_pacing}

参考例句：
{narrative_examples}
{detail_examples}

请创作符合上述风格的旁白描写。
"""
        focus_features = focus_prompt.format(
            narrator_distance=style_data.get("narrative_voice", {}).get("narrator_distance", ""),
            commentary_style=style_data.get("narrative_voice", {}).get("commentary_style", ""),
            micro_expression=style_data.get("detail_craftsmanship", {}).get("micro_expression", ""),
            environmental_detail=style_data.get("detail_craftsmanship", {}).get("environmental_detail", ""),
            atmosphere_building=style_data.get("scene_construction", {}).get("atmosphere_building", ""),
            overall_pacing=style_data.get("rhythm_control", {}).get("overall_pacing", ""),
            narrative_examples="\n".join(style_data.get("narrative_voice", {}).get("narrative_examples", [])),
            detail_examples="\n".join(style_data.get("detail_craftsmanship", {}).get("detail_examples", []))
        )
    else:  # mixed 或无法解析JSON时使用完整内容
        focus_features = f"【完整风格档案】\n{style_data_str}"

    # 续写提示词模板
    rewrite_prompt = PromptTemplate.from_template("""
你是一位专业的游戏剧本作家，现在需要严格模仿特定作者的风格进行创作。

【核心原则】
1. **绝对禁止抄袭**：不得使用原文的情节、角色名、具体事件
2. **风格精准模仿**：句式、用词、节奏、细节、情感表达必须高度一致
3. **避免AI通病**：
   - 不要"工业糖精"式的虚假情感
   - 不要空降设定，要自然融入
   - 不要强行贴标签，要通过细节展现
   - 不要情感快进，要有积累过程
   - 不要模板化剧情（如刻意的偶遇、巧合）
4. **真实的人性**：理解情感的复杂性、矛盾性、渐变性

{focus_features}

【当前场景/上文】
{scene}

【创作任务】
请严格按照上述风格特征进行续写（300-500字），注意：
- 保持风格的微观特征（用词、句式、标点）
- 保持风格的宏观特征（节奏、氛围、情感浓度）
- 让细节自然流淌，不要刻意堆砌
- 让情感真实可信，不要浮夸虚假
""")
    
    prompt = rewrite_prompt.format(focus_features=focus_features, scene=scene)
    response = llm.invoke(prompt)
    return response.content


# ==================== EPUB文本提取函数 ====================

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

def extract_text_from_epub(epub_path: str, merge_short_chapters=True, min_chunk_size=3000):
    """
    从epub中提取文本
    
    Args:
        epub_path: epub文件路径
        merge_short_chapters: 是否合并短章节
        min_chunk_size: 合并后每个文本块的最小字符数
    """
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
    
    # 合并短章节,创建更大的文本块用于风格分析
    merged_chapters = []
    current_chunk = ""
    
    for chapter in raw_chapters:
        current_chunk += chapter + "\n\n"
        
        # 如果当前块足够大,或者这是最后一章
        if len(current_chunk) >= min_chunk_size:
            merged_chapters.append(current_chunk.strip())
            current_chunk = ""
    
    # 添加最后剩余的内容
    if current_chunk.strip():
        merged_chapters.append(current_chunk.strip())
    
    return merged_chapters
