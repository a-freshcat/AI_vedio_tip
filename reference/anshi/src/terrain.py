# -*- coding: utf-8 -*-
"""《安史之乱》B站科普风格三维立体浮雕底图、古海岸线与全域势力疆界生成引擎。
特征：
1. 完整华北—中原—关中 16:9 宏观格局（LON 104.8~123.5, LAT 31.9~40.4），涵盖黄河几字弯与下游、
   渤海湾与唐代古海岸线、太行/秦岭/吕梁/恒山/燕山/崤山/泰山；
2. 锐利三维山脊浮雕（Ridged Multifractal 岩脊褶皱 + 西北 315° 光源高精度 Hillshade + 河谷下切 + 平原平滑）；
3. 全域无缝势力划分：以山脉关隘加权距离场自然贴合太行/秦岭/黄河地形，正片叠底叠加唐（暖赭红）、
   燕（冷靛蓝）疆域色块，并绘制「醒目白光晕 + 深墨实线」双层战线边界；
4. 增绘唐代渤海湾/苏北「古海岸线」浅灰蓝对比带与深海质感。
"""
import math
import numpy as np
from matplotlib.path import Path as MplPath
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt, gaussian_filter

from surface_texture import resize_field, steerable_slope_fields, texture_field

LON0, LON1 = 104.8, 123.5
LAT0, LAT1 = 31.9, 40.4

# 现代海岸与黄渤海大面
SEA_POLYS = [
    [
        (125.0, 29.0), (121.8, 30.8), (121.9, 31.4), (121.5, 31.9),
        (120.7, 32.8), (120.1, 33.9), (119.5, 34.6), (119.2, 35.1),
        (119.8, 35.6), (120.4, 36.1), (121.3, 36.7), (122.4, 37.1),
        (122.6, 37.4), (121.4, 37.55), (120.75, 37.82), (120.1, 37.4),
        (119.3, 37.15), (118.9, 37.4), (118.4, 37.9), (117.7, 38.5),
        (117.65, 39.0), (118.3, 39.15), (119.0, 39.4), (119.6, 39.9),
        (120.5, 40.5), (121.4, 41.2), (125.0, 41.2), (125.0, 29.0),
    ]
]

# 唐代渤海湾—黄河三角洲—苏北浅滩「古海岸线」退缩对比带（展现古代海湾更深入内陆）
ANCIENT_COAST_POLYS = [
    [
        # 天津—沧州—利津一带唐代西退古海岸带
        (118.6, 37.25), (118.0, 37.55), (117.35, 38.05), (117.15, 38.65),
        (117.30, 39.15), (117.95, 39.35), (118.95, 39.55), (119.55, 39.95),
        (119.6, 39.9), (119.0, 39.4), (118.3, 39.15), (117.65, 39.0),
        (117.7, 38.5), (118.4, 37.9), (118.9, 37.4), (119.3, 37.15), (118.6, 37.25),
    ],
    [
        # 盐城苏北古滩涂微弧退缩带
        (120.7, 32.8), (120.1, 33.9), (119.5, 34.6), (119.45, 34.45),
        (119.85, 33.80), (120.42, 32.75), (120.7, 32.8),
    ],
]

