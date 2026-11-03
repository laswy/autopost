"""
MV hoạt hình người que 100% (không dùng hình người thật), 9:16, 11 cảnh theo kịch bản "Little Wanderer" hip-hop drill.
Video nguồn chỉ dùng để lấy nhạc (âm thanh). Nhân vật: Little Wanderer (nam), bạn nữ, ba cô dân làng áo đỏ, người thợ áo đen.

Chạy:
    python -m skills.wanderer_mv music_src.mp4 out.mp4
"""

import math
import subprocess
import sys
import tempfile
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from skills.explainer_video import _font
from skills.hybrid_stickman import (BLACK, ORANGE, RED, WHITE, Wanderer, base, dust, footwork, freeze, graffiti, headbop,
                                    ink_burst, note, run_arms, shoulder, sparks)
from skills.story_stickman import ss

W, H = 1080, 1920
FPS = 24
BPM = 96.0
INK = (24, 22, 30, 255)
G = 1580                        # mặt đất tiền cảnh
DROPS = (16.53, 25.7, 48.1)


def mixc(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(len(a)))


def grad(top, bot, y0=0, y1=H, w=W, h=H):
    col = np.zeros((h, 1, 3), np.float32)
    for y in range(h):
        k = max(0.0, min(1.0, (y - y0) / max(1, (y1 - y0))))
        col[y, 0] = mixc(top, bot, k)
    return Image.fromarray(np.repeat(col, w, axis=1).astype("uint8")).convert("RGBA")


def house(d, x, gy, w, h, wall, roof, door=True):
    d.rectangle([x, gy - h, x + w, gy], fill=wall, outline=INK, width=5)
    d.polygon([(x - 22, gy - h), (x + w / 2, gy - h - w * 0.34), (x + w + 22, gy - h)], fill=roof, outline=INK)
    d.line([(x - 22, gy - h), (x + w + 22, gy - h)], fill=INK, width=5)
    for wx in (x + w * 0.12, x + w * 0.62):
        d.rectangle([wx, gy - h * 0.72, wx + w * 0.24, gy - h * 0.42], fill=(190, 226, 240, 255), outline=INK, width=4)
    if door:
        d.rectangle([x + w * 0.4, gy - h * 0.46, x + w * 0.6, gy], fill=(120, 78, 50, 255), outline=INK, width=4)


def tree(d, x, gy, s=1.0):
    d.rectangle([x - 10 * s, gy - 130 * s, x + 10 * s, gy], fill=(96, 66, 44, 255))
    for ox, oy, r in ((0, -170, 70), (-50, -130, 52), (50, -135, 55)):
        d.ellipse([x + ox * s - r * s, gy + oy * s - r * s, x + ox * s + r * s, gy + oy * s + r * s], fill=(70, 150, 72, 255), outline=INK, width=3)


def cloud(d, x, y, s=1.0, a=230):
    for ox, oy, r in ((0, 0, 50), (46, 10, 40), (-46, 12, 38), (16, -22, 40)):
        d.ellipse([x + ox * s - r * s, y + oy * s - r * s, x + ox * s + r * s, y + oy * s + r * s], fill=(255, 255, 255, a))


def setfh(ch, fh):
    ch.fh = fh
    ch.TH, ch.SH, ch.TO = 0.24 * fh, 0.24 * fh, 0.27 * fh
    ch.UA, ch.FA, ch.HR = 0.17 * fh, 0.16 * fh, 0.15 * fh


