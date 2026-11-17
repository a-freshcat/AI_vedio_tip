# -*- coding: utf-8 -*-
"""
src/hc_tactical.py
《唐末黄巢起义（874–884）》3D 立体地形多兵团战役沙盘动画引擎（1920×1080）
全面对标《安史之乱》battle_anim.py 高精度多兵团实时对抗标准：
- 每场战役双方均出动多列步兵/重步/骑兵/义军阵型（每方 8~14 个独立 Actor 算子），含真实脚步/奔马晃动、
  挥刀闪白冲刺、阵亡倒地变暗尸体留场、脚下扬尘、双向箭雨对射、多道刀光血花、破门烈火浓烟、主将帅旗倒塌；
- 攻城写实约束：步兵推架多架木制云梯登城与城头唐军守卒搏杀，骑兵必须等东门/关门攻破火起后方由地面冲入；
- 渡河写实约束：河道显式架设木浮桥渡口，大军与沙陀鸦军严禁无桥踏水穿河。
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from hc_terrain import compute_hillshade, ridged_multifractal_2d
from landmarks import make_landmark_sprite, make_war_banner
from sprites import make_sprite

W_PX, H_PX = 1920, 1080
UNIT_H = 62

FACTION_STYLE = {
    "TANG":   dict(color="#D63227", banner_bg="#C93326", banner_trim="#F7D348", arrow="#E03828", unit_c="#C0392B", unit_a="#F5B041"),
    "QI":     dict(color="#2B5B84", banner_bg="#2B5B84", banner_trim="#F6C226", arrow="#3B82C4", unit_c="#2E6499", unit_a="#F6C226"),
    "SHATUO": dict(color="#2A2D34", banner_bg="#242730", banner_trim="#CBD5E1", arrow="#384152", unit_c="#2A2E38", unit_a="#CBD5E1"),
}

PIL_BOLD_48 = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 48)
PIL_BOLD_36 = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 36)
PIL_BOLD_32 = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 32)
PIL_BOLD_28 = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 28)
PIL_BOLD_22 = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 22)


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else float(x))


def _smooth(x: float) -> float:
    x = _clamp01(x)
    return x * x * (3.0 - 2.0 * x)


def _ease_out(x: float) -> float:
    x = _clamp01(x)
    return 1.0 - (1.0 - x) ** 2.6


def _bump(u: float) -> float:
    return math.sin(math.pi * u) if 0.0 <= u <= 1.0 else 0.0


def _path_pos(keys: List[Tuple[float, float, float]], u: float) -> Tuple[float, float]:
    """keys = [(u, x, y), ...]"""
    if u <= keys[0][0]:
        return float(keys[0][1]), float(keys[0][2])
    if u >= keys[-1][0]:
        return float(keys[-1][1]), float(keys[-1][2])
    for i in range(len(keys) - 1):
        u0, x0, y0 = keys[i]
        u1, x1, y1 = keys[i + 1]
        if u0 <= u <= u1:
            f = (u - u0) / max(u1 - u0, 1e-6)
            if len(keys) == 2:
                f = _smooth(f)
            return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
    return float(keys[-1][1]), float(keys[-1][2])


def _tight_rgba(img: Image.Image, thresh: int = 32) -> Image.Image:
    a = np.asarray(img)[..., 3]
    ys, xs = np.where(a > thresh)
    if len(xs) == 0:
        return img
    return img.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))


def _pivot_canvas(img: Image.Image) -> Image.Image:
    w, h = img.size
    s = 2 * max(w, h) + 8
    c = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    c.paste(img, (s // 2 - w // 2, s // 2 - h), img)
    return c


def _tint(img: Image.Image, rgb: Tuple[int, int, int], k: float) -> Image.Image:
    if k <= 0.01:
        return img
    a = np.asarray(img, dtype=np.float32)
    a[..., :3] = a[..., :3] * (1.0 - k) + np.array(rgb, np.float32) * k
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def _darken(img: Image.Image, k: float) -> Image.Image:
    if k <= 0.01:
        return img
    a = np.asarray(img, dtype=np.float32)
    g = a[..., :3].mean(-1, keepdims=True)
    a[..., :3] = (a[..., :3] * (1.0 - 0.45 * k) + g * 0.45 * k) * (1.0 - 0.34 * k)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def _paste_safe(dst: Image.Image, src: Image.Image, x: float, y: float) -> None:
    x0, y0 = int(round(x)), int(round(y))
    sx0, sy0 = max(0, -x0), max(0, -y0)
    dx0, dy0 = max(0, x0), max(0, y0)
    w = min(src.width - sx0, dst.width - dx0)
    h = min(src.height - sy0, dst.height - dy0)
    if w > 0 and h > 0:
        dst.alpha_composite(src.crop((sx0, sy0, sx0 + w, sy0 + h)), dest=(dx0, dy0))


class Actor:
    """复刻 battle_anim.py 的高精多兵团独立算子：支持路径运动、冲刺劈砍、中刃闪白、倒地成尸、帅旗倒塌。"""
    def __init__(
        self, img: Image.Image, keys: List[Tuple[float, float, float]], *,
        kind: str = "inf", face_left: bool = False, die_u: float | None = None,
        fall_dir: int = 1, slashes: Tuple[float, ...] = (), phase: float = 0.0,
        banner: bool = False, fade_u: Tuple[float, float] | None = None,
    ):
        self.cv = {
            False: _pivot_canvas(img),
            True: _pivot_canvas(img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)),
        }
        self.w, self.h = img.size
        self.keys = keys
        self.kind = kind
        self.face_left = face_left
        self.die_u = die_u
        self.fall_dir = fall_dir
        self.slashes = list(slashes)
        self.phase = phase
        self.banner = banner
        self.fade_u = fade_u

    def pos(self, u: float) -> Tuple[float, float]:
        if self.die_u is not None and u > self.die_u:
            u = self.die_u
        return _path_pos(self.keys, u)

    def render(self, u: float, layer_corpses: Image.Image, layer_live: Image.Image, shadow_draw: ImageDraw.ImageDraw) -> None:
        al = 1.0
        if self.fade_u:
            al = 1.0 - _smooth((u - self.fade_u[0]) / max(1e-4, self.fade_u[1] - self.fade_u[0]))
            if al <= 0.02:
                return
        x, y = self.pos(u)
        dead = (self.die_u is not None and u >= self.die_u)
        cv = self.cv[False]
        ang, dx, dy, flash, dark = 0.0, 0.0, 0.0, 0.0, 0.0

        if dead:
            du = (u - self.die_u) / (0.06 if not self.banner else 0.09)
            a = _ease_out(du)
            ang = self.fall_dir * (84.0 if not self.banner else 78.0) * a
            dx = -self.fall_dir * 14.0 * a
            flash = max(0.0, 1.0 - (u - self.die_u) / 0.02) * 0.85
            dark = (0.28 if self.banner else 1.0) * _smooth((u - self.die_u - 0.02) / 0.08)
        else:
            x1, y1 = self.pos(max(0.0, u - 0.015))
            x2, y2 = self.pos(min(1.0, u + 0.015))
            mv = min(1.0, math.hypot(x2 - x1, y2 - y1) / 14.0)
            if self.kind == "cav":
                dy -= 4.2 * mv * abs(math.sin(2.0 * math.pi * 12.0 * u + self.phase))
                ang += 3.0 * mv * math.sin(2.0 * math.pi * 12.0 * u + self.phase)
            elif not self.banner:
                dy -= 3.2 * mv * abs(math.sin(2.0 * math.pi * 15.0 * u + self.phase))
                ang += 3.8 * mv * math.sin(2.0 * math.pi * 7.5 * u + self.phase)
            else:
                ang += 1.8 * math.sin(2.0 * math.pi * 5.0 * u + self.phase)
            fwd = -1.0 if self.face_left else 1.0
            for su in self.slashes:
                b = _bump((u - su + 0.015) / 0.05)
                dx += fwd * 14.0 * b
                ang += -fwd * 9.5 * b

        img = cv
        if abs(ang) > 0.05:
            img = img.rotate(ang, resample=Image.Resampling.BICUBIC)
        if flash > 0.0:
            img = _tint(img, (255, 240, 220), flash)
        if dark > 0.0:
            img = _darken(img, dark)
        if al < 0.99:
            arr = np.asarray(img).copy()
            arr[..., 3] = (arr[..., 3].astype(np.float32) * al).astype(np.uint8)
            img = Image.fromarray(arr, "RGBA")

        fx, fy = x + dx, y + dy
        if not dead:
            sw = self.w * (0.76 if not self.banner else 0.48)
            shadow_draw.ellipse([x + dx - sw / 2, y - 7, x + dx + sw / 2, y + 6], fill=(20, 17, 16, int(64 * al)))
            _paste_safe(layer_live, img, fx - img.width / 2, fy - img.height / 2)
        else:
            ln = self.h * 0.92
            cx = x + dx - self.fall_dir * ln * 0.42
            shadow_draw.ellipse([cx - ln / 2, y - 7, cx + ln / 2, y + 6], fill=(20, 17, 16, int(52 * al)))
            _paste_safe(layer_corpses, img, fx - img.width / 2, fy - img.height / 2)


def _draw_outlined_text(d: ImageDraw.ImageDraw, xy: Tuple[float, float], txt: str, font, fill, anchor="mm", sw=4):
    d.text(xy, txt, font=font, fill=fill, anchor=anchor, stroke_width=sw, stroke_fill=(14, 12, 10, 255))


def _draw_bilibili_hud(im: Image.Image, title_parts: List[Tuple[str, str]], bottom_subtitle: str) -> None:
    d = ImageDraw.Draw(im, "RGBA")
    # 顶部左对齐丝滑圆角底框（不拉通右侧，彻底让出辽东湾与渤海视野）
    widths = [d.textbbox((0, 0), txt, font=PIL_BOLD_48)[2] - d.textbbox((0, 0), txt, font=PIL_BOLD_48)[0] for txt, _ in title_parts]
    total_tw = sum(widths) + 4 * max(0, len(widths) - 1)
    d.rounded_rectangle([24, 12, 58 + total_tw + 38, 82], radius=12, fill=(12, 14, 20, 182), outline=(228, 178, 68, 145), width=2)
    x = 50
    for txt, col_hex in title_parts:
        rgb = tuple(int(col_hex.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
        _draw_outlined_text(d, (x, 47), txt, PIL_BOLD_48, rgb, anchor="lm", sw=5)
        bbox = d.textbbox((0, 0), txt, font=PIL_BOLD_48)
        x += (bbox[2] - bbox[0]) + 4
    if bottom_subtitle:
        d.rectangle([0, H_PX - 68, W_PX, H_PX], fill=(12, 14, 20, 182))
        _draw_outlined_text(d, (W_PX // 2, H_PX - 34), bottom_subtitle, PIL_BOLD_32, (255, 255, 255, 255), anchor="mm", sw=4)


def _build_tactical_terrain(
    seed: int,
    hill_blobs: List[Tuple[float, float, float, float, float]],
    river_poly: List[Tuple[float, float]] | None = None,
    bridges: List[Tuple[float, float, float, float]] | None = None,
) -> Image.Image:
    ys = np.linspace(0.0, H_PX, H_PX, dtype=np.float32)[:, None]
    xs = np.linspace(0.0, W_PX, W_PX, dtype=np.float32)[None, :]
    ridge = ridged_multifractal_2d(H_PX, W_PX, octaves=(26.0, 12.0, 5.5, 2.4), seed=seed)
    elev = 0.14 + 0.36 * ridge
    for bx, by, sx, sy, amp in hill_blobs:
        elev += amp * np.exp(-(((xs - bx) / sx) ** 2 + ((ys - by) / sy) ** 2))
    hs = compute_hillshade(elev, az_deg=315.0, alt_deg=39.0, z_scale=11.0)
    t = np.clip((elev - 0.1) / 1.1, 0.0, 1.0)
    rgb = np.zeros((H_PX, W_PX, 3), dtype=np.float32)
    rgb[..., 0] = (0.86 - 0.18 * t) * (0.56 + 0.60 * hs)
    rgb[..., 1] = (0.82 - 0.22 * t) * (0.56 + 0.60 * hs)
    rgb[..., 2] = (0.66 - 0.22 * t) * (0.56 + 0.60 * hs)
    im = Image.fromarray(np.clip(rgb * 255.0, 0, 255).astype(np.uint8), mode="RGB").convert("RGBA")

    d = ImageDraw.Draw(im, "RGBA")
    if river_poly:
        d.line(river_poly, fill=(22, 30, 36, 235), width=86, joint="curve")
        d.line(river_poly, fill=(84, 156, 206, 255), width=74, joint="curve")
        d.line(river_poly, fill=(138, 198, 236, 195), width=28, joint="curve")

    if bridges:
        for x0, y0, x1, y1 in bridges:
            dx, dy = x1 - x0, y1 - y0
            ln = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / ln * 18.0, dx / ln * 18.0
            d.polygon(
                [(x0 - nx, y0 - ny), (x1 - nx, y1 - ny), (x1 + nx, y1 + ny), (x0 + nx, y0 + ny)],
                fill=(136, 94, 52, 255), outline=(42, 28, 16, 255), width=3,
            )
            steps = max(4, int(ln // 20))
            for k in range(1, steps):
                f = k / steps
                px, py = x0 + dx * f, y0 + dy * f
                d.line([(px - nx * 0.85, py - ny * 0.85), (px + nx * 0.85, py + ny * 0.85)], fill=(68, 44, 24, 220), width=2)
    return im


def _draw_double_arrow(d: ImageDraw.ImageDraw, p0: Tuple[float, float], p1: Tuple[float, float], rad: float, color_hex: str, prog: float, sw: float = 12.0) -> None:
    prog = _clamp01(prog)
    if prog <= 0.03:
        return
    x1, y1 = p0
    x2, y2 = p1
    mx, my = 0.5 * (x1 + x2), 0.5 * (y1 + y2)
    ctrl = (mx - (y2 - y1) * rad, my + (x2 - x1) * rad)
    pts = [
        (
            (1 - t) ** 2 * x1 + 2 * (1 - t) * t * ctrl[0] + t ** 2 * x2,
            (1 - t) ** 2 * y1 + 2 * (1 - t) * t * ctrl[1] + t ** 2 * y2,
        )
        for t in np.linspace(0.0, prog, max(8, int(44 * prog)))
    ]
    if len(pts) < 2:
        return
    fill = tuple(int(color_hex.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    d.line(pts, fill=(18, 16, 14, 245), width=int(sw + 10), joint="curve")
    d.line(pts, fill=(252, 250, 244, 255), width=int(sw + 5), joint="curve")
    d.line(pts, fill=fill, width=int(sw), joint="curve")

    tx0, ty0 = pts[-2]
    tx1, ty1 = pts[-1]
    ang = math.atan2(ty1 - ty0, tx1 - tx0)
    sz = sw * 2.1
    tip = (tx1 + math.cos(ang) * 14, ty1 + math.sin(ang) * 14)
    p_l = (tx1 - math.cos(ang - 0.55) * sz, ty1 - math.sin(ang - 0.55) * sz)
    p_r = (tx1 - math.cos(ang + 0.55) * sz, ty1 - math.sin(ang + 0.55) * sz)
    d.polygon([tip, p_l, p_r], fill=fill, outline=(18, 16, 14, 255), width=3)


def _draw_siege_ladder(d: ImageDraw.ImageDraw, base: Tuple[float, float], top: Tuple[float, float], prog: float) -> None:
    prog = _clamp01(prog)
    if prog <= 0.02:
        return
    bx, by = base
    tx = bx + (top[0] - bx) * prog
    ty = by + (top[1] - by) * prog
    dx, dy = tx - bx, ty - by
    ln = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / ln * 9.0, dx / ln * 9.0
    for sgn in (-1.0, 1.0):
        d.line([(bx + sgn * nx, by + sgn * ny), (tx + sgn * nx, ty + sgn * ny)], fill=(38, 24, 14, 255), width=7)
        d.line([(bx + sgn * nx, by + sgn * ny), (tx + sgn * nx, ty + sgn * ny)], fill=(156, 108, 60, 255), width=4)
    rungs = max(2, int(ln // 18))
    for k in range(1, rungs):
        f = k / rungs
        rx, ry = bx + dx * f, by + dy * f
        d.line([(rx - nx, ry - ny), (rx + nx, ry + ny)], fill=(122, 80, 42, 255), width=3)


def _draw_volleys(d: ImageDraw.ImageDraw, p_src: Tuple[float, float], p_dst: Tuple[float, float], u: float, seed: int, count: int = 28) -> None:
    u = _clamp01(u)
    if u <= 0.0 or u >= 1.0:
        return
    rng = np.random.default_rng(seed)
    for _ in range(count):
        off_t = float(rng.uniform(-0.20, 0.20))
        loc = (u - 0.15) * 1.3 + off_t
        if loc < 0.0 or loc > 1.0:
            continue
        sx = p_src[0] + rng.uniform(-85, 85)
        sy = p_src[1] + rng.uniform(-55, 55)
        ex = p_dst[0] + rng.uniform(-95, 95)
        ey = p_dst[1] + rng.uniform(-65, 65)
        px = sx + (ex - sx) * loc
        py = sy + (ey - sy) * loc - math.sin(loc * math.pi) * 145.0
        px2 = sx + (ex - sx) * max(0.0, loc - 0.08)
        py2 = sy + (ey - sy) * max(0.0, loc - 0.08) - math.sin(max(0.0, loc - 0.08) * math.pi) * 145.0
        d.line([(px2, py2), (px, py)], fill=(255, 246, 210, 235), width=3)
        d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(224, 92, 42, 245))


def _draw_slash_and_blood(d: ImageDraw.ImageDraw, center: Tuple[float, float], u: float, seed: int) -> None:
    if u <= 0.0 or u >= 1.0:
        return
    cx, cy = center
    ang = -0.65 + u * 2.4
    p0 = (cx - math.cos(ang) * 48, cy - math.sin(ang) * 48)
    p1 = (cx + math.cos(ang) * 48, cy + math.sin(ang) * 48)
    d.line([p0, p1], fill=(252, 186, 62, 215), width=14)
    d.line([p0, p1], fill=(255, 254, 230, 250), width=6)
    rng = np.random.default_rng(seed + int(u * 25))
    for _ in range(7):
        ang_b = float(rng.uniform(0, 2 * math.pi))
        r_b = float(rng.uniform(8, 38)) * u
        bx = cx + math.cos(ang_b) * r_b
        by = cy + math.sin(ang_b) * r_b
        d.ellipse([bx - 4, by - 4, bx + 4, by + 4], fill=(178, 22, 26, 220))


def _draw_fire_smoke(d: ImageDraw.ImageDraw, center: Tuple[float, float], u: float, seed: int) -> None:
    u = _clamp01(u)
    if u <= 0.02:
        return
    rng = np.random.default_rng(seed + int(u * 45))
    cx, cy = center
    for _ in range(20):
        rx = cx + float(rng.uniform(-62, 62)) * (0.4 + 0.6 * u)
        ry = cy - float(rng.uniform(0, 145)) * u
        rr = float(rng.uniform(16, 46)) * (0.6 + 0.6 * u)
        d.ellipse([rx - rr, ry - rr, rx + rr, ry + rr], fill=(56, 52, 50, int(135 * (1.0 - 0.35 * u))))
    for _ in range(14):
        rx = cx + float(rng.uniform(-38, 38))
        ry = cy - float(rng.uniform(0, 64))
        rr = float(rng.uniform(8, 24))
        col = (248, 146, 36, 215) if rng.random() > 0.4 else (224, 66, 28, 200)
        d.ellipse([rx - rr, ry - rr, rx + rr, ry + rr], fill=col)


class HuangChaoTacticalRenderer:
    def __init__(self) -> None:
        self.unit_imgs: Dict[Tuple[str, str, bool], Image.Image] = {}
        for fac in ("TANG", "QI", "SHATUO"):
            st = FACTION_STYLE[fac]
            for ut in ("infantry", "cavalry", "heavy_inf", "militia"):
                for fl in (False, True):
                    raw = make_sprite(ut, st["unit_c"], st["unit_a"], flip=fl, size=(144, 116))
                    crop = _tight_rgba(raw, thresh=50)
                    cw, ch = crop.size
                    uw = max(24, int(round(cw * (UNIT_H / max(ch, 1)))))
                    self.unit_imgs[(fac, ut, fl)] = crop.resize((uw, UNIT_H), Image.Resampling.LANCZOS)

        def mk_ban(nm: str, fac: str, h_px: int = 132) -> Image.Image:
            st = FACTION_STYLE[fac]
            raw = make_war_banner(nm, st["banner_bg"], st["banner_trim"], size=(100, 160))
            crop = _tight_rgba(raw, thresh=25)
            cw, ch = crop.size
            return crop.resize((max(42, int(round(cw * h_px / max(ch, 1)))), h_px), Image.Resampling.LANCZOS)

        self.banners = {
            "黄巢": mk_ban("黄巢", "QI", 142),
            "尚让": mk_ban("尚让", "QI", 132),
            "林言": mk_ban("林言", "QI", 128),
            "李克用": mk_ban("李克用", "SHATUO", 146),
            "朱温": mk_ban("朱温", "TANG", 136),
            "唐守将": mk_ban("唐守将", "TANG", 134),
            "张承范": mk_ban("张承范", "TANG", 134),
        }

        self.city_tang = make_landmark_sprite("city", "#C93326", "#F7D348", size=(370, 280))
        self.city_qi = make_landmark_sprite("city", "#2B5B84", "#F6C226", size=(370, 280))
        self.pass_tang = make_landmark_sprite("pass", "#C93326", "#F7D348", size=(390, 290))
        self.pass_qi = make_landmark_sprite("pass", "#2B5B84", "#F6C226", size=(390, 290))

        # 三大战场 3D 地形底图
        self.bg_gz = _build_tactical_terrain(
            seed=879,
            hill_blobs=[(340, 250, 280, 190, 0.58), (1580, 310, 310, 220, 0.55), (1450, 620, 200, 150, 0.35)],
            river_poly=[(0, 795), (480, 825), (960, 805), (1440, 845), (1920, 820)],
            bridges=[(440, 770, 460, 880), (920, 755, 950, 860)],
        )
        self.bg_tg = _build_tactical_terrain(
            seed=880,
            hill_blobs=[(1020, 825, 440, 190, 0.88), (1040, 480, 250, 145, 0.45), (320, 760, 270, 185, 0.68), (1680, 360, 240, 170, 0.52)],
            river_poly=[(0, 220), (540, 245), (1080, 220), (1560, 195), (1920, 175)],
            bridges=None,
        )
        self.bg_wmd = _build_tactical_terrain(
            seed=884,
            hill_blobs=[(360, 240, 270, 175, 0.45), (1600, 820, 290, 185, 0.48), (1450, 280, 240, 160, 0.38)],
            river_poly=[(0, 560), (480, 515), (980, 565), (1480, 520), (1920, 550)],
            bridges=[(680, 465, 710, 615), (1210, 475, 1245, 610)],
        )

        self.actors_gz = self._build_actors_gz()
        self.actors_tg = self._build_actors_tg()
        self.actors_wmd = self._build_actors_wmd()

    def _u(self, fac: str, ut: str, fl: bool) -> Image.Image:
        return self.unit_imgs[(fac, ut, fl)]

    def _build_actors_gz(self) -> List[Actor]:
        acts: List[Actor] = []
        # 1. 唐军前出迎击兵团（4 名迎敌骑兵/重步，交锋死伤倒地，绝不让黄巢只打空气）
        for i, (ux, uy, du, sl) in enumerate([(925, 535, 0.34, (0.20, 0.29)), (960, 585, 0.40, (0.24, 0.34)), (890, 565, 0.31, (0.18,)), (995, 555, 0.44, (0.26,))]):
            acts.append(Actor(self._u("TANG", "cavalry" if i % 2 == 0 else "heavy_inf", True), [(0.0, ux + 200, uy - 55), (0.26, ux, uy), (0.45, ux + 40, uy - 10)], kind="cav" if i % 2 == 0 else "inf", face_left=True, die_u=du, fall_dir=-1, slashes=sl, phase=i * 0.9))
        # 2. 唐军广州城头守卒（6 名守城步卒 + 帅旗，云梯肉搏后逐一跌落/倒地）
        for i, (wx, wy, du) in enumerate([(1065, 345, 0.56), (1110, 355, 0.60), (1155, 345, 0.65), (1205, 355, 0.72), (1250, 365, 0.78), (1290, 385, 0.84)]):
            acts.append(Actor(self._u("TANG", "infantry", True), [(0.0, wx, wy), (1.0, wx, wy)], face_left=True, die_u=du, fall_dir=-1, slashes=(0.45, 0.54), phase=i * 0.6))
        acts.append(Actor(self.banners["唐守将"], [(0.0, 1345, 345), (1.0, 1345, 345)], face_left=True, die_u=0.80, fall_dir=-1, banner=True))

        # 3. 黄巢前锋攻城步兵（8 名梯队推进，过西桥与正道厮杀后推云梯攀城！）
        acts.append(Actor(self.banners["黄巢"], [(0.0, 340, 610), (0.70, 560, 565), (1.0, 960, 480)], banner=True))
        acts.append(Actor(self.banners["尚让"], [(0.0, 465, 735), (0.65, 790, 565), (1.0, 1080, 495)], banner=True))
        ladder_targets = [(1050, 395), (1095, 415), (1145, 425), (1055, 370), (1100, 390), (1150, 400)]
        for i, (tx, ty) in enumerate(ladder_targets):
            sx, sy = 440 + (i % 3) * 55, 650 + (i // 3) * 55
            mx, my = 885 + (i % 3) * 45, 515 + (i // 3) * 28
            acts.append(Actor(self._u("QI", "heavy_inf" if i < 2 else "infantry", False), [(0.0, sx, sy), (0.36, mx, my), (0.64, tx, ty), (1.0, tx + 35, ty - 10)], die_u=(0.54 if i == 4 else None), slashes=(0.24, 0.50, 0.60), phase=i * 0.7))

        # 4. 破门后突入广州城门的铁骑（4 骑：破门前沿南侧木桥过河列阵待命，u>=0.58 东门火起方由地面直扑门洞！）
        for i in range(4):
            bx, by = 435 + i * 28, 890 + (i % 2) * 24
            wx, wy = 650 + i * 36, 650 + (i % 2) * 22
            acts.append(Actor(self._u("QI", "cavalry", False), [(0.0, bx, by), (0.35, 455 + i * 18, 755), (0.58, wx, wy), (0.88, 1185 + i * 22, 460 + (i % 2) * 14)], kind="cav", slashes=(0.74,), phase=i * 0.8))
        return acts

    def _build_actors_tg(self) -> List[Actor]:
        acts: List[Actor] = []
        # 1. 唐军张承范守关军团（5 名关墙守卒 + 4 名关东前出阻击重甲 + 帅旗）
        for i, (fx, fy, du) in enumerate([(1285, 455, 0.36), (1295, 515, 0.42), (1260, 485, 0.33), (1325, 490, 0.46)]):
            acts.append(Actor(self._u("TANG", "heavy_inf", False), [(0.0, 1120, fy), (0.28, fx, fy), (0.48, fx - 55, fy)], face_left=False, die_u=du, fall_dir=1, slashes=(0.24, 0.34), phase=i * 0.7))
        for i, (wx, wy, du) in enumerate([(960, 385, 0.58), (1005, 395, 0.62), (1055, 385, 0.66), (1095, 405, 0.72), (915, 415, 0.76)]):
            acts.append(Actor(self._u("TANG", "infantry", False), [(0.0, wx, wy), (1.0, wx, wy)], die_u=du, fall_dir=1, slashes=(0.48, 0.60), phase=i * 0.8))
        acts.append(Actor(self.banners["张承范"], [(0.0, 860, 390), (1.0, 860, 390)], die_u=0.74, fall_dir=1, banner=True))

        # 2. 尚让正面攻关（6 名步兵 + 帅旗）
        acts.append(Actor(self.banners["尚让"], [(0.0, 1620, 430), (0.65, 1390, 445), (1.0, 1080, 440)], face_left=True, banner=True))
        for i in range(6):
            sx, sy = 1560 + (i % 2) * 45, 435 + i * 24
            mx, my = 1230 + (i % 2) * 28, 465 + (i % 3) * 24
            acts.append(Actor(self._u("QI", "infantry", True), [(0.0, sx, sy), (0.38, mx, my), (0.66, 1120, 425 + (i % 3) * 14), (0.95, 1020, 455)], face_left=True, die_u=(0.40 if i == 5 else None), slashes=(0.26, 0.52), phase=i * 0.6))

        # 3. 林言禁谷奇袭轻骑（5 骑沿南侧禁谷山道杀到关后，配合正面破门入关中）
        acts.append(Actor(self.banners["林言"], [(0.0, 1590, 775), (0.45, 1040, 875), (0.85, 760, 560)], face_left=True, banner=True))
        for i in range(5):
            off = i * 28
            acts.append(Actor(self._u("QI", "cavalry", True), [(0.0, 1540 + off, 775 + (i % 2) * 24), (0.35, 1050 + off * 0.6, 865 + (i % 2) * 18), (0.62, 665 + off * 0.4, 650), (0.88, 925 + off * 0.5, 465)], kind="cav", face_left=True, slashes=(0.64, 0.72), phase=i * 0.7))
        return acts

    def _build_actors_wmd(self) -> List[Actor]:
        acts: List[Actor] = []
        # 1. 李克用黑衣沙陀鸦儿军（6 骑 + 帅旗，严格顺东西两座浮桥过黄河冲击半渡之敌！）
        acts.append(Actor(self.banners["李克用"], [(0.0, 385, 315), (0.55, 625, 435), (1.0, 780, 680)], banner=True))
        acts.append(Actor(self.banners["朱温"], [(0.0, 1180, 305), (0.60, 1215, 455), (1.0, 1275, 665)], banner=True))
        for i in range(6):
            bridge_pts = (
                [(0.0, 400 + i * 35, 250 + (i % 2) * 28), (0.28, 675, 455), (0.52, 710, 625), (0.88, 865 + i * 32, 785 + (i % 2) * 22)]
                if i < 3 else
                [(0.0, 960 + (i - 3) * 38, 240 + (i % 2) * 28), (0.32, 1205, 465), (0.56, 1245, 615), (0.90, 1365 + (i - 3) * 32, 745 + (i % 2) * 22)]
            )
            acts.append(Actor(self._u("SHATUO", "cavalry", False), bridge_pts, kind="cav", slashes=(0.54, 0.64, 0.74), phase=i * 0.75))

        # 朱温唐军协同步骑（3 名沿东浮桥跟进合围）
        for i in range(3):
            acts.append(Actor(self._u("TANG", "cavalry", False), [(0.0, 1150 + i * 32, 310), (0.42, 1220, 470), (0.66, 1245, 625), (0.95, 1320 + i * 28, 725)], kind="cav", slashes=(0.68,), phase=i * 0.6))

        # 2. 黄巢齐军列阵迎击与溃逃兵团（8 名迎战步骑 + 尚让、黄巢双帅旗，4 人阵亡渡口，尚让旗倒下）
        acts.append(Actor(self.banners["尚让"], [(0.0, 745, 680), (0.55, 795, 705), (1.0, 815, 715)], die_u=0.66, fall_dir=-1, banner=True))
        acts.append(Actor(self.banners["黄巢"], [(0.0, 1150, 720), (0.55, 1460, 795), (1.0, 1740, 845)], banner=True))
        qi_def = [
            (725, 650, 0.56, True), (765, 695, 0.60, True), (835, 665, 0.64, True), (1255, 645, 0.62, True),
            (920, 745, None, False), (1040, 765, None, False), (1285, 710, None, False), (1380, 745, None, False),
        ]
        for i, (qx, qy, du, fl) in enumerate(qi_def):
            keys = [(0.0, qx - 30, qy), (0.48, qx, qy)] if du is not None else [(0.0, qx, qy), (0.48, qx + 80, qy + 30), (1.0, qx + 480, qy + 125)]
            ut = "cavalry" if (i >= 6 or i == 2) else ("heavy_inf" if i < 2 else "infantry")
            acts.append(Actor(self._u("QI", ut, fl), keys, kind="cav" if ut == "cavalry" else "inf", face_left=fl, die_u=du, fall_dir=-1, slashes=(0.54,), phase=i * 0.65))
        return acts

    def _render_scene(self, bg: Image.Image, actors: List[Actor], u: float, extras_fn, hud_title, hud_sub) -> Image.Image:
        im = bg.copy()
        layer_corpses = Image.new("RGBA", (W_PX, H_PX), (0, 0, 0, 0))
        layer_shadows = Image.new("RGBA", (W_PX, H_PX), (0, 0, 0, 0))
        layer_live = Image.new("RGBA", (W_PX, H_PX), (0, 0, 0, 0))
        layer_fx = Image.new("RGBA", (W_PX, H_PX), (0, 0, 0, 0))

        sd = ImageDraw.Draw(layer_shadows, "RGBA")
        # 脚下扬尘
        for ac in actors:
            if ac.banner or (ac.die_u is not None and u >= ac.die_u):
                continue
            x1, y1 = ac.pos(max(0.0, u - 0.02))
            x2, y2 = ac.pos(u)
            if math.hypot(x2 - x1, y2 - y1) > 2.5:
                sd.ellipse([x2 - 22, y2 - 6, x2 + 10, y2 + 7], fill=(168, 146, 112, 72))

        for ac in actors:
            ac.render(u, layer_corpses, layer_live, sd)

        fx_d = ImageDraw.Draw(layer_fx, "RGBA")
        extras_fn(im, fx_d, layer_live, u)

        im.alpha_composite(layer_corpses)
        im.alpha_composite(layer_shadows)
        im.alpha_composite(layer_live)
        im.alpha_composite(layer_fx)
        _draw_bilibili_hud(im, hud_title, hud_sub)
        return im.convert("RGB")

    def render(self, bid: str, u: float) -> Image.Image:
        u = _clamp01(u)
        if bid == "B_GZ":
            def ex(bg_im, d, live, t):
                breached = t >= 0.56
                city_sp = self.city_qi if t >= 0.85 else self.city_tang
                _paste_safe(bg_im, city_sp, 1185 - city_sp.width / 2, 400 - city_sp.height / 2)
                _draw_outlined_text(d, (1185, 560), "广州城（珠江北岸）", PIL_BOLD_28, (255, 232, 132, 255), sw=4)
                _draw_outlined_text(d, (690, 815), "珠   江   水   系", PIL_BOLD_22, (226, 244, 255, 255), sw=3)
                lp = _ease_out((t - 0.14) / 0.24)
                for bx, by, tx, ty in [(950, 505, 1055, 390), (1000, 535, 1105, 415), (1050, 550, 1150, 425)]:
                    _draw_siege_ladder(d, (bx, by), (tx, ty), lp)
                _draw_double_arrow(d, (510, 675), (1030, 465), 0.10, "#2B5B84", min(1.0, t / 0.52), sw=13)
                if breached:
                    _draw_double_arrow(d, (465, 760), (1175, 465), -0.08, "#F6C226", (t - 0.55) / 0.35, sw=14)
                    _draw_fire_smoke(d, (1185, 425), (t - 0.56) / 0.44, seed=41)
                _draw_volleys(d, (620, 620), (1160, 380), (t - 0.18) / 0.24, seed=879, count=30)
                _draw_volleys(d, (1180, 360), (920, 540), (t - 0.22) / 0.24, seed=871, count=20)
                if 0.20 <= t <= 0.42:
                    _draw_slash_and_blood(d, (935, 555), (t - 0.20) / 0.22, seed=11)
                if 0.46 <= t <= 0.68:
                    _draw_slash_and_blood(d, (1110, 385), (t - 0.46) / 0.22, seed=12)

            return self._render_scene(
                self.bg_gz, self.actors_gz, u, ex,
                [("乾符六年九月 · ", "#FFFFFF"), ("黄巢强攻广州城，激战破门换帜", "#FFE04D")],
                "齐唐外围拼杀后步兵架梯登城缠斗，东门炸破起火后齐军铁骑突入城内斩旗破广州",
            )

        if bid == "B_TG":
            def ex(bg_im, d, live, t):
                breached = t >= 0.50
                psp = self.pass_qi if t >= 0.78 else self.pass_tang
                _paste_safe(bg_im, psp, 1020 - psp.width / 2, 445 - psp.height / 2)
                _draw_outlined_text(d, (1020, 610), "潼关雄关（黄河拐弯南岸）", PIL_BOLD_28, (255, 232, 132, 255), sw=4)
                _draw_outlined_text(d, (1030, 885), "禁 谷 奇 袭 山 道", PIL_BOLD_22, (255, 224, 150, 255), sw=3)
                _draw_outlined_text(d, (720, 215), "黄     河", PIL_BOLD_22, (226, 244, 255, 255), sw=3)
                lp = _ease_out((t - 0.12) / 0.24)
                for bx, by, tx, ty in [(1220, 500, 1125, 415), (1250, 535, 1140, 440)]:
                    _draw_siege_ladder(d, (bx, by), (tx, ty), lp)
                _draw_double_arrow(d, (1520, 480), (1140, 470), 0.08, "#2B5B84", min(1.0, t / 0.50), sw=13)
                _draw_double_arrow(d, (1500, 785), (780, 560), 0.28, "#F6C226", min(1.0, t / 0.65), sw=13)
                if breached:
                    _draw_fire_smoke(d, (1025, 445), (t - 0.50) / 0.50, seed=88)
                _draw_volleys(d, (1420, 450), (1020, 400), (t - 0.15) / 0.26, seed=880, count=28)
                _draw_volleys(d, (1010, 390), (1280, 480), (t - 0.18) / 0.26, seed=881, count=22)
                if 0.26 <= t <= 0.45:
                    _draw_slash_and_blood(d, (1285, 485), (t - 0.26) / 0.19, seed=21)
                if 0.54 <= t <= 0.74:
                    _draw_slash_and_blood(d, (925, 445), (t - 0.54) / 0.20, seed=22)

            return self._render_scene(
                self.bg_tg, self.actors_tg, u, ex,
                [("广明元年十二月 · ", "#FFFFFF"), ("尚让正面强攻・林言绕禁谷破潼关", "#FFE04D")],
                "尚让步兵强攻阻住张承范，林言奇兵迂回禁谷从关后破门斩旗，齐军涌入关中",
            )

        # B_WMD 梁田坡—王满渡半渡决战
        def ex_w(bg_im, d, live, t):
            _draw_outlined_text(d, (960, 540), "王 满 渡（黄河故道）", PIL_BOLD_28, (226, 244, 255, 255), sw=4)
            _draw_outlined_text(d, (640, 575), "西浮桥", PIL_BOLD_22, (255, 224, 150, 255), sw=3)
            _draw_outlined_text(d, (1325, 575), "东浮桥", PIL_BOLD_22, (255, 224, 150, 255), sw=3)
            # 箭头止步于北岸桥头入口，既指明两路合围方向又不遮挡南岸渡桥混战的小人阵列
            _draw_double_arrow(d, (440, 270), (705, 475), -0.14, "#2A2D34", min(1.0, t / 0.58), sw=13)
            _draw_double_arrow(d, (980, 265), (1230, 475), -0.10, "#C93326", max(0.0, (t - 0.08) / 0.58), sw=12)
            _draw_volleys(d, (640, 390), (880, 680), (t - 0.20) / 0.30, seed=884, count=30)
            if 0.44 <= t <= 0.68:
                _draw_slash_and_blood(d, (755, 665), (t - 0.44) / 0.24, seed=31)
                _draw_slash_and_blood(d, (1255, 655), (t - 0.44) / 0.24, seed=32)
            if t >= 0.48:
                _draw_fire_smoke(d, (715, 610), (t - 0.48) / 0.52, seed=91)

        return self._render_scene(
            self.bg_wmd, self.actors_wmd, u, ex_w,
            [("中和四年五月 · ", "#FFFFFF"), ("沙陀鸦军渡桥合围，王满渡半渡大溃败", "#FFE04D")],
            "李克用黑衣鸦儿军与朱温沿浮桥两路猛扑半渡齐军，尚让折旗降唐，黄巢残部突围泰山",
        )