# 主要水系（name -> (pts, width_px, is_major)）
RIVER_LINES = {
    "黄河": (
        [
            (105.6, 37.3), (106.2, 38.0), (106.7, 38.9), (106.9, 39.8), (108.5, 40.55),
            (110.8, 40.2), (111.1, 39.2), (110.7, 38.0), (110.5, 36.7), (110.35, 35.5),
            (110.28, 34.64), (110.65, 34.60), (111.15, 34.76), (112.10, 34.88), (112.79, 34.86),
            (113.40, 34.92), (114.00, 35.15), (114.50, 35.50), (114.95, 35.90),
            (115.40, 36.30), (115.90, 36.90), (116.40, 37.45), (116.85, 37.95),
            (117.30, 38.35), (117.75, 38.55),
        ],
        4.6, True,
    ),
    "渭水": ([(105.5, 34.55), (107.1, 34.36), (108.1, 34.30), (108.95, 34.38), (109.75, 34.52), (110.28, 34.64)], 2.8, True),
    "汾水": ([(112.1, 38.4), (112.47, 37.70), (112.1, 36.9), (111.5, 36.1), (110.9, 35.6), (110.4, 35.55)], 2.2, False),
    "洛水": ([(110.3, 34.1), (111.3, 34.35), (112.44, 34.65), (113.0, 34.82)], 2.0, False),
    "滹沱河": ([(113.2, 39.05), (113.9, 38.45), (114.25, 38.08), (114.65, 38.15), (115.4, 38.28), (116.2, 38.65), (116.8, 38.90)], 2.1, False),
    "漳水": ([(113.2, 36.45), (113.8, 36.32), (114.35, 36.15), (114.8, 36.22), (115.2, 36.45)], 1.9, False),
    "淮水": ([(113.4, 32.4), (114.6, 32.35), (115.8, 32.45), (117.1, 32.75), (118.4, 33.05), (119.5, 33.6), (120.2, 33.9)], 2.6, True),
    "汉水": ([(106.8, 33.05), (109.0, 32.7), (110.8, 32.5), (112.14, 32.02), (112.8, 31.3)], 2.5, False),
    "白沟·海河": ([(114.8, 38.95), (115.7, 39.05), (116.4, 39.05), (117.2, 39.12), (117.65, 39.02)], 2.0, False),
    "泾水": ([(106.4, 35.55), (107.4, 35.05), (108.2, 34.70), (108.95, 34.42)], 1.8, False),
}

CANALS = {
    "通济渠": [(112.44, 34.67), (113.65, 34.76), (114.35, 34.80), (115.62, 34.38), (116.9, 33.8), (118.52, 33.03), (119.4, 32.4)],
    "永济渠": [(113.0, 35.15), (114.1, 35.5), (115.15, 36.28), (115.8, 37.0), (116.4, 37.9), (117.0, 39.0), (116.45, 39.8)],
}

# 山脉脊线与丘陵台原（用于构建立体浮雕高度场与跨山阻力场）
HILL_PLATEAUS = [
    # 陕北—陇东黄土高原
    ([(106.2, 35.2), (107.8, 36.1), (109.4, 37.2), (110.1, 38.6), (108.0, 38.2), (106.0, 36.6)], 0.34, 1.35),
    # 晋中南太行山前坡与上党高原
    ([(112.0, 35.4), (112.7, 36.5), (113.1, 38.0)], 0.42, 0.78),
    # 豫西熊耳—伏牛丘陵
    ([(110.5, 34.45), (111.5, 34.30), (112.7, 34.00), (113.3, 33.50)], 0.38, 0.56),
    # 山东泰沂山地与胶东丘陵
    ([(116.8, 35.85), (117.7, 36.20), (118.9, 36.20), (120.5, 36.90), (121.6, 37.25)], 0.36, 0.72),
    # 大别山余脉与桐柏丘陵
    ([(113.3, 32.45), (114.8, 31.90), (116.5, 31.50)], 0.34, 0.62),
]

MOUNTAIN_SPINES = [
    # 太行山脉（纵贯南北的壮阔山脊墙）
    ([(112.3, 35.15), (113.15, 35.95), (113.65, 37.00), (113.95, 38.10), (114.35, 39.10), (115.10, 39.85)], 1.00, 0.44),
    # 恒山·军都·燕山
    ([(113.3, 39.25), (114.4, 39.75), (115.5, 40.15), (116.8, 40.35), (118.4, 40.25), (120.0, 40.05)], 0.96, 0.45),
    # 吕梁山
    ([(110.95, 35.80), (111.20, 37.00), (111.55, 38.20), (112.25, 39.15), (113.35, 39.30)], 0.92, 0.42),
    # 秦岭（东西横亘关中南侧）
    ([(105.2, 34.05), (107.0, 33.85), (108.8, 33.78), (110.05, 34.15), (110.85, 34.32)], 1.05, 0.44),
    # 崤山·熊耳·伏牛山
    ([(110.3, 34.42), (111.1, 34.36), (111.85, 34.18), (112.55, 33.82), (113.25, 33.42)], 0.78, 0.34),
    # 嵩山
    ([(112.6, 34.48), (113.1, 34.48)], 0.62, 0.25),
    # 泰山主脊
    ([(117.0, 36.18), (117.8, 36.26), (118.5, 36.02)], 0.66, 0.32),
    # 大别山
    ([(113.6, 32.35), (114.8, 31.70), (116.1, 31.20)], 0.80, 0.42),
    # 大巴山·米仓山
    ([(105.5, 32.75), (107.5, 32.35), (109.5, 31.95)], 0.92, 0.55),
]

