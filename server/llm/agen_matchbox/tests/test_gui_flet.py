"""
针对 Flet 0.28.3 重构后 GUI 框架的全面方法级调用测试与属性完备性验证。

测试目标：
1. 验证每个 GUI 方法都可以被正确调用，执行完整逻辑链路，且不产生任何 AttributeError / 运行时报错；
2. 验证所有 Flet 控件的属性在 0.28.3 版本中有效存在；
3. 验证字体侦测与跨平台兼容性；
4. 验证数据操作（CRUD、重命名、排序、保存、配额、明细聚合）对数据库和界面的真实联动。
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import flet as ft

from gui.theme import get_recommended_font_family, create_theme
from gui.dpi import configure_page_window
from gui.main_window import LLMConfigGUI


class MockWindow:
    def __init__(self):
        self.width = 1420
        self.height = 880
        self.min_width = 1180
        self.min_height = 720

    def center(self):
        pass

    def close(self):
        pass


class MockFletPage:
    """模拟 Flet 0.28.3 Page 对象的全功能测试环境。"""
    def __init__(self):
        self.title = ""
        self.window = MockWindow()
        self.theme = None
        self.theme_mode = None
        self.padding = 0
        self.spacing = 0
        self.controls = []
        self.dialogs_opened = []
        self.dialogs_closed = []
        self.snacks_opened = []

    def clean(self):
        self.controls.clear()

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        pass

    def open(self, control: ft.Control):
        if not hasattr(control, "open"):
            raise ValueError(f"{control.__class__.__qualname__} has no open attribute")
        control.open = True
        if isinstance(control, ft.SnackBar):
            self.snacks_opened.append(control)
        else:
            self.dialogs_opened.append(control)

    def close(self, control: ft.Control):
        if not hasattr(control, "open"):
            raise ValueError(f"{control.__class__.__qualname__} has no open attribute")
        control.open = False
        self.dialogs_closed.append(control)


class TestFletGUIComprehensive(unittest.TestCase):
    """GUI 方法级与属性全覆盖测试套件。"""

    @classmethod
    def setUpClass(cls):
        cls._orig_db_url = os.environ.get("AGENT_MATCHBOX_DATABASE_URL")
        os.environ["AGENT_MATCHBOX_DATABASE_URL"] = "sqlite://"

    @classmethod
    def tearDownClass(cls):
        if cls._orig_db_url is not None:
            os.environ["AGENT_MATCHBOX_DATABASE_URL"] = cls._orig_db_url
        else:
            os.environ.pop("AGENT_MATCHBOX_DATABASE_URL", None)

    def setUp(self):
        self.mock_page = MockFletPage()
        self.gui = LLMConfigGUI(self.mock_page, auto_bootstrap=False)
        self.gui.probe_models = MagicMock()
        # 预载入基础配置环境
        self.gui._bootstrap_startup_continue()

    # ------------------------------------------------------------------ #
    #  1. 字体跨平台兼容性测试                                              #
    # ------------------------------------------------------------------ #

    def test_font_family_platform_compatibility(self):
        """测试在 Ubuntu Desktop (Linux) 与 Windows 下的字体适配。"""
        # 测试 Windows 平台
        with patch("sys.platform", "win32"):
            win_font = get_recommended_font_family()
            self.assertIn(win_font, ["Microsoft YaHei UI", "Microsoft YaHei"])
            win_theme = create_theme(font_family=win_font)
            self.assertEqual(win_theme.font_family, win_font)

        # 测试 Ubuntu Desktop 平台
        with patch("sys.platform", "linux"):
            ubuntu_font = get_recommended_font_family()
            self.assertEqual(ubuntu_font, "Noto Sans CJK SC")
            ubuntu_theme = create_theme(font_family=ubuntu_font)
            self.assertEqual(ubuntu_theme.font_family, "Noto Sans CJK SC")

        # 验证 page 上的主题被成功注入
        self.assertIsNotNone(self.gui.page.theme)
        self.assertIsNotNone(self.gui.page.theme.font_family)

    # ------------------------------------------------------------------ #
    #  2. 属性完备性测试                                                   #
    # ------------------------------------------------------------------ #

    def test_all_gui_attributes_exist(self):
        """验证重构后的类和控件属性完全齐全。"""
        expected_attrs = [
            "page",
            "current_config",
            "probe_models_cache",
            "platform_display_to_key",
            "platform_keys_in_order",
            "last_selected_platform_name",
            "user_usage_rows",
            "user_usage_sort_column",
            "user_usage_sort_descending",
            "header_status_text",
            "user_usage_status_text",
            "platform_dropdown",
            "base_url_entry",
            "platform_url_entry",
            "recharge_url_entry",
            "api_key_entry",
            "model_list_view",
            "filter_entry",
            "probe_list_view",
            "user_usage_table",
            "log_list_view",
            "ai_manager",
        ]
        for attr in expected_attrs:
            self.assertTrue(hasattr(self.gui, attr), f"GUI 缺少属性: {attr}")

    # ------------------------------------------------------------------ #
    #  3. 格式化与基础工具方法测试                                          #
    # ------------------------------------------------------------------ #

    def test_format_and_utilities(self):
        """测试格式化与辅助方法。"""
        # Token 缩写格式化
        self.assertEqual(self.gui._fmt_tokens(0), "0")
        self.assertEqual(self.gui._fmt_tokens(999), "999")
        self.assertEqual(self.gui._fmt_tokens(1500), "1.500K")
        self.assertEqual(self.gui._fmt_tokens(2500000), "2.500M")
        self.assertEqual(self.gui._fmt_tokens("invalid"), "invalid")

        # 尺寸缩放
        self.assertEqual(self.gui._scale(100), 100)

        # 探针缓存 key
        k = self.gui._get_probe_cache_key("p1", "https://api.test", "sk-123")
        self.assertEqual(k, "p1::https://api.test::sk-123")
        self.assertIsNone(self.gui._get_probe_cache_key("", "", ""))

        # 日志记录与清理
        self.gui.log("测试信息", tag="success")
        self.gui.log("测试错误", tag="error")
        self.gui.log("测试警告", tag="warning")
        self.assertGreaterEqual(len(self.gui.log_list_view.controls), 3)
        self.gui._clear_log()
        self.assertEqual(len(self.gui.log_list_view.controls), 0)

    # ------------------------------------------------------------------ #
    #  4. 平台管理方法调用测试 (CRUD、保存、默认、重命名)                       #
    # ------------------------------------------------------------------ #

    def test_platform_methods(self):
        """测试平台面板全部方法的调用。"""
        # 1. 加载配置
        self.gui.load_config_from_db()
        self.assertIsInstance(self.gui.current_config, dict)

        # 2. 模拟添加新平台
        test_plat_name = f"UnitTestPlat_{os.getpid()}"
        test_plat_url = f"https://api.unittest-{os.getpid()}.com/v1"
        try:
            # 直接调用底层保证状态
            created = self.gui.ai_manager.admin_add_sys_platform(
                test_plat_name,
                test_plat_url,
                api_key="test_key_123",
                recharge_url="https://recharge.unittest.com",
            )
            p_id = created.id if hasattr(created, "id") else None
            self.gui.current_config[test_plat_name] = {
                "base_url": test_plat_url,
                "recharge_url": "https://recharge.unittest.com",
                "api_key": "test_key_123",
                "models": {},
                "_db_id": p_id,
            }
        except Exception:
            pass

        self.gui._refresh_platform_combo(selected_platform_name=test_plat_name)
        self.assertEqual(self.gui._resolve_platform_name(), test_plat_name)

        # 3. 平台选择触发与 Base URL 统一性验证
        self.gui.on_platform_selected()
        self.assertEqual(self.gui.platform_url_entry.label, "Base URL")
        self.assertIs(self.gui.base_url_entry, self.gui.platform_url_entry)
        self.assertEqual(self.gui.platform_url_entry.value, test_plat_url)

        # 4. 保存平台 URL
        new_url = "https://api.unittest-updated.com/v1"
        self.gui.platform_url_entry.value = new_url
        self.gui.save_platform_url()
        self.assertEqual(self.gui.current_config[test_plat_name]["base_url"], new_url)

        # 5. 保存充值地址
        new_recharge = "https://recharge.updated.com"
        self.gui.recharge_url_entry.value = new_recharge
        self.gui.save_recharge_url()
        self.assertEqual(self.gui.current_config[test_plat_name]["recharge_url"], new_recharge)

        # 6. 保存 API Key
        self.gui.api_key_entry.value = "new_secret_key"
        self.gui.save_api_key()
        self.assertEqual(self.gui.current_config[test_plat_name]["api_key"], "new_secret_key")

        # 6.1 一键保存平台全部配置 (save_platform_config)
        self.gui.platform_url_entry.value = "https://api.all-in-one.com/v1"
        self.gui.recharge_url_entry.value = "https://recharge.all-in-one.com"
        self.gui.api_key_entry.value = "sk-all-in-one-123"
        save_res = self.gui.save_platform_config()
        self.assertTrue(save_res)
        self.assertEqual(self.gui.current_config[test_plat_name]["base_url"], "https://api.all-in-one.com/v1")
        self.assertEqual(self.gui.current_config[test_plat_name]["recharge_url"], "https://recharge.all-in-one.com")
        self.assertEqual(self.gui.current_config[test_plat_name]["api_key"], "sk-all-in-one-123")

        # 7. 设为默认平台
        self.gui.set_as_default()

        # 8. 平台重命名
        renamed_plat = f"UnitTestPlatRenamed_{os.getpid()}"
        self.gui._execute_rename_platform(test_plat_name, renamed_plat)
        self.assertIn(renamed_plat, self.gui.current_config)

        # 9. 平台禁用/删除
        self.gui.delete_platform()

    # ------------------------------------------------------------------ #
    #  5. 模型管理方法测试 (格式化、增删改查、排序)                            #
    # ------------------------------------------------------------------ #

    def test_model_methods(self):
        """测试模型面板全部方法。"""
        # 1. 格式化与解析
        fmt = self.gui._format_model_list_item(
            "gpt-4o",
            {"model_name": "gpt-4o", "input_modalities": ["text", "image"], "output_modalities": ["text"]},
        )
        self.assertIn("gpt-4o", fmt)
        self.assertIn("→ gpt-4o", fmt)
        ext = self.gui._extract_display_name(fmt)
        self.assertEqual(ext, "gpt-4o")

        # 2. 模拟平台添加模型
        plat_name = next(iter(self.gui.current_config.keys()))
        db_id = self.gui.current_config[plat_name]["_db_id"]
        model_payload = {
            "display_name": "TestModel1",
            "model_name": "test-m1",
            "input_modalities": ["text"],
            "output_modalities": ["text"],
            "max_context_tokens": 128000,
            "max_output_tokens": 4096,
        }
        self.gui.ai_manager.admin_sync_platform_models(db_id, [model_payload])
        self.gui.load_config_from_db()
        self.gui._refresh_platform_combo(plat_name)
        self.gui.on_platform_selected()

        # 3. 验证模型在列表中
        self.gui.selected_model_display_name = "TestModel1"
        self.assertEqual(self.gui._get_selected_model_display_name(), "TestModel1")

        # 3.1 验证模型项上的智能操作图标：文本模型包含对话测试与速度测试
        self.gui._refresh_model_list_view()
        rendered_cards = self.gui.model_list_view.controls
        self.assertGreater(len(rendered_cards), 0)
        card_trailing = rendered_cards[0].content.trailing
        tooltips = [btn.tooltip for btn in card_trailing.controls if hasattr(btn, "tooltip")]
        self.assertIn("对话测试", tooltips)
        self.assertIn("速度测试", tooltips)
        self.assertNotIn("测试向量", tooltips)

        # 3.2 模拟添加 Embedding 模型，验证智能展示测试向量图标
        embed_payload = {
            "display_name": "TestEmbeddingModel",
            "model_name": "text-embedding-3-small",
            "input_modalities": ["text"],
            "output_modalities": ["embedding"],
        }
        self.gui.ai_manager.admin_sync_platform_models(db_id, [model_payload, embed_payload])
        self.gui.load_config_from_db()
        self.gui._refresh_platform_combo(plat_name)
        self.gui.on_platform_selected()
        self.gui._refresh_model_list_view()
        embed_card = [c for c in self.gui.model_list_view.controls if c.data == "TestEmbeddingModel"][0]
        embed_tooltips = [btn.tooltip for btn in embed_card.content.trailing.controls if hasattr(btn, "tooltip")]
        self.assertIn("测试向量", embed_tooltips)
        self.assertNotIn("对话测试", embed_tooltips)
        self.assertNotIn("速度测试", embed_tooltips)

        # 4. 排序保存调用
        self.gui.reorder_models()

        # 5. 删除模型
        self.gui.delete_model()

    # ------------------------------------------------------------------ #
    #  6. 模型探测与过滤测试                                               #
    # ------------------------------------------------------------------ #

    def test_probe_and_filter_methods(self):
        """测试探测数据渲染与关键字过滤。"""
        mock_models = [
            {"id": "claude-3-5-sonnet", "max_context_tokens": 200000, "max_output_tokens": 8192},
            {"id": "gpt-4o", "max_context_tokens": 128000, "max_output_tokens": 4096},
            {"id": "text-embedding-3-small"},
        ]
        self.gui.show_probe_results(mock_models)
        self.assertEqual(len(self.gui.probe_list_view.controls), 3)

        # 关键词过滤
        self.gui.filter_entry.value = "gpt"
        self.gui.on_filter_change()
        self.assertEqual(len(self.gui.probe_list_view.controls), 1)

        # 清除过滤
        self.gui.clear_filter()
        self.assertEqual(len(self.gui.probe_list_view.controls), 3)

        # 全选探测模型
        self.gui.select_all_probe_models()
        self.assertEqual(len(self.gui.selected_probe_model_ids), 3)

        # 清空选择
        self.gui.clear_probe_selection()
        self.assertEqual(len(self.gui.selected_probe_model_ids), 0)

        # 批量添加选中的模型
        self.gui.selected_probe_model_ids = {"gpt-4o", "claude-3-5-sonnet"}
        plat_name = self.gui._resolve_platform_name()
        self.gui._batch_add_probe_models(["gpt-4o", "claude-3-5-sonnet"])
        self.assertIn("gpt-4o", self.gui.current_config[plat_name]["models"])
        self.assertIn("claude-3-5-sonnet", self.gui.current_config[plat_name]["models"])

        # 探测错误展示（仅记录日志，不弹窗阻塞）
        initial_dialogs_count = len(self.mock_page.dialogs_opened)
        self.gui.show_probe_error("连接超时")
        self.assertEqual(len(self.mock_page.dialogs_opened), initial_dialogs_count)
        self.assertIn("连接超时", self.gui.log_list_view.controls[-1].value)

    # ------------------------------------------------------------------ #
    #  7. 用户调用总览与多列排序测试                                         #
    # ------------------------------------------------------------------ #

    def test_user_usage_overview_and_sorting(self):
        """测试全用户用量表格的刷新与排序。"""
        self.gui.user_usage_rows = [
            {"user_id": "user_a", "requests": 10, "total_tokens": 5000, "prompt_tokens": 2000, "completion_tokens": 3000, "sys_paid_requests": 5, "self_paid_requests": 5, "errors": 0},
            {"user_id": "user_b", "requests": 50, "total_tokens": 20000, "prompt_tokens": 8000, "completion_tokens": 12000, "sys_paid_requests": 30, "self_paid_requests": 20, "errors": 1},
            {"user_id": "user_c", "requests": 5, "total_tokens": 1000, "prompt_tokens": 500, "completion_tokens": 500, "sys_paid_requests": 1, "self_paid_requests": 4, "errors": 0},
        ]
        # 按 requests 排序 (降序)
        self.gui.sort_user_usage_overview("requests", toggle=False, descending=True)
        self.assertEqual(len(self.gui.user_usage_table.rows), 3)
        first_row_uid = self.gui.user_usage_table.rows[0].cells[0].content.value
        self.assertEqual(first_row_uid, "user_b")

        # 按 user_id 排序 (升序)
        self.gui.sort_user_usage_overview("user_id", toggle=False, descending=False)
        first_row_uid_asc = self.gui.user_usage_table.rows[0].cells[0].content.value
        self.assertEqual(first_row_uid_asc, "user_a")

    # ------------------------------------------------------------------ #
    #  8. 对话框弹窗调用与渲染测试 (全 Dialogs 测试)                           #
    # ------------------------------------------------------------------ #

    def test_dialogs_opening_and_rendering(self):
        """测试所有弹窗均可被正常构造打开并关闭。"""
        # 1. 打开添加模型弹窗
        self.gui.open_add_model_dialog(custom_model_id="deepseek-chat")
        self.assertGreater(len(self.mock_page.dialogs_opened), 0)
        self.mock_page.close(self.mock_page.dialogs_opened[-1])

        # 2. 打开系统用途管理弹窗
        self.gui.edit_system_model()
        self.assertGreater(len(self.mock_page.dialogs_opened), 0)
        self.mock_page.close(self.mock_page.dialogs_opened[-1])

        # 3. 打开用户配额管理弹窗
        self.gui.open_quota_manager_dialog(default_user_id="user_test_123")
        self.assertGreater(len(self.mock_page.dialogs_opened), 0)
        self.mock_page.close(self.mock_page.dialogs_opened[-1])

        # 4. 打开用户调用详情弹窗
        self.gui.open_user_usage_detail_dialog("user_test_123")
        self.assertGreater(len(self.mock_page.dialogs_opened), 0)
        self.mock_page.close(self.mock_page.dialogs_opened[-1])

        # 5. 打开主密钥设置弹窗
        self.gui.open_set_llm_key_dialog()
        self.assertGreater(len(self.mock_page.dialogs_opened), 0)
        self.mock_page.close(self.mock_page.dialogs_opened[-1])

    # ------------------------------------------------------------------ #
    #  9. 模型测试与测速结果展示测试                                        #
    # ------------------------------------------------------------------ #

    def test_probe_test_results(self):
        """测试对话与 Embedding 测试结果弹窗及日志。"""
        self.gui.show_test_result(True, "test-model", {"choices": [{"message": {"content": "Hello World"}}]})
        self.gui.show_test_result(False, "test-model", "API Error 401")
        self.gui.show_embedding_test_result(True, "test-embed", {"dims": 1536})
        self.gui.show_embedding_test_result(False, "test-embed", "Dimension mismatch")
    # ------------------------------------------------------------------ #
    #  10. YAML 导入导出与主密钥流程测试                                     #
    # ------------------------------------------------------------------ #

    def test_yaml_reload_and_export(self):
        """测试从 YAML 重置数据库与导出 YAML 逻辑。"""
        # 拦截确认对话框为 True 直接执行，并 mock 底层磁盘覆盖操作
        with patch.object(self.gui, "ask_yes_no", side_effect=lambda title, msg, on_yes, on_no=None: on_yes()):
            with patch.object(self.gui.ai_manager, "admin_save_to_yaml", return_value={"config_path": "mock.yaml", "key_path": "mock.yaml"}):
                with patch.object(self.gui.ai_manager, "admin_reload_from_yaml"):
                    self.gui.export_db_to_yaml()
                    self.gui.reload_from_yaml()

    def test_dialog_parsing_helpers(self):
        """测试对话框整数与浮点数校验逻辑。"""
        self.assertEqual(self.gui._parse_optional_non_negative_int("100", field_label="测试"), 100)
        self.assertIsNone(self.gui._parse_optional_non_negative_int("", field_label="测试"))
        with self.assertRaises(ValueError):
            self.gui._parse_optional_non_negative_int("-5", field_label="测试")
        with self.assertRaises(ValueError):
            self.gui._parse_optional_non_negative_int("abc", field_label="测试")

        self.assertEqual(self.gui._parse_optional_non_negative_float("1.25", field_label="测试"), 1.25)
        self.assertIsNone(self.gui._parse_optional_non_negative_float("   ", field_label="测试"))
        with self.assertRaises(ValueError):
            self.gui._parse_optional_non_negative_float("-1.5", field_label="测试")

    def test_key_manager_startup_flow(self):
        """测试主密钥启动自检分支逻辑。"""
        import agen_matchbox.gui.key_manager as km
        # 情况一：有环境变量
        with patch.object(km, "get_env_var", return_value="test_master_key_32bytes_1234567"):
            with patch.object(self.gui, "_apply_master_key_change", return_value=True):
                self.assertTrue(self.gui._ensure_master_key_ready_on_startup())

        # 情况二：无环境变量触发弹窗
        with patch.object(km, "get_env_var", return_value=None):
            res = self.gui._ensure_master_key_ready_on_startup()
            self.assertFalse(res)
            self.assertGreater(len(self.mock_page.dialogs_opened), 0)

    def test_main_entrypoint(self):
        """测试主入口 main 函数可正常启动调用 ft.app。"""
        from gui.main_window import main
        with patch("flet.app") as mock_app:
            main()
            self.assertTrue(mock_app.called)


if __name__ == "__main__":
    unittest.main()
