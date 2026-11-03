"""
Video lai: người que "THE LITTLE WANDERER" nhảy HipHop/Drill trên nền video người thật (giữ nguyên video gốc, tỉ lệ gốc, âm thanh gốc).

Chạy:
    python -m skills.hybrid_stickman src.mp4 out.mp4 [bpm]
Nhân vật: người que mực đen gầy, đầu to tròn, 3 sợi tóc rối ngả trái, mắt nhỏ biểu cảm, lông mày lệch, áo hoodie đen rộng,
quần ống rộng, giày thể thao trắng, tai nghe. Bạn nữ: cùng thiết kế, áo hoodie đỏ, tóc hai chỏm, tai nghe hồng.
Các "màn" (act) gắn với thời gian thật của clip; người que đứng ở vùng an toàn để không che mặt người thật và sản phẩm.
"""

import math
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from skills.explainer_video import BOLD, _font
from skills.story_stickman import Char, ik, ss, blend, rad

W, H = 1280, 720
FPS = 24
BPM = 96.0
BLACK = (14, 14, 18, 255)
WHITE = (250, 250, 252, 255)
ORANGE = (255, 150, 40, 255)
RED = (214, 40, 48, 255)


def rotl(x, y, cx, cy, a):
    c, s = math.cos(a), math.sin(a)
    return (cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c)


# ───────────────────────── nhân vật ─────────────────────────