VALLEY_CARVES = [
    # 关中渭河平川
    ([(106.9, 34.42), (108.9, 34.36), (110.30, 34.62)], 0.68, 0.36),
    # 汾河谷地（太原—晋南）
    ([(111.3, 35.75), (112.1, 36.8), (112.47, 37.75)], 0.68, 0.30),
    # 华北平原平缓区压平
    ([(114.8, 35.0), (115.6, 36.8), (116.4, 38.6), (117.2, 39.4)], 0.82, 1.45),
    # 黄淮平原
    ([(114.3, 33.8), (116.8, 33.5), (119.0, 32.9)], 0.82, 1.30),
    # 南阳盆地
    ([(111.8, 32.6), (112.53, 33.02), (113.1, 33.2)], 0.62, 0.45),
]

# 宏大地形标注
MOUNTAIN_DISPLAY_LABELS = [
    (113.65, 37.35, "太  行  山", 72),
    (107.45, 33.62, "秦   岭", -4),
    (111.20, 37.35, "吕 梁 山", 76),
    (114.25, 39.55, "恒  山", 12),
    (117.10, 40.05, "燕  山", -4),
    (117.75, 36.22, "泰 山", 8),
    (111.65, 34.05, "崤山·伏牛", -18),
]

RIVER_DISPLAY_LABELS = [
    (110.58, 36.90, "黄 河", 84),
    (115.85, 36.85, "黄河", 44),
    (108.05, 34.48, "渭 水", -4),
    (111.90, 36.60, "汾 水", 62),
    (116.25, 37.85, "永济渠", 60),
    (116.95, 33.55, "通济渠", -22),
    (116.40, 32.45, "淮 水", 8),
]


def fit_aspect_bounds(lon_min, lon_max, lat_min, lat_max):
    """将经纬度包围盒校正至严格 16:9 无拉伸比例。"""
    lon_c = 0.5 * (lon_min + lon_max)
    lat_c = 0.5 * (lat_min + lat_max)
    cos_c = math.cos(math.radians(lat_c))
    target_ratio = 16.0 / 9.0
    dlon = lon_max - lon_min
    dlat = lat_max - lat_min
    cur_ratio = (dlon * cos_c) / max(dlat, 1e-6)
    if cur_ratio < target_ratio:
        dlon = (dlat * target_ratio) / cos_c
    else:
        dlat = (dlon * cos_c) / target_ratio
    return (lon_c - 0.5 * dlon, lon_c + 0.5 * dlon, lat_c - 0.5 * dlat, lat_c + 0.5 * dlat)


def smooth_polyline(pts, steps=8):
    if len(pts) < 3:
        return list(pts)
    ext = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = map(np.array, ext[i - 1 : i + 3])
        for j in range(steps):
            t = j / float(steps)
            t2, t3 = t * t, t * t * t
            q = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append((float(q[0]), float(q[1])))
    out.append(pts[-1])
    return out


def lonlat_to_px(lon, lat, bounds, W=1920, H=1080):
    lon0, lon1, lat0, lat1 = bounds
    x = (np.asarray(lon) - lon0) / (lon1 - lon0) * W
    y = (np.asarray(lat) - lat0) / (lat1 - lat0) * H
    if np.ndim(lon) == 0 and np.ndim(lat) == 0:
        return float(x), float(y)
    return x, y


def _dist_to_polyline(GX, GY, pts):
    d2 = np.full_like(GX, 1e9)
    for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
        dx, dy = x2 - x1, y2 - y1
        seg2 = dx * dx + dy * dy + 1e-12
        t = np.clip(((GX - x1) * dx + (GY - y1) * dy) / seg2, 0.0, 1.0)
        px, py = x1 + t * dx, y1 + t * dy
        d2 = np.minimum(d2, (GX - px) ** 2 + (GY - py) ** 2)
    return np.sqrt(d2)