class MV:
    def __init__(self, audio_wav):
        self.b = Wanderer(False)
        self.g = Wanderer(True, face=-1)
        self.v = [Wanderer(True, face=1) for _ in range(3)]
        for v in self.v:
            v.headphones, v.hairnet, v.hood = False, True, (214, 40, 48, 255)
        self.worker = Wanderer(False, face=-1)
        self.worker.headphones, self.worker.cap, self.worker.glasses, self.worker.hood = False, True, True, (30, 30, 36, 255)
        self.cache = {}
        w = wave.open(audio_wav)
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        hop = int(sr / FPS)
        self.env = np.array([np.sqrt((x[i * hop:(i + 1) * hop] ** 2).mean()) for i in range(len(x) // hop)])
        self.env = self.env / (self.env.max() + 1e-6)

    def E(self, t):
        return float(self.env[min(len(self.env) - 1, max(0, int(t * FPS)))])

    def beat(self, t):
        return (t * BPM / 60) % 1.0

    def fig(self, im, ch, P, t, expr="neutral", props=(), face=None, fh=700, sx=1.0, seed=0):
        setfh(ch, fh)
        layer = Image.new("RGBA", im.size, (0, 0, 0, 0)) if sx != 1.0 else im
        pts = ch.draw(layer, P, t=t, seed=int(t * 12) + seed, expr=expr, props=props, face=face)
        if sx != 1.0:
            bb = layer.getbbox()
            if bb:
                crop = layer.crop(bb)
                nw = max(4, int(crop.width * abs(sx)))
                crop = crop.resize((nw, crop.height), Image.BICUBIC)
                if sx < 0:
                    crop = crop.transpose(Image.FLIP_LEFT_RIGHT)
                im.alpha_composite(crop, (int(P["hx"] - nw / 2), bb[1]))
        return pts

    # ───────── nền (vẽ một lần, lưu cache) ─────────
    def bg(self, key):
        if key in self.cache:
            return self.cache[key]
        im = getattr(self, "bg_" + key)()
        self.cache[key] = im
        return im

    def bg_court(self):
        im = grad((255, 156, 92), (255, 226, 160), 0, 1100)
        d = ImageDraw.Draw(im, "RGBA")
        d.ellipse([420, 760, 700, 1040], fill=(255, 244, 200, 255))
        for x in (30, 330, 760):
            house(d, x, 1350, 270, 240, (240, 214, 170, 255), (178, 70, 58, 255))
        tree(d, 640, 1350, 1.2)
        d.rectangle([0, 1350, W, H], fill=(184, 150, 120, 255))
        d.rectangle([0, 1350, W, 1370], fill=(150, 118, 92, 255))
        # tường graffiti
        d.rectangle([560, 780, 1060, 1350], fill=(52, 56, 90, 255), outline=INK, width=6)
        for i, col in enumerate(((255, 80, 140), (80, 220, 255), (255, 214, 60), (120, 255, 140), (255, 140, 40))):
            d.ellipse([590 + i * 90, 840 + (i % 2) * 120, 700 + i * 90, 950 + (i % 2) * 120], outline=col + (255,), width=12)
        d.line([(600, 1250), (1040, 1180)], fill=(255, 255, 255, 255), width=10)
        return im

    def bg_street(self):
        im = grad((140, 200, 255), (232, 244, 255), 0, 1100)
        d = ImageDraw.Draw(im, "RGBA")
        cloud(d, 200, 260, 1.8)
        cloud(d, 800, 420, 1.4)
        for i, x in enumerate((-40, 280, 600, 880)):
            house(d, x, 1380, 250, 260 + (i % 2) * 60, [(250, 226, 190), (210, 236, 214), (240, 210, 210), (214, 226, 244)][i] + (255,),
                  [(200, 80, 64), (70, 110, 180), (214, 150, 50), (160, 60, 70)][i] + (255,))
        for x in (210, 520, 800):
            tree(d, x, 1385, 1.0)
        d.rectangle([0, 1380, W, H], fill=(96, 98, 108, 255))
        for x in range(0, W, 180):
            d.rectangle([x, 1620, x + 90, 1640], fill=(250, 240, 200, 255))
        return im

    def bg_aerial(self):                                      # nhìn từ trên cao, cuộn dọc
        hh = 3600
        im = Image.new("RGBA", (W, hh), (96, 160, 80, 255))
        d = ImageDraw.Draw(im, "RGBA")
        rnd = np.random.RandomState(5)
        for y in range(0, hh, 36):
            d.line([(0, y), (W, y)], fill=(88, 150, 74, 120), width=3)
        for x in (200, 560, 900):                              # đường làng
            d.rectangle([x - 28, 0, x + 28, hh], fill=(222, 204, 168, 255))
        for y in (500, 1300, 2100, 2900):
            d.rectangle([0, y - 24, W, y + 24], fill=(222, 204, 168, 255))
        for i in range(70):
            x = rnd.randint(20, W - 160)
            y = rnd.randint(40, hh - 160)
            w_, h_ = rnd.randint(90, 150), rnd.randint(80, 120)
            col = [(210, 90, 60), (70, 110, 190), (230, 160, 60), (150, 150, 160), (200, 70, 90)][i % 5]
            d.rectangle([x + 10, y + 12, x + w_ + 10, y + h_ + 12], fill=(40, 70, 40, 90))
            d.rectangle([x, y, x + w_, y + h_], fill=col + (255,), outline=INK, width=3)
            d.line([(x, y + h_ / 2), (x + w_, y + h_ / 2)], fill=(0, 0, 0, 120), width=3)
        for i in range(60):
            x, y = rnd.randint(0, W), rnd.randint(0, hh)
            r = rnd.randint(20, 46)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(46, 120, 60, 255), outline=(30, 90, 44, 255), width=3)
        return im

    def bg_stall(self):
        im = Image.new("RGBA", (W, H), (244, 226, 196, 255))
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, 1380, W, H], fill=(170, 120, 84, 255))
        d.rectangle([60, 300, 1020, 620], fill=(204, 48, 56, 255), outline=INK, width=8)
        d.text((540, 460), "ĐẶC SẢN QUÊ HƯƠNG", font=_font(86), fill=(255, 244, 220, 255), anchor="mm", stroke_width=4, stroke_fill=INK)
        for y in (700, 900):
            d.rectangle([60, y, 1020, y + 18], fill=(120, 80, 50, 255))
            for x in range(90, 1000, 120):
                d.rectangle([x, y - 96, x + 84, y], fill=(238, 238, 244, 255), outline=INK, width=3)
                d.rectangle([x + 8, y - 70, x + 76, y - 30], fill=(214, 60, 60, 255))
        d.rectangle([0, 1320, W, 1400], fill=(122, 82, 56, 255), outline=INK, width=6)
        d.rectangle([420, 1150, 650, 1320], fill=(250, 250, 252, 255), outline=INK, width=6)
        d.rectangle([436, 1190, 634, 1290], fill=(214, 60, 60, 255))
        d.text((535, 1240), "BÚN TƯƠI", font=_font(38), fill=WHITE, anchor="mm")
        return im

    def bg_factory(self):
        im = grad((120, 188, 250), (214, 236, 255), 0, 1100)
        d = ImageDraw.Draw(im, "RGBA")
        cloud(d, 260, 300, 2.0)
        cloud(d, 860, 520, 1.5)
        d.rectangle([0, 700, W, 1400], fill=(232, 236, 240, 255), outline=INK, width=6)
        for x in range(0, W, 120):
            d.polygon([(x, 700), (x + 60, 560), (x + 120, 700)], fill=(170, 180, 196, 255), outline=INK)
        for x in range(60, W, 190):
            d.rectangle([x, 820, x + 110, 940], fill=(120, 170, 220, 255), outline=INK, width=4)
        d.rectangle([380, 1080, 700, 1400], fill=(120, 130, 146, 255), outline=INK, width=6)
        d.rectangle([0, 1400, W, H], fill=(104, 108, 120, 255))
        d.ellipse([120, 1640, 520, 1720], fill=(150, 190, 230, 120))
        return im

    def bg_field(self):
        im = grad((255, 190, 110), (255, 234, 170), 0, 900)
        d = ImageDraw.Draw(im, "RGBA")
        d.ellipse([360, 560, 740, 940], fill=(255, 246, 210, 255))
        d.polygon([(0, 960), (200, 780), (420, 940), (700, 760), (1080, 960)], fill=(120, 130, 170, 255))
        d.rectangle([0, 940, W, H], fill=(222, 182, 70, 255))
        for i in range(26):                                    # hàng lúa phối cảnh
            y = 960 + (i ** 1.7) * 6
            if y > H:
                break
            d.line([(0, y), (W, y)], fill=(196, 150, 40, 140), width=int(3 + i * 0.5))
        return im

    def bg_aerialfield(self):
        hh = 3600
        im = Image.new("RGBA", (W, hh), (210, 170, 60, 255))
        d = ImageDraw.Draw(im, "RGBA")
        rnd = np.random.RandomState(9)
        x = 0
        while x < W:
            w_ = rnd.randint(150, 260)
            y = 0
            while y < hh:
                h_ = rnd.randint(260, 520)
                col = [(226, 182, 60), (214, 164, 40), (240, 200, 80), (196, 160, 54)][rnd.randint(0, 4)]
                d.rectangle([x, y, x + w_ - 14, y + h_ - 14], fill=col + (255,), outline=(120, 90, 30, 255), width=3)
                for l in range(0, h_ - 20, 22):
                    d.line([(x + 6, y + l), (x + w_ - 20, y + l)], fill=(160, 120, 30, 90), width=3)
                y += h_
            x += w_
        for cx in (260, 640, 940):
            d.rectangle([cx, 0, cx + 34, hh], fill=(110, 170, 200, 255))
        return im

    def bg_shop(self):
        im = Image.new("RGBA", (W, H), (248, 232, 204, 255))
        d = ImageDraw.Draw(im, "RGBA")
        for y in (330, 560, 790):
            d.rectangle([0, y, W, y + 20], fill=(130, 90, 60, 255))
            for x in range(10, W, 120):
                d.rectangle([x, y - 110, x + 90, y], fill=(214, 60, 60, 255), outline=INK, width=3)
                d.rectangle([x + 10, y - 84, x + 80, y - 40], fill=(250, 244, 230, 255))
        d.rectangle([0, 1180, W, 1360], fill=(126, 84, 56, 255), outline=INK, width=6)
        d.rectangle([0, 1360, W, H], fill=(176, 136, 100, 255))
        return im

    def bg_workshop(self):
        im = Image.new("RGBA", (W, H), (226, 214, 196, 255))
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, 1400, W, H], fill=(150, 130, 108, 255))
        d.rectangle([660, 360, 1020, 760], fill=(160, 210, 240, 255), outline=INK, width=8)
        d.line([(840, 360), (840, 760)], fill=INK, width=6)
        d.line([(660, 560), (1020, 560)], fill=INK, width=6)
        for x in (40, 200, 350):                                # bao gạo
            for y in (1180, 1030):
                d.rounded_rectangle([x, y, x + 140, y + 160], 14, fill=(244, 244, 238, 255), outline=INK, width=4)
        d.rectangle([380, 1290, 1060, 1330], fill=(126, 84, 50, 255), outline=INK, width=5)
        d.rectangle([420, 1330, 450, 1420], fill=(100, 66, 40, 255))
        d.rectangle([980, 1330, 1010, 1420], fill=(100, 66, 40, 255))
        return im

    def bg_stage(self):
        im = grad((40, 24, 70), (120, 40, 90), 0, 1500)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, 1450, W, H], fill=(44, 30, 50, 255))
        d.rectangle([80, 360, 1000, 1100], fill=(204, 40, 56, 255), outline=(255, 255, 255, 255), width=10)
        d.text((540, 560), "QUÊ", font=_font(240), fill=(255, 236, 140, 255), anchor="mm", stroke_width=10, stroke_fill=INK)
        d.text((540, 800), "HƯƠNG", font=_font(220), fill=(255, 255, 255, 255), anchor="mm", stroke_width=10, stroke_fill=INK)
        for cx in (160, 540, 920):
            d.polygon([(cx, 0), (cx - 160, 1450), (cx + 160, 1450)], fill=(255, 240, 180, 40))
        return im

    def bg_road(self):
        im = grad((130, 200, 250), (240, 248, 255), 0, 1200)
        d = ImageDraw.Draw(im, "RGBA")
        cloud(d, 220, 300, 2.0)
        cloud(d, 800, 480, 1.6)
        d.polygon([(0, 1000), (260, 820), (560, 980), (820, 800), (1080, 960), (1080, 1300), (0, 1300)], fill=(90, 150, 120, 255))
        d.rectangle([0, 1300, W, H], fill=(86, 88, 100, 255))
        for x in range(0, W, 200):
            d.rectangle([x, 1750, x + 100, 1772], fill=(250, 240, 200, 255))
        return im

    # ───────── từng cảnh ─────────
    def villagers_dance(self, im, t, xs, g, fh, mode):
        for i, x in enumerate(xs):
            fn = [headbop, shoulder, footwork][(mode + i) % 3]
            self.fig(im, self.v[i % 3], fn(t + i * 0.12, x, g, fh), t, "smile", fh=fh, face=1)

    def sc01(self, t, lo):                                                  # 0 đến 4: mở màn drill
        im = self.bg("court").copy()
        self.villagers_dance(im, t, (200, 400, 600), 1500, 520, 1)
        x = 840
        if lo < 0.45:
            pass
        else:
            fall = min(1.0, (lo - 0.45) / 0.45)
            y = G - (1 - fall) ** 2 * 1700 if lo < 0.9 else G
            if lo < 0.9:
                P = freeze(x, y, 700)
                P["aL1"], P["aR1"] = 150, 150
                self.fig(im, self.b, P, t, "wow", ("shades",), fh=700, face=-1)
            elif lo < 1.7:
                P = headbop(t, x, G, 700)
                P["aR1"], P["aR2"] = 160, 30
                self.fig(im, self.b, P, t, "hype", ("shades",), fh=700, face=-1)       # kéo mũ / chỉnh kính
            else:
                self.fig(im, self.b, footwork(t, x, G, 700), t, "joy", ("shades",), fh=700, face=-1)
            if 0.9 <= lo < 1.6:
                dust(im, x, G + 8, ss((lo - 0.9) / 0.7))
            if 0.9 <= lo < 1.15:
                ink_burst(im, x, G - 160, (lo - 0.9) / 0.25)
        return im

    def sc02(self, t, lo):                                                  # 4 đến 9: quê hương từ trên cao
        if lo < 3.4:
            im = Image.new("RGBA", (W, H))
            big = self.bg("aerial")
            off = int(1100 + lo * 170)
            im.paste(big.crop((0, off, W, off + H)), (0, 0))
            d = ImageDraw.Draw(im, "RGBA")
            ry = 1000 - (off - 1100 - 0) % 1  # mái nhà đứng yên trong khung (flycam giữ mục tiêu)
            d.rectangle([420, 880, 700, 1100], fill=(230, 120, 70, 255), outline=INK, width=6)
            d.line([(420, 990), (700, 990)], fill=(120, 50, 30, 255), width=6)
            self.fig(im, self.b, headbop(t, 560, 940, 300), t, "hype", ("megaphone",), fh=300, face=1)
            for n in range(7):                                              # nốt nhạc biến thành graffiti
                a = (lo * 0.55 + n / 7) % 1.0
                nx = 600 + math.sin(n * 2.1) * 260 * a
                ny = 860 - a * 700
                col = [(255, 90, 160), (110, 220, 255), (255, 224, 80), (170, 255, 120), (255, 150, 60), (190, 140, 255), (255, 255, 255)][n]
                if a < 0.45:
                    note(d, nx, ny, 26 + a * 20, col + (240,))
                else:
                    k_ = (a - 0.45) / 0.55
                    r = 30 + 50 * k_
                    kind = n % 3
                    if kind == 0:
                        d.polygon([(nx + math.cos(rad_) * r * (1 if i % 2 == 0 else 0.45), ny + math.sin(rad_) * r * (1 if i % 2 == 0 else 0.45))
                                   for i, rad_ in enumerate([j * math.pi / 5 for j in range(10)])], fill=col + (int(230 * (1 - k_)),), outline=INK)
                    elif kind == 1:
                        d.line([(nx - r, ny + r * 0.4), (nx + r, ny - r * 0.4)], fill=col + (int(230 * (1 - k_)),), width=14)
                        d.polygon([(nx + r, ny - r * 0.4), (nx + r - 30, ny - r * 0.4 - 14), (nx + r - 30, ny - r * 0.4 + 24)], fill=col + (int(230 * (1 - k_)),))
                    else:
                        d.ellipse([nx - r, ny - r * 0.7, nx + r, ny + r * 0.7], outline=col + (int(230 * (1 - k_)),), width=10)
            return im
        im = self.bg("street").copy()                                       # nhảy từ mái nhà xuống đường làng
        k = ss((lo - 3.4) / 1.4)
        hx = 130 + 470 * k
        hy = 1010 + (G - 1010) * (k ** 1.6) - math.sin(k * math.pi) * 380
        d = ImageDraw.Draw(im, "RGBA")
        if k < 1.0:
            P = run_arms(t, hx, hy, 640, 3)
            P["aL1"], P["aR1"] = 150, 150
            self.fig(im, self.b, P, t, "wow", ("megaphone",), fh=640, face=1)
        else:
            self.fig(im, self.b, headbop(t, hx, G, 640), t, "joy", ("megaphone",), fh=640, face=1)
            if lo < 5.4:
                dust(im, hx, G + 6, ss((lo - 4.8) / 0.6))
        return im

    def sc03(self, t, lo):                                                  # 9 đến 14: hai cô trò chuyện
        im = self.bg("stall").copy()
        talk = math.sin(t * 5)
        Pg = headbop(t * 1.6, 840, 1500, 560)
        self.fig(im, self.g, Pg, t, "smile", ("shades",) if lo > 3 else (), fh=560, face=-1)           # nữ ló sau lưng, gật liên tục
        for i, x in enumerate((250, 620)):
            P = base(x, 1500, 640, torso=3 * talk, head=8 * math.sin(t * 5 + i * 2), aL1=40 + 24 * talk * (1 if i == 0 else -1), aL2=90,
                     aR1=30 - 18 * talk, aR2=60, lL1=4, lR1=-4)
            self.fig(im, self.v[i], P, t, "smile", fh=640, face=1 if i == 0 else -1)
        if lo > 2.2:
            sxv = math.cos(max(0, lo - 2.2) * 8) if lo < 2.9 else 1
            Pb = shoulder(t, 140, 1580, 700)
            if lo > 2.9:
                Pb["aR1"], Pb["aR2"] = 92, 88
            self.fig(im, self.b, Pb, t, "hype", fh=700, sx=sxv, face=1)
        if lo > 2.9:
            Pg2 = dict(Pg)
            Pg2["aL1"], Pg2["aL2"] = 85, 80
            self.fig(im, self.g, Pg2, t, "hype", fh=560, face=-1)
        return im

    def sc04(self, t, lo):                                                  # 14 đến 18: drill dance battle
        im = self.bg("factory").copy()
        self.villagers_dance(im, t, (330, 540, 750), 1440, 430, 0)
        seq = [headbop, shoulder, footwork]
        if t < 16.53:
            fn = seq[min(2, int(lo / 0.85))]
            self.fig(im, self.b, fn(t, 200, 1620, 760), t, "hype", fh=760, face=1)
            self.fig(im, self.g, fn(t + 0.25, 880, 1620, 760), t, "hype", fh=760, face=-1)
        else:
            self.fig(im, self.b, freeze(200, 1620, 760, 1), t, "joy", ("shades",), fh=760, face=1)
            self.fig(im, self.g, freeze(880, 1620, 760, -1), t, "joy", ("shades",), fh=760, face=-1)
            if t - 16.53 < 0.9:
                graffiti(im, "DROP!", 540, 330, 190, (255, 70, 90, 255), -6, ss((t - 16.53) / 0.2))
        return im

    def sc05(self, t, lo):                                                  # 18 đến 23: hồn quê giữa cánh đồng
        im = self.bg("field").copy()
        d = ImageDraw.Draw(im, "RGBA")
        if lo < 3.4:
            x = -200 + (lo / 3.4) * 1500
            P = run_arms(t, x, 1500, 640, 6.5)
            P["aL1"], P["aR1"] = 105, 105
            self.fig(im, self.g, P, t, "joy", fh=640, face=1)
        if lo > 1.8:
            P = footwork(t, 800 if lo < 3.4 else 600, 1560, 640)
            self.fig(im, self.b, P, t, "hype", ("nonla",), fh=640, face=-1)
        if lo >= 3.4:
            self.fig(im, self.g, freeze(300, 1560, 640, 1), t, "joy", fh=640, face=1)
            self.fig(im, self.b, freeze(600, 1560, 640, -1), t, "joy", ("nonla",), fh=640, face=-1)
        pulse = math.sin(t * BPM / 60 * 2 * math.pi) * 8
        for n in range(24):                                                  # lúa tiền cảnh lay theo nhịp
            bx = n * 48 + 10
            sw = math.sin(t * 3 + n * 0.7) * 16 + pulse
            d.line([(bx, H + 10), (bx + sw * 0.5, H - 200), (bx + sw * 1.8, H - 330)], fill=(232, 188, 60, 255), width=7)
            for m in range(5):
                d.ellipse([bx + sw * 1.6 - 7, H - 330 + m * 20 - 7, bx + sw * 1.6 + 7, H - 330 + m * 20 + 7], fill=(250, 214, 90, 255))
        return im

    def sc06(self, t, lo):                                                  # 23 đến 28: màu vàng quê hương
        im = Image.new("RGBA", (W, H))
        off = int(300 + lo * 330)
        im.paste(self.bg("aerialfield").crop((0, off, W, off + H)), (0, 0))
        d = ImageDraw.Draw(im, "RGBA")
        ly = 900 + math.sin(lo * 2.2) * 40
        leaf = [(120, ly + 30), (360, ly - 60), (640, ly - 70), (960, ly + 10), (700, ly + 90), (380, ly + 100)]
        d.polygon(leaf, fill=(104, 190, 70, 255), outline=INK)
        d.line([(160, ly + 30), (940, ly + 8)], fill=(60, 130, 46, 255), width=8)
        P = base(540, ly + 40, 420, torso=86, head=-12, aL1=100, aL2=130, aR1=92, aR2=60, lL1=82, lL2=96, lR1=72, lR2=90, hy=ly - 14)
        self.fig(im, self.b, P, t, "joy", ("shades",), fh=420, face=1)
        for n, col in enumerate(((255, 255, 255, 220), (255, 224, 90, 220), (110, 220, 255, 220))):  # sóng âm theo nhạc thật
            pts = []
            for x in range(0, W, 12):
                e = self.E(t - (x / W) * 0.6)
                pts.append((x, 440 + n * 70 + math.sin(x * 0.05 + t * 8 + n) * (30 + 190 * e)))
            d.line(pts, fill=col, width=9, joint="curve")
        if 0 <= t - 25.7 < 0.9:                                             # biến thành nét graffiti, chuyển cảnh cực nhanh
            k = (t - 25.7) / 0.9
            for n, col in enumerate(((255, 80, 140), (80, 220, 255), (255, 214, 60), (120, 255, 140), (255, 140, 40), (190, 140, 255))):
                y0 = 250 + n * 260
                pts = [(x, y0 + math.sin(x * 0.012 + n) * 120 * (1 - k)) for x in range(-40, int(W * min(1.0, k * 2.2)), 16)]
                if len(pts) > 1:
                    d.line(pts, fill=col + (int(255 * (1 - k * 0.5)),), width=34, joint="curve")
        return im

    def sc07(self, t, lo):                                                  # 28 đến 33: sản vật quê nhà
        im = self.bg("shop").copy()
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([380, 1010, 700, 1290], fill=(250, 250, 252, 255), outline=INK, width=7)
        d.rectangle([400, 1060, 680, 1240], fill=(214, 60, 60, 255))
        d.text((540, 1150), "BÚN TƯƠI SẤY", font=_font(52), fill=WHITE, anchor="mm")
        d.rectangle([0, 1290, W, 1330], fill=(126, 84, 56, 255))
        if lo < 2.4:
            P = shoulder(t, 170, 1580, 780)
            P["aR1"], P["aR2"] = 76, 66
            self.fig(im, self.b, P, t, "wow", ("magnifier",), fh=780, face=1)
        else:
            k = ss((lo - 2.4) / 0.3)
            if lo < 2.8:
                ink_burst(im, 170, 1200, (lo - 2.4) / 0.4)
            sw = math.sin(t * 6) * 28
            P = base(820, 1290, 330, torso=-4, aL1=20, aL2=10, aR1=70 + sw, aR2=60 + sw * 0.5, head=6 * math.sin(t * 6))
            self.fig(im, self.b, P, t, "hype", fh=330 * k + 10, face=-1)
            graffiti(im, "SẢN VẬT", 540, 300, 190, (255, 210, 50, 255), -6, ss((lo - 1.2) / 0.3) if lo < 3.4 else 1)
            graffiti(im, "QUÊ NHÀ", 540, 520, 190, (255, 90, 140, 255), 5, ss((lo - 2.7) / 0.3))
        return im

    def sc08(self, t, lo):                                                  # 33 đến 37: lao động và sáng tạo
        im = self.bg("workshop").copy()
        b = self.beat(t)
        P = base(760, 1500, 700, torso=10, aL1=60, aL2=64, aR1=74, aR2=72, lL1=8, lR1=-8, head=4 * math.sin(t * 10))
        pw = self.fig(im, self.worker, P, t, "neutral", ("drill",), fh=700, face=-1)
        if b < 0.5:
            sparks(im, pw["hR"][0] - 90, pw["hR"][1], t)
        Q = headbop(t * 2, 250, 1580, 640)
        Q["aR1"], Q["aR2"] = 74, 84
        pq = self.fig(im, self.b, Q, t, "hype", ("goggles", "drill"), fh=640, face=1)
        if b < 0.5:
            sparks(im, pq["hR"][0] + 90, pq["hR"][1], t, (120, 230, 255))
        return im

    def sc09(self, t, lo):                                                  # 37 đến 42: nụ cười quê hương
        im = self.bg("stage").copy()
        d = ImageDraw.Draw(im, "RGBA")
        k = ss((lo - 0.3) / 0.9)
        gx = 1180 - 520 * k
        P = shoulder(t, gx, 1560, 700)
        P["aR1"], P["aR2"] = 150, 120
        self.fig(im, self.g, P, t, "hype", ("mic",), fh=700, face=-1)
        for n in range(7):                                                  # đám đông tí hon cổ vũ
            Pn = headbop(t + n * 0.17, 90 + n * 150, 1800, 280)
            Pn["aL1"], Pn["aR1"] = 150 + 10 * math.sin(t * 9 + n), 150 - 10 * math.sin(t * 9 + n)
            Pn["aL2"], Pn["aR2"] = 170, 170
            self.fig(im, self.b if n % 2 == 0 else self.v[n % 3], Pn, t, "joy", fh=280, face=1)
        Pv = headbop(t, 230, 1540, 600)
        self.fig(im, self.v[0], Pv, t, "smile", fh=600, face=1)
        return im

    def sc10(self, t, lo):                                                  # 42 đến 47: cú chuyển bất ngờ, ô tô
        im = self.bg("road").copy()
        d = ImageDraw.Draw(im, "RGBA")
        bounce = 0
        if lo > 2.6:
            bounce = abs(math.sin(t * BPM / 60 * math.pi)) * 16
        cx, cy = 330, 1560 - bounce
        spd = 0 if lo < 2.6 else 1
        # thân xe đỏ
        body = [(cx, cy - 160), (cx + 120, cy - 330), (cx + 480, cy - 360), (cx + 640, cy - 190), (cx + 700, cy - 170), (cx + 700, cy - 40), (cx, cy - 40)]
        d.polygon(body, fill=(214, 40, 48, 255), outline=INK)
        d.polygon([(cx + 150, cy - 190), (cx + 220, cy - 310), (cx + 420, cy - 330), (cx + 520, cy - 190)], fill=(176, 226, 250, 255), outline=INK)
        if lo > 1.2:                                                         # cửa mở, nam bước vào ghế lái
            pass
        gx_, gy_ = cx + 330, cy - 170
        self.fig(im, self.g, headbop(t * 1.4, gx_, cy - 130, 330), t, "joy", ("shades",), fh=330, face=1)
        if lo < 1.2:
            bx = 120 + lo / 1.2 * 150
            self.fig(im, self.b, footwork(t, bx, 1580, 560) if lo < 1.0 else base(bx, 1580, 560), t, "hype", fh=560, face=1)
        else:
            self.fig(im, self.b, headbop(t * 1.4, cx + 250, cy - 130, 330), t, "joy", ("shades",), fh=330, face=1)
        d.polygon([(cx + 140, cy - 190), (cx + 230, cy - 320), (cx + 330, cy - 330), (cx + 330, cy - 190)], fill=(176, 226, 250, 60))
        door_open = ss((lo - 1.0) / 0.4) if lo < 1.8 else max(0.0, 1 - ss((lo - 1.8) / 0.4))
        d.polygon([(cx + 330, cy - 190), (cx + 330, cy - 40), (cx + 330 + 180 * door_open, cy - 70), (cx + 330 + 180 * door_open, cy - 220)], fill=(190, 30, 40, 255), outline=INK)
        for wx in (cx + 150, cx + 540):                                      # bánh xe quay mạnh
            d.ellipse([wx - 80, cy - 120, wx + 80, cy + 40], fill=(30, 30, 36, 255), outline=WHITE, width=3)
            rot = t * (22 if spd else 0) + wx
            for a in range(0, 360, 60):
                r = math.radians(a) + rot
                d.line([(wx, cy - 40), (wx + math.cos(r) * 64, cy - 40 + math.sin(r) * 64)], fill=(220, 220, 230, 255), width=5)
        if spd:
            for n in range(9):
                yy = 1250 + n * 55
                d.line([(1000 - (t * 900 + n * 120) % 700, yy), (1060 - (t * 900 + n * 120) % 700, yy)], fill=(255, 255, 255, 140), width=6)
            for n in range(5):
                a = (t * 2 + n * 0.2) % 1.0
                d.ellipse([cx - 40 - a * 120, cy - 60 - a * 40, cx - 10 - a * 120, cy - 30 - a * 40], fill=(220, 220, 226, int(200 * (1 - a))))
        return im

    def sc11(self, t, lo):                                                  # 47 đến 52: kết thúc đáng nhớ
        im = self.bg("workshop").copy()
        if t < 48.1:
            P = shoulder(t * 1.5, 280, 1580, 700)
            P["aR1"], P["aR2"] = 130 + 40 * math.sin(t * 12), 150
            self.fig(im, self.b, P, t, "hype", ("goggles", "drill"), fh=700, face=1)
            self.fig(im, self.worker, shoulder(t, 780, 1500, 700), t, "smile", ("drill",), fh=700, face=-1)
        else:
            self.fig(im, self.b, freeze(300, 1580, 700, 1), t, "joy", ("shades",), fh=700, face=1)
            self.fig(im, self.worker, freeze(780, 1500, 700, -1), t, "joy", fh=700, face=-1)
            if t - 48.1 < 1.2:
                graffiti(im, "FREEZE!", 540, 300, 200, (110, 230, 255, 255), -6, ss((t - 48.1) / 0.2))
        return im


