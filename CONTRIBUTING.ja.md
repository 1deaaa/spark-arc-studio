# SparkArc コントリビューションガイド（日本語）

## 1. 目的と位置づけ
本ガイドは、SparkArcメインプロジェクトにおける強制的かつ厳格な開発ガイドラインです。プロジェクトの規模が非常に大きく、複数のAgentが連携するシステムになっているため、すべてのコントリビューター（人間の開発者およびAIプログラミングアシスタントの両方）は、コードの記述や変更を開始する前に、**本ガイドを[AGENTS.md](file:///d:/Desktop/sparkarc/AGENTS.md)と併せて読まなければなりません**。
私たちは**「統一された窓口での集約、二重実装の排除」**という根本的な原則に従います。新しい機能を開発する前に、該当するロジックを受け入れることができるFacade、Pipeline、または大統一された共通基盤がシステム内にすでに存在するかどうかを優先して確認し、並行した処理ラインや車輪の再発明を行うことを厳格に禁止します。

## 2. 核心アーキテクチャと二重パイプラインプロトコル
SparkArcのストリーミング応答システムは、責任の境界が明確に分かれた2つのパイプラインで構成されています。2つのパイプライン間でイベントプロトコルやコンシューマ状態を混用することは厳格に禁止されています。

### 2.1 チャットメインライン (Chat NDJSON)
- **用途**：自由な対話、Agentの委譲（Handoff）やスケジューリングのやり取り、ツールの呼び出しプロセスの可視化。
- **フロントエンド集約**：[chatStore.ts](file:///d:/Desktop/sparkarc/client/src/components/stores/chatStore.ts)（`_consumeStream`がストリーム解析を統一して処理し、時系列Segmentsを管理）。
- **バックエンド集約**：[chat.py](file:///d:/Desktop/sparkarc/server/agents/routes/chat.py)ルート ＋ [communication.py](file:///d:/Desktop/sparkarc/server/agents/communication.py)（`SparkBaseAgent.chat_stream`）。
- **重要な事実**：
  - ストリームの伝送形式はNDJSONです（イベントには `task_snapshot`, `assistant_delta`, `reasoning_delta`, `tool_*`, `task_done` などが含まれます）。
  - チャット状態と履歴はイベントログを用いたインクリメンタルCheckpointモデルによって復旧されます。再接続時やページリロード時の復旧には、必ず `task_snapshot` とカーソルベースのリプレイを使用する必要があります。リプレイにProgress Queueを使用したり、破壊的な読み出しを行う `get_nowait` などのインターフェースを使用することは**厳格に禁止**されています。

### 2.2 業務タスクメインライン (Business SSE / セマンティックストリーム)
- **用途**：実行に時間がかかる業務タスク（例：文体クローン、Museインスピレーション生成、世界設定集生成、大綱の構成、プロット編集、脚本作成などの独立した業務ライン）。
- **フロントエンド集約**：[streamingRuntime.ts](file:///d:/Desktop/sparkarc/client/src/utils/streamingRuntime.ts)（`createStreamingTask`を使用してタスクのライフサイクルとグローバルな読み込みマスク（Loading Mask）を統一管理）。
- **バックエンド集約**：[streaming_utils.py](file:///d:/Desktop/sparkarc/server/agents/routes/streaming_utils.py)（`iterate_sync_iterable_in_thread`を使用して同期ジェネレータを非同期レスポンスにブリッジ）。
- **重要な事実**：
  - 標準的なセマンティックフレーム（Semantic Frame）プロトコルに従い、`onStart`, `onProgress`, `onDelta`, `onStats`, `onDone`, `onError`, `onCancelled` などのイベントフレームを統一して付与します。
  - フロントエンドはコンポーネント内に独自の「キャンセル＋統計」状態マシンを実装してはならず、すべての業務ストリームは `createStreamingTask` を通してホストされる必要があります。

## 3. 大統一ツールとインフラ共通基盤
プロジェクトの長期的な保守性を確保し、類似するコードブロックの重複を避けるため、SparkArcは以下の共通基盤を提供しています。類似する機能要件については、**必ずこれらのコンポーネントを再利用する**必要があり、ビジネスレイヤーやAgent内部で独自のローカルロジックを実装することは厳格に禁止されています：

1. **局所置換および差分修正 (Patch)**：
   - [common.py](file:///d:/Desktop/sparkarc/server/agents/tools/common.py) の `_apply_patch` 関数に集約されています。脚本の書き換え、アウトラインの更新、世界観設定の変更など、テキストを特定して置換するロジックは、必ずこの関数を呼び出す必要があります。独自の正規表現や `.replace()` の使用は禁止されています。
2. **インテリジェントテキスト分割 (Token Chunking)**：
   - [chunking.py](file:///d:/Desktop/sparkarc/server/core/file_ingest/chunking.py) の `TokenTextSplitter` に集約されています。トークン数に基づくテキストの分割処理は、必ずこのコンポーネントを再利用してください。
3. **セマンティックチャンカー (Semantic Chunker)**：
   - [SemanticChunker](file:///d:/Desktop/sparkarc/server/story/semantic_chunker/) ディレクトリに集約されています。プロジェクトファイル、ナレッジグラフ、ベクトルインデックスのセマンティックチャンキング（Semantic Chunking）は、すべてこのエンジンを再利用する必要があります。
4. **共通基盤の拡張原則**：
   - 将来的に複数の場所で再利用される可能性のある低レイヤーインフラ（ベクトル検索、キャッシュ制御、ドキュメント解析など）は、最初に共通ツールレイヤーまたはコアサービスレイヤーに下げる必要があり、各ビジネスラインやAgent内部で車輪の再発明を行うことは厳格に禁止されています。

## 4. バックエンド拡張と Agent 三モーダル規約
新しいAgentの追加やツールの拡張は、厳密な登録および規約プロセスに従う必要があります：

### 4.1 新規 Agent 登録チェックリスト
1. **ベースの再利用**：デフォルトで `SparkBaseAgent`（通信およびチャット）と `SparkAgentExecutor`（実行プロトコル）を継承する必要があります。
2. **4大登録ポイント**：
   - [registry.py](file:///d:/Desktop/sparkarc/server/agents/registry.py) ：Agentメタデータの登録。
   - [runtime.py](file:///d:/Desktop/sparkarc/server/agents/routes/runtime.py) ：ロック戦略やルートシグナル（Beacon）の設定。
   - [agent_tools.py](file:///d:/Desktop/sparkarc/server/agents/agent_tools.py) ＆ [tools/registry.py](file:///d:/Desktop/sparkarc/server/agents/tools/registry.py) ：ツールの登録とAgentへのバインド。
   - [director_graph.py](file:///d:/Desktop/sparkarc/server/agents/director_graph.py) ：Directorによる委譲対象とするかどうかの設定。

### 4.2 Agent 三モーダル Prompt 規約
役割の混線を防ぐため、すべての専門Agentは必ず3つの呼び出しモードを実装する必要があります：
- **専門作業モード (Specialized Work)**：`agent.execute()` からトリガー。YAML の `system` + `user` フィールドを使用。出力フォーマットは極めて厳格で、機械パーサによる解析またはファイル直接保存を前提とし、会話的な表現（挨拶など）は一切禁止されます。
- **対話モード (Chat Mode)**：チャットルートからトリガー。YAML の `chat_system` フィールドを使用。エンドユーザー向けであり、自然な対話やインスピレーションのための提案を許容します。
- **監督委譲モード (Pipeline Mode)**：Directorの委譲（Delegate）からトリガー。YAML の `pipeline_system` フィールドを使用。親（監督）Agent向け。

#### Prompt構成と唯一の真実のソース（Truth Source）の制約
1. **Tool Reference の自動注入**：
   - `_get_tool_prompt_references()` を使用して、フォーマット仕様を対応する保存ツールの YAML `system` フィールドに紐付けます。`pipeline_system` プロンプトは極めてシンプル（受け手の宣言、ツールの呼び出し、および要約報告のみ）に保ち、フォーマット仕様を `pipeline_system` 内に複製することは厳格に禁止されています。
2. **共有プロンプトベース (`base` フィールド)**：
   - 共通のペルソナ設定や基本方針は、YAML の最上位 `base` フィールドに定義し、各モード内で `{base.xxx}` プレースホルダーを使用して参照することで、二重保守を避ける必要があります。
3. **追加ツールルール (`tool_rules` フィールド)**：
   - Agent特有のツール呼び出し順序、出力の純度、アンチインジェクションの要件などは、YAML の `tool_rules` フィールドに記述し、基底クラスが自動的に追加します。Pythonコード内で直接ツールルールをハードコードすることは禁止されています。

## 5. フロントエンド拡張と国際化 (I18n)
1. **UIストリームイベントの同期**：
   - ツールの実行UIメタデータ（`ui_scope` / `ui_target` / `ui_refresh_events`）は、必ずバックエンドの [communication.py](file:///d:/Desktop/sparkarc/server/agents/communication.py) の `build_tool_stream_event` を通して注入され、フロントエンドは `chatStore` から直接読み込む必要があります。フロントエンドのコンポーネント内でUIの更新トリガーをハードコードすることは厳格に禁止されています。
2. **フロントエンドマッピング自己チェック checklist**：
   - Agentを変更または追加する際、以下のUIマッピングが更新されているかを確認してください：
     1. デフォルトアサイン先: [GlobalChatFloat.vue](file:///d:/Desktop/sparkarc/client/src/components/share/GlobalChatFloat.vue) (`viewAgentMap`)。
     2. バブル表示: [useAgentRegistry.ts](file:///d:/Desktop/sparkarc/client/src/composables/useAgentRegistry.ts) (`agentIconMap`/`agentColorMap`/`agentNameMap`)。
     3. フロー図（ブループリント）のレイアウト: [AgentFlowBlueprint.vue](file:///d:/Desktop/sparkarc/client/src/components/lorebook/AgentFlowBlueprint.vue)。
     4. シミュレーション用データ: `agentRuntimeStore.ts`。
     5. 設定パネル: `AiSettingsPanel.vue`。
3. **Vue I18n の強制的制約**：
   - ユーザーに見えるテキストの**ハードコードは禁止**されています。すべてのUI文言は、`zh-CN`, `en-US`, `ja-JP` のロケールファイルに同期して追加される必要があります。

## 6. データベースと移行（Migration）のレッドライン
1. **手動による Alembic 移行ファイルの編集禁止**：
   - データベースの構造変更を行う場合は、まず [models.py](file:///d:/Desktop/sparkarc/server/core/models.py) のモデル定義を変更し、自動生成スクリプトを実行してください：
     `python server/gen_migration.py`
     アプリケーション起動時に [auto_migrate.py](file:///d:/Desktop/sparkarc/server/core/auto_migrate.py) を通して移行処理が自動的に実行されます。

## 7. 典型的なアーキテクチャアンチパターン（禁止事項）
SparkArcのコーディングにおいて、以下の行為は**重大なアーキテクチャ違反**とみなされます：
1. **パイプラインの重複複製**：`streaming_utils.py` を使用せず、複数のルートでストリームのブリッジロジックをコピーすること。
2. **読み込みマスクの迂回**：`createStreamingTask` を使用せずに、コンポーネント内で手動で読み込みマスクを制御したり、直接Loadingイベントを送信すること。
3. **UIイベントの迂回**：`build_tool_stream_event` を使用せず、フロントエンドコンポーネントで直接ツール状態マシンや更新トリガーを処理すること。
4. **ストリームプロトコルの混用**：`NDJSON` を直接SSEフレームに変換したり、SSEイベントを直接 `chatStore` にプッシュすること。
5. **保存出口の迂回**：Agent内部でファイルの物理パスを直接指定して書き込み、統一された出力口である `write_result` を迂回すること。
6. **ゴースト登録**：`registry.py` やFacadeを更新せずにAgentやツールを作成すること。
7. **手動 DDL の実行**：スキーマの更新で移行スクリプトを生成せず、手動でDBを操作すること。
8. **Gitリポジトリの汚染**：テスト、デバッグ、または検証の過程で生成された一時ファイル（キャッシュ、FAISSベクトル、pickleシリアライズファイル、中間JSONなど）を、Gitで追跡されているテストディレクトリ（例：`server/test/`）に直接保存し、不要なファイルでバージョン管理システムを汚染すること。
9. **循環依存**：低レイヤーの共通サービスやツールクラスから、ルートレイヤー（`server/agents/routes/*`）のプライベート実装を逆参照すること。
10. **並行処理の危険性**：実行に時間がかかる物理タスクに対して並行書き込みロックを使用しないこと、またはストリーム再接続時にフロントエンドから `clientId` を送信しないこと。

## 8. 回帰テストと一時ファイル保存に関する制限
チャットストリーム、Agentのコラボレーション、またはツールの連携の修正を行う際は、関連するテストをすべてパスし、かつ一時ファイルに関する制限を遵守する必要があります：

### 8.1 一時ファイル sandbox ルール (極めて重要)
- テスト、デバッグ、または検証スクリプトによって生成されるすべての一時キャッシュ、インデックス、グラフ、シリアライズファイルは、**必ずプロジェクトルートの `/.tmp/` ディレクトリ配下に保存されなければなりません**。
- Gitリポジトリの清潔さを保つため、一時的なテスト出力を `server/test/` やその配下に直接保存することは厳格に禁止されています。

### 8.2 推奨される回帰テストコマンド
- **バックエンドテスト**：
  ```bash
  cd server
  pytest test/test_chat_stream_events.py test/test_chat_history_segments.py test/test_tool_event_ui_metadata.py test/test_director_graph.py test/test_director_handoff_protocol.py test/test_director_skip_confirmation.py test/test_stream_semantics_runtime.py
  ```
- **フロントエンドテスト**：
  ```bash
  cd client
  npm run test -- src/components/stores/__tests__/chatStore.spec.ts src/utils/__tests__/streamingRuntime.spec.ts
  ```

## 9. AI Agentの権限および安全対策
1. ユーザーから**簡体字中国語**による明確な指示がない限り、AIアシスタントは読み取り専用のGitコマンドのみ使用が許可されます。`git commit` や `git push` などの書き込み操作は厳格に禁止されています。
2. 自動承認（Auto-approval）ポリシーが有効になっている場合でも、AIアシスタントは安全対策を最優先し、自動承認をユーザーの意図と見なしてはならず、GitHub CLIなどでリモートリポジトリを操作することは厳格に禁止されています。
