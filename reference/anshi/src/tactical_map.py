# -*- coding: utf-8 -*-
"""B站历史科普风格 3D 立体地形关键战役战术渲染模块（1920×1080）。
核心视觉对标参考图：
1. 3D 岩脊分形凹凸地形（Ridged Multifractal + 315° Hillshade）：立体绝壁、黄土台原与开阔平川一目了然；
2. 水系采用「深黑外岸线 + 亮天蓝水体 + 白字粗黑边河名」；
3. 主将树立传统中国竖幅锯齿火焰边「帅旗」（哥舒翰、李嗣业、郭子仪、崔乾祐、安守忠、回纥叶护），
   配合精修 4x 超采样骑步陌刀兵种精灵；
4. 战术动作采用高饱和「外黑边 + 白光晕 + 阵营色」双描边大箭头，顶部大标题与底部 B站科普大字幕直观叙事。
"""
import math
import zlib
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter
from matplotlib import font_manager as fm, patheffects
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.patches import Circle, Ellipse, Polygon, Rectangle

from landmarks import make_landmark_sprite, make_war_banner
from sprites import make_sprite
from surface_texture import rotated_texture_field, steerable_slope_fields, texture_field
from terrain import compute_hillshade, ridged_multifractal_2d, smooth_polyline

# 固定战役地形纹理种子，确保同一战场跨进程与连续帧完全零闪烁
BATTLE_TERRAIN_SEEDS = {
    "B03": 753,
    "B05": 755,
    "B06": 762,
    "B10": 764,
    "B11": 766,
    "B13": 768,
    "B15": 770,
    "B16": 772,
    "B21": 774,
}

W_PX, H_PX = 1920, 1080
FONT_REG = fm.FontProperties(fname=r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = fm.FontProperties(fname=r"C:\Windows\Fonts\msyhbd.ttc")
FONT_KAI = fm.FontProperties(fname=r"C:\Windows\Fonts\simkai.ttf")

# 阵营高饱和帅旗与箭头配色
FACTION_STYLE = {
    "TANG": dict(color="#D63227", banner_bg="#C93326", banner_trim="#F7D348", arrow="#E03828", unit_c="#C0392B", unit_a="#F5B041"),
    "YAN_AN": dict(color="#4A68C8", banner_bg="#4663C2", banner_trim="#F5CC46", arrow="#5170E0", unit_c="#4E5EA8", unit_a="#DDE4F6"),
    "YAN_SHI": dict(color="#3A5298", banner_bg="#3A5298", banner_trim="#E6C85A", arrow="#4868C0", unit_c="#334878", unit_a="#BAC8E2"),
    "UYGHUR": dict(color="#158E7E", banner_bg="#148F77", banner_trim="#F7D348", arrow="#18A68F", unit_c="#148F77", unit_a="#A3E4D7"),
    "FANZHEN": dict(color="#D35400", banner_bg="#D35400", banner_trim="#F5C74C", arrow="#E67E22", unit_c="#D35400", unit_a="#F5B041"),
}


def px_to_pt(px):
    return float(px) * 72.0 / 100.0


def text_outline(stroke_px=4.2, stroke_col="#12100E"):
    return [patheffects.withStroke(linewidth=px_to_pt(stroke_px * 2.0), foreground=stroke_col)]


def draw_bilibili_hud(ax, title_parts, bottom_subtitle):
    """参考图同款顶部大标题 + 底部大号白字黑边字幕条。"""
    # 顶部标题：按精确字符步宽顺接排列，避免标点后产生多余空格断档
    x_cur = 60.0
    y_top = 1022.0
    for txt, col in title_parts:
        ax.text(
            x_cur, y_top, txt,
            fontproperties=FONT_BOLD, fontsize=px_to_pt(48), color=col,
            ha="left", va="center", zorder=48,
            path_effects=text_outline(4.8, "#0F0D0C"),
        )
        units = 0.0
        for ch in txt:
            if ch == " ":
                units += 0.34
            elif ch in ("·", "—", "，", "。", "、"):
                units += 0.56
            elif ord(ch) < 128:
                units += 0.58
            else:
                units += 0.99
        x_cur += units * 48.0

    # 底部半透明黑底衬条 + 居中大号白字黑边科普字幕
    if bottom_subtitle:
        ax.add_patch(Rectangle((0, 0), W_PX, 108.0, fc="#0D0F14", ec="none", alpha=0.66, zorder=46))
        ax.text(
            W_PX * 0.5, 54.0, bottom_subtitle,
            fontproperties=FONT_BOLD, fontsize=px_to_pt(37), color="#FFFFFF",
            ha="center", va="center", zorder=48,
            path_effects=text_outline(4.0, "#000000"),
        )


def draw_double_stroked_arrow(
    ax, p_from, p_to, color,
    shaft_px=13.0, head_w_px=34.0, head_l_px=36.0,
    ctrl_pt=None, rad=0.0, alpha=1.0, zorder=28, progress=1.0,
):
    """B站科普同款醒目双描边大箭头：外深黑边 + 亮白衬框 + 高饱和实心箭身，支持按弧长动态生长。"""
    x1, y1 = float(p_from[0]), float(p_from[1])
    x2, y2 = float(p_to[0]), float(p_to[1])
    if ctrl_pt is None:
        mx, my = 0.5 * (x1 + x2), 0.5 * (y1 + y2)
        dx, dy = x2 - x1, y2 - y1
        ctrl_pt = (mx - dy * rad, my + dx * rad) if abs(rad) > 1e-4 else (mx, my)

    ts = np.linspace(0.0, 1.0, 72)
    arr_full = np.array([
        (
            (1 - t) ** 2 * x1 + 2 * (1 - t) * t * ctrl_pt[0] + t ** 2 * x2,
            (1 - t) ** 2 * y1 + 2 * (1 - t) * t * ctrl_pt[1] + t ** 2 * y2,
        )
        for t in ts
    ], dtype=float)

    diffs_full = np.diff(arr_full, axis=0)
    seg_full = np.hypot(diffs_full[:, 0], diffs_full[:, 1])
    cum_full = np.concatenate([[0.0], np.cumsum(seg_full)])
    total_full = float(cum_full[-1])

    prog = float(np.clip(progress, 0.0, 1.0))
    if prog < 0.999:
        s_end = total_full * prog
        if s_end < 16.0:
            return arr_full
        idx_end = max(0, min(len(arr_full) - 2, int(np.searchsorted(cum_full, s_end, side="right")) - 1))
        rem_end = (s_end - cum_full[idx_end]) / max(seg_full[idx_end], 1e-6)
        p_tip = arr_full[idx_end] + rem_end * (arr_full[idx_end + 1] - arr_full[idx_end])
        arr = np.vstack([arr_full[: idx_end + 1], p_tip[None, :]])
        diffs = np.diff(arr, axis=0)
        seg_lens = np.hypot(diffs[:, 0], diffs[:, 1])
        cum = np.concatenate([[0.0], np.cumsum(seg_lens)])
        total = float(cum[-1])
        head_scale = min(1.0, total / max(head_l_px * 1.45, 1.0))
        head_l_eff = max(10.0, head_l_px * head_scale)
        hw_h_eff = max(shaft_px * 0.85, head_w_px * 0.5 * (0.55 + 0.45 * head_scale))
    else:
        arr, seg_lens, cum, total = arr_full, seg_full, cum_full, total_full
        head_l_eff = head_l_px
        hw_h_eff = head_w_px * 0.5

    if total < head_l_eff + 6.0:
        return arr_full

    s_cut = total - head_l_eff
    idx_cut = max(0, min(len(arr) - 2, int(np.searchsorted(cum, s_cut, side="right")) - 1))
    rem = (s_cut - cum[idx_cut]) / max(seg_lens[idx_cut], 1e-6)
    p_base = arr[idx_cut] + rem * (arr[idx_cut + 1] - arr[idx_cut])

    shaft = np.vstack([arr[: idx_cut + 1], p_base[None, :]])
    m = len(shaft)
    tang = np.zeros_like(shaft)
    tang[0] = shaft[1] - shaft[0]
    tang[-1] = arr[-1] - p_base
    if m > 2:
        tang[1:-1] = shaft[2:] - shaft[:-2]
    u = tang / (np.hypot(tang[:, 0], tang[:, 1])[:, None] + 1e-6)
    nrm = np.column_stack([-u[:, 1], u[:, 0]])

    u_end = arr[-1] - p_base
    u_end /= (np.hypot(u_end[0], u_end[1]) + 1e-6)
    n_end = np.array([-u_end[1], u_end[0]])

    hw_s = shaft_px * 0.5
    pts = np.vstack([
        shaft + nrm * hw_s,
        (p_base + n_end * hw_h_eff)[None, :],
        arr[-1][None, :],
        (p_base - n_end * hw_h_eff)[None, :],
        (shaft - nrm * hw_s)[::-1],
    ])
    patch = Polygon(
        pts, closed=True, fc=color, ec="none", alpha=alpha, zorder=zorder,
        path_effects=[
            patheffects.withStroke(linewidth=px_to_pt(7.2), foreground="#141110", alpha=alpha),
            patheffects.withStroke(linewidth=px_to_pt(3.6), foreground="#FFFFFF", alpha=alpha * 0.96),
        ],
    )
    ax.add_patch(patch)
    return arr_full


def _tight_rgba(img, thresh=40):
    arr = np.asarray(img)
    mask = arr[..., 3] > thresh
    if not mask.any():
        return img
    ys, xs = np.where(mask)
    return img.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))


