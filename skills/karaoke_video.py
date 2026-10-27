"""
Karaoke video — truyện đọc to có phụ đề từng chữ sáng lên theo giọng đọc (9:16).

Dùng lại các phần của autopost: edge-tts (có WordBoundary để biết giờ từng chữ),
font Be Vietnam Pro trong assets/, MoviePy xuất mp4. Khác story_pipeline ở chỗ
phụ đề tô sáng từng chữ đúng lúc nó được đọc, và mỗi đoạn có thể dùng giọng riêng.

Chạy thử:
    python -m skills.karaoke_video spec.json output.mp4
spec.json:
    {
      "title": "Ít Đường, Nhiều Cậu", "subtitle": "Chương 5 · Chiếc ô và trạm chờ",
      "brand": "Đọc Đêm", "cta": "Đọc trọn truyện trên Đọc Đêm. Link ở bio.",
      "segments": [{"text": "...", "voice": "vi-VN-HoaiMyNeural", "type": "hook|story|cta"}]
    }
"""

import asyncio
import json
import os
import re
import ssl
import sys
import tempfile
from pathlib import Path

import numpy as np

from config import FONT_PATH

W, H = 1080, 1920
FPS = 24
PAD = 0.35            # giây nghỉ giữa các đoạn
RATE = "-8%"
FONT_SIZE = 66
HI = (255, 214, 102)      # chữ đang đọc
DONE = (255, 255, 255)    # chữ đã đọc
TODO = (190, 170, 190)    # chữ chưa đọc


def _ssl_fix():
    """Dùng CA của môi trường (proxy) cho edge-tts mà vẫn bật kiểm tra chứng chỉ."""
    cafile = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if not cafile or not os.path.exists(cafile):
        return
    try:
        import edge_tts.communicate as c
        c._SSL_CTX = ssl.create_default_context(cafile=cafile)
    except Exception:
        pass


async def _tts(text: str, voice: str, mp3: Path) -> list[dict]:
    import edge_tts
    _ssl_fix()
    com = edge_tts.Communicate(text, voice, rate=RATE, boundary="WordBoundary")
    words = []
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append({"w": ch["text"], "s": ch["offset"] / 1e7,
                              "e": (ch["offset"] + ch["duration"]) / 1e7})
    return words


def _tokens(text: str) -> list[str]:
    return text.split()


def _align(tokens: list[str], words: list[dict], dur: float) -> list[tuple[float, float]]:
    """Gán thời gian cho từng token hiển thị. Khớp theo thứ tự; lệch số lượng thì chia theo độ dài."""
    if len(tokens) == len(words):
        return [(w["s"], w["e"]) for w in words]
    total = sum(len(t) for t in tokens) or 1
    t0 = words[0]["s"] if words else 0.0
    t1 = words[-1]["e"] if words else dur
    out, cur = [], t0
    for t in tokens:
        d = (t1 - t0) * len(t) / total
        out.append((cur, cur + d))
        cur += d
    return out


def _font(size):
    from PIL import ImageFont
    return ImageFont.truetype(FONT_PATH, size)


def _background(seed: int = 7):
    from PIL import Image, ImageDraw, ImageFilter
    img = Image.new("RGB", (W, H))
    px = np.zeros((H, W, 3), dtype=np.uint8)
    top, bot = np.array([48, 20, 58]), np.array([20, 12, 36])
    for y in range(H):
        px[y, :, :] = top + (bot - top) * (y / H)
    img = Image.fromarray(px)
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(glow)
    rng = np.random.default_rng(seed)
    for _ in range(14):  # các đốm sáng mờ như đèn đường trong mưa
        x, y, r = int(rng.integers(0, W)), int(rng.integers(0, H)), int(rng.integers(60, 190))
        col = (int(rng.integers(150, 230)), int(rng.integers(70, 130)), int(rng.integers(90, 160)))
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    return Image.blend(img, Image.fromarray(np.maximum(np.array(img), (np.array(glow) * 0.5).astype(np.uint8))), 0.55)


