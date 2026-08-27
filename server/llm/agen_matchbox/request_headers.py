"""统一构建发往上游模型服务的请求头。"""

from __future__ import annotations

from typing import Mapping, Optional


SPARKARC_HANDSHAKE_HEADER = "X-SparkArc-Client"
SPARKARC_HANDSHAKE_VALUE = "sparkarc"


def build_upstream_request_headers(
    existing_headers: Optional[Mapping[str, str]] = None,
) -> dict[str, str]:
    """在已有请求头上补充固定的 SparkArc 客户端标识。

    标识不携带用户、项目、会话或请求序号等动态信息，因此不会改变请求
    消息内容，也不会把动态数据引入上游提示词缓存前缀。
    """
    headers = dict(existing_headers or {})
    header_name = SPARKARC_HANDSHAKE_HEADER.casefold()
    for key in list(headers):
        if str(key).casefold() == header_name:
            del headers[key]
    headers[SPARKARC_HANDSHAKE_HEADER] = SPARKARC_HANDSHAKE_VALUE
    return headers
