from __future__ import annotations


def test_semantic_result_location_uses_full_search_budget(monkeypatch) -> None:
    from agents.tools import search

    observed = []

    def fake_collect(user_id, project_name, *, max_source_chars):
        observed.append((user_id, project_name, max_source_chars))
        return []

    monkeypatch.setattr("story.project_files.collect_project_files", fake_collect)

    assert search._locate_chunk_positions("7", "demo", []) == []
    assert observed == [("7", "demo", search.SEARCH_MAX_SOURCE_CHARS)]
