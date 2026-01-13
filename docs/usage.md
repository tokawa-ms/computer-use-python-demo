# 使用方法ドキュメント

## セットアップ

### 1. 必要なソフトウェア

- Python 3.10 以上
- Windows OS（PyAutoGUI の Windows 固有機能を使用）
- Azure OpenAI サービスのアクセス権

### 2. 依存関係のインストール

```bash
# 仮想環境の作成（推奨）
python -m venv .venv

# 仮想環境の有効化
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Windows (CMD)
.venv\Scripts\activate.bat

# 依存関係のインストール
pip install -r requirements.txt
```

### 3. 環境設定

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

# オプション設定
LOG_TYPED_TEXT_IN_SESSION_SUMMARY=true
```

### 4. Azure 認証の設定

このツールは `DefaultAzureCredential` を使用します。以下のいずれかの方法で認証を設定してください：

**方法1: Azure CLI**
```bash
az login
```

**方法2: 環境変数**
```env
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_TENANT_ID=your-tenant-id
```

**方法3: マネージドID**
- Azure VM または Azure App Service で実行する場合、自動的に認証されます

## 基本的な使用方法

### コマンドライン引数で実行

```bash
python computer-use-test.py --message "ブラウザを開いてGoogleで検索してください"
```

### 環境変数で実行

`.env` ファイルに `TARGET_MESSAGE` を設定してから：

```bash
python computer-use-test.py
```

### モジュールとして実行

```bash
python -m src.main --message "メモ帳を開いてください"
```

## 実行例

### 例1: シンプルなタスク

```bash
python computer-use-test.py --message "電卓アプリを開いて 123 + 456 を計算してください"
```

### 例2: ファイル操作

```bash
python computer-use-test.py --message "メモ帳を開いて「今日の日付」と入力し、デスクトップに test.txt として保存してください"
```

### 例3: ブラウザ操作

```bash
python computer-use-test.py --message "Microsoft Edgeを開いて https://www.microsoft.com にアクセスしてください"
```

## 設定のカスタマイズ

### ディスプレイ設定

`src/config.py` でディスプレイサイズを変更できます：

```python
DISPLAY_WIDTH = 2560   # モデルが認識するディスプレイ幅
DISPLAY_HEIGHT = 1600  # モデルが認識するディスプレイ高さ
```

**注意**: これらの値は実際のスクリーンサイズと異なっても構いません。座標は自動的にスケーリングされます。

### 自動確認の設定

```python
# src/config.py
AUTO_CONFIRM = True  # 確認要求に自動で「はい」と返答
CONFIRM_MESSAGE = "はい、進めてください。"  # 自動確認時のメッセージ
```

### デバッグ設定

```python
# src/config.py
SAVE_MODEL_RESPONSE_DEBUG_IMAGE = True  # デバッグ画像を保存
EVIDENCE_BEFORE_AFTER_FOR_INPUT = True  # 入力前後のスクリーンショットを保存
```

### セッションサマリー設定

```python
# src/config.py
ENABLE_SESSION_SUMMARY = True  # セッションサマリーを有効化
LOG_TYPED_TEXT_IN_SESSION_SUMMARY = True  # 入力テキストをログに記録
```

**警告**: `LOG_TYPED_TEXT_IN_SESSION_SUMMARY = True` の場合、パスワードなどの機密情報がログファイルに記録される可能性があります。

### ステータスインジケーター設定

ステータスインジケーターを有効にすると、実行中に画面上（デフォルトは右上）に小さな常時最前面ウィンドウが表示され、現在のステップやフェーズ、経過時間などが確認できます。

```env
# .env ファイル
ENABLE_STATUS_INDICATOR=true

# 位置の調整（オプション）
STATUS_INDICATOR_POSITION=top-right  # top-left, bottom-right, bottom-left も可能
STATUS_INDICATOR_OFFSET_X=12
STATUS_INDICATOR_OFFSET_Y=12

# 外観の調整（オプション）
STATUS_INDICATOR_OPACITY=0.78
STATUS_INDICATOR_WIDTH=280
STATUS_INDICATOR_HEIGHT=92
STATUS_INDICATOR_FONT_FAMILY=Segoe UI
STATUS_INDICATOR_FONT_SIZE=9

# クリック透過（Windows のみ、オプション）
STATUS_INDICATOR_CLICK_THROUGH=true
```

**クリック透過について**: Windows では `STATUS_INDICATOR_CLICK_THROUGH=true` に設定すると、インジケーターウィンドウをクリックしてもその下のウィンドウに操作が伝わります（誤クリック防止）。

## 出力ファイル

### スクリーンショット

実行中に撮影されたスクリーンショットは `screenshots/` ディレクトリに保存されます：

- `YYYYmmdd_HHMMSS_mmm.png`: 元のスクリーンショット
- `YYYYmmdd_HHMMSS_mmmR.png`: アノテーション付き（クリックポイント）
- `YYYYmmdd_HHMMSS_mmmN.png`: アノテーション付き（テキスト）
- `YYYYmmdd_HHMMSS_mmm_Debug.png`: デバッグ情報付き

### セッションサマリー

セッションの実行ログは以下の形式で保存されます：

- `YYYYmmdd_HHMMSS-sessionsummary.txt`: セッション全体のサマリー

**ファイル例**:
```
session_start=2024-01-15T10:30:00
model_summary=gpt-4o-mini
---
[2024-01-15T10:30:05] step=0 kind=model_summary
メモ帳アプリケーションを起動する操作を実行します。

