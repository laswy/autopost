"""
Phim ngắn người que 9:16 "Cái Ô Con Thỏ" (chương 22 truyện Hai Ca Một Mái Nhà).
Tám cảnh liền mạch trong phòng trọ: ngồi đối diện, kể hết, lộ bí mật, cãi nhau, con bé quay lại, bố bỏ đi, cái ô con thỏ.
Tái dùng lớp Char, ik, blend, World của skills/story_stickman.py, đăng ký thêm kind vào KINDS, PAL, CAM.

Chạy:  python -m skills.story_ou out.mp4
"""

import asyncio
import math
import subprocess
import sys
import tempfile
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from skills import story_stickman as sm
from skills.explainer_video import _font
from skills.story_stickman import (CAM, FPS, H, KINDS, W, Char, STYLE, World, blend, rad, ss, walk_pose)

PAL = World.PAL

FL = 1500                      # mặt sàn phòng trọ
LINE = (46, 34, 30, 255)
INK = (24, 20, 26, 255)

LINES = [      # (cảnh, lời dẫn ngôi thứ nhất của Hạnh)
    (0, "Mẹ dắt Bống đi chợ, để lại căn phòng cho vợ chồng tôi."),
    (1, "Tôi kể hết. Một trăm mười tám giây trong rạp."),
    (2, "Anh cũng có chuyện. Mười một triệu, vay của người thích anh."),
    (3, "Chúng tôi cãi nhau. Ai cũng có chỗ khác để ở."),
    (4, "Rồi cửa mở. Con bé quay lại lấy cái ô."),
    (5, "Nó nói: bố mẹ đừng cãi nữa. Con về với bà."),
    (6, "Anh cầm áo khoác ra cửa. Bậc thứ chín kêu cạch."),
    (7, "Chiều, con mở cái ô trong nhà, che cho mẹ trước."),
]
SECS = [{"start": i * 5.0, "end": (i + 1) * 5.0, "kind": f"ou{i}"} for i in range(8)]
TONES = [(255, 214, 160), (206, 218, 240), (216, 196, 220), (232, 150, 130), (186, 200, 224), (170, 178, 196), (150, 164, 200), (255, 190, 200)]
for i in range(8):
    PAL[f"ou{i}"] = ((200, 190, 180), (230, 220, 210), (120, 100, 90), (255, 214, 160))
CAM.update({"ou0": (1.0, 1.12, 0, 40), "ou1": (1.12, 1.04, 60, -40), "ou2": (1.0, 1.2, 0, 0), "ou3": (1.1, 1.18, 0, 0),
            "ou4": (1.0, 1.28, 0, 70), "ou5": (1.28, 1.34, 70, 60), "ou6": (1.0, 1.0, 0, 0), "ou7": (1.25, 1.0, 40, 0)})


def tint(im, col, a):
    ov = Image.new("RGBA", im.size, col + (int(a),))
    im.alpha_composite(ov)


