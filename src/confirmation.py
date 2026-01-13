"""
確認処理モジュール

ユーザー確認の自動化と判定を行います。
"""

from .client import (
    get_first_computer_call,
    iter_output_texts,
    make_tools,
    responses_create_with_retry,
)
from .config import (
    AUTO_CONFIRM,
    AUTO_CONFIRM_BLOCK_RISKY,
    CONFIRM_MESSAGE,
    RISKY_CONFIRM_TERMS,
    USE_CONFIRM_INTERPRETER_MODEL,
)
from .session import log_session_event


# モデル名（init_models で設定される）
CONFIRM_INTERPRETER_MODEL: str | None = None
COMPUTER_USE_MODEL: str | None = None


def init_models(
    *, confirm_model: str | None = None, computer_use_model: str | None = None
) -> None:
    """
    確認処理で使用するモデル名を設定します。

    Args:
        confirm_model: 確認判定に使用するモデル名
        computer_use_model: コンピューター操作に使用するモデル名
    """
    global CONFIRM_INTERPRETER_MODEL, COMPUTER_USE_MODEL
    CONFIRM_INTERPRETER_MODEL = confirm_model
    COMPUTER_USE_MODEL = computer_use_model


def _looks_like_confirmation_request_heuristic(text: str) -> bool:
    """
    ヒューリスティックでメッセージが確認要求かどうかを判定します。

    Args:
        text: チェックするテキスト

    Returns:
        確認要求と思われる場合は True
    """
    if not isinstance(text, str) or not text.strip():
        return False
    t = text
    return (
        "Should I" in t
        or "Can I" in t
        or "よろしい" in t
        or "進め" in t
        or "よい" in t
        or "開きますか" in t
        or "しますか" in t
        or "続行" in t
        or "続け" in t
    )


def _should_auto_confirm_via_interpreter(text: str) -> bool:
    """
    AIモデルを使用してメッセージが確認要求かどうかを判定します。

    リスクの高い用語が含まれる場合は自動確認を行いません。

    Args:
        text: チェックするテキスト

    Returns:
        自動確認すべき場合は True
    """
    if not isinstance(text, str) or not text.strip():
        return False

    # リスクの高い用語が含まれる場合は手動確認を要求
    if AUTO_CONFIRM_BLOCK_RISKY:
        lowered = text.lower()
        if any(term in lowered for term in RISKY_CONFIRM_TERMS):
            return False

    prompt = (
        "You are a classifier. Decide whether the assistant message is asking the user "
        "for permission/confirmation to proceed with the next step in a computer automation task. "
        "If it asks for confirmation (yes/no), answer YES. Otherwise answer NO.\n\n"
        "Rules:\n"
        "- Answer EXACTLY one token: YES or NO.\n"
        "- Treat Japanese questions like '開きますか？/よろしいですか？/進めてもいいですか？' as YES.\n"
        "- If it's just status reporting or instructions without asking permission, answer NO.\n"
    )

    try:
        if CONFIRM_INTERPRETER_MODEL is None:
            raise RuntimeError(
                "CONFIRM_INTERPRETER_MODEL is not set. Set AZURE_OPENAI_MODEL_CONFIRM in .env or disable USE_CONFIRM_INTERPRETER_MODEL."
            )
        r = responses_create_with_retry(
            model=CONFIRM_INTERPRETER_MODEL,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text[:4000]},
            ],
            max_output_tokens=32,
            truncation="auto",
        )
        out = "\n".join(iter_output_texts(getattr(r, "output", []) or []))
        out = (out or "").strip().upper()
        # 余分な空白や改行を許容
        first = out.split()[0] if out else ""
        return first == "YES"
    except Exception as e:
        print(f"[confirm-interpreter] failed; falling back to heuristic: {e}")
        return _looks_like_confirmation_request_heuristic(text)


