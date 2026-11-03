"""
Explainer video, kiểu "người que + thẻ tiêu đề + phụ đề tô vàng" (9:16), một giọng dẫn.

Phân tích video mẫu (banlinhmem):
  1. Nền pastel phẳng, đổi màu theo từng ý (mint, đào, tím nhạt, kem, hồng, xanh lá, xanh dương), đoạn cuối nền tối.
  2. Nhân vật người que đen: đầu tròn, hai chấm mắt trắng, thân bo tròn, tay chân dày; 1 đến 3 người, một người có thể
     đổi sang màu nhấn (hồng) kèm vòng tròn / tam giác mờ để nhấn mạnh.
  3. Mỗi ý có một thẻ tiêu đề trắng viền mảnh, chữ hoa đậm màu nhấn của cảnh, dấu "=" nhỏ bên dưới.
  4. Icon minh họa đơn giản (đồng hồ, trái tim + tiền, bóng đèn, cầu thang, cửa, cây, bong bóng nói / nghĩ).
  5. Phụ đề: khối trắng bo tròn, chữ đậm, 1 đến 2 dòng, từ khóa tô vàng như bút dạ; mỗi cụm 3 đến 6 chữ.
  6. Nhịp: cảnh đổi mỗi 4 đến 8 giây, một giọng dẫn duy nhất, thanh tiến độ mỏng ở mép trên.

Chạy:
    python -m skills.explainer_video spec.json out.mp4
spec.json:
    {"handle": "@tmadoc", "voice": "vi-VN-HoaiMyNeural", "rate": "-2%", "pitch": "+0Hz",
     "scenes": [
       {"text": "Nhiều khi *không phải bạn* nói quá nhiều.", "title": "ĐÓN LẤY CÂU CHUYỆN", "palette": "mint",
        "equals": true, "figures": [{"x": 0.3, "pose": "stand"}, {"x": 0.7, "pose": "point_l"}],
        "props": [{"kind": "clock", "x": 0.5, "y": 0.45, "size": 0.2}],
        "bubble": {"kind": "thought", "text": "Phải nói gì?", "x": 0.55, "y": 0.3},
        "audio": "tuỳ chọn: tệp giọng thu sẵn cho cảnh này"}]}
*từ khóa* trong text sẽ được tô vàng ở phụ đề. palette: mint, peach, lavender, cream, pink, green, blue, dark.
pose: stand, point_r, point_l, wave, hands_up, shrug, think, sad. figure: color "black" | "accent", scale, halo.
prop.kind: clock, heart, coin, bulb, stairs, door, window, plant, phone, house, cup, letter, question, none.
"""

import asyncio
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import ASSETS_DIR
from skills.cartoon_video import _tts, _words_from_audio

W, H = 1080, 1920
FPS = 24
S = 2
BOLD = str(Path(ASSETS_DIR) / "font_bold.ttf")
INK = (22, 22, 28)
GROUND = 0.70                      # đường chân nhân vật, tỉ lệ chiều cao
SUB_Y = 0.80                       # tâm phụ đề

PALETTES = {                       # (nền trên, nền dưới, màu nhấn)
    "mint": ((214, 236, 230), (180, 214, 208), (18, 104, 96)),
    "peach": ((250, 230, 214), (236, 206, 188), (150, 48, 40)),
    "lavender": ((228, 224, 248), (204, 198, 232), (58, 44, 140)),
    "cream": ((250, 242, 204), (234, 222, 170), (120, 92, 24)),
    "pink": ((252, 224, 232), (240, 196, 210), (176, 36, 84)),
    "green": ((228, 242, 214), (198, 224, 184), (46, 106, 46)),
    "blue": ((218, 236, 252), (186, 212, 240), (28, 84, 160)),
    "dark": ((18, 30, 44), (8, 14, 24), (230, 240, 250)),
}
ORDER = ["mint", "peach", "lavender", "cream", "pink", "green", "blue"]


def _font(size):
    return ImageFont.truetype(BOLD, size)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ───────────────────────── nền, thẻ, phụ đề ─────────────────────────

