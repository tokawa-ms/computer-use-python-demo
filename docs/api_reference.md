# API リファレンス

このドキュメントは、各モジュールの主要な関数とクラスのリファレンスを提供します。

## src.config モジュール

### 環境変数関連

#### `_env(name: str, default: str | None = None) -> str | None`

環境変数を取得します。

**パラメータ**:
- `name`: 環境変数名
- `default`: デフォルト値（省略可能）

**戻り値**:
- 環境変数の値、または設定されていない場合はデフォルト値

---

#### `_env_bool(name: str, default: bool = False) -> bool`

環境変数をブール値として取得します。

**パラメータ**:
- `name`: 環境変数名
- `default`: デフォルト値

**戻り値**:
- "1", "true", "yes", "y", "on" の場合は True、それ以外は False

---

#### `_require_env(name: str) -> str`

必須の環境変数を取得します。

**パラメータ**:
- `name`: 環境変数名

**戻り値**:
- 環境変数の値

**例外**:
- `RuntimeError`: 環境変数が設定されていない場合

---

#### `_build_azure_openai_base_url() -> str`

Azure OpenAI のベース URL を構築します。

**戻り値**:
- Azure OpenAI のベース URL

**例外**:
- `RuntimeError`: 必要な環境変数が設定されていない場合

### 設定定数

- `DISPLAY_WIDTH`: モデルが認識するディスプレイ幅（デフォルト: 2560）
- `DISPLAY_HEIGHT`: モデルが認識するディスプレイ高さ（デフォルト: 1600）
- `MAX_STEPS`: 最大実行ステップ数（デフォルト: 30）
- `AUTO_CONFIRM`: 自動確認の有効化（デフォルト: True）
- `SCREENSHOTS_DIR`: スクリーンショット保存ディレクトリ

---

## src.utils モジュール

#### `normalize_key_name(key: str) -> str`

キーボードキー名を正規化します。

**パラメータ**:
- `key`: 元のキー名

**戻り値**:
- 正規化されたキー名

**例**:
```python
normalize_key_name("control")  # "ctrl"
normalize_key_name("return")   # "enter"
```

---

#### `normalize_mouse_button(button: str | None) -> str`

マウスボタン名を正規化します。

**パラメータ**:
- `button`: 元のボタン名（None の場合は "left" を返す）

**戻り値**:
- "left", "right", "middle" のいずれか

---

#### `format_typed_text_for_log(text: str, *, max_chars: int = 200) -> str`

ログ出力用にテキストをフォーマットします。

**パラメータ**:
- `text`: フォーマットするテキスト
- `max_chars`: 最大文字数

**戻り値**:
- フォーマットされたテキスト

---

#### `scale_point(x: int, y: int, *, from_width: int, from_height: int, to_width: int, to_height: int) -> tuple[int, int]`

座標をスケーリングします。

**パラメータ**:
- `x`, `y`: 元の座標
- `from_width`, `from_height`: 元のディスプレイサイズ
- `to_width`, `to_height`: 変換先のディスプレイサイズ

**戻り値**:
- スケーリングされた座標 (x, y)

---

## src.client モジュール

#### `init_client() -> None`

Azure OpenAI クライアントを初期化します。

環境変数から設定を読み込み、Azure 認証情報を使用してクライアントを作成します。

---

#### `responses_create_with_retry(**kwargs) -> Response`

リトライロジックを含む API リクエストを実行します。

**パラメータ**:
- `**kwargs`: `client.responses.create` に渡すパラメータ

**戻り値**:
- API レスポンス

**例外**:
- `RuntimeError`: クライアントが初期化されていない場合
- 各種 API エラー: リトライ上限に達した場合

**リトライ対象**:
- レート制限エラー (429)
- 接続エラー
- サーバーエラー (5xx)
- セーフティチェック

---

#### `get_first_computer_call(response_output: list) -> ComputerCall | None`

レスポンスから最初のコンピューターコールを取得します。

**パラメータ**:
- `response_output`: API レスポンスの出力リスト

**戻り値**:
- 最初のコンピューターコール、存在しない場合は None

---

#### `iter_output_texts(response_output: list) -> list[str]`

レスポンスからテキスト出力を抽出します。

**パラメータ**:
- `response_output`: API レスポンスの出力リスト

**戻り値**:
- テキスト出力のリスト

---

#### `make_tools(environment: str) -> list[dict]`