class Wanderer(Char):
    def __init__(self, girl=False, fh=330, face=1):
        super().__init__("woman" if girl else "man", fh=fh, face=face)
        self.girl = girl
        self.headphones, self.hairnet, self.cap, self.glasses, self.pants = True, False, False, False, BLACK
        self.cup = (255, 120, 170, 255) if girl else ORANGE
        self.hood = RED if girl else BLACK
        self.TH, self.SH, self.TO = 0.24 * fh, 0.24 * fh, 0.27 * fh
        self.UA, self.FA, self.HR = 0.17 * fh, 0.16 * fh, 0.15 * fh

    def draw(self, im, P, t=0.0, seed=0, expr="neutral", props=(), vel=0.0, face=None):
        fd = face if face is not None else self.face
        pts = self.pts(P)
        d = ImageDraw.Draw(im, "RGBA")
        k = self.fh / 330.0
        rnd = np.random.RandomState(seed)

        def jt(p, a=0.8):
            return (p[0] + rnd.uniform(-a, a), p[1] + rnd.uniform(-a, a))

        def tube(seq, w0, w1, fill=BLACK):
            """Ống mực đen có viền trắng, nhỏ dần."""
            for pass_ in (0, 1):
                for i in range(len(seq) - 1):
                    a, b = seq[i], seq[i + 1]
                    wa = w0 + (w1 - w0) * i / max(1, len(seq) - 1)
                    wb = w0 + (w1 - w0) * (i + 1) / max(1, len(seq) - 1)
                    extra = 6 if pass_ == 0 else 0
                    col = WHITE if pass_ == 0 else fill
                    d.line([a, b], fill=col, width=int(max(wa, wb) + extra))
                    for p, wv in ((a, wa), (b, wb)):
                        d.ellipse([p[0] - (wv + extra) / 2, p[1] - (wv + extra) / 2, p[0] + (wv + extra) / 2, p[1] + (wv + extra) / 2], fill=col)

        def shoe(side):
            fx, fy = pts[f"f{side}"]
            sh = [(fx - 12 * fd * k, fy - 14 * k), (fx + 18 * fd * k, fy - 14 * k), (fx + 44 * fd * k, fy + 2 * k), (fx + 44 * fd * k, fy + 16 * k), (fx - 16 * fd * k, fy + 16 * k)]
            d.polygon(sh, fill=WHITE, outline=BLACK)
            d.line(sh + [sh[0]], fill=BLACK, width=3)
            d.line([(fx - 16 * fd * k, fy + 12 * k), (fx + 44 * fd * k, fy + 12 * k)], fill=ORANGE if not self.girl else (255, 120, 170, 255), width=4)

        def leg(side):
            hip, kn, ft = pts["hip"], pts[f"k{side}"], pts[f"f{side}"]
            tube([hip, kn, ft], 40 * k, 34 * k)                       # quần ống rộng
            shoe(side)

        def arm(side):
            sh_, e_, h_ = pts["sh"], pts[f"e{side}"], pts[f"h{side}"]
            tube([sh_, e_, h_], 34 * k, 24 * k, self.hood)
            d.ellipse([h_[0] - 11 * k, h_[1] - 11 * k, h_[0] + 11 * k, h_[1] + 11 * k], fill=BLACK, outline=WHITE, width=3)

        leg("L")
        arm("L")
        # hoodie rộng
        tt = pts["t"]
        u = (math.sin(tt), -math.cos(tt))
        pr = (math.cos(tt), math.sin(tt))
        shd = (pts["sh"][0] + u[0] * 10, pts["sh"][1] + u[1] * 10)
        hem = (pts["hip"][0] - u[0] * 0.10 * self.fh, pts["hip"][1] - u[1] * 0.10 * self.fh)
        sw, fl = 0.115 * self.fh, 0.15 * self.fh
        poly = [(shd[0] + pr[0] * sw, shd[1] + pr[1] * sw), (shd[0] - pr[0] * sw, shd[1] - pr[1] * sw),
                (hem[0] - pr[0] * fl, hem[1] - pr[1] * fl), (hem[0] + pr[0] * fl, hem[1] + pr[1] * fl)]
        d.polygon(poly, fill=self.hood, outline=WHITE)
        d.line(poly + [poly[0]], fill=WHITE, width=4)
        hood_c = (pts["neck"][0] - u[0] * 4 - fd * 8 * k, pts["neck"][1] - u[1] * 4 + 8 * k)
        d.ellipse([hood_c[0] - 26 * k, hood_c[1] - 18 * k, hood_c[0] + 26 * k, hood_c[1] + 18 * k], fill=self.hood, outline=WHITE, width=3)
        pk = (hem[0] - u[0] * 0.02 * self.fh, hem[1] - u[1] * 0.02 * self.fh)
        d.line([(pk[0] - pr[0] * 40 * k + u[0] * 40 * k, pk[1] - pr[1] * 40 * k + u[1] * 40 * k),
                (pk[0] + pr[0] * 40 * k + u[0] * 40 * k, pk[1] + pr[1] * 40 * k + u[1] * 40 * k)], fill=WHITE, width=3)   # túi bụng
        for sgn in (-1, 1):                                          # dây rút
            d.line([(pts["neck"][0] + sgn * 9 * k, pts["neck"][1] + 6 * k), (pts["neck"][0] + sgn * 11 * k - u[0] * 40 * k, pts["neck"][1] - u[1] * 40 * k + 6 * k)], fill=WHITE, width=3)
        leg("R")
        arm("R")
        # đầu to tròn
        hx, hy = pts["head"]
        r = self.HR
        th = pts["th"]
        # 3 sợi tóc rối ngả trái
        for n, (ang, ln) in enumerate(() if (self.hairnet or self.cap) else ((-108, 1.0), (-92, 1.3), (-76, 0.9))):
            a = rad(ang) + th * 0.4
            base = (hx + math.cos(a) * r * 0.92, hy + math.sin(a) * r * 0.92)
            mid = (base[0] - 14 * k + math.sin(t * 9 + n) * 3, base[1] - 18 * k * ln)
            end = (mid[0] - 22 * k, mid[1] - 8 * k * ln + 6 * k)
            for pass_ in (0, 1):
                d.line([base, mid, end], fill=WHITE if pass_ == 0 else BLACK, width=int(9 * k + 4) if pass_ == 0 else int(6 * k + 2), joint="curve")
        d.ellipse([hx - r - 3, hy - r - 3, hx + r + 3, hy + r + 3], fill=WHITE)
        d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=BLACK)
        if self.girl:                                                # hai chỏm tóc
            for sgn in (-1, 1):
                cx_, cy_ = hx + sgn * r * 0.85, hy - r * 0.85
                d.ellipse([cx_ - 14 * k, cy_ - 14 * k, cx_ + 14 * k, cy_ + 14 * k], fill=BLACK, outline=WHITE, width=3)
        if self.hairnet:
            d.ellipse([hx - r * 1.08, hy - r * 1.18, hx + r * 1.08, hy + r * 0.2], fill=(244, 244, 248, 235), outline=WHITE)
        if self.cap:
            d.pieslice([hx - r * 1.05, hy - r * 1.15, hx + r * 1.05, hy + r * 0.85], 180, 360, fill=(30, 30, 36, 255), outline=WHITE)
            d.polygon([(hx + fd * r * 0.6, hy - r * 0.3), (hx + fd * r * 1.6, hy - r * 0.15), (hx + fd * r * 0.6, hy - r * 0.05)], fill=(30, 30, 36, 255), outline=WHITE)
        if self.glasses:
            for cx_ in (hx + fd * r * 0.20, hx + fd * r * 0.65):
                d.ellipse([cx_ - 14 * k, hy - 12 * k, cx_ + 14 * k, hy + 16 * k], outline=(220, 220, 230, 255), width=3)
        # tai nghe
        hb = [(hx + math.cos(rad(a)) * (r + 6 * k), hy + math.sin(rad(a)) * (r + 6 * k)) for a in range(-170, -9, 10)]
        if self.headphones:
            d.line(hb, fill=(120, 120, 130, 255), width=int(7 * k + 2), joint="curve")
            for sgn in (-1, 1):
                cx_, cy_ = hx + sgn * (r + 4 * k), hy - 2 * k
                d.rounded_rectangle([cx_ - 9 * k, cy_ - 16 * k, cx_ + 9 * k, cy_ + 16 * k], 6, fill=self.cup, outline=WHITE, width=2)
        # mặt: mắt nhỏ, lông mày lệch
        e1 = (hx + fd * r * 0.20, hy + r * 0.06)
        e2 = (hx + fd * r * 0.62, hy + r * 0.06)
        blink = (t % 3.4) < 0.1
        for i_, (ex, ey) in enumerate((e1, e2)):
            if expr in ("smile", "joy") or blink:
                d.arc([ex - 8 * k, ey - 6 * k, ex + 8 * k, ey + 8 * k], 200, 340, fill=WHITE, width=3)
            else:
                rr = (5.5 if expr != "wow" else 8) * k
                d.ellipse([ex - rr, ey - rr * 1.2, ex + rr, ey + rr * 1.2], fill=WHITE)
                d.ellipse([ex - rr * .45 + fd * 1.5, ey - rr * .5, ex + rr * .45 + fd * 1.5, ey + rr * .5], fill=BLACK)
            raise_ = (8 if i_ == 0 else 3) * k + (5 * k if expr in ("wow", "hype") else 0)
            tilt = (-4 if i_ == 0 else 5) * k * fd
            d.line([(ex - 9 * k, ey - 12 * k - raise_ + tilt), (ex + 9 * k, ey - 14 * k - raise_ - tilt)], fill=WHITE, width=3)
        mx, my = hx + fd * r * 0.42, hy + r * 0.52
        if expr in ("smile", "joy", "hype"):
            d.arc([mx - 14 * k, my - 8 * k, mx + 14 * k, my + 12 * k], 10, 170, fill=WHITE, width=3)
        elif expr == "wow":
            d.ellipse([mx - 6 * k, my - 3 * k, mx + 6 * k, my + 11 * k], outline=WHITE, width=3)
        else:
            d.line([(mx - 9 * k, my), (mx + 9 * k, my + 2 * k)], fill=WHITE, width=3)
        # đạo cụ
        for pr_ in props:
            self.prop(d, pr_, pts, fd, k, t)
        return pts

    def prop(self, d, kind, pts, fd, k, t):
        h = pts["hR"]
        hx, hy = pts["head"]
        r = self.HR
        if kind == "shades":
            d.rounded_rectangle([hx - r * 0.1 - (0 if fd > 0 else r * 0.9), hy - r * 0.05, hx + r * 0.95 - (0 if fd > 0 else r * 0.1), hy + r * 0.32], 8,
                                fill=(8, 8, 10, 255), outline=WHITE, width=3)
            d.line([(hx + fd * r * 0.2, hy), (hx + fd * r * 0.5, hy + r * 0.1)], fill=(180, 200, 255, 255), width=3)
        elif kind == "goggles":
            for cx_ in (hx + fd * r * 0.20, hx + fd * r * 0.65):
                d.ellipse([cx_ - 15 * k, hy - 14 * k, cx_ + 15 * k, hy + 16 * k], outline=(120, 220, 255, 255), width=4)
        elif kind == "megaphone":
            a = rad(-25 if fd > 0 else 205)
            cone = [h, (h[0] + math.cos(a - 0.35) * 70 * k * fd, h[1] + math.sin(a - 0.35) * 70 * k), (h[0] + math.cos(a + 0.35) * 70 * k * fd, h[1] + math.sin(a + 0.35) * 70 * k)]
            d.polygon(cone, fill=ORANGE, outline=WHITE)
        elif kind == "mic":
            d.line([h, (h[0] + fd * 6 * k, h[1] - 26 * k)], fill=BLACK, width=int(7 * k))
            d.ellipse([h[0] + fd * 6 * k - 11 * k, h[1] - 38 * k, h[0] + fd * 6 * k + 11 * k, h[1] - 16 * k], fill=(180, 180, 190, 255), outline=WHITE, width=2)
        elif kind == "drill":
            body = [(h[0] - 8 * k, h[1] - 12 * k), (h[0] + fd * 52 * k, h[1] - 12 * k), (h[0] + fd * 52 * k, h[1] + 8 * k), (h[0] - 8 * k, h[1] + 8 * k)]
            d.polygon(body, fill=(60, 66, 76, 255), outline=WHITE)
            d.rectangle([h[0] + fd * 6 * k - 6, h[1] + 8 * k, h[0] + fd * 6 * k + 12 * k, h[1] + 34 * k], fill=ORANGE, outline=WHITE)
            bit = (h[0] + fd * 52 * k, h[1] - 2 * k)
            d.line([bit, (bit[0] + fd * 28 * k, bit[1])], fill=(210, 210, 220, 255), width=4)
            for n in range(3):
                d.line([(bit[0] + fd * 28 * k, bit[1] + (n - 1) * 8 * k * math.sin(t * 40)), (bit[0] + fd * 46 * k, bit[1] + (n - 1) * 12 * k)], fill=(255, 220, 120, 200), width=2)
        elif kind == "magnifier":
            c = (h[0] + fd * 36 * k, h[1] - 20 * k)
            d.line([h, c], fill=BLACK, width=int(8 * k))
            d.ellipse([c[0] - 46 * k, c[1] - 46 * k, c[0] + 46 * k, c[1] + 46 * k], fill=(190, 230, 255, 90), outline=WHITE, width=5)
            d.ellipse([c[0] - 42 * k, c[1] - 42 * k, c[0] + 42 * k, c[1] + 42 * k], outline=BLACK, width=3)
            d.arc([c[0] - 30 * k, c[1] - 30 * k, c[0] + 30 * k, c[1] + 30 * k], 200, 260, fill=WHITE, width=4)
        elif kind == "nonla":
            top = (hx - fd * 4, hy - r * 1.9)
            d.polygon([top, (hx - r * 1.9, hy - r * 0.55), (hx + r * 1.9, hy - r * 0.55)], fill=(238, 214, 150, 255), outline=WHITE)
            d.line([top, (hx - r * 1.9, hy - r * 0.55)], fill=(180, 150, 90, 255), width=3)
            d.line([(hx - r, hy - r * 0.55), (hx - r * 0.7, hy + r * 0.7)], fill=RED, width=3)
        elif kind == "flag":
            d.line([h, (h[0], h[1] - 80 * k)], fill=BLACK, width=int(5 * k))
            d.polygon([(h[0], h[1] - 80 * k), (h[0] + fd * 60 * k + math.sin(t * 8) * 6, h[1] - 68 * k), (h[0], h[1] - 52 * k)], fill=RED, outline=WHITE)


