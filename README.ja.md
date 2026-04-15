# SparkArc: クロスプラットフォーム Agent 物語制作スタジオ

[简体中文](README.md) | [English](README.en.md) | [日本語](README.ja.md)

SparkArc は、複数 Agent の協調で創作を進める本格的な制作スタジオです。
小さな着想を、公開可能な物語世界と実行可能なコンテンツ資産へ拡張します。

対応領域:

- 小説執筆
- 脚本制作
- Web 演出公開
- ゲームエンジン連携可能な物語データ化

SparkArc は次の全工程を一気通貫でつなぎます。

`着想 -> 世界観 -> テンポ -> 構成 -> 執筆 -> 品質検証 -> 公開 -> 共有 -> 演出`

---

## SparkArc が解く課題

一般的な AI 執筆ツールは、次のどちらかに偏りがちです。

- ブラックボックス生成で構造制御が弱い
- プロンプト設計をユーザー側に押し戻す

SparkArc はプロダクト設計を次のように置き換えます。

1. ユーザーは Director Agent と自然言語で会話する
2. Director が専門 Agent とツールへタスクを分配する
3. 構造化エディタに生成結果を自動反映する
4. どの段階でも人間が介入し、方向修正できる

IDE 級の制御力と、チャット級の操作感を両立するのが SparkArc の価値です。

---

## プロダクトの中核価値

### 1. 本番制作向け Studio UX

- 単一の会話入口でマルチ Agent を指揮
- 世界観・概要・構成・脚本の層別編集
- 生成過程を追跡できるホワイトボックス型体験
- 必要箇所のみ専門 Agent で局所的に改稿

### 2. 人間主導の創作コントロール

SparkArc は「創造の主語は人間」を前提にします。

- `Manual`：AI は整理・検証・提案のみ
- `Hybrid`（推奨）：核となる着想は人間、展開補完は AI
- `Auto`：粗いアイデアから複数方向を自動探索

### 3. 品質と整合性の閉ループ

- `Style Agent`：文体再現で AI らしさを低減
- `Critic Agent`：証拠ベースの編集レビュー（S/A/B/C/D）
- `GraphRAG`：長編での事実整合と設定衝突の抑制

### 4. モバイルとデスクトップの連続性

- 移動中でも触れる軽量編集フロー
- 深い編集と管理はデスクトップ Studio で実施
- MCP 経由で外部ツールから着想を取り込み

### 5. 公開・演出まで見据えた成果物

- Web 演出リンクとして即共有
- ゲームエンジン接続へ自然に拡張
- テキストではなく実行可能な物語資産として管理

### 6. 拡張しやすい Agent 運用モデル

SparkArc は協調権限を以下で分離します。

- `Beacon`：可視性・受信可否
- `Horn`：能動発話権
- `Baton`：現在タスクの推進責任

大規模化してもエージェント間の混線を抑え、保守可能性を維持できます。

---

## Agent パイプライン（制作視点）

| 段階 | 実務対応 | Agent / Tool | 役割 |
| :-- | :-- | :-- | :-- |
| 0. 調停 | ディレクション | `Director` | 意図解釈、文脈維持、タスク分配 |
| 1. 企画 | ハイコンセプト | `Muse` | 着想の種を拡張し方向性を作る |
| 2. 設定 | ストーリーバイブル | `Lorebook` | 世界観ルール、設定、人物基盤を整備 |
| 3. 構造 | ビート設計 | `Showrunner` | ビートと章・シーン骨格を生成 |
| 4. 執筆 | 脚本草稿 | `Scriptwriter` + `GraphRAG` | 事実制約を守りながらシーン本文を生成 |
| 5. 品質 | Script Doctor | `Critic` + `Style` + `GraphRAG` | AI 臭・論理破綻・整合性ズレを検出 |
| 6. 出力 | 実行資産 | Web Player / Unity SDK | 物語を公開可能・実行可能資産へ変換 |

---

## アーキテクチャ要点

### バックエンド収束点

- 通信基盤: `server/agents/communication.py`
- 実行プロトコル: `server/agents/agent_utils.py`
- ツール門面: `server/agents/agent_tools.py`
- 多 Agent 調停: `server/agents/director_graph.py`
- ストリーム橋渡し: `server/agents/routes/streaming_utils.py`
- セマンティックストリーム: `server/agents/routes/stream_semantics.py`

### フロントエンド収束点

- ストリーミング基盤: `client/src/utils/streamingRuntime.ts`
- チャット収束: `client/src/components/stores/chatStore.ts`
- 全体ローディング: `client/src/components/share/GlobalLoading.vue`
- イベントバス: `client/src/eventBus.ts`

### 2 つのストリーム規約

- チャット系: NDJSON（`assistant_delta`, `tool_*`, `reasoning_delta`）
- 業務系: セマンティック SSE（`onStart`, `onDelta`, `onDone` など）

この 2 つは設計上分離されており、混在させません。

---

## クイックスタート

### A. Docker（推奨）

```bash
git clone https://github.com/your-repo/sparkarc.git
cd sparkarc
docker compose up -d --build
```

起動先: http://localhost:7788

`git pull` 後は再起動ではなく再ビルドしてください。

```bash
git pull --ff-only
docker compose up -d --build --force-recreate
docker compose logs --tail=120 sparkarc
```

理由: 新コードを確実に反映し、古いマウントファイルによる上書き事故を防ぐためです。

### B. ローカル開発

1. Python 環境を作成し `server` 依存を導入
2. `client` でフロントエンドをビルド
3. `server` を起動
4. http://localhost:6688 へアクセス

---

## i18n と言語ポリシー

- UI 対応言語: `zh-CN`, `en-US`, `ja-JP`
- 設定画面で即時切替可能
- Agent system prompt の言語ルール:

1. 既定では現在ロケールを優先
2. ユーザーが他言語を自発使用、または明示要求した場合のみ切替

フロントエンド実装では、ユーザー表示文言のハードコードを避け、Vue I18n を使用してください。

---

## リポジトリガイド

- メイン貢献ガイド:
  - `CONTRIBUTING.zh-CN.md`
  - `CONTRIBUTING.en.md`
  - `CONTRIBUTING.ja.md`
- Agent 制約と設計規約: `AGENTS.md`
- Agent 言語方針: `agent.md`

---

## Matchbox Gateway

SparkArc は `server/llm/agen_matchbox` に Matchbox を同梱します。

Matchbox は Agent ワークロード向けに、モデルルーティング・鍵管理・配額制御・使用量可視化を統合提供します。

詳細:

- `server/llm/agen_matchbox/README.md`
- `server/llm/agen_matchbox/README.en.md`
- `server/llm/agen_matchbox/README.ja.md`

---

## プロダクトロードマップ（方向性）

- 立ち絵スタイル統一パイプライン
- 背景画像の軽量生成/編集ワークフロー
- 役割特化型 Scriptwriter サブ Agent パック
- スキーマ駆動のカスタム UI コンポーネント生成

SparkArc は、物語制作を「高品質で、再現可能で、創作者主導」にすることを目標に進化します。

---

## ブランド・商標に関する声明

SparkArc は本プロジェクトの公式名称および識別标识です。

本プロジェクトのコードは AGPL-3.0 で公開されていますが、**「SparkArc」の名称、ロゴ、ブランド視覚デザインおよび関連する識別标识はコードのライセンス対象に含まれません**。

本プロジェクトに基づくデプロイ、改変版または配布版は、オリジナルプロジェクトとの公式・授権・代理・提携関係を暗示してはなりません。