コンピューター使用ツールの定義を作成します。

**パラメータ**:
- `environment`: 実行環境 ("windows", "linux", "macos")

**戻り値**:
- ツール定義のリスト

---

## src.image_processing モジュール

#### `capture_fullscreen_screenshot(*, screenshots_dir: os.PathLike | str) -> Path`

フルスクリーンのスクリーンショットを撮影します。

**パラメータ**:
- `screenshots_dir`: スクリーンショットの保存先ディレクトリ

**戻り値**:
- 保存されたスクリーンショットのパス

---

#### `get_primary_screen_size() -> tuple[int, int]`

プライマリスクリーンのサイズを取得します。

**戻り値**:
- (幅, 高さ) のタプル

---

#### `annotate_click_points(image_path: os.PathLike | str, points: list[tuple[int, int]], *, output_path: os.PathLike | str | None = None, display_width: int | None = None, display_height: int | None = None) -> Path`

画像にクリックポイントのアノテーションを追加します。

**パラメータ**:
- `image_path`: 元の画像のパス
- `points`: クリックポイントのリスト [(x, y), ...]
- `output_path`: 出力ファイルのパス（省略可能）
- `display_width`: ディスプレイ幅（スケーリング用、省略可能）
- `display_height`: ディスプレイ高さ（スケーリング用、省略可能）

**戻り値**:
- アノテーション付き画像のパス

---

#### `annotate_text(image_path: os.PathLike | str, note: str, *, output_path: os.PathLike | str | None = None) -> Path`

画像にテキストアノテーションを追加します。

**パラメータ**:
- `image_path`: 元の画像のパス
- `note`: 追加するテキスト
- `output_path`: 出力ファイルのパス（省略可能）

**戻り値**:
- アノテーション付き画像のパス

---

#### `image_file_to_data_url(image_path: os.PathLike | str, *, default_mime: str = "image/png") -> str`

画像ファイルを Data URL に変換します。

**パラメータ**:
- `image_path`: 画像ファイルのパス
- `default_mime`: デフォルトの MIME タイプ

**戻り値**:
- Data URL 形式の文字列

**例外**:
- `FileNotFoundError`: 画像ファイルが存在しない場合

---

#### `choose_model_image(clean: Path, annotated: Path | None = None) -> Path`

モデルに送信する画像を選択します。

**パラメータ**:
- `clean`: クリーンな画像のパス
- `annotated`: アノテーション付き画像のパス（省略可能）

**戻り値**:
- 選択された画像のパス

---

## src.actions モジュール

#### `perform_click(x: int, y: int, *, display_width: int, display_height: int, button: str | None = None) -> tuple[int, int]`

指定された座標でマウスクリックを実行します。

**パラメータ**:
- `x`, `y`: モデル座標系の座標
- `display_width`: モデルのディスプレイ幅
- `display_height`: モデルのディスプレイ高さ
- `button`: クリックするボタン（"left", "right", "middle"、省略可能）

**戻り値**:
- 実際にクリックされたスクリーン座標 (px, py)

---

#### `perform_double_click(x: int, y: int, *, display_width: int, display_height: int, button: str | None = None) -> tuple[int, int]`

指定された座標でマウスダブルクリックを実行します。

**パラメータ**:
- `x`, `y`: モデル座標系の座標
- `display_width`: モデルのディスプレイ幅
- `display_height`: モデルのディスプレイ高さ
- `button`: クリックするボタン（省略可能）

**戻り値**:
- 実際にクリックされたスクリーン座標 (px, py)

---

#### `perform_move(x: int, y: int, *, display_width: int, display_height: int, duration: float = 0.0) -> tuple[int, int]`

マウスカーソルを指定された座標に移動します。

**パラメータ**:
- `x`, `y`: モデル座標系の座標
- `display_width`: モデルのディスプレイ幅
- `display_height`: モデルのディスプレイ高さ
- `duration`: 移動にかける時間（秒、省略可能）

**戻り値**:
- 実際の移動先スクリーン座標 (px, py)

---

#### `perform_drag(path: list[dict], *, display_width: int, display_height: int, duration: float = 0.2, button: str | None = None) -> tuple[int, int]`

マウスドラッグ操作を実行します。

**パラメータ**:
- `path`: ドラッグパスの座標リスト [{"x": x1, "y": y1}, ...]
- `display_width`: モデルのディスプレイ幅
- `display_height`: モデルのディスプレイ高さ
- `duration`: ドラッグにかける時間（秒、省略可能）
- `button`: ドラッグに使用するボタン（省略可能）