SCENES = [(0.0, 4.0, "sc01", (1.0, 1.1, 0, 0)), (4.0, 9.0, "sc02", (1.0, 1.0, 0, 0)), (9.0, 14.0, "sc03", (1.0, 1.08, 0, 0)),
          (14.0, 18.0, "sc04", (1.0, 1.06, 0, 0)), (18.0, 23.0, "sc05", (1.1, 1.0, 40, 0)), (23.0, 28.0, "sc06", (1.0, 1.08, 0, 0)),
          (28.0, 33.0, "sc07", (1.0, 1.06, 0, 0)), (33.0, 37.0, "sc08", (1.0, 1.08, 0, 0)), (37.0, 42.0, "sc09", (1.0, 1.0, 0, 0)),
          (42.0, 47.0, "sc10", (1.08, 1.0, 0, 0)), (47.0, 52.16, "sc11", (1.0, 1.1, 0, 0))]


def cam_crop(frame, z, px, shake):
    if z == 1.0 and px == 0 and abs(shake) < 0.5:
        return frame
    cw, ch = W / z, H / z
    cx = W / 2 + px + shake
    cy = H * 0.58 if z > 1 else H / 2
    x0 = max(0, min(W - cw, cx - cw / 2))
    y0 = max(0, min(H - ch, cy - ch / 2))
    return frame.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), Image.BICUBIC)


