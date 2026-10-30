"""
Cartoon video — truyện kể bằng hoạt hình 2D phẳng, nhân vật nói thoại, có phụ đề (9:16).

Kiểu "video giải thích TikTok": nền phòng ấm, nhân vật viền đậm đổi biểu cảm theo câu thoại,
miệng máy theo giờ từng chữ của edge-tts, phụ đề trắng viền đen ở 2/3 khung hình,
thỉnh thoảng chèn thẻ minh họa (bảng, ghi chú, bìa truyện).

Chạy thử:
    python -m skills.cartoon_video spec.json output.mp4
spec.json:
    {
      "title": "...", "brand": "Đọc Đêm",
      "characters": {
        "ba": {"look": "old_woman", "voice": "vi-VN-HoaiMyNeural", "pitch": "-6Hz",
               "skin": [250,214,180], "hair": [175,175,180], "shirt": [190,90,60],
               "clothes": "apron", "glasses": true, "flip": false,
               "room": "bep", "tag": "Bếp nhà cô Ba"},
        "narrator": {"voice": "vi-VN-HoaiMyNeural"}
      },
      "lines": [
        {"who": "ba", "text": "...", "emo": "neutral|happy|sad|surprised|worried|angry|teary"},
        {"who": "narrator", "text": "...", "card": {"kind": "grid|note|image", ...}}
      ]
    }
room: bep | phong | quan | xuong. look: man | woman | old_woman. clothes: hoodie | tee | apron | shirt.
"""

import asyncio
import json
import math
import os
import ssl
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import FONT_PATH
from skills.karaoke_video import _ssl_fix

W, H = 1080, 1920
FPS = 24
S = 2                                  # siêu mẫu khi vẽ nhân vật / nền cho mịn cạnh
PAD = 0.22
OUTLINE = (44, 28, 30)
SUB_Y = 1290                           # tâm khối phụ đề
HEAD = (540, 690)                      # tâm đầu khi cận cảnh


def _font(size):
    return ImageFont.truetype(FONT_PATH, size)


# ───────────────────────── nền ─────────────────────────

def _vignette(img: Image.Image, strength=0.55) -> Image.Image:
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / (W * .75)) ** 2 + ((yy - H * .48) / (H * .62)) ** 2)
    m = 1 - strength * np.clip(d - .35, 0, 1) ** 1.4
    return Image.fromarray((a * m[..., None]).clip(0, 255).astype(np.uint8))