**戻り値**:
- ドラッグ終了時のスクリーン座標 (px, py)

**例外**:
- `ValueError`: パスが空または 2 点未満の場合

---

#### `perform_scroll(x: int, y: int, *, display_width: int, display_height: int, scroll_x: int = 0, scroll_y: int = 0) -> tuple[int, int]`

指定された座標でスクロール操作を実行します。

**パラメータ**:
- `x`, `y`: モデル座標系の座標
- `display_width`: モデルのディスプレイ幅
- `display_height`: モデルのディスプレイ高さ
- `scroll_x`: 横スクロール量（省略可能）
- `scroll_y`: 縦スクロール量（省略可能）

**戻り値**:
- スクロール位置のスクリーン座標 (px, py)

---

#### `perform_type(text: str, *, interval: float = 0.0) -> None`

テキストを入力します。

**パラメータ**:
- `text`: 入力するテキスト
- `interval`: 各文字の入力間隔（秒、省略可能）

**例外**:
- `ValueError`: text が文字列でない場合

---

#### `perform_wait(duration_ms: int | None = None) -> None`

指定された時間だけ待機します。

**パラメータ**:
- `duration_ms`: 待機時間（ミリ秒、省略可能、None または 0 以下の場合は 1 秒待機）

---

#### `perform_keypress(keys: list[str]) -> None`

キーボードのキーを押します。

**パラメータ**:
- `keys`: 押すキーのリスト

**例外**:
- `ValueError`: キーが指定されていない場合

**例**:
```python
perform_keypress(["ctrl", "c"])  # Ctrl+C
perform_keypress(["enter"])      # Enter
```

---

## src.session モジュール

#### `init_models(*, summary_model: str | None = None) -> None`

セッション管理で使用するモデル名を設定します。

**パラメータ**:
- `summary_model`: サマリー生成に使用するモデル名

---

#### `log_session_event(*, step: int, kind: str, detail: str) -> None`

セッションイベントをログに記録します。

**パラメータ**:
- `step`: ステップ番号
- `kind`: イベントの種類
- `detail`: イベントの詳細

---

#### `log_model_response_summary(*, step: int, response_obj) -> None`

モデルレスポンスの要約をログに記録します。

**パラメータ**:
- `step`: ステップ番号
- `response_obj`: レスポンスオブジェクト

---

## src.confirmation モジュール

#### `init_models(*, confirm_model: str | None = None, computer_use_model: str | None = None) -> None`

確認処理で使用するモデル名を設定します。

**パラメータ**:
- `confirm_model`: 確認判定に使用するモデル名
- `computer_use_model`: コンピューター操作に使用するモデル名

---

#### `get_or_confirm_computer_call(r) -> tuple[Response, ComputerCall | None]`

レスポンスからコンピューターコールを取得するか、必要に応じて確認を送信します。

**パラメータ**:
- `r`: API レスポンス

**戻り値**:
- (レスポンス, コンピューターコール) のタプル
- コンピューターコールがない場合は (レスポンス, None)

**例外**:
- `RuntimeError`: COMPUTER_USE_MODEL が設定されていない場合

---

## src.indicator モジュール

### クラス: IndicatorStatus

**説明**: インジケーターに表示する状態を保持するデータクラス。

**属性**:
- `step` (int): 現在のステップ番号
- `max_steps` (int): 最大ステップ数
- `phase` (str): 現在のフェーズ（"API 待ち"、"操作中"、"確認中" など）
- `last_action` (str): 最後に実行したアクション
- `started_at` (float): セッション開始時刻（Unix タイムスタンプ）

---

### クラス: StatusIndicator

**説明**: 実行中に画面上にステータスウィンドウを表示するクラス。別スレッドで Tkinter を動かし、メインスレッドからは状態を更新するだけで動作します。

#### `__init__(*, enabled: bool = True, opacity: float = 0.78, width: int = 280, height: int = 92, margin: int = 12, poll_ms: int = 120, position: str = "top-right", offset_x: int = 12, offset_y: int = 12, font_family: str = "Segoe UI", font_size: int = 9, click_through: bool = True) -> None`

ステータスインジケーターを初期化します。

