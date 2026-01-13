# アーキテクチャドキュメント

## 概要

このプロジェクトは、Azure OpenAI の computer-use 機能を使用して Windows 環境を自動操作するためのツールです。モジュール化された構造により、保守性と拡張性が向上しています。

## ディレクトリ構造

```
202501-computer-use-test/
├── computer-use-test.py      # メインエントリーポイント（後方互換性用）
├── src/                       # ソースコードディレクトリ
│   ├── __init__.py           # パッケージ初期化
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
├── screenshots/               # スクリーンショット保存先（実行時生成）
├── .env                       # 環境変数ファイル（Git管理外）
├── .env.example              # 環境変数のサンプル
├── requirements.txt          # Python依存関係
└── README.md                 # プロジェクト概要
```

## モジュール構成

### 1. config.py - 環境設定モジュール

**責務**: 環境変数の読み込みと設定値の管理

**主要機能**:
- `.env` ファイルからの環境変数読み込み
- Azure OpenAI エンドポイントの構築
- アプリケーション全体で使用される定数の定義
- ディスプレイ設定、APIリトライ設定、セーフティ設定など

**主要な関数**:
- `_env()`: 環境変数の取得
- `_env_bool()`: ブール値としての環境変数取得
- `_require_env()`: 必須環境変数の取得
- `_build_azure_openai_base_url()`: Azure OpenAI ベースURLの構築

### 2. utils.py - ユーティリティモジュール

**責務**: 汎用的なヘルパー関数の提供

**主要機能**:
- キー名の正規化（control → ctrl など）
- マウスボタン名の正規化
- テキストフォーマット
- 座標のスケーリング

**主要な関数**:
- `normalize_key_name()`: キーボードキー名の正規化
- `normalize_mouse_button()`: マウスボタン名の正規化
- `format_typed_text_for_log()`: ログ用テキストフォーマット
- `scale_point()`: 座標のスケーリング

### 3. client.py - Azure OpenAI クライアントモジュール

**責務**: Azure OpenAI API との通信管理

**主要機能**:
- Azure認証とクライアント初期化
- APIリクエストのリトライロジック
- レート制限、接続エラー、サーバーエラーの処理
- セーフティチェックの自動確認
- レスポンスの解析

**主要な関数**:
- `init_client()`: クライアントの初期化
- `responses_create_with_retry()`: リトライ機能付きAPIリクエスト
- `get_first_computer_call()`: レスポンスからコンピューターコールを取得
- `iter_output_texts()`: レスポンスからテキスト出力を抽出
- `make_tools()`: ツール定義の作成

### 4. image_processing.py - 画像処理モジュール

**責務**: スクリーンショットと画像アノテーション

**主要機能**:
- フルスクリーンスクリーンショットの撮影
- クリックポイントのアノテーション（赤い円と十字線）
- テキストアノテーション（半透明背景付き）
- 画像のData URL変換
- モデル送信用画像の選択

**主要な関数**:
- `capture_fullscreen_screenshot()`: スクリーンショット撮影
- `annotate_click_points()`: クリックポイントのアノテーション
- `annotate_text()`: テキストアノテーション
- `image_file_to_data_url()`: Data URL変換
- `get_primary_screen_size()`: スクリーンサイズ取得

### 5. actions.py - アクション実行モジュール

**責務**: コンピューター操作の実行

**主要機能**:
- マウス操作（クリック、ダブルクリック、移動、ドラッグ）
- キーボード操作（テキスト入力、キープレス）
- スクロール操作
- 待機操作
- 座標の自動スケーリング

**主要な関数**:
- `perform_click()`: クリック実行
- `perform_double_click()`: ダブルクリック実行
- `perform_move()`: マウス移動
- `perform_drag()`: ドラッグ操作
- `perform_scroll()`: スクロール操作
- `perform_type()`: テキスト入力
- `perform_keypress()`: キープレス
- `perform_wait()`: 待機

### 6. session.py - セッション管理モジュール

**責務**: セッションログとサマリーの記録

**主要機能**:
- セッション開始時刻の記録
- 各ステップのアクションログ
- AIモデルによるレスポンスの要約
- タイムスタンプ付きイベントログ

**主要な関数**:
- `init_models()`: 使用モデルの設定
- `log_session_event()`: イベントのログ記録
- `log_model_response_summary()`: モデルレスポンスの要約ログ

### 7. confirmation.py - 確認処理モジュール

**責務**: ユーザー確認の自動化と判定

**主要機能**:
- メッセージが確認要求かどうかの判定
- ヒューリスティック判定（キーワードベース）
- AIモデルによる確認要求判定
- リスク用語のチェック
- 自動確認メッセージの送信

