from __future__ import annotations

from core.request_context import get_current_locale, normalize_response_locale

_POLICY_MARKER = "[SPARKARC_LANG_POLICY]"

_LANGUAGE_LABEL = {
    'zh-CN': '中文',
    'en-US': 'English',
    'ja-JP': '日本語',
}

_POLICY_TEXT = {
    'zh-CN': (
        "你必须优先使用当前语言（中文）进行交流与创作。"
        "仅当用户主动使用其他语言或明确要求切换时，才可以切换到用户指定语言。"
        "若任务要求固定输出协议（如 JSON、代码、标记语言），请先满足协议格式，再在自然语言说明中遵循上述语言规则。"
    ),
    'en-US': (
        "You must prioritize the current language (English) for communication and creative writing. "
        "Only switch when the user proactively uses another language or explicitly asks for a language change. "
        "When a strict output protocol is required (JSON/code/markup), satisfy that protocol first, then apply the language rule to natural-language narration."
    ),
    'ja-JP': (
        "対話・創作では現在の言語（日本語）を優先してください。"
        "ユーザーが自発的に他言語を使う、または明示的に切り替えを求めた場合にのみ、その言語へ切り替えてください。"
        "JSON・コード・マークアップなど厳密な出力形式が必要な場合は形式要件を優先し、その上で自然言語の説明には上記の言語ルールを適用してください。"
    ),
}


def resolve_agent_locale(locale: str | None = None) -> str:
    if locale is not None:
        return normalize_response_locale(locale)
    return get_current_locale()


def build_language_policy_prefix(locale: str | None = None) -> str:
    resolved = resolve_agent_locale(locale)
    label = _LANGUAGE_LABEL.get(resolved, _LANGUAGE_LABEL['zh-CN'])
    policy_text = _POLICY_TEXT.get(resolved, _POLICY_TEXT['zh-CN'])
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
