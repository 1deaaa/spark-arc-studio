"""大陆合规能力的语言门控契约测试。"""

from core.compliance_features import (
    is_force_public_share_review_effective,
    is_mainland_compliance_locale,
)


def test_public_share_review_is_effective_only_for_mainland_locale(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.compliance_features.get_force_public_share_review",
        lambda: True,
    )

    assert is_mainland_compliance_locale("zh-CN") is True
    assert is_force_public_share_review_effective("zh-CN") is True

    for locale in ("en-US", "ja-JP", "ko-KR"):
        assert is_mainland_compliance_locale(locale) is False
        assert is_force_public_share_review_effective(locale) is False
"""中国大陆地区合规行为回归。"""