**パラメータ**:
- `enabled`: インジケーターを有効にするかどうか（デフォルト: True）
- `opacity`: ウィンドウの不透明度（0.2～1.0、デフォルト: 0.78）
- `width`: ウィンドウの幅（ピクセル、デフォルト: 280）
- `height`: ウィンドウの高さ（ピクセル、デフォルト: 92）
- `margin`: ウィンドウのマージン（ピクセル、デフォルト: 12）
- `poll_ms`: 状態更新のポーリング間隔（ミリ秒、デフォルト: 120）
- `position`: ウィンドウの位置（"top-right", "top-left", "bottom-right", "bottom-left"、デフォルト: "top-right"）
- `offset_x`: 水平方向のオフセット（ピクセル、デフォルト: 12）
- `offset_y`: 垂直方向のオフセット（ピクセル、デフォルト: 12）
- `font_family`: フォントファミリー（デフォルト: "Segoe UI"）
- `font_size`: フォントサイズ（6～48、デフォルト: 9）
- `click_through`: クリック透過を有効にするかどうか（Windows のみ、デフォルト: True）

---

#### `start() -> None`

インジケーターを起動します（別スレッドで実行）。

**注意**: `enabled=False` の場合は何もしません。

---

#### `stop() -> None`

インジケーターを停止します。

---

#### `update(*, step: int, max_steps: int, phase: str, last_action: str) -> None`

表示状態を更新します。

**パラメータ**:
- `step`: 現在のステップ番号
- `max_steps`: 最大ステップ数
- `phase`: 現在のフェーズ
- `last_action`: 最後に実行したアクション

**例**:
```python
from src.indicator import StatusIndicator

indicator = StatusIndicator(enabled=True)
indicator.start()

# 状態を更新
indicator.update(
    step=1,
    max_steps=30,
    phase="操作中",
    last_action="click"
)

# 終了時
indicator.stop()
```

---

## src.debug モジュール

#### `save_model_debug_image(*, sent_image_path: Path, step: int, response_obj) -> Path | None`

モデルレスポンス用のデバッグ画像を保存します。

**パラメータ**:
- `sent_image_path`: モデルに送信された画像のパス
- `step`: ステップ番号
- `response_obj`: レスポンスオブジェクト

**戻り値**:
- デバッグ画像のパス、保存されなかった場合は None

---

## src.main モジュール

#### `init_runtime_from_env() -> None`

環境変数からランタイム設定を初期化します。

**例外**:
- `RuntimeError`: 必須の環境変数が設定されていない場合

---

#### `build_initial_user_instruction(*, message: str) -> str`

初期ユーザー指示を構築します。

**パラメータ**:
- `message`: ユーザーからの直接指示

**戻り値**:
- 構築された指示文字列

---

#### `execute_action(*, step: int, action, action_type: str) -> Path | None`

単一のアクションを実行します。

**パラメータ**:
- `step`: 現在のステップ番号
- `action`: アクションオブジェクト
- `action_type`: アクションの種類

**戻り値**:
- 生成されたスクリーンショットのパス、生成されなかった場合は None

**例外**:
- `ValueError`: 無効なアクションパラメータの場合

---

#### `main(argv: list[str] | None = None) -> int`

メイン実行関数。

**パラメータ**:
- `argv`: コマンドライン引数のリスト（テスト用、省略可能）

**戻り値**:
- 終了コード（0: 成功）

**例外**:
- `RuntimeError`: 必須パラメータが不足している場合

---

## 使用例

### 基本的な実行

```python
from src.main import main

# コマンドライン引数で実行
main(["--message", "メモ帳を開いてください"])
```

### カスタムアクションの実行

```python
from src import actions

# クリック操作
actions.perform_click(100, 200, display_width=2560, display_height=1600)

# テキスト入力
actions.perform_type("Hello, World!")

# キープレス
actions.perform_keypress(["ctrl", "s"])
```

### スクリーンショット撮影

```python
from src.image_processing import capture_fullscreen_screenshot, annotate_text
from pathlib import Path

# スクリーンショット撮影
screenshot_path = capture_fullscreen_screenshot(screenshots_dir="screenshots")

# アノテーション追加
annotated_path = annotate_text(screenshot_path, "テスト実行中")
```

### セッションログの記録

```python
from src.session import log_session_event, init_models

# モデル初期化
init_models(summary_model="gpt-4o-mini")

# イベントログ記録
log_session_event(step=1, kind="action", detail="クリック操作を実行")
```
