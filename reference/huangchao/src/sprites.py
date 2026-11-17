# -*- coding: utf-8 -*-
"""高清晰兵棋小人精灵（4倍超采样抗锯齿 RGBA）：
- cavalry: 奔马骑士（分段马腿马蹄、马鬃、缰绳鞍具、兜鍪护耳红缨、明光铠护心镜、马槊红缨战旗）
- infantry: 披甲步卒（兜鍪、披膊、明光铠护心镜、腿裙战靴、铆钉盾牌、长矛）
- heavy_inf: 陌刀重甲武士（双层重甲披膊、飘带披风、双手持带镡长柄宽刃陌刀）
- mixed: 骑兵+步卒混编双剪影
- levy: 新募轻装矛兵（束发抹额、布衣腰带、绑腿）
- militia: 义军执旗卒（火焰牙边大旗+飘带）
运行 python src/sprites.py 会生成 output/sprites_preview.png 供检视。
"""
from pathlib import Path
from PIL import Image, ImageDraw
import numpy as np


def _catmull_rom(pts, n_per_seg=8):
    p = np.asarray(pts, dtype=float)
    n = len(p)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = p[(i - 1) % n], p[i], p[(i + 1) % n], p[(i + 2) % n]
        for j in range(n_per_seg):
            t = j / n_per_seg
            t2, t3 = t * t, t * t * t
            q = 0.5 * (
                (2 * p1)
                + (-p0 + p2) * t
                + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                + (-p0 + 3 * p1 - 3 * p2 + p3) * t3
            )
            out.append((float(q[0]), float(q[1])))
    return out


def _hex_rgba(hexcol, alpha=255):
    h = hexcol.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def _scale_col(rgba, factor):
    return (
        max(0, min(255, int(rgba[0] * factor))),
        max(0, min(255, int(rgba[1] * factor))),
        max(0, min(255, int(rgba[2] * factor))),
        rgba[3],
    )


def _blend(rgba1, rgba2, t=0.5):
    return tuple(int(rgba1[i] * (1 - t) + rgba2[i] * t) for i in range(4))


def _draw_tang_helmet(P, poly, line, draw, S, scale, cx, cy, fill, accent, ink, heavy=False):
    """绘制唐式兜鍪：眉庇、弧形顿项护耳、面部暗影、顶针、长红缨。"""
    dark = _scale_col(fill, 0.68)
    face_skin = (212, 168, 134, 255)
    face_shadow = (145, 102, 76, 255)
    tassel = (210, 48, 38, 255) if fill[0] < 160 else accent

    # 飘逸长红缨（向后飘动）
    poly([(cx - 1, cy - 8), (cx - 11, cy - 11), (cx - 17, cy - 5), (cx - 12, cy - 3), (cx - 4, cy - 5)], tassel, w=1.0, smooth=True)
    # 面庞（微暗阴影）
    draw.ellipse([P(cx - 4.2, cy - 2.0), P(cx + 4.8, cy + 5.8)], fill=face_skin, outline=ink, width=max(1, int(1.1 * S * scale)))
    poly([(cx - 4, cy - 2), (cx + 4.5, cy - 2), (cx + 4.5, cy + 1.2), (cx - 4, cy + 1.2)], face_shadow, ec=None)
    # 盔体穹顶
    poly([(cx - 5.5, cy - 0.5), (cx - 4.5, cy - 6.5), (cx + 4.0, cy - 6.5), (cx + 5.8, cy - 0.5)], fill, w=1.4)
    # 眉庇（前檐）
    poly([(cx - 5.0, cy - 1.2), (cx + 6.8, cy - 1.2), (cx + 6.2, cy + 0.6), (cx - 4.5, cy + 0.4)], accent, w=1.0)
    # 顿项（左右护耳护颈）
    poly([(cx - 6.8, cy - 1.0), (cx - 3.2, cy - 1.0), (cx - 2.8, cy + 6.2), (cx - 7.5, cy + 5.5)], dark, w=1.1)
    if heavy:
        poly([(cx + 1.5, cy + 0.2), (cx + 4.2, cy + 0.2), (cx + 4.6, cy + 5.4), (cx + 1.8, cy + 5.4)], dark, w=1.0)
    # 顶针尖
    poly([(cx - 2.0, cy - 6.5), (cx + 0.0, cy - 11.2), (cx + 2.0, cy - 6.5)], accent, w=1.0)


