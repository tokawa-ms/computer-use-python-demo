"""\
ステータスインジケーターモジュール

実行中に画面右上へ小さな常時最前面ウィンドウを表示して、
現在のステップやフェーズなどを簡易表示します。

- Tkinter を別スレッドで動かし、メインスレッドからはキューに状態を投げるだけにします。
- Tkinter が利用できない環境では no-op として動作します。
"""

from __future__ import annotations

import queue
import sys
import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class IndicatorStatus:
    """インジケーターに表示する状態。"""

    step: int
    max_steps: int
    phase: str
    last_action: str
    started_at: float


class StatusIndicator:
    """右上に小さいインジケーターウィンドウを表示します。"""

    def __init__(
        self,
        *,
        enabled: bool = True,
        opacity: float = 0.78,
        width: int = 280,
        height: int = 92,
        margin: int = 12,
        poll_ms: int = 120,
        position: str = "top-right",
        offset_x: int = 12,
        offset_y: int = 12,
        font_family: str = "Segoe UI",
        font_size: int = 9,
        click_through: bool = True,
    ) -> None:
        self.enabled = bool(enabled)
        self.opacity = max(0.2, min(1.0, float(opacity)))
        # 極端な値で表示不能になるのを防ぐ
        self.width = max(140, int(width))
        self.height = max(60, int(height))
        self.margin = int(margin)
        self.poll_ms = int(poll_ms)
        self.position = str(position or "top-right")
        self.offset_x = int(offset_x)
        self.offset_y = int(offset_y)
        self.font_family = str(font_family or "Segoe UI")
        self.font_size = max(6, min(48, int(font_size)))
        self.click_through = bool(click_through)

        self._queue: "queue.Queue[IndicatorStatus | None]" = queue.Queue()
        self._thread: threading.Thread | None = None
        self._started_at = time.time()

    def start(self) -> None:
        """インジケーターを起動します（別スレッド）。"""
        if not self.enabled:
            return
        if self._thread is not None and self._thread.is_alive():
            return

        self._thread = threading.Thread(
            target=self._ui_thread_main,
            name="status-indicator",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """インジケーターを停止します。"""
        if not self.enabled:
            return
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass

    def update(
        self, *, step: int, max_steps: int, phase: str, last_action: str
    ) -> None:
        """表示状態を更新します。"""
        if not self.enabled:
            return
        status = IndicatorStatus(
            step=int(step),
            max_steps=int(max_steps),
            phase=str(phase),
            last_action=str(last_action),
            started_at=self._started_at,
        )
        try:
            self._queue.put_nowait(status)
        except Exception:
            # UIが落ちている/キューが詰まっている等は無視
            pass

    def _ui_thread_main(self) -> None:
        """TkinterのUIスレッド本体。"""
        try:
            import tkinter as tk
            from tkinter import TclError
        except Exception:
            # Tkinter が利用できない環境では no-op
            self.enabled = False
            return

        try:
            root = tk.Tk()
        except Exception:
            self.enabled = False
            return

        # 右上・枠なし・最前面
        try:
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-alpha", max(0.2, min(1.0, self.opacity)))
            # 可能ならタスクバーに出さない
            try:
                root.wm_attributes("-toolwindow", True)
            except Exception:
                pass
        except Exception:
            pass

        bg = "#111111"
        fg = "#EDEDED"
        root.configure(background=bg)

        # テキスト
        font = (self.font_family, self.font_size)
        text_var = tk.StringVar(value="starting...")
        label = tk.Label(
            root,
            textvariable=text_var,
            justify="left",
            anchor="nw",
            background=bg,
            foreground=fg,
            font=font,
            padx=10,
            pady=8,
        )
        label.pack(fill="both", expand=True)

        # Windows: クリック透過（背面にクリックを通す）
        if self.click_through and sys.platform.startswith("win"):
            try:
                root.update_idletasks()
                _enable_click_through_windows(root)
                # スタイル変更後に再描画を促す
                root.update_idletasks()
            except Exception:
                pass

        # 初期配置
        def place_window() -> None:
            try:
                # マルチモニタ環境では virtual root を基準にすると置き場所が安定する
                try:
                    vx = int(root.winfo_vrootx())
                    vy = int(root.winfo_vrooty())
                    vw = int(root.winfo_vrootwidth())
                    vh = int(root.winfo_vrootheight())
                except Exception:
                    vx = 0
                    vy = 0
                    vw = int(root.winfo_screenwidth())
                    vh = int(root.winfo_screenheight())

                pos = (self.position or "top-right").strip().lower()
                # 互換: margin を残しつつ、offset_x/y を優先
                ox = max(
                    0, int(self.offset_x if self.offset_x is not None else self.margin)
                )
                oy = max(
                    0, int(self.offset_y if self.offset_y is not None else self.margin)
                )

                if "left" in pos:
                    x = vx + ox
                else:
                    x = vx + max(0, vw - self.width - ox)

                if "bottom" in pos:
                    y = vy + max(0, vh - self.height - oy)
                else:
                    y = vy + oy

                root.geometry(f"{self.width}x{self.height}+{x}+{y}")

                # 念のため最前面へ
                try:
                    root.deiconify()
                    root.lift()
                except Exception:
                    pass
            except Exception:
                pass

        place_window()

        # 最新状態
        last: IndicatorStatus | None = None

        def format_status(s: IndicatorStatus) -> str:
            elapsed = max(0.0, time.time() - s.started_at)
            mm = int(elapsed // 60)
            ss = int(elapsed % 60)
            step_part = f"Step {s.step}/{s.max_steps}"
            phase_part = f"Phase: {s.phase}"
            action_part = f"Last: {s.last_action}" if s.last_action else "Last: (none)"
            time_part = f"Elapsed: {mm:02d}:{ss:02d}"
            return "\n".join((step_part, phase_part, action_part, time_part))

        def pump_queue() -> None:
            nonlocal last
            try:
                while True:
                    item = self._queue.get_nowait()
                    if item is None:
                        try:
                            root.destroy()
                        except Exception:
                            pass
                        return
                    last = item
            except queue.Empty:
                pass

            if last is not None:
                try:
                    text_var.set(format_status(last))
                except Exception:
                    pass

            # 位置ずれ対策（DPI/解像度変更など）
            place_window()

            try:
                root.after(self.poll_ms, pump_queue)
            except TclError:
                return

        root.after(self.poll_ms, pump_queue)

        # クリックで閉じない（誤操作防止）。閉じたい場合は stop() を呼ぶ。
        try:
            root.mainloop()
        except Exception:
            # UIスレッドの例外で本体を落とさない
            return


def _enable_click_through_windows(root) -> None:
    """Windowsでクリック透過（背面クリック）を有効にします。"""

    import ctypes
    from ctypes import wintypes

    hwnd = int(getattr(root, "winfo_id")())
    if not hwnd:
        return

    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_NOACTIVATE = 0x08000000

    user32 = ctypes.windll.user32

    # Tkinter では winfo_id() が子 HWND を返すことがあるため、トップレベルを取得
    try:
        GA_ROOT = 2
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        top = user32.GetAncestor(wintypes.HWND(hwnd), GA_ROOT)
        hwnd_target = int(top) if top else hwnd
    except Exception:
        hwnd_target = hwnd

    # 32/64bit両対応で安全な型を使う
    is_64 = ctypes.sizeof(ctypes.c_void_p) == 8
    if is_64:
        GetWindowLongPtr = user32.GetWindowLongPtrW
        SetWindowLongPtr = user32.SetWindowLongPtrW
        GetWindowLongPtr.argtypes = [wintypes.HWND, ctypes.c_int]
        GetWindowLongPtr.restype = ctypes.c_ssize_t
        SetWindowLongPtr.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        SetWindowLongPtr.restype = ctypes.c_ssize_t
    else:
        GetWindowLongPtr = user32.GetWindowLongW
        SetWindowLongPtr = user32.SetWindowLongW
        GetWindowLongPtr.argtypes = [wintypes.HWND, ctypes.c_int]
        GetWindowLongPtr.restype = wintypes.LONG
        SetWindowLongPtr.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
        SetWindowLongPtr.restype = wintypes.LONG

    exstyle = int(GetWindowLongPtr(wintypes.HWND(hwnd_target), GWL_EXSTYLE))
    # WS_EX_LAYERED は Tk が -alpha 設定時に付与するため、ここでは強制しない
    exstyle |= WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
    SetWindowLongPtr(wintypes.HWND(hwnd_target), GWL_EXSTYLE, exstyle)

    # スタイル変更を確実に反映させ、再描画させる
    try:
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        SWP_FRAMECHANGED = 0x0020
        user32.SetWindowPos(
            wintypes.HWND(hwnd_target),
            None,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
        )
        user32.InvalidateRect(wintypes.HWND(hwnd_target), None, True)
        user32.UpdateWindow(wintypes.HWND(hwnd_target))
    except Exception:
        pass
