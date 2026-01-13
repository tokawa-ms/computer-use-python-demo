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

# 常時適用されるIME安定性のための指示テンプレート
IME_GUIDANCE_TEMPLATE = """あなたはWindows環境を操作します。日本語IMEのON/OFFミスを避けるため、文字入力(type/keypressで入力に影響する操作)の前には必ず以下を守ってください。

1) 入力先をクリックしてフォーカスを確実にする（カーソル点滅/入力枠の強調を確認）。
2) タスクバー等のIME表示（例: A/あ）を目視で確認する。
3) 期待する状態でない場合のみIMEを切り替える（半角/全角など）。
4) 必要なら短いテスト入力で確認してから本入力を行う。
5) 不確実な場合は推測で続行せず、スクリーンショットを要求して状況確認する。
6) ひとつのテキストボックスに対する入力で、日本語、英語の切り替えを行う際には、切り替えごとにスクリーンショットとってモデルに確認を求める。

重要: 1回の切替で決め打ちしない。必ず表示を再確認する。
"""
