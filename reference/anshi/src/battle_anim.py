# -*- coding: utf-8 -*-
"""3D 战役战术动画引擎：支持 B03（东京洛阳保卫战）、B05（嘉山大捷）、B06（灵宝西原大败）。

图层：below(地形/河/城墙/城楼) → 尸体 → 阴影/扬尘 → 活动士兵与帅旗 → 刀光/血花/箭雨/战火浓烟
      → 战术箭头 → above(地名/城名/标题/字幕)
坐标统一使用图像像素坐标（x 向右，y 向下）。所有随机量用固定种子，逐帧完全确定。
"""
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import tactical_map as tm
from landmarks import make_war_banner
from sprites import make_sprite

W, H = tm.W_PX, tm.H_PX
UNIT_H = 56


# ----------------------------------------------------------------------------- 工具
def clamp01(u):
    return max(0.0, min(1.0, u))


def smooth(u):
    u = clamp01(u)
    return u * u * (3 - 2 * u)


def ease_out(u):
    u = clamp01(u)
    return 1 - (1 - u) ** 3


def bump(u):
    return math.sin(math.pi * u) if 0.0 <= u <= 1.0 else 0.0


def path_pos(keys, t):
    """keys=[(t,x,y),...] 首段缓入、末段缓出、中段线性。"""
    if t <= keys[0][0]:
        return keys[0][1], keys[0][2]
    if t >= keys[-1][0]:
        return keys[-1][1], keys[-1][2]
    for i in range(len(keys) - 1):
        t0, x0, y0 = keys[i]
        t1, x1, y1 = keys[i + 1]
        if t0 <= t <= t1:
            u = (t - t0) / max(t1 - t0, 1e-6)
            if len(keys) == 2:
                u = smooth(u)
            elif i == 0:
                u = (u * u) * 0.5 + u * 0.5
            elif i == len(keys) - 2:
                u = 1 - (1 - u) * ((1 - u) * 0.5 + 0.5)
            return x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
    return keys[-1][1], keys[-1][2]


def pivot_canvas(img):
    """把精灵放到方形画布上，使其底边中点（脚底）位于画布中心，方便绕脚底旋转。"""
    w, h = img.size
    s = 2 * max(w, h) + 8
    c = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    c.paste(img, (s // 2 - w // 2, s // 2 - h), img)
    return c


def paste(dst, src, x, y):
    """带越界裁剪的 alpha_composite。"""
    x, y = int(round(x)), int(round(y))
    sx0, sy0 = max(0, -x), max(0, -y)
    x0, y0 = max(0, x), max(0, y)
    w = min(src.width - sx0, dst.width - x0)
    h = min(src.height - sy0, dst.height - y0)
    if w <= 0 or h <= 0:
        return
    dst.alpha_composite(src.crop((sx0, sy0, sx0 + w, sy0 + h)), dest=(x0, y0))


def tint(img, rgb, k):
    if k <= 0.01:
        return img
    a = np.asarray(img, dtype=np.float32)
    a[..., :3] = a[..., :3] * (1 - k) + np.array(rgb, np.float32) * k
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def darken(img, k):
    """尸体：压暗并去饱和。"""
    if k <= 0.01:
        return img
    a = np.asarray(img, dtype=np.float32)
    g = a[..., :3].mean(-1, keepdims=True)
    a[..., :3] = (a[..., :3] * (1 - 0.45 * k) + g * 0.45 * k) * (1 - 0.32 * k)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def with_alpha(img, al):
    if al >= 0.999:
        return img
    a = np.asarray(img).copy()
    a[..., 3] = (a[..., 3].astype(np.float32) * al).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def unit_sprite(fac, ut, flip):
    st = tm.FACTION_STYLE[fac]
    raw = make_sprite(ut, st["unit_c"], st["unit_a"], flip=flip, size=(150, 120))
    crop = tm._tight_rgba(raw, thresh=65)
    cw, ch = crop.size
    uw = max(22, int(round(cw * (UNIT_H / max(ch, 1)))))
    return crop.resize((uw, UNIT_H), Image.Resampling.LANCZOS)


def banner_sprite(name, fac, h_px):
    st = tm.FACTION_STYLE[fac]
    raw = make_war_banner(name, st["banner_bg"], st["banner_trim"], size=(100, 160))
    crop = tm._tight_rgba(raw, thresh=30)
    cw, ch = crop.size
    w_px = max(44, int(round(cw * (h_px / max(ch, 1)))))
    return crop.resize((w_px, h_px), Image.Resampling.LANCZOS)


def group_slots(x_up, y_up, count, uw, layout="horizontal"):
    """复刻 _place_unit_group 排布，返回图像坐标的脚底点。"""
    step = uw * (0.95 if layout == "column" else 0.90)
    x0 = -(count - 1) * step * 0.5
    out = []
    for i in range(count):
        cx, cy_up = x_up + x0 + i * step, y_up + (-4.0 if i % 2 else 4.0)
        out.append((cx, H - cy_up + UNIT_H * 0.5))
    return out


# ----------------------------------------------------------------------------- 角色
class Actor:
    def __init__(self, name, img, keys, *, kind="inf", face_left=False, turn_t=None,
                 die_t=None, fall_dir=1, slashes=(), fade=None, gait=1.0, phase=0.0, banner=False):
        self.name = name
        self.base = img
        self.cv = {False: pivot_canvas(img), True: pivot_canvas(img.transpose(Image.Transpose.FLIP_LEFT_RIGHT))}
        self.w, self.h = img.size
        self.keys = keys
        self.kind = kind
        self.face_left = face_left
        self.turn_t = turn_t
        self.die_t = die_t
        self.fall_dir = fall_dir         # +1 向画面左倒，-1 向右倒
        self.slashes = list(slashes)
        self.fade = fade
        self.gait = gait
        self.phase = phase
        self.banner = banner

    def pos(self, t):
        if self.die_t is not None and t > self.die_t:
            t = self.die_t
        return path_pos(self.keys, t)

    def speed(self, t):
        x1, y1 = self.pos(t - 0.04)
        x2, y2 = self.pos(t + 0.04)
        return math.hypot(x2 - x1, y2 - y1) / 0.08

    def facing_left(self, t):
        fl = self.face_left
        if self.turn_t is not None and t >= self.turn_t:
            fl = not fl
        return fl

    def dead(self, t):
        return self.die_t is not None and t >= self.die_t

    def render(self, t, overlay, shadow_draw):
        x, y = self.pos(t)
        al = 1.0
        if self.fade:
            al = 1.0 - smooth((t - self.fade[0]) / max(1e-4, self.fade[1] - self.fade[0]))
            if al <= 0.01:
                return
        mirrored = self.facing_left(t) != self.face_left
        cv = self.cv[mirrored]
        ang, dx, dy = 0.0, 0.0, 0.0
        flash, dark = 0.0, 0.0

        if self.dead(t):
            u = (t - self.die_t) / (0.42 if not self.banner else 0.75)
            a = ease_out(u)
            over = 0.08 * bump(clamp01((u - 0.7) / 0.3))
            ang = self.fall_dir * (86.0 if not self.banner else 80.0) * (a - over)
            dx = -self.fall_dir * 16.0 * a
            flash = max(0.0, 1.0 - (t - self.die_t) / 0.12) * 0.85
            dark = (0.28 if self.banner else 1.0) * smooth((t - self.die_t - 0.15) / 0.6)
        else:
            sp = self.speed(t)
            mv = min(1.0, sp / 140.0)
            if self.kind == "cav":
                f = 3.1 * self.gait
                dy -= 3.2 * mv * abs(math.sin(2 * math.pi * f * t + self.phase))
                ang += 2.6 * mv * math.sin(2 * math.pi * f * t + self.phase)
            elif not self.banner:
                f = 3.8 * self.gait
                dy -= 2.6 * mv * abs(math.sin(2 * math.pi * f * t + self.phase))
                ang += 3.5 * mv * math.sin(2 * math.pi * f * 0.5 * t + self.phase)
                dy -= 0.8 * math.sin(2 * math.pi * 0.9 * t + self.phase)
            else:
                ang += 2.2 * mv * math.sin(2 * math.pi * 1.7 * t + self.phase)
            fwd = -1.0 if self.facing_left(t) else 1.0
            for ts in self.slashes:
                b = bump((t - ts + 0.08) / 0.30)
                dx += fwd * 13.0 * b
                ang += -fwd * 9.0 * b

        img = cv
        if abs(ang) > 0.05:
            img = img.rotate(ang, resample=Image.Resampling.BICUBIC)
        if flash > 0:
            img = tint(img, (255, 236, 220), flash)
        if dark > 0:
            img = darken(img, dark)
        img = with_alpha(img, al)
        fx, fy = x + dx, y + dy

        if not self.dead(t):
            sw = self.w * (0.78 if not self.banner else 0.5)
            shadow_draw.ellipse([x + dx - sw / 2, y - 7, x + dx + sw / 2, y + 6], fill=(20, 17, 16, int(56 * al)))
        else:
            ln = self.h * 0.95
            cx = x + dx - self.fall_dir * ln * 0.45
            shadow_draw.ellipse([cx - ln / 2, y - 8, cx + ln / 2, y + 7], fill=(20, 17, 16, int(50 * al)))
        paste(overlay, img, fx - img.width / 2, fy - img.height / 2)


# ----------------------------------------------------------------------------- 特效
def draw_slash(layer, glow, cx, cy, u, face_left, R=60):
    """刀光：白色锥形弧，头宽尾细。u∈[0,1]。"""
    if not (0 <= u <= 1):
        return
    th0, th1 = math.radians(115), math.radians(245)
    head = th0 + (th1 - th0) * min(1.0, u * 1.7)
    tail = th0 + (th1 - th0) * max(0.0, u * 1.7 - 0.75)
    if head - tail < 0.02:
        return
    n = 18
    outer, inner = [], []
    for i in range(n + 1):
        th = tail + (head - tail) * i / n
        w = 3 + 17 * (i / n) ** 1.3
        ox, oy = math.cos(th) * R, math.sin(th) * R
        ix, iy = math.cos(th) * (R - w), math.sin(th) * (R - w)
        outer.append((cx + (ox if face_left else -ox), cy - oy))
        inner.append((cx + (ix if face_left else -ix), cy - iy))
    poly = outer + inner[::-1]
    al = int(245 * (1 - u) ** 0.6)
    ImageDraw.Draw(glow).polygon(poly, fill=(255, 214, 120, int(al * 0.9)))
    ImageDraw.Draw(layer).polygon(poly, fill=(255, 255, 250, al))


def draw_blood(layer, x, y, t_rel, seed, away=-1):
    """血花/受击火花粒子：away=-1 向左喷。"""
    if not (0 <= t_rel <= 0.48):
        return
    rng = np.random.default_rng(seed)
    d = ImageDraw.Draw(layer)
    if t_rel < 0.14:
        k = 1.0 - t_rel / 0.14
        r1 = 18 * (1.2 - 0.4 * k)
        a0 = int(230 * k)
        d.line([(x - r1, y), (x + r1, y)], fill=(255, 240, 185, a0), width=4)
        d.line([(x, y - r1), (x, y + r1)], fill=(255, 240, 185, a0), width=4)
        d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(255, 250, 220, a0))
    for _ in range(16):
        vx = away * rng.uniform(75, 275) + rng.uniform(-35, 35)
        vy = -rng.uniform(45, 255)
        col = (182, 24, 18) if rng.random() < 0.72 else (255, 198, 92)
        px, py = x + vx * t_rel, y + vy * t_rel + 520 * t_rel ** 2
        qx, qy = px - vx * 0.028, py - (vy + 1040 * t_rel) * 0.028
        a = int(235 * (1 - t_rel / 0.48))
        d.line([(qx, qy), (px, py)], fill=col + (a,), width=4)


def draw_dust(layer, actor, t):
    d = ImageDraw.Draw(layer)
    k0 = int((t - 0.65) / 0.09)
    for k in range(max(0, k0), int(t / 0.09) + 1):
        tk = k * 0.09
        if tk > t or actor.speed(tk) < 90 or actor.dead(tk):
            continue
        age = t - tk
        x, y = actor.pos(tk)
        back = 1 if actor.facing_left(tk) else -1
        r = 6 + 22 * age / 0.65
        a = int(78 * (1 - age / 0.65))
        jx = ((k * 37) % 11) - 5
        d.ellipse([x + back * 30 + jx - r, y - 6 - r * 0.7, x + back * 30 + jx + r, y - 6 + r * 0.5],
                  fill=(196, 172, 128, a))


def draw_volley(layer, src, dst, t_rel, seed, n=16, dur=0.58):
    if not (0 <= t_rel <= dur + 0.25):
        return
    rng = np.random.default_rng(seed)
    d = ImageDraw.Draw(layer)
    for _ in range(n):
        delay = rng.uniform(0, 0.24)
        u = (t_rel - delay) / dur
        if not (0 <= u <= 1):
            continue
        sx, sy = src[0] + rng.uniform(-75, 75), src[1] + rng.uniform(-22, 22)
        ex, ey = dst[0] + rng.uniform(-42, 42), dst[1] + rng.uniform(-16, 16)
        hgt = rng.uniform(70, 145)

        def p(v):
            return sx + (ex - sx) * v, sy + (ey - sy) * v - hgt * 4 * v * (1 - v)

        tail, a, b = p(max(0, u - 0.14)), p(max(0, u - 0.08)), p(u)
        d.line([tail, b], fill=(255, 240, 200, 125), width=2)
        d.line([a, b], fill=(26, 20, 16, 235), width=3)
        d.ellipse([b[0] - 2, b[1] - 2, b[0] + 2, b[1] + 2], fill=(245, 220, 150, 240))


def draw_breach_smoke(layer, glow, cx, cy, t_rel, scale=1.0):
    """战火与黑灰烟柱：支持缩放以适配城门小火或狭道火车烈焰。"""
    if t_rel <= 0:
        return
    ramp = clamp01(t_rel / 0.65)
    d_sm = ImageDraw.Draw(layer)
    d_gl = ImageDraw.Draw(glow)
    n_puffs = 14
    for i in range(n_puffs):
        age = (t_rel + i * (1.8 / n_puffs)) % 1.8
        u = age / 1.8
        px = cx - 96.0 * scale * u + 8.0 * scale * math.sin(u * 6.5 + i)
        py = cy - 118.0 * scale * u
        r = (11.0 + 27.0 * u) * scale * ramp
        a = int(128 * ramp * math.sin(math.pi * u) ** 0.75)
        d_sm.ellipse([px - r, py - r * 0.85, px + r, py + r * 0.85], fill=(56, 48, 42, a))
    for ox, h_f, w_f, ph in [(-11, 30, 9, 0.0), (0, 38, 11, 1.8), (11, 26, 8, 3.4)]:
        ox, h_f, w_f = ox * scale, h_f * scale, w_f * scale
        flick = 0.82 + 0.24 * math.sin(t_rel * 13.0 + ph)
        sway = 5.0 * scale * math.sin(t_rel * 9.5 + ph)
        bx, by = cx + ox, cy + 4
        tip = (bx - 4 * scale + sway, by - h_f * ramp * flick)
        poly_out = [(bx - w_f * ramp, by), (bx - w_f * 0.45 * ramp, by - h_f * 0.45 * ramp), tip,
                    (bx + w_f * 0.55 * ramp, by - h_f * 0.40 * ramp), (bx + w_f * ramp, by)]
        d_gl.polygon(poly_out, fill=(242, 114, 24, int(198 * ramp)))
        tip_in = (bx - 2 * scale + sway * 0.6, by - h_f * 0.62 * ramp * flick)
        poly_in = [(bx - w_f * 0.5 * ramp, by), tip_in, (bx + w_f * 0.5 * ramp, by)]
        d_gl.polygon(poly_in, fill=(255, 218, 96, int(225 * ramp)))


def draw_siege_ladder(layer, p_base, p_top, t_rel, fade_at=None):
    """木制云梯：t_rel∈[0, 0.45] 自城下架抵城垛；fade_at 到来后倾倒淡出。"""
    if t_rel < 0.0:
        return
    al = 1.0
    if fade_at is not None and t_rel >= fade_at:
        al = max(0.0, 1.0 - smooth((t_rel - fade_at) / 0.45))
        if al <= 0.02:
            return
    u = ease_out(min(1.0, t_rel / 0.45))
    bx, by = float(p_base[0]), float(p_base[1])
    tx, ty = float(p_top[0]), float(p_top[1])
    cx = bx + (tx - bx) * u
    cy = by + (ty - by) * u - (1.0 - u) * 18.0
    dx, dy = cx - bx, cy - by
    L = max(1.0, math.hypot(dx, dy))
    nx, ny = -dy / L, dx / L
    hw = 8.5
    d = ImageDraw.Draw(layer)
    a_edge = int(235 * al)
    a_wood = int(245 * al)
    for sgn in (-1.0, 1.0):
        r1 = (bx + nx * hw * sgn, by + ny * hw * sgn)
        r2 = (cx + nx * hw * sgn, cy + ny * hw * sgn)
        d.line([r1, r2], fill=(28, 18, 11, a_edge), width=6)
        d.line([r1, r2], fill=(172, 112, 56, a_wood), width=3)
    n_rungs = max(4, int(L / 13.0))
    for k in range(1, n_rungs):
        f = k / float(n_rungs)
        rx, ry = bx + dx * f, by + dy * f
        p1 = (rx - nx * (hw + 1.0), ry - ny * (hw + 1.0))
        p2 = (rx + nx * (hw + 1.0), ry + ny * (hw + 1.0))
        d.line([p1, p2], fill=(28, 18, 11, a_edge), width=4)
        d.line([p1, p2], fill=(205, 146, 78, a_wood), width=2)


# ----------------------------------------------------------------------------- 基类
class BattleAnimatorBase:
    BID = "B03"
    ACTION_END = 8.4

    def __init__(self, arrow_renderer=None, cues=None, default_cues=None, skip_static_fire=False):
        self.arrow_renderer = arrow_renderer
        self.cues = {**(default_cues or {}), **(cues or {})}
        self._arrow_cache = {}
        self.actors = []
        self.events = []
        self.fx = []
        self._build_layers(self.BID, skip_static_fire=skip_static_fire)
        self._build_cast()

    def _build_layers(self, bid, skip_static_fire=False):
        fig = plt.figure(figsize=(19.2, 10.8), dpi=100, frameon=False)
        ax = fig.add_axes([0, 0, 1, 1])
        try:
            tm.draw_tactical_map(ax, bid, detail_background=True, arrow_progress=0.0)
            kids = list(ax.get_children())
            vis = [k.get_visible() for k in kids]
            is_unit = lambda k: 21.3 <= k.get_zorder() <= 22.2 or abs(k.get_zorder() - 26.0) < 0.05
            is_fire = lambda k: skip_static_fire and abs(k.get_zorder() - 29.0) < 0.05

            for k, v in zip(kids, vis):
                k.set_visible(v and k.get_zorder() < 21.0)
            fig.canvas.draw()
            self.below = Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[..., :3].copy(), "RGB").convert("RGBA")
            for k, v in zip(kids, vis):
                k.set_visible(v and k.get_zorder() >= 22.5 and not is_unit(k) and not is_fire(k))
            fig.patch.set_visible(False)
            ax.patch.set_visible(False)
            fig.canvas.draw()
            self.above = Image.fromarray(np.asarray(fig.canvas.buffer_rgba()).copy(), "RGBA")
        finally:
            plt.close(fig)

    def _build_cast(self):
        raise NotImplementedError

    def _arrows(self, prog):
        if self.arrow_renderer is None:
            return None
        key = round(min(1.0, prog), 3)
        if key >= 1.0 and 1.0 in self._arrow_cache:
            return self._arrow_cache[1.0]
        arr = self.arrow_renderer(self.BID, key)
        img = Image.fromarray(arr, "RGBA") if arr is not None else None
        if key >= 1.0:
            self._arrow_cache[1.0] = img
        return img

    def frame(self, t, arrow_prog=1.0):
        canvas = self.below.copy()
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dust = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        bodies = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        props = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        live = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        for a in self.actors:
            if a.kind == "cav":
                draw_dust(dust, a, t)
        order = sorted(self.actors, key=lambda a: (0 if a.dead(t) and t - a.die_t > 0.45 else 1, a.pos(t)[1]))
        for a in order:
            tgt = bodies if (a.dead(t) and t - a.die_t > 0.45) else live
            a.render(t, tgt, sd)
        fxl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for f in self.fx:
            if f[0] == "ladder":
                fade_at = f[4] if len(f) > 4 else None
                draw_siege_ladder(props, f[2], f[3], t - f[1], fade_at=fade_at)
            elif f[0] == "slash":
                draw_slash(fxl, glow, f[2][0], f[2][1], (t - f[1]) / 0.30, f[3])
            elif f[0] == "blood":
                draw_blood(fxl, f[2][0], f[2][1], t - f[1], f[4], f[3])
            elif f[0] == "volley":
                draw_volley(fxl, f[2], f[3], t - f[1], 77)
            elif f[0] == "smoke":
                sc = f[3] if len(f) > 3 else 1.0
                draw_breach_smoke(fxl, glow, f[2][0], f[2][1], t - f[1], scale=sc)
        canvas.alpha_composite(shadow)
        canvas.alpha_composite(bodies)
        canvas.alpha_composite(props)
        canvas.alpha_composite(dust)
        canvas.alpha_composite(live)
        canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(9)))
        canvas.alpha_composite(glow)
        canvas.alpha_composite(fxl)
        arr = self._arrows(arrow_prog)
        if arr is not None:
            adim = float(self.cues["arrows_dim_at"])
            ares = float(self.cues["arrows_restore_at"])
            k = 1.0 - 0.7 * smooth((t - adim) / 0.45) + 0.7 * smooth((t - ares) / 0.55)
            canvas.alpha_composite(with_alpha(arr, k))
        canvas.alpha_composite(self.above)
        return np.asarray(canvas.convert("RGB"))


