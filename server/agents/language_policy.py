from __future__ import annotations

from core.request_context import get_current_locale, normalize_response_locale

_POLICY_MARKER = "[SPARKARC_LANG_POLICY]"

# 语言标识 → 该语言的自称（用于注入提示词）
# 新增语言只需在此字典添加一行即可，无需再写整段翻译
_LANGUAGE_LABEL = {
    'zh-CN': '中文',
    'en-US': 'English',
    'ja-JP': '日本語',
    'ko-KR': '한국어',
}

# 统一中文模板：直接用中文写一句话注入，大模型完全能理解
# 「{label}」会被替换为当前语言的自称（如 "中文"、"English"、"日本語"）
_POLICY_TEMPLATE = (
    "你必须优先使用{label}完成所有创作和与用户交流，"
    "除非用户主动使用其他语言。"
    "所有面向用户的专名与标题默认使用当前语言下的单一正式名称；"
    "不要在名称或标题后自动追加括号翻译、外语释义、缩写展开、罗马音或学术式副标题。"
    "只有用户明确要求双语命名，或既有正式名称本身确实包含括号时才保留；正文中的必要括号说明不受此限制。"
    "若任务要求固定输出协议（如 JSON、代码、标记语言），请先满足协议格式，再在自然语言说明中遵循上述语言规则。"
)


def resolve_agent_locale(locale: str | None = None) -> str:
    if locale is not None:
        return normalize_response_locale(locale)
    return get_current_locale()


def build_language_policy_prefix(locale: str | None = None) -> str:
    resolved = resolve_agent_locale(locale)
    label = _LANGUAGE_LABEL.get(resolved, _LANGUAGE_LABEL['zh-CN'])
    policy_text = _POLICY_TEMPLATE.format(label=label)
    return (
        f"{_POLICY_MARKER}\n"
        f"首选语言: {label}\n"
        f"规则: {policy_text}\n"
        f"{_POLICY_MARKER}\n\n"
    )


def prepend_prompt_language_policy(prompt: str, locale: str | None = None) -> str:
    if not isinstance(prompt, str):
        return prompt

    content = prompt.strip()
    if not content:
        return prompt

    if content.startswith(_POLICY_MARKER):
        return prompt

    return build_language_policy_prefix(locale) + prompt
