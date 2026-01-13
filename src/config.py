"""
環境設定モジュール

このモジュールは環境変数の読み込みと設定値の管理を担当します。
.envファイルから設定を読み込み、アプリケーション全体で使用される設定値を提供します。
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    load_dotenv = None


# スクリプトのディレクトリパス
SCRIPT_DIR = Path(__file__).resolve().parent.parent

# .envファイルから環境変数を読み込む（.envファイルはGitHubにコミットしないこと）
if load_dotenv is not None:
    load_dotenv()


def _env(name: str, default: str | None = None) -> str | None:
    """
    環境変数を取得します。

    Args:
        name: 環境変数名
        default: デフォルト値（環境変数が設定されていない場合）

    Returns:
        環境変数の値、または設定されていない場合はデフォルト値
    """
    v = os.getenv(name)
    if v is None:
        return default
    v = str(v).strip()
    return v if v else default


def _env_bool(name: str, default: bool = False) -> bool:
    """
    環境変数をブール値として取得します。

    Args:
        name: 環境変数名
        default: デフォルト値

    Returns:
        環境変数の値をブール値に変換した結果
        "1", "true", "yes", "y", "on" はTrue、それ以外はFalse
    """
    v = _env(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    """環境変数を整数として取得します（不正な場合は default）。"""
    v = _env(name)
    if v is None:
        return int(default)
    try:
        return int(str(v).strip())
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    """環境変数を浮動小数として取得します（不正な場合は default）。"""
    v = _env(name)
    if v is None:
        return float(default)
    try:
        return float(str(v).strip())
    except Exception:
        return float(default)


def _require_env(name: str) -> str:
    """
    必須の環境変数を取得します。設定されていない場合はエラーを発生させます。

    Args:
        name: 環境変数名

    Returns:
        環境変数の値

    Raises:
        RuntimeError: 環境変数が設定されていない場合
    """
    v = _env(name)
    if v is None:
        raise RuntimeError(
            f"Missing required env var: {name}. "
            "Create a .env file (see .env.example) or set it in your environment."
        )
    return v


def _build_azure_openai_base_url() -> str:
    """
    Azure OpenAIのベースURLを構築します。

    環境変数から以下の優先順位でURLを構築します：
    1. AZURE_OPENAI_BASE_URL
    2. AZURE_OPENAI_ENDPOINT
    3. AZURE_OPENAI_RESOURCE_NAME

    Returns:
        Azure OpenAIのベースURL

    Raises:
        RuntimeError: 必要な環境変数が設定されていない場合
    """
    base_url = _env("AZURE_OPENAI_BASE_URL")
    if base_url:
        # 末尾のスラッシュの有無を統一
        return base_url.rstrip("/") + "/"

    endpoint = _env("AZURE_OPENAI_ENDPOINT")
    if endpoint:
        # エンドポイント形式: https://<resource>.openai.azure.com
        return endpoint.rstrip("/") + "/openai/v1/"

    resource = _env("AZURE_OPENAI_RESOURCE_NAME")
    if resource:
        # リソース名形式: <resource>
        return f"https://{resource}.openai.azure.com/openai/v1/"

    raise RuntimeError(
        "Missing Azure OpenAI endpoint. Set AZURE_OPENAI_ENDPOINT (recommended) or AZURE_OPENAI_BASE_URL in .env."
    )


# ディスプレイ設定
DISPLAY_WIDTH = 2560
DISPLAY_HEIGHT = 1600

# スクリーンショット保存ディレクトリ
SCREENSHOTS_DIR = SCRIPT_DIR / "screenshots"

# 最大ステップ数
MAX_STEPS = 30

# 自動確認設定
AUTO_CONFIRM = True
CONFIRM_MESSAGE = "はい、進めてください。"

# エビデンス設定
# 入力操作（type/keypress）の前後でスクリーンショットを撮影するかどうか
EVIDENCE_BEFORE_AFTER_FOR_INPUT = True

# アノテーション設定
# タイプされたテキストをアノテーションに表示するかどうか
# True にすると、機密情報がスクリーンショットに含まれる可能性があります
SHOW_TYPED_TEXT_IN_ANNOTATION = False
ANNOTATION_MAX_CHARS = 60

# モデル入力画像ポリシー
# アノテーション付き画像をモデルに送信するかどうか
SEND_ANNOTATED_IMAGE_TO_MODEL = False

# デバッグスナップショット設定
SAVE_MODEL_RESPONSE_DEBUG_IMAGE = True
DEBUG_NOTE_MAX_CHARS = 4000
DEBUG_NOTE_IMAGE_MAX_CHARS = 800
DEBUG_TEXT_FILE_MAX_CHARS = 200000

# APIリトライ設定
MAX_API_RETRIES = 8
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 30.0

# セーフティチェック処理
# True の場合、セーフティチェックを自動的に確認します（無人実行では非推奨）
AUTO_ACK_SAFETY_CHECKS = False

# セッションサマリー設定
ENABLE_SESSION_SUMMARY = True
SESSION_SUMMARY_MAX_OUTPUT_TOKENS = 256

# セッションサマリーに入力されたテキスト内容を記録するかどうか
# 警告: 機密情報が記録される可能性があります
LOG_TYPED_TEXT_IN_SESSION_SUMMARY = _env_bool("LOG_TYPED_TEXT_IN_SESSION_SUMMARY", True)
SESSION_SUMMARY_TYPED_TEXT_MAX_CHARS = 200

# 実行中ステータスインジケーター（右上小窓）
# Tkinter で小さな常時最前面ウィンドウを表示し、簡易ステータスを出します。
ENABLE_STATUS_INDICATOR = _env_bool("ENABLE_STATUS_INDICATOR", False)

# インジケーターの見た目/挙動の調整（任意）
STATUS_INDICATOR_OPACITY = _env_float("STATUS_INDICATOR_OPACITY", 0.78)
STATUS_INDICATOR_WIDTH = _env_int("STATUS_INDICATOR_WIDTH", 280)
STATUS_INDICATOR_HEIGHT = _env_int("STATUS_INDICATOR_HEIGHT", 92)
STATUS_INDICATOR_MARGIN = _env_int("STATUS_INDICATOR_MARGIN", 12)
STATUS_INDICATOR_POLL_MS = _env_int("STATUS_INDICATOR_POLL_MS", 120)
STATUS_INDICATOR_FONT_FAMILY = _env("STATUS_INDICATOR_FONT_FAMILY", "Segoe UI")
STATUS_INDICATOR_FONT_SIZE = _env_int("STATUS_INDICATOR_FONT_SIZE", 9)
# top-right / top-left / bottom-right / bottom-left
STATUS_INDICATOR_POSITION = _env("STATUS_INDICATOR_POSITION", "top-right")
STATUS_INDICATOR_OFFSET_X = _env_int("STATUS_INDICATOR_OFFSET_X", 12)
STATUS_INDICATOR_OFFSET_Y = _env_int("STATUS_INDICATOR_OFFSET_Y", 12)
# True にするとクリックを背面に通し、フォーカスを奪いにくくします（Windowsで有効）
STATUS_INDICATOR_CLICK_THROUGH = _env_bool("STATUS_INDICATOR_CLICK_THROUGH", True)

# 確認インタープリターモデルの使用
# メッセージがユーザー確認を求めているかどうかを判定するために軽量モデルを使用するかどうか
USE_CONFIRM_INTERPRETER_MODEL = True

# 自動確認のセーフティガードレール
# リスクの高いアクションに関する確認は手動確認を要求するかどうか
AUTO_CONFIRM_BLOCK_RISKY = True

# リスクの高い確認に含まれる用語
RISKY_CONFIRM_TERMS = (
    "購入",
    "支払い",
    "決済",
    "送金",
    "振込",
    "削除",
    "フォーマット",
    "初期化",
    "解除",
    "退会",
    "アンインストール",
    "delete",
    "purchase",
    "payment",
    "transfer",
    "format",
    "uninstall",
)

# 常時適用されるガイダンス指示テンプレート（System prompt）
GUIDANCE_TEMPLATE = """あなたはWindows環境を操作します。文字入力は「コピー&ペースト」を基本とし、IMEモードはトラブル要因になるため絶対に切り替えません。

