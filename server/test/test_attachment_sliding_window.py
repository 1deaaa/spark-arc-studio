"""附件分片滑动窗口（read_attachment_chunk 历史折叠）测试

覆盖：
1. ``collapse_attachment_chunk_history`` 折叠规则
   - 只对 read_attachment_chunk 的 ToolMessage 生效
   - fresh_call_ids 内的不被折叠
   - 已折叠的不重复折叠
   - tool_call_id / name 在折叠后保留
   - 其他工具的 ToolMessage 不被影响
2. **端到端真实 epub 模拟**：
   - 解析真实 epub 文件 → 落盘成附件
   - 模拟导演多轮调用 read_attachment_chunk
   - 每轮后核对 messages 列表的 token 变化
   - 验证：上下文增量 ≤ 单片大小，绝对不会累积
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


# ==================== 单元：折叠规则 ====================


def test_collapse_replaces_old_attachment_chunk_messages_with_placeholder():
    """旧 read_attachment_chunk 的 ToolMessage content 被替换为占位，新一片保留完整正文。"""
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    from agents.communication import (
        ATTACHMENT_CHUNK_COLLAPSED_PLACEHOLDER,
        collapse_attachment_chunk_history,
    )

    long_text_old = '老的 chunk 全文 ' * 1000
    long_text_new = '新的 chunk 全文 ' * 1000

    messages = [
        HumanMessage(content='请总结附件'),
        AIMessage(content='我先读第 1 部分'),
        ToolMessage(content=long_text_old, tool_call_id='call_1', name='read_attachment_chunk'),
        AIMessage(content='第 1 部分的关键信息：xxx。继续读第 2 部分。'),
        ToolMessage(content=long_text_new, tool_call_id='call_2', name='read_attachment_chunk'),
    ]

    collapsed = collapse_attachment_chunk_history(messages, fresh_call_ids={'call_2'})

    assert collapsed == 1
    # 旧消息：折叠
    assert messages[2].content == ATTACHMENT_CHUNK_COLLAPSED_PLACEHOLDER
    assert messages[2].tool_call_id == 'call_1'
    assert messages[2].name == 'read_attachment_chunk'
    # 新消息：完整保留
    assert messages[4].content == long_text_new
    assert messages[4].tool_call_id == 'call_2'


def test_collapse_does_not_touch_other_tools():
    """其他工具（如 web_search、semantic_search）的 ToolMessage 不被影响。"""
    from langchain_core.messages import AIMessage, ToolMessage

    from agents.communication import collapse_attachment_chunk_history

    big_search_result = '语义搜索返回的大段文本 ' * 500

    messages = [
        AIMessage(content='我先做语义搜索'),
        ToolMessage(content=big_search_result, tool_call_id='call_1', name='semantic_search'),
        AIMessage(content='再读附件第 1 部分'),
        ToolMessage(content='附件 chunk_1 全文', tool_call_id='call_2', name='read_attachment_chunk'),
        AIMessage(content='再读第 2 部分'),
        ToolMessage(content='附件 chunk_2 全文', tool_call_id='call_3', name='read_attachment_chunk'),
    ]

    collapsed = collapse_attachment_chunk_history(messages, fresh_call_ids={'call_3'})

    # 只折叠了 1 个（call_2）
    assert collapsed == 1
    # semantic_search 的 ToolMessage 完全没动
    assert messages[1].content == big_search_result
    # call_3 是 fresh，保留
    assert messages[5].content == '附件 chunk_2 全文'


def test_collapse_idempotent_does_not_repeat():
    """已经折叠过的 ToolMessage 第二次调用 collapse 不会重复处理。"""
    from langchain_core.messages import ToolMessage

    from agents.communication import (
        ATTACHMENT_CHUNK_COLLAPSED_PLACEHOLDER,
        collapse_attachment_chunk_history,
    )

    messages = [
        ToolMessage(
            content=ATTACHMENT_CHUNK_COLLAPSED_PLACEHOLDER,
            tool_call_id='call_1',
            name='read_attachment_chunk',
        ),
        ToolMessage(
            content='当前最新片正文',
            tool_call_id='call_2',
            name='read_attachment_chunk',
        ),
    ]

    collapsed = collapse_attachment_chunk_history(messages, fresh_call_ids={'call_2'})
    assert collapsed == 0  # 第一条已折叠，第二条是 fresh
    assert messages[0].content == ATTACHMENT_CHUNK_COLLAPSED_PLACEHOLDER
    assert messages[1].content == '当前最新片正文'


def test_collapse_with_empty_fresh_collapses_all_old_chunks():
    """fresh_call_ids 为空时，所有 read_attachment_chunk 的 ToolMessage 都被折叠（极端场景）。"""
    from langchain_core.messages import ToolMessage

    from agents.communication import (
        ATTACHMENT_CHUNK_COLLAPSED_PLACEHOLDER,
        collapse_attachment_chunk_history,
    )

    messages = [
        ToolMessage(content='片 1 正文', tool_call_id='c1', name='read_attachment_chunk'),
        ToolMessage(content='片 2 正文', tool_call_id='c2', name='read_attachment_chunk'),
        ToolMessage(content='片 3 正文', tool_call_id='c3', name='read_attachment_chunk'),
    ]

    collapsed = collapse_attachment_chunk_history(messages, fresh_call_ids=set())
    assert collapsed == 3
    for m in messages:
        assert m.content == ATTACHMENT_CHUNK_COLLAPSED_PLACEHOLDER


# ==================== 端到端：真实 epub 文件读取 + 滑窗模拟 ====================


REAL_EPUB_PATH = r'D:\Desktop\被窝是青春的坟墓.epub'


@pytest.fixture
def real_epub_attachment(tmp_path, monkeypatch):
    """解析真实 epub 文件 → 落盘为附件，返回 attachment_id + 项目目录。

    若桌面文件不存在则跳过整个 e2e 测试（CI 友好）。
    """
    if not os.path.exists(REAL_EPUB_PATH):
        pytest.skip(f'真实 epub 文件不存在：{REAL_EPUB_PATH}（在 CI 上正常跳过）')

    # 隔离项目目录
    project_path = tmp_path / 'projects' / 'sliding_window_demo'
    project_path.mkdir(parents=True, exist_ok=True)

    def _fake_get_project_path(user_id: str, project_name: str) -> str:  # noqa: ARG001
        return str(project_path)

    monkeypatch.setattr('agents.attachment.storage.get_project_path', _fake_get_project_path)

    from agents.attachment import save_attachment
    from core.file_ingest import parse_uploaded_file

    parsed = parse_uploaded_file(REAL_EPUB_PATH, filename='被窝是青春的坟墓.epub')

    # 用 file_ingest 自带的 token splitter 切分
    from core.file_ingest.chunking import split_text_by_tokens
    chunks = split_text_by_tokens(parsed.full_text, chunk_tokens=64000)
    chunk_texts = [c.text for c in chunks]

    meta = save_attachment(
        user_id='user_e2e',
        project_name='sliding_window_demo',
        filename='被窝是青春的坟墓.epub',
        source_format='.epub',
        full_text=parsed.full_text,
        chunks=chunk_texts,
        total_tokens=sum(c.estimated_tokens for c in chunks),
    )

    return {
        'attachment_id': meta.attachment_id,
        'chunk_count': meta.chunk_count,
        'total_chars': len(parsed.full_text),
        'project_path': str(project_path),
    }


def _estimate_tokens(text: str) -> int:
    """统一的 token 估算：中文按字数算，英文按词长 / 4，做个粗略折中。"""
    return max(1, len(text) // 2)  # 中文场景下平均 2 char ≈ 1 token


def test_real_epub_sliding_window_keeps_context_bounded(real_epub_attachment, monkeypatch):
    """端到端：用真实 epub 模拟导演 N 轮 read_attachment_chunk 调用，
    每轮后 dump messages 状态，验证：
    1. ToolMessage 内容能正确读取（前 100 字符里包含中文）
    2. 滑窗折叠后历史 ToolMessage 全是占位文本
    3. 最新 1 片完整保留
    4. 总 token 数始终 ≤ 单片估算 + 占位开销，绝对不累积
    """
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    from agents.communication import (
        ATTACHMENT_CHUNK_COLLAPSED_PLACEHOLDER,
        collapse_attachment_chunk_history,
    )
    from agents.tools.attachment import read_attachment_chunk

    # 模拟导演聊天上下文（ToolExecutionContext.get_context() 读取 ContextVar）
    from core.request_context import current_project_name, current_user_id
    user_token = current_user_id.set('user_e2e')
    project_token = current_project_name.set('sliding_window_demo')

    info = real_epub_attachment
    aid = info['attachment_id']
    chunk_count = info['chunk_count']

    print(f"\n[E2E] 真实 epub 解析：{info['total_chars']:,} chars → {chunk_count} 个分片")
    assert chunk_count >= 2, '本测试需要至少 2 个分片（说明文件足够大）'

    # ---- 模拟导演的 messages 序列 ----
    messages = [HumanMessage(content='请总结这本小说的核心主题')]

    token_history: list[int] = []

    # 模拟最多读 min(chunk_count, 4) 片，足够看出滑窗效果
    rounds = min(chunk_count, 4)
    for i in range(rounds):
        # AIMessage 模拟 LLM 决策"调 read_attachment_chunk"
        call_id = f'call_chunk_{i}'
        ai_msg = AIMessage(
            content=f'第 {i + 1} 轮提炼：本片关键信息是青春主题、回忆叙事、抒情语气...',
            tool_calls=[{
                'name': 'read_attachment_chunk',
                'args': {'attachment_id': aid, 'chunk_index': i},
                'id': call_id,
            }],
        )
        messages.append(ai_msg)

        # 真实调用 read_attachment_chunk 工具拿到 chunk 正文
        tool_result = read_attachment_chunk.invoke({
            'attachment_id': aid,
            'chunk_index': i,
        })

        # 内容正确性：前若干字符里应包含汉字（说明真的读到了原文）
        assert isinstance(tool_result, str)
        assert len(tool_result) > 100, '工具返回应为正文级别长文本'
        assert any('\u4e00' <= ch <= '\u9fff' for ch in tool_result[:200]), '前 200 字符应含中文'

        # 模拟 chat_stream 主循环的折叠步骤
        fresh_ids = {call_id}
        messages.append(ToolMessage(
            content=tool_result,
            tool_call_id=call_id,
            name='read_attachment_chunk',
        ))
        collapse_attachment_chunk_history(messages, fresh_call_ids=fresh_ids)

        # 统计当前 messages 的总 token 估算
        total_chars = sum(len(str(m.content)) for m in messages)
        total_tokens = _estimate_tokens(' '.join(str(m.content) for m in messages))
        token_history.append(total_tokens)

        # 内部状态自检
        tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
        latest_tool = tool_msgs[-1]
        old_tools = tool_msgs[:-1]

        # 最新 ToolMessage：未被折叠（content 等于真实 tool_result）
        assert latest_tool.content == tool_result
        assert latest_tool.tool_call_id == call_id
        # 历史 ToolMessage：全是占位
        for m in old_tools:
            assert m.content == ATTACHMENT_CHUNK_COLLAPSED_PLACEHOLDER, (
                f'历史片 {m.tool_call_id} 应被折叠为占位，实际仍是 {len(str(m.content))} 字符'
            )

        print(
            f"  [round {i + 1}/{rounds}] messages={len(messages)} | "
            f"chars={total_chars:,} | est_tokens={total_tokens:,} | "
            f"latest_chunk_chars={len(tool_result):,}"
        )

    # ---- 关键断言：token 总数应当"近乎稳定"，不随轮次线性累积 ----
    # 允许小幅增长（因为每轮多了一个 AIMessage 提炼 + 占位文本），
    # 但增量应该远小于一片完整正文（约 10000 chars）
    if len(token_history) >= 2:
        first_round = token_history[0]
        last_round = token_history[-1]
        per_chunk_full_size = _estimate_tokens('片正文 ' * 10000)  # ~5000 tokens 量级

        growth = last_round - first_round
        print(f'\n[E2E] token 累积情况：第 1 轮 {first_round:,} → 第 {rounds} 轮 {last_round:,} | 增量 {growth:,}')
        assert growth < per_chunk_full_size, (
            f'滑窗失效！token 累积 {growth} 应远小于单片大小 {per_chunk_full_size}'
        )


def test_real_epub_sliding_window_without_collapse_would_explode(real_epub_attachment, monkeypatch):
    """对照实验：如果 NOT 调用折叠 helper，token 将随轮次线性增长。

    这个测试不是 SUT 的覆盖，纯粹是"科学验证"——证明折叠确实有效。
    """
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    from agents.tools.attachment import read_attachment_chunk

    from core.request_context import current_project_name, current_user_id
    user_token = current_user_id.set('user_e2e')
    project_token = current_project_name.set('sliding_window_demo')

    info = real_epub_attachment
    aid = info['attachment_id']
    rounds = min(info['chunk_count'], 4)

    messages = [HumanMessage(content='请总结这本小说的核心主题')]
    token_history: list[int] = []

    for i in range(rounds):
        ai_msg = AIMessage(
            content='略',
            tool_calls=[{
                'name': 'read_attachment_chunk',
                'args': {'attachment_id': aid, 'chunk_index': i},
                'id': f'call_{i}',
            }],
        )
        messages.append(ai_msg)
        tool_result = read_attachment_chunk.invoke({'attachment_id': aid, 'chunk_index': i})
        messages.append(ToolMessage(
            content=tool_result,
            tool_call_id=f'call_{i}',
            name='read_attachment_chunk',
        ))
        # 故意不调 collapse_attachment_chunk_history
        total_tokens = _estimate_tokens(' '.join(str(m.content) for m in messages))
        token_history.append(total_tokens)
        print(f'  [无折叠 round {i + 1}] est_tokens={total_tokens:,}')

    # 不折叠时，最后一轮 token 应当是第一轮的至少 2x（因为多累了若干片）
    if len(token_history) >= 2:
        ratio = token_history[-1] / max(1, token_history[0])
        print(f'\n[对照] 无折叠的 token 增长倍数：{ratio:.2f}x')
        assert ratio >= 1.8, f'对照组应有显著累积，实际增长仅 {ratio:.2f}x'