class Room(World):
    def __init__(self, spec):
        super().__init__(spec)
        self.han = Char("woman", fh=600)
        self.han.st = dict(STYLE["woman"], coat=(128, 164, 150, 255), coat_d=(64, 92, 84, 255), scarf=(214, 130, 120, 255))
        self.tuan = Char("man", fh=620)
        self.bong = Char("woman", fh=330)
        self.bong.st = dict(STYLE["woman"], coat=(255, 178, 200, 255), scarf=(255, 255, 255, 255), coat_d=(190, 110, 140, 255))
        self.ba = Char("woman", fh=520)
        self.ba.st = dict(STYLE["woman"], coat=(118, 86, 62, 255), coat_d=(70, 50, 38, 255), scarf=(200, 190, 170, 255), hair=(190, 190, 196, 255))
        self.mote = np.random.RandomState(11)
        self.dust = [(self.mote.uniform(0, W), self.mote.uniform(300, 1500), self.mote.uniform(0.3, 1.0)) for _ in range(60)]

    # ───── phòng ─────
    def room(self, im, t, tone, fan=1.0, lit=1.0, paper=0.0):
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, 0, W, H], fill=(236, 226, 208, 255))
        for y in range(0, FL, 6):
            k = y / FL
            d.line([(0, y), (W, y)], fill=(int(238 - 30 * k), int(228 - 36 * k), int(208 - 40 * k), 255), width=6)
        for x in range(0, W, 120):
            d.line([(x, 0), (x, FL)], fill=(210, 198, 176, 70), width=2)
        # sàn gạch
        d.rectangle([0, FL, W, H], fill=(186, 160, 136, 255))
        for x in range(-200, W + 200, 220):
            d.line([(x, FL), (x + (x - W / 2) * 0.9, H)], fill=(150, 124, 102, 255), width=4)
        for y in (FL + 70, FL + 190, FL + 340):
            d.line([(0, y), (W, y)], fill=(150, 124, 102, 255), width=4)
        d.rectangle([0, FL - 14, W, FL], fill=(120, 96, 78, 255))
        # cửa sổ có nắng
        d.rectangle([700, 250, 1010, 820], fill=(176, 214, 238, 255), outline=INK, width=8)
        d.line([(855, 250), (855, 820)], fill=INK, width=6)
        d.line([(700, 530), (1010, 530)], fill=INK, width=6)
        for k in range(5):
            d.line([(720 + k * 60, 820), (720 + k * 60 - 40, 280)], fill=(255, 255, 255, 90), width=8)
        shaft = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shaft)
        sd.polygon([(700, 250), (1010, 250), (640, FL + 220), (180, FL + 220)], fill=tone + (int(60 * lit),))
        im.alpha_composite(shaft.filter(ImageFilter.GaussianBlur(26)))
        # tủ lạnh có tờ giấy kẻ ô
        d.rounded_rectangle([40, 430, 330, 1500], 18, fill=(246, 246, 250, 255), outline=INK, width=7)
        d.line([(40, 760), (330, 760)], fill=INK, width=5)
        d.rounded_rectangle([88, 560, 150, 640], 6, fill=(196, 202, 214, 255))
        pw = math.sin(t * 7) * 6 * paper
        sheet = [(140 + pw, 880), (270 + pw * 0.4, 880), (270 + pw * 0.6, 1050), (140 + pw, 1050)]
        d.polygon(sheet, fill=(255, 255, 242, 255), outline=INK)
        for gy in range(900, 1040, 22):
            d.line([(150 + pw, gy), (262 + pw * 0.5, gy)], fill=(160, 180, 210, 255), width=2)
        d.text((205 + pw * 0.5, 1030), "hết giấu", font=_font(20), fill=(60, 50, 50, 255), anchor="mm")
        # dây phơi + áo đồng phục
        d.line([(0, 200), (W, 160)], fill=INK, width=4)
        for cx, col in ((420, (130, 170, 210)), (560, (240, 240, 244)), (640, (130, 170, 210))):
            sw = math.sin(t * 1.6 + cx) * 6
            d.polygon([(cx - 55 + sw, 180), (cx + 55 + sw, 176), (cx + 62 + sw, 350), (cx - 62 + sw, 354)], fill=col + (255,), outline=INK)
        # quạt treo tường quay
        d.ellipse([410, 460, 490, 540], fill=(120, 124, 136, 255), outline=INK, width=5)
        for b in range(3):
            a = t * 9 * fan + b * 2.094
            d.polygon([(450, 500), (450 + math.cos(a) * 130 - math.sin(a) * 22, 500 + math.sin(a) * 130 + math.cos(a) * 22),
                       (450 + math.cos(a) * 130 + math.sin(a) * 22, 500 + math.sin(a) * 130 - math.cos(a) * 22)], fill=(150, 160, 176, 130), outline=INK)
        # giường + gối hoa lan
        d.rectangle([620, FL - 330, 1100, FL - 70], fill=(150, 112, 84, 255), outline=INK, width=6)
        d.rectangle([620, FL - 330, 1100, FL - 260], fill=(244, 236, 220, 255), outline=INK, width=4)
        d.rounded_rectangle([860, FL - 360, 1010, FL - 290], 26, fill=(120, 160, 200, 255), outline=INK, width=4)
        d.text((935, FL - 325), "hoa lan", font=_font(18), fill=(255, 255, 255, 255), anchor="mm")
        # chiếu + mâm nhựa tròn trống
        d.polygon([(230, FL + 40), (860, FL + 40), (900, FL + 330), (190, FL + 330)], fill=(214, 186, 120, 255), outline=INK)
        for k in range(14):
            d.line([(230 - k * 3 + k * 46, FL + 40), (190 + k * 50, FL + 330)], fill=(180, 150, 92, 255), width=3)
        d.ellipse([400, FL + 120, 680, FL + 230], fill=(220, 90, 76, 255), outline=INK, width=5)
        d.ellipse([430, FL + 134, 650, FL + 206], fill=(236, 120, 104, 255))
        # bụi nắng
        for x, y, v in self.dust:
            yy = (y + t * 22 * v) % 1300 + 250
            xx = x + math.sin(t * 0.8 + v * 9) * 18
            d.ellipse([xx - 3, yy - 3, xx + 3, yy + 3], fill=(255, 255, 240, int(120 * v * lit)))
        tint(im, tone, 40)

    # ───── tư thế ngồi co gối ─────
    def sit(self, x, face, tt=0.0, lean=0.0, hy_off=0):
        fh = 600
        hy = FL - 0.081 * fh - 6 + 40 + hy_off
        l1 = 130 * face
        return {"hx": x, "hy": hy, "torso": lean * face, "head": 4 * math.sin(tt), "aL1": 100 * face, "aL2": 150 * face,
                "aR1": 70 * face, "aR2": 140 * face, "lL1": l1, "lL2": 10 * face, "lR1": l1 - 12 * face, "lR2": 4 * face}

    def stand(self, x, face, tt=0.0, fh=620):
        return {"hx": x, "hy": FL - 0.47 * fh + 6, "torso": 2 * face, "head": 2, "aL1": 8 * face, "aL2": 4 * face,
                "aR1": 6 * face, "aR2": 4 * face, "lL1": 2, "lL2": 0, "lR1": -2, "lR2": 0}

    def bandage(self, im, pts):
        d = ImageDraw.Draw(im, "RGBA")
        x, y = pts["hR"]
        d.rounded_rectangle([x - 20, y - 18, x + 20, y + 18], 8, fill=(250, 250, 252, 255), outline=LINE, width=3)
        d.line([(x - 18, y - 4), (x + 18, y + 6)], fill=(190, 190, 200, 255), width=2)

    def umbrella(self, im, cx, cy, r, openv, ang=0):
        d = ImageDraw.Draw(im, "RGBA")
        if openv < 0.15:
            d.line([(cx, cy), (cx + math.sin(rad(ang)) * 150, cy - math.cos(rad(ang)) * 150)], fill=(250, 190, 140, 255), width=8)
            d.line([(cx, cy), (cx - 8, cy + 30)], fill=INK, width=8)
            return
        d.line([(cx, cy), (cx, cy - r * 1.05)], fill=(250, 190, 140, 255), width=8)
        rr = r * openv
        d.pieslice([cx - rr, cy - r * 1.05 - rr * 0.8, cx + rr, cy - r * 1.05 + rr * 0.8], 180, 360, fill=(255, 168, 196, 255), outline=INK, width=5)
        for k in range(1, 4):
            d.line([(cx, cy - r * 1.05 - rr * 0.8), (cx - rr + k * rr / 2, cy - r * 1.05)], fill=(220, 120, 150, 255), width=3)
        bx, by = cx, cy - r * 1.05 - rr * 0.35
        for sg in (-1, 1):
            d.ellipse([bx + sg * rr * 0.16 - rr * 0.07, by - rr * 0.46, bx + sg * rr * 0.16 + rr * 0.07, by - rr * 0.1], fill=(255, 255, 255, 255), outline=INK, width=3)
        d.ellipse([bx - rr * 0.22, by - rr * 0.2, bx + rr * 0.22, by + rr * 0.16], fill=(255, 255, 255, 255), outline=INK, width=3)
        d.ellipse([bx - rr * 0.09, by - rr * 0.07, bx - rr * 0.03, by + rr * 0.0], fill=INK)
        d.ellipse([bx + rr * 0.03, by - rr * 0.07, bx + rr * 0.09, by + rr * 0.0], fill=INK)

    def zig(self, im, x0, y0, dirx, t, n=5, col=(160, 40, 50, 230), s=1.0):
        d = ImageDraw.Draw(im, "RGBA")
        rnd = np.random.RandomState(int(t * 14) % 53)
        for i in range(n):
            ang = rnd.uniform(-0.5, 0.5)
            pts = [(x0, y0 + i * 18 - 40)]
            for j in range(1, 5):
                pts.append((pts[-1][0] + dirx * (40 + rnd.uniform(0, 26)) * s, pts[-1][1] + (rnd.uniform(-30, 30)) + ang * 40))
            d.line(pts, fill=col, width=6, joint="curve")

    # ───── các cảnh ─────
    def scene_ou0(self, im, t, local, lamp, seed):                               # sáng, bà dắt Bống ra
        self.room(im, t, TONES[0], 1.0, 1.0)
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([950, 700, 1090, FL], fill=(60, 44, 36, 255), outline=INK, width=6)       # khung cửa tối
        d.rectangle([1000, 760, 1090, FL], fill=(232, 224, 200, 255))
        px = 960 + 140 * ss((local - 2.0) / 2.5)
        self.umbrella(im, 330, FL - 70, 130, 0.0, 70)                                         # ô con thỏ đã gập, bỏ quên cạnh tủ
        h = self.han.draw(im, self.sit(720, -1, t, 6), seed, t=t, expr="tired", face=-1)
        k = self.tuan.draw(im, self.sit(300, 1, t, 4), seed + 1, t=t, expr="tired", face=1)
        self.bandage(im, k)
        if local < 4.6:
            wk = walk_pose(px, local * 0.9, lean=6, amp=18, speed=4.2)
            wk["hy"] = FL - 0.47 * 520 + 4 - abs(math.sin(local * 4)) * 5
            self.ba.draw(im, wk, seed + 2, t=t, expr="smile", face=1)
            bw = walk_pose(px - 120, local * 1.6 + 0.4, lean=4, amp=22, speed=7.0)
            bw["hy"] = FL - 0.47 * 330 + 4 - abs(math.sin(local * 9)) * 8
            self.bong.draw(im, bw, seed + 3, t=t, expr="smile", face=1)

    def scene_ou1(self, im, t, local, lamp, seed):                               # kể hết
        self.room(im, t, TONES[1], 0.7, 0.4)
        d = ImageDraw.Draw(im, "RGBA")
        sp = math.sin(t * 3.2)
        P = self.sit(740, -1, t, 8)
        P["aR1"], P["aR2"] = -70 + sp * 18, -120 + sp * 22
        P["aL1"], P["aL2"] = -40 - sp * 14, -80
        P["head"] = -8 + sp * 3
        h = self.han.draw(im, P, seed, t=t, expr="sad", face=-1)
        Q = self.sit(300, 1, t, 22)
        Q["head"] = 24
        Q["aL1"], Q["aL2"] = 40, 150
        Q["aR1"], Q["aR2"] = 30, 150
        k = self.tuan.draw(im, Q, seed + 1, t=t, expr="sad", face=1)
        self.bandage(im, k)
        # biểu tượng kể chuyện nổi lên từ tay Hạnh
        a0 = h["hR"]
        icons = ("cup", "note", "ticket", "hand")
        for n, ic in enumerate(icons):
            kk = (local - 0.3 - n * 0.9) / 1.2
            if kk < 0 or kk > 1.6:
                continue
            ix = a0[0] - 140 - n * 40 + math.sin(kk * 3 + n) * 20
            iy = a0[1] - 90 - kk * 280
            al = int(255 * (1 - max(0, kk - 1.0) / 0.6))
            if ic == "cup":
                d.rounded_rectangle([ix - 34, iy - 30, ix + 34, iy + 30], 10, fill=(255, 250, 240, al), outline=INK, width=4)
                d.arc([ix + 22, iy - 14, ix + 56, iy + 18], 270, 90, fill=INK, width=5)
            elif ic == "note":
                d.rectangle([ix - 34, iy - 44, ix + 34, iy + 44], fill=(255, 214, 80, al), outline=INK, width=4)
                d.text((ix, iy), "For H.", font=_font(22), fill=INK, anchor="mm")
            elif ic == "ticket":
                for off in (-14, 14):
                    d.rectangle([ix - 40 + off, iy - 26 + off, ix + 40 + off, iy + 26 + off], fill=(236, 90, 90, al), outline=INK, width=4)
            else:
                d.ellipse([ix - 30, iy - 24, ix + 30, iy + 24], fill=(250, 220, 200, al), outline=INK, width=4)
                d.ellipse([ix - 6, iy - 6, ix + 40, iy + 24], fill=(250, 220, 200, al), outline=INK, width=4)
        if local > 3.2:                                                       # bộ đếm 118
            n = int(118 * ss((local - 3.2) / 1.7))
            d.text((540, 700), str(n), font=_font(260), fill=(30, 30, 40, int(220 * ss((local - 3.2) / 0.4))), anchor="mm", stroke_width=8, stroke_fill=(255, 255, 255, 220))
            d.text((540, 860), "giây", font=_font(70), fill=(30, 30, 40, 220), anchor="mm")

    def scene_ou2(self, im, t, local, lamp, seed):                               # mười một triệu
        self.room(im, t, TONES[2], 1.0, 0.3)
        d = ImageDraw.Draw(im, "RGBA")
        up = ss((local - 0.3) / 1.0)
        P = self.stand(300, 1)
        S = self.sit(300, 1, t, 6)
        T = blend(S, P, up)
        T["hx"] = 300
        if up < 1:
            T["lL1"] = S["lL1"] + (P["lL1"] - S["lL1"]) * up
        k = self.tuan.draw(im, T, seed, t=t, expr="pain" if local > 1.2 else "sad", face=1)
        self.bandage(im, k)
        P2 = self.sit(760, -1, t, 6)
        up2 = ss((local - 1.6) / 1.0)
        H2 = blend(P2, self.stand(760, -1), up2)
        h = self.han.draw(im, H2, seed + 1, t=t, expr="surprised" if local > 2.2 else "sad", face=-1)
        if local > 1.0:                                                       # phong bì 11 triệu và bóng người đàn bà
            ex, ey = 540, 820 + math.sin(local * 2) * 10
            sc = ss((local - 1.0) / 0.5)
            d.rectangle([ex - 130 * sc, ey - 80 * sc, ex + 130 * sc, ey + 80 * sc], fill=(246, 232, 200, 255), outline=INK, width=6)
            d.line([(ex - 130 * sc, ey - 80 * sc), (ex, ey + 10 * sc), (ex + 130 * sc, ey - 80 * sc)], fill=INK, width=5)
            if sc > 0.9:
                d.text((ex, ey + 30), "11 triệu", font=_font(60), fill=(150, 30, 40, 255), anchor="mm")
        if local > 2.6:                                                       # chiếc ghế nhựa đỏ mờ hiện lên
            g = ss((local - 2.6) / 0.8)
            gx, gy = 130, 1440
            d.rectangle([gx, gy - 160, gx + 110, gy - 140], fill=(214, 70, 70, int(200 * g)), outline=INK, width=4)
            d.rectangle([gx, gy - 300, gx + 14, gy - 140], fill=(214, 70, 70, int(200 * g)), outline=INK, width=4)
            d.rectangle([gx + 96, gy - 140, gx + 110, gy], fill=(214, 70, 70, int(200 * g)))
            d.rectangle([gx, gy - 140, gx + 14, gy], fill=(214, 70, 70, int(200 * g)))

    def scene_ou3(self, im, t, local, lamp, seed):                               # cãi nhau
        self.room(im, t, TONES[3], 2.6, 0.2, paper=1.0)
        d = ImageDraw.Draw(im, "RGBA")
        sx = math.sin(t * 40) * 4
        w1 = math.sin(t * 9)
        w2 = math.sin(t * 9 + 2)
        Pt = self.stand(330 + sx, 1)
        Pt.update({"torso": 10, "head": 10 + w1 * 6, "aL1": 70 + w1 * 20, "aL2": 110, "aR1": 120 + w2 * 24, "aR2": 130 + w2 * 16})
        k = self.tuan.draw(im, Pt, seed, t=t, expr="angry", face=1)
        self.bandage(im, k)
        Ph = self.stand(760 - sx, -1)
        Ph.update({"torso": -10, "head": -10 + w2 * 6, "aL1": -70 - w2 * 20, "aL2": -110, "aR1": -120 - w1 * 24, "aR2": -130 - w1 * 16})
        h = self.han.draw(im, Ph, seed + 1, t=t, expr="angry", face=-1)
        self.zig(im, k["head"][0] + 90, k["head"][1] - 10, 1, t)
        self.zig(im, h["head"][0] - 90, h["head"][1] - 10, -1, t + 0.3, col=(40, 70, 150, 230))

    def scene_ou4(self, im, t, local, lamp, seed):                               # cửa mở, Bống đứng đó
        quiet = ss(local / 1.2)
        self.room(im, t, TONES[4], 0.2, 0.2)
        d = ImageDraw.Draw(im, "RGBA")
        tint(im, (20, 26, 44), 90 * quiet)
        d = ImageDraw.Draw(im, "RGBA")
        Pt = self.stand(300, 1)
        Pt.update({"torso": 4, "head": 8, "aL1": 20, "aL2": 40, "aR1": 24, "aR2": 40})
        k = self.tuan.draw(im, Pt, seed, t=t, expr="surprised", face=1)
        self.bandage(im, k)
        Ph = self.stand(700, -1)
        Ph.update({"torso": -4, "head": -10, "aL1": -26, "aL2": -50, "aR1": -20, "aR2": -44})
        self.han.draw(im, Ph, seed + 1, t=t, expr="surprised", face=-1)
        # Bống ở khung cửa phải, tay cầm kẹo bông gòn
        d.rectangle([900, 600, 1100, FL], fill=(60, 44, 36, 255), outline=INK, width=6)
        d.rectangle([930, 650, 1100, FL], fill=(240, 236, 216, 255))
        bx = 1010 - 40 * ss((local - 0.6) / 1.4)
        Pb = self.stand(bx, -1, fh=330)
        Pb["hy"] = FL - 0.47 * 330 + 4
        Pb.update({"torso": -2, "head": -6, "aL1": -18, "aL2": -30, "aR1": -50, "aR2": -150})
        b = self.bong.draw(im, Pb, seed + 2, t=t, expr="sad", face=-1)
        hx, hy = b["hR"]
        d.rounded_rectangle([hx - 6, hy - 70, hx + 6, hy], 4, fill=(250, 240, 230, 255))
        d.ellipse([hx - 40, hy - 130, hx + 40, hy - 60], fill=(255, 176, 208, 255), outline=INK, width=3)

    def scene_ou5(self, im, t, local, lamp, seed):                               # bố mẹ đừng cãi nữa
        self.room(im, t, TONES[5], 0.15, 0.1)
        d = ImageDraw.Draw(im, "RGBA")
        tint(im, (24, 28, 40), 110)
        d = ImageDraw.Draw(im, "RGBA")
        walk = ss((local - 0.4) / 1.6)
        bx = 800 - 330 * walk
        Pb = self.stand(bx, -1, fh=360)
        Pb["hy"] = FL - 0.47 * 360 + 6
        Pb.update({"torso": 10, "head": 26, "aL1": -10, "aL2": -20, "aR1": -12, "aR2": -22})
        if walk < 1:
            wk = walk_pose(bx, local * 1.6, lean=8, amp=14, speed=3.4)
            wk["hy"] = FL - 0.47 * 360 + 6 - abs(math.sin(local * 5)) * 4
            wk["head"] = 24
            Pb = wk
        self.umbrella(im, 330, FL - 70, 130, 0.0, 70) if walk < 0.9 else None
        self.bong.fh = 360
        self.bong.draw(im, Pb, seed, t=t, expr="sad", face=-1)
        self.bong.fh = 330
        if walk >= 0.9:                                                       # ôm ô vào ngực
            d.line([(bx - 20, FL - 190), (bx - 70, FL - 130)], fill=(255, 190, 150, 255), width=8)
        Pt = self.stand(300, 1)
        Pt.update({"torso": 18, "head": 24, "aL1": 40, "aL2": 70, "aR1": 20, "aR2": 40})
        k = self.tuan.draw(im, Pt, seed + 1, t=t, expr="pain", face=1)
        self.bandage(im, k)
        Ph = self.sit(850, -1, t, 10)
        self.han.draw(im, Ph, seed + 2, t=t, expr="sad", face=-1)

    def scene_ou6(self, im, t, local, lamp, seed):                               # cầu thang, bậc thứ chín
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, 0, W, H], fill=(52, 56, 70, 255))
        for y in range(0, H, 8):
            d.line([(0, y), (W, y)], fill=(int(50 + y * 0.015), int(54 + y * 0.012), int(70 + y * 0.01), 255), width=8)
        d.rectangle([120, 260, 360, 1100], fill=(220, 214, 190, 255), outline=INK, width=6)       # cửa phòng trọ sáng
        d.rectangle([150, 300, 330, 1070], fill=(250, 244, 220, 255))
        for k in range(14):                                                   # lan can sắt
            d.line([(700 + k * 26, 520), (700 + k * 26, 1220)], fill=(40, 60, 70, 255), width=8)
        d.line([(690, 520), (1090, 480)], fill=(40, 60, 70, 255), width=14)
        n_steps = 12
        prog = ss(local / 4.4)
        # bậc thang chéo xuống, tay vịn
        pts = []
        for i in range(n_steps + 1):
            x = 560 + (i * 64)
            y = 980 + i * 78
            pts.append((x, y))
        for i in range(n_steps):
            x0, y0 = pts[i]
            d.rectangle([x0 - 300, y0, x0 + 40, y0 + 22], fill=(150, 154, 166, 255), outline=INK, width=4)
            d.rectangle([x0 - 300, y0 + 22, x0 + 40, y0 + 78], fill=(110, 114, 126, 255), outline=INK, width=3)
        step = min(n_steps - 1, int(prog * 12))
        sx = pts[min(n_steps - 1, step)][0] - 120
        sy = pts[min(n_steps - 1, step)][1]
        fh = 520
        ph = local * 5
        P = walk_pose(sx, local, lean=14, amp=10, speed=4.0)
        P["hy"] = sy - 0.47 * fh + 4
        P["hx"] = sx
        tp = self.tuan.fh
        self.tuan.fh = fh
        k = self.tuan.draw(im, P, seed, t=t, expr="sad", face=1, vel=0.4)
        self.tuan.fh = tp
        if step == 8 and prog < 0.9:                                          # bậc thứ chín, bậc kêu
            for n in range(5):
                aa = n * 1.26
                d.line([(pts[8][0] - 120 + math.cos(aa) * 40, pts[8][1] - 10 + math.sin(aa) * 40), (pts[8][0] - 120 + math.cos(aa) * 100, pts[8][1] - 10 + math.sin(aa) * 100)], fill=(255, 220, 80, 255), width=7)
            d.text((pts[8][0] - 130, pts[8][1] - 140), "CẠCH!", font=_font(110), fill=(255, 220, 80, 255), anchor="mm", stroke_width=6, stroke_fill=INK)
        # Hạnh ôm Bống ở cửa
        Ph = self.stand(230, 1)
        Ph.update({"torso": 4, "head": 6, "aL1": 36, "aL2": 40, "aR1": 24, "aR2": 40})
        self.han.fh = 520
        self.han.draw(im, Ph, seed + 1, t=t, expr="sad", face=1)
        self.han.fh = 600
        tint(im, TONES[6], 30)

    def scene_ou7(self, im, t, local, lamp, seed):                               # cái ô con thỏ che cho mẹ
        self.room(im, t, TONES[7], 0.8, 1.3)
        d = ImageDraw.Draw(im, "RGBA")
        tint(im, (255, 190, 200), 40)
        d = ImageDraw.Draw(im, "RGBA")
        P = self.sit(560, -1, t, 8)
        P["head"] = 6
        h = self.han.draw(im, P, seed, t=t, expr="tired" if local < 2.4 else "smile", face=-1)
        Pb = self.sit(760, -1, t, 4)
        Pb["hy"] = FL - 0.081 * 330 - 6 + 20
        self.bong.draw(im, Pb, seed + 1, t=t, expr="smile", face=-1)
        o = ss((local - 1.0) / 1.2)
        self.umbrella(im, 660, 1130, 230, o, 0)
        im.alpha_composite(self.glow((255, 170, 200), 360, int(70 * o)), (660 - 360, 900 - 360))
        if local > 1.0:
            for n in range(5):
                a = (local * 0.4 + n * 0.2) % 1.0
                d.ellipse([480 + n * 90, 900 - a * 300, 492 + n * 90, 912 - a * 300], fill=(255, 220, 230, int(180 * (1 - a))))


