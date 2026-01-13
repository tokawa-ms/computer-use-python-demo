"""
画像処理モジュール

スクリーンショットの撮影、アノテーション、画像変換などの画像関連機能を提供します。
"""

import base64
import mimetypes
import os
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageGrab

from .config import (
    ANNOTATION_MAX_CHARS,
    SEND_ANNOTATED_IMAGE_TO_MODEL,
    SHOW_TYPED_TEXT_IN_ANNOTATION,
)
from .utils import format_typed_text_for_log, normalize_key_name


def image_file_to_data_url(
    image_path: os.PathLike | str, *, default_mime: str = "image/png"
) -> str:
    """
    画像ファイルをData URLに変換します。
    
    Args:
        image_path: 画像ファイルのパス
        default_mime: デフォルトのMIMEタイプ
    
    Returns:
        Data URL形式の文字列
    
    Raises:
        FileNotFoundError: 画像ファイルが存在しない場合
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")

    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type:
        mime_type = default_mime

    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def capture_fullscreen_screenshot(*, screenshots_dir: os.PathLike | str) -> Path:
    """
    フルスクリーンのスクリーンショットを撮影します。
    
    プライマリスクリーンのスクリーンショットを撮影し、
    タイムスタンプを含むファイル名で保存します。
    
    Args:
        screenshots_dir: スクリーンショットの保存先ディレクトリ
    
    Returns:
        保存されたスクリーンショットのパス
    """
    out_dir = Path(screenshots_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # YYYYmmdd_HHMMSS_mmm.png 形式のタイムスタンプ
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    out_path = out_dir / f"{ts}.png"

    # プライマリスクリーンをキャプチャ
    # (all_screens=True を使用すると、マルチモニター環境で
    # クリック座標とのマッピングが困難になる可能性があります)
    img = ImageGrab.grab()
    img.save(out_path)
    return out_path


def get_primary_screen_size() -> tuple[int, int]:
    """
    プライマリスクリーンのサイズを取得します。
    
    Returns:
        (幅, 高さ) のタプル
    """
    img = ImageGrab.grab()
    return img.size


def annotate_click_points(
    image_path: os.PathLike | str,
    points: list[tuple[int, int]],
    *,
    output_path: os.PathLike | str | None = None,
    display_width: int | None = None,
    display_height: int | None = None,
) -> Path:
    """
    画像にクリックポイントのアノテーションを追加します。
    
    クリックされた位置に円と十字線を描画します。
    
    Args:
        image_path: 元の画像のパス
        points: クリックポイントのリスト [(x, y), ...]
        output_path: 出力ファイルのパス（None の場合は自動生成）
        display_width: ディスプレイ幅（スケーリング用）
        display_height: ディスプレイ高さ（スケーリング用）
    
    Returns:
        アノテーション付き画像のパス
    """
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

            # 画像サイズに応じた円の半径を計算
            r = max(10, int(min(img.width, img.height) * 0.012))
            
            # 円を描画
            draw.ellipse(
                (px - r, py - r, px + r, py + r), outline=(255, 0, 0, 255), width=5
            )
            # 十字線を描画
            draw.line((px - r * 2, py, px + r * 2, py), fill=(255, 0, 0, 255), width=3)
            draw.line((px, py - r * 2, px, py + r * 2), fill=(255, 0, 0, 255), width=3)

        img.save(dst)

    return dst


def annotate_text(
    image_path: os.PathLike | str,
    note: str,
    *,
    output_path: os.PathLike | str | None = None,
) -> Path:
    """
    画像にテキストアノテーションを追加します。
    
    画像の左上隅に半透明の黒背景でテキストを描画します。
    
    Args:
        image_path: 元の画像のパス
        note: 追加するテキスト
        output_path: 出力ファイルのパス（None の場合は自動生成）
    
    Returns:
        アノテーション付き画像のパス
    """
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

        # 画像サイズに応じたマージンとパディングを計算
        margin = max(10, int(min(img.width, img.height) * 0.01))
        pad = max(8, int(min(img.width, img.height) * 0.008))

        # テキストのバウンディングボックスを計算
        bbox = draw.multiline_textbbox((0, 0), text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x0 = margin
        y0 = margin
        x1 = min(img.width - margin, x0 + tw + pad * 2)
        y1 = min(img.height - margin, y0 + th + pad * 2)

        # 半透明の背景を描画
        draw.rectangle((x0, y0, x1, y1), fill=(0, 0, 0, 170))
        # テキストを描画
        draw.multiline_text((x0 + pad, y0 + pad), text, fill=(255, 255, 255, 255))

        composed = Image.alpha_composite(img, overlay)
        composed.save(dst)

    return dst


def choose_model_image(clean: Path, annotated: Path | None = None) -> Path:
    """
    モデルに送信する画像を選択します。
    
    設定に基づいて、クリーンな画像またはアノテーション付き画像を選択します。
    
    Args:
        clean: クリーンな画像のパス
        annotated: アノテーション付き画像のパス
    
    Returns:
        選択された画像のパス
    """
    if SEND_ANNOTATED_IMAGE_TO_MODEL and annotated is not None:
        return annotated
    return clean


def summarize_typed_text(text: str) -> str:
    """
    タイプされたテキストをアノテーション用に要約します。
    
    設定に応じて、テキストの内容を表示するか、文字数のみを表示します。
    
    Args:
        text: タイプされたテキスト
    
    Returns:
        アノテーション用の要約文字列
    """
    if not SHOW_TYPED_TEXT_IN_ANNOTATION:
        return f"type: {len(text)} chars"

    compact = text.replace("\r\n", "\n").replace("\r", "\n")
    compact = compact.replace("\n", "\\n")
    if len(compact) > ANNOTATION_MAX_CHARS:
        compact = compact[:ANNOTATION_MAX_CHARS] + "…"
    return f"type: '{compact}'"


def summarize_keypress(keys: list[str]) -> str:
    """
    キープレスをアノテーション用に要約します。
    
    Args:
        keys: キーのリスト
    
    Returns:
        アノテーション用の要約文字列
    """
    norm = [normalize_key_name(k) for k in keys if isinstance(k, str) and k.strip()]
    if not norm:
        return "keypress: (empty)"
    joined = "+".join(norm)
    if len(joined) > ANNOTATION_MAX_CHARS:
        joined = joined[:ANNOTATION_MAX_CHARS] + "…"
    return f"keypress: {joined}"


def extract_click_points(response_output: list) -> list[tuple[int, int]]:
    """
    レスポンスからクリックポイントを抽出します。
    
    Args:
        response_output: APIレスポンスの出力リスト
    
    Returns:
        クリックポイントのリスト [(x, y), ...]
    """
    points: list[tuple[int, int]] = []
    for item in response_output:
        if getattr(item, "type", None) != "computer_call":
            continue
        
        action = getattr(item, "action", None)
        if getattr(action, "type", None) != "click":
            continue

        x = getattr(action, "x", None)
        y = getattr(action, "y", None)
        if isinstance(x, int) and isinstance(y, int):
            points.append((x, y))

    return points
