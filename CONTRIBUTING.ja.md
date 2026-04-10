# SparkArc コントリビューションガイド（日本語）

## 1. 目的
本ガイドはメインプロジェクトへの貢献に適用されます。AGENTS.md と合わせて読み、まず統一パイプライン原則を優先してください。

## 2. アーキテクチャの必須ルール
- チャット系: フロントは chatStore、バックエンドは server/agents/routes/chat.py + SparkBaseAgent.chat_stream を利用。
- 業務ストリーム: フロントは createStreamingTask、バックエンドは stream_semantics + iterate_sync_iterable_in_thread を利用。
- ツール拡張: server/agents/agent_tools.py に統一登録。ルートや単独 Agent で独自プロトコルを作らないこと。
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