[2024-01-15T10:30:10] step=1 kind=action
click button=None model=(100,200) screen=(125,250)

[2024-01-15T10:30:12] step=1 kind=model_summary
メモ帳が開かれたことを確認し、次にテキストを入力します。
```

### デバッグログ

デバッグテキストファイルは各スクリーンショットと共に保存されます：

- `YYYYmmdd_HHMMSS_mmm_Debug.txt`: 詳細なデバッグ情報

## トラブルシューティング

### 問題: 環境変数が読み込まれない

**解決策**:
- `.env` ファイルがプロジェクトのルートディレクトリにあることを確認
- `python-dotenv` がインストールされていることを確認: `pip install python-dotenv`

### 問題: Azure 認証エラー

**解決策**:
- `az login` を実行して Azure にログイン
- または、環境変数 `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID` を設定

### 問題: クリック座標がずれる

**解決策**:
- `src/config.py` の `DISPLAY_WIDTH` と `DISPLAY_HEIGHT` を確認
- スクリーンの解像度を確認: `image_processing.get_primary_screen_size()` が正しい値を返すか確認
- マルチモニター環境の場合、プライマリモニターの設定を確認

### 問題: 日本語入力ができない

**解決策**:
- IME の状態を確認（タスクバーの「A」または「あ」の表示）
- `IME_GUIDANCE_TEMPLATE` の指示に従ってモデルがIMEを切り替えているか確認
- 必要に応じて手動でIMEを切り替えてから再実行

### 問題: API レート制限エラー

**解決策**:
- リトライロジックが自動的に処理しますが、頻繁に発生する場合は以下を調整：
  - `src/config.py` の `MAX_API_RETRIES` を増やす
  - `INITIAL_BACKOFF_SECONDS` を増やす

## セキュリティのベストプラクティス

### 1. 環境変数ファイルの保護

`.env` ファイルは絶対に GitHub にコミットしないでください。`.gitignore` で除外されていることを確認してください。

### 2. 機密情報の入力を避ける

パスワードやAPIキーなどの機密情報を入力するタスクは避けてください。以下の設定で記録を最小限にできます：

```python
SHOW_TYPED_TEXT_IN_ANNOTATION = False
LOG_TYPED_TEXT_IN_SESSION_SUMMARY = False
```

### 3. セーフティチェックの活用

リスクの高い操作（購入、削除など）は自動確認がブロックされ、手動確認が求められます：

```python
AUTO_CONFIRM_BLOCK_RISKY = True  # デフォルトで有効
```

### 4. スクリーンショットの管理

`screenshots/` ディレクトリと `*-sessionsummary.txt` ファイルは機密情報を含む可能性があります。これらのファイルは `.gitignore` で除外されています。

## 高度な使用方法

### カスタムアクションの追加

新しいアクションを追加するには：

1. `src/actions.py` に新しい `perform_*()` 関数を追加
2. `src/main.py` の `execute_action()` に新しいアクションタイプを追加

例：
```python
# src/actions.py
def perform_custom_action():
    # カスタムロジック
    pass

# src/main.py
def execute_action(...):
    # ...
    elif action_type == "custom_action":
        perform_custom_action()
```

### セッションサマリーのカスタマイズ

サマリー生成のプロンプトをカスタマイズするには、`src/session.py` の `_summarize_text_with_model()` 関数を変更します。

### ログレベルの調整

より詳細なログを出力するには、各 `print()` 文を確認し、必要に応じて追加します。

## パフォーマンスチューニング

### 1. スクリーンショットの最適化

頻繁なスクリーンショットはパフォーマンスに影響します：

```python
EVIDENCE_BEFORE_AFTER_FOR_INPUT = False  # 入力前後のスクリーンショットを無効化
```

### 2. デバッグ画像の無効化

デバッグ画像の生成を無効化：

```python
SAVE_MODEL_RESPONSE_DEBUG_IMAGE = False
```

### 3. セッションサマリーの無効化

セッションサマリーを無効化してAPI呼び出しを削減：

```python
ENABLE_SESSION_SUMMARY = False
```

## よくある質問

**Q: このツールは Mac や Linux で動作しますか？**

A: 現在は Windows 専用です。PyAutoGUI は他のOSでも動作しますが、IME関連の機能やWindows固有の動作に依存しています。

**Q: 最大ステップ数を変更できますか？**

A: はい、`src/config.py` の `MAX_STEPS` を変更してください。

**Q: タスクを途中で停止するには？**

A: マウスカーソルを画面の隅に移動すると、PyAutoGUI の FAILSAFE 機能で停止します。

**Q: 複数のタスクを連続実行できますか？**

A: 現在は1つのタスクのみです。複数のタスクを実行するには、スクリプトを複数回実行するか、メインループをカスタマイズしてください。

## サポート

問題が発生した場合は、以下の情報を含めて報告してください：

1. エラーメッセージ
2. セッションサマリーファイル
3. デバッグログファイル
4. 実行したコマンド
5. 環境情報（Python バージョン、OS、Azure OpenAI モデル）