# ----------------------------------------------------------------------------- B03 东京洛阳保卫战
DEFAULT_B03_CUES = {
    "charge_start": 0.35,
    "front_kills": [1.75, 2.05, 2.40],
    "chase_north_turn": 2.00,
    "chase_north_kill": 3.83,
    "chase_south_turn": 1.92,
    "chase_south_kill": 4.81,
    "mix_arrive": 4.90,
    "volley": 5.02,
    "wall_deaths": [5.55, 5.82],
    "smoke_start": 5.95,
    "gate_slash": 6.12,
    "banner_fall": 6.25,
    "arrows_dim_at": 1.35,
    "arrows_restore_at": 7.30,
    "action_end": 8.40,
}


class B03Animator(BattleAnimatorBase):
    BID = "B03"
    ACTION_END = 8.4

    def __init__(self, arrow_renderer=None, cues=None):
        super().__init__(arrow_renderer=arrow_renderer, cues=cues, default_cues=DEFAULT_B03_CUES)

    def _build_cast(self):
        cav = unit_sprite("YAN_AN", "cavalry", True)
        mix = unit_sprite("YAN_AN", "mixed", True)
        levy = unit_sprite("TANG", "levy", False)
        inf = unit_sprite("TANG", "infantry", False)
        A = []
        c = self.cues

        L = group_slots(995, 512, 5, levy.width)
        C = group_slots(1425, 545, 5, cav.width)
        M = group_slots(1600, 405, 4, mix.width)
        T = group_slots(655, 618, 3, inf.width)

        cs = float(c["charge_start"])
        fk = list(c["front_kills"])
        for ci, li, ts in [(0, 4, fk[0]), (1, 3, fk[1]), (2, 2, fk[2])]:
            vx, vy = L[li]
            hx, hy = vx + 52, vy - 2
            A.append(Actor(f"C{ci}", cav, [(0.0,) + C[ci], (cs + ci * 0.08,) + C[ci], (ts - 0.05, hx, hy), (ts + 0.5, hx - 40, hy - 10), (ts + 1.8, hx - 170 + ci * 20, hy - 34 + ci * 30)],
                           kind="cav", face_left=True, slashes=[ts], phase=ci * 1.3, gait=1.1))
            A.append(Actor(f"L{li}", levy, [(0.0,) + L[li], (ts, vx + 4, vy)], die_t=ts + 0.06, fall_dir=1, phase=li))
            self.fx += [("slash", ts, (hx - 20, hy - 30), True), ("blood", ts + 0.06, (vx + 6, vy - 30), -1, 100 + li)]
            self.events += [(ts, "slash", hx), (ts + 0.06, "death", vx)]

        x1, y1 = L[1]
        nturn, nk = float(c["chase_north_turn"]), float(c["chase_north_kill"])
        nmid = 0.5 * (nturn + nk)
        l1_keys = [(0.0, x1, y1), (nturn, x1, y1), (nmid, 905, 612), (nk + 0.05, 832, 622)]
        A.append(Actor("L1", levy, l1_keys, turn_t=nturn, die_t=nk + 0.05, fall_dir=1, gait=1.25, phase=0.7))
        cx3, cy3 = l1_keys[-1][1] + 50, l1_keys[-1][2] - 2
        A.append(Actor("C3", cav, [(0.0,) + C[3], (cs + 0.15,) + C[3], (nmid - 0.35, 1075, 588), (nk - 0.01, cx3, cy3), (nk + 0.82, cx3 - 42, cy3 + 10), (nk + 1.77, 910, 608)],
                       kind="cav", face_left=True, slashes=[nk], phase=2.2, gait=1.15))
        self.fx += [("slash", nk, (cx3 - 22, cy3 - 32), True), ("blood", nk + 0.06, (l1_keys[-1][1] + 4, l1_keys[-1][2] - 30), -1, 201)]
        self.events += [(nk, "slash", cx3), (nk + 0.06, "death", l1_keys[-1][1])]

        x0, y0 = L[0]
        sturn, sk = float(c["chase_south_turn"]), float(c["chase_south_kill"])
        l0_keys = [(0.0, x0, y0), (sturn, x0, y0), (sturn + 0.35 * (sk - sturn), 850, 705), (sturn + 0.72 * (sk - sturn), 755, 756), (sk + 0.05, 695, 766)]
        A.append(Actor("L0", levy, l0_keys, turn_t=sturn, die_t=sk + 0.05, fall_dir=1, gait=1.28, phase=1.9))
        cx4, cy4 = l0_keys[-1][1] + 52, l0_keys[-1][2] - 2
        A.append(Actor("C4", cav, [(0.0,) + C[4], (cs + 0.45,) + C[4], (sturn + 0.34 * (sk - sturn), 1020, 685), (sturn + 0.75 * (sk - sturn), 835, 745), (sk - 0.01, cx4, cy4), (sk + 0.84, 610, 778), (sk + 2.55, 395, 792)],
                       kind="cav", face_left=True, slashes=[sk], phase=0.4, gait=1.18))
        self.fx += [("slash", sk, (cx4 - 22, cy4 - 32), True), ("blood", sk + 0.06, (l0_keys[-1][1] + 4, l0_keys[-1][2] - 30), -1, 202)]
        self.events += [(sk, "slash", cx4), (sk + 0.06, "death", l0_keys[-1][1])]

        m_arr, vt = float(c["mix_arrive"]), float(c["volley"])
        wd1, wd2 = float(c["wall_deaths"][0]), float(c["wall_deaths"][1])
        gs, sm, bf, end_t = float(c["gate_slash"]), float(c["smoke_start"]), float(c["banner_fall"]), float(c["action_end"])
        tgt = [(870, 650), (940, 676), (1010, 650), (1080, 678)]
        yan_inf_assault = unit_sprite("YAN_AN", "infantry", True)
        lad_t = max(0.4, m_arr - 0.55)
        self.fx.append(("ladder", lad_t, (812, 622), (748, 496)))
        for i in range(4):
            if i == 0:
                A.append(Actor("M0", yan_inf_assault, [(0.0,) + M[0], (cs + 0.60,) + M[0], (m_arr - 0.10, 812, 622),
                                                      (gs - 0.05, 756, 498), (gs + 0.68, 725, 495)],
                               kind="inf", face_left=True, slashes=[gs], phase=0.0))
                self.fx.append(("slash", gs, (734, 466), True))
                self.events.append((gs, "slash", 756))
            else:
                A.append(Actor(f"M{i}", mix, [(0.0,) + M[i], (cs + 0.60,) + M[i], (m_arr,) + tgt[i]], kind="cav", face_left=True, phase=i * 0.9))
        self.fx.append(("volley", vt, (935, 625), (665, 458)))
        self.events.append((vt, "volley", 900))
        for i, (tx, ty) in enumerate(T):
            if i == 2:
                A.append(Actor("T2", inf, [(0.0, tx, ty)], die_t=wd1, fall_dir=1, phase=i))
                self.fx.append(("blood", wd1, (tx + 4, ty - 30), -1, 301))
                self.events.append((wd1, "death", tx))
            elif i == 1:
                A.append(Actor("T1", inf, [(0.0, tx, ty)], die_t=wd2, fall_dir=-1, phase=i))
                self.fx.append(("blood", wd2, (tx, ty - 30), -1, 302))
                self.events.append((wd2, "death", tx))
            else:
                A.append(Actor("T0", inf, [(0.0, tx, ty), (wd2 + 0.06, tx, ty), (wd2 + 0.92, tx - 86, ty + 8)], turn_t=wd2 + 0.06, fade=(wd2 + 0.52, wd2 + 1.02), phase=i))
        self.fx.append(("smoke", sm, (742, 578), 1.0))

        f0 = sturn - 0.07
        fcq = banner_sprite("封常清", "TANG", 142)
        A.append(Actor("B_feng", fcq, [(0.0, 862, H - 412), (f0, 862, H - 412), (f0 + 1.1, 730, 775), (sk - 0.25, 510, 792), (bf - 0.1, 275, 796), (min(end_t, bf + 1.2), 140, 798)],
                       banner=True, fade=(min(end_t - 0.7, bf + 0.6), min(end_t - 0.1, bf + 1.2)), phase=0.3))
        lc = banner_sprite("李憕", "TANG", 128)
        A.append(Actor("B_li", lc, [(0.0, 555, H - 528)], banner=True, die_t=bf, fall_dir=-1))
        self.events.append((bf, "banner_fall", 555))
        al = banner_sprite("安禄山", "YAN_AN", 152)
        A.append(Actor("B_an", al, [(0.0, 1625, H - 555), (cs + 0.8, 1625, H - 555), (bf - 0.2, 1380, H - 545)], banner=True, phase=1.1))
        self.actors = A


