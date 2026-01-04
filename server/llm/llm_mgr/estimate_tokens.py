import re
import tiktoken

# -----------------------------------------------------------------------------
# 全局单例模式加载编码器（避免重复加载消耗）
# -----------------------------------------------------------------------------
_cl100k = None
_o200k = None

def _get_cl100k():
    global _cl100k
    if _cl100k is None:
        _cl100k = tiktoken.get_encoding("cl100k_base")
    return _cl100k

def _get_o200k():
    global _o200k
    if _o200k is None:
        _o200k = tiktoken.get_encoding("o200k_base")
    return _o200k

# -----------------------------------------------------------------------------
# 核心配置表 (基于 2025 Q1 实测效率榜单)
# 格式: (词表大小, 编码器函数, 英文系数, 中文系数, 代码系数)
# 系数计算公式: Factor = 1 / Efficiency (效率越高，系数越小)
# -----------------------------------------------------------------------------
CONFIG = {
    # === 200k 级 (基准阵营) ===
    # GPT-4o / GPT-5
    # 效率: 基准 (1.0)
    "gpt":      (200000, _get_o200k, 1.00, 1.00, 1.00),
    "openai":   (200000, _get_o200k, 1.00, 1.00, 1.00),

    # Claude 
    # 效率: En 0.9x, Zh 0.8x, Code 1.0x
    # 系数: 1/0.9=1.11, 1/0.8=1.25
    "claude":   (200000, _get_o200k, 1.11, 1.25, 1.00),
    "anthropic":(200000, _get_o200k, 1.11, 1.25, 1.00),

    # Grok (参考 GPT-4o 标准)
    "grok":     (200000, _get_o200k, 1.00, 1.00, 1.00),
    
    # === 150k-160k 级 (国产) ===
    # Qwen
    # 效率: En 1.0x, Zh 2.0x, Code 1.1x
    # 系数: 1.0, 0.50, 0.91
    "qwen":     (152000, _get_cl100k, 1.00, 0.50, 0.91),

    # Kimi
    # 效率: En 1.0x, Zh 2.0x , Code 1.0x
    "kimi":     (160000, _get_cl100k, 1.00, 0.50, 1.00),

    # GLM-4
    # 效率: En 1.0x, Zh 1.8x, Code 1.0x
    # 系数: 1.0, 0.56
    "glm":      (152000, _get_cl100k, 1.00, 0.56, 1.00),
    "chatglm":  (152000, _get_cl100k, 1.00, 0.56, 1.00),
    
    # === 128k-131k 级 ===
    # DeepSeek V3
    # 效率: En 0.9x, Zh 1.8x, Code 1.1x
    # 系数: 1.11, 0.56, 0.91
    "deepseek": (129000, _get_cl100k, 1.11, 0.56, 0.91),

    # Mistral Tekken
    # 效率: En 1.1x, Zh 1.3x, Code 1.3x
    # 系数: 0.91, 0.77, 0.77
    "mistral":  (131000, _get_cl100k, 0.91, 0.77, 0.77),
    
    # === 256k 级 (Unigram) ===
    # Gemini 1.5
    # 效率: En 1.0x, Zh 1.5x, Code 1.2x
    # 系数: 1.0, 0.67, 0.83
    "gemini":   (256000, _get_cl100k, 1.00, 0.67, 0.83),
    "gemma":    (256000, _get_cl100k, 1.00, 0.67, 0.83),
}

# 预编译正则，匹配中日韩字符及全角标点
CJK = re.compile(r'[\u3000-\u9fff\uac00-\ud7af\uff00-\uffef]')


def estimate_tokens(text: str, model: str = None, is_code: bool = False) -> int:
    """
    估算文本 Token 数量 (v3.0 - 基于2025 Q1实测数据)
    """
    if not text:
        return 0
    
    # 1. 匹配模型配置
    cfg = None
    if model:
        m = model.lower()
        for key in CONFIG:
            if key in m:
                cfg = CONFIG[key]
                break
    
    # 2. 默认回退逻辑 (Fall back to cl100k standard)
    # 如果找不到模型，使用 cl100k 作为工业标准，不带任何偏置系数
    if cfg is None:
        cfg = (100000, _get_cl100k, 1.0, 1.0, 1.0)
    
    # 解包配置
    vocab_size, encoder_fn, en_factor, zh_factor, code_factor = cfg
    
    # 3. 获取基准 Token 数
    # disallowed_special=() 允许处理所有文本，防止报错
    base_count = len(encoder_fn().encode(text, disallowed_special=()))
    
    # 4. 计算动态修正系数
    final_factor = 1.0
    
    if is_code:
        final_factor = code_factor
    else:
        # 计算中文占比 (0.0 ~ 1.0)
        cjk_chars = len(CJK.findall(text))
        ratio = cjk_chars / len(text) if len(text) > 0 else 0
        
        # 线性插值：根据中文浓度混合中英系数
        final_factor = zh_factor * ratio + en_factor * (1 - ratio)
    
    # 5. 输出结果 (向上取整并确保至少为1)
    return max(1, int(base_count * final_factor))


def get_vocab_size(model: str) -> int:
    """获取模型词表大小 (用于参考)"""
    if not model:
        return 100000
    m = model.lower()
    for key, cfg in CONFIG.items():
        if key in m:
            return cfg[0]
    return 100000