def _classify_file_operation_confirmation(text: str) -> str:
    """確認要求の文面を分類します。

    Returns:
        "none" / "save_as" / "overwrite" / "delete" / "mixed"

    NOTE: 自律実行の安全性のため、誤検知は安全側に倒します。
    """
    if not isinstance(text, str) or not text.strip():
        return "none"

    lowered = text.lower()

    file_context_terms = (
        "file",
        "folder",
        "directory",
        "path",
        "document",
        "ファイル",
        "フォルダ",
        "ディレクトリ",
        "パス",
        "ドキュメント",
        "保存",
    )
    has_file_context = any(t in lowered for t in file_context_terms)

    save_as_terms = (
        "別名保存",
        "名前を付けて保存",
        "名前をつけて保存",
        "save as",
        "save a copy",
        "save a new copy",
        "save copy",
        "save new copy",
        "save as new",
    )

    overwrite_terms_strong = (
        "上書き",
        "上書き保存",
        "置き換え",
        "overwrite",
        "overwrite existing",
        "replace existing",
        "replace the existing",
    )

    delete_terms_strong = (
        "削除",
        "消去",
        "ゴミ箱",
        "delete",
        "unlink",
        "erase",
        "rm ",
        "rmdir",
        "del ",
    )

    # 英語の "remove" は汎用すぎるので、ファイル文脈がある時だけ削除扱い
    delete_terms_soft = ("remove", "remove it", "remove the")

    save_as_hit = any(term in lowered for term in save_as_terms)

    overwrite_hit = any(term in lowered for term in overwrite_terms_strong)
    if overwrite_hit and not has_file_context:
        # 置換など一般文脈の誤検知を減らす
        overwrite_hit = any(
            term in lowered for term in ("上書き", "上書き保存", "overwrite")
        )

    delete_hit = any(term in lowered for term in delete_terms_strong)
    if not delete_hit and has_file_context:
        delete_hit = any(term in lowered for term in delete_terms_soft)

    if save_as_hit and (overwrite_hit or delete_hit):
        return "mixed"
    if delete_hit:
        return "delete"
    if overwrite_hit:
        return "overwrite"
    if save_as_hit:
        return "save_as"
    return "none"


def get_or_confirm_computer_call(r):
    """
    レスポンスからコンピューターコールを取得するか、必要に応じて確認を送信します。

    レスポンスにコンピューターコールが含まれていない場合、
    メッセージが確認要求かどうかを判定し、必要に応じて自動確認を送信します。

    Args:
        r: APIレスポンス

    Returns:
        (レスポンス, コンピューターコール) のタプル
        コンピューターコールがない場合は (レスポンス, None)

    Raises:
        RuntimeError: COMPUTER_USE_MODEL が設定されていない場合
    """
    computer_call = get_first_computer_call(r.output)
    if computer_call is not None:
        return r, computer_call

    # 自動確認が無効の場合はそのまま返す
    if not AUTO_CONFIRM:
        return r, None

    # 確認要求かどうかを判定
    output_texts = "\n".join(iter_output_texts(r.output))
    needs_confirm = (
        _should_auto_confirm_via_interpreter(output_texts)
        if USE_CONFIRM_INTERPRETER_MODEL
        else _looks_like_confirmation_request_heuristic(output_texts)
    )
    if not needs_confirm:
        return r, None

    # ファイル操作（上書き/削除）は拒否、別名保存は許可（別名保存を明示指定）
    file_op = _classify_file_operation_confirmation(output_texts)
    if file_op in ("delete", "overwrite", "save_as", "mixed"):
        if COMPUTER_USE_MODEL is None:
            raise RuntimeError(
                "COMPUTER_USE_MODEL is not set. Set AZURE_OPENAI_MODEL_COMPUTER_USE in .env."
            )

        if file_op == "delete":
            message = "いいえ。ファイルの削除は行えません。削除しない代替手順で進めてください。"
            kind = "auto_deny"
            detail = "refused: delete"
        elif file_op == "overwrite":
            message = "いいえ。ファイルの上書き保存は行えません。別名保存（名前を付けて保存）で進めてください。"
            kind = "auto_deny"
            detail = "refused: overwrite"
        else:
            # save_as / mixed は安全側に「別名保存」を明示して続行
            message = (
                "別名保存（名前を付けて保存 / Save As）で進めてください。"
                "上書き保存やファイル削除はしないでください。"
            )
            kind = "auto_confirm"
            detail = f"directed: {file_op}"

        r2 = responses_create_with_retry(
            model=COMPUTER_USE_MODEL,
            previous_response_id=r.id,
            tools=make_tools("windows"),
            input=[{"role": "user", "content": message}],
            truncation="auto",
        )
        log_session_event(step=-1, kind=kind, detail=detail)
        print(r2.output)
        return r2, get_first_computer_call(r2.output)

    # 自動確認メッセージを送信
    if COMPUTER_USE_MODEL is None:
        raise RuntimeError(
            "COMPUTER_USE_MODEL is not set. Set AZURE_OPENAI_MODEL_COMPUTER_USE in .env."
        )
    r2 = responses_create_with_retry(
        model=COMPUTER_USE_MODEL,
        previous_response_id=r.id,
        tools=make_tools("windows"),
        input=[{"role": "user", "content": CONFIRM_MESSAGE}],
        truncation="auto",
    )
    log_session_event(step=-1, kind="auto_confirm", detail=f"sent: {CONFIRM_MESSAGE}")
    print(r2.output)
    return r2, get_first_computer_call(r2.output)
