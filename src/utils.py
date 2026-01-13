"""
ユーティリティモジュール

汎用的なヘルパー関数を提供します。
キー名の正規化、マウスボタンの正規化、テキストフォーマットなどの機能を含みます。
"""


def normalize_key_name(key: str) -> str:
    """
    キー名を正規化します。
    
    様々なキー名のエイリアスを統一された名前に変換します。
    
    Args:
        key: 元のキー名
    
    Returns:
        正規化されたキー名
    """
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


def normalize_mouse_button(button: str | None) -> str:
    """
    マウスボタン名を正規化します。
    
    Args:
        button: 元のボタン名（None の場合は "left" を返す）
    
    Returns:
        正規化されたボタン名（"left", "right", "middle" のいずれか）
    """
    if not isinstance(button, str) or not button:
        return "left"

    b = button.strip().lower()
    aliases = {
        "left": "left",
        "right": "right",
        "middle": "middle",
        # pyautoguiが直接サポートしていない値のフォールバック
        "wheel": "middle",
        "back": "left",
        "forward": "left",
    }
    return aliases.get(b, "left")


def format_typed_text_for_log(text: str, *, max_chars: int = 200) -> str:
    """
    ログ出力用にタイプされたテキストをフォーマットします。
    
    改行をエスケープし、長すぎる場合は省略します。
    
    Args:
        text: フォーマットするテキスト
        max_chars: 最大文字数
    
    Returns:
        フォーマットされたテキスト
    """
    compact = text.replace("\r\n", "\n").replace("\r", "\n")
    compact = compact.replace("\n", "\\n")
    if len(compact) > max_chars:
        compact = compact[:max_chars] + "…"
    return compact


def scale_point(
    x: int,
    y: int,
    *,
    from_width: int,
    from_height: int,
    to_width: int,
    to_height: int,
) -> tuple[int, int]:
    """
    座標をあるディスプレイサイズから別のサイズにスケーリングします。
    
    モデルが返す座標（仮想ディスプレイサイズ）を
    実際の物理スクリーンの座標に変換する際に使用します。
    
    Args:
        x: 元のX座標
        y: 元のY座標
        from_width: 元のディスプレイ幅
        from_height: 元のディスプレイ高さ
        to_width: 変換先のディスプレイ幅
        to_height: 変換先のディスプレイ高さ
    
    Returns:
        スケーリングされた座標 (x, y)
    """
    sx = to_width / from_width
    sy = to_height / from_height
    return int(round(x * sx)), int(round(y * sy))