def background(room: str) -> Image.Image:
    walls = {"bep": (122, 92, 70), "phong": (62, 96, 118), "quan": (56, 84, 82), "xuong": (112, 86, 70)}
    floors = {"bep": (150, 98, 62), "phong": (136, 98, 74), "quan": (152, 98, 56), "xuong": (140, 104, 70)}
    wall, floor = walls.get(room, walls["quan"]), floors.get(room, floors["quan"])
    im = Image.new("RGB", (W * S, H * S), wall)
    d = ImageDraw.Draw(im)
    s = S
    fy = 1170
    d.rectangle([0, 0, W * s, fy * s], fill=wall)
    dark = tuple(int(c * .88) for c in wall)
    d.rectangle([0, 820 * s, W * s, fy * s], fill=dark)                                  # tường dưới
    d.line([(0, 820 * s), (W * s, 820 * s)], fill=OUTLINE, width=6 * s)
    for x in (60, 400, 740):                                                              # ô ốp tường
        d.rectangle([x * s, 870 * s, (x + 280) * s, 1130 * s], outline=tuple(int(c * .75) for c in wall), width=5 * s)
    d.rectangle([0, fy * s, W * s, H * s], fill=floor)                                    # sàn gỗ
    d.line([(0, fy * s), (W * s, fy * s)], fill=OUTLINE, width=8 * s)
    for i in range(1, 9):
        y = fy + i * i * 14
        d.line([(0, y * s), (W * s, y * s)], fill=tuple(int(c * .82) for c in floor), width=4 * s)
    if room == "quan":
        d.rectangle([90 * s, 330 * s, 360 * s, 560 * s], fill=(52, 74, 70), outline=OUTLINE, width=9 * s)
        d.polygon([(130 * s, 520 * s), (230 * s, 400 * s), (290 * s, 470 * s), (320 * s, 430 * s), (340 * s, 520 * s)], fill=(96, 138, 116))
        d.line([(540 * s, 0), (540 * s, 240 * s)], fill=OUTLINE, width=5 * s)             # đèn thả
        d.polygon([(470 * s, 330 * s), (610 * s, 330 * s), (580 * s, 240 * s), (500 * s, 240 * s)], fill=(88, 124, 112), outline=OUTLINE)
    elif room == "bep":
        d.rectangle([700 * s, 300 * s, 1000 * s, 620 * s], fill=(214, 226, 230), outline=OUTLINE, width=10 * s)   # cửa sổ sương
        d.line([(850 * s, 300 * s), (850 * s, 620 * s)], fill=OUTLINE, width=8 * s)
        d.line([(700 * s, 460 * s), (1000 * s, 460 * s)], fill=OUTLINE, width=8 * s)
        d.rectangle([60 * s, 400 * s, 460 * s, 450 * s], fill=(118, 80, 52), outline=OUTLINE, width=7 * s)       # kệ
        for i, c in enumerate(((190, 80, 60), (230, 190, 90), (90, 140, 100), (200, 120, 70))):
            d.rounded_rectangle([(90 + i * 90) * s, 320 * s, (150 + i * 90) * s, 400 * s], 10 * s, fill=c, outline=OUTLINE, width=6 * s)
        d.rectangle([0, 1020 * s, W * s, 1140 * s], fill=(176, 126, 84), outline=OUTLINE, width=8 * s)             # bàn bếp
    elif room == "xuong":
        d.rectangle([60 * s, 300 * s, 1020 * s, 340 * s], fill=(96, 66, 46), outline=OUTLINE, width=7 * s)       # xà treo dụng cụ
        for i, x in enumerate((120, 260, 400)):                                                              # cưa, búa, thước
            d.line([(x * s, 340 * s), (x * s, (470 + 40 * (i % 2)) * s)], fill=OUTLINE, width=9 * s)
            d.rectangle([(x - 30) * s, (470 + 40 * (i % 2)) * s, (x + 30) * s, (520 + 40 * (i % 2)) * s], fill=(176, 176, 182), outline=OUTLINE, width=6 * s)
        for r in range(3):                                                                                   # giá ghế đẩu bên phải
            y = 420 + r * 190
            d.rectangle([700 * s, y * s, 1040 * s, (y + 22) * s], fill=(96, 66, 46), outline=OUTLINE, width=6 * s)
            for c in range(3):
                x = 720 + c * 105
                d.ellipse([x * s, (y - 46) * s, (x + 90) * s, (y - 6) * s], fill=(236, 180, 110), outline=OUTLINE, width=6 * s)
                d.line([((x + 12) * s), ((y - 12) * s), ((x - 2) * s), (y * s)], fill=OUTLINE, width=6 * s)
                d.line([((x + 78) * s), ((y - 12) * s), ((x + 92) * s), (y * s)], fill=OUTLINE, width=6 * s)
        d.polygon([(120 * s, 1100 * s), (200 * s, 1080 * s), (280 * s, 1100 * s), (240 * s, 1150 * s), (160 * s, 1150 * s)], fill=(226, 196, 140))  # đống mạt cưa
    else:  # phong
        d.rectangle([40 * s, 0, 330 * s, 900 * s], fill=(70, 110, 190), outline=OUTLINE, width=9 * s)           # rèm xanh
        for x in (110, 190, 260):
            d.line([(x * s, 0), (x * s, 900 * s)], fill=(54, 90, 160), width=7 * s)
        d.rectangle([760 * s, 980 * s, 980 * s, 1330 * s], fill=(226, 232, 236), outline=OUTLINE, width=9 * s)  # tủ lạnh nhỏ
        d.line([(760 * s, 1130 * s), (980 * s, 1130 * s)], fill=OUTLINE, width=6 * s)
        d.rectangle([420 * s, 300 * s, 640 * s, 520 * s], fill=(236, 214, 150), outline=OUTLINE, width=9 * s)    # tranh
        d.ellipse([480 * s, 350 * s, 580 * s, 450 * s], fill=(226, 120, 80))
    im = im.resize((W, H), Image.LANCZOS)
    return _vignette(im)


