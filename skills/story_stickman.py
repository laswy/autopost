"""
Phim ngắn người que (9:16) kể một câu chuyện liên tục, nét mực vẽ tay, bối cảnh phố đêm.

Chạy:
    python -m skills.story_stickman spec.json out.mp4
spec.json: {"audio": "song.wav", "duration": 30.0, "fade_out": 0.9,
            "sections": [{"start":0,"end":7,"kind":"ride"}, {"kind":"awning"}, {"kind":"stoop"}, {"kind":"fall"}, {"kind":"moon"}]}
Nhân vật nam: người que gầy, áo khoác cũ, đầu tròn, nét mực đen có viền sáng mảnh (đọc được trên nền tối).
Nhân vật nữ: bóng hồng nhạt, tóc và váy lay theo gió.
Bộ khớp: xương sống, hai tay (vai, khuỷu, cổ tay), hai chân (hông, gối, bàn chân); tư thế nội suy mềm theo thời gian.
"""

import json
import math
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920
FPS = 24
GY = 1330                       # mặt đường
FH = 640                        # chiều cao tham chiếu của người que
INK = (16, 16, 22, 255)
RIM = (205, 212, 226, 170)
COAT = (104, 98, 92, 255)
PINK = (255, 188, 206, 255)


def ss(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def mix(a, b, k):
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(len(a)))


def rad(d):
    return math.radians(d)