# ----------------------------------------------------------------------------- B05 嘉山大捷
DEFAULT_B05_CUES = {
    "charge_start": 0.45,
    "front_kills": [1.89, 2.49, 3.72],
    "chase_turn": 2.65,
    "chase_kill": 4.33,
    "chase_gate_slash": 5.53,
    "arrows_dim_at": 1.35,
    "arrows_restore_at": 7.00,
    "action_end": 8.58,
}


class B05Animator(BattleAnimatorBase):
    """嘉山大捷：唐军涉过滹沱水反冲破敌、正面连斩燕骑、东北追砍溃逃敌骑直逼博陵。"""
    BID = "B05"
    ACTION_END = 8.58

    def __init__(self, arrow_renderer=None, cues=None):
        super().__init__(arrow_renderer=arrow_renderer, cues=cues, default_cues=DEFAULT_B05_CUES)

    def _build_cast(self):
        tang_mix = unit_sprite("TANG", "mixed", False)
        yan_cav = unit_sprite("YAN_AN", "cavalry", True)
        A = []
        c = self.cues

        L = group_slots(820, 480, 5, tang_mix.width)   # 唐精锐混编 (朝右)
        R = group_slots(1260, 560, 4, yan_cav.width)   # 史思明边骑 (朝左)

        cs = float(c["charge_start"])
        fk = list(c["front_kills"])

        # 1) 唐军前锋 L4, L3, L2 渡河强攻，连斩燕军前阵 R0, R1, R2
        for li, ri, ts in [(4, 0, fk[0]), (3, 1, fk[1]), (2, 2, fk[2])]:
            vx, vy = R[ri]
            hx, hy = vx - 54, vy + 2
            A.append(Actor(f"L{li}", tang_mix, [(0.0,) + L[li], (cs + (4 - li) * 0.12,) + L[li], (ts - 0.05, hx, hy), (ts + 0.55, hx + 46, hy - 14), (ts + 1.85, hx + 160, hy - 55)],
                           kind="cav", face_left=False, slashes=[ts], phase=li * 1.1, gait=1.15))
            A.append(Actor(f"R{ri}", yan_cav, [(0.0,) + R[ri], (ts - 0.5, vx - 30, vy + 4), (ts, vx - 4, vy)], die_t=ts + 0.06, fall_dir=-1, face_left=True, phase=ri))
            self.fx += [("slash", ts, (hx + 22, hy - 30), False), ("blood", ts + 0.06, (vx - 6, vy - 28), 1, 400 + ri)]
            self.events += [(ts, "slash", hx), (ts + 0.06, "death", vx)]

        # 2) 史思明溃逃追砍：R3 转身东北奔逃向博陵，唐骑 L1 从背后追上劈倒在地
        rx3, ry3 = R[3]
        cturn = float(c["chase_turn"])
        ck = float(c["chase_kill"])
        cmid = 0.5 * (cturn + ck)
        r3_keys = [(0.0, rx3, ry3), (cturn, rx3, ry3), (cmid, 1365, 480), (ck + 0.05, 1410, 415)]
        A.append(Actor("R3", yan_cav, r3_keys, kind="cav", face_left=True, turn_t=cturn, die_t=ck + 0.05, fall_dir=-1, gait=1.25, phase=0.8))
        hx1, hy1 = r3_keys[-1][1] - 52, r3_keys[-1][2] + 4
        A.append(Actor("L1", tang_mix, [(0.0,) + L[1], (cs + 0.25,) + L[1], (cmid - 0.35, 1210, 535), (ck - 0.01, hx1, hy1), (ck + 0.80, hx1 + 52, hy1 - 28), (ck + 1.80, 1435, 390)],
                       kind="cav", face_left=False, slashes=[ck], phase=1.7, gait=1.2))
        self.fx += [("slash", ck, (hx1 + 22, hy1 - 30), False), ("blood", ck + 0.06, (r3_keys[-1][1] - 4, r3_keys[-1][2] - 28), 1, 411)]
        self.events += [(ck, "slash", hx1), (ck + 0.06, "death", r3_keys[-1][1])]

        # 3) 唐先锋 L0 乘胜追抵博陵城外一击耀武，逼使史思明退守博陵
        gs = float(c["chase_gate_slash"])
        A.append(Actor("L0", tang_mix, [(0.0,) + L[0], (cs + 0.40,) + L[0], (cmid, 1140, 560), (gs - 0.02, 1405, 345), (gs + 0.85, 1390, 355)],
                       kind="cav", face_left=False, slashes=[gs], phase=2.4, gait=1.22))
        self.fx.append(("slash", gs, (1425, 315), False))
        self.events.append((gs, "slash", 1405))

        # 4) 帅旗：郭子仪旗渡河前压，史思明旗溃退博陵城下
        end_t = float(c["action_end"])
        gzy = banner_sprite("郭子仪", "TANG", 150)
        A.append(Actor("B_guo", gzy, [(0.0, 650, H - 500), (cs + 0.6, 650, H - 500), (ck - 0.2, 960, 565), (end_t - 1.2, 1120, 550)],
                       banner=True, phase=0.2))
        ssm = banner_sprite("史思明", "YAN_AN", 150)
        A.append(Actor("B_shi", ssm, [(0.0, 1410, H - 570), (cturn, 1410, H - 570), (ck, 1465, 430), (gs + 0.4, 1485, 365)],
                       banner=True, phase=1.1))
        self.events.append((gs + 0.35, "gong_retreat", 1485))
        self.actors = A


# ----------------------------------------------------------------------------- B06 灵宝西原大败
DEFAULT_B06_CUES = {
    "arrows_done": 2.30,
    "march_start": 0.80,
    "fire_start": 10.38,
    "volley": 11.43,
    "ambush_kills": [12.52, 13.15, 13.75],
    "chase_kills": [14.35, 14.98, 16.19],
    "arrows_dim_at": 2.90,
    "arrows_restore_at": 16.30,
    "action_end": 17.42,
}