for i in range(8):
    KINDS[f"ou{i}"] = f"scene_ou{i}"


# ───────────────────────── âm thanh ─────────────────────────

async def _tts(text, path):
    import os
    import ssl

    import edge_tts
    from edge_tts import communicate as _c
    ca = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
    if os.path.exists(ca):
        _c._SSL_CTX = ssl.create_default_context(cafile=ca)
    last = None
    for _ in range(5):
        try:
            await edge_tts.Communicate(text, "vi-VN-HoaiMyNeural", rate="+10%").save(path)
            return
        except Exception as e:  # noqa
            last = e
            await asyncio.sleep(2)
    raise last


def build_audio(tmp, dur):
    sr = 22050
    mix = np.zeros(int(sr * dur), np.float32)
    rnd = np.random.RandomState(2)
    n = rnd.randn(len(mix)).astype(np.float32)
    k = np.ones(400, np.float32) / 400
    fan = np.convolve(n, k, mode="same") * 0.55                           # tiếng quạt, brown noise
    mix += fan * (0.5 + 0.3 * np.sin(np.arange(len(mix)) / sr * 2 * math.pi * 1.5))
    t = np.arange(len(mix)) / sr
    chords = [(220, 261.6, 329.6), (196, 246.9, 293.7), (174.6, 220, 261.6), (196, 246.9, 293.7)]
    for i, ch in enumerate(chords):
        a, b = int(i * 10 * sr), int(min(dur, (i + 1) * 10) * sr)
        seg = np.zeros(b - a, np.float32)
        for f in ch:
            seg += np.sin(2 * math.pi * f * t[a:b]) * 0.05
        env = np.minimum(1, np.minimum(np.arange(b - a) / (sr * 2), (b - a - np.arange(b - a)) / (sr * 2)))
        mix[a:b] += seg * env
    for sec, text in LINES:                                               # giọng dẫn, mỗi cảnh một dòng
        p = f"{tmp}/l{sec}.mp3"
        asyncio.run(_tts(text, p))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, "-ac", "1", "-ar", str(sr), f"{tmp}/l{sec}.wav"], check=True)
        w = wave.open(f"{tmp}/l{sec}.wav")
        v = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        max_len = int(sr * 4.7)
        print('dòng', sec, round(len(v) / sr, 2))
        v = v[:max_len]
        a = int((sec * 5 + 0.35) * sr)
        mix[a:a + len(v)] += v * 0.9
    for tc in (30 + 4 * 5 / 5 * 0 + 2.0,):                                  # tiếng "cạch" ở bậc thứ chín
        a = int(tc * sr)
        mix[a:a + 2000] += np.sin(2 * math.pi * 900 * np.arange(2000) / sr) * np.exp(-np.arange(2000) / 300) * 0.5
    for tt in (5 + 3.2, 5 + 3.4, 15.0, 20.0):
        a = int(tt * sr)
        mix[a:a + 3000] += np.sin(2 * math.pi * 70 * np.arange(3000) / sr) * np.exp(-np.arange(3000) / 700) * 0.6
    mix /= max(1.0, float(np.abs(mix).max()) / 0.9)
    out = f"{tmp}/mix.wav"
    w = wave.open(out, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes((mix * 32767).astype(np.int16).tobytes())
    w.close()
    return out


def render(out_path):
    from moviepy import AudioFileClip, VideoClip
    from moviepy.audio.fx import AudioFadeOut
    dur = 40.0
    tmp = tempfile.mkdtemp()
    audio = build_audio(tmp, dur)
    w = Room({"sections": SECS})

    def make(t):
        i, s = w.sec(t)
        local = t - s["start"]
        base, lamp = w.bg(t)
        getattr(w, KINDS[s["kind"]])(base, t, local, lamp, int(t * 8))
        z0, z1, x0, x1 = CAM[s["kind"]]
        k = ss(local / (s["end"] - s["start"]))
        z = z0 + (z1 - z0) * k
        px = x0 + (x1 - x0) * k
        shake = 0.0
        if s["kind"] == "ou3":
            shake = math.sin(t * 55) * 9
        if s["kind"] == "ou4" and local < 0.5:
            shake = math.sin(t * 70) * 14 * (1 - local / 0.5)
        cw, ch = W / z, H / z
        cx = W / 2 + px + shake
        cy = H * 0.64 if z > 1 else H / 2
        x0_ = max(0, min(W - cw, cx - cw / 2))
        y0_ = max(0, min(H - ch, cy - ch / 2))
        frame = base.crop((int(x0_), int(y0_), int(x0_ + cw), int(y0_ + ch))).resize((W, H), Image.BICUBIC)
        a = 1.0
        if t < 0.6:
            a = ss(t / 0.6)
        if t > dur - 1.2:
            a = min(a, ss((dur - t) / 1.2))
        arr = np.array(frame.convert("RGB")).astype(np.float32) * a
        return arr.astype("uint8")

    clip = VideoClip(make, duration=dur).with_fps(FPS)
    au = AudioFileClip(audio).with_effects([AudioFadeOut(1.2)])
    clip.with_audio(au).write_videofile(out_path, fps=FPS, codec="libx264", audio_codec="aac", preset="veryfast", threads=4, logger=None)
    return {"video_path": out_path, "duration": dur}


if __name__ == "__main__":
    print(render(sys.argv[1]))
