"""
アクション実行モジュール

コンピューター操作のアクション（クリック、入力、スクロールなど）を実行します。
"""

import sys
import time

import pyautogui

from .image_processing import get_primary_screen_size
from .utils import normalize_key_name, normalize_mouse_button, scale_point


# PyAutoGUIの設定
pyautogui.FAILSAFE = True  # マウスを画面の隅に移動すると緊急停止
pyautogui.PAUSE = 0.05  # 各操作の間隔


def perform_click(
    x: int,
    y: int,
    *,
    display_width: int,
    display_height: int,
    button: str | None = None,
) -> tuple[int, int]:
    """
    指定された座標でマウスクリックを実行します。

    モデルが返す座標を実際のスクリーン座標にスケーリングしてからクリックします。

    Args:
        x: モデル座標系のX座標
        y: モデル座標系のY座標
        display_width: モデルのディスプレイ幅
        display_height: モデルのディスプレイ高さ
        button: クリックするボタン ("left", "right", "middle")

    Returns:
        実際にクリックされたスクリーン座標 (px, py)
    """
    screen_w, screen_h = get_primary_screen_size()
    px, py = scale_point(
        x,
        y,
        from_width=display_width,
        from_height=display_height,
        to_width=screen_w,
        to_height=screen_h,
    )
    pyautogui.click(px, py, button=normalize_mouse_button(button))
    return px, py


def perform_double_click(
    x: int,
    y: int,
    *,
    display_width: int,
    display_height: int,
    button: str | None = None,
) -> tuple[int, int]:
    """
    指定された座標でマウスダブルクリックを実行します。

    Args:
        x: モデル座標系のX座標
        y: モデル座標系のY座標
        display_width: モデルのディスプレイ幅
        display_height: モデルのディスプレイ高さ
        button: クリックするボタン ("left", "right", "middle")

    Returns:
        実際にクリックされたスクリーン座標 (px, py)
    """
    screen_w, screen_h = get_primary_screen_size()
    px, py = scale_point(
        x,
        y,
        from_width=display_width,
        from_height=display_height,
        to_width=screen_w,
        to_height=screen_h,
    )
    pyautogui.doubleClick(px, py, button=normalize_mouse_button(button))
    return px, py


def perform_move(
    x: int,
    y: int,
    *,
    display_width: int,
    display_height: int,
    duration: float = 0.0,
) -> tuple[int, int]:
    """
    マウスカーソルを指定された座標に移動します。

    Args:
        x: モデル座標系のX座標
        y: モデル座標系のY座標
        display_width: モデルのディスプレイ幅
        display_height: モデルのディスプレイ高さ
        duration: 移動にかける時間（秒）

    Returns:
        実際の移動先スクリーン座標 (px, py)
    """
    screen_w, screen_h = get_primary_screen_size()
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
    """
    マウスドラッグ操作を実行します。

    指定されたパスに沿ってマウスをドラッグします。

    Args:
        path: ドラッグパスの座標リスト [{"x": x1, "y": y1}, {"x": x2, "y": y2}, ...]
        display_width: モデルのディスプレイ幅
        display_height: モデルのディスプレイ高さ
        duration: ドラッグにかける時間（秒）
        button: ドラッグに使用するボタン

    Returns:
        ドラッグ終了時のスクリーン座標 (px, py)

    Raises:
        ValueError: パスが空または2点未満の場合
    """
    if not path:
        raise ValueError("drag.path is empty")

    # パスから座標を抽出
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

    # スクリーン座標にスケーリング
    screen_w, screen_h = get_primary_screen_size()
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

    # ドラッグを実行
    (start_x, start_y) = scaled[0]
    pyautogui.moveTo(start_x, start_y)
    pyautogui.mouseDown(button=normalize_mouse_button(button))

    per_step = duration / max(1, (len(scaled) - 1))
    last_x, last_y = start_x, start_y
    for px, py in scaled[1:]:
        pyautogui.moveTo(px, py, duration=per_step)
        last_x, last_y = px, py

    pyautogui.mouseUp(button=normalize_mouse_button(button))
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
    """
    指定された座標でスクロール操作を実行します。

    Args:
        x: モデル座標系のX座標
        y: モデル座標系のY座標
        display_width: モデルのディスプレイ幅
        display_height: モデルのディスプレイ高さ
        scroll_x: 横スクロール量
        scroll_y: 縦スクロール量

    Returns:
        スクロール位置のスクリーン座標 (px, py)
    """
    px, py = perform_move(
        x, y, display_width=display_width, display_height=display_height
    )
    if isinstance(scroll_y, int) and scroll_y:
        pyautogui.scroll(scroll_y)
    if isinstance(scroll_x, int) and scroll_x:
        pyautogui.hscroll(scroll_x)
    return px, py


def perform_type(text: str, *, interval: float = 0.0) -> None:
    """
    テキストを入力します。

    Args:
        text: 入力するテキスト
        interval: 各文字の入力間隔（秒）

    Raises:
        ValueError: text が文字列でない場合
    """
    if not isinstance(text, str):
        raise ValueError("type.text must be a string")
    if not text:
        return

    # 日本語入力などでpyautogui.writeが失敗するケースがあるため、
    # 可能ならクリップボード経由で貼り付けする。
    try:
        import pyperclip  # type: ignore

        previous = None
        try:
            previous = pyperclip.paste()
        except Exception:
            previous = None

        try:
            pyperclip.copy(text)
            time.sleep(0.02)
            modifier = "command" if sys.platform == "darwin" else "ctrl"
            pyautogui.hotkey(modifier, "v")
            time.sleep(0.02)
        finally:
            if isinstance(previous, str):
                try:
                    pyperclip.copy(previous)
                except Exception:
                    pass
    except Exception:
        # クリップボードが使えない環境では従来方式にフォールバック
        pyautogui.write(text, interval=interval)


def perform_wait(duration_ms: int | None = None) -> None:
    """
    指定された時間だけ待機します。

    Args:
        duration_ms: 待機時間（ミリ秒）。None または 0 以下の場合は1秒待機
    """
    if isinstance(duration_ms, int) and duration_ms > 0:
        time.sleep(duration_ms / 1000)
    else:
        time.sleep(1.0)


def perform_keypress(keys: list[str]) -> None:
    """
    キーボードのキーを押します。

    単一のキーの場合はpress、複数のキーの場合はhotkeyとして実行します。

    Args:
        keys: 押すキーのリスト

    Raises:
        ValueError: キーが指定されていない場合
    """
    norm = [normalize_key_name(k) for k in keys if isinstance(k, str) and k.strip()]
    if not norm:
        raise ValueError("No keys provided for keypress")
    if len(norm) == 1:
        pyautogui.press(norm[0])
    else:
        pyautogui.hotkey(*norm)