class B06Animator(BattleAnimatorBase):
    """灵宝西原大败：漫长纵队拥塞河崖狭道 → 火车纵火阻前、南山伏兵截腰与追砍大溃败。"""
    BID = "B06"
    ACTION_END = 17.42

    def __init__(self, arrow_renderer=None, cues=None):
        super().__init__(arrow_renderer=arrow_renderer, cues=cues, default_cues=DEFAULT_B06_CUES, skip_static_fire=True)

    def _build_cast(self):
        tang_mix = unit_sprite("TANG", "mixed", False)
        yan_cav = unit_sprite("YAN_AN", "cavalry", True)
        yan_inf = unit_sprite("YAN_AN", "infantry", True)
        A = []
        c = self.cues

        C1 = group_slots(635, 762, 5, tang_mix.width, layout="column")   # 唐后继纵队
        C2 = group_slots(1035, 768, 4, tang_mix.width, layout="column")  # 唐前军纵队
        E = group_slots(1510, 768, 4, yan_cav.width)                     # 崔乾祐正面骑兵
        S = group_slots(1140, 470, 4, yan_inf.width)                     # 南山绝壁伏兵

        ms = float(c["march_start"])
        fs = float(c["fire_start"])
        vt = float(c["volley"])
        ak = list(c["ambush_kills"])
        ck = list(c["chase_kills"])
        end_t = float(c["action_end"])

        # 阶段 1：火起前前军 C2 与后队 C1 沿着河崖狭道东进并陷入拥塞；南山伏兵悄悄下山逼近坡沿
        c2_adv = [(p[0] + 68.0, p[1]) for p in C2]
        c1_adv = [(p[0] + 58.0, p[1]) for p in C1]

        # 阶段 2（火起爆发）：C2[3], C2[2], C2[1] 被崔乾祐前锋与冲下山坡的伏兵先后斩杀于火场
        for ci, ts, attacker_src in [(3, ak[0], ("E", 0)), (2, ak[1], ("E", 1)), (1, ak[2], ("S", 0))]:
            vx, vy = c2_adv[ci]
            A.append(Actor(f"C2_{ci}", tang_mix, [(0.0,) + C2[ci], (ms,) + C2[ci], (fs - 0.3, vx, vy)],
                           kind="cav", face_left=False, die_t=ts + 0.05, fall_dir=1, phase=ci))
            hx, hy = vx + 50, vy - 2
            if attacker_src[0] == "E":
                ei = attacker_src[1]
                A.append(Actor(f"E{ei}", yan_cav, [(0.0,) + E[ei], (fs - 0.1,) + E[ei], (ts - 0.04, hx, hy), (ts + 0.85, hx - 70, hy + 6)],
                               kind="cav", face_left=True, slashes=[ts], phase=ei, gait=1.18))
            else:
                A.append(Actor("S0", yan_inf, [(0.0,) + S[0], (ms + 1.8,) + S[0], (fs - 0.2, 1085, 455), (ts - 0.04, hx - 12, hy + 8), (ts + 0.9, hx - 55, hy + 14)],
                               kind="inf", face_left=True, slashes=[ts], phase=0.5, gait=1.2))
            self.fx += [("slash", ts, (hx - 20, hy - 30), True), ("blood", ts + 0.05, (vx + 4, vy - 28), -1, 500 + ci)]
            self.events += [(ts, "slash", hx), (ts + 0.05, "death", vx)]

        # 阶段 3（追砍溃败）：C2[0] 与 C1[4], C1[3] 调头向潼关西逃，依次被崔乾祐骑兵与南山伏兵追上砍倒
        turn_rout = fs + 1.4
        # Chase 1: E2 追斩 C2[0]
        v0x, v0y = c2_adv[0]
        A.append(Actor("C2_0", tang_mix, [(0.0,) + C2[0], (ms,) + C2[0], (fs - 0.2, v0x, v0y), (turn_rout, v0x, v0y), (ck[0] + 0.05, 865, 336)],
                       kind="cav", face_left=False, turn_t=turn_rout, die_t=ck[0] + 0.05, fall_dir=1, gait=1.25))
        hx2, hy2 = 915, 334
        A.append(Actor("E2", yan_cav, [(0.0,) + E[2], (fs,) + E[2], (ak[1], 1185, 332), (ck[0] - 0.01, hx2, hy2), (ck[0] + 1.1, 800, 342)],
                       kind="cav", face_left=True, slashes=[ck[0]], phase=1.4, gait=1.25))
        self.fx += [("slash", ck[0], (hx2 - 22, hy2 - 30), True), ("blood", ck[0] + 0.05, (868, 306), -1, 511)]
        self.events += [(ck[0], "slash", hx2), (ck[0] + 0.05, "death", 865)]

        # Chase 2: E3 追斩 C1[4]
        v4x, v4y = c1_adv[4]
        A.append(Actor("C1_4", tang_mix, [(0.0,) + C1[4], (ms,) + C1[4], (fs - 0.2, v4x, v4y), (turn_rout + 0.1, v4x, v4y), (ck[1] + 0.05, 660, 342)],
                       kind="cav", face_left=False, turn_t=turn_rout + 0.1, die_t=ck[1] + 0.05, fall_dir=1, gait=1.28, phase=0.9))
        hx3, hy3 = 710, 340
        A.append(Actor("E3", yan_cav, [(0.0,) + E[3], (fs + 0.2,) + E[3], (ck[0], 985, 335), (ck[1] - 0.01, hx3, hy3), (ck[1] + 1.0, 610, 345)],
                       kind="cav", face_left=True, slashes=[ck[1]], phase=2.0, gait=1.28))
        self.fx += [("slash", ck[1], (hx3 - 22, hy3 - 30), True), ("blood", ck[1] + 0.05, (664, 312), -1, 512)]
        self.events += [(ck[1], "slash", hx3), (ck[1] + 0.05, "death", 660)]

        # Chase 3: S1 追斩 C1[3] 于潼关东外
        v3x, v3y = c1_adv[3]
        A.append(Actor("C1_3", tang_mix, [(0.0,) + C1[3], (ms,) + C1[3], (fs - 0.2, v3x, v3y), (turn_rout + 0.2, v3x, v3y), (ck[2] + 0.05, 495, 345)],
                       kind="cav", face_left=False, turn_t=turn_rout + 0.2, die_t=ck[2] + 0.05, fall_dir=1, gait=1.3, phase=1.4))
        hx1s, hy1s = 545, 344
        A.append(Actor("S1", yan_inf, [(0.0,) + S[1], (ms + 2.0,) + S[1], (fs - 0.2, 1115, 455), (ak[2], 935, 395), (ck[2] - 0.01, hx1s, hy1s), (end_t, 475, 348)],
                       kind="inf", face_left=True, slashes=[ck[2]], phase=1.1, gait=1.25))
        self.fx += [("slash", ck[2], (hx1s - 22, hy1s - 30), True), ("blood", ck[2] + 0.05, (499, 315), -1, 513)]
        self.events += [(ck[2], "slash", hx1s), (ck[2] + 0.05, "death", 495)]

        # 其余唐后队残部 C1[0..2] 仓皇西逃入潼关
        for ri in range(3):
            rx0, ry0 = c1_adv[ri]
            A.append(Actor(f"C1_{ri}", tang_mix, [(0.0,) + C1[ri], (ms,) + C1[ri], (fs - 0.2, rx0, ry0), (turn_rout + 0.25, rx0, ry0), (ck[2] - 0.2, 310 + ri * 28, 355), (end_t - 0.2, 175 + ri * 20, 360)],
                           kind="cav", face_left=False, turn_t=turn_rout + 0.25, fade=(end_t - 1.5, end_t - 0.5), gait=1.3, phase=ri))

        # 南山其余伏兵 S2, S3 潜伏至坡沿后齐射箭雨并下山逼近
        for si in [2, 3]:
            sx0, sy0 = S[si]
            A.append(Actor(f"S{si}", yan_inf, [(0.0, sx0, sy0), (ms + 2.0, sx0, sy0), (fs - 0.2, sx0 - 20, 465), (vt + 0.3, sx0 - 20, 465), (end_t - 0.8, sx0 - 115, 370)],
                           kind="inf", face_left=True, phase=si))

        # 箭雨与峡谷烈焰火车浓烟
        self.fx.append(("volley", vt, (1120, 455), (960, 330)))
        self.events.append((vt, "volley", 1040))
        self.fx.append(("smoke", fs, (1185, 316), 1.35))
        self.fx.append(("smoke", fs + 0.35, (1085, 326), 1.15))
        self.events.append((fs, "fire_ambush", 1140))

        # 帅旗：哥舒翰西撤退入潼关；南山伏兵上山沿；崔乾祐前压
        gsh = banner_sprite("哥舒翰", "TANG", 148)
        A.append(Actor("B_geshu", gsh, [(0.0, 635, H - 795), (ms, 635, H - 795), (fs - 0.2, 710, H - 795), (turn_rout + 0.2, 710, H - 795), (ck[2] + 0.1, 315, 310), (end_t - 0.3, 185, 315)],
                       banner=True, fade=(end_t - 1.2, end_t - 0.3), phase=0.2))
        ns = banner_sprite("南山伏兵", "YAN_AN", 140)
        A.append(Actor("B_nanshan", ns, [(0.0, 1315, H - 460), (ms + 2.0, 1315, H - 460), (fs, 1280, 470), (end_t - 0.8, 1210, 415)], banner=True, phase=0.9))
        cqy = banner_sprite("崔乾祐", "YAN_AN", 148)
        A.append(Actor("B_cui", cqy, [(0.0, 1510, H - 800), (fs, 1510, H - 800), (end_t - 0.6, 1250, 290)], banner=True, phase=1.4))
        self.actors = A


# ----------------------------------------------------------------------------- B10 太原保卫战
DEFAULT_B10_CUES = {
    "arrows_done": 1.60,
    "siege_advance": 0.85,
    "volley": 2.15,
    "tunnel_smoke": 2.95,
    "sally_kills": [4.25, 4.88, 5.48],
    "chase_turn": 5.85,
    "chase_kills": [6.68, 7.38],
    "arrows_dim_at": 1.95,
    "arrows_restore_at": 7.70,
    "action_end": 8.55,
}


