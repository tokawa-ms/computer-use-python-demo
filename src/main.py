"""
メインモジュール

Azure OpenAI computer-use の実行ロジックを統合します。
コマンドライン引数の処理、初期化、メインループの実行を担当します。
"""

import argparse
import shutil
import time
from pathlib import Path

from . import actions
from . import client
from . import confirmation
from . import debug
from . import image_processing
from . import indicator
from . import session
from .config import (
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    EVIDENCE_BEFORE_AFTER_FOR_INPUT,
    GUIDANCE_TEMPLATE,
    MAX_STEPS,
    SCREENSHOTS_DIR,
    _env,
    _require_env,
    ENABLE_SESSION_SUMMARY,
    ENABLE_STATUS_INDICATOR,
    STATUS_INDICATOR_CLICK_THROUGH,
    STATUS_INDICATOR_FONT_FAMILY,
    STATUS_INDICATOR_FONT_SIZE,
    STATUS_INDICATOR_HEIGHT,
    STATUS_INDICATOR_OFFSET_X,
    STATUS_INDICATOR_OFFSET_Y,
    STATUS_INDICATOR_OPACITY,
    STATUS_INDICATOR_POLL_MS,
    STATUS_INDICATOR_POSITION,
    STATUS_INDICATOR_WIDTH,
    USE_CONFIRM_INTERPRETER_MODEL,
)
from .utils import format_typed_text_for_log


def init_runtime_from_env() -> None:
    """
    環境変数からランタイム設定を初期化します。

    Azure OpenAI クライアント、使用するモデル名などを設定します。

    Raises:
        RuntimeError: 必須の環境変数が設定されていない場合
    """
    # 必須モデルの取得
    computer_use_model = _require_env("AZURE_OPENAI_MODEL_COMPUTER_USE")

    # オプショナルモデルの取得
    summary_model = None
    if ENABLE_SESSION_SUMMARY:
        summary_model = _require_env("AZURE_OPENAI_MODEL_SUMMARY")

    confirm_model = None
    if USE_CONFIRM_INTERPRETER_MODEL:
        confirm_model = _require_env("AZURE_OPENAI_MODEL_CONFIRM")

    # クライアントとモデルの初期化
    client.init_client()
    confirmation.init_models(
        confirm_model=confirm_model, computer_use_model=computer_use_model
    )
    session.init_models(summary_model=summary_model)


def build_initial_user_instruction(*, message: str) -> str:
    """
    初期ユーザー指示を構築します。

    Args:
        message: ユーザーからの直接指示

    Returns:
        構築された指示文字列
    """
    # TARGET_MESSAGE をそのまま computer-use への直接指示として扱う
    return message