# ───────────────────────── điệu nhảy ─────────────────────────

def base(x, ground, fh, **kw):
    P = {"hx": x, "hy": ground - 0.48 * fh, "torso": 0, "head": 0, "aL1": 14, "aL2": 10, "aR1": 14, "aR2": 10,
         "lL1": 3, "lL2": 0, "lR1": -3, "lR2": 0}
    P.update(kw)
    return P


def headbop(t, x, g, fh, bpm=BPM):
    b = t * bpm / 60
    s = math.sin(b * 2 * math.pi)
    return base(x, g, fh, hy=g - 0.48 * fh + 0.025 * fh * (1 - abs(s)) * -1 + 0.02 * fh * s * s, torso=5 * s, head=14 * s,
                aL1=22 + 10 * s, aL2=60, aR1=22 - 10 * s, aR2=60, lL1=8, lL2=-6, lR1=-10, lR2=6)


def shoulder(t, x, g, fh, bpm=BPM):
    b = t * bpm / 60
    s = math.sin(b * math.pi * 2)
    q = math.sin(b * math.pi * 2 + math.pi / 2)
    return base(x, g, fh, torso=10 * s, head=-8 * s, aL1=40 + 20 * q, aL2=95, aR1=40 - 20 * q, aR2=95,
                lL1=10, lL2=-10, lR1=-14, lR2=8, hy=g - 0.46 * fh + 0.02 * fh * abs(s))