def _place_unit_group(ax, x, y, faction, ut, flip=False, count=4, layout="horizontal", unit_h=56, alpha=1.0, zorder=22):
    st = FACTION_STYLE[faction]
    raw = make_sprite(ut, st["unit_c"], st["unit_a"], flip=flip, size=(150, 120))
    crop = _tight_rgba(raw, thresh=65)
    cw, ch = crop.size
    uw = max(22, int(round(cw * (unit_h / max(ch, 1)))))
    sp = np.asarray(crop.resize((uw, unit_h), Image.Resampling.LANCZOS), dtype=float)
    sp[..., 3] *= alpha
    sp_u8 = np.clip(sp, 0, 255).astype(np.uint8)

    pts = []
    if layout == "column":
        step = uw * 0.95
        x0 = -(count - 1) * step * 0.5
        for i in range(count):
            pts.append((x + x0 + i * step, y + (-4.0 if i % 2 else 4.0)))
    elif layout == "tight_grid":
        cols = math.ceil(count / 2)
        for i in range(count):
            r, c = i // cols, i % cols
            pts.append((x + (c - (cols - 1) * 0.5) * uw * 0.90 + (7 if r else -7), y + (r - 0.5) * unit_h * 0.72))
    else:  # horizontal
        step = uw * 0.90
        x0 = -(count - 1) * step * 0.5
        for i in range(count):
            pts.append((x + x0 + i * step, y + (-4.0 if i % 2 else 4.0)))

    for px, py in sorted(pts, key=lambda p: -p[1]):
        ax.add_patch(Ellipse((px, py - unit_h * 0.42), width=uw * 0.78, height=13.0, fc="#141110", ec="none", alpha=0.22 * alpha, zorder=zorder - 0.5))
        ax.add_artist(AnnotationBbox(OffsetImage(sp_u8, zoom=1.0), (px, py), frameon=False, zorder=zorder))


def _place_banner(ax, x, y, name, faction, h_px=152, zorder=26):
    st = FACTION_STYLE[faction]
    raw = make_war_banner(name, st["banner_bg"], st["banner_trim"], size=(100, 160))
    crop = _tight_rgba(raw, thresh=30)
    cw, ch = crop.size
    w_px = max(44, int(round(cw * (h_px / max(ch, 1)))))
    arr = np.asarray(crop.resize((w_px, h_px), Image.Resampling.LANCZOS), dtype=np.uint8)
    ab = AnnotationBbox(OffsetImage(arr, zoom=1.0), (x, y), box_alignment=(0.5, 0.0), frameon=False, zorder=zorder)
    ax.add_artist(ab)


def _place_building(ax, kind, x, y, name, faction, width_px=130, lbl_dx=0, lbl_dy=-26, zorder=19):
    st = FACTION_STYLE[faction]
    raw = make_landmark_sprite(kind, st["banner_bg"], st["banner_trim"], size=(240, 192))
    crop = _tight_rgba(raw, thresh=40)
    cw, ch = crop.size
    h_px = max(24, int(round(ch * (width_px / max(cw, 1)))))
    arr = np.asarray(crop.resize((int(width_px), h_px), Image.Resampling.LANCZOS), dtype=np.uint8)
    ax.add_patch(Ellipse((x, y + 4.0), width=width_px * 0.92, height=h_px * 0.24, fc="#141110", ec="none", alpha=0.28, zorder=zorder - 0.5))
    ax.add_artist(AnnotationBbox(OffsetImage(arr, zoom=1.0), (x, y), box_alignment=(0.5, 0.0), frameon=False, zorder=zorder))
    if name:
        ax.text(
            x + lbl_dx, y + lbl_dy, name,
            fontproperties=FONT_BOLD, fontsize=px_to_pt(32), color="#FFFFFF",
            ha="center", va="center", zorder=zorder + 4,
            path_effects=text_outline(4.2, "#12100E"),
        )


def _dist_seg_2d(GX, GY, pts):
    d2 = np.full_like(GX, 1e9)
    for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
        dx, dy = x2 - x1, y2 - y1
        seg2 = dx * dx + dy * dy + 1e-12
        t = np.clip(((GX - x1) * dx + (GY - y1) * dy) / seg2, 0.0, 1.0)
        d2 = np.minimum(d2, (GX - (x1 + t * dx)) ** 2 + (GY - (y1 + t * dy)) ** 2)
    return np.sqrt(d2)