def _draw_horse_leg(poly, segs, col, hoof_col, w=1.3):
    """按大腿/关节/管部/球节/马蹄绘制单条马腿。"""
    # segs: (hip, knee, fetlock, hoof_tip, hoof_back, fetlock_back, knee_back, hip_back)
    poly(segs, col, w=w)
    # 马蹄（最后一段底部深色蹄甲）
    hoof = [segs[2], segs[3], segs[4], segs[5]]
    poly(hoof, hoof_col, w=1.0)


def _draw_horseman(draw, S, ox, oy, fill, accent, ink, scale=1.0):
    """在 (ox, oy) 绘制向右飞驰的高精骑士（100x100 基准坐标系）。"""
    def P(x, y):
        return ((ox + x * scale) * S, (oy + y * scale) * S)

    def poly(pts, fc, ec=ink, w=1.6, smooth=False):
        rpts = _catmull_rom(pts, 8) if smooth else pts
        spts = [P(x, y) for x, y in rpts]
        draw.polygon(spts, fill=fc)
        if ec:
            draw.line(spts + [spts[0]], fill=ec, width=max(1, int(w * S * scale)), joint="curve")

    def line(pts, col, w=2.2):
        spts = [P(x, y) for x, y in pts]
        draw.line(spts, fill=col, width=max(1, int(w * S * scale)), joint="curve")

    dark = _scale_col(fill, 0.68)
    hi = _blend(fill, (255, 248, 228, 255), 0.26)
    hoof = (42, 34, 30, 255)
    leather = (92, 58, 36, 255)
    tassel = (205, 42, 36, 255)

    # 1. 波浪马尾（双股分层）
    poly([(23, 55), (14, 51), (7, 56), (4, 65), (10, 63), (15, 59), (24, 60)], dark, w=1.3, smooth=True)
    poly([(22, 58), (13, 60), (7, 68), (11, 70), (17, 64), (24, 62)], _scale_col(fill, 0.55), w=1.1, smooth=True)

    # 2. 远侧前后腿（带膝/飞节弯折与深色马蹄）
    _draw_horse_leg(poly, [(29, 62), (24, 71), (18, 79), (14, 86), (17, 88), (21, 81), (28, 73), (34, 64)], dark, hoof)
    _draw_horse_leg(poly, [(61, 61), (68, 70), (74, 77), (79, 82), (82, 79), (77, 74), (71, 67), (65, 59)], dark, hoof)

    # 3. 飘动分段马鬃
    mane = [(62, 41), (59, 34), (63, 29), (62, 23), (67, 22), (69, 25), (66, 33), (64, 41)]
    poly(mane, dark, w=1.1)

    # 4. 马身、弓颈与马首（样条平滑）
    horse = [
        (23, 57), (27, 49), (38, 48), (54, 48), (61, 41),
        (65, 29), (69, 22), (72, 25), (76, 24), (84, 32),
        (89, 37), (85, 41), (78, 39), (74, 38), (71, 47),
        (67, 58), (61, 65), (46, 65), (33, 66), (25, 63),
    ]
    poly(horse, fill, w=1.7, smooth=True)

    # 马臀与肩部淡高光
    poly([(28, 52), (35, 50), (37, 55), (29, 57)], hi, ec=None, smooth=True)
    poly([(60, 46), (66, 44), (67, 53), (61, 54)], hi, ec=None, smooth=True)

    # 马眼与鼻孔
    draw.ellipse([P(75.5, 29.0), P(78.2, 31.5)], fill=(250, 245, 230, 255), outline=ink, width=max(1, int(0.9 * S * scale)))
    draw.ellipse([P(76.3, 29.5), P(77.6, 30.8)], fill=ink)
    draw.ellipse([P(85.2, 36.2), P(86.8, 37.8)], fill=ink)

    # 马具：胸带、障泥鞍褥、带金边鞍桥、辔头与缰绳
    line([(60, 50), (70, 53)], accent, w=1.6)
    poly([(36, 48), (55, 48), (58, 61), (35, 61)], accent, w=1.2)
    poly([(39, 50), (53, 50), (54, 57), (39, 57)], dark, w=1.0)
    # 辔头
    line([(72, 27), (81, 35)], leather, w=1.4)
    line([(77, 38), (83, 33)], leather, w=1.3)

    # 5. 近侧前后腿（前伸蹬跃，骨骼关节与蹄清晰）
    _draw_horse_leg(poly, [(32, 60), (30, 70), (28, 79), (25, 87), (29, 89), (32, 80), (35, 71), (39, 62)], fill, hoof)
    _draw_horse_leg(poly, [(60, 58), (68, 64), (74, 60), (80, 62), (82, 65), (75, 67), (69, 71), (58, 64)], fill, hoof)

    # 6. 骑士披风、腿裙与战靴
    poly([(43, 31), (30, 41), (20, 50), (33, 52), (44, 44)], accent, w=1.2, smooth=True)
    # 腿裙与护胫战靴
    poly([(44, 48), (52, 48), (54, 57), (45, 57)], dark, w=1.1)
    poly([(46, 56), (53, 56), (52, 65), (47, 65)], fill, w=1.2)
    poly([(47, 64), (53, 64), (55, 69), (47, 69)], hoof, w=1.1)

    # 7. 躯干明光铠（双护心镜 + 蹀躞腰带 + 披膊）
    poly([(42, 30), (55, 30), (56, 49), (43, 49)], fill, w=1.5)
    # 双圆护心镜
    draw.ellipse([P(44.2, 34.5), P(48.8, 39.2)], fill=accent, outline=ink, width=max(1, int(1.0 * S * scale)))
    draw.ellipse([P(49.5, 34.5), P(54.1, 39.2)], fill=accent, outline=ink, width=max(1, int(1.0 * S * scale)))
    # 腰带与带扣
    poly([(43, 44), (56, 44), (56, 47.5), (43, 47.5)], leather, w=1.0)
    poly([(48, 44), (51.5, 44), (51.5, 47.5), (48, 47.5)], accent, w=0.9)
    # 披膊
    poly([(41, 30), (47, 30), (46, 36), (39, 35)], accent, w=1.1)

    # 8. 唐式兜鍪
    _draw_tang_helmet(P, poly, line, draw, S, scale, 48.5, 24.5, fill, accent, ink)

    # 9. 手臂、缰绳握持、马槊长矛 + 枪头金属高光与红缨 + 燕尾战旗
    # 左手拉缰
    line([(53, 35), (60, 39), (78, 37)], leather, w=1.2)
    poly([(49, 34), (59, 37), (58, 41), (48, 38)], fill, w=1.2)
    draw.ellipse([P(56.5, 36.5), P(60.5, 40.5)], fill=(212, 168, 134, 255), outline=ink, width=max(1, int(1.0 * S * scale)))
    # 长矛杆
    line([(24, 47), (94, 13)], "#4A3525", w=2.3)
    # 枪头（暗背+亮刃高光）
    poly([(91, 14), (99, 10), (93, 18)], "#CFD8DC", w=1.1)
    line([(92, 14), (99, 10)], "#FFFFFF", w=1.2)
    # 枪头红缨
    poly([(88, 16), (82, 22), (86, 23), (90, 17)], tassel, w=0.9)
    # 燕尾旗
    poly([(84, 18), (67, 11), (72, 18), (66, 23), (82, 19)], accent, w=1.1)