def _tag(img: Image.Image, text: str) -> Image.Image:
    if not text:
        return img
    d = ImageDraw.Draw(img, "RGBA")
    f = _font(40)
    w = d.textlength(text, font=f)
    x0, x1 = (W - w) / 2 - 36, (W + w) / 2 + 36
    d.rounded_rectangle([x0, 96, x1, 176], 40, fill=(30, 22, 24, 200))
    d.text((W / 2, 136), text, font=f, fill=(255, 236, 190), anchor="mm")
    return img


# ───────────────────────── nhân vật ─────────────────────────

def _poly(d, pts, cx, cy, fill, width=10):
    P = [((cx + x) * S, (cy + y - 150) * S) for x, y in pts]
    d.polygon(P, fill=fill, outline=OUTLINE, width=width * S)
    d.line(P + [P[0]], fill=OUTLINE, width=width * S, joint="curve")


def _ell(d, x0, y0, x1, y1, fill=None, width=10, outline=OUTLINE):
    d.ellipse([x0 * S, (y0 - 150) * S, x1 * S, (y1 - 150) * S], fill=fill, outline=outline, width=width * S if outline else 0)


def _line(d, pts, width=12, fill=OUTLINE):
    d.line([(x * S, (y - 150) * S) for x, y in pts], fill=fill, width=width * S, joint="curve")


def _arc(d, box, a0, a1, width=10, fill=OUTLINE):
    x0, y0, x1, y1 = box
    d.arc([x0 * S, (y0 - 150) * S, x1 * S, (y1 - 150) * S], a0, a1, fill=fill, width=width * S)


def _rrect(d, x0, y0, x1, y1, r, fill, width=10):
    d.rounded_rectangle([x0 * S, (y0 - 150) * S, x1 * S, (y1 - 150) * S], r * S, fill=fill, outline=OUTLINE, width=width * S)


HAIR_MALE = [(-252, -30), (-290, -150), (-215, -185), (-238, -290), (-140, -248), (-118, -345), (-40, -262), (12, -356),
             (72, -268), (150, -330), (168, -238), (252, -232), (236, -128), (256, -50), (205, -70), (165, -150),
             (100, -190), (22, -138), (-60, -186), (-140, -128), (-205, -96)]
HAIR_CAP = [(-256, -40), (-262, -190), (-160, -300), (0, -338), (160, -300), (262, -190), (256, -40), (196, -130),
            (70, -208), (-30, -178), (-140, -112), (-206, -60)]


