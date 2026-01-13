import base64
import mimetypes
from pathlib import Path
import sys
from datetime import datetime
import time
import random
import re
import argparse

import os
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI
from openai import APIConnectionError, APIStatusError, BadRequestError, RateLimitError
from PIL import Image, ImageDraw, ImageGrab
import pyautogui

try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    load_dotenv = None


pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


# Load env vars from .env (do not commit .env to GitHub)
if load_dotenv is not None:
    load_dotenv()


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None:
        return default
    v = str(v).strip()
    return v if v else default


def _require_env(name: str) -> str:
    v = _env(name)
    if v is None:
        raise RuntimeError(
            f"Missing required env var: {name}. "
            "Create a .env file (see .env.example) or set it in your environment."
        )
    return v


def _build_azure_openai_base_url() -> str:
    base_url = _env("AZURE_OPENAI_BASE_URL")
    if base_url:
        # Accept either with or without trailing slash.
        return base_url.rstrip("/") + "/"

    endpoint = _env("AZURE_OPENAI_ENDPOINT")
    if endpoint:
        # Endpoint form: https://<resource>.openai.azure.com
        return endpoint.rstrip("/") + "/openai/v1/"

    resource = _env("AZURE_OPENAI_RESOURCE_NAME")
    if resource:
        # Resource name form: <resource>
        return f"https://{resource}.openai.azure.com/openai/v1/"

    raise RuntimeError(
        "Missing Azure OpenAI endpoint. Set AZURE_OPENAI_ENDPOINT (recommended) or AZURE_OPENAI_BASE_URL in .env."
    )


# Runtime-initialized globals (filled by _init_runtime_from_env in main)
client: OpenAI | None = None
COMPUTER_USE_MODEL: str | None = None
SESSION_SUMMARY_MODEL: str | None = None
CONFIRM_INTERPRETER_MODEL: str | None = None


# Evidence settings
EVIDENCE_BEFORE_AFTER_FOR_INPUT = True
SHOW_TYPED_TEXT_IN_ANNOTATION = (
    False  # If True, may capture sensitive text into screenshots
)
ANNOTATION_MAX_CHARS = 60
# Model input image policy
SEND_ANNOTATED_IMAGE_TO_MODEL = False

# Debug snapshot settings
SAVE_MODEL_RESPONSE_DEBUG_IMAGE = True
DEBUG_NOTE_MAX_CHARS = 4000

# Debug note policy:
# - Image: short summary (kept small for readability)
# - Text file: full note (can be much larger)
DEBUG_NOTE_IMAGE_MAX_CHARS = 800
DEBUG_TEXT_FILE_MAX_CHARS = 200000


# Always-on instruction template for Japanese IME stability
IME_GUIDANCE_TEMPLATE = """あなたはWindows環境を操作します。日本語IMEのON/OFFミスを避けるため、文字入力(type/keypressで入力に影響する操作)の前には必ず以下を守ってください。

1) 入力先をクリックしてフォーカスを確実にする（カーソル点滅/入力枠の強調を確認）。
2) タスクバー等のIME表示（例: A/あ）を目視で確認する。
3) 期待する状態でない場合のみIMEを切り替える（半角/全角など）。
4) 必要なら短いテスト入力で確認してから本入力を行う。
5) 不確実な場合は推測で続行せず、スクリーンショットを要求して状況確認する。
6) ひとつのテキストボックスに対する入力で、日本語、英語の切り替えを行う際には、切り替えごとにスクリーンショットとってモデルに確認を求める。

重要: 1回の切替で決め打ちしない。必ず表示を再確認する。
"""


# API retry settings
MAX_API_RETRIES = 8
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 30.0

# Safety check handling
# If True, automatically acknowledges safety checks (not recommended for unattended runs).
AUTO_ACK_SAFETY_CHECKS = False