def execute_action(
    *,
    step: int,
    action,
    action_type: str,
    cycle_base_image: Path | None = None,
) -> Path | None:
    """
    単一のアクションを実行します。

    Args:
        step: 現在のステップ番号
        action: アクションオブジェクト
        action_type: アクションの種類

    Returns:
        生成されたスクリーンショットのパス、スクリーンショットが生成されなかった場合は None

    Raises:
        ValueError: 無効なアクションパラメータの場合
    """
    screenshot_path: Path | None = None

    def _split_stamp_and_index(path: Path) -> tuple[str, int | None]:
        parts = (path.stem or "").split("_")
        if len(parts) >= 2 and parts[-1].isdigit() and len(parts[-1]) == 2:
            return ("_".join(parts[:-1]), int(parts[-1]))
        return (path.stem, None)

    def _cycle_artifact_path(
        *, idx: int, tail: str, ext: str | None = None
    ) -> Path | None:
        if cycle_base_image is None:
            return None
        try:
            base = Path(cycle_base_image)
        except Exception:
            return None
        stamp, _ = _split_stamp_and_index(base)
        suffix = ext if isinstance(ext, str) and ext else base.suffix
        return base.with_name(f"{stamp}_{idx:02d}{tail}{suffix}")

    def _format_pointer_debug(
        *,
        model_x: int,
        model_y: int,
        model_w: int,
        model_h: int,
        px: int,
        py: int,
        screen_w: int,
        screen_h: int,
    ) -> str:
        mx = max(1, int(model_w))
        my = max(1, int(model_h))
        sx = max(1, int(screen_w))
        sy = max(1, int(screen_h))

        model_max_x = mx - 1
        model_max_y = my - 1
        screen_max_x = sx - 1
        screen_max_y = sy - 1

        model_rx = model_x / mx
        model_ry = model_y / my
        screen_rx = px / sx
        screen_ry = py / sy

        return (
            f"model_ratio=({model_x}/{mx}={model_rx:.4f},{model_y}/{my}={model_ry:.4f}) "
            f"model_max=({model_max_x},{model_max_y}) "
            f"screen_ratio=({px}/{sx}={screen_rx:.4f},{py}/{sy}={screen_ry:.4f}) "
            f"screen_max=({screen_max_x},{screen_max_y})"
        )

    if action_type == "screenshot":
        # スクリーンショットの撮影
        screenshot_path = image_processing.capture_fullscreen_screenshot(
            screenshots_dir=SCREENSHOTS_DIR
        )
        print(f"[{step}] Captured screenshot: {screenshot_path}")
        session.log_session_event(step=step, kind="action", detail="screenshot")

    elif action_type == "click":
        # クリック操作
        x = getattr(action, "x", None)
        y = getattr(action, "y", None)
        button = getattr(action, "button", None)
        if not isinstance(x, int) or not isinstance(y, int):
            raise ValueError(f"Invalid click coordinates: x={x} y={y}")

        px, py, screen_w, screen_h = actions.perform_click(
            x,
            y,
            display_width=DISPLAY_WIDTH,
            display_height=DISPLAY_HEIGHT,
            button=button,
        )
        debug = _format_pointer_debug(
            model_x=x,
            model_y=y,
            model_w=DISPLAY_WIDTH,
            model_h=DISPLAY_HEIGHT,
            px=px,
            py=py,
            screen_w=screen_w,
            screen_h=screen_h,
        )
        if isinstance(button, str) and button:
            print(
                f"[{step}] Clicked ({button}): model=({x},{y}) -> screen=({px},{py}) {debug}"
            )
        else:
            print(f"[{step}] Clicked: model=({x},{y}) -> screen=({px},{py}) {debug}")
        session.log_session_event(
            step=step,
            kind="action",
            detail=f"click button={button} model=({x},{y}) screen=({px},{py}) {debug}",
        )
        time.sleep(0.2)

        # クリック後のスクリーンショット
        screenshot_path = image_processing.capture_fullscreen_screenshot(
            screenshots_dir=SCREENSHOTS_DIR
        )
        print(f"[{step}] Captured screenshot: {screenshot_path}")

    elif action_type == "double_click":
        # ダブルクリック操作
        x = getattr(action, "x", None)
        y = getattr(action, "y", None)
        if not isinstance(x, int) or not isinstance(y, int):
            raise ValueError(f"Invalid double_click coordinates: x={x} y={y}")

        px, py, screen_w, screen_h = actions.perform_double_click(
            x, y, display_width=DISPLAY_WIDTH, display_height=DISPLAY_HEIGHT
        )
        debug = _format_pointer_debug(
            model_x=x,
            model_y=y,
            model_w=DISPLAY_WIDTH,
            model_h=DISPLAY_HEIGHT,
            px=px,
            py=py,
            screen_w=screen_w,
            screen_h=screen_h,
        )
        print(f"[{step}] Double-clicked: model=({x},{y}) -> screen=({px},{py}) {debug}")
        session.log_session_event(
            step=step,
            kind="action",
            detail=f"double_click model=({x},{y}) screen=({px},{py}) {debug}",
        )
        time.sleep(0.2)

        screenshot_path = image_processing.capture_fullscreen_screenshot(
            screenshots_dir=SCREENSHOTS_DIR
        )
        print(f"[{step}] Captured screenshot: {screenshot_path}")

    elif action_type == "move":
        # マウス移動操作
        x = getattr(action, "x", None)
        y = getattr(action, "y", None)
        if not isinstance(x, int) or not isinstance(y, int):
            raise ValueError(f"Invalid move coordinates: x={x} y={y}")

        px, py, screen_w, screen_h = actions.perform_move(
            x, y, display_width=DISPLAY_WIDTH, display_height=DISPLAY_HEIGHT
        )
        debug = _format_pointer_debug(
            model_x=x,
            model_y=y,
            model_w=DISPLAY_WIDTH,
            model_h=DISPLAY_HEIGHT,
            px=px,
            py=py,
            screen_w=screen_w,
            screen_h=screen_h,
        )
        print(f"[{step}] Moved: model=({x},{y}) -> screen=({px},{py}) {debug}")
        session.log_session_event(
            step=step,
            kind="action",
            detail=f"move model=({x},{y}) screen=({px},{py}) {debug}",
        )
        time.sleep(0.1)

        screenshot_path = image_processing.capture_fullscreen_screenshot(
            screenshots_dir=SCREENSHOTS_DIR
        )
        print(f"[{step}] Captured screenshot: {screenshot_path}")

    elif action_type == "drag":
        # ドラッグ操作
        path = getattr(action, "path", None)
        if not isinstance(path, list) or not path:
            raise ValueError(f"Invalid drag path: {path}")

        px, py, screen_w, screen_h = actions.perform_drag(
            path, display_width=DISPLAY_WIDTH, display_height=DISPLAY_HEIGHT
        )
        # drag は path 終点のスクリーン座標を返すが、モデル座標側は path の最後を比率表示に使う
        last = path[-1]
        if isinstance(last, dict):
            model_x = last.get("x")
            model_y = last.get("y")
        else:
            model_x = getattr(last, "x", None)
            model_y = getattr(last, "y", None)
        if not isinstance(model_x, int):
            model_x = 0
        if not isinstance(model_y, int):
            model_y = 0
        debug = _format_pointer_debug(
            model_x=model_x,
            model_y=model_y,
            model_w=DISPLAY_WIDTH,
            model_h=DISPLAY_HEIGHT,
            px=px,
            py=py,
            screen_w=screen_w,
            screen_h=screen_h,
        )
        print(f"[{step}] Dragged; ended at screen=({px},{py}) {debug}")
        session.log_session_event(
            step=step, kind="action", detail=f"drag ended_screen=({px},{py}) {debug}"
        )
        time.sleep(0.2)

        screenshot_path = image_processing.capture_fullscreen_screenshot(
            screenshots_dir=SCREENSHOTS_DIR
        )
        print(f"[{step}] Captured screenshot: {screenshot_path}")

    elif action_type == "scroll":
        # スクロール操作
        x = getattr(action, "x", None)
        y = getattr(action, "y", None)
        scroll_x = getattr(action, "scroll_x", 0)
        scroll_y = getattr(action, "scroll_y", 0)
        if not isinstance(x, int) or not isinstance(y, int):
            raise ValueError(f"Invalid scroll coordinates: x={x} y={y}")
        if not isinstance(scroll_x, int) or not isinstance(scroll_y, int):
            raise ValueError(
                f"Invalid scroll values: scroll_x={scroll_x} scroll_y={scroll_y}"
            )

        px, py, screen_w, screen_h = actions.perform_scroll(
            x,
            y,
            display_width=DISPLAY_WIDTH,
            display_height=DISPLAY_HEIGHT,
            scroll_x=scroll_x,
            scroll_y=scroll_y,
        )
        debug = _format_pointer_debug(
            model_x=x,
            model_y=y,
            model_w=DISPLAY_WIDTH,
            model_h=DISPLAY_HEIGHT,
            px=px,
            py=py,
            screen_w=screen_w,
            screen_h=screen_h,
        )
        print(
            f"[{step}] Scrolled at screen=({px},{py}) x={scroll_x} y={scroll_y} {debug}"
        )
        session.log_session_event(
            step=step,
            kind="action",
            detail=f"scroll at_screen=({px},{py}) scroll_x={scroll_x} scroll_y={scroll_y} {debug}",
        )
        time.sleep(0.2)

        screenshot_path = image_processing.capture_fullscreen_screenshot(
            screenshots_dir=SCREENSHOTS_DIR
        )
        print(f"[{step}] Captured screenshot: {screenshot_path}")

    elif action_type == "type":
        # テキスト入力操作
        text = getattr(action, "text", None)
        if not isinstance(text, str):
            raise ValueError(f"Invalid type text: {text}")

        # 入力前のエビデンススクリーンショット
        if EVIDENCE_BEFORE_AFTER_FOR_INPUT:
            dst = _cycle_artifact_path(idx=5, tail="_Evidence_BeforeType")
            if dst is not None:
                try:
                    before_path = (
                        image_processing.capture_fullscreen_screenshot_to_path(dst)
                    )
                    print(f"[{step}] Evidence (before type): {before_path}")
                except Exception:
                    before_path = image_processing.capture_fullscreen_screenshot(
                        screenshots_dir=SCREENSHOTS_DIR
                    )
                    print(f"[{step}] Evidence (before type): {before_path}")
            else:
                before_path = image_processing.capture_fullscreen_screenshot(
                    screenshots_dir=SCREENSHOTS_DIR
                )
                print(f"[{step}] Evidence (before type): {before_path}")

        actions.perform_type(text)
        print(f"[{step}] Typed {len(text)} chars")
        logged = format_typed_text_for_log(text, max_chars=200)
        session.log_session_event(
            step=step,
            kind="action",
            detail=f"type chars={len(text)} text='{logged}'",
        )
        time.sleep(0.5)

        # 入力後のエビデンススクリーンショット
        after_path = image_processing.capture_fullscreen_screenshot(
            screenshots_dir=SCREENSHOTS_DIR
        )
        dst = _cycle_artifact_path(idx=6, tail="_Evidence_AfterType")
        if dst is not None:
            try:
                shutil.copy2(after_path, dst)
                print(f"[{step}] Evidence (after type): {dst}")
            except Exception:
                print(f"[{step}] Evidence (after type): {after_path}")
        else:
            print(f"[{step}] Evidence (after type): {after_path}")
        screenshot_path = after_path

    elif action_type == "wait":
        # 待機操作
        duration_ms = getattr(action, "duration_ms", None)
        actions.perform_wait(duration_ms)
        print(f"[{step}] Waited: duration_ms={duration_ms}")
        session.log_session_event(
            step=step, kind="action", detail=f"wait duration_ms={duration_ms}"
        )

        screenshot_path = image_processing.capture_fullscreen_screenshot(
            screenshots_dir=SCREENSHOTS_DIR
        )
        print(f"[{step}] Captured screenshot: {screenshot_path}")

    elif action_type == "keypress":
        # キープレス操作
        keys = getattr(action, "keys", None)
        if not isinstance(keys, list) or not keys:
            raise ValueError(f"Invalid keypress keys: {keys}")

        # 入力前のエビデンススクリーンショット
        if EVIDENCE_BEFORE_AFTER_FOR_INPUT:
            dst = _cycle_artifact_path(idx=5, tail="_Evidence_BeforeKeypress")
            if dst is not None:
                try:
                    before_path = (
                        image_processing.capture_fullscreen_screenshot_to_path(dst)
                    )
                    print(f"[{step}] Evidence (before keypress): {before_path}")
                except Exception:
                    before_path = image_processing.capture_fullscreen_screenshot(
                        screenshots_dir=SCREENSHOTS_DIR
                    )
                    print(f"[{step}] Evidence (before keypress): {before_path}")
            else:
                before_path = image_processing.capture_fullscreen_screenshot(
                    screenshots_dir=SCREENSHOTS_DIR
                )
                print(f"[{step}] Evidence (before keypress): {before_path}")

        actions.perform_keypress(keys)
        print(f"[{step}] Keypress: {keys}")
        session.log_session_event(
            step=step, kind="action", detail=f"keypress keys={keys}"
        )
        time.sleep(0.5)

        # 入力後のエビデンススクリーンショット
        after_path = image_processing.capture_fullscreen_screenshot(
            screenshots_dir=SCREENSHOTS_DIR
        )
        dst = _cycle_artifact_path(idx=6, tail="_Evidence_AfterKeypress")
        if dst is not None:
            try:
                shutil.copy2(after_path, dst)
                print(f"[{step}] Evidence (after keypress): {dst}")
            except Exception:
                print(f"[{step}] Evidence (after keypress): {after_path}")
        else:
            print(f"[{step}] Evidence (after keypress): {after_path}")
        screenshot_path = after_path

    else:
        raise ValueError(f"Unsupported action type: {action_type}")

    return screenshot_path