def footwork(t, x, g, fh, bpm=BPM):
    b = t * bpm / 60 * 2
    s = math.sin(b * math.pi * 2)
    c = math.cos(b * math.pi * 2)
    return base(x + 14 * s, g, fh, hy=g - 0.44 * fh + 0.02 * fh * abs(c), torso=8 * c, head=6,
                aL1=50 + 25 * c, aL2=110, aR1=50 - 25 * c, aR2=110,
                lL1=26 * s, lL2=26 * s - 26 * max(0, c), lR1=-26 * s, lR2=-26 * s - 26 * max(0, -c))


def freeze(x, g, fh, side=1):
    return base(x, g, fh, hy=g - 0.43 * fh, torso=10 * side, head=-12 * side, aL1=150 * 1.0, aL2=170, aR1=70, aR2=-10,
                lL1=22 * side, lL2=10, lR1=-26 * side, lR2=-14)


def run_arms(t, x, g, fh, speed=7.0):
    ph = t * speed
    l = 32 * math.sin(ph)
    return base(x, g, fh, hy=g - 0.46 * fh - abs(math.sin(ph)) * 0.02 * fh, torso=8, head=-4,
                aL1=100, aL2=104, aR1=100, aR2=104, lL1=l, lL2=l - 20 * (1 + math.cos(ph)), lR1=-l, lR2=-l - 20 * (1 - math.cos(ph)))


# ───────────────────────── hiệu ứng ─────────────────────────

def graffiti(im, text, x, y, size, fill, ang=-6, k=1.0, outline=WHITE):
    if k <= 0.02:
        return
    f = _font(int(size * (0.6 + 0.4 * k)))
    layer = Image.new("RGBA", (int(f.getlength(text)) + 60, int(size * 1.7)), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    cx, cy = layer.width / 2, layer.height / 2
    for dx, dy in ((7, 8), (-3, 6)):
        ld.text((cx + dx, cy + dy), text, font=f, fill=(0, 0, 0, 190), anchor="mm", stroke_width=6, stroke_fill=(0, 0, 0, 190))
    ld.text((cx, cy), text, font=f, fill=fill, anchor="mm", stroke_width=6, stroke_fill=outline)
    layer = layer.rotate(ang, resample=Image.BICUBIC, expand=True)
    layer.putalpha(layer.getchannel("A").point(lambda v: int(v * min(1.0, k * 1.5))))
    im.alpha_composite(layer, (int(x - layer.width / 2), int(y - layer.height / 2)))


def note(d, x, y, s, col):
    d.ellipse([x - s * 0.5, y, x + s * 0.5, y + s * 0.7], fill=col)
    d.line([(x + s * 0.45, y + s * 0.3), (x + s * 0.45, y - s * 1.2)], fill=col, width=int(max(3, s * 0.18)))
    d.line([(x + s * 0.45, y - s * 1.2), (x + s * 1.0, y - s * 0.8)], fill=col, width=int(max(3, s * 0.18)))


def dust(im, x, y, k):
    d = ImageDraw.Draw(im, "RGBA")
    for n in range(14):
        a = n / 14 * math.pi
        r = 14 + 60 * k + n % 3 * 8
        px, py = x + math.cos(a) * r * (1 if n % 2 else -1) * 1.1, y - math.sin(a) * r * 0.55
        rr = (10 + n % 4 * 5) * (1 - k * 0.7)
        d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=(240, 236, 228, int(200 * (1 - k))))


