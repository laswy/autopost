"""
Lyric video kiểu người que (9:16) cho một bài hát có sẵn.

Chạy:
    python -m skills.lyric_video spec.json out.mp4            # có lyric
    python -m skills.lyric_video spec.json out_clean.mp4 --no-lyrics   # bản không chữ, để tự khớp lời ở CapCut
spec.json:
    {"audio": "song.wav", "duration": 30.0, "handle": "@tmadoc", "fade_out": 0.8,
     "sections": [{"start": 0, "end": 7.5, "kind": "ride"}, ...],
     "lyrics": [{"start": 0.8, "end": 6.8, "lines": ["dòng 1", "dòng 2"],
                 "words": [[0.8, 1.1], ...]  # tuỳ chọn: mốc từng chữ (giây) để khớp chuẩn
                }]}
kind: ride (đạp xích lô đêm, đèn đường chạy), ride_cold (trời lạnh, có bóng người phía xa),
      sit (ngồi gục trên xe, dấu hỏi), stumble (loạng choạng, ghế sau trống),
      walk_meet (bước chậm về phía bóng người, trăng).
Sửa lời: chỉ cần sửa mục "lyrics" (start, end, lines, words) rồi chạy lại.
"""

import json
import math
import random
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from skills.explainer_video import BOLD, POSES, figure_image, _font

W, H = 1080, 1920
FPS = 24

POSES["ride"] = ([22, 4], [22, 4], 2)
POSES["fall"] = ([110, 150], [70, 20], 10)

SKY = {                         # kind -> (nền trên, nền dưới, ánh đèn)
    "ride": ((16, 10, 34), (70, 34, 60), (255, 176, 80)),
    "ride_cold": ((12, 16, 44), (44, 40, 90), (255, 190, 110)),
    "sit": ((10, 18, 26), (34, 46, 56), (230, 180, 100)),
    "stumble": ((26, 10, 24), (80, 28, 46), (255, 130, 80)),
    "walk_meet": ((30, 16, 50), (150, 70, 70), (255, 210, 130)),
}
ACC = (240, 100, 140)           # màu nhấn: bóng "em"


def lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(len(a)))


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


