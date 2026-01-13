"""
セッション管理モジュール

セッションサマリーの記録と管理を行います。
実行ログの要約生成、イベントの記録などを含みます。
"""

from datetime import datetime
from pathlib import Path

from .client import iter_output_texts, responses_create_with_retry
from .config import (
    ENABLE_SESSION_SUMMARY,
    SCRIPT_DIR,
    SESSION_SUMMARY_MAX_OUTPUT_TOKENS,
)
from .utils import format_typed_text_for_log


# セッション開始時刻
_SESSION_START_DT = datetime.now()
_SESSION_START_STAMP = _SESSION_START_DT.strftime("%Y%m%d_%H%M%S")

# セッションサマリーファイルのパス
SESSION_SUMMARY_PATH = SCRIPT_DIR / f"{_SESSION_START_STAMP}-sessionsummary.txt"

# モデル名（init_models で設定される）
SESSION_SUMMARY_MODEL: str | None = None


def init_models(*, summary_model: str | None = None) -> None:
    """
    セッション管理で使用するモデル名を設定します。
    
    Args:
        summary_model: サマリー生成に使用するモデル名
    """
    global SESSION_SUMMARY_MODEL
    SESSION_SUMMARY_MODEL = summary_model


def _append_session_summary_line(line: str) -> None:
    """
    セッションサマリーファイルに行を追加します。
    
    Args:
        line: 追加する行
    """
    if not ENABLE_SESSION_SUMMARY:
        return
    SESSION_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SESSION_SUMMARY_PATH.open("a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")


def _ensure_session_summary_header() -> None:
    """
    セッションサマリーファイルにヘッダーを書き込みます（まだ存在しない場合）。
    """
    if not ENABLE_SESSION_SUMMARY:
        return
    if SESSION_SUMMARY_PATH.exists():
        return
    header = (
        f"session_start={_SESSION_START_DT.isoformat(timespec='seconds')}\n"
        f"model_summary={SESSION_SUMMARY_MODEL}\n"
        "---\n"
    )
    SESSION_SUMMARY_PATH.write_text(header, encoding="utf-8")


def _summarize_text_with_model(text: str) -> str:
    """
    テキストをAIモデルで要約します。
    
    Args:
        text: 要約するテキスト
    
    Returns:
        要約されたテキスト
    
    Raises:
        RuntimeError: モデルが設定されていない場合
    """
    if not isinstance(text, str) or not text.strip():
        return "(no content)"

    if SESSION_SUMMARY_MODEL is None:
        raise RuntimeError(
            "SESSION_SUMMARY_MODEL is not set. Set AZURE_OPENAI_MODEL_SUMMARY in .env or disable ENABLE_SESSION_SUMMARY."
        )

    prompt = (
        "あなたはログ要約器です。以下のログ1件を、操作の時系列で追えるように日本語で簡潔に要約してください。\n"
        "要件:\n"
        "- 1〜3行程度。\n"
        "- 重要: 次の操作/指示があれば明示する。\n"
        "- 余計な推測はしない。\n"
    )

    r = responses_create_with_retry(
        model=SESSION_SUMMARY_MODEL,
        input=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text[:12000]},
        ],
        max_output_tokens=SESSION_SUMMARY_MAX_OUTPUT_TOKENS,
        truncation="auto",
        temperature=0,
    )
    out = "\n".join(iter_output_texts(getattr(r, "output", []) or []))
    out = (out or "").strip()
    return out or "(empty summary)"


def log_session_event(*, step: int, kind: str, detail: str) -> None:
    """
    セッションイベントをログに記録します。
    
    Args:
        step: ステップ番号
        kind: イベントの種類
        detail: イベントの詳細
    """
    if not ENABLE_SESSION_SUMMARY:
        return
    _ensure_session_summary_header()
    ts = datetime.now().isoformat(timespec="seconds")
    _append_session_summary_line(f"[{ts}] step={step} kind={kind}\n{detail}\n")


def _summarize_action_for_log(action) -> str:
    """
    アクションをログ用に要約します。
    
    Args:
        action: アクションオブジェクト
    
    Returns:
        要約された文字列
    """
    action_type = getattr(action, "type", None)
    if not isinstance(action_type, str):
        return "action: (none)"

    if action_type in ("click", "double_click", "move"):
        x = getattr(action, "x", None)
        y = getattr(action, "y", None)
        button = getattr(action, "button", None)
        extra = f", button={button}" if isinstance(button, str) and button else ""
        return f"action: {action_type} x={x} y={y}{extra}"

    if action_type == "drag":
        path = getattr(action, "path", None)
        n = len(path) if isinstance(path, list) else "?"
        return f"action: drag path_len={n}"

    if action_type == "scroll":
        x = getattr(action, "x", None)
        y = getattr(action, "y", None)
        sx = getattr(action, "scroll_x", None)
        sy = getattr(action, "scroll_y", None)
        return f"action: scroll x={x} y={y} scroll_x={sx} scroll_y={sy}"

    if action_type == "type":
        text = getattr(action, "text", "")
        ln = len(text) if isinstance(text, str) else "?"
        if isinstance(text, str):
            preview = format_typed_text_for_log(text)
            return f"action: type text_len={ln} text='{preview}'"
        return f"action: type text_len={ln}"

    if action_type == "keypress":
        keys = getattr(action, "keys", None)
        from .image_processing import summarize_keypress
        return (
            summarize_keypress(keys) if isinstance(keys, list) else "action: keypress"
        )

    if action_type == "wait":
        duration_ms = getattr(action, "duration_ms", None)
        return f"action: wait duration_ms={duration_ms}"

    if action_type == "screenshot":
        return "action: screenshot"

    return f"action: {action_type}"


def log_model_response_summary(*, step: int, response_obj) -> None:
    """
    モデルレスポンスの要約をログに記録します。
    
    Args:
        step: ステップ番号
        response_obj: レスポンスオブジェクト
    """
    if not ENABLE_SESSION_SUMMARY:
        return

    from .client import get_first_computer_call

    rid = getattr(response_obj, "id", None)
    texts = iter_output_texts(getattr(response_obj, "output", []) or [])
    msg = "\n".join(t.strip() for t in texts if isinstance(t, str) and t.strip())

    next_call = get_first_computer_call(getattr(response_obj, "output", []) or [])
    next_action = getattr(next_call, "action", None) if next_call is not None else None
    action_line = _summarize_action_for_log(next_action)

    raw = f"response_id={rid}\n{action_line}"
    if msg:
        raw += "\nmessage:\n" + msg

    try:
        summary = _summarize_text_with_model(raw)
    except Exception as e:
        summary = f"(summary_failed: {e})"

    log_session_event(step=step, kind="model_summary", detail=summary)
