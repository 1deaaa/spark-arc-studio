from __future__ import annotations

from typing import Optional

from .request_context import get_current_locale, normalize_response_locale
from .system_settings import get_force_public_share_review


def is_mainland_compliance_locale(locale: Optional[str] = None) -> bool:
    effective_locale = normalize_response_locale(locale if locale is not None else get_current_locale())
    return effective_locale == "zh-CN"



def is_force_public_share_review_effective(locale: Optional[str] = None) -> bool:
    return is_mainland_compliance_locale(locale) and get_force_public_share_review()