def _hypsometric_tactical_rgb(elev, hs, seed_tint=0, *, detail_background=False):
    """高立体质感岩石与黄土设色（精修模式平滑高海拔岩阶过渡，避免分形山顶形成斑驳浅斑）。"""
    stops = np.array([0.00, 0.16, 0.34, 0.54, 0.76, 0.94, 1.00])
    if detail_background:
        colors = np.array([
            [176, 186, 134],  # 谷底河岸润泽浅草黄绿
            [208, 190, 146],  # 灵宝/平川黄土开阔走廊
            [188, 156, 108],  # 黄土台原斜坡
            [142, 102, 68],   # 中山峭壁岩面
            [112, 78, 52],    # 深岩山壁
            [118, 86, 60],    # 峻岭岩脊
            [128, 98, 72],    # 高脊石质受光面（明暗由 315° Hillshade 统一塑造）
        ], dtype=float)
    else:
        colors = np.array([
            [176, 186, 134],  # 谷底河岸润泽浅草黄绿
            [208, 190, 146],  # 灵宝/平川黄土开阔走廊
            [188, 156, 108],  # 黄土台原斜坡
            [142, 102, 68],   # 中山峭壁岩面
            [106, 72, 46],    # 深岩山脊
            [136, 106, 82],   # 峻岭岩峰
            [162, 138, 112],  # 向阳微亮岩脊（绝不发白）
        ], dtype=float)
    e = np.clip(elev, 0.0, 1.0)
    rgb = np.zeros(e.shape + (3,), dtype=float)
    for ch in range(3):
        rgb[..., ch] = np.interp(e, stops, colors[:, ch])

    # 强化三维明暗雕刻
    shade = 0.54 + 0.64 * hs
    rgb = np.clip(rgb * shade[..., None], 0, 255)
    hi_gain = 0.14 if detail_background else 0.24
    ridge_hi = np.clip((elev - 0.62) / 0.34, 0, 1) * np.clip((hs - 0.68) / 0.28, 0, 1) * hi_gain
    rgb = rgb * (1.0 - ridge_hi[..., None]) + np.array([196.0, 178.0, 148.0]) * ridge_hi[..., None]
    return rgb


def _build_unit_calm_mask(GX, GY, units):
    """在军阵落位区域生成平滑避让掩膜，压低地面反差以保证前景兵种小人与箭头清晰好读。"""
    calm = np.zeros_like(GX, dtype=float)
    for ux, uy, _fac, _ut, _flip, ucnt, ulay in units or []:
        rx = max(135.0, float(ucnt) * (46.0 if ulay == "column" else 42.0))
        ry = 96.0 if ulay == "tight_grid" else 82.0
        d2 = ((GX - float(ux)) / rx) ** 2 + ((GY - float(uy)) / ry) ** 2
        calm = np.maximum(calm, np.exp(-(d2 ** 1.35)))
    return np.clip(calm, 0.0, 1.0)


def _finish_tactical_ground(rgb, elev, hillshade, banks, units, GX, GY, seed):
    """为战术底图叠加河岸浅滩/零散草色、台地细坡褶与浅沟、南崖岩面阴影，并保持军阵下方低对比。"""
    rng = np.random.default_rng(seed + 1)
    shape = elev.shape
    calm = _build_unit_calm_mask(GX, GY, units)
    detail_gate = 1.0 - 0.65 * calm

    plain = 1.0 - np.clip((elev - 0.17) / 0.22, 0.0, 1.0)
    foothill = np.exp(-((elev - 0.28) / 0.11) ** 2) * np.clip((elev - 0.14) / 0.11, 0.0, 1.0)
    hillside = np.clip((elev - 0.19) / 0.30, 0.0, 1.0)

    # 识别地形斜坡与陡崖，区分台地斜坡与南崖绝壁
    gy, gx = np.gradient(gaussian_filter(elev, sigma=2.5))
    slope = np.hypot(gx, gy)
    cliff = hillside * np.clip((elev - 0.34) / 0.30, 0.0, 1.0) * np.clip((slope - 0.007) / 0.026, 0.0, 1.0)
    curv = gaussian_filter(elev, sigma=5.0) - gaussian_filter(elev, sigma=1.15)
    toe_ao = np.clip(curv * 15.0, -0.050, 0.095) * np.clip(hillside + 0.75 * foothill, 0.0, 1.0)

    soil = texture_field(rng, shape, (10.5, 17.5))
    grass = texture_field(rng, shape, (2.8, 5.8))
    grain = texture_field(rng, shape, (0.65, 1.0))

    # 沿局部山体坡向生成顺坡浅沟（rills）与沿等高线延展的台地坡褶/岩层（slope_strata），平滑过渡无圆斑
    rills, slope_strata = steerable_slope_fields(rng, shape, gx, gy, sigma_along=9.5, sigma_across=2.2)
    north_scarp = np.clip(-gy * 26.0, 0.0, 1.0) * cliff

    # 1. 平原柔和土色变化（军阵区保持低对比）
    plain_color = (soil * 0.64 + grass * 0.26 + grain * 0.10) * detail_gate
    rgb += (plain * plain_color)[..., None] * np.array([12.5, 9.0, 5.2])
    rgb += (plain * grain * detail_gate)[..., None] * np.array([1.4, 1.9, 1.3])

    # 2. 台地坡褶浅沟、陡崖岩面与坡脚暗影（不在梯度高度场里注入高频像素噪点）
    rough_elev = (
        elev
        + detail_gate * hillside * (0.024 * slope_strata + 0.032 * rills)
        + detail_gate * foothill * (0.016 * rills + 0.008 * slope_strata)
        + detail_gate * cliff * (0.018 * rills + 0.012 * slope_strata)
    )
    rough_light, _ = compute_hillshade(rough_elev, azimuth_deg=315.0, altitude_deg=36.0, z_factor=10.5)
    weathering = (
        detail_gate * hillside * (0.018 * slope_strata + 0.016 * rills)
        - detail_gate * (0.045 * north_scarp + 0.020 * cliff)
        - detail_gate * toe_ao
    )
    rgb *= (1.0 + weathering + 0.50 * (rough_light - hillshade))[..., None]
    rgb += (detail_gate * grain * (0.4 + 0.4 * hillside))[..., None] * np.array([2.2, 2.0, 1.6])

    # 3. 河岸浅滩与坡脚/岸边零散草色
    bank_grass = np.zeros(shape, dtype=float)
    wet_shore = np.zeros(shape, dtype=float)
    for distance, half_width in banks:
        shore_distance = distance - half_width
        wet = np.exp(-((shore_distance - 5.5) / 4.2) ** 2) * plain
        wet_shore = np.maximum(wet_shore, wet)

        sand_edge = 16.5 + 4.8 * grass
        sand = 0.34 * np.exp(-((shore_distance - sand_edge) / 12.0) ** 2) * plain
        sand *= 0.72 + 0.20 * grass + 0.08 * grain
        sand *= (1.0 - 0.50 * calm)
        rgb += sand[..., None] * (np.array([224.0, 195.0, 140.0]) - rgb)

        grass_band = np.exp(-((shore_distance - 46.0) / 30.0) ** 2) * plain
        bank_grass = np.maximum(bank_grass, grass_band)

    # 河缘湿土微暗过渡，让黑岸线与黄土岸坡自然衔接
    rgb *= (1.0 - 0.075 * wet_shore * detail_gate)[..., None]

    patches = np.clip(0.52 * grass + 0.36 * grain - 0.18 * soil, 0.0, 1.0)
    clustered = np.clip((grass + 0.30) / 1.15, 0.0, 1.0)
    dabs = rng.random(shape) < 0.24 * clustered
    flecks = np.clip(gaussian_filter(dabs.astype(np.float32), (0.7, 1.25)) - 0.04, 0.0, 0.38)
    scrub = patches * (0.070 * plain + 0.22 * bank_grass + 0.13 * foothill)
    scrub += flecks * (0.68 * bank_grass + 0.42 * foothill)
    scrub *= detail_gate
    rgb += scrub[..., None] * (np.array([116.0, 129.0, 79.0]) - rgb)
    return rgb