def _draw_infantry(draw, S, ox, oy, fill, accent, ink, scale=1.0, heavy=False, light=False, flag_only=False):
    """绘制向右推进的高精步兵（持盾长矛 / 陌刀重步 / 新募兵 / 义军）。"""
    def P(x, y):
        return ((ox + x * scale) * S, (oy + y * scale) * S)

    def poly(pts, fc, ec=ink, w=1.6, smooth=False):
        rpts = _catmull_rom(pts, 8) if smooth else pts
        spts = [P(x, y) for x, y in rpts]
        draw.polygon(spts, fill=fc)
        if ec:
            draw.line(spts + [spts[0]], fill=ec, width=max(1, int(w * S * scale)), joint="curve")

    def line(pts, col, w=2.3):
        spts = [P(x, y) for x, y in pts]
        draw.line(spts, fill=col, width=max(1, int(w * S * scale)), joint="curve")

    dark = _scale_col(fill, 0.68)
    boots = (44, 32, 26, 255)
    leather = (92, 58, 36, 255)
    skin = (212, 168, 134, 255)
    tassel = (205, 42, 36, 255)

    # 1. 重甲武士背后飘带披风
    if heavy:
        poly([(37, 34), (20, 49), (16, 67), (28, 66), (38, 49)], accent, w=1.2, smooth=True)

    # 2. 双腿、护胫/绑腿与战靴
    poly([(41, 61), (36, 77), (42, 78), (47, 63)], dark, w=1.3)
    poly([(50, 61), (55, 77), (61, 76), (55, 61)], fill, w=1.3)
    # 护胫或绑腿纹理
    if light or flag_only:
        line([(38, 70), (42, 72)], accent, w=1.1)
        line([(53, 70), (57, 72)], accent, w=1.1)
    else:
        poly([(36, 70), (42, 70), (41, 79), (35, 79)], accent, w=1.0)
        poly([(53, 70), (59, 70), (60, 79), (54, 79)], accent, w=1.0)
    # 战靴
    poly([(35, 78), (41, 78), (40, 86), (32, 86)], boots, w=1.2)
    poly([(54, 78), (60, 78), (64, 85), (55, 86)], boots, w=1.2)

    # 3. 躯干铠甲 / 布衣 + 腿裙甲片纹 + 蹀躞腰带
    if heavy:
        poly([(34, 33), (62, 33), (65, 67), (32, 67)], fill)
        # 重甲双层腿裙与甲片暗纹
        poly([(32, 53), (64, 53), (65, 67), (32, 67)], dark, w=1.2)
        for sx in (40, 48, 56):
            line([(sx, 54), (sx, 66)], ink, w=0.9)
        line([(33, 60), (64, 60)], ink, w=0.9)
        # 披膊（含横纹）
        poly([(29, 34), (41, 31), (40, 44), (29, 42)], accent, w=1.2)
        line([(30, 38), (40, 38)], ink, w=0.9)
        poly([(55, 31), (67, 34), (67, 42), (56, 44)], accent, w=1.2)
        line([(56, 38), (66, 38)], ink, w=0.9)
        # 双护心镜 + 宽腰带
        draw.ellipse([P(40, 36), P(47, 43)], fill=accent, outline=ink, width=max(1, int(1.1 * S * scale)))
        draw.ellipse([P(49, 36), P(56, 43)], fill=accent, outline=ink, width=max(1, int(1.1 * S * scale)))
        poly([(34, 48), (63, 48), (63, 53), (34, 53)], leather, w=1.1)
        poly([(46, 48), (51, 48), (51, 53), (46, 53)], accent, w=1.0)
    elif light or flag_only:
        poly([(40, 35), (56, 35), (58, 63), (38, 63)], fill)
        poly([(39, 48), (57, 48), (57, 52), (39, 52)], leather, w=1.0)
        poly([(46, 48), (50, 48), (50, 52), (46, 52)], accent, w=0.9)
        if flag_only:
            draw.ellipse([P(44, 38), P(52, 46)], fill=accent, outline=ink, width=max(1, int(1.0 * S * scale)))
    else:
        poly([(37, 34), (59, 34), (61, 64), (36, 64)], fill)
        # 腿裙与甲片线
        poly([(36, 53), (60, 53), (61, 64), (36, 64)], dark, w=1.2)
        for sx in (43, 49, 55):
            line([(sx, 54), (sx, 63)], ink, w=0.8)
        # 披膊
        poly([(33, 35), (41, 33), (40, 42), (33, 41)], accent, w=1.1)
        poly([(55, 33), (63, 35), (63, 41), (56, 42)], accent, w=1.1)
        # 明光铠双护心镜 + 腰带
        draw.ellipse([P(41, 37), P(47.5, 43.5)], fill=accent, outline=ink, width=max(1, int(1.1 * S * scale)))
        draw.ellipse([P(49, 37), P(55.5, 43.5)], fill=accent, outline=ink, width=max(1, int(1.1 * S * scale)))
        poly([(37, 48), (60, 48), (60, 52), (37, 52)], leather, w=1.0)
        poly([(46.5, 48), (50.5, 48), (50.5, 52), (46.5, 52)], accent, w=0.9)

    # 4. 头部与兜鍪 / 束发抹额
    if light or flag_only:
        # 束发发髻 + 面容 + 抹额
        poly([(45, 16), (51, 16), (50, 21), (46, 21)], ink, w=1.0)
        draw.ellipse([P(42, 20), P(55, 33)], fill=skin, outline=ink, width=max(1, int(1.4 * S * scale)))
        poly([(42, 22), (55, 22), (55, 26), (42, 26)], accent, w=1.0)
        poly([(42, 23), (35, 25), (37, 28), (42, 25)], accent, w=0.9)
    else:
        _draw_tang_helmet(P, poly, line, draw, S, scale, 48.0, 26.0, fill, accent, ink, heavy=heavy)

    # 5. 手臂与武器/盾牌
    if heavy:
        # 双手执长柄宽刃陌刀
        line([(21, 74), (67, 29)], "#4A3525", w=2.8)
        # 护手镡
        line([(61, 25), (71, 35)], accent, w=2.6)
        # 宽刃陌刀（暗钢背+银亮刀锋）
        poly([(65, 29), (89, 5), (94, 10), (70, 34)], "#CFD8DC", w=1.3)
        line([(70, 33), (94, 10)], "#FFFFFF", w=1.4)
        # 刀镡红缨
        poly([(61, 33), (53, 41), (63, 40)], tassel, w=1.0)
        # 握刀双手
        draw.ellipse([P(35, 52), P(41, 58)], fill=skin, outline=ink, width=max(1, int(1.0 * S * scale)))
        draw.ellipse([P(51, 38), P(57, 44)], fill=skin, outline=ink, width=max(1, int(1.0 * S * scale)))
    elif flag_only:
        line([(59, 86), (62, 10)], "#4A3525", w=2.5)
        poly([(60, 12), (62, 4), (64, 12)], "#ECEFF1", w=1.0)
        # 火焰牙边大旗 + 飘带
        poly([(61, 14), (94, 19), (87, 24), (93, 29), (86, 33), (92, 38), (61, 39)], accent, w=1.2)
        poly([(62, 38), (74, 48), (69, 49), (61, 41)], tassel, w=0.9)
        draw.ellipse([P(56, 46), P(62, 52)], fill=skin, outline=ink, width=max(1, int(1.0 * S * scale)))
    else:
        # 长矛 + 金属高光 + 红缨
        line([(36, 70), (80, 13)], "#4A3525", w=2.4)
        poly([(76, 16), (86, 5), (81, 19)], "#CFD8DC", w=1.1)
        line([(80, 18), (86, 5)], "#FFFFFF", w=1.1)
        poly([(75, 19), (70, 26), (74, 27), (78, 20)], tassel, w=0.9)
        draw.ellipse([P(41, 50), P(47, 56)], fill=skin, outline=ink, width=max(1, int(1.0 * S * scale)))
        if not light:
            # 唐式椭圆盾：铆钉外圈 + 盾鼻圆纹
            draw.ellipse([P(50, 37), P(72, 67)], fill=accent, outline=ink, width=max(1, int(1.7 * S * scale)))
            draw.ellipse([P(54, 41), P(68, 63)], fill=fill, outline=ink, width=max(1, int(1.2 * S * scale)))
            draw.ellipse([P(58, 49), P(64, 55)], fill=accent, outline=ink, width=max(1, int(1.0 * S * scale)))
            for ang in range(0, 360, 45):
                rx = 61 + 9.2 * np.cos(np.radians(ang))
                ry = 52 + 12.8 * np.sin(np.radians(ang))
                draw.ellipse([P(rx - 0.8, ry - 0.8), P(rx + 0.8, ry + 0.8)], fill=ink)


