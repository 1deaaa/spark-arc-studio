from pathlib import Path
import sys


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


from agents.communication import SparkBaseAgent


def test_tool_call_chunks_without_index_share_one_buffer():
    agent = SparkBaseAgent(agent_id="agent_showrunner", user_id="1")
    buffers = {}

    first_index = agent._append_tool_call_chunk_buffer(
        buffers,
        {"name": "patch_outline", "args": '{"search_text": "旧文本", '},
    )
    second_index = agent._append_tool_call_chunk_buffer(
        buffers,
        {"args": '"replace_text": "新文本"}'},
    )

    assert first_index == 0
    assert second_index == 0
    assert len(buffers) == 1

    specs = agent._build_tool_specs_from_chunk_buffers(buffers)
    assert len(specs) == 1
    assert specs[0]["name"] == "patch_outline"
    assert specs[0]["args"] == {"search_text": "旧文本", "replace_text": "新文本"}