class B10Animator(BattleAnimatorBase):
    """太原保卫战：史思明合围晋阳 → 城头箭雨阻滞与地道塌陷土山 → 李光弼出城连斩与东路追砍溃敌。"""
    BID = "B10"
    ACTION_END = 8.55

    def __init__(self, arrow_renderer=None, cues=None):
        super().__init__(arrow_renderer=arrow_renderer, cues=cues, default_cues=DEFAULT_B10_CUES)

    def _build_cast(self):
        tang_inf = unit_sprite("TANG", "infantry", False)
        yan_mix = unit_sprite("YAN_AN", "mixed", True)
        A = []
        c = self.cues

        T = group_slots(950, 620, 4, tang_inf.width)   # 晋阳守军 (朝右)
        Y = group_slots(1380, 540, 5, yan_mix.width)   # 史思明十万围兵 (朝左)

        sa = float(c["siege_advance"])
        vt = float(c["volley"])
        sm = float(c["tunnel_smoke"])
        sk = list(c["sally_kills"])
        cturn = float(c["chase_turn"])
        ck = list(c["chase_kills"])
        end_t = float(c["action_end"])

        # 1) 燕军架云梯逼东墙，守城箭雨阻击 + 地道塌陷炸毁云梯与土山
        lad_t10 = min(vt - 0.15, sa + 0.45)
        self.fx.append(("ladder", lad_t10, (1120, 588), (1055, 495), max(0.6, sm - lad_t10 + 0.15)))
        self.fx.append(("volley", vt, (1035, 490), (1185, 565)))
        self.events.append((vt, "volley", 1110))
        self.fx.append(("smoke", sm, (1152, 578), 1.25))
        self.fx.append(("smoke", sm + 0.18, (1222, 588), 0.95))
        self.events.append((sm, "tunnel_blast", 1170))

        # 2) 出击守军 T3, T2, T1 由地面东门涌出杀敌（不跳城楼）
        gate_posts = [None, (995, 588), (1022, 594), (1046, 576)]
        y_mound = [(1170, 558), (1228, 572), (1290, 584)]
        for idx, (mx, my) in enumerate(y_mound):
            ts = sk[idx]
            A.append(Actor(f"Y{idx}", yan_mix, [(0.0,) + Y[idx], (sa + idx * 0.10,) + Y[idx], (sm - 0.10, mx, my), (ts, mx + 6, my)],
                           kind="cav", face_left=True, die_t=ts + 0.06, fall_dir=-1, phase=idx * 0.7))
            hx, hy = mx - 48, my + 2
            ti = 3 - idx
            p0 = gate_posts[ti]
            sally_keys = [(0.0,) + p0, (sm + 0.35 + idx * 0.12,) + p0, (sm + 0.85 + idx * 0.12, 1095, 572 + idx * 10), (ts - 0.04, hx, hy)]
            if idx == 0:
                # T3 先斩 Y0，再顺势东追 Y3
                y3_end = (1540, 505)
                hx_c0, hy_c0 = y3_end[0] - 50, y3_end[1] + 2
                sally_keys += [(ts + 0.55, hx + 46, hy - 14), (cturn + 0.10, 1295, 535), (ck[0] - 0.02, hx_c0, hy_c0),
                               (ck[0] + 0.55, hx_c0 + 44, hy_c0 - 12), (end_t - 0.25, 1145, 560)]
                A.append(Actor("T3", tang_inf, sally_keys, slashes=[ts, ck[0]], gait=1.2, phase=0.4))
                self.fx += [("slash", ck[0], (hx_c0 + 22, hy_c0 - 30), False), ("blood", ck[0] + 0.06, (y3_end[0] - 6, y3_end[1] - 28), 1, 510)]
                self.events += [(ck[0], "slash", hx_c0), (ck[0] + 0.06, "death", y3_end[0])]
            elif idx == 1:
                # T2 先斩 Y1，再追砍东溃的 Y4
                y4_end = (1615, 595)
                hx_c1, hy_c1 = y4_end[0] - 50, y4_end[1] + 2
                sally_keys += [(ts + 0.50, hx + 42, hy + 8), (cturn + 0.18, 1345, 580), (ck[1] - 0.02, hx_c1, hy_c1),
                               (ck[1] + 0.52, hx_c1 + 42, hy_c1 - 10), (end_t - 0.25, 1165, 585)]
                A.append(Actor("T2", tang_inf, sally_keys, slashes=[ts, ck[1]], gait=1.18, phase=1.1))
                self.fx += [("slash", ck[1], (hx_c1 + 22, hy_c1 - 30), False), ("blood", ck[1] + 0.06, (y4_end[0] - 6, y4_end[1] - 28), 1, 511)]
                self.events += [(ck[1], "slash", hx_c1), (ck[1] + 0.06, "death", y4_end[0])]
            else:
                # T1 斩 Y2 后退回地面东门警戒
                sally_keys += [(ts + 0.65, hx + 45, hy - 4), (end_t - 0.4, 1055, 582)]
                A.append(Actor("T1", tang_inf, sally_keys, slashes=[ts], gait=1.12, phase=1.8))
            self.fx += [("slash", ts, (hx + 22, hy - 30), False), ("blood", ts + 0.06, (mx, my - 28), 1, 500 + idx)]
            self.events += [(ts, "slash", hx), (ts + 0.06, "death", mx)]

        # 3) T0 留守北都城墙上，居高射箭督战
        A.append(Actor("T0", tang_inf, [(0.0,) + T[0], (sm, T[0][0] + 24, T[0][1]), (end_t, 945, 488)], phase=0.2))

        # 4) 后阵燕军 Y3, Y4 转身东溃并遭追砍倒地
        y3_mid = (1440, 520)
        A.append(Actor("Y3", yan_mix, [(0.0,) + Y[3], (sa + 0.25,) + Y[3], (sm - 0.1, 1345, 538), (cturn, 1345, 538),
                                       (0.5 * (cturn + ck[0]),) + y3_mid, (ck[0] + 0.05, 1540, 505)],
                       kind="cav", face_left=True, turn_t=cturn, die_t=ck[0] + 0.06, fall_dir=-1, gait=1.25, phase=0.6))
        y4_turn = cturn + 0.08
        A.append(Actor("Y4", yan_mix, [(0.0,) + Y[4], (sa + 0.35,) + Y[4], (sm - 0.1, 1405, 576), (y4_turn, 1405, 576),
                                       (0.5 * (y4_turn + ck[1]), 1515, 588), (ck[1] + 0.05, 1615, 595)],
                       kind="cav", face_left=True, turn_t=y4_turn, die_t=ck[1] + 0.06, fall_dir=-1, gait=1.28, phase=1.4))

        # 5) 帅旗：李光弼镇守太原，史思明帅旗东溃
        lgb = banner_sprite("李光弼", "TANG", 150)
        A.append(Actor("B_li", lgb, [(0.0, 830, H - 620), (sm + 0.5, 830, H - 620), (sk[2], 885, H - 615), (end_t - 0.4, 845, H - 620)],
                       banner=True, phase=0.2))
        ssm = banner_sprite("史思明", "YAN_AN", 150)
        A.append(Actor("B_shi", ssm, [(0.0, 1510, H - 550), (sa + 0.4, 1510, H - 550), (sm, 1415, H - 540), (cturn, 1415, H - 540),
                                      (ck[1], 1695, H - 530), (end_t - 0.2, 1745, H - 520)],
                       banner=True, fade=(ck[1] + 0.1, end_t - 0.1), phase=1.1))
        self.events.append((cturn + 0.30, "gong_retreat", 1550))
        self.actors = A


# ----------------------------------------------------------------------------- B11 睢阳保卫战
DEFAULT_B11_CUES = {
    "arrows_done": 1.65,
    "siege_press": 0.90,
    "defender_volley": 2.35,
    "volley_kill": 2.72,
    "sally_kill": 4.10,
    "reinforce_assault": 5.55,
    "breach_smoke": 6.60,
    "wall_deaths": [7.55, 8.20, 8.85],
    "banner_fall": 9.45,
    "arrows_dim_at": 1.95,
    "arrows_restore_at": 9.65,
    "action_end": 10.30,
}


class B11Animator(BattleAnimatorBase):
    """睢阳保卫战：尹子奇重围强攻 → 城头箭雨射杀先登、张巡突击砍杀 → 绝粮破门、血战殉城帅旗倒下。"""
    BID = "B11"
    ACTION_END = 10.30

    def __init__(self, arrow_renderer=None, cues=None):
        super().__init__(arrow_renderer=arrow_renderer, cues=cues, default_cues=DEFAULT_B11_CUES)

    def _build_cast(self):
        tang_inf_l = unit_sprite("TANG", "infantry", True)
        yan_inf_r = unit_sprite("YAN_AN", "infantry", False)
        yan_cav_r = unit_sprite("YAN_AN", "cavalry", False)
        A = []
        c = self.cues

        T = group_slots(960, 620, 3, tang_inf_l.width)   # 睢阳守军 (T1, T2 城头；T0 守地面西门，均朝左)
        Y = group_slots(480, 540, 5, yan_inf_r.width)    # 尹子奇攻城步骑 (步兵登云梯，骑兵待破门后由地面进城)

        sp = float(c["siege_press"])
        vt = float(c["defender_volley"])
        vk = float(c["volley_kill"])
        sk = float(c["sally_kill"])
        ra = float(c["reinforce_assault"])
        sm = float(c["breach_smoke"])
        wd = list(c["wall_deaths"])
        bf = float(c["banner_fall"])
        end_t = float(c["action_end"])

        # 1) 两架木制攻城云梯斜架西城墙 + 城头箭雨射落先登步兵 YI2
        self.fx.append(("ladder", sp + 0.35, (798, 572), (868, 492)))
        self.fx.append(("ladder", max(sp + 0.50, ra - 0.10), (806, 595), (885, 492)))

        self.fx.append(("volley", vt, (875, 492), (842, 524)))
        self.events.append((vt, "volley", 855))
        A.append(Actor("YI2", yan_inf_r, [(0.0,) + Y[4], (sp,) + Y[4], (vt - 0.10, 798, 572), (vk - 0.05, 842, 524)],
                       kind="inf", face_left=False, die_t=vk, fall_dir=1, phase=0.8))
        self.fx.append(("blood", vk, (840, 496), -1, 601))
        self.events.append((vk, "death", 842))

        # 2) YI1 逼至西门外地面，T0 守将由地面西门洞出击斩杀 YI1 后退守门内
        A.append(Actor("YI1", yan_inf_r, [(0.0,) + Y[3], (sp + 0.12,) + Y[3], (vk + 0.35, 725, 588), (sk, 725, 588)],
                       kind="inf", face_left=False, die_t=sk + 0.06, fall_dir=1, phase=1.4))
        self.fx += [("slash", sk, (752, 558), True), ("blood", sk + 0.06, (722, 558), -1, 602)]
        self.events += [(sk, "slash", 775), (sk + 0.06, "death", 725)]

        t0_gate = (900, 588)
        A.append(Actor("T0", tang_inf_l, [(0.0,) + t0_gate, (vk + 0.25,) + t0_gate, (sk - 0.55, 818, 588), (sk - 0.02, 775, 588),
                                          (sk + 0.68, 825, 588), (sm - 0.10, 882, 588), (wd[0], 905, 588)],
                       face_left=True, slashes=[sk], die_t=wd[0] + 0.06, fall_dir=-1, gait=1.18, phase=0.2))

        # 3) 西门城门爆破浓烟（仅破门洞后，骑兵 YC0, YC1 从地面城门洞突入内院；步兵 YI0 顺云梯登城墙斩 T1, T2）
        self.fx.append(("smoke", sm, (820, 582), 1.30))
        self.fx.append(("smoke", sm + 0.25, (842, 566), 0.95))
        self.events.append((sm, "breach_blast", 828))

        # 骑兵 YC0 待城门破开后，经地面门洞突入内庭砍倒 T0（不上城头！）
        A.append(Actor("YC0", yan_cav_r, [(0.0,) + Y[2], (sp + 0.25,) + Y[2], (sk, 650, 588), (ra, 625, 588),
                                          (sm, 785, 588), (wd[0] - 0.02, 855, 588), (wd[0] + 0.75, 935, 592)],
                       kind="cav", face_left=False, slashes=[wd[0]], phase=0.5))
        self.fx += [("slash", wd[0], (878, 558), False), ("blood", wd[0] + 0.06, (905, 558), 1, 610)]
        self.events += [(wd[0], "slash", 855), (wd[0] + 0.06, "death", 905)]

        # 骑兵 YC1 随后穿过破开的城门洞进入地面内庭横扫，始终保持在地面 y≈598
        A.append(Actor("YC1", yan_cav_r, [(0.0,) + Y[1], (ra,) + Y[1], (sm + 0.15, 760, 596), (wd[0] + 0.35, 865, 598), (end_t - 0.3, 955, 598)],
                       kind="cav", face_left=False, gait=1.16, phase=1.7))

        # 城头守将 T1, T2：由攻城步兵 YI0 攀爬第二架云梯登城墙连斩
        A.append(Actor("T1", tang_inf_l, [(0.0,) + T[1], (wd[1], T[1][0], T[1][1])],
                       face_left=True, die_t=wd[1] + 0.06, fall_dir=-1, phase=1.1))
        y0_w1_x, y0_w1_y = T[1][0] - 48, T[1][1]
        t2_end = (1035, 492)
        A.append(Actor("T2", tang_inf_l, [(0.0,) + T[2], (wd[1] - 0.15,) + T[2], (wd[2], t2_end[0], t2_end[1])],
                       face_left=True, turn_t=wd[1] + 0.05, die_t=wd[2] + 0.06, fall_dir=-1, gait=1.1, phase=2.2))
        y0_w2_x, y0_w2_y = t2_end[0] - 48, t2_end[1]

        A.append(Actor("YI0", yan_inf_r, [(0.0,) + Y[0], (ra,) + Y[0], (sm - 0.25, 806, 595), (wd[1] - 0.25, 885, 490),
                                          (wd[1] - 0.02, y0_w1_x, y0_w1_y), (wd[2] - 0.02, y0_w2_x, y0_w2_y),
                                          (end_t - 0.25, y0_w2_x + 15, y0_w2_y + 6)],
                       kind="inf", face_left=False, slashes=[wd[1], wd[2]], gait=1.18, phase=2.6))
        self.fx += [("slash", wd[1], (y0_w1_x + 20, y0_w1_y - 30), False), ("blood", wd[1] + 0.06, (T[1][0] - 4, T[1][1] - 28), 1, 611),
                    ("slash", wd[2], (y0_w2_x + 20, y0_w2_y - 30), False), ("blood", wd[2] + 0.06, (t2_end[0] - 4, t2_end[1] - 28), 1, 612)]
        self.events += [(wd[1], "slash", y0_w1_x), (wd[1] + 0.06, "death", T[1][0]),
                        (wd[2], "slash", y0_w2_x), (wd[2] + 0.06, "death", t2_end[0])]

        # 4) 帅旗：尹子奇合围进逼（停在箭矢西侧以免遮挡文字）；张巡城破殉国、帅旗倒下
        yzq = banner_sprite("尹子奇", "YAN_AN", 150)
        A.append(Actor("B_yin", yzq, [(0.0, 360, H - 540), (ra, 440, H - 540), (sm + 0.4, 515, H - 525), (bf, 540, H - 525)],
                       banner=True, phase=0.6))
        zx = banner_sprite("张巡", "TANG", 150)
        A.append(Actor("B_zhang", zx, [(0.0, 1095, H - 610)], banner=True, die_t=bf, fall_dir=-1))
        self.events.append((bf, "banner_fall", 1095))
        self.actors = A