def make_sprite(unit_type, color_hex, accent_hex, flip=False, size=(120, 96)):
    """生成指定兵种与配色的透明 RGBA PIL Image（4x 超采样）。"""
    S = 4
    W, H = size[0] * S, size[1] * S
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    fill = _hex_rgba(color_hex, 255)
    accent = _hex_rgba(accent_hex, 255)
    ink = (36, 26, 22, 255)

    draw.ellipse([16 * S, 81 * S, 104 * S, 92 * S], fill=(40, 28, 20, 52))

    if unit_type == "cavalry":
        _draw_horseman(draw, S, 8, -1, fill, accent, ink, scale=0.96)
    elif unit_type == "infantry":
        _draw_infantry(draw, S, 12, 1, fill, accent, ink, scale=0.95)
    elif unit_type == "heavy_inf":
        _draw_infantry(draw, S, 10, -1, fill, accent, ink, scale=0.98, heavy=True)
    elif unit_type == "levy":
        _draw_infantry(draw, S, 14, 2, fill, accent, ink, scale=0.90, light=True)
    elif unit_type == "militia":
        _draw_infantry(draw, S, 8, 1, fill, accent, ink, scale=0.92, flag_only=True)
    elif unit_type == "mixed":
        _draw_horseman(draw, S, 1, -1, fill, accent, ink, scale=0.77)
        _draw_infantry(draw, S, 48, 14, fill, accent, ink, scale=0.75)
    else:
        _draw_infantry(draw, S, 12, 1, fill, accent, ink, scale=0.95)

    out = img.resize(size, Image.Resampling.LANCZOS)
    if flip:
        out = out.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return out