def ridged_multifractal_2d(H, W, seed=755, octaves=((18.0, 0.45), (8.5, 0.30), (4.0, 0.17), (1.8, 0.08))):
    """生成 1.0 - |noise| 山脊分形肌理（使山地具有真实锐利沟壑感）。"""
    rng = np.random.default_rng(seed)
    acc = np.zeros((H, W), dtype=float)
    w_sum = 0.0
    for sig, w in octaves:
        n = gaussian_filter(rng.normal(0.0, 1.0, (H, W)), sigma=sig)
        mx = np.max(np.abs(n)) + 1e-9
        ridge = 1.0 - np.abs(n / mx) ** 0.85
        acc += w * ridge
        w_sum += w
    return np.clip(acc / max(w_sum, 1e-9), 0.0, 1.0)


def compute_hillshade(elev, azimuth_deg=315.0, altitude_deg=38.0, z_factor=9.5):
    """计算高反差三维浮雕明暗值 [0..1] 与坡度遮蔽。"""
    gy, gx = np.gradient(elev * z_factor)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az = math.radians(azimuth_deg)
    alt = math.radians(altitude_deg)
    hs = np.clip(
        math.sin(alt) * np.cos(slope) + math.cos(alt) * np.sin(slope) * np.cos(az - aspect),
        0.08, 1.0,
    )
    return hs, slope


def build_relief_terrain(bounds=None, W=1920, H=1080):
    """在指定视口生成高精 3D 岩脊浮雕地形、古海岸线与海陆掩膜。"""
    if bounds is None:
        bounds = fit_aspect_bounds(LON0, LON1, LAT0, LAT1)
    lon0, lon1, lat0, lat1 = bounds
    # 先在 960×540 生成三维高度场与浮雕以保持极高速度，再双三次放大至 1920×1080
    sw, sh = 960, 540
    lons = np.linspace(lon0, lon1, sw)
    lats = np.linspace(lat0, lat1, sh)
    GX, GY = np.meshgrid(lons, lats)

    pts = np.column_stack([GX.ravel(), GY.ravel()])
    sea = np.zeros(len(pts), dtype=bool)
    for poly in SEA_POLYS:
        sea |= MplPath(poly).contains_points(pts)
    sea_mask_s = sea.reshape(sh, sw)
    land_mask_s = ~sea_mask_s

    anc = np.zeros(len(pts), dtype=bool)
    for poly in ANCIENT_COAST_POLYS:
        anc |= MplPath(poly).contains_points(pts)
    ancient_belt_s = anc.reshape(sh, sw) & land_mask_s

    elev = np.full((sh, sw), 0.03, dtype=float)
    for spine, h, w in HILL_PLATEAUS:
        d = _dist_to_polyline(GX, GY, smooth_polyline(spine, 4))
        elev = np.maximum(elev, h * np.exp(-(d / w) ** 2))
    for spine, depth, w in VALLEY_CARVES:
        d = _dist_to_polyline(GX, GY, smooth_polyline(spine, 4))
        elev *= (1.0 - depth * np.exp(-(d / w) ** 2)).clip(0.08, 1.0)
    for spine, h, w in MOUNTAIN_SPINES:
        d = _dist_to_polyline(GX, GY, smooth_polyline(spine, 5))
        elev = np.maximum(elev, h * np.exp(-(d / w) ** 2))

    # 河谷与关隘狭槽下切
    for rname, (rpts, _, is_maj) in RIVER_LINES.items():
        d = _dist_to_polyline(GX, GY, rpts)
        gw = 0.20 if rname == "黄河" else (0.17 if is_maj else 0.13)
        carve = np.where(elev > 0.28, 0.72 if rname == "黄河" else 0.56, 0.30)
        elev *= (1.0 - carve * np.exp(-(d / gw) ** 2)).clip(0.02, 1.0)

    # 仅在丘陵和山地叠加锐利岩脊分形凹凸，保持平原顺滑
    ridge_tex = ridged_multifractal_2d(sh, sw, seed=755)
    mtn_weight = np.clip((elev - 0.14) / 0.26, 0.0, 1.0)
    elev = elev * (1.0 - 0.42 * mtn_weight) + (elev * ridge_tex * 1.45) * (0.42 * mtn_weight)
    elev = gaussian_filter(elev, sigma=0.75)
    elev = np.clip(elev, 0.0, 1.0)
    elev[~land_mask_s] = 0.0

    hs, slope = compute_hillshade(elev, azimuth_deg=315.0, altitude_deg=38.0, z_factor=11.5)
    # 融合局部微坡度对比（强三维凹凸）
    relief_mod = np.clip(0.56 + 0.62 * hs - 0.14 * np.clip(elev, 0, 1), 0.38, 1.18)

    # 升采样至目标 1920×1080
    def _up(arr, is_bool=False):
        if is_bool:
            im = Image.fromarray((arr.astype(np.uint8) * 255), mode="L").resize((W, H), Image.Resampling.BILINEAR)
            return np.asarray(im) > 127
        im = Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), mode="L").resize((W, H), Image.Resampling.BICUBIC)
        return np.asarray(im, dtype=float) / 255.0

    elev_f = np.asarray(
        Image.fromarray(np.clip(elev * 255.0, 0, 255).astype(np.uint8), mode="L").resize((W, H), Image.Resampling.BICUBIC),
        dtype=float,
    ) / 255.0
    rmod_f = np.asarray(
        Image.fromarray(np.clip((relief_mod - 0.35) / 0.90 * 255.0, 0, 255).astype(np.uint8), mode="L").resize((W, H), Image.Resampling.BICUBIC),
        dtype=float,
    ) / 255.0 * 0.90 + 0.35

    land_f = _up(land_mask_s, is_bool=True)
    anc_f = _up(ancient_belt_s, is_bool=True)

    lons_f = np.linspace(lon0, lon1, W)
    lats_f = np.linspace(lat0, lat1, H)
    GXF, GYF = np.meshgrid(lons_f, lats_f)

    return dict(
        bounds=bounds, W=W, H=H,
        lons=lons_f, lats=lats_f, GX=GXF, GY=GYF,
        land=land_f, ancient_coast=anc_f, elev=elev_f, relief_mod=rmod_f,
    )


