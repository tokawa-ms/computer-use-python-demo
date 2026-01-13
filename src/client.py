"""
Azure OpenAI クライアントモジュール

Azure OpenAI APIとの通信を管理します。
リトライロジック、セーフティチェックの処理、レスポンス解析などを含みます。
"""

import random
import re
import time

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI
from openai import APIConnectionError, APIStatusError, BadRequestError, RateLimitError

from .config import (
    AUTO_ACK_SAFETY_CHECKS,
    INITIAL_BACKOFF_SECONDS,
    MAX_API_RETRIES,
    MAX_BACKOFF_SECONDS,
    _build_azure_openai_base_url,
)


# グローバルクライアントインスタンス（init_clientで初期化）
client: OpenAI | None = None


def init_client() -> None:
    """
    Azure OpenAI クライアントを初期化します。
    
    環境変数から設定を読み込み、Azure認証情報を使用してクライアントを作成します。
    """
    global client
    base_url = _build_azure_openai_base_url()
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    client = OpenAI(base_url=base_url, api_key=token_provider)


def _get_retry_after_seconds(err: Exception) -> float | None:
    """
    HTTPレスポンスからRetry-Afterヘッダーの値を取得します。
    
    Args:
        err: 例外オブジェクト
    
    Returns:
        Retry-After の秒数、取得できない場合は None
    """
    resp = getattr(err, "response", None)
    headers = getattr(resp, "headers", None)
    if not headers:
        headers = getattr(err, "headers", None)

    if not headers:
        return None

    ra = None
    try:
        ra = headers.get("retry-after") or headers.get("Retry-After")
    except Exception:
        ra = None

    if ra is None:
        return None

    try:
        return float(ra)
    except Exception:
        return None


def _extract_unacknowledged_safety_check_ids(err: Exception) -> list[str]:
    """
    サーバーエラーメッセージから未確認のセーフティチェックIDを抽出します。
    
    Args:
        err: 例外オブジェクト
    
    Returns:
        セーフティチェックIDのリスト
    """
    message = None
    try:
        message = getattr(err, "message", None)
    except Exception:
        message = None

    if not isinstance(message, str) or not message:
        message = str(err)

    if "unacknowledged safety check" not in message:
        return []

    # [...] 内の引用符で囲まれたIDを抽出
    ids = re.findall(r"'([^']+)'", message)
    return [i for i in ids if isinstance(i, str) and i.startswith("cu_sc_")]


def _confirm_ack_safety_checks(ids: list[str]) -> bool:
    """
    セーフティチェックの確認をユーザーに求めます。
    
    Args:
        ids: セーフティチェックIDのリスト
    
    Returns:
        確認された場合は True、それ以外は False
    """
    if not ids:
        return False
    if AUTO_ACK_SAFETY_CHECKS:
        return True

    print("\n[safety] Computer tool safety check requires acknowledgement.")
    for sid in ids:
        print(f"  - {sid}")
    ans = input("Acknowledge and continue? [y/N]: ").strip().lower()
    return ans in ("y", "yes")


def _add_acknowledged_safety_checks_to_input(input_param, ids: list[str]):
    """
    入力パラメータにセーフティチェックの確認情報を追加します。
    
    Args:
        input_param: 元の入力パラメータ
        ids: セーフティチェックIDのリスト
    
    Returns:
        確認情報が追加された入力パラメータ
    """
    if not ids:
        return input_param

    # 入力は文字列またはアイテムのリスト
    if not isinstance(input_param, list):
        return input_param
    
    acknowledged = [{"id": sid} for sid in ids]
    updated: list = []
    for item in input_param:
        if isinstance(item, dict) and item.get("type") == "computer_call_output":
            # 既に確認情報がある場合は上書きしない
            if "acknowledged_safety_checks" not in item:
                new_item = dict(item)
                new_item["acknowledged_safety_checks"] = acknowledged
                updated.append(new_item)
            else:
                updated.append(item)
        else:
            updated.append(item)
    return updated