def make_battle_icon(size=(44, 44)):
    """绘制双剑交锋图标（4x超采样）。"""
    S = 4
    W, H = size[0] * S, size[1] * S
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ink = (45, 22, 16, 255)
    steel = (242, 245, 248, 255)
    gold = (230, 175, 65, 255)
    d.ellipse([4 * S, 4 * S, 40 * S, 40 * S], fill=(192, 57, 43, 210), outline=(255, 240, 200, 230), width=2 * S)
    for sgn in (1, -1):
        cx = 22
        pts = lambda l: [((cx + sgn * (x - cx)) * S, y * S) for x, y in l]
        d.polygon(pts([(10, 34), (31, 10), (35, 9), (34, 13), (13, 37)]), fill=steel, outline=ink)
        d.line(pts([(11, 29), (17, 35)]), fill=gold, width=3 * S)
        d.line(pts([(8, 36), (13, 31)]), fill=gold, width=2 * S)
    return img.resize(size, Image.Resampling.LANCZOS)


if __name__ == "__main__":
    ROOT = Path(__file__).resolve().parent.parent
    OUT = ROOT / "output" / "sprites_preview.png"
    OUT.parent.mkdir(exist_ok=True)
    types = [
        ("cavalry", "#6C3483", "#D2B4DE", False),
        ("infantry", "#C0392B", "#F5B041", False),
        ("heavy_inf", "#C0392B", "#F5B041", False),
        ("mixed", "#C0392B", "#F5B041", False),
        ("levy", "#C0392B", "#F5B041", False),
        ("militia", "#C0392B", "#F5B041", False),
        ("cavalry", "#148F77", "#A3E4D7", True),
        ("cavalry", "#2C3E50", "#85929E", False),
    ]
    sheet = Image.new("RGBA", (1040, 290), (244, 238, 221, 255))
    for i, (ut, c1, c2, fl) in enumerate(types):
        sp = make_sprite(ut, c1, c2, flip=fl, size=(126, 100))
        sheet.alpha_composite(sp, ((i % 4) * 255 + 55, (i // 4) * 140 + 18))
    sheet.save(OUT)
    print(OUT)
