# computer-use-test

Azure OpenAI の computer-use 機能を使用して Windows 環境を自動操作するためのツールです。

## 特徴

- **モジュール化された構造**: 保守性と拡張性に優れた設計
- **詳細な日本語コメント**: すべての関数に日本語の docstring を完備
- **包括的なドキュメント**: アーキテクチャ、API、使用方法を網羅
- **自動リトライ**: API エラー、レート制限、接続エラーに自動対応
- **セッション管理**: 実行ログと AI による要約を自動記録

## プロジェクト構成

```
computer-use-python-demo/
├── computer-use-test.py      # メインエントリーポイント
├── src/                       # ソースコードディレクトリ
│   ├── config.py             # 環境設定と定数管理
│   ├── utils.py              # 汎用ユーティリティ関数
│   ├── client.py             # Azure OpenAI クライアント
│   ├── image_processing.py   # 画像処理機能
│   ├── actions.py            # コンピューター操作実行
│   ├── session.py            # セッション管理とログ記録
│   ├── confirmation.py       # ユーザー確認の自動化
│   ├── debug.py              # デバッグ情報生成
│   ├── indicator.py          # ステータスインジケーター
│   └── main.py               # メイン実行ロジック
├── docs/                      # ドキュメントディレクトリ
│   ├── architecture.md       # アーキテクチャドキュメント
│   ├── api_reference.md      # API リファレンス
│   └── usage.md              # 使用方法ドキュメント
└── requirements.txt          # Python依存関係
```

## クイックスタート

### 1. 依存関係のインストール

```bash
# 仮想環境の作成（推奨）
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows PowerShell

# 依存関係のインストール
pip install -r requirements.txt
```

### 2. 環境設定

`.env.example` をコピーして `.env` を作成し、必要な値を設定します：

```bash
cp .env.example .env
```

`.env` ファイルの設定例：

```env
# Azure OpenAI エンドポイント
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com

# Azure OpenAI モデルのデプロイ名
AZURE_OPENAI_MODEL_COMPUTER_USE=gpt-4o-computer-use
AZURE_OPENAI_MODEL_SUMMARY=gpt-4o-mini
AZURE_OPENAI_MODEL_CONFIRM=gpt-4o-mini

# 実行するタスク（または --message で指定）
TARGET_MESSAGE=メモ帳を開いて「Hello, World!」と入力してください
```

### 3. Azure 認証の設定

```bash
az login
```

### 4. 実行

```bash
# 環境変数から読み込み
python computer-use-test.py

# コマンドライン引数で指定
python computer-use-test.py --message "メモ帳を開いてください"
```

## ドキュメント

詳細な情報は `docs/` ディレクトリを参照してください：

- **[architecture.md](docs/architecture.md)**: システムアーキテクチャ、モジュール構成、データフロー
- **[api_reference.md](docs/api_reference.md)**: 全関数の完全な API リファレンス
- **[usage.md](docs/usage.md)**: 詳細なセットアップ手順、実行例、トラブルシューティング

## 主要機能

### 自動操作

- マウス操作（クリック、ダブルクリック、移動、ドラッグ）
- キーボード操作（テキスト入力、キープレス）
- スクロール操作
- スクリーンショット撮影

### 画像処理

- フルスクリーンスクリーンショット撮影
- クリックポイントのアノテーション
- テキストアノテーション
- デバッグ情報の画像オーバーレイ

### セッション管理

- タイムスタンプ付きイベントログ
- AI モデルによるレスポンスの自動要約
- デバッグ用詳細ログ

### 確認処理

- ヒューリスティック判定による確認要求の検出
- AI モデルによる確認要求の判定
- リスク用語の自動検出と手動確認要求
- 自動確認メッセージの送信

### ステータス表示（任意）

実行中に、画面右上へ小さなインジケーター（常時最前面・枠なし）を表示できます。

- 有効化: `.env` に `ENABLE_STATUS_INDICATOR=true`
- 表示内容: `Step/Max`、フェーズ（API 待ち/操作中/確認中）、直近アクション、経過時間

調整（任意）:

- クリック透過（誤クリック防止）: `STATUS_INDICATOR_CLICK_THROUGH=true`（Windows）
- 位置: `STATUS_INDICATOR_POSITION=top-right|top-left|bottom-right|bottom-left`
- オフセット: `STATUS_INDICATOR_OFFSET_X` / `STATUS_INDICATOR_OFFSET_Y`
- 見た目: `STATUS_INDICATOR_OPACITY`、`STATUS_INDICATOR_WIDTH/HEIGHT`、`STATUS_INDICATOR_FONT_FAMILY/SIZE`

## セキュリティ

- `.env` ファイルは **絶対にコミットしない**でください（`.gitignore` で除外済み）
- `screenshots/` と `*-sessionsummary.txt` には機密情報が含まれる可能性があります
- 入力テキストのログ記録は `LOG_TYPED_TEXT_IN_SESSION_SUMMARY=false` で無効化できます

## トラブルシューティング

詳細は [docs/usage.md](docs/usage.md) のトラブルシューティングセクションを参照してください。

### よくある問題

- **環境変数が読み込まれない**: `.env` ファイルの場所と `python-dotenv` のインストールを確認
- **Azure 認証エラー**: `az login` を実行するか、環境変数で認証情報を設定
- **クリック座標がずれる**: `src/config.py` の `DISPLAY_WIDTH` と `DISPLAY_HEIGHT` を確認

## 開発

### コードの変更

各モジュールは独立して変更可能です：

- 新しいアクションを追加: `src/actions.py` に `perform_*()` 関数を追加
- 新しい画像処理: `src/image_processing.py` に関数を追加
- 設定の追加: `src/config.py` に定数を追加

### テスト

```bash
# 構文チェック
python -m py_compile src/*.py computer-use-test.py
```

## ライセンス

このプロジェクトは MIT ライセンスの下で提供されています。詳細は [LICENSE](LICENSE) ファイルを参照してください。

## 注意事項

- このツールは Windows 専用です
- PyAutoGUI の FAILSAFE 機能により、マウスを画面の隅に移動すると緊急停止します
- 最大ステップ数はデフォルトで 30 です（`src/config.py` で変更可能）
