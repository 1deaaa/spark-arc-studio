"""
守护对象：
- 平台充值地址是平台级配置，必须进入数据库。
- matchbox_cfg.yaml 的导入、强制重置与导出必须保留充值地址。
- 用户自定义平台与系统平台使用同一套充值地址归一逻辑。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


SERVER_ROOT = Path(__file__).resolve().parents[2]


def _run_probe(code: str, tmp_path: Path) -> str:
    env = os.environ.copy()
    env["AGENT_MATCHBOX_HOME"] = str(tmp_path / "matchbox-home")

    completed = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", code],
        cwd=SERVER_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def test_matchbox_yaml_platform_recharge_url_roundtrip(tmp_path: Path) -> None:
    code = r"""
from pathlib import Path
import os
import yaml

from llm.agen_matchbox.manager import AIManager
from llm.agen_matchbox.models import LLMPlatform

home = Path(os.environ["AGENT_MATCHBOX_HOME"])
home.mkdir(parents=True, exist_ok=True)
cfg = {
    "充值测试平台": {
        "base_url": "https://api.billing-example.test/v1",
        "recharge_url": "https://billing-example.test/top-up",
        "models": {
            "测试模型": "billing-model",
        },
    },
}
(home / "matchbox_cfg.yaml").write_text(
    yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
    encoding="utf-8",
)

manager = AIManager()
from llm.agen_matchbox.models import Base
Base.metadata.create_all(manager.engine)
manager.admin_reload_from_yaml()

with manager.Session() as session:
    platform = session.query(LLMPlatform).filter_by(name="充值测试平台").one()
    print(f"db_recharge_url={platform.recharge_url}")

exported = manager.admin_build_export_data()
print(f"export_recharge_url={exported['充值测试平台']['recharge_url']}")
"""

    output = _run_probe(code, tmp_path)

    assert "db_recharge_url=https://billing-example.test/top-up" in output
    assert "export_recharge_url=https://billing-example.test/top-up" in output


def test_matchbox_custom_platform_recharge_url_updates_and_clears(tmp_path: Path) -> None:
    code = r"""
from llm.agen_matchbox.manager import AIManager
from llm.agen_matchbox.models import LLMPlatform

manager = AIManager()
from llm.agen_matchbox.models import Base
Base.metadata.create_all(manager.engine)
platform = manager.add_platform(
    "用户充值平台",
    "https://api.custom-billing.test/v1",
    user_id="user-1",
    recharge_url="https://custom-billing.test/pay",
)

with manager.Session() as session:
    stored = session.query(LLMPlatform).filter_by(id=platform.id).one()
    print(f"created_recharge_url={stored.recharge_url}")

manager.update_platform_details(
    "user-1",
    platform.id,
    "用户充值平台",
    "https://api.custom-billing.test/v1",
    recharge_url="",
    update_recharge_url=True,
)

with manager.Session() as session:
    stored = session.query(LLMPlatform).filter_by(id=platform.id).one()
    print(f"cleared_recharge_url={stored.recharge_url}")
"""

    output = _run_probe(code, tmp_path)

    assert "created_recharge_url=https://custom-billing.test/pay" in output
    assert "cleared_recharge_url=None" in output


def test_matchbox_hosted_key_policy_distinguishes_owner_admin_from_shared_users(tmp_path: Path) -> None:
    code = r"""
import os
from concurrent.futures import ThreadPoolExecutor

os.environ["LLM_KEY"] = "matchbox-owner-policy-test-key"

from core.request_context import set_current_context
from llm.routes_llm import _run_with_user_context
from llm.agen_matchbox.manager import AIManager
from llm.agen_matchbox.models import LLMPlatform

manager = AIManager()
from llm.agen_matchbox.models import Base
Base.metadata.create_all(manager.engine)
manager.llm_auto_key = False

platform = manager.admin_add_sys_platform(
    "托管策略测试平台",
    "https://api.hosted-policy.test/v1",
    "sk-hosted",
)
model = manager.add_model(
    platform.id,
    "hosted-chat-model",
    "托管聊天模型",
    admin_mode=True,
)