# ----------------------------------------------------------------------------- B13 香积寺决战与收复长安
DEFAULT_B13_CUES = {
    "arrows_done": 1.80,
    "clash_start": 0.90,
    "modao_hold": 2.95,
    "east_ambush_kills": [4.25, 4.88, 5.50],
    "pincer_swing": 6.10,
    "modao_kills": [7.25, 7.85],
    "rout_turn": 8.20,
    "chase_kills": [9.25, 10.05, 10.85],
    "arrows_dim_at": 2.15,
    "arrows_restore_at": 11.00,
    "action_end": 11.80,
}


class B13Animator(BattleAnimatorBase):
    """香积寺决战：安守忠骑冲击 → 李嗣业陌刀稳阵、回纥破东原伏兵后绕袭阵后 → 南北夹击溃追燕军。"""
    BID = "B13"
    ACTION_END = 11.80

    def __init__(self, arrow_renderer=None, cues=None):
        super().__init__(arrow_renderer=arrow_renderer, cues=cues, default_cues=DEFAULT_B13_CUES)

    def _build_cast(self):
        yan_cav_l = unit_sprite("YAN_AN", "cavalry", True)
        tang_hvy_r = unit_sprite("TANG", "heavy_inf", False)
        tang_mix_r = unit_sprite("TANG", "mixed", False)
        uyg_cav_l = unit_sprite("UYGHUR", "cavalry", True)
        A = []
        c = self.cues

        YM = group_slots(845, 735, 5, yan_cav_l.width)    # 安守忠主力骑兵 (北，朝左)
        TM = group_slots(845, 450, 5, tang_hvy_r.width)   # 李嗣业陌刀前军 (中南，朝右)
        TG = group_slots(500, 445, 4, tang_mix_r.width)   # 郭子仪左翼 (西南，朝右)
        YA = group_slots(1470, 650, 3, yan_cav_l.width)   # 东原伏兵 (东北，朝左)
        U = group_slots(1470, 340, 4, uyg_cav_l.width)    # 回纥叶护铁骑 (东南，朝左)

        cs = float(c["clash_start"])
        mh = float(c["modao_hold"])
        ek = list(c["east_ambush_kills"])
        ps = float(c["pincer_swing"])
        mk = list(c["modao_kills"])
        rt = float(c["rout_turn"])
        ck = list(c["chase_kills"])
        end_t = float(c["action_end"])

        # 1) 东原伏兵战：回纥铁骑北上击破 YA0, YA1，追斩逃兵 YA2
        ya_tgt = [(YA[0][0], YA[0][1]), (YA[1][0], YA[1][1]), (1295, 395)]
        for i in range(2):
            vx, vy = ya_tgt[i]
            hx, hy = vx + 46, vy + 10
            A.append(Actor(f"YA{i}", yan_cav_l, [(0.0, vx, vy), (ek[i], vx, vy)],
                           kind="cav", face_left=True, die_t=ek[i] + 0.06, fall_dir=1, phase=i * 0.7))
            self.fx += [("slash", ek[i], (hx - 20, hy - 30), True), ("blood", ek[i] + 0.06, (vx - 4, vy - 28), -1, 700 + i)]
            self.events += [(ek[i], "slash", hx), (ek[i] + 0.06, "death", vx)]

        # YA2 向西北遁逃被 U2 追斩
        ya2_end = ya_tgt[2]
        A.append(Actor("YA2", yan_cav_l, [(0.0,) + YA[2], (ek[1] - 0.1,) + YA[2], (ek[2] + 0.05,) + ya2_end],
                       kind="cav", face_left=True, die_t=ek[2] + 0.06, fall_dir=1, gait=1.22, phase=1.9))
        self.fx += [("slash", ek[2], (ya2_end[0] + 24, ya2_end[1] - 26), True),
                    ("blood", ek[2] + 0.06, (ya2_end[0] - 4, ya2_end[1] - 28), -1, 702)]
        self.events += [(ek[2], "slash", ya2_end[0] + 46), (ek[2] + 0.06, "death", ya2_end[0])]

        # 2) 正面锋线：李嗣业陌刀壁立稳住阵脚，随后大进斩杀 YM0, YM1
        # 先让 YM 南压，TM 北进稳阵（mh 时刻刀光火花稳住阵线）
        self.fx.append(("slash", mh, (840, 520), False))
        self.events.append((mh, "slash", 840))

        ym0_end = (760, 495)
        A.append(Actor("YM0", yan_cav_l, [(0.0,) + YM[0], (cs,) + YM[0], (mh, 775, 505), (mk[0],) + ym0_end],
                       kind="cav", face_left=True, die_t=mk[0] + 0.06, fall_dir=1, phase=0.2))
        self.fx += [("slash", mk[0], (ym0_end[0] - 20, ym0_end[1] - 28), False),
                    ("blood", mk[0] + 0.06, (ym0_end[0] + 4, ym0_end[1] - 28), 1, 710)]
        self.events += [(mk[0], "slash", ym0_end[0] - 42), (mk[0] + 0.06, "death", ym0_end[0])]

        ym1_end = (845, 480)
        A.append(Actor("YM1", yan_cav_l, [(0.0,) + YM[1], (cs + 0.1,) + YM[1], (mh + 0.08, 845, 500), (mk[1],) + ym1_end],
                       kind="cav", face_left=True, die_t=mk[1] + 0.06, fall_dir=1, phase=0.9))
        self.fx += [("slash", mk[1], (ym1_end[0] - 20, ym1_end[1] - 28), False),
                    ("blood", mk[1] + 0.06, (ym1_end[0] + 4, ym1_end[1] - 28), 1, 711)]
        self.events += [(mk[1], "slash", ym1_end[0] - 42), (mk[1] + 0.06, "death", ym1_end[0])]

        # 李嗣业陌刀阵 TM0..TM4 北进协同合围
        A.append(Actor("TM0", tang_hvy_r, [(0.0,) + TM[0], (cs + 0.3,) + TM[0], (mh, 765, 578), (mk[0] - 0.1, 725, 515), (end_t - 0.4, 725, 440)],
                       phase=0.1))
        A.append(Actor("TM1", tang_hvy_r, [(0.0,) + TM[1], (cs + 0.3,) + TM[1], (mh, 800, 574), (mk[0] - 0.02, ym0_end[0] - 44, ym0_end[1] + 4),
                                           (end_t - 0.4, 775, 415)],
                       slashes=[mh, mk[0]], phase=0.8))
        A.append(Actor("TM2", tang_hvy_r, [(0.0,) + TM[2], (cs + 0.3,) + TM[2], (mh, 845, 568), (mk[1] - 0.02, ym1_end[0] - 44, ym1_end[1] + 4),
                                           (end_t - 0.4, 845, 395)],
                       slashes=[mk[1]], phase=1.5))
        A.append(Actor("TM3", tang_hvy_r, [(0.0,) + TM[3], (cs + 0.3,) + TM[3], (mh, 895, 576), (mk[1], 905, 510), (end_t - 0.4, 910, 410)],
                       phase=2.1))
        A.append(Actor("TM4", tang_hvy_r, [(0.0,) + TM[4], (cs + 0.3,) + TM[4], (mh, 945, 582), (mk[1], 955, 515), (end_t - 0.4, 965, 425)],
                       phase=2.8))

        # 3) 溃败与三路追砍：YM2, YM3, YM4 向西北溃逃，遭回纥铁骑 U0, U1 与郭子仪右哨 TG3 追杀倒地
        ym2_end = (670, 280)
        A.append(Actor("YM2", yan_cav_l, [(0.0,) + YM[2], (cs + 0.15,) + YM[2], (mh, 865, 465), (rt, 865, 445),
                                          (0.5 * (rt + ck[0]), 765, 355), (ck[0] + 0.05,) + ym2_end],
                       kind="cav", face_left=True, die_t=ck[0] + 0.06, fall_dir=1, gait=1.28, phase=1.4))
        ym3_end = (545, 225)
        A.append(Actor("YM3", yan_cav_l, [(0.0,) + YM[3], (cs + 0.22,) + YM[3], (mh, 915, 452), (rt, 900, 410),
                                          (0.5 * (rt + ck[1]), 710, 305), (ck[1] + 0.05,) + ym3_end],
                       kind="cav", face_left=True, die_t=ck[1] + 0.06, fall_dir=1, gait=1.30, phase=2.0))
        ym4_end = (470, 345)
        A.append(Actor("YM4", yan_cav_l, [(0.0,) + YM[4], (cs + 0.28,) + YM[4], (mh, 955, 470), (rt + 0.08, 865, 435),
                                          (0.5 * (rt + ck[2]), 655, 385), (ck[2] + 0.05,) + ym4_end],
                       kind="cav", face_left=True, die_t=ck[2] + 0.06, fall_dir=1, gait=1.25, phase=2.5))

        # 回纥铁骑 U0..U3 破东原伏兵后西绕合围追斩 YM2, YM3
        u0_hx, u0_hy = ym2_end[0] + 50, ym2_end[1] + 4
        A.append(Actor("U0", uyg_cav_l, [(0.0,) + U[0], (ek[0] - 0.85, 1410, 560), (ek[0] - 0.02, YA[0][0] + 46, YA[0][1] + 10),
                                         (ps, 1185, 318), (rt, 990, 355), (ck[0] - 0.02, u0_hx, u0_hy),
                                         (ck[0] + 0.65, u0_hx - 58, u0_hy - 18), (end_t - 0.2, 575, 255)],
                       kind="cav", face_left=True, slashes=[ek[0], ck[0]], gait=1.25, phase=0.2))
        self.fx += [("slash", ck[0], (u0_hx - 22, u0_hy - 30), True), ("blood", ck[0] + 0.06, (ym2_end[0] - 4, ym2_end[1] - 28), -1, 720)]
        self.events += [(ck[0], "slash", u0_hx), (ck[0] + 0.06, "death", ym2_end[0])]

        u1_hx, u1_hy = ym3_end[0] + 50, ym3_end[1] + 4
        A.append(Actor("U1", uyg_cav_l, [(0.0,) + U[1], (ek[1] - 0.85, 1465, 575), (ek[1] - 0.02, YA[1][0] + 46, YA[1][1] + 10),
                                         (ps + 0.15, 1220, 305), (rt + 0.15, 965, 325), (ck[1] - 0.02, u1_hx, u1_hy),
                                         (ck[1] + 0.65, u1_hx - 55, u1_hy - 12), (end_t - 0.2, 470, 215)],
                       kind="cav", face_left=True, slashes=[ek[1], ck[1]], gait=1.28, phase=0.9))
        self.fx += [("slash", ck[1], (u1_hx - 22, u1_hy - 30), True), ("blood", ck[1] + 0.06, (ym3_end[0] - 4, ym3_end[1] - 28), -1, 721)]
        self.events += [(ck[1], "slash", u1_hx), (ck[1] + 0.06, "death", ym3_end[0])]

        A.append(Actor("U2", uyg_cav_l, [(0.0,) + U[2], (ek[1], 1495, 540), (ek[2] - 0.02, ya2_end[0] + 46, ya2_end[1] + 8),
                                         (ps + 0.3, 1140, 340), (end_t - 0.3, 895, 345)],
                       kind="cav", face_left=True, slashes=[ek[2]], gait=1.20, phase=1.6))
        A.append(Actor("U3", uyg_cav_l, [(0.0,) + U[3], (ek[1] + 0.2, 1525, 550), (ps + 0.35, 1280, 350), (end_t - 0.3, 985, 375)],
                       kind="cav", face_left=True, gait=1.18, phase=2.3))

        # 郭子仪左翼推进，TG3 转向西北追砍 YM4 倒地
        for i in range(3):
            A.append(Actor(f"TG{i}", tang_mix_r, [(0.0,) + TG[i], (mh, TG[i][0] + 55, TG[i][1] - 55), (mk[1], TG[i][0] + 150, TG[i][1] - 135),
                                                  (end_t - 0.3, TG[i][0] + 205, TG[i][1] - 195)],
                           kind="cav", face_left=False, phase=i * 0.7))
        tg3_hx, tg3_hy = ym4_end[0] + 50, ym4_end[1] + 4
        A.append(Actor("TG3", tang_mix_r, [(0.0,) + TG[3], (mh, 615, 595), (rt, 695, 480),
                                           (ck[2] - 0.02, tg3_hx, tg3_hy), (ck[2] + 0.65, tg3_hx - 54, tg3_hy - 18), (end_t - 0.2, 415, 330)],
                       kind="cav", face_left=False, turn_t=rt + 0.12, slashes=[ck[2]], gait=1.24, phase=2.8))
        self.fx += [("slash", ck[2], (tg3_hx - 22, tg3_hy - 30), True), ("blood", ck[2] + 0.06, (ym4_end[0] - 4, ym4_end[1] - 28), -1, 722)]
        self.events += [(ck[2], "slash", tg3_hx), (ck[2] + 0.06, "death", ym4_end[0])]

        # 4) 帅旗：安守忠帅旗西北溃遁，三路唐回大纛合围胜局
        az = banner_sprite("安守忠", "YAN_AN", 148)
        A.append(Actor("B_an", az, [(0.0, 640, H - 750), (rt, 640, H - 750), (ck[1], 450, 265), (end_t - 0.2, 315, 210)],
                       banner=True, fade=(ck[1] + 0.1, end_t - 0.2), phase=0.5))
        self.events.append((rt + 0.30, "gong_retreat", 620))

        lsy = banner_sprite("李嗣业", "TANG", 148)
        A.append(Actor("B_li", lsy, [(0.0, 1045, H - 455), (mh, 1045, H - 455), (mk[1], 1035, 535), (end_t - 0.4, 1015, 445)],
                       banner=True, phase=0.2))
        gzy = banner_sprite("郭子仪", "TANG", 144)
        A.append(Actor("B_guo", gzy, [(0.0, 375, H - 455), (mh, 445, 580), (end_t - 0.4, 575, 470)],
                       banner=True, phase=1.0))
        uy = banner_sprite("回纥叶护", "UYGHUR", 148)
        A.append(Actor("B_uy", uy, [(0.0, 1640, H - 340), (ek[0], 1620, 560), (ps, 1520, 445), (end_t - 0.4, 1280, 470)],
                       banner=True, phase=1.7))
        self.actors = A