def draw_character(spec: dict, emo: str, mouth: str, blink: bool) -> Image.Image:
    """Trả về RGBA đã thu nhỏ về W x (H-150) (vùng y=150..H), đã lật nếu cần."""
    skin = tuple(spec.get("skin", (250, 214, 180)))
    hair = tuple(spec.get("hair", (110, 70, 48)))
    shirt = tuple(spec.get("shirt", (60, 130, 90)))
    look = spec.get("look", "man")
    clothes = spec.get("clothes", "hoodie")
    skin_d = tuple(int(c * .9) for c in skin)
    layer = Image.new("RGBA", (W * S, (H - 150) * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = HEAD
    off = 42

    if look in ("woman", "old_woman"):                                         # tóc sau
        if look == "woman":
            _ell(d, cx - 295, cy - 310, cx + 295, cy + 470, hair)
        else:
            _ell(d, cx - 95, cy - 440, cx + 95, cy - 250, hair)                # búi
    _rrect(d, cx - 70, cy + 200, cx + 70, cy + 380, 30, skin_d)                # cổ
    _rrect(d, cx - 400, cy + 330, cx + 400, cy + 1500, 160, shirt)             # thân
    if clothes == "hoodie":
        _line(d, [(cx - 45, cy + 400), (cx - 50, cy + 560)], 14, (240, 230, 205))
        _line(d, [(cx + 45, cy + 400), (cx + 48, cy + 560)], 14, (240, 230, 205))
        _arc(d, (cx - 130, cy + 290, cx + 130, cy + 470), 20, 160, 14)
    elif clothes == "apron":
        _rrect(d, cx - 230, cy + 470, cx + 230, cy + 1500, 60, (236, 224, 196))
        _line(d, [(cx - 230, cy + 480), (cx - 120, cy + 340)], 16)
        _line(d, [(cx + 230, cy + 480), (cx + 120, cy + 340)], 16)
    elif clothes == "shirt":
        _poly(d, [(-95, 330), (0, 470), (95, 330), (60, 310), (0, 390), (-60, 310)], cx, cy, (245, 245, 240), 8)
    else:
        _arc(d, (cx - 120, cy + 270, cx + 120, cy + 440), 20, 160, 14)
    _ell(d, cx - 245, cy - 265, cx + 245, cy + 265, skin)                      # đầu
    _ell(d, cx - 282, cy - 25, cx - 205, cy + 70, skin_d, 9)                   # tai
    if look == "man":
        _poly(d, HAIR_MALE, cx, cy, hair)
    else:
        _poly(d, HAIR_CAP, cx, cy, hair)

    ex1, ex2, ey = cx - 95 + off, cx + 95 + off, cy - 30
    if emo == "surprised":
        for ex in (ex1, ex2):
            _ell(d, ex - 40, ey - 46, ex + 40, ey + 46, (255, 255, 255), 8)
            _ell(d, ex - 14, ey - 18, ex + 14, ey + 18, OUTLINE, 0, None)
    elif blink or emo == "sleep":
        for ex in (ex1, ex2):
            _arc(d, (ex - 30, ey - 18, ex + 30, ey + 22), 20, 160, 9)
    else:
        for ex in (ex1, ex2):
            _ell(d, ex - 19, ey - 28, ex + 19, ey + 28, OUTLINE, 0, None)
            _ell(d, ex + 2, ey - 18, ex + 14, ey - 6, (255, 255, 255), 0, None)
    if spec.get("glasses"):
        for ex in (ex1, ex2):
            _ell(d, ex - 66, ey - 66, ex + 66, ey + 66, None, 7)
        _line(d, [(ex1 + 66, ey - 5), (ex2 - 66, ey - 5)], 7)
    by = ey - 82 - (28 if emo == "surprised" else 0)                            # lông mày
    sl = {"sad": 28, "worried": 22, "teary": 30, "angry": -26}.get(emo, 0)
    arch = 12 if emo in ("happy", "surprised") else 0
    _line(d, [(ex1 - 48, by + sl * .0 + (sl * .8 if sl > 0 else 0)), (ex1, by - arch), (ex1 + 48, by - sl * .9 if sl > 0 else by + abs(sl) * .9)], 14, hair if look != "old_woman" else (120, 120, 126))
    _line(d, [(ex2 - 48, by - sl * .9 if sl > 0 else by + abs(sl) * .9), (ex2, by - arch), (ex2 + 48, by + (sl * .8 if sl > 0 else 0))], 14, hair if look != "old_woman" else (120, 120, 126))
    _line(d, [(cx + off + 30, cy + 20), (cx + off + 52, cy + 62), (cx + off + 22, cy + 66)], 9)   # mũi
    if emo in ("happy", "teary", "worried"):
        _ell(d, ex1 - 70, ey + 60, ex1 - 10, ey + 100, (240, 150, 140), 0, None)
    if emo == "teary":
        _ell(d, ex1 - 40, ey + 40, ex1 - 6, ey + 100, (130, 190, 240), 7)
        _ell(d, ex2 + 10, ey + 45, ex2 + 44, ey + 105, (130, 190, 240), 7)

    mx, my = cx + off, cy + 140
    closed = {"happy": "smile", "sad": "frown", "teary": "frown", "worried": "frown",
              "angry": "flat", "surprised": "o"}.get(emo, "flat" if look == "man" else "smile_small")
    shape = mouth if mouth != "closed" else closed
    if shape == "smile":
        _arc(d, (mx - 70, my - 40, mx + 70, my + 50), 15, 165, 11)
    elif shape == "smile_small":
        _arc(d, (mx - 50, my - 25, mx + 50, my + 35), 20, 160, 10)
    elif shape == "frown":
        _arc(d, (mx - 55, my + 5, mx + 55, my + 65), 200, 340, 11)
    elif shape == "flat":
        _line(d, [(mx - 48, my + 18), (mx + 48, my + 18)], 11)
    elif shape == "o":
        _ell(d, mx - 28, my - 8, mx + 28, my + 52, (120, 40, 40), 9)
    elif shape == "open":
        _ell(d, mx - 52, my - 26, mx + 52, my + 62, (120, 40, 44), 10)
        _ell(d, mx - 28, my + 24, mx + 28, my + 58, (226, 110, 120), 0, None)
    else:  # open_small
        _ell(d, mx - 34, my - 14, mx + 34, my + 40, (120, 40, 44), 10)
        _ell(d, mx - 18, my + 14, mx + 18, my + 38, (226, 110, 120), 0, None)

    out = layer.resize((W, H - 150), Image.LANCZOS)
    if spec.get("flip"):
        out = out.transpose(Image.FLIP_LEFT_RIGHT)
    return out


# ───────────────────────── thẻ minh họa ─────────────────────────

def card_frame(card: dict, room: str) -> Image.Image:
    img = background(room).convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 120))
    img = Image.alpha_composite(img, ov)
    d = ImageDraw.Draw(img, "RGBA")
    kind = card.get("kind", "note")
    title = card.get("title", "")
    if kind == "image" and card.get("path"):
        pic = Image.open(card["path"]).convert("RGB")
        tw = 560
        pic = pic.resize((tw, int(pic.height * tw / pic.width)), Image.LANCZOS)
        x0, y0 = (W - tw) // 2, 190
        d.rounded_rectangle([x0 - 18, y0 - 18, x0 + tw + 18, y0 + pic.height + 18], 26, fill=(250, 240, 220), outline=OUTLINE, width=8)
        img.paste(pic, (x0, y0))
        return img.convert("RGB")
    if kind == "grid":
        n = card.get("n", 3)
        d.rounded_rectangle([140, 380, 940, 1180], 30, fill=(48, 44, 52, 255), outline=OUTLINE, width=10)
        d.rounded_rectangle([190, 340, 890, 430], 14, fill=(244, 200, 80), outline=OUTLINE, width=8)
        d.text((540, 385), title, font=_font(46), fill=OUTLINE, anchor="mm")
        cell, gap = 190, 18
        x0 = 540 - (n * cell + (n - 1) * gap) / 2
        for r in range(n):
            for c in range(n):
                xa, ya = x0 + c * (cell + gap), 470 + r * (cell + gap)
                d.rounded_rectangle([xa, ya, xa + cell, ya + cell], 16, fill=(244, 232, 210))
                d.text((xa + cell / 2, ya + cell / 2), card.get("mark", "?"), font=_font(100), fill=(192, 70, 60), anchor="mm")
    else:  # note
        d.rounded_rectangle([160, 420, 920, 1100], 24, fill=(246, 236, 208), outline=OUTLINE, width=10)
        d.rounded_rectangle([210, 370, 870, 470], 14, fill=(244, 200, 80), outline=OUTLINE, width=8)
        d.text((540, 420), title, font=_font(46), fill=OUTLINE, anchor="mm")
        f = _font(54)
        y = 560
        for ln in card.get("lines", []):
            d.text((540, y), ln, font=f, fill=(70, 50, 40), anchor="mm")
            y += 100
    return img.convert("RGB")