**主要な関数**:
- `init_models()`: 使用モデルの設定
- `get_or_confirm_computer_call()`: コンピューターコール取得または確認送信

### 8. debug.py - デバッグモジュール

**責務**: デバッグ情報の生成

**主要機能**:
- デバッグノートの生成
- デバッグテキストファイルの保存
- デバッグ画像の生成（レスポンス情報をオーバーレイ）

**主要な関数**:
- `save_model_debug_image()`: デバッグ画像の保存

### 9. indicator.py - ステータスインジケーターモジュール

**責務**: 実行状態の視覚的な表示

**主要機能**:
- 常時最前面のステータスウィンドウ表示
- 現在のステップ、フェーズ、最後のアクションの表示
- 経過時間の表示
- マルチスレッドでの安全な状態更新
- クリック透過機能（Windows）

**主要なクラスと関数**:
- `StatusIndicator`: インジケーターウィンドウの管理クラス
- `IndicatorStatus`: 表示状態を保持するデータクラス
- `start()`: インジケーターの開始
- `update_status()`: 状態の更新
- `shutdown()`: インジケーターの終了

### 10. main.py - メインモジュール

**責務**: アプリケーション全体の統合と実行

**主要機能**:
- コマンドライン引数の解析
- 各モジュールの初期化
- メインループの実行
- アクションの実行とAPIとの通信

**主要な関数**:
- `init_runtime_from_env()`: ランタイム初期化
- `execute_action()`: 単一アクションの実行
- `main()`: メインエントリーポイント

## データフロー

1. **初期化フロー**:
   ```
   main() → init_runtime_from_env() → config, client, session, confirmation の初期化
   ```

2. **APIリクエストフロー**:
   ```
   main() → client.responses_create_with_retry() → Azure OpenAI API
   ```

3. **アクション実行フロー**:
   ```
   main() → execute_action() → actions.perform_*() → pyautogui → Windows OS
   ```

4. **画像処理フロー**:
   ```
   アクション実行 → image_processing.capture_fullscreen_screenshot()
   → image_processing.annotate_*() → モデルへ送信
   ```

5. **ログ記録フロー**:
   ```
   各ステップ → session.log_session_event() → セッションサマリーファイル
   レスポンス受信 → session.log_model_response_summary() → AIによる要約
   ```

## 設定管理

設定は以下の優先順位で決定されます：

1. **コマンドライン引数** (`--message`)
2. **環境変数** (`.env` ファイルまたはシステム環境変数)
3. **デフォルト値** (各モジュールで定義)

### 必須環境変数

- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI のエンドポイント
- `AZURE_OPENAI_MODEL_COMPUTER_USE`: コンピューター操作用モデル
- `AZURE_OPENAI_MODEL_SUMMARY`: サマリー生成用モデル（セッションサマリー有効時）
- `AZURE_OPENAI_MODEL_CONFIRM`: 確認判定用モデル（確認インタープリター有効時）

## エラーハンドリング

### APIエラー

- **レート制限 (429)**: 指数バックオフでリトライ
- **接続エラー**: 指数バックオフでリトライ
- **サーバーエラー (5xx)**: 指数バックオフでリトライ
- **セーフティチェック**: ユーザー確認後にリトライ

### アクションエラー

- **無効な座標**: エラーログ出力後、実行を停止
- **無効なパラメータ**: ValueError を発生させて停止

## セキュリティ考慮事項

1. **環境変数の保護**: `.env` ファイルは `.gitignore` で除外
2. **機密情報のログ記録**: `SHOW_TYPED_TEXT_IN_ANNOTATION` で制御可能
3. **セーフティチェック**: リスク用語の検出と手動確認
4. **Azure認証**: DefaultAzureCredential による安全な認証

## パフォーマンス最適化

1. **画像処理**: 必要な場合のみアノテーションを生成
2. **APIリトライ**: Retry-After ヘッダーの尊重
3. **スクリーンショット**: プライマリスクリーンのみキャプチャ

## 拡張性

新しい機能を追加する場合：

1. **新しいアクション**: `actions.py` に新しい `perform_*()` 関数を追加
2. **新しい画像処理**: `image_processing.py` に関数を追加
3. **新しい設定**: `config.py` に定数を追加
4. **メインループの変更**: `main.py` の `execute_action()` を更新

## テストとデバッグ

- **構文チェック**: `python -m py_compile src/*.py`
- **デバッグ画像**: `SAVE_MODEL_RESPONSE_DEBUG_IMAGE = True` で有効化
- **セッションログ**: `ENABLE_SESSION_SUMMARY = True` で有効化