def sparks(im, x, y, t, col=(255, 220, 110)):
    d = ImageDraw.Draw(im, "RGBA")
    for n in range(10):
        a = (n * 36 + t * 400) % 360
        L = 18 + (n * 7 + int(t * 60)) % 36
        d.line([(x, y), (x + math.cos(rad(a)) * L, y + math.sin(rad(a)) * L)], fill=col + (230,), width=3)


def ink_burst(im, x, y, k, col=(255, 255, 255)):
    d = ImageDraw.Draw(im, "RGBA")
    for n in range(14):
        a = rad(n * 360 / 14)
        r0, r1 = 40 + 120 * k, 70 + 190 * k
        d.line([(x + math.cos(a) * r0, y + math.sin(a) * r0), (x + math.cos(a) * r1, y + math.sin(a) * r1)], fill=col + (int(220 * (1 - k)),), width=6)


def wave_lines(im, t, y, amp, col=(255, 255, 255, 190), x0=0, x1=W):
    d = ImageDraw.Draw(im, "RGBA")
    pts = [(x, y + math.sin(x * 0.04 + t * 9) * amp * (0.5 + 0.5 * math.sin(x * 0.013 + t * 3))) for x in range(x0, x1, 10)]
    d.line(pts, fill=col, width=5, joint="curve")


# ───────────────────────── các màn theo thời gian thật ─────────────────────────