def _build_tactical_relief_rgb(cfg, seed=755, *, detail_background=True):
    """为关键战役构建真正三维立体凹凸的 1920×1080 战术地形底图（河道留待矢量平滑叠加）。"""
    sw, sh = 640, 360
    xs = np.linspace(0, W_PX, sw)
    ys = np.linspace(0, H_PX, sh)
    GX, GY = np.meshgrid(xs, ys)
    elev = np.full((sh, sw), 0.14, dtype=float)

    for spine, h, w in cfg.get("ridges", []):
        d = _dist_seg_2d(GX, GY, smooth_polyline(spine, 5))
        elev = np.maximum(elev, h * np.exp(-(d / w) ** 2))
    for cx, cy, h, rx, ry in cfg.get("plateaus", []):
        d2 = ((GX - cx) / rx) ** 2 + ((GY - cy) / ry) ** 2
        elev = np.maximum(elev, h * np.exp(-(d2 ** 1.5)))
    for spine, depth, w in cfg.get("valleys", []):
        d = _dist_seg_2d(GX, GY, smooth_polyline(spine, 5))
        elev *= (1.0 - depth * np.exp(-(d / w) ** 2)).clip(0.18, 1.0)

    # 叠加锐利 3D 岩脊褶皱
    rt = ridged_multifractal_2d(sh, sw, seed=seed, octaves=((14.0, 0.44), (6.5, 0.32), (3.0, 0.16), (1.4, 0.08)))
    mtn_w = np.clip((elev - 0.22) / 0.26, 0.0, 1.0)
    elev = elev * (1.0 - 0.44 * mtn_w) + (elev * rt * 1.42) * (0.44 * mtn_w)
    elev = np.clip(gaussian_filter(elev, sigma=0.75), 0.0, 1.0)

    # 沿水系柔和下切河岸浅滩，不画锯齿黑像素边缘
    banks = []
    for r_pts, r_w, _ in cfg.get("river_ribbons", []):
        d_r = _dist_seg_2d(GX, GY, smooth_polyline(r_pts, 6))
        elev *= np.where(d_r < r_w * 1.4, 0.40 + 0.60 * np.clip(d_r / max(r_w * 1.4, 1.0), 0.0, 1.0), 1.0)
        banks.append((d_r, r_w))

    hs, _ = compute_hillshade(elev, azimuth_deg=315.0, altitude_deg=36.0, z_factor=10.0)
    rgb = _hypsometric_tactical_rgb(elev, hs, detail_background=detail_background)
    if detail_background:
        rgb = _finish_tactical_ground(rgb, elev, hs, banks, cfg.get("units", []), GX, GY, seed)
    pil = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), mode="RGB").resize((W_PX, H_PX), Image.Resampling.BICUBIC)
    return np.asarray(pil, dtype=np.uint8)


def _draw_vector_tactical_river(ax, r_pts, half_w_px, zorder=6):
    """矢量抗锯齿大河绘制：柔和浅岸坡 + 深墨岸线 + 立体渐变亮蓝水体（零像素阶梯锯齿）。"""
    sm = smooth_polyline(r_pts, 10)
    xs, ys = zip(*sm)
    w_full = half_w_px * 2.0
    ax.plot(xs, ys, color="#BFA878", lw=px_to_pt(w_full + 24.0), solid_capstyle="round", solid_joinstyle="round", alpha=0.55, zorder=zorder - 0.2)
    ax.plot(xs, ys, color="#191614", lw=px_to_pt(w_full + 9.0), solid_capstyle="round", solid_joinstyle="round", zorder=zorder)
    ax.plot(xs, ys, color="#3A78B4", lw=px_to_pt(w_full), solid_capstyle="round", solid_joinstyle="round", zorder=zorder + 0.1)
    ax.plot(xs, ys, color="#6EAEEB", lw=px_to_pt(w_full * 0.56), solid_capstyle="round", solid_joinstyle="round", zorder=zorder + 0.2)


def _draw_tactical_river_texture(ax, rivers, seed):
    """在矢量河道内部叠加水色渐变、近岸浅滩带与断续水纹，保持黑岸线与河心清晰对比。"""
    if not rivers:
        return
    width, height = 960, 540
    shape = (height, width)
    rng = np.random.default_rng(seed + 2)
    current = texture_field(rng, shape, (5.5, 13.0))
    ripple = texture_field(rng, shape, (1.1, 6.8))
    glint = texture_field(rng, shape, (0.55, 4.4))
    grid_x, grid_y = np.meshgrid(
        (np.arange(width) + 0.5) * W_PX / width,
        (np.arange(height) + 0.5) * H_PX / height,
    )

    for idx, (points, half_width, _rname) in enumerate(rivers):
        sm = smooth_polyline(points, 10)
        distance = _dist_seg_2d(grid_x, grid_y, sm)
        # 计算河道主走向，融合顺流波纹与横向断续水纹
        p0, p1 = points[0], points[-1]
        ang = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
        flow = rotated_texture_field(
            np.random.default_rng(seed + 20 + idx),
            shape,
            sigma_along=18.0,
            sigma_across=2.6,
            angle_deg=ang,
        )

        shore = np.clip((distance / half_width - 0.22) / 0.78, 0.0, 1.0)
        shore = shore * shore * (3.0 - 2.0 * shore)
        deep = np.array([112.0, 176.0, 228.0])
        edge = np.array([56.0, 118.0, 174.0])
        colors = deep + shore[..., None] * (edge - deep)

        # 近岸沙洲浅滩带（微透青绿暖浅水调）
        shoal_noise = np.clip(0.55 + 0.45 * current + 0.35 * flow, 0.0, 1.0)
        shoal = np.exp(-((distance / half_width - 0.78) / 0.14) ** 2) * shoal_noise
        colors = colors * (1.0 - 0.24 * shoal[..., None]) + np.array([128.0, 186.0, 198.0]) * (0.24 * shoal[..., None])

        # 断续水纹高光（避免整条河道均匀条纹，随水流明暗错落断续）
        broken_gate = np.clip(0.65 + 0.55 * flow + 0.35 * current, 0.0, 1.0)
        crests = (np.clip(1.25 * (glint + 0.42 * ripple - 0.22), 0.0, 1.0) ** 2) * broken_gate
        light = 5.5 * current + 4.5 * flow + 4.8 * ripple + 3.2 * glint + 10.5 * crests
        colors += light[..., None]

        alpha = np.clip((half_width - distance) / 3.4, 0.0, 1.0)
        rgba = np.dstack((np.clip(colors, 0, 255), alpha * 255.0)).astype(np.uint8)
        ax.imshow(rgba, extent=[0, W_PX, 0, H_PX], origin="lower", interpolation="bilinear", zorder=6.3)


