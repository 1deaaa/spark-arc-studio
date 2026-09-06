"""附件缓存引用与回收行为回归。"""

from __future__ import annotations


def test_attachment_metadata_uses_imported_files_as_single_source() -> None:
    from agents.routes.chat_attachment import (
        build_user_message_metadata,
        extract_imported_files_meta,
    )

    legacy_only = {
        "importedFile": {"attachmentId": "legacy", "filename": "旧附件.txt"}
    }
    assert extract_imported_files_meta(legacy_only) == []

    active_meta = {
        "importedFiles": [
            {"attachmentId": "attachment-1", "filename": "附件.txt"},
            {"attachmentId": "attachment-1", "filename": "重复附件.txt"},
            {"attachment_id": "legacy-snake", "filename": "旧字段.txt"},
        ]
    }
    files = extract_imported_files_meta(active_meta)
    assert files == [
        {
            "attachmentId": "attachment-1",
            "filename": "附件.txt",
            "sourceFormat": "",
            "totalTokens": 0,
            "chunkTokens": 0,
            "isPartial": False,
            "isOversized": False,
            "warnings": [],
            "uploadedAt": 0,
        }
    ]

    metadata = build_user_message_metadata("direct", "当前上下文", files)
    assert metadata["importedFiles"] == files
    assert "importedFile" not in metadata


def test_attachment_gc_deletes_only_unreferenced_cache(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))

    from agents.attachment import collect_orphan_attachments, save_attachment

    project_path = tmp_path / "uid_41" / "projects" / "demo"
    project_path.mkdir(parents=True)
    referenced = save_attachment("41", "demo", "保留.txt", "txt", "保留正文", ["保留正文"], 4)
    orphan = save_attachment("41", "demo", "孤儿.txt", "txt", "孤儿正文", ["孤儿正文"], 4)

    monkeypatch.setattr(
        "agents.attachment.gc._referenced_attachment_ids",
        lambda user_id, project_name: {referenced.attachment_id},
    )

    result = collect_orphan_attachments("41", "demo")

    assert result["deleted"] == [orphan.attachment_id]
    assert referenced.attachment_id in result["retained"]
    assert (project_path / ".attachments" / referenced.attachment_id).is_dir()
    assert not (project_path / ".attachments" / orphan.attachment_id).exists()


def test_save_attachment_reconciles_stale_chunks_on_reupload(monkeypatch, tmp_path) -> None:
    """同内容重传 + 切分变化时，磁盘分片必须与本次切分对账，不留多余旧分片。"""
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))

    from agents.attachment import get_attachment_meta, load_chunks, save_attachment

    project_path = tmp_path / "uid_42" / "projects" / "demo"
    project_path.mkdir(parents=True)

    first = save_attachment("42", "demo", "长文.txt", "txt", "正文", ["第一片", "第二片"], 10)
    assert len(load_chunks("42", "demo", first.attachment_id)) == 2

    second = save_attachment("42", "demo", "长文.txt", "txt", "正文", ["唯一片"], 5)

    assert second.attachment_id == first.attachment_id
    assert get_attachment_meta("42", "demo", first.attachment_id).chunk_count == 1
    assert load_chunks("42", "demo", first.attachment_id) == ["唯一片"]
    chunk_dir = project_path / ".attachments" / first.attachment_id / "chunks"
    assert sorted(p.name for p in chunk_dir.iterdir()) == ["chunk_0.txt"]