# 势力在三维浮雕上呈现的基础染色（参考图样式：唐=暖赭橙红、燕=冷天/靛蓝、史燕=深靛蓝、藩镇=暖琥珀褐）
FACTION_TERRITORY_RGB = {
    "TANG": (222, 134, 96),       # 暖朱砂赭红调，正片叠底后贴近参考图左侧暖橘红
    "YAN_AN": (118, 152, 224),    # 鲜明冷群青天蓝调，正片叠底后贴近参考图右侧蓝区
    "YAN_SHI": (98, 132, 206),    # 深海群青蓝
    "FANZHEN": (208, 158, 92),    # 琥珀土黄
    "UYGHUR": (92, 174, 158),
}


def _geographic_anchors(control_dict):
    """补充未设城池的地理边界锚点（陇右/朔方、山西高原、辽西、江南淮南、东齐半岛），使战线自然贴合山河大势。"""
    ty = control_dict.get("TAIYUAN", "TANG")
    fy = control_dict.get("FANYANG", "YAN_AN")
    py = control_dict.get("PINGYUAN", "TANG")
    extra = [
        (105.2, 39.2, "TANG"), (105.4, 36.8, "TANG"), (105.2, 34.0, "TANG"), (105.5, 32.1, "TANG"),
        (108.5, 32.0, "TANG"), (112.0, 31.8, "TANG"), (116.5, 31.9, "TANG"), (119.5, 32.2, "TANG"),
        # 河东山西高原（随太原归属，确保战线紧贴太行西脊）
        (112.8, 39.1, ty), (112.9, 36.2, ty), (111.5, 36.1, ty),
        # 齐鲁半岛
        (120.8, 36.9, "TANG"), (118.4, 36.6, py if py in ("YAN_AN", "YAN_SHI") else "TANG"),
        # 辽西幽蓟东北缘
        (118.0, 39.9, fy), (119.8, 40.3, fy),
    ]
    return extra