# ----------------------------------------------------------------------------- B15 相州（邺城）九节度之溃
DEFAULT_B15_CUES = {
    "arrows_done": 1.45,
    "siege_press": 0.65,
    "volley": 1.65,
    "raid_smoke": 2.35,
    "front_kills": [3.25, 4.10, 4.95],
    "chase_turn": 5.30,
    "chase_kills": [6.15, 7.15],
    "arrows_dim_at": 1.65,
    "arrows_restore_at": 7.50,
    "action_end": 8.40,
}


class B15Animator(BattleAnimatorBase):
    """相州（邺城）九节度之溃：唐军久围城下 → 史思明截粮道纵火伴狂风骤起 → 正面击溃与西南追砍逃卒。"""
    BID = "B15"
    ACTION_END = 8.40

    def __init__(self, arrow_renderer=None, cues=None):
        super().__init__(arrow_renderer=arrow_renderer, cues=cues, default_cues=DEFAULT_B15_CUES)

    def _build_cast(self):
        tang_mix_r = unit_sprite("TANG", "mixed", False)
        yan_an_l = unit_sprite("YAN_AN", "infantry", True)
        yan_shi_l = unit_sprite("YAN_SHI", "cavalry", True)
        A = []
        c = self.cues

        T = group_slots(600, 350, 5, tang_mix_r.width)      # 郭子仪九节度官军 (左下，朝右)
        YA = group_slots(950, 585, 3, yan_an_l.width)       # 安庆绪邺城守军
        YS = group_slots(1440, 640, 5, yan_shi_l.width)     # 史思明精骑 (右上，朝左)

        sp = float(c["siege_press"])
        vt = float(c["volley"])
        rs = float(c["raid_smoke"])
        fk = list(c["front_kills"])
        cturn = float(c["chase_turn"])
        ck = list(c["chase_kills"])
        end_t = float(c["action_end"])

        # 1) 守军城墙阻击箭雨 + 史思明截粮道狂风烟火
        self.fx.append(("volley", vt, (925, 535), (765, 680)))
        self.events.append((vt, "volley", 845))
        self.fx.append(("smoke", rs, (1170, 610), 1.25))
        self.fx.append(("smoke", rs + 0.22, (865, 675), 1.05))
        self.events.append((rs, "breach_blast", 1020))

        # YA 城内守军象征性前压南门
        for i in range(3):
            A.append(Actor(f"YA{i}", yan_an_l, [(0.0,) + YA[i], (rs,) + YA[i], (fk[1], YA[i][0] - 24, YA[i][1] + 56), (end_t, YA[i][0] - 34, YA[i][1] + 68)],
                           face_left=True, phase=i * 0.6))

        # 2) YS0, YS1, YS2 疾驰突袭并连斩唐前军 T4, T3, T2
        t_pos = [(675, 735), (705, 725), (725, 750), (775, 720), (825, 700)]
        for ys_i, ti, ts in [(0, 4, fk[0]), (1, 3, fk[1]), (2, 2, fk[2])]:
            vx, vy = t_pos[ti]
            hx, hy = vx + 52, vy - 2
            A.append(Actor(f"YS{ys_i}", yan_shi_l, [(0.0,) + YS[ys_i], (rs - 0.15, 1185 + ys_i * 35, 560 + ys_i * 15),
                                                    (ts - 0.04, hx, hy), (ts + 0.60, hx - 48, hy + 18), (end_t - 0.2, 610 - ys_i * 25, 760 + ys_i * 14)],
                           kind="cav", face_left=True, slashes=[ts], gait=1.24, phase=ys_i * 0.7))
            A.append(Actor(f"T{ti}", tang_mix_r, [(0.0,) + T[ti], (sp,) + T[ti], (vt, vx, vy), (ts, vx - 4, vy)],
                           kind="cav", face_left=False, die_t=ts + 0.06, fall_dir=1, phase=ti))
            self.fx += [("slash", ts, (hx - 22, hy - 30), True), ("blood", ts + 0.06, (vx + 4, vy - 28), -1, 800 + ti)]
            self.events += [(ts, "slash", hx), (ts + 0.06, "death", vx)]

        # 3) 唐余部 T1, T0 转身西南溃退，遭 YS3, YS4 追砍倒地
        t1_end = (415, 775)
        A.append(Actor("T1", tang_mix_r, [(0.0,) + T[1], (sp,) + T[1], (vt, t_pos[1][0], t_pos[1][1]), (cturn, t_pos[1][0], t_pos[1][1]),
                                          (0.5 * (cturn + ck[0]), 550, 752), (ck[0] + 0.05,) + t1_end],
                       kind="cav", face_left=False, turn_t=cturn, die_t=ck[0] + 0.06, fall_dir=1, gait=1.25, phase=0.8))
        hx3, hy3 = t1_end[0] + 52, t1_end[1] - 2
        A.append(Actor("YS3", yan_shi_l, [(0.0,) + YS[3], (rs, 1250, 595), (cturn, 920, 690), (ck[0] - 0.02, hx3, hy3),
                                          (ck[0] + 0.65, hx3 - 55, hy3 + 12), (end_t - 0.2, 310, 795)],
                       kind="cav", face_left=True, slashes=[ck[0]], gait=1.28, phase=1.4))
        self.fx += [("slash", ck[0], (hx3 - 22, hy3 - 30), True), ("blood", ck[0] + 0.06, (t1_end[0] + 4, t1_end[1] - 28), -1, 811)]
        self.events += [(ck[0], "slash", hx3), (ck[0] + 0.06, "death", t1_end[0])]

        t0_end = (315, 815)
        t0_turn = cturn + 0.08
        A.append(Actor("T0", tang_mix_r, [(0.0,) + T[0], (sp,) + T[0], (vt, t_pos[0][0], t_pos[0][1]), (t0_turn, t_pos[0][0], t_pos[0][1]),
                                          (0.5 * (t0_turn + ck[1]), 485, 780), (ck[1] + 0.05,) + t0_end],
                       kind="cav", face_left=False, turn_t=t0_turn, die_t=ck[1] + 0.06, fall_dir=1, gait=1.28, phase=1.6))
        hx4, hy4 = t0_end[0] + 52, t0_end[1] - 2
        A.append(Actor("YS4", yan_shi_l, [(0.0,) + YS[4], (rs + 0.1, 1300, 615), (cturn + 0.1, 860, 725), (ck[1] - 0.02, hx4, hy4),
                                          (ck[1] + 0.60, hx4 - 48, hy4 + 10), (end_t - 0.2, 230, 830)],
                       kind="cav", face_left=True, slashes=[ck[1]], gait=1.26, phase=2.1))
        self.fx += [("slash", ck[1], (hx4 - 22, hy4 - 30), True), ("blood", ck[1] + 0.06, (t0_end[0] + 4, t0_end[1] - 28), -1, 812)]
        self.events += [(ck[1], "slash", hx4), (ck[1] + 0.06, "death", t0_end[0])]

        # 4) 帅旗：郭子仪旗西南溃撤；史思明旗压抵相州胜势
        gzy = banner_sprite("郭子仪", "TANG", 145)
        A.append(Actor("B_guo", gzy, [(0.0, 450, H - 360), (cturn - 0.1, 450, H - 360), (ck[1], 235, 825), (end_t - 0.1, 165, 845)],
                       banner=True, fade=(ck[0] + 0.2, end_t - 0.15), phase=0.4))
        self.events.append((cturn + 0.25, "gong_retreat", 420))
        ssm = banner_sprite("史思明", "YAN_SHI", 150)
        A.append(Actor("B_shi", ssm, [(0.0, 1590, H - 650), (rs, 1410, 480), (ck[0], 1245, 515), (end_t - 0.3, 1185, 525)],
                       banner=True, phase=1.2))
        self.actors = A


# ----------------------------------------------------------------------------- B16 河阳三城保卫战
DEFAULT_B16_CUES = {
    "arrows_done": 1.45,
    "siege_press": 0.65,
    "volley": 1.85,
    "front_kills": [3.35, 4.15, 5.05],
    "chase_turn": 5.45,
    "chase_kills": [6.45, 7.45],
    "arrows_dim_at": 1.75,
    "arrows_restore_at": 7.75,
    "action_end": 8.55,
}