def responses_create_with_retry(**kwargs):
    """
    リトライロジックを含むAPIリクエストを実行します。
    
    レート制限、接続エラー、サーバーエラー、セーフティチェックなどに対応して
    自動的にリトライします。
    
    Args:
        **kwargs: client.responses.create に渡すパラメータ
    
    Returns:
        APIレスポンス
    
    Raises:
        RuntimeError: クライアントが初期化されていない場合
        各種APIエラー: リトライ上限に達した場合
    """
    if client is None:
        raise RuntimeError(
            "OpenAI client is not initialized. Ensure init_client() is called before API requests."
        )
    last_err: Exception | None = None

    for attempt in range(0, MAX_API_RETRIES + 1):
        try:
            return client.responses.create(**kwargs)
        
        except BadRequestError as e:
            # Azure/OpenAI computer-use ツールは、継続前に明示的な確認を要求する場合があります
            last_err = e
            ids = _extract_unacknowledged_safety_check_ids(e)
            if not ids:
                raise

            if not _confirm_ack_safety_checks(ids):
                raise

            # 確認情報を追加してリトライ
            kwargs = dict(kwargs)
            kwargs["input"] = _add_acknowledged_safety_checks_to_input(
                kwargs.get("input"), ids
            )

            print(
                f"[safety] acknowledged {len(ids)} safety check(s); retrying request "
                f"(attempt {attempt + 1}/{MAX_API_RETRIES})"
            )
            continue
        
        except RateLimitError as e:
            # レート制限エラー: 指数バックオフでリトライ
            last_err = e
            if attempt >= MAX_API_RETRIES:
                raise

            retry_after = _get_retry_after_seconds(e)
            backoff = min(MAX_BACKOFF_SECONDS, INITIAL_BACKOFF_SECONDS * (2**attempt))
            jitter = random.uniform(0.0, min(1.0, backoff))
            sleep_s = retry_after if retry_after is not None else (backoff + jitter)
            sleep_s = max(0.5, min(MAX_BACKOFF_SECONDS, sleep_s))

            print(
                f"[rate-limit] 429 Too Many Requests; retrying in {sleep_s:.1f}s "
                f"(attempt {attempt + 1}/{MAX_API_RETRIES})"
            )
            time.sleep(sleep_s)

        except APIConnectionError as e:
            # 接続エラー: 指数バックオフでリトライ
            last_err = e
            if attempt >= MAX_API_RETRIES:
                raise
            backoff = min(MAX_BACKOFF_SECONDS, INITIAL_BACKOFF_SECONDS * (2**attempt))
            jitter = random.uniform(0.0, min(1.0, backoff))
            sleep_s = max(0.5, min(MAX_BACKOFF_SECONDS, backoff + jitter))
            print(
                f"[network] API connection error; retrying in {sleep_s:.1f}s "
                f"(attempt {attempt + 1}/{MAX_API_RETRIES})"
            )
            time.sleep(sleep_s)

        except APIStatusError as e:
            # サーバーエラー (5xx): リトライ
            last_err = e
            status = getattr(e, "status_code", None)
            if status not in (500, 502, 503, 504):
                raise
            if attempt >= MAX_API_RETRIES:
                raise

            backoff = min(MAX_BACKOFF_SECONDS, INITIAL_BACKOFF_SECONDS * (2**attempt))
            jitter = random.uniform(0.0, min(1.0, backoff))
            sleep_s = max(0.5, min(MAX_BACKOFF_SECONDS, backoff + jitter))
            print(
                f"[server] HTTP {status}; retrying in {sleep_s:.1f}s "
                f"(attempt {attempt + 1}/{MAX_API_RETRIES})"
            )
            time.sleep(sleep_s)

    if last_err is not None:
        raise last_err
    raise RuntimeError("responses_create_with_retry: failed without exception")


def get_first_computer_call(response_output: list):
    """
    レスポンスから最初のコンピューターコールを取得します。
    
    Args:
        response_output: APIレスポンスの出力リスト
    
    Returns:
        最初のコンピューターコール、存在しない場合は None
    """
    calls = [
        item
        for item in response_output
        if getattr(item, "type", None) == "computer_call"
    ]
    return calls[0] if calls else None


def iter_output_texts(response_output: list) -> list[str]:
    """
    レスポンスからテキスト出力を抽出します。
    
    Args:
        response_output: APIレスポンスの出力リスト
    
    Returns:
        テキスト出力のリスト
    """
    texts: list[str] = []
    for item in response_output:
        if getattr(item, "type", None) != "message":
            continue
        for content_item in getattr(item, "content", []) or []:
            if getattr(content_item, "type", None) == "output_text":
                text = getattr(content_item, "text", None)
                if isinstance(text, str) and text:
                    texts.append(text)
    return texts


def make_tools(environment: str) -> list[dict]:
    """
    コンピューター使用ツールの定義を作成します。
    
    Args:
        environment: 実行環境 ("windows", "linux", "macos")
    
    Returns:
        ツール定義のリスト
    """
    from .config import DISPLAY_WIDTH, DISPLAY_HEIGHT
    
    return [
        {
            "type": "computer_use_preview",
            "display_width": DISPLAY_WIDTH,
            "display_height": DISPLAY_HEIGHT,
            "environment": environment,
        }
    ]
