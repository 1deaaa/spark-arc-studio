# Matchbox Agent Gateway: Agent システム向け内蔵 LLM ゲートウェイ

[简体中文](README.md) | [English](README.en.md) | [日本語](README.ja.md)

Matchbox は Agent ネイティブなアプリケーション向けに設計された、内蔵型のフル機能 LLM ゲートウェイです。
モデルルーティング、鍵分離、配額管理、使用量追跡を、Agent が動く同一ランタイム内で完結させます。

---

## プロダクトとしての位置づけ

Matchbox は次の両立を狙うチーム向けです。

- ローカル検証・試作の高速性
- 本番運用に必要なマルチユーザー統制

外部ゲートウェイを別系統で運用するのではなく、アプリ本体のライフサイクルに AI ゲートウェイを統合することで、実装と運用の断絶を減らします。

---

## 内蔵型を選ぶ理由

### 1. Agent 編成と自然に接続

- LangChain / LangGraph パターンに素直に適合
- ツール呼び出し情報や文脈をアプリ層で保持しやすい
- ストリーミング時の多段転送による遅延・互換崩れを抑制

### 2. 鍵管理を単一戦略で運用

- システム托管キーを管理可能
- ユーザー BYOK を併用可能
- `LLM_AUTO_KEY` によるフォールバック戦略を選択可能

### 3. 課金実態に一致する配額設計

呼び出しは資金源で分岐します。

- `sys_paid`: 托管キー利用
- `self_paid`: ユーザーキー利用

各口径で「時間窓上限」「総量上限」を独立設定できます。

### 4. 運用コストの削減

- 追加 Redis / OneAPI 構成が不要
- SQLite + SQLAlchemy で永続化
- GUI 管理ツールを同梱

---

## 主な機能

- マルチユーザーのプラットフォーム/モデル管理
- 用途スロット: `main` / `fast` / `reason` + カスタム用途
- API Key の暗号化保存
- OpenAI 互換プロバイダのモデル動的探測
- reasoning ストリーム互換の正規化
- 使用量統計と口座別可視化
- GUI 管理（`matchbox_cfg_gui.py`）

---

## ランタイム運用モデル

Matchbox は実運用で 2 つの経路を使い分けます。

### A. 管理経路（推奨）

通常トラフィックはこの経路を使います。

```python
from llm.agen_matchbox import initialize_matchbox, matchbox

initialize_matchbox(ensure_defaults=True)
client = matchbox().get_user_llm(user_id='user_123', usage_key='main', agent_name='agent_director')
result = client.invoke('サイバーパンク世界観の種を生成して')
```

この経路で自動処理されるもの:

- ユーザー用途選択の解決
- 鍵優先順位の解決
- プロバイダ呼び出し前の配額検証
- 使用量の記録

### B. 軽量経路（バイパス）

一時スクリプトや補助ツールで DB 連携が不要な場合に使います。

- `create_quick_llm(...)`
- `create_quick_embedding(...)`

---

## 重要概念

### システムユーザー

`SYSTEM_USER_ID = "-1"` はバックエンド/システム呼び出し用の特別ユーザーです。

### 全体モード切替

- `USE_SYS_LLM_CONFIG = True`: システム定義プラットフォーム/モデルをユーザーで共有
- `USE_SYS_LLM_CONFIG = False`: ユーザーが私有プラットフォーム/モデルを管理可能

### フォールバック制御

- `LLM_AUTO_KEY = True`: ユーザーキー未設定時にシステムキーへ降格可能
- `LLM_AUTO_KEY = False`: ユーザーキー必須時は未設定で即失敗

### 配額口径

配額は実際のキー経路に対して適用されます。

- `sys_paid` 上限は托管キー呼び出しにのみ適用
- `self_paid` 上限はユーザーキー呼び出しにのみ適用

これにより、托管予算が尽きてもユーザー自費経路を不必要に止めません。

---

## データソース方針

Matchbox は二重データソースを明確に使い分けます。

- 実行時正本: `llm_config.db`
- 初期化/増分同期/出力: `matchbox_cfg.yaml`

重要事項:

1. YAML は初期構造の投入に使う
2. 実行時は DB が権威
3. GUI 変更は DB に直接反映
4. 新環境で `ENC:` 鍵が復号できなくても、構造同期は継続可能（鍵はローカル再設定）

---

## 初回セットアップ（推奨）

1. GUI を起動:

```bash
python matchbox_cfg_gui.py
```

2. `LLM_KEY`（暗号化マスターキー）を設定
3. 対象プラットフォームへ実キーを登録
4. モデル探測と接続テストを実施
5. `main` / `fast` / `reason` の用途スロットを確認

---

## セキュリティ指針

- 平文 API Key をコミットしない
- 環境変数 + 暗号化 DB 保存を推奨
- `.env` は私有管理
- 環境移行時は托管キーのローテーションを推奨

---

## 運用メモ

- アプリ起動時に Matchbox を初期化
- 必要に応じて終了時に `reset_matchbo()` を呼ぶ
- `AGENT_MATCHBOX_HOME` で DB/.env/YAML/state の実行位置を統一
- 更新後はコンテナ再ビルドで古いマウント状態を排除

---

## 関連ドキュメント

- 貢献ガイド:
  - `CONTRIBUTING.zh-CN.md`
  - `CONTRIBUTING.en.md`
  - `CONTRIBUTING.ja.md`
- メインプロジェクト:
  - `../../../../README.md`
  - `../../../../README.en.md`
  - `../../../../README.ja.md`

Matchbox の目的は、Agent 中心プロダクトに対して「信頼できる・統制可能な LLM アクセス基盤」を、余計な運用複雑性なしで提供することです。

---

## ライセンス

マッチ箱 Agent ゲートウェイは、本ディレクトリ内の `LICENSE` に従って Apache License 2.0 で個別にライセンスされており、独立したコンポーネントとして再利用できます。

このライセンスは `server/llm/agen_matchbox` 内で明示的に対象となるコンポーネントのみに適用され、SparkArc メインプロジェクトのその他の部分に適用される AGPL-3.0-only ライセンスを変更するものではありません。
