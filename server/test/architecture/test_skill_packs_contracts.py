from __future__ import annotations

from pathlib import Path

from agents.communication import SparkBaseAgent
from agents.skill_packs import (
    build_quality_adapter_text,
    import_skill_markdown,
    public_skill_record,
    read_skill,
    read_skill_reference,
)
from agents.tools.registry import get_tools_for_agent


def test_skill_tools_are_stable_tools_not_dynamic_system_payload() -> None:
    agent = SparkBaseAgent("agent_scriptwriter", user_id="skill-test", project_name="demo")
    prompt = agent._build_tool_system_prompt("基础提示词", skip_tool_confirmation=False)

    assert "search_skills" in {tool.name for tool in get_tools_for_agent("agent_scriptwriter")}
    assert "Agent Skills 读取边界" in prompt
    assert "SKILL.md 正文" not in prompt
    assert "按需读取一个 Skill 的质量适配视图" in prompt
    assert "QUALITY_ADAPTER" not in prompt


def test_quality_adapter_drops_runtime_workflow_sections() -> None:
    raw = """---
name: Workflow Writer
description: Helps prose quality.
---
# Workflow Writer

## Writing Principles
Use concrete sensory detail and make dialogue carry subtext.

## Script Usage
Run `python scripts/write.py` and call the external tool before drafting.

```python
print("should not enter model context")
```
"""

    adapted, meta = build_quality_adapter_text(raw)

    assert "concrete sensory detail" in adapted
    assert "dialogue carry subtext" in adapted
    assert "python scripts" not in adapted
    assert "external tool" not in adapted
    assert "print(" not in adapted
    assert meta["dropped_runtime_sections"] >= 1


def test_read_skill_returns_quality_view_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("agents.skill_packs.USERDATA_ROOT", str(tmp_path))

    raw = """---
name: Quality Only
description: Improves prose.
---
# Quality Only

## Style Checklist
- Prefer specific verbs.

## Installation
Install packages and run scripts/do_work.sh.
"""
    imported = import_skill_markdown("42", raw)
    text = read_skill("42", imported.skill_id)

    assert "读取视图：quality_only" in text
    assert "Prefer specific verbs" in text
    assert "scripts/do_work.sh" not in text


def test_skill_reference_and_public_record_do_not_leak_runtime_material(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("agents.skill_packs.USERDATA_ROOT", str(tmp_path))

    raw = """---
name: Ref Skill
description: Has references.
---
# Ref Skill

## Style
Use tense verbs.
"""
    imported = import_skill_markdown("42", raw)
    skill_dir = tmp_path / "uid_42" / ".sparkarc" / "user_skills" / "packs" / imported.skill_id.replace(":", "__")
    ref_dir = skill_dir / "references"
    ref_dir.mkdir(parents=True, exist_ok=True)
    (ref_dir / "guide.md").write_text(
        "## Quality Checklist\nUse images that reveal character.\n\n## Tool Workflow\nRun scripts/refine.py",
        encoding="utf-8",
    )

    # 模拟旧索引补充参考路径，避免重新导入影响测试焦点。
    text = read_skill_reference("42", imported.skill_id, "references/guide.md")
    assert "Use images that reveal character" in text
    assert "scripts/refine.py" not in text

    record = public_skill_record({
        "skill_id": imported.skill_id,
        "name": imported.name,
        "storage_path": str(skill_dir),
        "content_hash": "secret",
    })
    assert "storage_path" not in record
    assert "content_hash" not in record
