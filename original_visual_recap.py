"""Generate original abstract title cards when no reusable footage is available.

These visuals are procedurally drawn by NEXORA. They are not screenshots,
fan art, or representations of official scenes from the requested work.
"""
from __future__ import annotations

from io import BytesIO
import re

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1280
HEIGHT = 720
PALETTES = [
    ((10, 18, 38), (27, 74, 104), (80, 184, 190)),
    ((24, 16, 48), (71, 48, 108), (192, 112, 154)),
    ((9, 34, 44), (24, 91, 100), (116, 196, 162)),
    ((35, 22, 40), (105, 51, 70), (223, 143, 104)),
    ((12, 25, 52), (40, 64, 117), (139, 164, 224)),
    ((26, 26, 32), (74, 75, 88), (184, 177, 151)),
    ((12, 35, 45), (35, 91, 100), (124, 190, 185)),
    ((23, 18, 42), (78, 57, 98), (179, 145, 201)),
]


def _font(size: int):
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _safe_display_title(title: str) -> str:
    clean = " ".join(str(title or "").split())[:90]
    # Use a predictable ASCII title on hosts without a Myanmar-capable font.
    if not clean or not clean.isascii():
        return "NEXORA STORY RECAP"
    return clean


def build_original_visual_cards(title: str, count: int = 8) -> list[tuple[str, bytes]]:
    """Return PNG cards with original abstract art and a clear provenance label."""
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 12:
        raise ValueError("Original visual card အရေအတွက်သည် 1 မှ 12 အတွင်း ဖြစ်ရပါမယ်။")
    display_title = _safe_display_title(title)
    title_font = _font(48)
    label_font = _font(22)
    cards = []
    for index in range(count):
        dark, mid, accent = PALETTES[index % len(PALETTES)]
        image = Image.new("RGB", (WIDTH, HEIGHT), dark)
        draw = ImageDraw.Draw(image, "RGBA")
        # Large layered geometry creates an original visual backdrop without
        # borrowing imagery from the film, series, or third-party creators.
        draw.ellipse((650 + index * 17, -210, 1390 + index * 11, 530),
                     fill=(*mid, 170), outline=(*accent, 150), width=5)
        draw.ellipse((780 - index * 9, 70, 1240 - index * 7, 530),
                     outline=(*accent, 130), width=7)
        draw.arc((120, 80, 900, 860), start=195 + index * 8, end=335 + index * 8,
                 fill=(*accent, 180), width=5)
        for ring in range(5):
            x = 80 + ring * 52 + index * 13
            draw.line((x, 500, x + 180, 330 - ring * 20),
                      fill=(*accent, 65), width=3)
        draw.rounded_rectangle((64, 70, 1216, 650), radius=34,
                               outline=(255, 255, 255, 45), width=2)
        draw.text((104, 112), "NEXORA  /  ORIGINAL VISUALS",
                  font=label_font, fill=(235, 242, 250, 220))
        # Keep the requested work title visible while avoiding unsupported
        # glyph substitution on minimal Linux hosts.
        title_text = display_title
        bbox = draw.textbbox((0, 0), title_text, font=title_font)
        while bbox[2] - bbox[0] > 1060 and len(title_text) > 12:
            title_text = title_text[:-4] + "..."
            bbox = draw.textbbox((0, 0), title_text, font=title_font)
        draw.text((104, 300), title_text, font=title_font,
                  fill=(255, 255, 255, 245), stroke_width=1,
                  stroke_fill=(0, 0, 0, 80))
        draw.text((104, 590), "ABSTRACT BACKGROUND  •  NOT OFFICIAL FOOTAGE",
                  font=label_font, fill=(230, 235, 245, 190))
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        cards.append((f"nexora_original_visual_{index + 1:02d}.png", buffer.getvalue()))
    return cards