def _draw_island_and_bridges(ax, sc):
    """在河道之上绘制河心沙洲（如河阳中潬岛）与木质浮桥/军桥，杜绝城池悬水或徒步踩水。"""
    for cx, cy, rx, ry, ang in sc.get("islands", []):
        ax.add_patch(Ellipse((cx, cy), rx * 2.04, ry * 2.08, angle=ang, fc="#241D17", ec="none", zorder=7.9))
        ax.add_patch(Ellipse((cx, cy), rx * 1.96, ry * 1.96, angle=ang, fc="#DFC99B", ec="#4A3828", lw=px_to_pt(2.0), zorder=8.0))
        ax.add_patch(Ellipse((cx, cy), rx * 1.72, ry * 1.66, angle=ang, fc="#C7AF7F", ec="none", zorder=8.1))

    for (x1, y1), (x2, y2), bw in sc.get("bridges", []):
        dx, dy = float(x2 - x1), float(y2 - y1)
        L = max(1.0, math.hypot(dx, dy))
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        hw = float(bw) * 0.5
        # 桥面木板底与两侧护栏
        deck = [(x1 + nx * hw, y1 + ny * hw), (x2 + nx * hw, y2 + ny * hw),
                (x2 - nx * hw, y2 - ny * hw), (x1 - nx * hw, y1 - ny * hw)]
        ax.add_patch(Polygon(deck, closed=True, fc="#9A6234", ec="#24160D", lw=px_to_pt(2.6), zorder=9.0))
        # 横向木排/跳板纹路
        n_planks = max(4, int(L / 10.0))
        for k in range(1, n_planks):
            t = k / float(n_planks)
            px, py = x1 + dx * t, y1 + dy * t
            ax.plot([px - nx * hw * 0.9, px + nx * hw * 0.9], [py - ny * hw * 0.9, py + ny * hw * 0.9],
                    color="#5B361B", lw=px_to_pt(1.6), zorder=9.1)
        # 两侧深木护栏实线
        for sgn in (-1.0, 1.0):
            ax.plot([x1 + nx * hw * sgn, x2 + nx * hw * sgn], [y1 + ny * hw * sgn, y2 + ny * hw * sgn],
                    color="#2D1A0E", lw=px_to_pt(3.2), solid_capstyle="butt", zorder=9.2)


def _draw_tactical_fire_plume(ax, fx_x, fx_y, length=380.0):
    """参考风向烈焰浓烟效果：局部刺目火舌配顺风翻涌黑灰浓烟。"""
    sw, sh = 640, 360
    sx, sy = sw / W_PX, sh / H_PX
    yy, xx = np.mgrid[0:sh, 0:sw]
    cx, cy = fx_x * sx, fx_y * sy
    len_s = length * sx
    t = np.clip((cx - xx) / len_s, 0.0, 1.2)
    valid = (cx - xx >= -16) & (cx - xx <= len_s * 1.1)
    spine = cy + 10.0 * np.sin(t * 4.5) + 18.0 * t
    sig = 12.0 + 20.0 * np.clip(t, 0, 1)
    smoke = np.where(valid, np.exp(-0.5 * ((yy - spine) / sig) ** 2), 0.0)
    smoke *= np.clip((t + 0.08) / 0.14, 0, 1) * np.clip(1.0 - np.maximum(0.0, (t - 0.55) / 0.50), 0, 1)
    smoke = gaussian_filter(smoke, sigma=2.5)
    smoke = smoke / max(float(smoke.max()), 1e-6)

    f1 = np.exp(-(((xx - cx) / 14.0) ** 2 + ((yy - cy) / 10.0) ** 2))
    f2 = np.exp(-(((xx - (cx - 12)) / 10.0) ** 2 + ((yy - (cy + 5)) / 8.0) ** 2)) * 0.85
    fire = np.clip(gaussian_filter(np.maximum(f1, f2), sigma=1.4), 0.0, 1.0)

    layer = np.zeros((sh, sw, 4), dtype=float)
    layer[..., 0:3] = [66.0, 58.0, 52.0]
    layer[..., 3] = np.clip(smoke * 0.60, 0.0, 0.65) * 255.0

    mix = np.clip(fire * 1.3, 0, 1)
    layer[..., 0] = layer[..., 0] * (1 - mix) + 242.0 * mix
    layer[..., 1] = layer[..., 1] * (1 - mix) + 128.0 * mix
    layer[..., 2] = layer[..., 2] * (1 - mix) + 32.0 * mix
    layer[..., 3] = np.maximum(layer[..., 3], fire * 238.0)

    pil = Image.fromarray(np.flipud(np.clip(layer, 0, 255).astype(np.uint8)), mode="RGBA").resize((W_PX, H_PX), Image.Resampling.BILINEAR)
    ax.imshow(np.asarray(pil), extent=[0, W_PX, 0, H_PX], origin="upper", interpolation="bilinear", zorder=29)