def _wrap(tokens: list[str], font, max_w: int) -> list[list[int]]:
    lines, cur, cur_w = [], [], 0
    space = font.getlength(" ")
    for i, t in enumerate(tokens):
        w = font.getlength(t)
        if cur and cur_w + space + w > max_w:
            lines.append(cur)
            cur, cur_w = [i], w
        else:
            cur_w += (space if cur else 0) + w
            cur.append(i)
    if cur:
        lines.append(cur)
    return lines


def _frame(bg, header: tuple[str, str], brand: str, tokens: list[str], lines, active: int):
    """active: chỉ số token đang đọc; -1 = chưa đọc chữ nào; len = đã đọc hết."""
    from PIL import ImageDraw
    img = bg.copy()
    d = ImageDraw.Draw(img)
    f_big, f_small, f_brand = _font(FONT_SIZE), _font(34), _font(38)

    d.text((W // 2, 150), header[0], font=_font(56), fill=(255, 214, 102), anchor="mm",
           stroke_width=2, stroke_fill=(0, 0, 0))
    if header[1]:
        d.text((W // 2, 215), header[1], font=f_small, fill=(215, 195, 215), anchor="mm")

    lh = int(FONT_SIZE * 1.55)
    y = H // 2 - (len(lines) * lh) // 2
    space = f_big.getlength(" ")
    for ln in lines:
        widths = [f_big.getlength(tokens[i]) for i in ln]
        x = (W - (sum(widths) + space * (len(ln) - 1))) / 2
        for i, wd in zip(ln, widths):
            col = HI if i == active else (DONE if i < active else TODO)
            d.text((x, y), tokens[i], font=f_big, fill=col, anchor="lm",
                   stroke_width=3, stroke_fill=(0, 0, 0))
            x += wd + space
        y += lh

    d.text((W // 2, H - 110), brand, font=f_brand, fill=(215, 195, 215), anchor="mm")
    return np.array(img)


async def build(spec: dict, out_path: str) -> dict:
    from moviepy import AudioClip, AudioFileClip, ImageClip, concatenate_audioclips, concatenate_videoclips

    work = Path(tempfile.mkdtemp(prefix="karaoke_"))
    bg = _background()
    header = (spec.get("title", ""), spec.get("subtitle", ""))
    brand = spec.get("brand", "")
    f_big = _font(FONT_SIZE)
    max_w = W - 180

    segs = spec["segments"]
    results = await asyncio.gather(*[
        _tts(s["text"], s.get("voice", "vi-VN-HoaiMyNeural"), work / f"v{i}.mp3")
        for i, s in enumerate(segs)])

    clips, parts = [], []
    silence = lambda d: AudioClip(lambda t: np.zeros((np.size(t), 2)), duration=d, fps=44100)
    for i, (s, words) in enumerate(zip(segs, results)):
        mp3 = work / f"v{i}.mp3"
        seg_audio = AudioFileClip(str(mp3))
        dur = seg_audio.duration
        tokens = _tokens(s["text"])
        times = _align(tokens, words, dur)
        lines = _wrap(tokens, f_big, max_w)
        n = len(tokens)

        # trạng thái: trước khi đọc, từng chữ sáng, sau khi đọc xong
        starts = [t[0] for t in times]
        states = [-1] + list(range(n)) + [n]
        edges = [0.0] + starts + [times[-1][1], dur + PAD]
        for k, st in enumerate(states):
            a, b = edges[k], edges[k + 1]
            if b - a <= 0.001:
                continue
            clips.append(ImageClip(_frame(bg, header, brand, tokens, lines, st)).with_duration(b - a))
        parts += [seg_audio, silence(PAD)]

    video = concatenate_videoclips(clips, method="chain")
    video = video.with_audio(concatenate_audioclips(parts))
    video.write_videofile(out_path, fps=FPS, codec="libx264", audio_codec="aac",
                          bitrate="3500k", preset="fast", logger=None)
    return {"video_path": out_path, "duration": video.duration, "work_dir": str(work)}


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(asyncio.run(build(spec, sys.argv[2])))
