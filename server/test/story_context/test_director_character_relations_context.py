from agents.context_provider import AgentContextProvider


def _provider(bundle: dict) -> AgentContextProvider:
    provider = AgentContextProvider.__new__(AgentContextProvider)
    provider.user_id = "test-user"
    provider.project_name = "test-project"
    provider.project_path = None
    provider._bundle_cache = bundle
    provider._build_story_tags_block = lambda: ""
    return provider


def test_director_context_includes_confirmed_character_relations() -> None:
    relation = "- 沈砚 → 顾青：师徒；备注：表面疏离"
    provider = _provider(
        {
            "roles": "--- 角色: 沈砚 ---\n主角",
            "relations_text": relation,
        }
    )

    context = provider.build_context_for_agent("agent_director")

    assert "【作者确认的角色关系】" in context
    assert relation in context


def test_director_context_omits_empty_character_relations_block() -> None:
    provider = _provider(
        {
            "roles": "--- 角色: 沈砚 ---\n主角",
            "relations_text": "",
        }
    )

    context = provider.build_context_for_agent("agent_director")

    assert "【作者确认的角色关系】" not in context


def test_lorebook_keeps_relations_from_detailed_character_summary() -> None:
    relation = "- 沈砚 → 顾青：师徒"
    provider = _provider(
        {
            "characters_detailed_summary": (
                "### 已有角色设定\n\n#### 沈砚\n主角\n"
                f"【作者确认关系】\n{relation}"
            )
        }
    )

    context = provider.build_context_for_agent("agent_lorebook")

    assert "【作者确认关系】" in context
    assert relation in context