class Show:
    def __init__(self, bpm=BPM):
        self.bpm = bpm
        self.boy = Wanderer(False, 330, 1)
        self.girl = Wanderer(True, 330, -1)
        self.drops = [16.53, 25.7, 48.1]
        self.beat = 60.0 / bpm

    def fig(self, im, who, P, t, expr="neutral", props=(), face=None, scale=1.0, sx=1.0, seed=0):
        ch = self.boy if who == "boy" else self.girl
        scale = scale * 1.22
        ch.fh = 330 * scale
        ch.TH, ch.SH, ch.TO = 0.24 * ch.fh, 0.24 * ch.fh, 0.27 * ch.fh
        ch.UA, ch.FA, ch.HR = 0.17 * ch.fh, 0.16 * ch.fh, 0.15 * ch.fh
        layer = Image.new("RGBA", im.size, (0, 0, 0, 0)) if sx != 1.0 else im
        pts = ch.draw(layer, P, t=t, seed=int(t * 12) + seed, expr=expr, props=props, face=face)
        if sx != 1.0:
            bbox = layer.getbbox()
            if bbox:
                crop = layer.crop(bbox)
                cx = P["hx"]
                nw = max(4, int(crop.width * abs(sx)))
                crop = crop.resize((nw, crop.height), Image.BICUBIC)
                if sx < 0:
                    crop = crop.transpose(Image.FLIP_LEFT_RIGHT)
                im.alpha_composite(crop, (int(cx - nw / 2), bbox[1]))
        return pts

    # --- 0.0 đến 2.1: mở màn, rơi xuống đúng nhịp bass, bắt chước người thật ---
    def act_open(self, im, t, G=700):
        fh = 0.78
        if t < 0.55:
            return
        fall = ss((t - 0.55) / 0.35)
        y = G - (1 - fall) ** 2 * 520 if t < 0.9 else G
        P = footwork(t, 190, y, 330 * fh) if t > 1.2 else freeze(190, y, 330 * fh) if t < 1.0 else headbop(t, 190, y, 330 * fh)
        squash = 1.0
        if 0.88 < t < 1.1:
            squash = 0.9
        self.fig(im, "boy", P, t, "joy", ("shades",), scale=fh)
        if 0.88 <= t < 1.4:
            dust(im, 190, G + 4, ss((t - 0.88) / 0.5))
        if 0.88 <= t < 1.1:
            ink_burst(im, 190, G - 30, (t - 0.88) / 0.22)

    # --- 2.1 đến 3.6: ló đầu bên phải, gật theo nhịp ---
    def act_peek(self, im, t):
        k = ss((t - 2.1) / 0.25)
        P = headbop(t, 1300 + (1 - k) * 200, 660, 330 * 0.9)
        self.fig(im, "girl", P, t, "smile", scale=0.9, face=-1)

    # --- 3.6 đến 8.7: trên mái nhà, loa mini, nốt nhạc thành graffiti, nhảy xuống ---
    def act_roof(self, im, t, local):
        d = ImageDraw.Draw(im, "RGBA")
        k = ss(local / 2.0)
        if t < 7.0:
            x, y = 820, 468                                         # mái nhà trong khu dân cư (ảnh flycam)
            P = headbop(t, x, y, 330 * 0.42)
            self.fig(im, "boy", P, t, "hype", ("megaphone",), scale=0.42)
            for n in range(5):
                a = (t * 0.6 + n * 0.2) % 1.0
                nx, ny = x + 60 + a * 260, y - 130 - a * 180 + math.sin(a * 8 + n) * 16
                col = [(255, 90, 160), (110, 220, 255), (255, 224, 80), (170, 255, 120), (255, 150, 60)][n]
                note(d, nx, ny, 22 + a * 18, col + (int(240 * (1 - a * 0.6)),))
        else:                                                       # zoom xuống, nhảy từ mái nhà xuống đường làng
            j = ss((t - 7.0) / 1.2)
            x = 620 - 260 * j + 80 * math.sin(j * 3)
            y = 560 - 30 * j - math.sin(j * math.pi) * 150
            P = run_arms(t, x, y, 330 * (0.42 + 0.3 * j), 5)
            P["aL1"], P["aR1"] = 150, 150
            self.fig(im, "boy", P, t, "wow", scale=0.42 + 0.3 * j)

    # --- 8.7 đến 11.3: hai người trò chuyện, người que nữ gật liên tục, cả hai chỉ vào sản phẩm ---
    def act_talk(self, im, t, local):
        P = headbop(t * 1.5, 1180, 700, 330 * 0.74)
        self.fig(im, "girl", P, t, "smile", scale=0.74, face=-1)
        if local > 1.2:
            sx = math.cos(max(0, local - 1.2) * 9) if local < 1.9 else 1
            P2 = shoulder(t, 140, 700, 330 * 0.74)
            if local > 1.9:
                P2["aR1"], P2["aR2"] = 95, 92
            self.fig(im, "boy", P2, t, "hype", scale=0.74, sx=sx)

    # --- 13.0 đến 16.3: drill dance battle, hai người que phía trước ---
    def act_battle(self, im, t, local):
        seq = [headbop, shoulder, footwork]
        mv = int(local / 0.62)
        fh = 330 * 0.9
        if t < 16.0:
            fn = seq[(mv // 2) % 3]
            self.fig(im, "boy", fn(t, 150, 710, fh), t, "hype", scale=0.9)
            self.fig(im, "girl", fn(t + 0.3, 1130, 710, fh), t, "hype", scale=0.9, face=-1)
        else:
            q = min(1.0, (t - 16.0) / 0.5)
            self.fig(im, "boy", freeze(150, 710, fh, 1), t, "joy", ("shades",), scale=0.9)
            self.fig(im, "girl", freeze(1130, 710, fh, -1), t, "joy", scale=0.9, face=-1)

    # --- 17.9 đến 20.6: chạy qua cánh đồng, nón lá quá khổ ---
    def act_field(self, im, t, local):
        d = ImageDraw.Draw(im, "RGBA")
        x = -100 + local * 520 if local < 2.4 else 1150
        self.fig(im, "girl", run_arms(t, 80 + (local / 2.7) * 1100, 706, 330 * 0.48, 6.5), t, "joy", scale=0.48, face=1)
        self.fig(im, "boy", footwork(t, 1130, 706, 330 * 0.6), t, "hype", ("nonla",), scale=0.6, face=-1)
        for n in range(20):                                         # lúa tiền cảnh đung đưa theo nhịp
            bx = n * 66 + 20
            sw = math.sin(t * 4 + n) * 12 + math.sin(t * 2 * math.pi * 96 / 60) * 6
            d.line([(bx, H + 10), (bx + sw, H - 70), (bx + sw * 1.8, H - 120)], fill=(236, 196, 70, 220), width=5)
            for m in range(4):
                d.ellipse([bx + sw * 1.6 - 5, H - 120 + m * 12 - 5, bx + sw * 1.6 + 5, H - 120 + m * 12 + 5], fill=(250, 214, 90, 230))

    # --- 20.6 đến 24.0: nằm trên lá lúa khổng lồ lướt theo flycam, sóng âm thành graffiti ---
    def act_leaf(self, im, t, local):
        d = ImageDraw.Draw(im, "RGBA")
        x = 160 + local * 280
        y = 170 + math.sin(local * 2) * 30
        leaf = [(x - 220, y + 40), (x - 60, y - 20), (x + 120, y - 10), (x + 250, y + 30), (x + 120, y + 56), (x - 60, y + 66)]
        d.polygon(leaf, fill=(110, 190, 70, 235), outline=WHITE)
        d.line([(x - 200, y + 44), (x + 230, y + 30)], fill=(70, 140, 50, 255), width=5)
        P = base(x, y + 28, 330 * 0.34, torso=84, head=-10, aL1=100, aL2=130, aR1=90, aR2=60, lL1=80, lL2=94, lR1=70, lR2=90, hy=y + 6)
        self.fig(im, "boy", P, t, "joy", ("shades",), scale=0.34)
        wave_lines(im, t, 290, 36)
        wave_lines(im, t + 0.3, 320, 24, (255, 224, 90, 190))

    # --- 26.3 đến 28.7: kính lúp soi sản phẩm, người bán hàng tí hon, chữ graffiti ---
    def act_product(self, im, t, local):
        P = shoulder(t, 150, 700, 330 * 0.78)
        P["aR1"], P["aR2"] = 78, 70
        self.fig(im, "boy", P, t, "wow", ("magnifier",), scale=0.78)
        graffiti(im, "SẢN VẬT QUÊ NHÀ", 360, 120, 70, (255, 210, 50, 255), -5, ss(local / 0.4))

    # --- 30.7 đến 34.3: máy khoan tí hon, tia sáng theo bass ---
    def act_drill(self, im, t, local):
        P = headbop(t * 2, 150, 704, 330 * 0.78)
        P["aR1"], P["aR2"] = 70, 82
        pts = self.fig(im, "boy", P, t, "hype", ("goggles", "drill"), scale=0.78)
        if (t * self.bpm / 60) % 1.0 < 0.5:
            sparks(im, pts["hR"][0] + 86, pts["hR"][1] - 2, t)

    # --- 36.9 đến 38.9: nữ cầm micro rap, đám người que nhỏ cổ vũ ---
    def act_rap(self, im, t, local):
        P = shoulder(t, 160, 704, 330 * 0.78)
        P["aR1"], P["aR2"] = 150, 120
        self.fig(im, "girl", P, t, "hype", ("mic",), scale=0.78, face=1)
        for n in range(4):
            Pn = headbop(t + n * 0.2, 1010 + n * 62, 706, 330 * 0.3)
            Pn["aL1"], Pn["aR1"] = 150 + 10 * math.sin(t * 9 + n), 150 - 10 * math.sin(t * 9 + n)
            Pn["aL2"], Pn["aR2"] = 170, 170
            self.fig(im, "boy" if n % 2 == 0 else "girl", Pn, t, "joy", scale=0.3, face=-1)

    # --- 42.5 đến 44.5: lên xe, nhún nhảy theo nhịp ---
    def act_car(self, im, t, local):
        P = headbop(t * 1.5, 1100, 706, 330 * 0.6)
        self.fig(im, "boy", P, t, "joy", ("shades",), scale=0.6, face=-1)
        P2 = headbop(t * 1.5 + 0.2, 960, 706, 330 * 0.6)
        self.fig(im, "girl", P2, t, "joy", ("shades",), scale=0.6, face=-1)

    # --- 44.5 đến 46.3: cầm cờ trên trời, trên xe cổ ---
    def act_flag(self, im, t, local):
        P = shoulder(t, 170, 330, 330 * 0.42)
        P["aR1"], P["aR2"] = 150, 168
        self.fig(im, "boy", P, t, "hype", ("flag",), scale=0.42)

    # --- 46.3 đến 48.0: xoay máy khoan như micro DJ rồi freeze trên bass drop 48.1 ---
    def act_dj(self, im, t, local):
        if t < 48.1:
            P = shoulder(t * 1.5, 150, 704, 330 * 0.78)
            P["aR1"], P["aR2"] = 130 + 40 * math.sin(t * 12), 150
            self.fig(im, "boy", P, t, "hype", ("goggles", "drill"), scale=0.78)
        else:
            self.fig(im, "boy", freeze(190, 704, 330 * 0.78, 1), t, "joy", ("shades",), scale=0.78)
            self.fig(im, "girl", freeze(1090, 704, 330 * 0.78, -1), t, "joy", ("shades",), scale=0.78, face=-1)


    # --- khoảng trống: chuyển cảnh nhanh, gặt lúa, chân dung, đám đông, lời kết ---
    def act_wipe(self, im, t, local):
        x = -150 + ss(local / 1.0) * 1500
        P = run_arms(t, x, 690, 330 * 0.8, 9.0)
        d = ImageDraw.Draw(im, "RGBA")
        for n in range(8):
            d.line([(x - 40 - n * 38, 690 - 80 - n * 22), (x - 200 - n * 38, 690 - 80 - n * 22)], fill=(255, 255, 255, 170 - n * 18), width=7)
        self.fig(im, "girl", P, t, "hype", scale=0.8, face=1)
        if local > 1.0:
            graffiti(im, "QUÊ", 640, 150, 120, (255, 80, 130, 255), -8, ss((local - 1.0) / 0.3))

    def act_harvest(self, im, t, local):
        P = shoulder(t, 1130, 706, 330 * 0.78)
        P["aR1"], P["aR2"] = 150, 150
        self.fig(im, "boy", P, t, "joy", scale=0.78, face=-1)
        d = ImageDraw.Draw(im, "RGBA")
        for n in range(5):
            a = (t * 0.7 + n * 0.2) % 1.0
            note(d, 1000 + n * 40, 560 - a * 160, 18, (255, 224, 90, int(230 * (1 - a))))

    def act_portrait(self, im, t, local):
        P = headbop(t, 1150, 706, 330 * 0.78)
        P["aL1"], P["aR1"], P["aL2"], P["aR2"] = 150, 150, 170, 170
        self.fig(im, "girl", P, t, "joy", scale=0.78, face=-1)

    def act_crowd(self, im, t, local):
        fn = [headbop, shoulder][int(local / 0.62) % 2]
        self.fig(im, "boy", fn(t, 140, 712, 330 * 0.85), t, "hype", scale=0.85)
        self.fig(im, "girl", fn(t + 0.3, 1140, 712, 330 * 0.85), t, "hype", scale=0.85, face=-1)

    def act_thumbs(self, im, t, local):
        P = headbop(t, 140, 712, 330 * 0.85)
        P["aR1"], P["aR2"] = 130, 150
        self.fig(im, "boy", P, t, "smile", ("shades",), scale=0.85)
        d = ImageDraw.Draw(im, "RGBA")
        for n in range(3):
            a = (t * 0.8 + n * 0.33) % 1.0
            cx, cy = 260 + n * 40, 380 - a * 150
            d.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=(255, 80, 130, int(230 * (1 - a))))

    def act_end(self, im, t, local):
        k = ss(local / 0.6)
        out = ss((local - 1.6) / 0.6)
        x1 = 150 - out * 400
        x2 = 1130 + out * 400
        self.fig(im, "boy", freeze(x1, 704, 330 * 0.8, 1), t, "joy", ("shades",), scale=0.8)
        self.fig(im, "girl", freeze(x2, 704, 330 * 0.8, -1), t, "joy", ("shades",), scale=0.8, face=-1)

    def overlay(self, t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        if t < 2.1:
            self.act_open(im, t)
        elif t < 3.6:
            self.act_peek(im, t)
        elif t < 8.7:
            self.act_roof(im, t, t - 3.6)
        elif t < 11.3:
            self.act_talk(im, t, t - 8.7)
        elif 11.3 <= t < 13.0:
            self.act_wipe(im, t, t - 11.3)
        elif 13.0 <= t < 16.9:
            self.act_battle(im, t, t - 13.0)
        elif 17.9 <= t < 20.6:
            self.act_field(im, t, t - 17.9)
        elif 20.6 <= t < 24.0:
            self.act_leaf(im, t, t - 20.6)
        elif 24.0 <= t < 26.3:
            self.act_harvest(im, t, t - 24.0)
        elif 26.3 <= t < 28.7:
            self.act_product(im, t, t - 26.3)
        elif 28.7 <= t < 30.7:
            self.act_portrait(im, t, t - 28.7)
        elif 30.7 <= t < 34.3:
            self.act_drill(im, t, t - 30.7)
        elif 34.3 <= t < 36.9:
            self.act_crowd(im, t, t - 34.3)
        elif 36.9 <= t < 38.9:
            self.act_rap(im, t, t - 36.9)
        elif 38.9 <= t < 40.9:
            self.act_thumbs(im, t, t - 38.9)
        elif 40.9 <= t < 42.5:
            self.act_drill(im, t, t - 40.9)
        elif 42.5 <= t < 44.5:
            self.act_car(im, t, t - 42.5)
        elif 44.5 <= t < 46.3:
            self.act_flag(im, t, t - 44.5)
        elif 46.3 <= t < 49.4:
            self.act_dj(im, t, t - 46.3)
        elif 49.4 <= t < 52.2:
            self.act_end(im, t, t - 49.4)
        for dr, txt, col in ((16.53, 'DROP!', (255, 70, 90, 255)), (25.7, 'QUÊ TA!', (255, 210, 50, 255)), (48.1, 'FREEZE!', (110, 230, 255, 255))):
            if 0 <= t - dr < 0.9:
                graffiti(im, txt, 640, 110, 110, col, -6, ss((t - dr) / 0.2))
        return im

    def shake(self, t):
        s = 0.0
        for dr in self.drops:
            if 0 <= t - dr < 0.4:
                s = max(s, 14 * (1 - (t - dr) / 0.4))
        # nhịp nhẹ theo kick
        return s


def render(src_path, out_path, bpm=BPM):
    from moviepy import VideoFileClip, VideoClip
    src = VideoFileClip(src_path)
    show = Show(bpm)

    def make(t):
        fr = Image.fromarray(src.get_frame(min(t, src.duration - 0.05))).convert("RGBA").resize((W, H), Image.BICUBIC)
        ov = show.overlay(t)
        fr.alpha_composite(ov)
        s = show.shake(t)
        arr = np.array(fr.convert("RGB"))
        if s > 0.5:
            dx, dy = int(math.sin(t * 90) * s), int(math.cos(t * 77) * s * 0.6)
            arr = np.roll(arr, (dy, dx), axis=(0, 1))
        for dr in show.drops:                                        # chớp trắng ngắn trên cú bass
            if 0 <= t - dr < 0.08:
                arr = np.clip(arr.astype(np.float32) + 70 * (1 - (t - dr) / 0.08), 0, 255).astype("uint8")
        return arr

    clip = VideoClip(make, duration=src.duration).with_fps(FPS).with_audio(src.audio)
    clip.write_videofile(out_path, fps=FPS, codec="libx264", audio_codec="aac", preset="veryfast", threads=4, logger=None)
    return {"video_path": out_path, "duration": src.duration}


if __name__ == "__main__":
    print(render(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else BPM))