1) 入力先を必ずクリックしてフォーカスを確実にする（カーソル点滅/入力枠の強調を確認）。
2) IME表示（例: A/あ）は参考情報として目視してよいが、IMEの切り替え操作は絶対にしない。
3) 文字入力は原則としてコピー&ペーストで行う（推測でキー入力しない）。
4) ペースト後は、当該フィールドに意図した文字列が入ったことを目視確認する。不確実なら追加のスクリーンショットを取得して確認する。
    ペーストに失敗した場合に限り、次の代替手段のみ許可する:
    - 入力欄を再度クリックしてフォーカスを取り直してから、Ctrl+V で貼り付け
    - 右クリックメニューの「貼り付け」
    - アプリのメニュー（編集 -> 貼り付け など）
    それでも貼り付けできない場合は、推測で手入力せずに停止し、状況が分かるスクリーンショットを追加取得してユーザーに確認する。

5) 入力の確定（Enter）や、フォーム送信/保存/登録/送信/実行（Submit/Save/Send/OK/適用/確定など）を行う前に、必ずスクリーンショットで入力内容を目視確認する。
6) その確認では「ユーザーの指示どおりの場所（フィールド/欄/宛先など）に」「指示どおりの値」が入っていることを、ラベルやプレースホルダーとセットで照合する。少しでも不確実なら推測で進めない。
7) 入力内容や入力先が一致していない/不明な場合は、確定・送信せずに修正または追加のスクリーンショット取得を行い、必要ならユーザーに確認を求める。
8) 表形式のデータを入力するときは、列ヘッダーと各行のデータが正しく対応していることを必ず確認する。
9) 列ヘッダーやテキストボックスのラベルを目視で確認し、指示された内容と現在選択しているセルやテキストボックスが一致していることを確かめてから入力する。
10) アプリケーションの起動や遷移は、スタートメニューから実施する

重要: IME切替は禁止。確実に確認できる状態でのみ進める。
"""

# 後方互換: 旧名称（互換のために残す）
IME_GUIDANCE_TEMPLATE = GUIDANCE_TEMPLATE