with manager.Session() as session:
    manager._resolve_default_ids_from_db(session)
    platform_obj = session.query(LLMPlatform).filter_by(id=platform.id).one()

    set_current_context("user-1", None, False)
    ordinary_access = manager._get_effective_api_access(session, "user-1", platform_obj)
    ordinary_view = manager._collect_platform_views(session, "user-1")[0]
    print(f"ordinary_api_key={bool(ordinary_access['api_key'])}")
    print(f"ordinary_status={ordinary_view['api_key_status']}")

    set_current_context("admin-1", None, True)
    admin_access = manager._get_effective_api_access(session, "admin-1", platform_obj)
    admin_view = manager._collect_platform_views(session, "admin-1")[0]
    print(f"admin_api_key={bool(admin_access['api_key'])}")
    print(f"admin_quota_scope={admin_access['quota_scope']}")
    print(f"admin_key_source={admin_access['key_source']}")
    print(f"admin_status={admin_view['api_key_status']}")

    manager.llm_auto_key = True
    set_current_context("user-1", None, False)
    shared_access = manager._get_effective_api_access(session, "user-1", platform_obj)
    shared_view = manager._collect_platform_views(session, "user-1")[0]
    print(f"shared_api_key={bool(shared_access['api_key'])}")
    print(f"shared_status={shared_view['api_key_status']}")

manager.llm_auto_key = False
set_current_context("admin-1", None, False)
with ThreadPoolExecutor(max_workers=1) as pool:
    admin_selection = pool.submit(
        _run_with_user_context,
        {"user_id": "admin-1", "is_admin": True},
        manager.get_user_selection_detail,
        "admin-1",
    ).result()
print(f"admin_selection_missing={bool(admin_selection['current'].get('missing_key'))}")
"""

    output = _run_probe(code, tmp_path)

    assert "ordinary_api_key=False" in output
    assert "ordinary_status=managed_available_but_locked" in output
    assert "admin_api_key=True" in output
    assert "admin_quota_scope=sys_paid" in output
    assert "admin_key_source=system_hosted" in output
    assert "admin_status=managed_owner_ok" in output
    assert "admin_selection_missing=False" in output
    assert "shared_api_key=True" in output
    assert "shared_status=managed_ok" in output


def test_matchbox_model_modalities_drive_model_views(tmp_path: Path) -> None:
    code = r"""
from llm.agen_matchbox.manager import AIManager

manager = AIManager()
from llm.agen_matchbox.models import Base
Base.metadata.create_all(manager.engine)
platform = manager.add_platform(
    "能力集合测试平台",
    "https://api.capability-view.test/v1",
    user_id="user-1",
)

manager.add_model(
    platform.id,
    "shared-remote-model",
    "聊天模型",
    user_id="user-1",
    input_modalities=["text"],
    output_modalities=["text"],
)
manager.add_model(
    platform.id,
    "shared-remote-model",
    "向量模型",
    user_id="user-1",
    input_modalities=["text"],
    output_modalities=["embedding"],
)
manager.add_model(
    platform.id,
    "shared-remote-model",
    "生图模型",
    user_id="user-1",
    input_modalities=["text", "image"],
    output_modalities=["image"],
)

platform_views = manager.get_platforms_with_models("user-1")
flat_chat_models = manager.get_platform_models("user-1")
embedding_views = manager.get_platforms_with_embeddings("user-1")

print(f"all_model_count={len(platform_views[0]['models'])}")
print(f"chat_model_count={len(flat_chat_models)}")
print(f"embedding_count={len(embedding_views[0]['embeddings'])}")
for model in platform_views[0]["models"]:
    print(
        f"{model['display_name']}="
        f"in:{','.join(model['input_modalities'])}|"
        f"out:{','.join(model['output_modalities'])}"
    )
"""

    output = _run_probe(code, tmp_path)

    assert "all_model_count=3" in output
    assert "chat_model_count=1" in output
    assert "embedding_count=1" in output
    assert "聊天模型=in:text|out:text" in output
    assert "向量模型=in:text|out:embedding" in output
    assert "生图模型=in:text,image|out:image" in output


def test_matchbox_image_adapter_is_preserved_as_model_field_not_extra_body(tmp_path: Path) -> None:
    code = r"""
from llm.agen_matchbox.manager import AIManager
from llm.agen_matchbox.image_generation import _select_adapter