def main(argv: list[str] | None = None) -> int:
    """
    メイン実行関数。

    コマンドライン引数を解析し、Azure OpenAI computer-use を実行します。

    Args:
        argv: コマンドライン引数のリスト（テスト用）

    Returns:
        終了コード（0: 成功）

    Raises:
        RuntimeError: 必須パラメータが不足している場合
    """
    # コマンドライン引数の解析
    parser = argparse.ArgumentParser(description="Azure OpenAI computer-use runner")
    parser.add_argument(
        "--message",
        default=_env("TARGET_MESSAGE"),
        help="Direct instruction for computer-use. You can also set TARGET_MESSAGE in .env",
    )
    args = parser.parse_args(argv)

    if not args.message:
        raise RuntimeError(
            "Missing message. Set TARGET_MESSAGE in .env or pass --message."
        )

    # ランタイムの初期化
    init_runtime_from_env()

    # ステータスインジケーター（右上小窓）
    status = indicator.StatusIndicator(
        enabled=ENABLE_STATUS_INDICATOR,
        opacity=STATUS_INDICATOR_OPACITY,
        width=STATUS_INDICATOR_WIDTH,
        height=STATUS_INDICATOR_HEIGHT,
        poll_ms=STATUS_INDICATOR_POLL_MS,
        position=str(STATUS_INDICATOR_POSITION or "top-right"),
        offset_x=STATUS_INDICATOR_OFFSET_X,
        offset_y=STATUS_INDICATOR_OFFSET_Y,
        font_family=str(STATUS_INDICATOR_FONT_FAMILY or "Segoe UI"),
        font_size=STATUS_INDICATOR_FONT_SIZE,
        click_through=STATUS_INDICATOR_CLICK_THROUGH,
    )
    status.start()
    status.update(step=0, max_steps=MAX_STEPS, phase="初期化", last_action="")

    # 初期ユーザー指示の構築
    user_instruction = build_initial_user_instruction(
        message=str(args.message),
    )

    try:
        # 初回APIリクエスト
        status.update(step=0, max_steps=MAX_STEPS, phase="API待ち", last_action="")
        response = client.responses_create_with_retry(
            model=confirmation.COMPUTER_USE_MODEL,
            tools=client.make_tools("windows"),
            input=[
                {"role": "system", "content": GUIDANCE_TEMPLATE},
                {"role": "user", "content": user_instruction},
            ],
            truncation="auto",
        )

        print(response.output)

        # 直近でモデルに送信した（= モデルが現状把握に使った）スクリーンショット
        last_sent_screenshot: Path | None = None

        # メインループ
        for step in range(1, MAX_STEPS + 1):
            status.update(
                step=step, max_steps=MAX_STEPS, phase="確認中", last_action=""
            )

            # 確認が必要な場合は自動確認を送信
            response, computer_call = confirmation.get_or_confirm_computer_call(
                response
            )
            if computer_call is None:
                print("No computer call found; stopping.")
                break

            # このレスポンスが指示しているアクションをログに残す（step のズレを防ぐ）
            session.log_model_response_summary(step=step, response_obj=response)
            if last_sent_screenshot is not None:
                try:
                    parts = (last_sent_screenshot.stem or "").split("_")
                    if len(parts) >= 2 and parts[-1].isdigit() and len(parts[-1]) == 2:
                        stamp = "_".join(parts[:-1])
                    else:
                        stamp = last_sent_screenshot.stem
                    debug_txt = last_sent_screenshot.with_name(f"{stamp}_02_Debug.txt")
                except Exception:
                    debug_txt = None
                debug.save_model_debug_text(
                    sent_image_path=last_sent_screenshot,
                    step=step,
                    response_obj=response,
                    output_path=debug_txt,
                )

            last_call_id = computer_call.call_id
            action = computer_call.action
            action_type = getattr(action, "type", None)

            status.update(
                step=step,
                max_steps=MAX_STEPS,
                phase="操作中",
                last_action=(
                    str(action_type) if isinstance(action_type, str) else "(unknown)"
                ),
            )

            # アクションの実行
            try:
                screenshot_path = execute_action(
                    step=step,
                    action=action,
                    action_type=action_type,
                    cycle_base_image=last_sent_screenshot,
                )
            except ValueError as e:
                print(f"[{step}] {e}; stopping.")
                break

            if screenshot_path is None:
                print(f"[{step}] No screenshot available; stopping.")
                break

            # 直前にモデルへ送った画像（タイムスタンプ.png）を基準に、実行結果を保存
            if last_sent_screenshot is not None and last_sent_screenshot.exists():
                try:
                    base = last_sent_screenshot
                    parts = (base.stem or "").split("_")
                    if len(parts) >= 2 and parts[-1].isdigit() and len(parts[-1]) == 2:
                        stamp = "_".join(parts[:-1])
                    else:
                        stamp = base.stem
                    debug_img = base.with_name(f"{stamp}_03_Debug{base.suffix}")
                    debug_img_r = base.with_name(f"{stamp}_04_Debug_R{base.suffix}")
                    shutil.copy2(screenshot_path, debug_img)

                    note = session._summarize_action_for_log(action)

                    points: list[tuple[int, int]] = []
                    if action_type in ("click", "double_click", "move", "scroll"):
                        x = getattr(action, "x", None)
                        y = getattr(action, "y", None)
                        if isinstance(x, int) and isinstance(y, int):
                            points = [(x, y)]
                    elif action_type == "drag":
                        path = getattr(action, "path", None)
                        if isinstance(path, list) and path:
                            last = path[-1]
                            if isinstance(last, dict):
                                x = last.get("x")
                                y = last.get("y")
                            else:
                                x = getattr(last, "x", None)
                                y = getattr(last, "y", None)
                            if isinstance(x, int) and isinstance(y, int):
                                points = [(x, y)]

                    image_processing.annotate_action_overlay(
                        debug_img,
                        output_path=debug_img_r,
                        note=note,
                        points=points,
                        display_width=DISPLAY_WIDTH,
                        display_height=DISPLAY_HEIGHT,
                    )
                    print(f"[{step}] Action screenshot saved: {debug_img}")
                    print(f"[{step}] Action overlay saved: {debug_img_r}")
                except Exception as e:
                    print(f"[{step}] Failed to save action evidence: {e}")

            # APIに結果を送信
            status.update(
                step=step,
                max_steps=MAX_STEPS,
                phase="API待ち",
                last_action=str(action_type),
            )
            # 次ステップの基準スクショは必ず `_01` を付けて保存
            sent_image_path = screenshot_path
            try:
                stem_parts = (sent_image_path.stem or "").split("_")
                if (
                    len(stem_parts) >= 2
                    and stem_parts[-1].isdigit()
                    and len(stem_parts[-1]) == 2
                ):
                    # すでに連番付きならそのまま（念のため 01 に統一）
                    stamp = "_".join(stem_parts[:-1])
                else:
                    stamp = sent_image_path.stem
                target = sent_image_path.with_name(
                    f"{stamp}_01{sent_image_path.suffix}"
                )
                if target != sent_image_path:
                    try:
                        sent_image_path = sent_image_path.replace(target)
                    except Exception:
                        shutil.copy2(sent_image_path, target)
                        sent_image_path = target
            except Exception:
                pass

            response = client.responses_create_with_retry(
                model=confirmation.COMPUTER_USE_MODEL,
                previous_response_id=response.id,
                tools=client.make_tools("windows"),
                input=[
                    {
                        "call_id": last_call_id,
                        "type": "computer_call_output",
                        "output": {
                            "type": "input_image",
                            "image_url": image_processing.image_file_to_data_url(
                                sent_image_path
                            ),
                        },
                    }
                ],
                truncation="auto",
            )

            # 次ステップの「現状把握（タイムスタンプ.png）」として保持
            last_sent_screenshot = sent_image_path

            print(response.output)

        status.update(step=MAX_STEPS, max_steps=MAX_STEPS, phase="完了", last_action="")
        return 0
    finally:
        # UIスレッドは daemon ですが、明示停止しておく
        status.stop()


if __name__ == "__main__":
    raise SystemExit(main())