def render(src_path, out_path):
    from moviepy import VideoClip, AudioFileClip
    tmp = tempfile.mkdtemp()
    wav = tmp + "/a.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src_path, "-vn", "-ac", "1", "-ar", "22050", wav], check=True)
    mv = MV(wav)
    dur = 52.15

    def make(t):
        for a, b, fn, (z0, z1, p0, p1) in SCENES:
            if a <= t < b or (fn == "sc11" and t >= a):
                lo = t - a
                break
        im = getattr(mv, fn)(t, lo)
        k = ss(lo / (b - a))
        z = z0 + (z1 - z0) * k
        px = p0 + (p1 - p0) * k
        shake = 0.0
        for dr in DROPS:
            if 0 <= t - dr < 0.4:
                shake = max(shake, 22 * (1 - (t - dr) / 0.4)) * math.sin(t * 90)
        if fn == "sc09" and lo > 3.6:
            kk = ss((lo - 3.6) / 0.6)
            z = 1.0 + 1.7 * kk
            px = -(540 - 230) * kk * 0 + (230 - 540) * kk
        im = cam_crop(im, z, px, shake)
        arr = np.array(im.convert("RGB")).astype(np.float32)
        for dr in DROPS:
            if 0 <= t - dr < 0.09:
                arr = np.clip(arr + 80 * (1 - (t - dr) / 0.09), 0, 255)
        if t < 0.4:
            arr *= ss(t / 0.4)
        if t > 50.4:
            arr *= ss((52.15 - t) / 1.7)
        return arr.astype("uint8")

    clip = VideoClip(make, duration=dur).with_fps(FPS)
    clip = clip.with_audio(AudioFileClip(wav))
    clip.write_videofile(out_path, fps=FPS, codec="libx264", audio_codec="aac", preset="veryfast", threads=4, logger=None)
    return {"video_path": out_path, "duration": dur}


if __name__ == "__main__":
    print(render(sys.argv[1], sys.argv[2]))