def _get_retry_after_seconds(err: Exception) -> float | None:
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
    """Extracts safety check ids from the server error message.

    Example message:
      Computer tool has unacknowledged safety check for ['cu_sc_...']
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

    # Capture quoted ids inside [...]
    ids = re.findall(r"'([^']+)'", message)
    return [i for i in ids if isinstance(i, str) and i.startswith("cu_sc_")]


def _confirm_ack_safety_checks(ids: list[str]) -> bool:
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
    """Attach acknowledged safety checks to any computer_call_output items in input."""

    if not ids:
        return input_param

    # input can be a string or list of items; we only handle list-style inputs.
    if not isinstance(input_param, list):
        return input_param
    acknowledged = [{"id": sid} for sid in ids]
    updated: list = []
    for item in input_param:
        if isinstance(item, dict) and item.get("type") == "computer_call_output":
            # Don't overwrite if caller already provided acknowledgement.
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
    if client is None:
        raise RuntimeError(
            "OpenAI client is not initialized. Ensure _init_runtime_from_env() is called before API requests."
        )
    last_err: Exception | None = None

    for attempt in range(0, MAX_API_RETRIES + 1):
        try:
            return client.responses.create(**kwargs)
        except BadRequestError as e:
            # Azure/OpenAI computer-use tool can require an explicit acknowledgement
            # before continuing. If we get a 400 for unacknowledged safety checks,
            # retry the exact same request with acknowledged_safety_checks attached to
            # the computer_call_output input item.
            last_err = e
            ids = _extract_unacknowledged_safety_check_ids(e)
            if not ids:
                raise

            if not _confirm_ack_safety_checks(ids):
                raise

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


def choose_model_image(clean: Path, annotated: Path | None = None) -> Path:
    if SEND_ANNOTATED_IMAGE_TO_MODEL and annotated is not None:
        return annotated
    return clean


def _summarize_action_for_debug(action) -> str:
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
        return f"action: type text_len={ln}"

    if action_type == "keypress":
        keys = getattr(action, "keys", None)
        return (
            _summarize_keypress(keys) if isinstance(keys, list) else "action: keypress"
        )

    if action_type == "wait":
        duration_ms = getattr(action, "duration_ms", None)
        return f"action: wait duration_ms={duration_ms}"

    if action_type == "screenshot":
        return "action: screenshot"

    return f"action: {action_type}"


def _build_debug_note(*, step: int, response_obj) -> str:
    rid = getattr(response_obj, "id", None)
    texts = _iter_output_texts(getattr(response_obj, "output", []) or [])
    msg = "\n".join(t.strip() for t in texts if isinstance(t, str) and t.strip())

    next_call = get_first_computer_call(getattr(response_obj, "output", []) or [])
    next_action = getattr(next_call, "action", None) if next_call is not None else None
    action_line = _summarize_action_for_debug(next_action)

    note = f"step={step}\nresponse_id={rid}\n{action_line}"
    if msg:
        note += "\nmessage:\n" + msg

    if len(note) > DEBUG_NOTE_MAX_CHARS:
        note = note[:DEBUG_NOTE_MAX_CHARS] + "…"
    return note


def _build_debug_note_summary(*, step: int, response_obj) -> str:
    """Short note for overlaying on the debug image."""

    full = _build_debug_note(step=step, response_obj=response_obj)
    # Keep only the header + a shortened message block.
    # This makes the image readable while the full text is written separately.
    if len(full) <= DEBUG_NOTE_IMAGE_MAX_CHARS:
        return full
    return full[:DEBUG_NOTE_IMAGE_MAX_CHARS] + "…"


def _write_debug_text_file(*, image_path: Path, step: int, response_obj) -> Path:
    txt_path = image_path.with_name(f"{image_path.stem}_Debug.txt")
    note = _build_debug_note(step=step, response_obj=response_obj)
    if len(note) > DEBUG_TEXT_FILE_MAX_CHARS:
        note = note[:DEBUG_TEXT_FILE_MAX_CHARS] + "…"
    txt_path.write_text(note, encoding="utf-8")
    return txt_path


def save_model_debug_image(
    *, sent_image_path: Path, step: int, response_obj
) -> Path | None:
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


def image_file_to_data_url(
    image_path: os.PathLike | str, *, default_mime: str = "image/png"
) -> str:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")

    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type:
        mime_type = default_mime

    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _iter_computer_calls(response_output: list) -> list:
    return [
        item
        for item in response_output
        if getattr(item, "type", None) == "computer_call"
    ]


def get_first_computer_call(response_output: list):
    calls = _iter_computer_calls(response_output)
    return calls[0] if calls else None


def _iter_output_texts(response_output: list) -> list[str]:
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


def extract_click_points(response_output: list) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for call in _iter_computer_calls(response_output):
        action = getattr(call, "action", None)
        if getattr(action, "type", None) != "click":
            continue

        x = getattr(action, "x", None)
        y = getattr(action, "y", None)
        if isinstance(x, int) and isinstance(y, int):
            points.append((x, y))

    return points


def annotate_click_points(
    image_path: os.PathLike | str,
    points: list[tuple[int, int]],
    *,
    output_path: os.PathLike | str | None = None,
    display_width: int | None = None,
    display_height: int | None = None,
) -> Path:
    src = Path(image_path)
    if output_path is None:
        output_path = src.with_name(f"{src.stem}R{src.suffix}")
    dst = Path(output_path)

    with Image.open(src) as img:
        img = img.convert("RGBA")
        draw = ImageDraw.Draw(img)

        scale_x = img.width / display_width if display_width else 1.0
        scale_y = img.height / display_height if display_height else 1.0

        for x, y in points:
            px = int(round(x * scale_x))
            py = int(round(y * scale_y))

            r = max(10, int(min(img.width, img.height) * 0.012))
            draw.ellipse(
                (px - r, py - r, px + r, py + r), outline=(255, 0, 0, 255), width=5
            )
            draw.line((px - r * 2, py, px + r * 2, py), fill=(255, 0, 0, 255), width=3)
            draw.line((px, py - r * 2, px, py + r * 2), fill=(255, 0, 0, 255), width=3)

        img.save(dst)

    return dst


def _summarize_typed_text(text: str) -> str:
    if not SHOW_TYPED_TEXT_IN_ANNOTATION:
        return f"type: {len(text)} chars"

    compact = text.replace("\r\n", "\n").replace("\r", "\n")
    compact = compact.replace("\n", "\\n")
    if len(compact) > ANNOTATION_MAX_CHARS:
        compact = compact[:ANNOTATION_MAX_CHARS] + "…"
    return f"type: '{compact}'"


def _summarize_keypress(keys: list[str]) -> str:
    norm = [_normalize_key_name(k) for k in keys if isinstance(k, str) and k.strip()]
    if not norm:
        return "keypress: (empty)"
    joined = "+".join(norm)
    if len(joined) > ANNOTATION_MAX_CHARS:
        joined = joined[:ANNOTATION_MAX_CHARS] + "…"
    return f"keypress: {joined}"


def annotate_text(
    image_path: os.PathLike | str,
    note: str,
    *,
    output_path: os.PathLike | str | None = None,
) -> Path:
    src = Path(image_path)
    if output_path is None:
        output_path = src.with_name(f"{src.stem}N{src.suffix}")
    dst = Path(output_path)

    with Image.open(src) as img:
        img = img.convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        text = note.strip()
        if not text:
            img.save(dst)
            return dst

        margin = max(10, int(min(img.width, img.height) * 0.01))
        pad = max(8, int(min(img.width, img.height) * 0.008))

        bbox = draw.multiline_textbbox((0, 0), text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x0 = margin
        y0 = margin
        x1 = min(img.width - margin, x0 + tw + pad * 2)
        y1 = min(img.height - margin, y0 + th + pad * 2)

        draw.rectangle((x0, y0, x1, y1), fill=(0, 0, 0, 170))
        draw.multiline_text((x0 + pad, y0 + pad), text, fill=(255, 255, 255, 255))

        composed = Image.alpha_composite(img, overlay)
        composed.save(dst)

    return dst


def capture_fullscreen_screenshot(*, screenshots_dir: os.PathLike | str) -> Path:
    out_dir = Path(screenshots_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # YYYYmmdd_HHMMSS_mmm.png
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    out_path = out_dir / f"{ts}.png"

    # Primary screen capture. (all_screens=True can create a virtual screen image that
    # doesn't map cleanly to click coordinates depending on multi-monitor layouts.)
    img = ImageGrab.grab()
    img.save(out_path)
    return out_path


def _get_primary_screen_size() -> tuple[int, int]:
    img = ImageGrab.grab()
    return img.size


def scale_point(
    x: int,
    y: int,
    *,
    from_width: int,
    from_height: int,
    to_width: int,
    to_height: int,
) -> tuple[int, int]:
    sx = to_width / from_width
    sy = to_height / from_height
    return int(round(x * sx)), int(round(y * sy))


def perform_click(
    x: int,
    y: int,
    *,
    display_width: int,
    display_height: int,
    button: str | None = None,
) -> tuple[int, int]:
    screen_w, screen_h = _get_primary_screen_size()
    px, py = scale_point(
        x,
        y,
        from_width=display_width,
        from_height=display_height,
        to_width=screen_w,
        to_height=screen_h,
    )
    pyautogui.click(px, py, button=_normalize_mouse_button(button))
    return px, py


def _normalize_key_name(key: str) -> str:
    k = key.strip().lower()
    aliases = {
        "control": "ctrl",
        "ctl": "ctrl",
        "escape": "esc",
        "esc": "esc",
        "return": "enter",
        "windows": "win",
        "command": "win",
        "option": "alt",
        "pageup": "pageup",
        "pagedown": "pagedown",
        "pgup": "pageup",
        "pgdn": "pagedown",
        "backspace": "backspace",
        "delete": "delete",
        "del": "delete",
    }
    return aliases.get(k, k)


def _normalize_mouse_button(button: str | None) -> str:
    if not isinstance(button, str) or not button:
        return "left"

    b = button.strip().lower()
    aliases = {
        "left": "left",
        "right": "right",
        "middle": "middle",
        # Best-effort fallbacks for values that pyautogui may not support directly.
        "wheel": "middle",
        "back": "left",
        "forward": "left",
    }
    return aliases.get(b, "left")


def perform_double_click(
    x: int,
    y: int,
    *,
    display_width: int,
    display_height: int,
    button: str | None = None,
) -> tuple[int, int]:
    screen_w, screen_h = _get_primary_screen_size()
    px, py = scale_point(
        x,
        y,
        from_width=display_width,
        from_height=display_height,
        to_width=screen_w,
        to_height=screen_h,
    )
    pyautogui.doubleClick(px, py, button=_normalize_mouse_button(button))
    return px, py


def perform_move(
    x: int,
    y: int,
    *,
    display_width: int,
    display_height: int,
    duration: float = 0.0,
) -> tuple[int, int]:
    screen_w, screen_h = _get_primary_screen_size()
    px, py = scale_point(
        x,
        y,
        from_width=display_width,
        from_height=display_height,
        to_width=screen_w,
        to_height=screen_h,
    )
    pyautogui.moveTo(px, py, duration=duration)
    return px, py


def perform_drag(
    path: list[dict],
    *,
    display_width: int,
    display_height: int,
    duration: float = 0.2,
    button: str | None = None,
) -> tuple[int, int]:
    if not path:
        raise ValueError("drag.path is empty")

    points: list[tuple[int, int]] = []
    for p in path:
        if isinstance(p, dict):
            x = p.get("x")
            y = p.get("y")
        else:
            x = getattr(p, "x", None)
            y = getattr(p, "y", None)
        if isinstance(x, int) and isinstance(y, int):
            points.append((x, y))

    if len(points) < 2:
        raise ValueError("drag.path must contain at least 2 points")

    screen_w, screen_h = _get_primary_screen_size()
    scaled = [
        scale_point(
            x,
            y,
            from_width=display_width,
            from_height=display_height,
            to_width=screen_w,
            to_height=screen_h,
        )
        for x, y in points
    ]

    (start_x, start_y) = scaled[0]
    pyautogui.moveTo(start_x, start_y)
    pyautogui.mouseDown(button=_normalize_mouse_button(button))

    per_step = duration / max(1, (len(scaled) - 1))
    last_x, last_y = start_x, start_y
    for px, py in scaled[1:]:
        pyautogui.moveTo(px, py, duration=per_step)
        last_x, last_y = px, py

    pyautogui.mouseUp(button=_normalize_mouse_button(button))
    return last_x, last_y


def perform_scroll(
    x: int,
    y: int,
    *,
    display_width: int,
    display_height: int,
    scroll_x: int = 0,
    scroll_y: int = 0,
) -> tuple[int, int]:
    px, py = perform_move(
        x, y, display_width=display_width, display_height=display_height
    )
    if isinstance(scroll_y, int) and scroll_y:
        pyautogui.scroll(scroll_y)
    if isinstance(scroll_x, int) and scroll_x:
        pyautogui.hscroll(scroll_x)
    return px, py


def perform_type(text: str, *, interval: float = 0.0) -> None:
    if not isinstance(text, str):
        raise ValueError("type.text must be a string")
    if not text:
        return
    pyautogui.write(text, interval=interval)


def perform_wait(duration_ms: int | None = None) -> None:
    if isinstance(duration_ms, int) and duration_ms > 0:
        time.sleep(duration_ms / 1000)
    else:
        time.sleep(1.0)


def perform_keypress(keys: list[str]) -> None:
    norm = [_normalize_key_name(k) for k in keys if isinstance(k, str) and k.strip()]
    if not norm:
        raise ValueError("No keys provided for keypress")
    if len(norm) == 1:
        pyautogui.press(norm[0])
    else:
        pyautogui.hotkey(*norm)


def _init_openai_client_from_env() -> None:
    global client
    base_url = _build_azure_openai_base_url()
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    client = OpenAI(base_url=base_url, api_key=token_provider)


SCRIPT_DIR = Path(__file__).resolve().parent
DISPLAY_WIDTH = 2560
DISPLAY_HEIGHT = 1600
SCREENSHOTS_DIR = SCRIPT_DIR / "screenshots"
MAX_STEPS = 30
AUTO_CONFIRM = True
CONFIRM_MESSAGE = "はい、進めてください。"

# Session summary settings
ENABLE_SESSION_SUMMARY = True
SESSION_SUMMARY_MODEL = None
SESSION_SUMMARY_MAX_OUTPUT_TOKENS = 256

# If True, logs the actual typed text into the session summary file.
# WARNING: This may record sensitive data.
LOG_TYPED_TEXT_IN_SESSION_SUMMARY = False
SESSION_SUMMARY_TYPED_TEXT_MAX_CHARS = 200

_SESSION_START_DT = datetime.now()
_SESSION_START_STAMP = _SESSION_START_DT.strftime("%Y%m%d_%H%M%S")
SESSION_SUMMARY_PATH = SCRIPT_DIR / f"{_SESSION_START_STAMP}-sessionsummary.txt"

# Optional: use a lightweight model to decide whether a message is asking for
# user confirmation (Japanese/English), and auto-approve it when AUTO_CONFIRM is on.
USE_CONFIRM_INTERPRETER_MODEL = True
CONFIRM_INTERPRETER_MODEL = None

# Safety guardrail for auto-confirm: if the confirmation is about risky actions,
# require manual confirmation instead.
AUTO_CONFIRM_BLOCK_RISKY = True
_RISKY_CONFIRM_TERMS = (
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


def _looks_like_confirmation_request_heuristic(text: str) -> bool:
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
    if not isinstance(text, str) or not text.strip():
        return False

    if AUTO_CONFIRM_BLOCK_RISKY:
        lowered = text.lower()
        if any(term in lowered for term in _RISKY_CONFIRM_TERMS):
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
        out = "\n".join(_iter_output_texts(getattr(r, "output", []) or []))
        out = (out or "").strip().upper()
        # Be tolerant to extra whitespace/newlines.
        first = out.split()[0] if out else ""
        return first == "YES"
    except Exception as e:
        print(f"[confirm-interpreter] failed; falling back to heuristic: {e}")
        return _looks_like_confirmation_request_heuristic(text)


def _append_session_summary_line(line: str) -> None:
    if not ENABLE_SESSION_SUMMARY:
        return
    SESSION_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SESSION_SUMMARY_PATH.open("a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")


def _ensure_session_summary_header() -> None:
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


def _summarize_text_with_nano_for_session(text: str) -> str:
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
    out = "\n".join(_iter_output_texts(getattr(r, "output", []) or []))
    out = (out or "").strip()
    return out or "(empty summary)"


def _format_typed_text_for_session(text: str) -> str:
    """Formats typed text for safe single-line-ish logging."""

    compact = text.replace("\r\n", "\n").replace("\r", "\n")
    compact = compact.replace("\n", "\\n")
    if len(compact) > SESSION_SUMMARY_TYPED_TEXT_MAX_CHARS:
        compact = compact[:SESSION_SUMMARY_TYPED_TEXT_MAX_CHARS] + "…"
    return compact


def log_session_event(*, step: int, kind: str, detail: str) -> None:
    if not ENABLE_SESSION_SUMMARY:
        return
    _ensure_session_summary_header()
    ts = datetime.now().isoformat(timespec="seconds")
    _append_session_summary_line(f"[{ts}] step={step} kind={kind}\n{detail}\n")


def log_model_response_summary(*, step: int, response_obj) -> None:
    if not ENABLE_SESSION_SUMMARY:
        return

    rid = getattr(response_obj, "id", None)
    texts = _iter_output_texts(getattr(response_obj, "output", []) or [])
    msg = "\n".join(t.strip() for t in texts if isinstance(t, str) and t.strip())

    next_call = get_first_computer_call(getattr(response_obj, "output", []) or [])
    next_action = getattr(next_call, "action", None) if next_call is not None else None
    action_line = _summarize_action_for_debug(next_action)

    raw = f"response_id={rid}\n{action_line}"
    if msg:
        raw += "\nmessage:\n" + msg

    try:
        summary = _summarize_text_with_nano_for_session(raw)
    except Exception as e:
        summary = f"(summary_failed: {e})"

    log_session_event(step=step, kind="model_summary", detail=summary)


def make_tools(environment: str) -> list[dict]:
    return [
        {
            "type": "computer_use_preview",
            "display_width": DISPLAY_WIDTH,
            "display_height": DISPLAY_HEIGHT,
            "environment": environment,
        }
    ]


def get_or_confirm_computer_call(r):
    """Returns (response_with_call, computer_call) or (response, None)."""
    computer_call = get_first_computer_call(r.output)
    if computer_call is not None:
        return r, computer_call

    if not AUTO_CONFIRM:
        return r, None

    output_texts = "\n".join(_iter_output_texts(r.output))
    needs_confirm = (
        _should_auto_confirm_via_interpreter(output_texts)
        if USE_CONFIRM_INTERPRETER_MODEL
        else _looks_like_confirmation_request_heuristic(output_texts)
    )
    if not needs_confirm:
        return r, None

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


def _init_runtime_from_env() -> None:
    global COMPUTER_USE_MODEL, SESSION_SUMMARY_MODEL, CONFIRM_INTERPRETER_MODEL

    COMPUTER_USE_MODEL = _require_env("AZURE_OPENAI_MODEL_COMPUTER_USE")
    if ENABLE_SESSION_SUMMARY:
        SESSION_SUMMARY_MODEL = _require_env("AZURE_OPENAI_MODEL_SUMMARY")
    if USE_CONFIRM_INTERPRETER_MODEL:
        CONFIRM_INTERPRETER_MODEL = _require_env("AZURE_OPENAI_MODEL_CONFIRM")

    _init_openai_client_from_env()


def _build_initial_user_instruction(
    *, recipient: str, message: str, app_name: str
) -> str:
    return f"{app_name} で {recipient} さんに、「{message}」とチャットメッセージを送ってください。"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Azure OpenAI computer-use runner")
    parser.add_argument(
        "--recipient",
        default=_env("TARGET_RECIPIENT"),
        help="Chat recipient (e.g. display name). You can also set TARGET_RECIPIENT in .env",
    )
    parser.add_argument(
        "--message",
        default=_env("TARGET_MESSAGE"),
        help="Message to send. You can also set TARGET_MESSAGE in .env",
    )
    parser.add_argument(
        "--app",
        default=_env("TARGET_APP", "Microsoft Teams"),
        help="Target app name (default: Microsoft Teams). You can also set TARGET_APP in .env",
    )
    args = parser.parse_args(argv)

    if not args.recipient:
        raise RuntimeError(
            "Missing recipient. Set TARGET_RECIPIENT in .env or pass --recipient."
        )
    if not args.message:
        raise RuntimeError(
            "Missing message. Set TARGET_MESSAGE in .env or pass --message."
        )

    _init_runtime_from_env()
    if COMPUTER_USE_MODEL is None:
        raise RuntimeError("COMPUTER_USE_MODEL is not set (unexpected).")

    user_instruction = _build_initial_user_instruction(
        recipient=str(args.recipient),
        message=str(args.message),
        app_name=str(args.app),
    )

    response = responses_create_with_retry(
        model=COMPUTER_USE_MODEL,
        tools=make_tools("windows"),
        input=[
            {"role": "system", "content": IME_GUIDANCE_TEMPLATE},
            {"role": "user", "content": user_instruction},
        ],
        truncation="auto",
    )

    print(response.output)
    log_model_response_summary(step=0, response_obj=response)

    for step in range(1, MAX_STEPS + 1):
        response, computer_call = get_or_confirm_computer_call(response)
        if computer_call is None:
            print("No computer call found; stopping.")
            break

        last_call_id = computer_call.call_id
        action = computer_call.action
        action_type = getattr(action, "type", None)

        screenshot_path: Path | None = None

        if action_type == "screenshot":
            screenshot_path = capture_fullscreen_screenshot(
                screenshots_dir=SCREENSHOTS_DIR
            )
            print(f"[{step}] Captured screenshot: {screenshot_path}")
            log_session_event(step=step, kind="action", detail="screenshot")

        elif action_type == "click":
            x = getattr(action, "x", None)
            y = getattr(action, "y", None)
            button = getattr(action, "button", None)
            if not isinstance(x, int) or not isinstance(y, int):
                print(f"[{step}] Invalid click coordinates: x={x} y={y}")
                break

            px, py = perform_click(
                x,
                y,
                display_width=DISPLAY_WIDTH,
                display_height=DISPLAY_HEIGHT,
                button=button,
            )
            if isinstance(button, str) and button:
                print(
                    f"[{step}] Clicked ({button}): model=({x},{y}) -> screen=({px},{py})"
                )
            else:
                print(f"[{step}] Clicked: model=({x},{y}) -> screen=({px},{py})")
            log_session_event(
                step=step,
                kind="action",
                detail=f"click button={button} model=({x},{y}) screen=({px},{py})",
            )
            time.sleep(0.2)

            screenshot_path = capture_fullscreen_screenshot(
                screenshots_dir=SCREENSHOTS_DIR
            )
            annotated_path = annotate_click_points(
                screenshot_path,
                [(x, y)],
                display_width=DISPLAY_WIDTH,
                display_height=DISPLAY_HEIGHT,
            )
            print(f"[{step}] Annotated screenshot saved: {annotated_path}")
            screenshot_path = choose_model_image(screenshot_path, annotated_path)

        elif action_type == "double_click":
            x = getattr(action, "x", None)
            y = getattr(action, "y", None)
            if not isinstance(x, int) or not isinstance(y, int):
                print(f"[{step}] Invalid double_click coordinates: x={x} y={y}")
                break

            px, py = perform_double_click(
                x, y, display_width=DISPLAY_WIDTH, display_height=DISPLAY_HEIGHT
            )
            print(f"[{step}] Double-clicked: model=({x},{y}) -> screen=({px},{py})")
            log_session_event(
                step=step,
                kind="action",
                detail=f"double_click model=({x},{y}) screen=({px},{py})",
            )
            time.sleep(0.2)

            screenshot_path = capture_fullscreen_screenshot(
                screenshots_dir=SCREENSHOTS_DIR
            )
            annotated_path = annotate_click_points(
                screenshot_path,
                [(x, y)],
                display_width=DISPLAY_WIDTH,
                display_height=DISPLAY_HEIGHT,
            )
            print(f"[{step}] Annotated screenshot saved: {annotated_path}")
            screenshot_path = choose_model_image(screenshot_path, annotated_path)

        elif action_type == "move":
            x = getattr(action, "x", None)
            y = getattr(action, "y", None)
            if not isinstance(x, int) or not isinstance(y, int):
                print(f"[{step}] Invalid move coordinates: x={x} y={y}")
                break

            px, py = perform_move(
                x, y, display_width=DISPLAY_WIDTH, display_height=DISPLAY_HEIGHT
            )
            print(f"[{step}] Moved: model=({x},{y}) -> screen=({px},{py})")
            log_session_event(
                step=step,
                kind="action",
                detail=f"move model=({x},{y}) screen=({px},{py})",
            )
            time.sleep(0.1)

            screenshot_path = capture_fullscreen_screenshot(
                screenshots_dir=SCREENSHOTS_DIR
            )
            print(f"[{step}] Captured screenshot: {screenshot_path}")

        elif action_type == "drag":
            path = getattr(action, "path", None)
            if not isinstance(path, list) or not path:
                print(f"[{step}] Invalid drag path: {path}")
                break

            px, py = perform_drag(
                path, display_width=DISPLAY_WIDTH, display_height=DISPLAY_HEIGHT
            )
            print(f"[{step}] Dragged; ended at screen=({px},{py})")
            log_session_event(
                step=step, kind="action", detail=f"drag ended_screen=({px},{py})"
            )
            time.sleep(0.2)

            screenshot_path = capture_fullscreen_screenshot(
                screenshots_dir=SCREENSHOTS_DIR
            )
            print(f"[{step}] Captured screenshot: {screenshot_path}")

        elif action_type == "scroll":
            x = getattr(action, "x", None)
            y = getattr(action, "y", None)
            scroll_x = getattr(action, "scroll_x", 0)
            scroll_y = getattr(action, "scroll_y", 0)
            if not isinstance(x, int) or not isinstance(y, int):
                print(f"[{step}] Invalid scroll coordinates: x={x} y={y}")
                break
            if not isinstance(scroll_x, int) or not isinstance(scroll_y, int):
                print(
                    f"[{step}] Invalid scroll values: scroll_x={scroll_x} scroll_y={scroll_y}"
                )
                break

            px, py = perform_scroll(
                x,
                y,
                display_width=DISPLAY_WIDTH,
                display_height=DISPLAY_HEIGHT,
                scroll_x=scroll_x,
                scroll_y=scroll_y,
            )
            print(f"[{step}] Scrolled at screen=({px},{py}) x={scroll_x} y={scroll_y}")
            log_session_event(
                step=step,
                kind="action",
                detail=f"scroll at_screen=({px},{py}) scroll_x={scroll_x} scroll_y={scroll_y}",
            )
            time.sleep(0.2)

            screenshot_path = capture_fullscreen_screenshot(
                screenshots_dir=SCREENSHOTS_DIR
            )
            print(f"[{step}] Captured screenshot: {screenshot_path}")

        elif action_type == "type":
            text = getattr(action, "text", None)
            if not isinstance(text, str):
                print(f"[{step}] Invalid type text: {text}")
                break

            before_path: Path | None = None
            if EVIDENCE_BEFORE_AFTER_FOR_INPUT:
                before_path = capture_fullscreen_screenshot(
                    screenshots_dir=SCREENSHOTS_DIR
                )
                print(f"[{step}] Evidence (before type): {before_path}")

            perform_type(text)
            print(f"[{step}] Typed {len(text)} chars")
            if LOG_TYPED_TEXT_IN_SESSION_SUMMARY:
                logged = _format_typed_text_for_session(text)
                log_session_event(
                    step=step,
                    kind="action",
                    detail=f"type chars={len(text)} text='{logged}'",
                )
            else:
                log_session_event(
                    step=step, kind="action", detail=f"type chars={len(text)}"
                )
            time.sleep(0.5)

            after_path = capture_fullscreen_screenshot(screenshots_dir=SCREENSHOTS_DIR)
            note = _summarize_typed_text(text)
            annotated_path = annotate_text(after_path, note)
            print(f"[{step}] Evidence (after type): {after_path}")
            print(f"[{step}] Evidence (after type, annotated): {annotated_path}")
            screenshot_path = choose_model_image(after_path, annotated_path)

        elif action_type == "wait":
            duration_ms = getattr(action, "duration_ms", None)
            perform_wait(duration_ms)
            print(f"[{step}] Waited: duration_ms={duration_ms}")
            log_session_event(
                step=step, kind="action", detail=f"wait duration_ms={duration_ms}"
            )

            screenshot_path = capture_fullscreen_screenshot(
                screenshots_dir=SCREENSHOTS_DIR
            )
            print(f"[{step}] Captured screenshot: {screenshot_path}")

        elif action_type == "keypress":
            keys = getattr(action, "keys", None)
            if not isinstance(keys, list) or not keys:
                print(f"[{step}] Invalid keypress keys: {keys}")
                break

            before_path: Path | None = None
            if EVIDENCE_BEFORE_AFTER_FOR_INPUT:
                before_path = capture_fullscreen_screenshot(
                    screenshots_dir=SCREENSHOTS_DIR
                )
                print(f"[{step}] Evidence (before keypress): {before_path}")

            perform_keypress(keys)
            print(f"[{step}] Keypress: {keys}")
            log_session_event(step=step, kind="action", detail=f"keypress keys={keys}")
            time.sleep(0.5)

            after_path = capture_fullscreen_screenshot(screenshots_dir=SCREENSHOTS_DIR)
            note = _summarize_keypress(keys)
            annotated_path = annotate_text(after_path, note)
            print(f"[{step}] Evidence (after keypress): {after_path}")
            print(f"[{step}] Evidence (after keypress, annotated): {annotated_path}")
            screenshot_path = choose_model_image(after_path, annotated_path)

        else:
            print(f"[{step}] Unsupported action type: {action_type}; stopping.")
            break

        sent_image_path = screenshot_path
        response = responses_create_with_retry(
            model=COMPUTER_USE_MODEL,
            previous_response_id=response.id,
            tools=make_tools("windows"),
            input=[
                {
                    "call_id": last_call_id,
                    "type": "computer_call_output",
                    "output": {
                        "type": "input_image",
                        "image_url": image_file_to_data_url(screenshot_path),
                    },
                }
            ],
            truncation="auto",
        )

        log_model_response_summary(step=step, response_obj=response)

        try:
            dbg_path = save_model_debug_image(
                sent_image_path=sent_image_path, step=step, response_obj=response
            )
            if dbg_path is not None:
                print(f"[{step}] Debug screenshot saved: {dbg_path}")
        except Exception as e:
            print(f"[{step}] Failed to save debug screenshot: {e}")

        print(response.output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