class B16Animator(BattleAnimatorBase):
    """河阳三城保卫战：史思明南岸进逼 → 中潬城头箭雨阻敌，李光弼渡黄河浮桥出击连斩并东追溃敌。"""
    BID = "B16"
    ACTION_END = 8.55

    def __init__(self, arrow_renderer=None, cues=None):
        super().__init__(arrow_renderer=arrow_renderer, cues=cues, default_cues=DEFAULT_B16_CUES)

    def _build_cast(self):
        tang_mix_r = unit_sprite("TANG", "mixed", False)
        yan_shi_l = unit_sprite("YAN_SHI", "cavalry", True)
        A = []
        c = self.cues

        T = group_slots(960, 820, 4, tang_mix_r.width)      # 李光弼北城官军 (上，朝右)
        YS = group_slots(1440, 335, 5, yan_shi_l.width)     # 史思明南岸骑兵 (下右，朝左)

        sp = float(c["siege_press"])
        vt = float(c["volley"])
        fk = list(c["front_kills"])
        cturn = float(c["chase_turn"])
        ck = list(c["chase_kills"])
        end_t = float(c["action_end"])

        # 1) 中潬城 / 南城矢雨阻滞史思明攻势
        self.fx.append(("volley", vt, (995, 560), (1165, 745)))
        self.events.append((vt, "volley", 1080))

        # 2) T0 走浮桥守住南城渡口，T3, T2, T1 严格经 x=1045 北浮桥->中潬岛->南浮桥渡河连斩 YS0, YS1, YS2
        A.append(Actor("T0", tang_mix_r, [(0.0,) + T[0], (0.60,) + T[0], (1.30, 1045, 455), (1.90, 1045, 545), (2.50, 1045, 650), (end_t, 1075, 695)],
                       kind="cav", face_left=False, phase=0.2))

        ys_tgt = [(1135, 735), (1195, 755), (1255, 772)]
        for idx, (vx, vy) in enumerate(ys_tgt):
            ts = fk[idx]
            A.append(Actor(f"YS{idx}", yan_shi_l, [(0.0,) + YS[idx], (sp + idx * 0.10,) + YS[idx], (vt + 0.1, vx, vy), (ts, vx + 4, vy)],
                           kind="cav", face_left=True, die_t=ts + 0.06, fall_dir=-1, phase=idx * 0.7))
            hx, hy = vx - 52, vy + 2
            ti = 3 - idx
            k_list = [(0.0,) + T[ti], (0.55 + idx * 0.12,) + T[ti], (1.15 + idx * 0.12, 1045, 455),
                      (1.75 + idx * 0.12, 1045, 545), (2.30 + idx * 0.12, 1045 + idx * 6, 635), (ts - 0.04, hx, hy)]
            if idx == 0:
                # T3 斩 YS0 后向东追斩 YS3
                ys3_end = (1535, 735)
                hx3, hy3 = ys3_end[0] - 52, ys3_end[1] + 2
                k_list += [(ts + 0.55, hx + 46, hy + 10), (cturn + 0.1, 1300, 740), (ck[0] - 0.02, hx3, hy3),
                           (ck[0] + 0.55, hx3 + 48, hy3 - 8), (end_t - 0.2, 1465, 730)]
                A.append(Actor("T3", tang_mix_r, k_list, kind="cav", face_left=False, slashes=[ts, ck[0]], gait=1.24, phase=0.5))
                self.fx += [("slash", ck[0], (hx3 + 22, hy3 - 30), False), ("blood", ck[0] + 0.06, (ys3_end[0] - 4, ys3_end[1] - 28), 1, 910)]
                self.events += [(ck[0], "slash", hx3), (ck[0] + 0.06, "death", ys3_end[0])]
            elif idx == 1:
                # T2 斩 YS1 后追斩 YS4
                ys4_end = (1625, 785)
                hx4, hy4 = ys4_end[0] - 52, ys4_end[1] + 2
                k_list += [(ts + 0.55, hx + 46, hy + 8), (cturn + 0.15, 1365, 770), (ck[1] - 0.02, hx4, hy4),
                           (ck[1] + 0.50, hx4 + 45, hy4 - 10), (end_t - 0.2, 1545, 775)]
                A.append(Actor("T2", tang_mix_r, k_list, kind="cav", face_left=False, slashes=[ts, ck[1]], gait=1.22, phase=1.2))
                self.fx += [("slash", ck[1], (hx4 + 22, hy4 - 30), False), ("blood", ck[1] + 0.06, (ys4_end[0] - 4, ys4_end[1] - 28), 1, 911)]
                self.events += [(ck[1], "slash", hx4), (ck[1] + 0.06, "death", ys4_end[0])]
            else:
                # T1 斩 YS2 后控扼南岸一线
                k_list += [(ts + 0.65, hx + 48, hy - 6), (end_t - 0.3, 1280, 755)]
                A.append(Actor("T1", tang_mix_r, k_list, kind="cav", face_left=False, slashes=[ts], gait=1.18, phase=1.9))
            self.fx += [("slash", ts, (hx + 22, hy - 30), False), ("blood", ts + 0.06, (vx - 4, vy - 28), 1, 900 + idx)]
            self.events += [(ts, "slash", hx), (ts + 0.06, "death", vx)]

        # 3) YS3, YS4 转身东溃遭追杀倒地
        A.append(Actor("YS3", yan_shi_l, [(0.0,) + YS[3], (sp + 0.25,) + YS[3], (vt, 1310, 745), (cturn, 1310, 745),
                                          (0.5 * (cturn + ck[0]), 1430, 738), (ck[0] + 0.05, 1535, 735)],
                       kind="cav", face_left=True, turn_t=cturn, die_t=ck[0] + 0.06, fall_dir=-1, gait=1.28, phase=0.8))
        y4_turn = cturn + 0.08
        A.append(Actor("YS4", yan_shi_l, [(0.0,) + YS[4], (sp + 0.35,) + YS[4], (vt, 1375, 775), (y4_turn, 1375, 775),
                                          (0.5 * (y4_turn + ck[1]), 1505, 780), (ck[1] + 0.05, 1625, 785)],
                       kind="cav", face_left=True, turn_t=y4_turn, die_t=ck[1] + 0.06, fall_dir=-1, gait=1.30, phase=1.5))

        # 4) 帅旗：李光弼镇守北城；史思明东溃退走
        lgb = banner_sprite("李光弼", "TANG", 150)
        A.append(Actor("B_li", lgb, [(0.0, 780, H - 825), (fk[0], 815, 265), (end_t - 0.3, 835, 275)], banner=True, phase=0.3))
        ssm = banner_sprite("史思明", "YAN_SHI", 150)
        A.append(Actor("B_shi", ssm, [(0.0, 1600, H - 345), (cturn, 1600, H - 345), (ck[1], 1765, 740), (end_t - 0.1, 1805, 745)],
                       banner=True, fade=(ck[0], end_t - 0.15), phase=1.1))
        self.events.append((cturn + 0.25, "gong_retreat", 1500))
        self.actors = A


# ----------------------------------------------------------------------------- B21 莫州—温泉栅平叛终局
DEFAULT_B21_CUES = {
    "arrows_done": 1.45,
    "pursuit_start": 0.60,
    "fanyang_volley": 1.90,
    "chase_kills": [3.85, 5.35, 6.85],
    "banner_fall": 7.75,
    "arrows_dim_at": 1.65,
    "arrows_restore_at": 7.90,
    "action_end": 8.65,
}


class B21Animator(BattleAnimatorBase):
    """莫州—温泉栅平叛终局：李怀仙范阳闭城箭拒 → 唐军自莫州疾追东进连斩史朝义余部 → 温泉栅帅旗倒下大乱平定。"""
    BID = "B21"
    ACTION_END = 8.65

    def __init__(self, arrow_renderer=None, cues=None):
        super().__init__(arrow_renderer=arrow_renderer, cues=cues, default_cues=DEFAULT_B21_CUES)

    def _build_cast(self):
        tang_mix_r = unit_sprite("TANG", "mixed", False)
        yan_shi_r = unit_sprite("YAN_SHI", "cavalry", False)
        A = []
        c = self.cues

        T = group_slots(360, 445, 4, tang_mix_r.width)      # 仆固瑒莫州北岸追击官军 (干爽北岸，全程不涉水)

        ps = float(c["pursuit_start"])
        vt = float(c["fanyang_volley"])
        ck = list(c["chase_kills"])
        bf = float(c["banner_fall"])
        end_t = float(c["action_end"])

        # 1) 范阳城头闭门拒纳箭雨
        self.fx.append(("volley", vt, (1190, 465), (1095, 515)))
        self.events.append((vt, "volley", 1145))

        # 2) 史朝义残部 YS0, YS1, YS2 自白沟北岸东溃，相继于范阳南、东道与温泉栅遭追斩倒地
        ys_starts = [(840, 555), (890, 540), (940, 560)]
        ys_ends = [(1065, 535), (1440, 470), (1615, 425)]

        A.append(Actor("YS0", yan_shi_r, [(0.0,) + ys_starts[0], (ps,) + ys_starts[0], (vt + 0.1, 980, 535), (ck[0] + 0.05,) + ys_ends[0]],
                       kind="cav", face_left=False, die_t=ck[0] + 0.06, fall_dir=-1, gait=1.25, phase=0.2))
        A.append(Actor("YS1", yan_shi_r, [(0.0,) + ys_starts[1], (ps,) + ys_starts[1], (vt + 0.1, 1085, 515), (ck[0], 1280, 495), (ck[1] + 0.05,) + ys_ends[1]],
                       kind="cav", face_left=False, die_t=ck[1] + 0.06, fall_dir=-1, gait=1.28, phase=0.9))
        A.append(Actor("YS2", yan_shi_r, [(0.0,) + ys_starts[2], (ps,) + ys_starts[2], (vt + 0.1, 1135, 520), (ck[1], 1435, 465), (ck[2] + 0.05,) + ys_ends[2]],
                       kind="cav", face_left=False, die_t=ck[2] + 0.06, fall_dir=-1, gait=1.30, phase=1.6))

        # 唐追兵 T3, T2, T1 全程沿白沟水系北岸干陆疾驰追砍
        for idx, ti, (vx, vy), ts in [(0, 3, ys_ends[0], ck[0]), (1, 2, ys_ends[1], ck[1]), (2, 1, ys_ends[2], ck[2])]:
            hx, hy = vx - 52, vy + 2
            k_list = [(0.0,) + T[ti], (ps + idx * 0.10,) + T[ti], (1.75 + idx * 0.15, 640 + idx * 35, 590 - idx * 12)]
            if idx >= 1:
                k_list.append((ck[0] + 0.15, 1110 + idx * 45, 520 - idx * 10))
            k_list += [(ts - 0.02, hx, hy), (ts + 0.58, hx + 48, hy - 10), (end_t - 0.25, vx + 15, vy - 18)]
            A.append(Actor(f"T{ti}", tang_mix_r, k_list, kind="cav", face_left=False, slashes=[ts], gait=1.26, phase=idx * 0.6))
            self.fx += [("slash", ts, (hx + 22, hy - 30), False), ("blood", ts + 0.06, (vx - 4, vy - 28), 1, 1000 + idx)]
            self.events += [(ts, "slash", hx), (ts + 0.06, "death", vx)]

        # T0 推进策应范阳以东防线（北岸陆路）
        A.append(Actor("T0", tang_mix_r, [(0.0,) + T[0], (ps + 0.25,) + T[0], (ck[0], 780, 560), (end_t - 0.3, 1255, 505)],
                       kind="cav", face_left=False, gait=1.18, phase=2.3))

        # 3) 帅旗：仆固瑒北岸东进、李怀仙踞守范阳、史朝义旗于温泉栅林中倒下
        pgc = banner_sprite("仆固瑒", "TANG", 145)
        A.append(Actor("B_pu", pgc, [(0.0, 450, H - 505), (ps, 450, H - 505), (ck[1], 880, 540), (end_t - 0.3, 1245, 505)], banner=True, phase=0.4))
        lhx = banner_sprite("李怀仙", "FANZHEN", 145)
        A.append(Actor("B_lhx", lhx, [(0.0, 1055, H - 620)], banner=True, phase=1.2))
        scy = banner_sprite("史朝义", "YAN_SHI", 145)
        A.append(Actor("B_shi_cy", scy, [(0.0, 1015, 520), (vt, 1210, 505), (ck[1], 1510, 465), (bf - 0.15, 1695, 435)],
                       banner=True, die_t=bf, fall_dir=-1, phase=1.7))
        self.events.append((bf, "banner_fall", 1695))
        self.actors = A