def ik(p, q, l1, l2, bend):
    """Hai đoạn nối từ p tới q, trả về khớp giữa. bend = +1 / -1 chọn phía gập."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    d = max(1e-3, min(math.hypot(dx, dy), l1 + l2 - 1e-3))
    a = math.atan2(dy, dx)
    c = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
    ang = math.acos(max(-1, min(1, c)))
    th = a + bend * ang
    return (p[0] + l1 * math.cos(th), p[1] + l1 * math.sin(th))


# ───────────────────────── bộ khớp người que ─────────────────────────

class Man:
    TH, SH, TO, UA, FA, HR = 0.235 * FH, 0.235 * FH, 0.30 * FH, 0.17 * FH, 0.165 * FH, 0.072 * FH

    def __init__(self):
        pass

    def pts(self, P):
        hx, hy = P["hx"], P["hy"]
        t = rad(P.get("torso", 0))
        u = (math.sin(t), -math.cos(t))
        hip = (hx, hy)
        sh = (hx + u[0] * self.TO * 0.93, hy + u[1] * self.TO * 0.93)
        neck = (hx + u[0] * self.TO, hy + u[1] * self.TO)
        th = t + rad(P.get("head", 0))
        head = (neck[0] + math.sin(th) * (self.HR + 8), neck[1] - math.cos(th) * (self.HR + 8))
        out = {"hip": hip, "sh": sh, "neck": neck, "head": head, "t": t}
        for side in ("L", "R"):
            a1, a2 = rad(P[f"a{side}1"]), rad(P[f"a{side}2"])
            e = (sh[0] + math.sin(a1) * self.UA, sh[1] + math.cos(a1) * self.UA)
            h_ = (e[0] + math.sin(a2) * self.FA, e[1] + math.cos(a2) * self.FA)
            out[f"e{side}"], out[f"h{side}"] = e, h_
            if f"fx{side}" in P:                                    # chân theo đích (đạp xe)
                foot = (P[f"fx{side}"], P[f"fy{side}"])
                knee = ik(hip, foot, self.TH, self.SH, P.get("kneebend", 1))
            else:
                l1, l2 = rad(P[f"l{side}1"]), rad(P[f"l{side}2"])
                knee = (hip[0] + math.sin(l1) * self.TH, hip[1] + math.cos(l1) * self.TH)
                foot = (knee[0] + math.sin(l2) * self.SH, knee[1] + math.cos(l2) * self.SH)
            out[f"k{side}"], out[f"f{side}"] = knee, foot
        if "hand_target" in P:                                      # tay bám ghi đông
            tx, ty = P["hand_target"]
            for side in ("L", "R"):
                out[f"h{side}"] = (tx, ty)
                out[f"e{side}"] = ik(sh, (tx, ty), self.UA, self.FA, -1)
        return out

    def draw(self, im, P, seed=0):
        pts = self.pts(P)
        rnd = np.random.RandomState(seed)

        def jit(p, a=1.6):
            return (p[0] + rnd.uniform(-a, a), p[1] + rnd.uniform(-a, a))
        d = ImageDraw.Draw(im, "RGBA")

        def stroke(seq, w):
            seq = [jit(p) for p in seq]
            d.line(seq, fill=RIM, width=w + 7, joint="curve")
            for p in seq:
                d.ellipse([p[0] - (w + 7) / 2, p[1] - (w + 7) / 2, p[0] + (w + 7) / 2, p[1] + (w + 7) / 2], fill=RIM)
            d.line(seq, fill=INK, width=w, joint="curve")
            for p in seq:
                d.ellipse([p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2], fill=INK)
        w = 9
        stroke([pts["hip"], pts["kL"], pts["fL"]], w)
        stroke([pts["sh"], pts["eL"], pts["hL"]], w - 1)
        # áo khoác cũ
        t = pts["t"]
        u = (math.sin(t), -math.cos(t))
        pr = (math.cos(t), math.sin(t))
        shd = (pts["sh"][0] + u[0] * 6, pts["sh"][1] + u[1] * 6)
        poly = [(shd[0] + pr[0] * 0.075 * FH, shd[1] + pr[1] * 0.075 * FH),
                (shd[0] - pr[0] * 0.075 * FH, shd[1] - pr[1] * 0.075 * FH),
                (pts["hip"][0] - pr[0] * 0.07 * FH - u[0] * 0.06 * FH, pts["hip"][1] - pr[1] * 0.07 * FH - u[1] * 0.06 * FH),
                (pts["hip"][0] + pr[0] * 0.07 * FH - u[0] * 0.06 * FH, pts["hip"][1] + pr[1] * 0.07 * FH - u[1] * 0.06 * FH)]
        poly = [jit(p, 1.2) for p in poly]
        d.polygon(poly, fill=COAT, outline=INK)
        d.line(poly + [poly[0]], fill=INK, width=5)
        mid_top = (pts["sh"][0], pts["sh"][1])
        mid_bot = (pts["hip"][0] - u[0] * 0.05 * FH, pts["hip"][1] - u[1] * 0.05 * FH)
        d.line([mid_top, mid_bot], fill=(60, 56, 54, 255), width=4)            # đường khuy áo
        for k in (0.35, 0.6):
            bx = mid_top[0] + (mid_bot[0] - mid_top[0]) * k
            by = mid_top[1] + (mid_bot[1] - mid_top[1]) * k
            d.ellipse([bx - 4, by - 4, bx + 4, by + 4], fill=(30, 28, 28, 255))
        d.line([(pts["sh"][0] - pr[0] * 28, pts["sh"][1] - pr[1] * 28), (pts["neck"][0], pts["neck"][1]),
                (pts["sh"][0] + pr[0] * 28, pts["sh"][1] + pr[1] * 28)], fill=(70, 66, 62, 255), width=6)  # cổ áo
        stroke([pts["hip"], pts["kR"], pts["fR"]], w)
        stroke([pts["sh"], pts["eR"], pts["hR"]], w - 1)
        # đầu
        hx, hy = pts["head"]
        r = self.HR
        d.ellipse([hx - r - 4, hy - r - 4, hx + r + 4, hy + r + 4], fill=RIM)
        d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=(232, 226, 218, 255), outline=INK, width=5)
        return pts


def woman(im, x, ground, t, glow=True, turn=0.0, pose="stand"):
    """Bóng người nữ màu hồng nhạt: đầu, tóc dài lay, váy loe lay, tay chân mảnh."""
    d = ImageDraw.Draw(im, "RGBA")
    H0 = FH * 0.95
    sway = math.sin(t * 1.7) * 6
    hipy = ground - 0.46 * H0
    sh = (x + sway * 0.3, hipy - 0.30 * H0)
    head = (x + sway * 0.4 + turn * 14, sh[1] - 0.11 * H0)
    # tóc
    hair = []
    for k in range(9):
        a = k / 8
        hair.append((head[0] - 22 + sway * 1.5 * a + turn * 12, head[1] + 8 + a * 0.40 * H0))
    d.polygon([(head[0] - 30, head[1] - 4), (head[0] + 30, head[1] - 4), (head[0] + 26 + sway * 3, head[1] + 0.35 * H0),
               (head[0] - 26 + sway * 3, head[1] + 0.38 * H0)], fill=(246, 150, 180, 255))
    # váy
    wave = math.sin(t * 2.2) * 9
    d.polygon([(sh[0] - 34, sh[1] + 20), (sh[0] + 34, sh[1] + 20),
               (x + 98 + wave, ground - 0.17 * H0), (x - 98 + wave * 0.6, ground - 0.17 * H0)], fill=PINK)
    d.line([(x - 98 + wave * 0.6, ground - 0.17 * H0), (x + 98 + wave, ground - 0.17 * H0)], fill=(255, 150, 180, 255), width=6)
    # chân, tay mảnh
    for sx in (-1, 1):
        d.line([(x + sx * 22, ground - 0.17 * H0), (x + sx * 24, ground)], fill=PINK, width=9)
        d.line([(sh[0] + sx * 32, sh[1] + 26), (sh[0] + sx * (40 + sway * 0.5), sh[1] + 0.20 * H0)], fill=PINK, width=8)
    hr = 0.062 * H0
    d.ellipse([head[0] - hr, head[1] - hr, head[0] + hr, head[1] + hr], fill=(255, 214, 224, 255))
    if glow:
        g = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).ellipse([x - 230, ground - 0.55 * H0 - 230, x + 230, ground - 0.55 * H0 + 230], fill=(255, 150, 190, 70))
        im.alpha_composite(g.filter(ImageFilter.GaussianBlur(40)))
    return head


# ───────────────────────── tư thế ─────────────────────────

def walk_pose(x, t, lean=4, amp=26, speed=5.0, hipy=None):
    ph = t * speed
    hy = (hipy if hipy else GY - 0.47 * FH + 2) + abs(math.sin(ph)) * -7
    l1 = amp * math.sin(ph)
    r1 = -amp * math.sin(ph)
    return {"hx": x, "hy": hy, "torso": lean, "head": 3,
            "aL1": -r1 * 0.9, "aL2": -r1 * 0.9 + 12, "aR1": -l1 * 0.9, "aR2": -l1 * 0.9 + 12,
            "lL1": l1, "lL2": l1 - 12 * (1 + math.cos(ph)), "lR1": r1, "lR2": r1 - 12 * (1 - math.cos(ph))}


def blend(A, B, k):
    out = {}
    for key in A:
        if key in B:
            out[key] = A[key] + (B[key] - A[key]) * k
    return out


STAND = {"hx": 0, "hy": GY - 0.47 * FH, "torso": 0, "head": 0,
         "aL1": 6, "aL2": 4, "aR1": 6, "aR2": 4, "lL1": 2, "lL2": 0, "lR1": -2, "lR2": 0}
LYING = {"hx": 0, "hy": GY - 26, "torso": 88, "head": 6,
         "aL1": 110, "aL2": 120, "aR1": 168, "aR2": 172, "lL1": 80, "lL2": 92, "lR1": 100, "lR2": 94}
SITUP = {"hx": 0, "hy": GY - 40, "torso": 28, "head": 10,
         "aL1": 40, "aL2": 64, "aR1": 60, "aR2": 40, "lL1": 78, "lL2": 6, "lR1": 66, "lR2": -8}
CROUCH = {"hx": 0, "hy": GY - 0.30 * FH, "torso": 36, "head": 8,
          "aL1": 30, "aL2": 50, "aR1": 44, "aR2": 60, "lL1": 60, "lL2": -6, "lR1": 52, "lR2": -4}


# ───────────────────────── thế giới ─────────────────────────

class World:
    def __init__(self, spec):
        self.spec = spec
        self.secs = spec["sections"]
        self.man = Man()
        self.cache = {}
        rnd = np.random.RandomState(3)
        self.rain = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(0.7, 1.3)) for _ in range(160)]
        self.shops = [(-60 + i * 300, rnd.randint(0, 3)) for i in range(5)]

    def sec(self, t):
        for i, s in enumerate(self.secs):
            if s["start"] <= t < s["end"]:
                return i, s
        return len(self.secs) - 1, self.secs[-1]

    PAL = {  # trời trên, trời dưới, đường, ánh đèn
        "ride": ((44, 62, 90), (96, 112, 140), (30, 36, 52), (255, 196, 110)),
        "awning": ((46, 60, 84), (108, 122, 146), (34, 40, 56), (255, 200, 120)),
        "stoop": ((26, 36, 52), (62, 74, 92), (20, 24, 36), (230, 186, 110)),
        "fall": ((22, 28, 40), (52, 60, 76), (18, 22, 32), (220, 170, 100)),
        "moon": ((52, 66, 100), (150, 164, 190), (40, 46, 66), (246, 240, 214)),
    }

    def pal(self, t):
        i, s = self.sec(t)
        cur = self.PAL[s["kind"]]
        if i > 0:
            k = ss((t - s["start"]) / 1.0)
            prev = self.PAL[self.secs[i - 1]["kind"]]
            cur = tuple(tuple(int(v) for v in mix(prev[j], cur[j], k)) for j in range(4))
        return cur

    def sprite(self, key, make):
        if key not in self.cache:
            self.cache[key] = make()
        return self.cache[key]

    def glow(self, col, r, a):
        def mk():
            g = Image.new("RGBA", (r * 2, r * 2), (0, 0, 0, 0))
            ImageDraw.Draw(g).ellipse([r * .25, r * .25, r * 1.75, r * 1.75], fill=col + (a,))
            return g.filter(ImageFilter.GaussianBlur(r * 0.35))
        return self.sprite(("glow", col, r, a), mk)

    def bg(self, t):
        top, bot, road, lamp = self.pal(t)
        key = ("bg", top, bot, road)

        def mk():
            col = np.zeros((H, 1, 3), np.float32)
            for y in range(H):
                if y < GY:
                    col[y, 0] = mix(top, bot, (y / GY) ** 1.4)
                else:
                    col[y, 0] = mix(road, tuple(c * 0.55 for c in road), (y - GY) / (H - GY))
            return Image.fromarray(np.repeat(col, W, axis=1).astype("uint8")).convert("RGBA")
        return self.sprite(key, mk).copy(), lamp

    def street(self, im, t, lamp, scroll, shops_lit=True):
        d = ImageDraw.Draw(im, "RGBA")
        # nhà hai bên: cửa hàng sáng đèn, trong trống
        off = scroll * 0.35 % 300
        for i, (x, kind) in enumerate(self.shops):
            xx = x - off
            h = 520 + kind * 90
            d.rectangle([xx, GY - h, xx + 270, GY], fill=(24, 30, 44, 255))
            d.rectangle([xx + 22, GY - 300, xx + 248, GY - 40], fill=lamp + (120,) if shops_lit else (18, 22, 32, 255),
                        outline=(10, 12, 18, 255), width=5)
            d.line([(xx + 135, GY - 300), (xx + 135, GY - 40)], fill=(10, 12, 18, 255), width=4)
            d.rectangle([xx + 22, GY - 350, xx + 248, GY - 310], fill=(60, 36, 36, 255))
            for wy in (GY - h + 60, GY - h + 150):
                d.rectangle([xx + 40, wy, xx + 80, wy + 50], fill=lamp + (80,) if (i + wy) % 2 else (16, 20, 30, 255))
        # cột đèn + quầng sáng + phản chiếu mặt đường ướt
        sp = 560
        off2 = scroll * 0.7 % sp
        for k in range(-1, 3):
            x = k * sp - off2 + 190
            d.rectangle([x - 8, GY - 560, x + 8, GY], fill=(14, 16, 24, 255))
            d.line([(x, GY - 560), (x + 76, GY - 584)], fill=(14, 16, 24, 255), width=11)
            lx, ly = x + 80, GY - 580
            im.alpha_composite(self.glow(lamp, 300, 120), (int(lx - 300), int(ly - 300)))
            d.ellipse([lx - 20, ly - 20, lx + 20, ly + 20], fill=(255, 244, 214, 255))
            refl = self.glow(lamp, 200, 90)
            im.alpha_composite(refl.resize((400, 520)), (int(lx - 200), GY + 30))
            for rr in range(3):                                      # gợn nước
                yy = GY + 70 + rr * 55 + math.sin(t * 2 + k + rr) * 5
                d.line([(lx - 110 + rr * 20, yy), (lx + 110 - rr * 20, yy)], fill=lamp + (60,), width=4)

    def draw_cyclo(self, im, rx, base, rot, rider_pose=True):
        d = ImageDraw.Draw(im, "RGBA")
        col, rim = (24, 24, 30, 255), (200, 206, 220, 150)
        wr = 118
        for wx in (rx, rx + 360):
            wy = base - wr
            d.ellipse([wx - wr - 4, wy - wr - 4, wx + wr + 4, wy + wr + 4], outline=rim, width=14)
            d.ellipse([wx - wr, wy - wr, wx + wr, wy + wr], outline=col, width=8)
            for a in range(0, 360, 40):
                r = rad(a + rot)
                d.line([(wx, wy), (wx + math.cos(r) * wr, wy + math.sin(r) * wr)], fill=col, width=3)
        d.rounded_rectangle([rx + 200, base - 360, rx + 520, base - 190], 26, fill=(70, 42, 40, 255), outline=col, width=7)
        d.arc([rx + 176, base - 520, rx + 540, base - 190], 180, 360, fill=col, width=9)
        d.line([(rx + 176, base - 355), (rx + 176, base - 190)], fill=col, width=6)
        d.line([(rx, base - wr), (rx + 120, base - 270), (rx + 360, base - wr)], fill=col, width=9)      # khung
        d.line([(rx - 30, base - 330), (rx + 120, base - 270)], fill=col, width=8)
        d.line([(rx + 120, base - 270), (rx + 120, base - 410)], fill=col, width=8)                  # cổ lái
        d.line([(rx + 100, base - 410), (rx + 150, base - 420)], fill=col, width=9)

    def rain_layer(self, im, t, a=120, slant=0.28):
        d = ImageDraw.Draw(im, "RGBA")
        for x, y, v in self.rain:
            yy = (y + t * 1500 * v) % (H + 100) - 50
            xx = (x - yy * slant) % W
            d.line([(xx, yy), (xx - 10 * slant * 3, yy + 38)], fill=(210, 220, 240, a), width=2)

    def mist(self, im, t, a=70):
        def mk():
            g = Image.new("RGBA", (W + 600, 520), (0, 0, 0, 0))
            gd = ImageDraw.Draw(g)
            for k in range(9):
                gd.ellipse([k * 150, 80 + (k % 3) * 40, k * 150 + 520, 440 - (k % 2) * 60], fill=(224, 232, 246, 120))
            return g.filter(ImageFilter.GaussianBlur(60))
        m = self.sprite("mist", mk)
        off = int(t * 28) % 600
        layer = m.crop((off, 0, off + W, 520))
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * a / 120)))
        im.alpha_composite(layer, (0, GY - 520))

    # ───── các cảnh ─────
    def scene_ride(self, im, t, local, lamp, seed):
        scroll = local * 560 + 900
        self.street(im, t, lamp, scroll)
        rx = 330
        ph = local * 5.2
        d = ImageDraw.Draw(im, "RGBA")
        self.draw_cyclo(im, rx, GY, ph * 57, True)
        cx, cy, r = rx + 50, GY - 118 - 40, 46
        fL = (cx + math.cos(ph) * r, cy + math.sin(ph) * r)
        fR = (cx - math.cos(ph) * r, cy - math.sin(ph) * r)
        P = {"hx": rx - 6, "hy": GY - 118 - 262 + abs(math.sin(ph)) * 3, "torso": 24, "head": 18,
             "aL1": 0, "aL2": 0, "aR1": 0, "aR2": 0, "fxL": fL[0], "fyL": fL[1], "fxR": fR[0], "fyR": fR[1], "kneebend": 1,
             "hand_target": (rx + 124, GY - 118 - 330)}
        pts = self.man.draw(im, P, seed)
        # mồ hôi
        for n in range(4):
            k = (local * 1.3 + n * 0.25) % 1.0
            hx, hy = pts["head"]
            px, py = hx + 36 + n * 6 + k * 14, hy + 12 + k * 130
            d.ellipse([px - 6, py - 9, px + 6, py + 9], fill=(190, 222, 255, int(220 * (1 - k))))

    def scene_awning(self, im, t, local, lamp, seed):
        self.street(im, t, lamp, 40)
        d = ImageDraw.Draw(im, "RGBA")
        # mái hiên sọc
        for i in range(10):
            col = (150, 60, 56, 255) if i % 2 == 0 else (214, 204, 190, 255)
            d.polygon([(40 + i * 52, GY - 640), (92 + i * 52, GY - 640), (112 + i * 52, GY - 590), (60 + i * 52, GY - 590)], fill=col)
        d.line([(60, GY - 590), (60, GY)], fill=(14, 16, 24, 255), width=10)
        d.line([(560, GY - 590), (560, GY)], fill=(14, 16, 24, 255), width=10)
        # cột đèn xa, bóng hồng
        self.mist(im, t, 110)
        woman(im, 880, GY, t, True, turn=ss((local - 3.0) / 2.0))
        # anh xoa tay vì lạnh, rồi nhìn về phía cô
        rub = math.sin(local * 9) * 6
        look = ss((local - 2.5) / 1.5)
        P = dict(STAND)
        P.update({"hx": 300, "torso": 4 + 6 * look, "head": -6 + 20 * look,
                  "aL1": 60 + rub, "aL2": 118 + rub, "aR1": 54 - rub, "aR2": 110 - rub, "lL1": 3, "lR1": -3})
        pts = self.man.draw(im, P, seed)
        for n in range(5):                                           # hơi thở lạnh
            k = (local * 0.7 + n * 0.2) % 1.0
            hx, hy = pts["head"]
            r = 8 + k * 22
            d.ellipse([hx + 40 + k * 70 - r, hy + 18 - k * 60 - r, hx + 40 + k * 70 + r, hy + 18 - k * 60 + r], fill=(240, 246, 255, int(160 * (1 - k))))
        self.draw_cyclo(im, 640, GY, 0)

    def scene_stoop(self, im, t, local, lamp, seed):
        self.street(im, t, lamp, 0, shops_lit=False)
        d = ImageDraw.Draw(im, "RGBA")
        for k in range(10):                                          # con đường dài, tối, đường chạy
            a = 40 + k * 8
            d.polygon([(W * 0.52 - 30 - k * 40, GY - 20 - k * 10), (W * 0.52 + 30 + k * 40, GY - 20 - k * 10),
                       (W * 0.52 + 36 + k * 44, GY - 14 - k * 10), (W * 0.52 - 36 - k * 44, GY - 14 - k * 10)], fill=(12, 14, 22, 70))
        for k in range(3):                                           # bậc thềm cũ
            d.rectangle([160 + k * 20, GY - 60 - k * 70, 600, GY - k * 70], fill=(54, 58, 66, 255), outline=(14, 16, 24, 255), width=5)
        seat_y = GY - 130
        P = dict(SITUP)
        P.update({"hx": 330, "hy": seat_y - 40, "torso": 38 + math.sin(local * 1.5) * 2, "head": 38,
                  "aL1": 100, "aL2": 160, "aR1": 96, "aR2": 150, "lL1": 70, "lL2": 6, "lR1": 62, "lR2": -2})
        self.man.draw(im, P, seed)
        # dấu hỏi lớn nhỏ rối thành vòng xoáy
        k = ss(local / 3.0)
        cx, cy = 420, GY - 760
        pts = []
        for a in range(0, int(900 * k), 12):
            r = 8 + a * 0.22
            pts.append((cx + math.cos(rad(a)) * r, cy + math.sin(rad(a)) * r * 0.8))
        if len(pts) > 2:
            d.line(pts, fill=(14, 14, 20, 230), width=5, joint="curve")
        for n, (qx, qy, sz) in enumerate(((230, GY - 880, 150), (620, GY - 980, 110), (700, GY - 760, 190), (160, GY - 700, 90))):
            f = __import__("skills.explainer_video", fromlist=["_font"])._font(sz)
            a = int(230 * (0.5 + 0.5 * math.sin(local * 1.8 + n)))
            d.text((qx + 3, qy + 3), "?", font=f, fill=(240, 240, 250, int(a * .4)), anchor="mm")
            d.text((qx, qy), "?", font=f, fill=(14, 14, 20, a), anchor="mm")

    def scene_fall(self, im, t, local, lamp, seed):
        scroll = local * 90
        self.street(im, t, lamp, scroll)
        d = ImageDraw.Draw(im, "RGBA")
        # ghế gỗ cũ trống phía sau
        cxh = 250 - scroll * 0.2
        d.rectangle([cxh, GY - 250, cxh + 120, GY - 235], fill=(92, 62, 40, 255), outline=(14, 14, 20, 255), width=4)
        d.rectangle([cxh, GY - 460, cxh + 14, GY - 235], fill=(92, 62, 40, 255), outline=(14, 14, 20, 255), width=4)
        d.rectangle([cxh + 106, GY - 250, cxh + 120, GY], fill=(92, 62, 40, 255), outline=(14, 14, 20, 255), width=4)
        d.rectangle([cxh, GY - 250, cxh + 14, GY], fill=(92, 62, 40, 255), outline=(14, 14, 20, 255), width=4)
        # ô bỏ quên bên vệ đường
        ux = 840 - scroll * 0.2
        d.arc([ux - 120, GY - 170, ux + 120, GY + 30], 180, 360, fill=(120, 40, 50, 255), width=40)
        d.line([(ux, GY - 70), (ux + 40, GY + 10)], fill=(20, 20, 26, 255), width=8)
        # chuỗi hành động: loạng choạng -> ngã -> vươn tay
        if local < 1.5:
            x = 330 + local * 100
            P = walk_pose(x, local, lean=10 + math.sin(local * 5) * 6, amp=16, speed=3.2)
            P["hx"] = x
        elif local < 2.3:
            k = ss((local - 1.5) / 0.8)
            A = walk_pose(330 + 1.5 * 100 + 30 * k, 1.5, lean=16, amp=12, speed=3.2)
            B = dict(LYING); B["hx"] = 560
            B["hy"] = GY - 24
            P = blend(A, B, k)
            if "hx" not in P:
                P["hx"] = 520
        else:
            k = ss((local - 2.3) / 1.2)
            P = dict(LYING); P["hx"] = 560 + 12 * k
            P["aR1"] = 150 + 20 * math.sin(local * 3) + 10 * k
            P["aR2"] = 160 + 12 * math.sin(local * 3.4)
        self.man.draw(im, P, seed)
        if 1.9 < local < 2.6:                                        # bắn nước
            for n in range(9):
                k = (local - 1.9) / 0.7
                d.ellipse([560 + math.cos(n) * 120 * k - 5, GY - 20 - math.sin(n * 1.7) ** 2 * 140 * k * (1 - k) - 5,
                           560 + math.cos(n) * 120 * k + 5, GY - 20 - math.sin(n * 1.7) ** 2 * 140 * k * (1 - k) + 5], fill=(200, 224, 255, 200))
        self.rain_layer(im, t, 130)

    def scene_moon(self, im, t, local, lamp, seed):
        self.street(im, t, lamp, 0)
        d = ImageDraw.Draw(im, "RGBA")
        mx, my = 700, 520
        im.alpha_composite(self.glow((220, 232, 255), 520, 120), (mx - 520, my - 520))
        d.ellipse([mx - 120, my - 120, mx + 120, my + 120], fill=(250, 248, 236, 255))
        for cr, (ox, oy, rr) in enumerate(((-30, -20, 26), (36, 28, 18), (-10, 46, 14))):
            d.ellipse([mx + ox - rr, my + oy - rr, mx + ox + rr, my + oy + rr], fill=(228, 226, 214, 255))
        # vệt sáng bạc trên mặt đường
        for k in range(22):
            yy = GY + 30 + k * 22
            w_ = 40 + k * 18 + math.sin(t * 2 + k) * 6
            d.line([(mx - w_ / 2 + math.sin(t + k) * 10, yy), (mx + w_ / 2, yy)], fill=(236, 242, 255, 90 - k * 3), width=5)
        girl_head = woman(im, 860, GY, t, True, turn=ss((local - 3.4) / 1.0))
        # chuỗi: nằm -> ngồi dậy -> đứng -> phủi áo -> bước chậm
        if local < 1.2:
            P = dict(LYING); P["hx"] = 560
        elif local < 2.0:
            k = ss((local - 1.2) / 0.8)
            A = dict(LYING); A["hx"] = 560
            B = dict(SITUP); B["hx"] = 556
            P = blend(A, B, k)
        elif local < 2.9:
            k = ss((local - 2.0) / 0.9)
            A = dict(SITUP); A["hx"] = 556
            B = dict(STAND); B["hx"] = 520
            P = blend(A, B, k)
        elif local < 3.9:
            P = dict(STAND); P["hx"] = 520
            sw = math.sin((local - 2.9) * 10)
            P.update({"torso": 6, "head": 8, "aL1": 20 + sw * 18, "aL2": 40 + sw * 25, "aR1": 24 - sw * 18, "aR2": 46 - sw * 25})
        else:
            k = (local - 3.9)
            x = 520 + k * 110
            P = walk_pose(x, k, lean=4, amp=20, speed=3.6)
        self.man.draw(im, P, seed)
        # hai bóng kéo dài trên mặt đường
        sx = P["hx"]
        d.polygon([(sx - 8, GY + 6), (sx + 8, GY + 6), (sx - 290, GY + 60), (sx - 330, GY + 60)], fill=(8, 10, 18, 110))
        d.polygon([(860 - 8, GY + 6), (860 + 8, GY + 6), (860 - 330, GY + 70), (860 - 372, GY + 70)], fill=(120, 50, 80, 80))


KINDS = {"ride": "scene_ride", "awning": "scene_awning", "stoop": "scene_stoop", "fall": "scene_fall", "moon": "scene_moon"}
CAM = {   # kind -> (zoom đầu, zoom cuối, lệch x đầu, x cuối)
    "ride": (1.12, 1.0, 120, 0), "awning": (1.0, 1.08, 0, 60), "stoop": (1.0, 1.22, 0, -40),
    "fall": (1.05, 1.02, 0, 0), "moon": (1.14, 1.0, 40, 0),
}


def render(spec, out_path):
    from moviepy import AudioFileClip, VideoClip
    from moviepy.audio.fx import AudioFadeOut
    w = World(spec)
    dur = spec.get("duration", 30.0)
    fade = spec.get("fade_out", 0.9)

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
        if s["kind"] == "fall" and 1.7 < local < 2.6:
            shake = math.sin(local * 60) * 10 * (1 - (local - 1.7) / 0.9)
        cw, ch = W / z, H / z
        cx = W / 2 + px + shake
        cy = H * 0.56 if z > 1 else H / 2
        box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
        box = (max(0, min(W - cw, box[0])), max(0, min(H - ch, box[1])))
        frame = base.crop((int(box[0]), int(box[1]), int(box[0] + cw), int(box[1] + ch))).resize((W, H), Image.BICUBIC)
        a = 1.0
        if t < 0.6:
            a = ss(t / 0.6)
        if t > dur - fade:
            a = min(a, ss((dur - t) / fade))
        # vignette nhẹ
        arr = np.array(frame.convert("RGB")).astype(np.float32)
        arr *= a
        return arr.astype("uint8")

    clip = VideoClip(make, duration=dur).with_fps(FPS)
    au = AudioFileClip(spec["audio"]).subclipped(0, dur).with_effects([AudioFadeOut(fade)])
    clip.with_audio(au).write_videofile(out_path, fps=FPS, codec="libx264", audio_codec="aac", preset="veryfast", threads=4, logger=None)
    return {"video_path": out_path, "duration": dur}


if __name__ == "__main__":
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    print(render(spec, sys.argv[2]))