# ───────────────────────── phụ đề ─────────────────────────

def subtitle_overlay(text: str) -> Image.Image:
    f = _font(66)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) > 880 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    lines.append(cur)
    lh = 86
    y = SUB_Y - (len(lines) - 1) * lh / 2
    for ln in lines:
        d.text((W / 2, y), ln, font=f, fill=(255, 255, 255), anchor="mm", stroke_width=9, stroke_fill=(0, 0, 0))
        y += lh
    return lay


# ───────────────────────── tổng hợp ─────────────────────────

async def _tts(text, voice, rate, pitch, mp3: Path):
    import edge_tts
    _ssl_fix()
    com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
    words = []
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append((ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7))
    return words


def _mouth_at(t, words, emo):
    for s, e in words:
        if s - 0.02 <= t <= e + 0.04:
            ph = int((t - s) / 0.11) % 3
            return ("open", "open_small", "open_small")[ph] if emo != "sad" else "open_small"
    return "closed"


def _blink_at(t):
    return (t % 3.4) < 0.13 and t > 0.4


async def build(spec: dict, out_path: str) -> dict:
    from moviepy import AudioClip, AudioFileClip, VideoClip, concatenate_audioclips, concatenate_videoclips

    chars = spec["characters"]
    work = Path(tempfile.mkdtemp(prefix="cartoon_"))
    lines = spec["lines"]
    results = await asyncio.gather(*[
        _tts(l["text"], chars[l["who"]]["voice"], l.get("rate", "-2%"), chars[l["who"]].get("pitch", "+0Hz"), work / f"v{i}.mp3")
        for i, l in enumerate(lines)])

    bgs: dict[str, Image.Image] = {}
    silence = lambda d: AudioClip(lambda t: np.zeros((np.size(t), 2)), duration=d, fps=44100)
    clips, parts = [], []
    for i, (l, words) in enumerate(zip(lines, results)):
        audio = AudioFileClip(str(work / f"v{i}.mp3"))
        dur = audio.duration + PAD
        who = chars[l["who"]]
        emo = l.get("emo", "neutral")
        room = who.get("room", "quan")
        sub = subtitle_overlay(l["text"])
        if l.get("card"):
            base_still = np.asarray(card_frame(l["card"], l.get("card_room", room)))
            cache = {}
        else:
            if room not in bgs:
                bgs[room] = background(room)
            cache = {}
            tag_bg = _tag(bgs[room].copy(), who.get("tag", ""))

        def frame_at(t, l=l, who=who, emo=emo, words=words, tag_bg=(tag_bg if not l.get("card") else None),
                     still=(base_still if l.get("card") else None), cache=cache, dur=dur, sub=sub):
            if still is not None:
                base = Image.fromarray(still)
            else:
                key = (_mouth_at(t, words, emo), _blink_at(t))
                if key not in cache:
                    ch = draw_character(who, emo, key[0], key[1])
                    im = tag_bg.convert("RGBA")
                    im.alpha_composite(ch, (0, 150))
                    cache[key] = im.convert("RGB")
                base = cache[key]
            z = 1.03 + 0.035 * min(1, t / dur)
            bw, bh = W / z, H / z
            l0 = (W - bw) / 2
            t0 = min(max((H - bh) * 0.35 + 7 * math.sin(2 * math.pi * t / 1.9), 0), H - bh)
            fr = base.resize((W, H), Image.BILINEAR, box=(l0, t0, l0 + bw, t0 + bh)).convert("RGBA")
            fr.alpha_composite(sub)
            return np.asarray(fr.convert("RGB"))

        clips.append(VideoClip(frame_at, duration=dur).with_fps(FPS))
        parts += [audio, silence(PAD)]

    video = concatenate_videoclips(clips, method="chain")
    video = video.with_audio(concatenate_audioclips(parts))
    video.write_videofile(out_path, fps=FPS, codec="libx264", audio_codec="aac",
                          bitrate="3500k", preset="fast", logger=None)
    return {"video_path": out_path, "duration": video.duration, "work_dir": str(work)}


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(asyncio.run(build(spec, sys.argv[2])))