def background(pal):
    top, bot, _ = PALETTES[pal]
    col = np.zeros((H, 1, 3), np.float32)
    for y in range(H):
        col[y, 0] = _lerp(top, bot, y / H)
    img = np.repeat(col, W, axis=1)
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / (W * .75)) ** 2 + ((yy - H / 2) / (H * .7)) ** 2)
    img *= (1 - 0.10 * np.clip(d, 0, 1.2))[..., None]
    return Image.fromarray(np.clip(img, 0, 255).astype("uint8"))


def title_card(text, accent, scale=1.0, dark=False):
    f = _font(78)
    lines = text.split("\n") if "\n" in text else _wrap(text, f, 800)
    lh = 96
    w = max(int(f.getlength(l)) for l in lines) + 120
    h = lh * len(lines) + 70
    im = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fillc = (28, 44, 62, 255) if dark else (252, 252, 250, 255)
    d.rounded_rectangle([0, 0, w * 2 - 1, h * 2 - 1], 22, fill=fillc, outline=accent + (255,), width=6)
    f2 = _font(156)
    for i, l in enumerate(lines):
        d.text((w, (35 + lh * i + lh / 2) * 2), l, font=f2, fill=accent, anchor="mm")
    im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return im


def _wrap(text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if font.getlength(t) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w_
    if cur:
        lines.append(cur)
    return lines


def equals_sign(accent):
    im = Image.new("RGBA", (120, 70), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for y in (12, 44):
        d.rounded_rectangle([10, y, 110, y + 16], 8, fill=accent + (255,))
    return im


def parse_marks(text):
    """'a *b c* d' -> [(word, hi)]"""
    out, hi = [], False
    for tok in text.replace("*", " * ").split():
        if tok == "*":
            hi = not hi
        else:
            out.append((tok, hi))
    return out


def chunks_from_words(words, max_words=5):
    out, cur = [], []
    for w_, hi in words:
        cur.append((w_, hi))
        if len(cur) >= max_words or w_.endswith((".", "?", "!", ",", ";")) and len(cur) >= 3:
            out.append(cur); cur = []
    if cur:
        if out and len(cur) <= 1:
            out[-1] += cur
        else:
            out.append(cur)
    return out


def subtitle_img(chunk):
    f = _font(60)
    words = chunk
    lines, cur = [], []
    for w_, hi in words:
        t = " ".join(x[0] for x in cur + [(w_, hi)])
        if f.getlength(t) > 780 and cur:
            lines.append(cur); cur = [(w_, hi)]
        else:
            cur.append((w_, hi))
    lines.append(cur)
    lh = 92
    bw = max(int(f.getlength(" ".join(x[0] for x in l))) for l in lines) + 96
    bh = lh * len(lines) + 36
    im = Image.new("RGBA", (bw * 2, bh * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, bw * 2 - 1, bh * 2 - 1], 28, fill=(255, 255, 255, 250))
    f2 = _font(120)
    sp = f2.getlength(" ")
    for i, l in enumerate(lines):
        tw = sum(f2.getlength(x[0]) for x in l) + sp * (len(l) - 1)
        x = bw - tw / 2
        cy = (18 + lh * i + lh / 2) * 2
        for w_, hi in l:
            ww = f2.getlength(w_)
            if hi:
                d.rounded_rectangle([x - 12, cy - 54, x + ww + 12, cy + 62], 16, fill=(255, 226, 64, 255))
            d.text((x, cy), w_, font=f2, fill=(20, 20, 24), anchor="lm")
            x += ww + sp
    return im.resize((bw, bh), Image.LANCZOS)


# ───────────────────────── người que ─────────────────────────

POSES = {                     # tay trái, tay phải: [góc cánh tay trên, góc cẳng tay], 0 = thả xuống, 90 = ngang, 180 = giơ lên
    "stand": ([6, 0], [6, 0], 0),
    "point_r": ([6, 0], [80, 84], 0),
    "point_l": ([80, 84], [6, 0], 0),
    "wave": ([6, 0], [55, 165], 0),
    "hands_up": ([150, 172], [150, 172], 0),
    "shrug": ([52, 100], [52, 100], 0),
    "think": ([6, 0], [24, 150], 4),
    "sad": ([3, 0], [3, 0], 12),
}


def _arm(d, cx, sy, a1, a2, side, L1, L2, w, col):
    ang = math.radians(a1)
    x1 = cx + side * math.sin(ang) * L1
    y1 = sy + math.cos(ang) * L1
    d.line([(cx, sy), (x1, y1)], fill=col, width=w)
    d.ellipse([x1 - w / 2, y1 - w / 2, x1 + w / 2, y1 + w / 2], fill=col)
    if a2:
        ang2 = math.radians(a2)
        x2 = x1 + side * math.sin(ang2) * L2
        y2 = y1 + math.cos(ang2) * L2
        d.line([(x1, y1), (x2, y2)], fill=col, width=w)
        d.ellipse([x2 - w / 2, y2 - w / 2, x2 + w / 2, y2 + w / 2], fill=col)
    d.ellipse([cx - w / 2, sy - w / 2, cx + w / 2, sy + w / 2], fill=col)


def figure_image(pose, height, color, bob=0.0):
    """Trả ảnh RGBA cao `height` px, rộng ~0.9*height. Neo chân ở đáy ảnh."""
    h = height * S
    Wf = int(h * 0.95)
    im = Image.new("RGBA", (Wf, int(h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = Wf / 2
    col = color + (255,)
    L, R, tilt = POSES.get(pose, POSES["stand"])
    hr = 0.085 * h
    hy = 0.10 * h + tilt * 0.002 * h
    ty, by = 0.20 * h, 0.52 * h
    tw = 0.21 * h
    lw = 0.075 * h
    # chân
    for sx in (-1, 1):
        x = cx + sx * 0.055 * h
        d.rounded_rectangle([x - lw / 2, by - 0.04 * h, x + lw / 2, h - 2], lw / 2, fill=col)
    # thân
    d.rounded_rectangle([cx - tw / 2, ty, cx + tw / 2, by], tw * 0.28, fill=col)
    # tay
    aw = int(0.062 * h)
    sy = ty + 0.04 * h
    _arm(d, cx - tw / 2 + aw * .35, sy, L[0], L[1], -1, 0.17 * h, 0.15 * h, aw, col)
    _arm(d, cx + tw / 2 - aw * .35, sy, R[0], R[1], 1, 0.17 * h, 0.15 * h, aw, col)
    # đầu
    d.ellipse([cx - hr, hy - hr, cx + hr, hy + hr], fill=col)
    er = 0.011 * h
    ey = hy + 0.008 * h
    for sx in (-1, 1):
        d.ellipse([cx + sx * 0.032 * h - er, ey - er, cx + sx * 0.032 * h + er, ey + er], fill=(255, 255, 255, 255))
    return im.resize((int(Wf / S), int(h / S)), Image.LANCZOS)


def halo(size, accent):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(size / 2, 0), (size * 0.98, size * 0.96), (size * 0.02, size * 0.96)], fill=accent + (60,))
    d.ellipse([size * .1, size * .15, size * .9, size * .95], fill=accent + (80,))
    return im


# ───────────────────────── icon ─────────────────────────

def prop_image(kind, size, accent):
    s = int(size * 2)
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = accent + (255,)
    w = max(6, s // 28)
    m = s // 2
    if kind == "clock":
        d.ellipse([s * .08, s * .08, s * .92, s * .92], outline=c, width=w * 2)
        d.line([(m, m), (m, s * .26)], fill=c, width=w, joint="curve")
        d.line([(m, m), (s * .68, m)], fill=c, width=w)
        d.ellipse([m - w, m - w, m + w, m + w], fill=c)
    elif kind == "heart":
        pts = []
        for i in range(0, 360, 4):
            t = math.radians(i)
            pts.append((m + 16 * math.sin(t) ** 3 * s / 40,
                        m * 0.95 - (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) * s / 40))
        d.polygon(pts, fill=(235, 90, 120, 255))
    elif kind == "coin":
        for k in range(3):
            y = s * (.62 - .17 * k)
            d.ellipse([s * .2, y, s * .8, y + s * .2], fill=(244, 186, 40, 255), outline=(150, 100, 10, 255), width=w)
        d.text((m, s * .32), "$", font=_font(int(s * .3)), fill=(150, 100, 10, 255), anchor="mm")
    elif kind == "bulb":
        d.ellipse([s * .25, s * .12, s * .75, s * .62], fill=(70, 150, 240, 255))
        d.rounded_rectangle([s * .38, s * .6, s * .62, s * .78], w, fill=(120, 130, 140, 255))
        for a in range(-60, 61, 30):
            r = math.radians(a - 90)
            d.line([(m + math.cos(r) * s * .34, s * .37 + math.sin(r) * s * .34), (m + math.cos(r) * s * .46, s * .37 + math.sin(r) * s * .46)], fill=(70, 150, 240, 255), width=w)
    elif kind == "stairs":
        for k in range(4):
            d.rectangle([s * (.15 + .17 * k), s * (.78 - .16 * k), s * (.32 + .17 * k), s * .9], fill=(244, 176, 30, 255))
        d.arc([s * .1, s * .08, s * .6, s * .7], 200, 320, fill=(244, 176, 30, 255), width=w)
    elif kind == "door":
        d.polygon([(s * .3, s * .08), (s * .78, s * .16), (s * .78, s * .92), (s * .3, s * .92)], fill=(255, 255, 255, 120), outline=(110, 110, 120, 200))
    elif kind == "window":
        d.rectangle([s * .2, s * .1, s * .8, s * .7], fill=(255, 255, 255, 140), outline=(110, 110, 120, 220), width=w)
        d.line([(m, s * .1), (m, s * .7)], fill=(110, 110, 120, 220), width=w)
        d.line([(s * .2, s * .4), (s * .8, s * .4)], fill=(110, 110, 120, 220), width=w)
    elif kind == "plant":
        d.rounded_rectangle([s * .35, s * .6, s * .65, s * .92], w, fill=(190, 150, 120, 255))
        for a, ln in ((-40, .4), (0, .5), (40, .4)):
            r = math.radians(a - 90)
            d.line([(m, s * .6), (m + math.cos(r) * s * ln, s * .6 + math.sin(r) * s * ln)], fill=(70, 150, 80, 255), width=w * 2)
    elif kind == "phone":
        d.rounded_rectangle([s * .3, s * .08, s * .7, s * .92], s * .06, fill=(40, 44, 56, 255))
        d.rounded_rectangle([s * .34, s * .16, s * .66, s * .8], s * .03, fill=(150, 210, 250, 255))
    elif kind == "house":
        d.polygon([(s * .1, s * .45), (m, s * .12), (s * .9, s * .45)], fill=c)
        d.rectangle([s * .2, s * .45, s * .8, s * .88], fill=(250, 250, 244, 255), outline=c, width=w)
        d.rectangle([s * .42, s * .6, s * .58, s * .88], fill=c)
    elif kind == "cup":
        d.rounded_rectangle([s * .2, s * .3, s * .7, s * .8], s * .06, fill=(250, 250, 244, 255), outline=c, width=w)
        d.arc([s * .55, s * .38, s * .88, s * .66], 270, 90, fill=c, width=w)
        for x in (.32, .45, .58):
            d.arc([s * x, s * .06, s * (x + .1), s * .26], 90, 270, fill=c, width=max(4, w // 2))
    elif kind == "letter":
        d.rounded_rectangle([s * .1, s * .25, s * .9, s * .78], s * .04, fill=(252, 252, 248, 255), outline=c, width=w)
        d.line([(s * .1, s * .27), (m, s * .55), (s * .9, s * .27)], fill=c, width=w)
    elif kind == "question":
        d.text((m, m), "?", font=_font(int(s * .9)), fill=c, anchor="mm")
    return im.resize((size, size), Image.LANCZOS)


def bubble_image(kind, text, accent):
    f = _font(52)
    lines = _wrap(text, f, 460)
    w = max(int(f.getlength(l)) for l in lines) + 90
    h = 74 * len(lines) + 56
    pad = 80
    im = Image.new("RGBA", ((w + 40) * 2, (h + pad) * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fill = (252, 252, 250, 255)
    if kind == "thought":
        d.rounded_rectangle([0, 0, w * 2, h * 2], min(h, 90), fill=fill, outline=accent + (255,), width=6)
        for i, r in enumerate((26, 18, 11)):
            cx, cy = w * 0.55 * 2 + i * 34, h * 2 + 22 + i * 40
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=accent + (255,), width=5)
    else:
        d.rounded_rectangle([0, 0, w * 2, h * 2], 60, fill=fill, outline=accent + (255,), width=6)
        d.polygon([(w * 0.7, h * 2 - 4), (w * 0.85, h * 2 - 4), (w * 0.72, h * 2 + 70)], fill=fill, outline=accent + (255,))
    f2 = _font(104)
    for i, l in enumerate(lines):
        d.text((w, (28 + 74 * i + 37) * 2), l, font=f2, fill=accent, anchor="mm")
    return im.resize((im.width // 2, im.height // 2), Image.LANCZOS)


# ───────────────────────── cảnh ─────────────────────────

def paste(base, im, cx, cy):
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def build_static(scene, pal):
    """Nền + icon + bóng nhân vật + dấu bằng. Không có thẻ, nhân vật, phụ đề."""
    top, bot, accent = PALETTES[pal]
    base = background(pal).convert("RGBA")
    d = ImageDraw.Draw(base, "RGBA")
    d.ellipse([W * 0.08, H * GROUND - 18, W * 0.92, H * GROUND + 22], fill=(0, 0, 0, 22))
    for p in scene.get("props", []):
        size = int(W * p.get("size", 0.2))
        if p.get("kind", "none") != "none":
            paste(base, prop_image(p["kind"], size, accent), W * p.get("x", .5), H * p.get("y", .45))
    if scene.get("equals") and scene.get("title"):
        paste(base, equals_sign(accent), W / 2, H * 0.285)
    return base


def build_figures(scene, pal):
    top, bot, accent = PALETTES[pal]
    figs = []
    for f in scene.get("figures", [{"x": 0.5, "pose": "stand"}]):
        scale = f.get("scale", 1.0)
        height = int(H * 0.36 * scale)
        color = accent if f.get("color") == "accent" else (240, 240, 244) if pal == "dark" else INK
        im = figure_image(f.get("pose", "stand"), height, color)
        if f.get("flip"):
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        halo_im = None
        if f.get("halo"):
            halo_im = halo(int(height * 1.15), accent)
        figs.append((im, W * f.get("x", .5), H * GROUND, halo_im, f.get("phase", 0.0)))
    return figs


async def build(spec: dict, out_path: str) -> dict:
    from moviepy import AudioClip, AudioFileClip, VideoClip, concatenate_audioclips, concatenate_videoclips
    from moviepy.audio.AudioClip import AudioClip as _AC  # noqa

    work = Path(tempfile.mkdtemp(prefix="explainer_"))
    voice = spec.get("voice", "vi-VN-HoaiMyNeural")
    scenes = spec["scenes"]

    async def voice_for(i, sc):
        text_plain = sc["text"].replace("*", "")
        if sc.get("audio"):
            import subprocess
            out = work / f"v{i}.mp3"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", sc["audio"], "-ar", "44100", "-ac", "2", str(out)], check=True)
            segs = _words_from_audio(out)
            return segs, None
        words = await _tts(text_plain, sc.get("voice", voice), sc.get("rate", spec.get("rate", "-2%")),
                           sc.get("pitch", spec.get("pitch", "+0Hz")), work / f"v{i}.mp3")
        return words, words

    res = []
    for i, sc in enumerate(scenes):            # tuần tự, thử lại: edge-tts hay từ chối khi gọi song song
        for attempt in range(4):
            try:
                res.append(await voice_for(i, sc))
                break
            except Exception:
                if attempt == 3:
                    raise
                await asyncio.sleep(1.5 * (attempt + 1))
    silence = lambda dur: AudioClip(lambda t: np.zeros((np.size(t), 2)), duration=dur, fps=44100)
    clips, parts = [], []
    total = 0.0
    n = len(scenes)
    starts = []
    for i, (sc, (timings, _)) in enumerate(zip(scenes, res)):
        audio = AudioFileClip(str(work / f"v{i}.mp3"))
        dur = audio.duration + sc.get("pad", 0.35)
        pal = sc.get("palette") or ORDER[i % len(ORDER)]
        static = build_static(sc, pal)
        figs = build_figures(sc, pal)
        accent = PALETTES[pal][2]
        title = sc.get("title")
        bub = bubble_image(sc["bubble"].get("kind", "speech"), sc["bubble"]["text"], accent) if sc.get("bubble") else None
        bpos = (sc["bubble"].get("x", 0.5), sc["bubble"].get("y", 0.36)) if sc.get("bubble") else None
        words = parse_marks(sc["text"])
        chunks = chunks_from_words(words)
        # thời điểm từng cụm: theo mốc từ nếu có, không thì chia theo số ký tự trên đoạn có tiếng
        if timings and len(timings) >= len(words) * 0.8 and not sc.get("audio"):
            idx, cs = 0, []
            for ch in chunks:
                a = timings[min(idx, len(timings) - 1)][0]
                idx += len(ch)
                b = timings[min(idx - 1, len(timings) - 1)][1]
                cs.append([a, b])
        else:
            segs = timings or [(0.0, audio.duration)]
            t0, t1 = segs[0][0], segs[-1][1]
            tot = sum(len(" ".join(x[0] for x in ch)) for ch in chunks) or 1
            acc, cs = 0, []
            for ch in chunks:
                l = len(" ".join(x[0] for x in ch))
                cs.append([t0 + (t1 - t0) * acc / tot, t0 + (t1 - t0) * (acc + l) / tot])
                acc += l
        # lấp khoảng hở: cụm hiện từ lúc bắt đầu đến lúc cụm sau bắt đầu
        for k in range(len(cs) - 1):
            cs[k][1] = cs[k + 1][0]
        cs[0][0] = 0.0
        cs[-1][1] = dur
        sub_imgs = [subtitle_img(ch) for ch in chunks]
        title_cache = {}

        def frame_at(t, static=static, figs=figs, title=title, bub=bub, bpos=bpos, cs=cs, sub_imgs=sub_imgs, accent=accent,
                     dur=dur, start=total, title_cache=title_cache, pal=pal):
            fr = static.copy()
            for im, x, y, hal, ph in figs:
                if hal is not None:
                    paste(fr, hal, x, y - im.height * 0.5)
                bob = math.sin(t * 2.4 + ph) * 3.0
                fr.alpha_composite(im, (int(x - im.width / 2), int(y - im.height + bob)))
            if title:
                pop = min(1.0, t / 0.22)
                sc_ = 0.82 + 0.18 * (1 - (1 - pop) ** 3) + (0.03 * math.sin(pop * math.pi) if pop < 1 else 0)
                key = round(sc_, 2)
                if key not in title_cache:
                    title_cache[key] = title_card(title, accent, key, dark=(pal == "dark"))
                paste(fr, title_cache[key], W / 2, H * 0.19)
            if bub is not None and t > 0.4:
                b = bub
                paste(fr, b, W * bpos[0], H * bpos[1])
            for (a, b_), si in zip(cs, sub_imgs):
                if a <= t < b_:
                    paste(fr, si, W / 2, H * SUB_Y)
                    break
            # thanh tiến độ mỏng
            d = ImageDraw.Draw(fr)
            prog = (start + t) / spec_total[0]
            d.rectangle([0, 0, W, 8], fill=(255, 255, 255, 120))
            d.rectangle([0, 0, int(W * min(1, prog)), 8], fill=(240, 60, 90, 255))
            hd = spec.get("handle", "")
            if hd:
                d.text((W - 36, H - 70), hd, font=_font(34), fill=(255, 255, 255, 200) if pal == "dark" else (60, 60, 70, 170), anchor="rm")
            return np.array(fr.convert("RGB"))

        starts.append(total)
        total += dur
        clips.append((frame_at, dur))
        parts.append(concatenate_audioclips([audio, silence(sc.get("pad", 0.35))]))

    spec_total = [total]
    vids = [VideoClip(fn, duration=d).with_fps(FPS) for fn, d in clips]
    video = concatenate_videoclips(vids)
    audio = concatenate_audioclips(parts)
    video = video.with_audio(audio)
    video.write_videofile(out_path, fps=FPS, codec="libx264", audio_codec="aac", preset="veryfast", threads=4, logger=None)
    return {"video_path": out_path, "duration": total, "work_dir": str(work)}


if __name__ == "__main__":
    import os
    os.environ.setdefault("SSL_CERT_FILE", "/root/.ccr/ca-bundle.crt")
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    print(asyncio.run(build(spec, sys.argv[2])))
