"""
デバッグモジュール

デバッグ用の画像とログファイルの生成を担当します。
"""

from pathlib import Path

from .client import get_first_computer_call, iter_output_texts
from .config import (
    DEBUG_NOTE_IMAGE_MAX_CHARS,
    DEBUG_NOTE_MAX_CHARS,
    DEBUG_TEXT_FILE_MAX_CHARS,
    SAVE_MODEL_RESPONSE_DEBUG_IMAGE,
)
from .image_processing import annotate_text
from .session import _summarize_action_for_log


def _build_debug_note(*, step: int, response_obj) -> str:
    """
    デバッグノートを構築します。
    
    Args:
        step: ステップ番号
        response_obj: レスポンスオブジェクト
    
    Returns:
        デバッグノートの文字列
    """
    rid = getattr(response_obj, "id", None)
    texts = iter_output_texts(getattr(response_obj, "output", []) or [])
    msg = "\n".join(t.strip() for t in texts if isinstance(t, str) and t.strip())

    next_call = get_first_computer_call(getattr(response_obj, "output", []) or [])
    next_action = getattr(next_call, "action", None) if next_call is not None else None
    action_line = _summarize_action_for_log(next_action)

    note = f"step={step}\nresponse_id={rid}\n{action_line}"
    if msg:
        note += "\nmessage:\n" + msg

    if len(note) > DEBUG_NOTE_MAX_CHARS:
        note = note[:DEBUG_NOTE_MAX_CHARS] + "…"
    return note


def _build_debug_note_summary(*, step: int, response_obj) -> str:
    """
    デバッグ画像用の短いノートを構築します。
    
    Args:
        step: ステップ番号
        response_obj: レスポンスオブジェクト
    
    Returns:
        短縮されたデバッグノートの文字列
    """
    full = _build_debug_note(step=step, response_obj=response_obj)
    # ヘッダー + 短縮されたメッセージブロックのみを保持
    if len(full) <= DEBUG_NOTE_IMAGE_MAX_CHARS:
        return full
    return full[:DEBUG_NOTE_IMAGE_MAX_CHARS] + "…"


def _write_debug_text_file(*, image_path: Path, step: int, response_obj) -> Path:
    """
    デバッグ用のテキストファイルを書き込みます。
    
    Args:
        image_path: 関連する画像のパス
        step: ステップ番号
        response_obj: レスポンスオブジェクト
    
    Returns:
        作成されたテキストファイルのパス
    """
    txt_path = image_path.with_name(f"{image_path.stem}_Debug.txt")
    note = _build_debug_note(step=step, response_obj=response_obj)
    if len(note) > DEBUG_TEXT_FILE_MAX_CHARS:
        note = note[:DEBUG_TEXT_FILE_MAX_CHARS] + "…"
    txt_path.write_text(note, encoding="utf-8")
    return txt_path


def save_model_debug_image(
    *, sent_image_path: Path, step: int, response_obj
) -> Path | None:
    """
    モデルレスポンス用のデバッグ画像を保存します。
    
    送信された画像にデバッグ情報をオーバーレイして保存します。
    
    Args:
        sent_image_path: モデルに送信された画像のパス
        step: ステップ番号
        response_obj: レスポンスオブジェクト
    
    Returns:
        デバッグ画像のパス、保存されなかった場合は None
    """
    if not SAVE_MODEL_RESPONSE_DEBUG_IMAGE:
        return None
    if not sent_image_path.exists():
        return None
    
    out_path = sent_image_path.with_name(
        f"{sent_image_path.stem}_Debug{sent_image_path.suffix}"
    )
    
    try:
        txt_path = _write_debug_text_file(
            image_path=sent_image_path, step=step, response_obj=response_obj
        )
        print(f"[{step}] Debug log saved: {txt_path}")
    except Exception as e:
        print(f"[{step}] Failed to save debug log: {e}")

    note = _build_debug_note_summary(step=step, response_obj=response_obj)
    return annotate_text(sent_image_path, note, output_path=out_path)