class Scene:
    def __init__(self, spec):
        self.spec = spec
        self.secs = spec["sections"]
        rnd = random.Random(7)
        self.bokeh = [(rnd.random() * W, rnd.random() * H, rnd.uniform(14, 46), rnd.uniform(0.2, 1.0), rnd.random() * 6.28) for _ in range(22)]
        self.bldg = [(i * 130 - 40, rnd.uniform(380, 760), rnd.uniform(90, 150)) for i in range(11)]
        self.ground = int(H * 0.72)
        self.cache = {}
        self.fig_cache = {}

    def sec_at(self, t):
        for i, s in enumerate(self.secs):
            if s["start"] <= t < s["end"]:
                return i, s
        return len(self.secs) - 1, self.secs[-1]

    def sky(self, t):
        i, s = self.sec_at(t)
        top, bot, lamp = SKY[s["kind"]]
        k = smooth((t - s["start"]) / 1.2)
        if i > 0:
            pt, pb, pl = SKY[self.secs[i - 1]["kind"]]
            top, bot, lamp = lerp(pt, top, k), lerp(pb, bot, k), lerp(pl, lamp, k)
        return top, bot, tuple(int(v) for v in lamp)

    def background(self, t):
        top, bot, lamp = self.sky(t)
        key = (tuple(int(v) for v in top), tuple(int(v) for v in bot))
        if key not in self.cache:
            col = np.zeros((H, 1, 3), np.float32)
            for y in range(H):
                col[y, 0] = lerp(top, bot, (y / H) ** 1.3)
            self.cache = {key: Image.fromarray(np.repeat(col, W, axis=1).astype("uint8")).convert("RGBA")}
        return self.cache[key].copy(), lamp

    def fig(self, pose, height, color):
        k = (pose, height, color)
        if k not in self.fig_cache:
            self.fig_cache[k] = figure_image(pose, height, color)
        return self.fig_cache[k]

    # ───── từng lớp ─────
    def draw_world(self, im, t, lamp, speed_pos):
        d = ImageDraw.Draw(im, "RGBA")
        # bokeh
        glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for x, y, r, a, ph in self.bokeh:
            yy = (y - t * 18 * a) % H
            xx = x + math.sin(t * 0.6 + ph) * 20
            gd.ellipse([xx - r, yy - r, xx + r, yy + r], fill=lamp + (int(34 * a),))
        im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(6)))
        # nhà xa (parallax chậm)
        off = (speed_pos * 0.15) % 130
        for i, (x, h, w) in enumerate(self.bldg):
            xx = x - off
            d.rectangle([xx, self.ground - h, xx + w, self.ground], fill=(10, 8, 20, 235))
            for wy in range(int(self.ground - h + 40), int(self.ground - 60), 70):
                if (i * 7 + wy // 70) % 3 == 0:
                    d.rectangle([xx + 22, wy, xx + 44, wy + 30], fill=lamp + (150,))
        # mặt đường
        d.rectangle([0, self.ground, W, H], fill=(8, 6, 16, 255))
        # cột đèn
        spacing = 520
        off2 = (speed_pos * 0.6) % spacing
        for k in range(-1, 4):
            x = k * spacing - off2 + 160
            d.rectangle([x - 7, self.ground - 520, x + 7, self.ground], fill=(30, 26, 40, 255))
            d.line([(x, self.ground - 520), (x + 70, self.ground - 540)], fill=(30, 26, 40, 255), width=10)
            lx, ly = x + 74, self.ground - 536
            pool = Image.new("RGBA", im.size, (0, 0, 0, 0))
            pd = ImageDraw.Draw(pool)
            pd.ellipse([lx - 230, ly - 230, lx + 230, ly + 230], fill=lamp + (60,))
            pd.ellipse([lx - 330, self.ground - 10, lx + 330, self.ground + 60], fill=lamp + (70,))
            im.alpha_composite(pool.filter(ImageFilter.GaussianBlur(24)))
            d.ellipse([lx - 18, ly - 18, lx + 18, ly + 18], fill=(255, 240, 200, 255))

    def draw_cyclo(self, im, cx, base_y, t, rot, tilt=0.0, empty_back=False):
        """Xích lô nhìn ngang: bánh sau (người đạp) và khoang khách phía trước. cx = vị trí người đạp."""
        d = ImageDraw.Draw(im, "RGBA")
        col = (240, 236, 232, 255)
        wr = 118
        # bánh sau
        for wx in (cx, cx + 330):
            wy = base_y - wr
            d.ellipse([wx - wr, wy - wr, wx + wr, wy + wr], outline=col, width=9)
            for a in range(0, 360, 45):
                r = math.radians(a + rot)
                d.line([(wx, wy), (wx + math.cos(r) * wr, wy + math.sin(r) * wr)], fill=col, width=3)
        # khoang
        d.rounded_rectangle([cx + 190, base_y - 330, cx + 470, base_y - 170], 24, outline=col, width=8)
        d.arc([cx + 170, base_y - 470, cx + 490, base_y - 170], 180, 360, fill=col, width=8)
        d.line([(cx + 15, base_y - 120), (cx + 200, base_y - 260)], fill=col, width=8)     # sườn xe
        d.line([(cx - 10, base_y - 250), (cx + 20, base_y - 350)], fill=col, width=8)      # ghi đông

    def draw_person(self, im, pose, height, x, feet_y, color, angle=0.0, bob=0.0):
        f = self.fig(pose, height, color)
        if angle:
            f = f.rotate(angle, resample=Image.BICUBIC, expand=True, center=(f.width / 2, f.height))
        im.alpha_composite(f, (int(x - f.width / 2), int(feet_y - f.height + bob)))

    def halo(self, im, x, y, r, a=70):
        g = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).ellipse([x - r, y - r, x + r, y + r], fill=ACC + (a,))
        im.alpha_composite(g.filter(ImageFilter.GaussianBlur(30)))

    def frame(self, t):
        i, s = self.sec_at(t)
        kind = s["kind"]
        local = t - s["start"]
        dur = s["end"] - s["start"]
        im, lamp = self.background(t)
        speed = {"ride": 520, "ride_cold": 420, "sit": 0, "stumble": 120, "walk_meet": 200}[kind]
        # quãng đường tích lũy (phân đoạn cũ cộng dồn)
        pos = 0.0
        for k, sec in enumerate(self.secs):
            sp = {"ride": 520, "ride_cold": 420, "sit": 0, "stumble": 120, "walk_meet": 200}[sec["kind"]]
            pos += sp * max(0.0, min(t, sec["end"]) - sec["start"]) if t > sec["start"] else 0.0
        self.draw_world(im, t, lamp, pos)
        gy = self.ground + 70
        beat = math.sin(t * 2 * math.pi * 88 / 60)               # nhịp 88 BPM
        if kind in ("ride", "ride_cold"):
            if kind == "ride_cold":                                  # bóng "em" ở phía xa, dưới đèn
                self.halo(im, 880, gy - 190, 190)
                self.draw_person(im, "stand", 330, 880, gy - 40, ACC)
            rot = pos * 0.6
            self.draw_cyclo(im, 250, gy, t, rot)
            self.draw_person(im, "ride", 520, 262, gy - 128, (235, 232, 240), bob=beat * 5)
            if kind == "ride_cold":                                  # hơi thở lạnh
                for n in range(5):
                    ph = (t * 0.8 + n * 0.2) % 1.0
                    r = 10 + ph * 22
                    ImageDraw.Draw(im, "RGBA").ellipse([300 + ph * 60 - r, gy - 640 - ph * 80 - r, 300 + ph * 60 + r, gy - 640 - ph * 80 + r], fill=(255, 255, 255, int(150 * (1 - ph))))
        elif kind == "sit":
            self.draw_cyclo(im, 380, gy, t, 0)
            self.draw_person(im, "sad", 440, 392, gy - 130, (235, 232, 240), bob=beat * 2)
            d = ImageDraw.Draw(im, "RGBA")
            for n, (qx, qy) in enumerate(((190, gy - 700), (640, gy - 760), (880, gy - 640))):
                a = int(200 * (0.5 + 0.5 * math.sin(t * 2 + n)))
                d.text((qx, qy - local * 12 % 40), "?", font=_font(140), fill=(240, 226, 200, a), anchor="mm")
        elif kind == "stumble":
            self.draw_cyclo(im, 250, gy, t, 0)
            k = smooth(local / 1.6)
            self.draw_person(im, "fall" if local > 1.0 else "sad", 500, 262 - 40 * k, gy - 130 + 60 * k, (235, 232, 240), angle=-34 * k)
            d = ImageDraw.Draw(im, "RGBA")
            d.rounded_rectangle([700, gy - 330, 980, gy - 170], 24, outline=(240, 236, 232, 120), width=6)   # ghế sau trống
        else:                                                         # walk_meet
            self.moon(im, 760, 620, lamp)
            k = smooth(local / dur)
            self.halo(im, 820, gy - 230, 240, 90)
            self.draw_person(im, "stand", 600, 820, gy, ACC, bob=beat * 3)
            x = 160 + (500 - 160) * k
            self.draw_person(im, "wave" if k > 0.9 else "stand", 600, x, gy, (235, 232, 240), bob=math.sin(local * 5) * 8)
        return im

    def moon(self, im, x, y, lamp):
        g = Image.new("RGBA", im.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(g)
        gd.ellipse([x - 160, y - 160, x + 160, y + 160], fill=lamp + (60,))
        im.alpha_composite(g.filter(ImageFilter.GaussianBlur(40)))
        ImageDraw.Draw(im, "RGBA").ellipse([x - 78, y - 78, x + 78, y + 78], fill=(255, 244, 214, 255))


# ───── lyric ─────

def lyric_layer(spec, t):
    for ly in spec.get("lyrics", []):
        if ly["start"] - 0.05 <= t <= ly["end"] + 0.4:
            break
    else:
        return None
    lines = ly["lines"]
    words = [w for l in lines for w in l.split()]
    n = len(words)
    st, en = ly["start"], ly["end"]
    wt = ly.get("words") or [[st + (en - st) * 0.62 * i / n, st + (en - st) * 0.62 * i / n + 0.25] for i in range(n)]
    f = _font(66)
    lh = 100
    layer = Image.new("RGBA", (W, lh * len(lines) + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    out_a = 1.0 - smooth((t - en) / 0.4)
    k = 0
    for li, line in enumerate(lines):
        ws = line.split()
        sp = f.getlength(" ")
        tw = sum(f.getlength(w) for w in ws) + sp * (len(ws) - 1)
        x = W / 2 - tw / 2
        y = 40 + lh * li + lh / 2
        for w in ws:
            a0 = smooth((t - wt[k][0]) / max(0.12, wt[k][1] - wt[k][0]))
            a = a0 * out_a
            if a > 0.01:
                for dx, dy in ((3, 4), (-2, 3), (0, 6)):
                    d.text((x + dx, y + dy), w, font=f, fill=(0, 0, 0, int(150 * a)), anchor="lm")
                d.text((x, y), w, font=f, fill=(255, 255, 255, int(255 * a)), anchor="lm")
            x += f.getlength(w) + sp
            k += 1
    return layer


def render(spec, out_path, with_lyrics=True):
    from moviepy import AudioFileClip, VideoClip
    sc = Scene(spec)
    dur = spec.get("duration", 30.0)
    fade = spec.get("fade_out", 0.8)
    handle = spec.get("handle", "")

    def make(t):
        im = sc.frame(t)
        if with_lyrics:
            ly = lyric_layer(spec, t)
            if ly is not None:
                im.alpha_composite(ly, (0, int(H * 0.77)))
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, 0, W, 8], fill=(255, 255, 255, 60))
        d.rectangle([0, 0, int(W * min(1.0, t / dur)), 8], fill=(240, 60, 90, 255))
        if handle:
            d.text((W - 36, H - 70), handle, font=_font(34), fill=(255, 255, 255, 190), anchor="rm")
        a = 1.0
        if t < 0.6:
            a = smooth(t / 0.6)
        if t > dur - fade:
            a = min(a, smooth((dur - t) / fade))
        arr = np.array(im.convert("RGB")).astype(np.float32) * a
        return arr.astype("uint8")

    clip = VideoClip(make, duration=dur).with_fps(FPS)
    au = AudioFileClip(spec["audio"]).subclipped(0, dur)
    from moviepy.audio.fx import AudioFadeOut
    au = au.with_effects([AudioFadeOut(fade)])
    clip = clip.with_audio(au)
    clip.write_videofile(out_path, fps=FPS, codec="libx264", audio_codec="aac", preset="veryfast", threads=4, logger=None)
    return {"video_path": out_path, "duration": dur}


def to_lrc(spec, path):
    def ts(x):
        return f"[{int(x // 60):02d}:{x % 60:05.2f}]"
    with open(path, "w", encoding="utf-8") as f:
        for ly in spec.get("lyrics", []):
            f.write(ts(ly["start"]) + " ".join(ly["lines"]) + "\n")


if __name__ == "__main__":
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    print(render(spec, sys.argv[2], with_lyrics="--no-lyrics" not in sys.argv))