def _macro_relief_material(elev, seed=756):
    """生成沿山脉走势自适应的坡脊/浅沟/坡麓浮雕及平原微土色变化。"""
    rng = np.random.default_rng(seed)
    small_elev = elev[::2, ::2].astype(np.float32)
    shape = small_elev.shape

    lowland = 1.0 - np.clip((small_elev - 0.10) / 0.19, 0.0, 1.0)
    foothill = np.exp(-((small_elev - 0.19) / 0.11) ** 2) * np.clip((small_elev - 0.05) / 0.08, 0.0, 1.0)
    upland = np.clip((small_elev - 0.15) / 0.36, 0.0, 1.0)

    # 沿局部山体坡向生成顺坡支脉/浅沟（downslope）与沿脉走向脊褶（contour）
    base_smooth = gaussian_filter(small_elev, sigma=3.5)
    gy, gx = np.gradient(base_smooth)
    gx_s = gaussian_filter(gx, sigma=2.5)
    gy_s = gaussian_filter(gy, sigma=2.5)
    spurs, strike = steerable_slope_fields(rng, shape, gx_s, gy_s, sigma_along=10.5, sigma_across=1.65)

    soil_macro = texture_field(rng, shape, (16.0, 26.0))
    soil_mid = texture_field(rng, shape, (6.0, 9.0))
    rock = texture_field(rng, shape, (2.8, 3.5))
    grain = texture_field(rng, shape, (0.85, 1.3))

    # 坡麓微凹浅沟与凸起山脊明暗区分
    curv = gaussian_filter(small_elev, sigma=5.5) - gaussian_filter(small_elev, sigma=1.4)
    piedmont_ao = np.clip(curv * 14.0, -0.045, 0.055) * (0.45 * upland + 0.80 * foothill)

    rough_elev = (
        small_elev
        + upland * (0.032 * spurs + 0.022 * strike + 0.014 * rock + 0.007 * grain)
        + foothill * (0.020 * spurs + 0.008 * strike + 0.006 * rock)
    )
    shade, _ = compute_hillshade(small_elev, z_factor=11.5)
    rough_shade, _ = compute_hillshade(rough_elev, z_factor=11.5)

    material = (
        1.0
        + 0.038 * lowland * soil_macro
        + 0.014 * lowland * soil_mid
        + 0.010 * grain
        + 0.020 * rock * upland
        + 0.016 * spurs * (0.65 * upland + 0.55 * foothill)
        - piedmont_ao
        + 0.58 * (rough_shade - shade)
    )
    earth_shift = resize_field((lowland * (0.65 * soil_macro + 0.35 * soil_mid)).astype(np.float32), elev.shape)
    return np.clip(resize_field(material, elev.shape), 0.74, 1.28), earth_shift