# ==============================================================================
# 关键战役专属 3D 战术场景配置
# ==============================================================================
SCENES = {
    "B03": dict(
        title_parts=[("天宝十四载十二月丁酉 · ", "#FFFFFF"), ("东京洛阳保卫战", "#FFE04D")],
        subtitle="封常清仓促所募新军四战难敌三镇边骑，洛阳城破，李憕卢奕殉国，残部西退陕郡",
        ridges=[
            ([(120, 795), (600, 775), (1120, 785)], 0.68, 105),
            ([(1780, 180), (1855, 540), (1830, 880)], 0.68, 175),
        ],
        plateaus=[
            (1620, 560, 0.34, 210, 260),
            (1320, 715, 0.28, 180, 85),
        ],
        valleys=[
            ([(180, 535), (860, 535), (1480, 535)], 0.55, 220),
        ],
        river_ribbons=[
            ([(0, 915), (560, 900), (1050, 885), (1520, 895), (1920, 915)], 44.0, "黄河"),
            ([(0, 210), (540, 225), (960, 250), (1440, 235), (1920, 265)], 36.0, "洛水"),
        ],
        walls=[[(490, 390), (800, 390), (800, 680), (490, 680), (490, 390)]],
        buildings=[("capital", 645, 455, "东京洛阳（上东门）", "TANG", 136, 0, -28)],
        labels=[
            ("黄   河", 1540, 902, 36, "#FFFFFF", 0),
            ("河阳桥（已断桥）", 960, 910, 26, "#FFE8A8", 0),
            ("北 邙 山", 1160, 790, 32, "#FFE8A8", 0),
            ("洛   水", 1280, 242, 34, "#FFFFFF", 0),
            ("葵园 · 虎牢来路", 1680, 815, 30, "#FFE8A8", 0),
        ],
        units=[
            (655, 618, "TANG", "infantry", False, 3, "horizontal"),
            (995, 512, "TANG", "levy", False, 5, "horizontal"),
            (1425, 545, "YAN_AN", "cavalry", True, 5, "horizontal"),
            (1600, 405, "YAN_AN", "mixed", True, 4, "horizontal"),
        ],
        banners=[
            (555, 528, "李憕", "TANG", 128),
            (862, 412, "封常清", "TANG", 142),
            (1625, 555, "安禄山", "YAN_AN", 152),
        ],
        arrows=[
            ((1275, 540), (1095, 518), "YAN_AN", 14.0, 0.08, 1.0, "三镇精骑连破四阵"),
            ((1425, 620), (825, 635), "YAN_AN", 11.5, -0.22, 0.90, "直逼上东门"),
            ((460, 535), (155, 535), "TANG", 12.0, -0.10, 0.92, "西退陕郡 · 潼关"),
        ],
        fire_at=None,
    ),
    "B06": dict(
        title_parts=[("天宝十五载六月 · ", "#FFFFFF"), ("灵宝西原大败，潼关失守", "#FFE04D")],
        subtitle="哥舒翰二十万大军纵队拥塞河崖狭道无法展开，遭崔乾祐南山伏击与火车破阵",
        ridges=[
            ([(0, 160), (420, 175), (860, 260), (1180, 420), (1440, 380), (1920, 220)], 0.96, 265),
            ([(920, 520), (1140, 610), (1320, 550)], 0.82, 130),
        ],
        plateaus=[
            (1130, 420, 0.42, 260, 150),
            (1720, 620, 0.32, 240, 180),
        ],
        valleys=[
            ([(160, 740), (680, 755), (1140, 765), (1760, 755)], 0.68, 125),
        ],
        river_ribbons=[
            ([(0, 965), (420, 955), (840, 945), (1140, 912), (1480, 938), (1920, 960)], 118.0, "黄河"),
        ],
        walls=[[(265, 360), (265, 515)], [(265, 625), (265, 855)]],
        buildings=[("pass", 265, 515, "潼 关", "TANG", 136, 0, -28)],
        labels=[
            ("黄   河", 960, 955, 42, "#FFFFFF", 0),
            ("秦岭 · 崤山绝壁（南面险崖）", 1510, 260, 34, "#FFE8A8", 0),
            ("七十里狭道（河崖夹束）", 460, 845, 29, "#FFF8DF", 0),
        ],
        units=[
            (635, 762, "TANG", "mixed", False, 5, "column"),
            (1035, 768, "TANG", "mixed", False, 4, "column"),
            (1510, 768, "YAN_AN", "cavalry", True, 4, "horizontal"),
            (1140, 470, "YAN_AN", "infantry", True, 4, "horizontal"),
        ],
        banners=[
            (635, 795, "哥舒翰", "TANG", 148),
            (1510, 800, "崔乾祐", "YAN_AN", 148),
            (1315, 460, "南山伏兵", "YAN_AN", 140),
        ],
        arrows=[
            ((350, 735), (490, 760), "TANG", 11.0, 0.0, 0.85, None),
            ((1140, 530), (1085, 725), "YAN_AN", 13.0, -0.08, 1.0, None),
            ((1395, 768), (1215, 768), "YAN_AN", 13.0, 0.0, 1.0, None),
            ((950, 725), (360, 600), "TANG", 11.0, -0.16, 0.92, "残部仅八千余人退入潼关"),
        ],
        fire_at=(1185, 772),
    ),
    "B13": dict(
        title_parts=[("至德二载九月 · ", "#FFFFFF"), ("香积寺决战与收复长安", "#FFE04D")],
        subtitle="李嗣业陌刀前军列墙稳住正面，回纥叶护铁骑击破东原伏兵后绕袭燕军阵后",
        ridges=[
            ([(1660, 200), (1760, 540), (1860, 880)], 0.72, 220),
        ],
        plateaus=[
            (1550, 560, 0.44, 240, 320),
            (840, 220, 0.34, 210, 95),
        ],
        valleys=[
            ([(240, 100), (240, 540), (240, 980)], 0.55, 180),
        ],
        river_ribbons=[
            ([(205, 0), (235, 340), (210, 710), (240, 1080)], 42.0, "沣水"),
        ],
        walls=[],
        buildings=[("temple", 845, 195, "香积寺（神禾原）", "TANG", 122, 0, -24)],
        labels=[
            ("沣 水", 225, 480, 34, "#FFFFFF", 86),
            ("东 原 高 地", 1690, 865, 34, "#FFE8A8", 0),
        ],
        units=[
            (845, 735, "YAN_AN", "cavalry", True, 5, "horizontal"),
            (845, 450, "TANG", "heavy_inf", False, 5, "horizontal"),
            (500, 445, "TANG", "mixed", False, 4, "horizontal"),
            (1470, 650, "YAN_AN", "cavalry", True, 3, "horizontal"),
            (1470, 340, "UYGHUR", "cavalry", True, 4, "horizontal"),
        ],
        banners=[
            (640, 750, "安守忠", "YAN_AN", 148),
            (1045, 455, "李嗣业", "TANG", 148),
            (375, 455, "郭子仪", "TANG", 144),
            (1640, 340, "回纥叶护", "UYGHUR", 148),
        ],
        arrows=[
            ((845, 505), (845, 675), "TANG", 13.5, 0.0, 1.0, "陌刀如墙稳住正面"),
            ((1470, 400), (1470, 595), "UYGHUR", 12.0, 0.0, 0.85, "先破东侧伏兵"),
            ((1430, 705), (1025, 745), "UYGHUR", 14.0, -0.34, 1.0, "回纥绕后夹击燕营"),
        ],
        fire_at=None,
    ),
    "B05": dict(
        title_parts=[("天宝十五载五月 · ", "#FFFFFF"), ("嘉山大捷", "#FFE04D")],
        subtitle="郭子仪、李光弼合兵出井陉截断河北敌后，斩首四万级，史思明遁走博陵",
        ridges=[([(80, 100), (220, 540), (320, 980)], 0.96, 260)],
        plateaus=[(820, 620, 0.42, 180, 120)],
        valleys=[([(460, 480), (1120, 480), (1760, 480)], 0.65, 220)],
        river_ribbons=[([(480, 0), (880, 480), (1420, 1080)], 38.0, "滹沱水系")],
        bridges=[((825, 472), (935, 486), 34.0)],
        walls=[],
        buildings=[
            ("pass", 350, 510, "井陉土门关", "TANG", 130, 0, -26),
            ("city", 1480, 820, "博 陵", "YAN_AN", 118, 0, -24),
        ],
        labels=[("太 行 东 麓", 180, 760, 36, "#FFE8A8", 76)],
        units=[(820, 480, "TANG", "mixed", False, 5, "horizontal"), (1260, 560, "YAN_AN", "cavalry", True, 4, "horizontal")],
        banners=[(650, 500, "郭子仪", "TANG", 150), (1410, 570, "史思明", "YAN_AN", 150)],
        arrows=[((430, 520), (710, 495), "TANG", 12.0, 0.0, 0.85, None), ((930, 500), (1175, 550), "TANG", 14.0, 0.1, 1.0, "合兵大破史思明")],
        fire_at=None,
    ),
    "B10": dict(
        title_parts=[("至德二载二月 · ", "#FFFFFF"), ("太原保卫战", "#FFE04D")],
        subtitle="李光弼以不足万人掘地道陷敌土山，出击斩首七万余级，坚守晋阳不落",
        ridges=[([(60, 120), (160, 560), (220, 980)], 0.90, 220), ([(1740, 100), (1680, 540), (1640, 980)], 0.92, 220)],
        plateaus=[],
        valleys=[([(720, 100), (920, 540), (1040, 980)], 0.62, 280)],
        river_ribbons=[([(685, 0), (740, 540), (790, 1080)], 40.0, "汾水")],
        walls=[[(820, 400), (1080, 400), (1080, 680), (820, 680), (820, 400)]],
        buildings=[("capital", 950, 470, "太原晋阳（北都）", "TANG", 136, 0, -26)],
        labels=[],
        units=[(950, 620, "TANG", "infantry", False, 4, "horizontal"), (1380, 540, "YAN_AN", "mixed", True, 5, "horizontal")],
        banners=[(830, 620, "李光弼", "TANG", 150), (1510, 550, "史思明", "YAN_AN", 150)],
        arrows=[((1240, 540), (1100, 540), "YAN_AN", 11.0, 0.0, 0.7, None), ((1050, 580), (1290, 580), "TANG", 14.0, 0.18, 1.0, "地道奇袭大破十万围兵")],
        fire_at=None,
    ),
    "B11": dict(
        title_parts=[("至德二载十月 · ", "#FFFFFF"), ("睢阳保卫战", "#FFE04D")],
        subtitle="张巡许远率六千余众血战数月遮蔽江淮漕运，弹尽粮绝城破殉国",
        ridges=[],
        plateaus=[(520, 740, 0.28, 300, 140)],
        valleys=[([(200, 260), (960, 240), (1760, 200)], 0.55, 220)],
        river_ribbons=[([(0, 280), (860, 250), (1920, 200)], 36.0, "通济渠（汴河漕运）")],
        walls=[[(820, 410), (1100, 410), (1100, 690), (820, 690), (820, 410)]],
        buildings=[("city", 960, 480, "睢 阳 城", "TANG", 132, 0, -26)],
        labels=[("通济渠 → 保障江淮财赋北运", 1520, 245, 30, "#FFFFFF", -2)],
        units=[(960, 620, "TANG", "infantry", False, 3, "horizontal"), (480, 540, "YAN_AN", "mixed", False, 5, "horizontal")],
        banners=[(1095, 610, "张巡", "TANG", 150), (360, 540, "尹子奇", "YAN_AN", 150)],
        arrows=[((620, 520), (805, 520), "YAN_AN", 13.0, 0.0, 1.0, "十三万重围"), ((825, 595), (630, 595), "TANG", 11.0, -0.24, 0.9, "固守十月扼贼南下")],
        fire_at=None,
    ),
    "B15": dict(
        title_parts=[("乾元二年三月 · ", "#FFFFFF"), ("相州（邺城）九节度之溃", "#FFE04D")],
        subtitle="六十万官军无元帅统筹久围不克，史思明截粮道并在狂风骤起中击溃唐军",
        ridges=[([(60, 100), (180, 540), (240, 980)], 0.92, 230)],
        plateaus=[],
        valleys=[([(460, 500), (1140, 500), (1760, 500)], 0.58, 280)],
        river_ribbons=[([(260, 820), (960, 770), (1680, 800)], 38.0, "漳水 / 安阳河")],
        walls=[[(820, 410), (1080, 410), (1080, 650), (820, 650), (820, 410)]],
        buildings=[("city", 950, 470, "邺城（相州）", "YAN_AN", 128, 0, -26)],
        labels=[],
        units=[(600, 350, "TANG", "mixed", False, 5, "horizontal"), (950, 585, "YAN_AN", "infantry", True, 3, "horizontal"), (1440, 640, "YAN_SHI", "cavalry", True, 5, "horizontal")],
        banners=[(450, 360, "郭子仪", "TANG", 145), (1590, 650, "史思明", "YAN_SHI", 150)],
        arrows=[((1320, 600), (740, 380), "YAN_SHI", 14.0, -0.20, 1.0, "截粮道兼狂风突袭")],
        fire_at=None,
    ),
    "B16": dict(
        title_parts=[("乾元二年十月 · ", "#FFFFFF"), ("河阳三城保卫战", "#FFE04D")],
        subtitle="李光弼扼守南北双城与黄河中潬岛浮桥，以少胜多大破史思明十余万之众",
        ridges=[([(0, 140), (960, 120), (1920, 140)], 0.72, 180)],
        plateaus=[(960, 540, 0.36, 170, 95)],
        valleys=[([(0, 540), (960, 540), (1920, 540)], 0.55, 220)],
        river_ribbons=[([(0, 540), (960, 540), (1920, 540)], 92.0, "黄河天堑")],
        islands=[(960, 534, 165, 46, 0)],
        bridges=[
            ((960, 602), (960, 560), 28.0),
            ((960, 502), (960, 474), 28.0),
            ((1045, 602), (1045, 554), 26.0),
            ((1045, 514), (1045, 474), 26.0),
        ],
        walls=[[(870, 680), (1050, 680)], [(870, 395), (1050, 395)]],
        buildings=[
            ("pass", 960, 685, "北城", "TANG", 112, -95, 25),
            ("city", 960, 500, "中潬城", "TANG", 110, 95, 25),
            ("pass", 960, 320, "南城", "TANG", 112, -95, 25),
        ],
        labels=[("黄   河", 400, 540, 40, "#FFFFFF", 0)],
        units=[(960, 820, "TANG", "mixed", False, 4, "horizontal"), (1440, 335, "YAN_SHI", "cavalry", True, 5, "horizontal")],
        banners=[(780, 825, "李光弼", "TANG", 150), (1600, 345, "史思明", "YAN_SHI", 150)],
        arrows=[((1035, 760), (1325, 385), "TANG", 13.5, 0.16, 1.0, "出击斩首万余级")],
        fire_at=None,
    ),
    "B21": dict(
        title_parts=[("广德元年正月 · ", "#FFFFFF"), ("莫州—温泉栅平叛终局", "#FFE04D")],
        subtitle="田承嗣、李怀仙相继献城降唐，史朝义走投无路于温泉栅林中自缢，大乱平定",
        ridges=[([(0, 940), (960, 960), (1920, 940)], 0.85, 210)],
        plateaus=[],
        valleys=[([(200, 420), (1100, 480), (1750, 580)], 0.55, 220)],
        river_ribbons=[([(160, 340), (880, 460), (1640, 600)], 32.0, "白沟水系")],
        walls=[],
        buildings=[
            ("city", 540, 480, "莫 州", "FANZHEN", 122, 0, -24),
            ("capital", 1180, 600, "范 阳", "FANZHEN", 132, 0, -24),
        ],
        labels=[("温泉栅（叛乱平定）", 1640, 740, 32, "#FFE8A8", 0)],
        units=[(360, 445, "TANG", "mixed", False, 4, "horizontal"), (1640, 630, "YAN_SHI", "cavalry", False, 3, "horizontal")],
        banners=[(450, 505, "仆固瑒", "TANG", 145), (1055, 620, "李怀仙", "FANZHEN", 145)],
        arrows=[((1275, 645), (1545, 640), "FANZHEN", 13.0, -0.05, 1.0, "闭城拒纳并追击")],
        fire_at=None,
    ),
}


