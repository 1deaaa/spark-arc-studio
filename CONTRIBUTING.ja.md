# SparkArc コントリビューションガイド（日本語）

## 1. 目的
本ガイドはメインプロジェクトへの貢献に適用されます。AGENTS.md と合わせて読み、まず統一パイプライン原則を優先してください。

## 2. アーキテクチャの必須ルール
- チャット系: フロントは chatStore、バックエンドは server/agents/routes/chat.py + SparkBaseAgent.chat_stream を利用。
- 業務ストリーム: フロントは createStreamingTask、バックエンドは stream_semantics + iterate_sync_iterable_in_thread を利用。
- ツール拡張: server/agents/agent_tools.py を統一ファサードとして経由し、実装は server/agents/tools/* に分割し、登録は server/agents/tools/registry.py に集約すること。ルートや単独 Agent で独自プロトコル・並行レジストリ・ローカル専用ツール経路を作らないこと。
- DB 変更: モデル変更 + server/gen_migration.py による生成のみ。手動 migration 禁止。

## 3. フロントエンド規約（必須）
- ユーザー表示テキストのハードコード禁止。
- 表示文言はすべて Vue I18n を使用。
- 新機能は必ず zh-CN / en-US / ja-JP を同時追加。
- チャット/ストリーム改修時は既存収束点を再利用:
  - client/src/components/stores/chatStore.ts
  - client/src/utils/streamingRuntime.ts

## 4. Agent と Prompt 規約
- Prompt はまず統一入口で管理: server/agents/agent_utils.py（load_prompt）と SparkBaseAgent の system prompt 組み立て。
- 言語方針: Agent は既定で設定言語を最優先し、ユーザーが他言語を自発的に使用するか、明示的に切り替えを要求した場合のみ切り替える。
- 同じ制約文を Agent ごとに重複実装しない。中央注入を優先。

### 4.1 Agent 三モーダル Prompt 規約（必須、詳細は AGENTS.md §4.5）
各専門 Agent の `server/agents/prompts/<agent>.yaml` は、三つの呼び出しモードに対応する三つのトップレベルフィールドを同時に定義する必要があります：

| モード | 呼び出し経路 | YAML フィールド | 受け手 |
| :--- | :--- | :--- | :--- |
| 専門作業（Specialized Work） | 業務ルート / パネルボタン → `agent.execute()` / 名前付きメソッド | `system` + `user` | 機械パーサ |
| 対話モード（Chat Mode） | `chat_stream(skip_tool_confirmation=False)` | `chat_system` | 一般ユーザー |
| 監督委譲モード（Pipeline Mode） | 監督 `delegate_task` → `sub_agent_node` → `chat_stream(skip_tool_confirmation=True)` | `pipeline_system` | 監督（上流 Agent） |

`pipeline_system` の記述必須ルール：
- **受け手宣言**：冒頭で「あなたの受け手は監督であってユーザーではない」と宣言。
- **三件セット本体**：本文は「ツール呼出 + 一発完了 + 監督への報告」の三件セットのみ。
- **フォーマット規格は tool reference で、複写しない**：構造化出力規格は `_get_tool_prompt_references()` で該当ツールの yaml `system` フィールドに紐付けるべきであり、`pipeline_system` 内に複写しない——二重保守になりドリフトしやすい。詳細は AGENTS.md §4.5.1。
- **無効参照厳禁**：「通常生成と同じ / 形式は system と同一」等の参照表現は禁止。コード上、二つの system は**相互排他**であり、LLM は他方を見られません。
- **ブレスト系の修飾語厳禁**：「発散思考 / 慣例を打破 / 情熱的に」など、構造化出力と衝突する語気修飾を書かない。
- **例外 — 落とし先ツールのない Agent**（例: critic、出力が直接監督に渡る）：`pipeline_system` に出力規格の要点（フィールド一覧、評価基準など）を直接埋め込むこと。`system` を参照する書き方は禁止。

`chat_system` は対話モードの人格と語調のみを規定し、出力フォーマットを強制しません。`system` は最も厳格な構造化規範を担います。以上いずれかに違反するとモード混線が発生します（例: 監督委譲された Muse がインスピレーションではなく世界観を構築——これは tool reference 未登録により pipeline モードで 7 条フォーマット規格が欠落した実歴バグです）。

## 5. テストと検証
チャット、多 Agent、ツール可視化、語義ストリームに関わる変更では最低限以下を回帰:
- server/test/test_chat_stream_events.py
- server/test/test_chat_history_segments.py
- server/test/test_tool_event_ui_metadata.py
- server/test/test_director_graph.py
- server/test/test_stream_semantics_runtime.py
- client/src/components/stores/__tests__/chatStore.spec.ts
- client/src/utils/__tests__/streamingRuntime.spec.ts

## 6. PR 前チェック
- 既存の統一パイプラインに接続できているか。
- 変更範囲にハードコード文言が残っていないか。
- zh-CN / en-US / ja-JP の翻訳が揃っているか。
- 必要なテストと手動回帰を実施したか。

## 7. 貢献の著作権とライセンス
- 書面で別途合意がない限り、貢献者は自身の独自性ある貢献について法的に保有する権利を保持します。
- Pull Request、パッチ、ドキュメント、デザイン素材、スクリプト、その他の貢献を本リポジトリへ提出することで、貢献者は当該内容を提出する権利を有することを確認し、本リポジトリの現在適用されるオープンソースライセンスに基づいて公開、マージ、再配布されることに同意したものとみなされます。
- メインプロジェクトは現在 AGPL-3.0-only を既定とします。ファイルまたはサブディレクトリに別の明示的なライセンス表示がある場合、その表示が当該ファイルまたはサブディレクトリに適用されます。詳細は LEGAL/LicensePolicy.zh-CN.md を参照してください。
- 本プロジェクトは現在 CLA の署名を要求しません。上流への貢献は歓迎しますが、AGPL-3.0 は第三者に上流リポジトリへの Pull Request 提出を義務付けるものではありません。
- 許可のない第三者コード、素材、文書、その他制限付きの内容を提出しないでください。
- 雇用、委託、共同開発、第三者ライセンス素材が関係する場合は、提出前に権利関係を確認してください。
