import inspect
import sqlite3

from sqlalchemy import text


def _create_legacy_schema(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE llm_platforms (
                id INTEGER PRIMARY KEY,
                name VARCHAR(80),
                user_id VARCHAR(255),
                base_url VARCHAR(255) NOT NULL,
                api_key VARCHAR(512),
                is_sys INTEGER DEFAULT 0,
                disable INTEGER DEFAULT 0,
                sort_order INTEGER DEFAULT 0,
                sys_credit_price_per_million_tokens INTEGER
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE llm_platform_models (
                id INTEGER PRIMARY KEY,
                platform_id INTEGER NOT NULL,
                model_name VARCHAR(120) NOT NULL,
                display_name VARCHAR(120),
                extra_body VARCHAR(1024),
                temperature FLOAT,
                max_context_tokens INTEGER DEFAULT 200000,
                max_output_tokens INTEGER DEFAULT 64000,
                sys_credit_price_per_million_tokens INTEGER,
                disable INTEGER DEFAULT 0,
                is_embedding INTEGER DEFAULT 0,
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY(platform_id) REFERENCES llm_platforms(id) ON DELETE CASCADE
            )
            """
        )
        # 旧库漂移：错误地把 user_id 做成了单列唯一，导致同一用户只能配置一个平台 key。
        cur.execute(
            """
            CREATE TABLE llm_sys_platform_keys (
                id INTEGER PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL UNIQUE,
                platform_id INTEGER NOT NULL,
                api_key VARCHAR(512),
                disable INTEGER DEFAULT 0,
                FOREIGN KEY(platform_id) REFERENCES llm_platforms(id) ON DELETE CASCADE
            )
            """
        )

        cur.execute(
            """
            INSERT INTO llm_platforms (
                id, name, user_id, base_url, api_key, is_sys, disable, sort_order, sys_credit_price_per_million_tokens
            ) VALUES
                (1, 'SysA', '-1', 'https://a.example.com/v1', NULL, 1, 0, 0, NULL),
                (2, 'SysB', '-1', 'https://b.example.com/v1', NULL, 1, 0, 1, NULL)
            """
        )

        conn.commit()
    finally:
        conn.close()


def test_test_platform_chat_default_timeout_is_30_seconds() -> None:
    from llm.agen_matchbox.utils import test_platform_chat

    timeout_default = inspect.signature(test_platform_chat).parameters["timeout"].default
    assert timeout_default == 30.0


def test_legacy_sys_key_unique_constraint_auto_repair(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENT_MATCHBOX_HOME", str(tmp_path / "matchbox_home"))
    monkeypatch.setenv("LLM_KEY", "unit-test-llm-key")

    # 确保测试进程使用当前环境变量重新初始化安全管理器。
    from llm.agen_matchbox.security import SecurityManager

    SecurityManager._instance = None

    db_path = tmp_path / "legacy_llm_config.db"
    _create_legacy_schema(str(db_path))

    from llm.agen_matchbox.manager import AIManager

    manager = AIManager(db_name=str(db_path))

    # 若修复生效，同一用户应能为两个不同系统平台分别保存 key。
    manager.update_platform_config("1001", 1, "key-for-a")
    manager.update_platform_config("1001", 2, "key-for-b")

    with manager.Session() as session:
        rows = session.execute(
            text(
                """
                SELECT user_id, platform_id
                FROM llm_sys_platform_keys
                WHERE user_id = :uid
                ORDER BY platform_id ASC
                """
            ),
            {"uid": "1001"},
        ).all()

    assert len(rows) == 2
    assert [r[1] for r in rows] == [1, 2]

    platforms = manager.get_platforms("1001")
    status_by_platform = {item["platform_id"]: item["api_key_set"] for item in platforms if item["is_sys"]}

    assert status_by_platform.get(1) is True
    assert status_by_platform.get(2) is True