def draw_tactical_map(ax, bid, beat_key=None, *, detail_background=True, terrain_seed=None, arrow_progress=1.0):
    """按 B站科普立体浮雕＋帅旗样式绘制指定战役的 1920×1080 战术图。"""
    sc = SCENES.get(bid, SCENES["B06"])
    ax.set_xlim(0, W_PX)
    ax.set_ylim(0, H_PX)
    ax.set_aspect("equal")
    ax.axis("off")

    # 1. 3D 立体岩脊浮雕底图与抗锯齿矢量河道（固定战役种子消除帧间闪烁）
    if terrain_seed is None:
        seed = BATTLE_TERRAIN_SEEDS.get(bid, zlib.crc32(bid.encode("utf-8")) & 0xFFFF)
    else:
        seed = terrain_seed
    relief_rgb = _build_tactical_relief_rgb(sc, seed=seed, detail_background=detail_background)
    ax.imshow(relief_rgb, extent=[0, W_PX, 0, H_PX], origin="lower", interpolation="bilinear", zorder=0)
    rivers = sc.get("river_ribbons", [])
    for r_pts, r_w, _ in rivers:
        _draw_vector_tactical_river(ax, r_pts, r_w, zorder=6)
    if detail_background:
        _draw_tactical_river_texture(ax, rivers, seed)
    _draw_island_and_bridges(ax, sc)

    # 2. 短城墙段
    for pts in sc.get("walls", []):
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color="#1D1815", lw=px_to_pt(16.0), solid_capstyle="butt", zorder=12)
        ax.plot(xs, ys, color="#C2B8A8", lw=px_to_pt(10.0), solid_capstyle="butt", zorder=13)
        ax.plot(xs, ys, color="#6D665C", lw=px_to_pt(3.5), ls=(0, (6.0, 6.0)), solid_capstyle="butt", zorder=14)

    # 3. 建筑地标
    for b_kind, bx, by, bname, bfac, bw, ldx, ldy in sc.get("buildings", []):
        _place_building(ax, b_kind, bx, by, bname, bfac, width_px=bw, lbl_dx=ldx, lbl_dy=ldy, zorder=19)

    # 4. 精修兵种军阵
    for ux, uy, ufac, ut, uflip, ucnt, ulay in sc.get("units", []):
        _place_unit_group(ax, ux, uy, ufac, ut, flip=uflip, count=ucnt, layout=ulay, unit_h=56, alpha=1.0, zorder=22)

    # 5. 竖幅火焰牙边主将帅旗
    for fx, fy, fname, ffac, fh in sc.get("banners", []):
        _place_banner(ax, fx, fy, fname, ffac, h_px=fh, zorder=26)

    # 6. 高饱和双描边战术箭头
    aprog = float(np.clip(arrow_progress, 0.0, 1.0))
    for p1, p2, afac, sw, rad, al, albl in sc.get("arrows", []):
        st = FACTION_STYLE[afac]
        curve = draw_double_stroked_arrow(
            ax, p1, p2, st["arrow"], shaft_px=sw, head_w_px=sw * 2.4, head_l_px=sw * 2.6,
            rad=rad, alpha=al, zorder=28, progress=aprog,
        )
        if albl and aprog >= 0.55:
            lbl_al = min(1.0, (aprog - 0.55) / 0.30) * al
            mid = curve[len(curve) // 2]
            dy_off = 165.0 if bid == "B15" else (-38.0 if (afac == "TANG" and bid == "B06") or (afac == "YAN_AN" and bid == "B11") else 34.0)
            ax.text(
                mid[0], mid[1] + dy_off, albl,
                fontproperties=FONT_BOLD, fontsize=px_to_pt(28), color="#FFFFFF", alpha=lbl_al,
                ha="center", va="center", zorder=40,
                path_effects=text_outline(4.0, "#12100E"),
            )

    # 7. 火攻浓烟（灵宝西原）
    if sc.get("fire_at"):
        fx_x, fx_y = sc["fire_at"]
        _draw_tactical_fire_plume(ax, fx_x, fx_y)

    # 8. 地形名与河流名（白/金字粗黑边）
    for ltxt, lx, ly, fs, col, rot in sc.get("labels", []):
        ax.text(
            lx, ly, ltxt,
            fontproperties=FONT_BOLD, fontsize=px_to_pt(fs), color=col,
            ha="center", va="center", rotation=rot, zorder=38,
            path_effects=text_outline(4.2, "#12100E"),
        )

    # 9. B站科普顶部标题 + 底部大字幕
    draw_bilibili_hud(ax, sc["title_parts"], sc["subtitle"])