manager = AIManager()
from llm.agen_matchbox.models import Base
Base.metadata.create_all(manager.engine)
platform = manager.add_platform(
    "显式生图协议平台",
    "https://api.x.ai/v1",
    api_key="sk-image-test",
    user_id="user-1",
)
model = manager.add_model(
    platform.id,
    "proxy-image-model",
    "代理生图模型",
    user_id="user-1",
    input_modalities=["text", "image"],
    output_modalities=["image"],
    image_generation_adapter="gemini_interactions",
    extra_body={
        "provider": "xai",
        "adapter": "xai_images",
        "image_generation": {
            "adapter": "gemini_interactions",
            "quality": "high",
        },
    },
)

resolved = manager.resolve_user_image_generation_model(
    "user-1",
    platform_id=platform.id,
    model_id=model.id,
)
print(f"resolved_extra={resolved['extra_body']}")
print(f"resolved_adapter={resolved['image_generation_adapter']}")
print(f"selected_adapter={_select_adapter(resolved)}")
"""

    output = _run_probe(code, tmp_path)

    assert "resolved_extra={'provider': 'xai', 'adapter': 'xai_images', 'image_generation': {'quality': 'high'}}" in output
    assert "resolved_adapter=gemini_interactions" in output
    assert "selected_adapter=gemini_interactions" in output


def test_matchbox_non_text_output_clears_token_pricing(tmp_path: Path) -> None:
    code = r"""
from llm.agen_matchbox.manager import AIManager

manager = AIManager()
from llm.agen_matchbox.models import Base
Base.metadata.create_all(manager.engine)
manager.billing_enabled = True
platform = manager.admin_add_sys_platform(
    "非文本计费清理平台",
    "https://api.non-text-pricing.test/v1",
    "sk-test",
)
model = manager.add_model(
    platform.id,
    "pricing-model",
    "可切换模型",
    admin_mode=True,
    input_modalities=["text"],
    output_modalities=["text"],
    temperature=0.8,
    sys_credit_input_price_per_million=1,
    sys_credit_cached_input_price_per_million=0.5,
    sys_credit_output_price_per_million=2,
)

manager.update_model(
    model.id,
    admin_mode=True,
    input_modalities=["text", "image"],
    output_modalities=["image"],
    update_modalities=True,
)

view = manager.admin_get_sys_platforms(include_models=True)[0]["models"][0]
print(f"input_modalities={','.join(view['input_modalities'])}")
print(f"output_modalities={','.join(view['output_modalities'])}")
print(f"temperature={view['temperature']}")
print(f"input_price={view['sys_credit_input_price_per_million']}")
print(f"cached_input_price={view['sys_credit_cached_input_price_per_million']}")
print(f"output_price={view['sys_credit_output_price_per_million']}")
"""

    output = _run_probe(code, tmp_path)

    assert "input_modalities=text,image" in output
    assert "output_modalities=image" in output
    assert "temperature=None" in output
    assert "input_price=None" in output
    assert "cached_input_price=None" in output
    assert "output_price=None" in output


def test_auth_verify_session_preserves_admin_identity(tmp_path: Path) -> None:
    auth_db = tmp_path / "auth-users.sqlite"
    code = rf"""
import os
from pathlib import Path

auth_db = Path(r"{auth_db}")
os.environ["SPARKARC_USERS_DATABASE_URL"] = "sqlite:///" + auth_db.as_posix()

from core.auth import UserDatabase
from core.models import UserInfo, user_engine

UserInfo.metadata.create_all(user_engine)

db = UserDatabase()

ok, admin_id = db.create_user("admin-user", "secret123")
assert ok, admin_id
admin_token = db.create_session(admin_id)
assert admin_token
admin_ok, admin_info = db.verify_session(admin_token)
print(f"admin_ok={{admin_ok}}")
print(f"admin_is_admin={{admin_info.get('is_admin')}}")

ok, normal_id = db.create_user("normal-user", "secret123")
assert ok, normal_id
normal_token = db.create_session(normal_id)
assert normal_token
normal_ok, normal_info = db.verify_session(normal_token)
print(f"normal_ok={{normal_ok}}")
print(f"normal_is_admin={{normal_info.get('is_admin')}}")
"""

    output = _run_probe(code, tmp_path)

    assert "admin_ok=True" in output
    assert "admin_is_admin=True" in output
    assert "normal_ok=True" in output
    assert "normal_is_admin=False" in output