def _finish_macro_water(base_rgb, sea, dist_coast, seed=757):
    """在黄渤海叠加近岸浅水色阶、海底坡折过渡带与稀疏水纹光泽（保持岸线零偏移）。"""
    rng = np.random.default_rng(seed)
    shape = dist_coast.shape
    texture_shape = tuple((size + 1) // 2 for size in shape)
    drift = resize_field(texture_field(rng, texture_shape, (7.0, 26.0)), shape)[sea]
    ripples = resize_field(texture_field(rng, texture_shape, (1.4, 10.5)), shape)[sea]
    glints = np.clip(ripples * 1.15 + 0.35 * drift - 0.35, 0.0, 1.0) ** 2

    distance = dist_coast[sea]
    # 两级近岸浅水色阶（贴岸极浅陆架 + 48px 外延缓坡阶）与连续深海渐变
    inner_shoal = np.exp(-((distance - 14.0) / 16.0) ** 2)
    shelf = np.exp(-(distance / 122.0) ** 1.45)
    terrace = 0.5 * (1.0 + np.tanh((46.0 - distance) / 10.5))

    base_rgb[sea] += shelf[:, None] * np.array([6.0, 15.0, 21.0])
    base_rgb[sea] += terrace[:, None] * np.array([7.5, 13.5, 14.0])
    base_rgb[sea] += inner_shoal[:, None] * np.array([10.0, 15.0, 10.0])

    sheen = (2.2 + 3.6 * shelf) * drift + (1.4 + 3.8 * terrace) * ripples + 9.5 * glints * (0.35 + 0.65 * shelf)
    base_rgb[sea] += sheen[:, None] * np.array([0.72, 0.90, 1.0])


FACTION_KEYS = ("TANG", "YAN_AN", "YAN_SHI", "FANZHEN")


def compute_smoothed_faction_scores(relief, cities, control_dict, owner_overrides=None):
    """计算低分辨率(480×270)地形阻隔加权势力连续分数场，可供静态出图或帧间插值。"""
    bounds = relief["bounds"]
    elev = relief["elev"]
    qw, qh = 480, 270
    lon0, lon1, lat0, lat1 = bounds
    cache = relief.setdefault("_score_grid_cache", {})
    if not cache:
        qlons = np.linspace(lon0, lon1, qw)
        qlats = np.linspace(lat0, lat1, qh)
        QGX, QGY = np.meshgrid(qlons, qlats)
        elev_q = np.asarray(
            Image.fromarray(np.clip(elev * 255.0, 0, 255).astype(np.uint8), mode="L").resize((qw, qh), Image.Resampling.BILINEAR),
            dtype=float,
        ) / 255.0
        cache["QGX"], cache["QGY"] = QGX, QGY
        cache["mtn_barrier"] = 1.0 - 0.55 * np.clip((elev_q - 0.30) / 0.45, 0.0, 1.0)
        cache["cos_lat"] = math.cos(math.radians(0.5 * (lat0 + lat1)))
    QGX, QGY = cache["QGX"], cache["QGY"]
    mtn_barrier = cache["mtn_barrier"]
    cos_lat = cache["cos_lat"]

    cdict = dict(control_dict)
    if owner_overrides:
        cdict.update(owner_overrides)

    scores = np.zeros((len(FACTION_KEYS), qh, qw), dtype=float)
    fidx = {k: i for i, k in enumerate(FACTION_KEYS)}

    for c in cities:
        if not c["control_tracked"]:
            continue
        fk = cdict.get(c["city_id"])
        if fk not in fidx:
            continue
        dx = (QGX - c["lon"]) * cos_lat
        dy = QGY - c["lat"]
        d2 = dx * dx + dy * dy
        imp_w = 1.0 + 0.14 * c["importance"]
        field = imp_w * mtn_barrier * np.exp(-d2 / (1.55 ** 2))
        scores[fidx[fk]] = np.maximum(scores[fidx[fk]], field)

    for alon, alat, afk in _geographic_anchors(cdict):
        if afk not in fidx:
            continue
        dx = (QGX - alon) * cos_lat
        dy = QGY - alat
        d2 = dx * dx + dy * dy
        field = 1.05 * np.exp(-d2 / (2.5 ** 2))
        scores[fidx[afk]] = np.maximum(scores[fidx[afk]], field)

    return np.array([gaussian_filter(scores[i], sigma=3.0) for i in range(len(FACTION_KEYS))])


def _get_macro_static_layers(relief, detail_background=True):
    """按 detail_background 缓存静态陆地材质、海面、古海岸渐变及各阵营陆地色板。"""
    cache = relief.setdefault("_macro_static_cache", {})
    key = bool(detail_background)
    if key in cache:
        return cache[key]

    W, H = relief["W"], relief["H"]
    land = relief["land"]
    elev = relief["elev"]
    rmod = relief["relief_mod"]
    anc = relief["ancient_coast"]

    earth_shift = None
    if detail_background:
        mat, earth_shift = _macro_relief_material(elev)
        rmod_eff = rmod * mat
    else:
        rmod_eff = rmod

    rock_mix = np.clip((elev - 0.34) / 0.50, 0.0, 0.46)
    faction_land = np.zeros((len(FACTION_KEYS), H, W, 3), dtype=np.float32)
    for i, fk in enumerate(FACTION_KEYS):
        tr, tg, tb = FACTION_TERRITORY_RGB[fk]
        r_ch = tr * (1.0 - rock_mix) + 214.0 * rock_mix
        g_ch = tg * (1.0 - rock_mix) + 206.0 * rock_mix
        b_ch = tb * (1.0 - rock_mix) + 196.0 * rock_mix
        faction_land[i, land, 0] = r_ch[land] * rmod_eff[land]
        faction_land[i, land, 1] = g_ch[land] * rmod_eff[land]
        faction_land[i, land, 2] = b_ch[land] * rmod_eff[land]

    if earth_shift is not None:
        es = (earth_shift[land, None] * np.array([3.6, 2.6, -2.4])).astype(np.float32)
        faction_land[:, land, :] += es[None, :, :]

    near_water_delta = None
    if detail_background:
        near_water = np.exp(-distance_transform_edt(land)[anc] / 44.0)
        near_water_delta = (near_water[:, None] * np.array([-8.5, 2.0, 7.0])).astype(np.float32)

    # 海洋静态图（与势力控制完全无关，可整段视频复用）
    sea = ~land
    dist_coast = distance_transform_edt(sea)
    sea_depth = np.clip(dist_coast / 55.0, 0.0, 1.0)
    sea_canvas = np.zeros((H, W, 3), dtype=float)
    sea_canvas[sea, 0] = 56.0 * (1.0 - sea_depth[sea]) + 18.0 * sea_depth[sea]
    sea_canvas[sea, 1] = 104.0 * (1.0 - sea_depth[sea]) + 56.0 * sea_depth[sea]
    sea_canvas[sea, 2] = 152.0 * (1.0 - sea_depth[sea]) + 102.0 * sea_depth[sea]
    if detail_background:
        _finish_macro_water(sea_canvas, sea, dist_coast)
    sea_glow = np.clip(1.0 - np.maximum(0.0, dist_coast - 1.2) / 5.5, 0.0, 1.0) * 0.65
    sea_canvas[sea] = sea_canvas[sea] * (1.0 - sea_glow[sea, None]) + 232.0 * sea_glow[sea, None]
    coast_edge = sea & (dist_coast <= 2.4)
    sea_canvas[coast_edge] = [26.0, 24.0, 22.0]

    layer = dict(
        faction_land=faction_land,
        near_water_delta=near_water_delta,
        sea=sea,
        sea_rgb=sea_canvas[sea].astype(np.float32),
        land=land,
        anc=anc,
        W=W,
        H=H,
    )
    cache[key] = layer
    return layer


def compose_macro_from_scores(relief, smoothed, *, detail_background=True):
    """由已平滑连续分数场极速合成 1920×1080 宏观势力底图。"""
    st = _get_macro_static_layers(relief, detail_background=detail_background)
    W, H = st["W"], st["H"]
    land = st["land"]
    anc = st["anc"]
    sea = st["sea"]

    winner_map = np.zeros((len(FACTION_KEYS), H, W), dtype=float)
    for i in range(len(FACTION_KEYS)):
        smax = max(float(smoothed[i].max()), 1e-6)
        im_s = Image.fromarray(np.clip(smoothed[i] / smax * 255.0, 0, 255).astype(np.uint8), mode="L").resize((W, H), Image.Resampling.BICUBIC)
        winner_map[i] = np.asarray(im_s, dtype=float) * (smax / 255.0)
    winner = np.argmax(winner_map, axis=0)

    base_rgb = np.zeros((H, W, 3), dtype=float)
    for i in range(len(FACTION_KEYS)):
        mask = land & (winner == i)
        if mask.any():
            base_rgb[mask] = st["faction_land"][i, mask]

    base_rgb[anc, 0] = base_rgb[anc, 0] * 0.25 + 178.0 * 0.75
    base_rgb[anc, 1] = base_rgb[anc, 1] * 0.25 + 196.0 * 0.75
    base_rgb[anc, 2] = base_rgb[anc, 2] * 0.25 + 212.0 * 0.75
    if st["near_water_delta"] is not None:
        base_rgb[anc] += st["near_water_delta"]

    border_px = np.zeros((H, W), dtype=bool)
    border_px[:, :-1] |= (winner[:, :-1] != winner[:, 1:]) & land[:, :-1] & land[:, 1:]
    border_px[:-1, :] |= (winner[:-1, :] != winner[1:, :]) & land[:-1, :] & land[1:, :]
    dist_border = distance_transform_edt(~border_px)

    white_glow = np.clip(1.0 - np.maximum(0.0, dist_border - 2.0) / 6.5, 0.0, 1.0) * 0.88
    white_glow[~land] = 0.0
    base_rgb = base_rgb * (1.0 - white_glow[..., None]) + 250.0 * white_glow[..., None]

    dark_line = np.clip(1.0 - np.maximum(0.0, dist_border - 0.8) / 1.8, 0.0, 1.0) * 0.94
    dark_line[~land] = 0.0
    base_rgb = base_rgb * (1.0 - dark_line[..., None]) + np.array([28.0, 24.0, 22.0]) * dark_line[..., None]

    base_rgb[sea] = st["sea_rgb"]
    return np.clip(base_rgb, 0, 255).astype(np.uint8), winner


def compose_macro_map_rgb(relief, cities, control_dict, owner_overrides=None, *, detail_background=True, smoothed_scores=None):
    """生成带 3D 浮雕山体、无缝势力配色、双层白光晕战线、古海岸线与深海光泽的全幅 1920×1080 地图。"""
    if smoothed_scores is None:
        smoothed_scores = compute_smoothed_faction_scores(relief, cities, control_dict, owner_overrides=owner_overrides)
    return compose_macro_from_scores(relief, smoothed_scores, detail_background=detail_background)
