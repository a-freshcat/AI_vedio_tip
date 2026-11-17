# -*- coding: utf-8 -*-
"""高清晰唐代标志建筑精灵库（4倍超采样抗锯齿 RGBA）：
- capital: 都城皇阙（三门城台、重檐庑殿主殿、左右双阙、金色鸱尾、双旗）
- pass: 雄关险隘（陡石关基、拱券城门、雉堞女墙、双层箭楼、拒马鹿角）
- city: 目标坚城（青砖城垣、城门楼、左右角楼、旗帜）
- temple: 名刹宝塔（五层唐式密檐方塔、塔刹相轮、飞檐配殿、红墙山门）
- camp: 军营大帐（木栅栏、望楼、中军大帐）
运行 python src/landmarks.py 会生成 output/landmarks_preview.png 供检视。
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

INK = (38, 26, 20, 255)
STONE_LIGHT = (182, 174, 158, 255)
STONE_MID = (138, 130, 118, 255)
STONE_DARK = (96, 88, 78, 255)
BRICK_WALL = (158, 152, 142, 255)
ROOF_DARK = (74, 52, 46, 255)
ROOF_TILE = (98, 66, 54, 255)
ROOF_PALACE = (168, 56, 40, 255)
ROOF_TEMPLE = (146, 60, 42, 255)
TIMBER = (118, 42, 30, 255)
GOLD = (228, 178, 68, 255)
MARBLE = (238, 232, 218, 255)
GATE_VOID = (32, 22, 18, 255)
WOOD = (128, 86, 52, 255)


def _hex_rgba(hexcol, alpha=255):
    h = hexcol.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def _draw_helper(draw, S):
    def P(x, y):
        return (x * S, y * S)

    def poly(pts, fc, ec=INK, w=1.4):
        spts = [P(x, y) for x, y in pts]
        draw.polygon(spts, fill=fc)
        if ec:
            draw.line(spts + [spts[0]], fill=ec, width=max(1, int(w * S)), joint="curve")

    def rect(x1, y1, x2, y2, fc, ec=INK, w=1.3):
        draw.rectangle([P(x1, y1), P(x2, y2)], fill=fc, outline=ec, width=max(1, int(w * S)))

    def line(pts, col, w=1.5):
        spts = [P(x, y) for x, y in pts]
        draw.line(spts, fill=col, width=max(1, int(w * S)), joint="curve")

    def arch_gate(cx, bottom_y, w, h):
        hw = w * 0.5
        # 矩形门洞 + 上半圆拱
        rect(cx - hw, bottom_y - h * 0.55, cx + hw, bottom_y, GATE_VOID, ec=INK, w=1.0)
        draw.pieslice(
            [P(cx - hw, bottom_y - h), P(cx + hw, bottom_y - h * 0.1)],
            180, 360, fill=GATE_VOID, outline=INK, width=max(1, int(1.0 * S)),
        )
        # 朱漆包钉门扇微缝
        line([(cx, bottom_y - h * 0.72), (cx, bottom_y)], (88, 36, 26, 255), w=0.9)

    def upturned_roof(cx, y_bot, half_w, h, fc=ROOF_DARK, ridge_gold=False, flare=4.0):
        """唐式反宇飞檐屋顶。"""
        pts = [
            (cx - half_w - flare, y_bot - 1.2),
            (cx - half_w * 0.65, y_bot - h * 0.65),
            (cx - half_w * 0.52, y_bot - h),
            (cx + half_w * 0.52, y_bot - h),
            (cx + half_w * 0.65, y_bot - h * 0.65),
            (cx + half_w + flare, y_bot - 1.2),
            (cx + half_w * 0.72, y_bot + 0.6),
            (cx - half_w * 0.72, y_bot + 0.6),
        ]
        poly(pts, fc, w=1.3)
        if ridge_gold:
            line([(cx - half_w * 0.52, y_bot - h), (cx + half_w * 0.52, y_bot - h)], GOLD, w=1.8)
            # 两侧金色鸱尾
            poly([(cx - half_w * 0.54, y_bot - h), (cx - half_w * 0.62, y_bot - h - 3.6),
                  (cx - half_w * 0.44, y_bot - h - 1.5)], GOLD, w=0.9)
            poly([(cx + half_w * 0.54, y_bot - h), (cx + half_w * 0.62, y_bot - h - 3.6),
                  (cx + half_w * 0.44, y_bot - h - 1.5)], GOLD, w=0.9)

    def flag(x, y_bot, h, col, acc, flip=False):
        sgn = -1 if flip else 1
        line([(x, y_bot), (x, y_bot - h)], WOOD, w=1.6)
        draw.ellipse([P(x - 1.2, y_bot - h - 1.8), P(x + 1.2, y_bot - h + 0.6)], fill=GOLD, outline=INK, width=max(1, int(0.7 * S)))
        poly([
            (x, y_bot - h + 1.5),
            (x + sgn * 14, y_bot - h + 4.5),
            (x + sgn * 10, y_bot - h + 7.5),
            (x + sgn * 13.5, y_bot - h + 10.5),
            (x, y_bot - h + 11.5),
        ], col, w=1.0)
        line([(x + sgn * 1.5, y_bot - h + 6.5), (x + sgn * 9.0, y_bot - h + 6.5)], acc, w=1.2)

    def crenellations(x1, x2, y, step=5.5, h=3.2, fc=STONE_MID):
        x = x1
        while x + 2.8 <= x2:
            rect(x, y - h, x + 3.0, y, fc, w=0.9)
            x += step

    return P, poly, rect, line, arch_gate, upturned_roof, flag, crenellations


def make_landmark_sprite(kind, color_hex="#C0392B", accent_hex="#F5B041", size=(140, 112)):
    """生成指定唐代建筑地标的 4x 超采样透明 RGBA PIL Image（基准坐标系 120x96）。"""
    S = 4
    W, H = size[0] * S, size[1] * S
    # 归一化到 120x96 设计空间，若 size 比例不同按 120x96 缩放
    base_w, base_h = 120, 96
    img = Image.new("RGBA", (base_w * S, base_h * S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    P, poly, rect, line, arch_gate, upturned_roof, flag, crenellations = _draw_helper(draw, S)
    fcol = _hex_rgba(color_hex, 255)
    facc = _hex_rgba(accent_hex, 255)

    # 地面投影
    draw.ellipse([10 * S, 81 * S, 110 * S, 92 * S], fill=(38, 26, 20, 56))

    if kind == "capital":
        # 1. 双侧高阙基座与阙楼
        for sgn in (-1, 1):
            qx = 60 + sgn * 41
            poly([(qx - 9, 85), (qx - 7.5, 52), (qx + 7.5, 52), (qx + 9, 85)], STONE_DARK, w=1.2)
            rect(qx - 6.5, 39, qx + 6.5, 52, TIMBER, w=1.1)
            upturned_roof(qx, 40, 8.5, 7.5, fc=ROOF_PALACE, ridge_gold=True, flare=3.0)
            flag(qx, 32, 22, fcol, facc, flip=(sgn < 0))

        # 2. 宏伟三门包砖城台（梯形收分）
        poly([(16, 86), (20, 58), (100, 58), (104, 86)], BRICK_WALL, w=1.6)
        # 砖缝横线
        for by in (66, 73, 80):
            line([(18.5, by), (101.5, by)], STONE_DARK, w=0.8)
        # 汉白玉护栏 & 女墙
        rect(19, 54.5, 101, 58, MARBLE, w=1.0)
        crenellations(21, 99, 54.5, step=6.0, h=2.8, fc=STONE_LIGHT)
        # 三道拱门
        arch_gate(41, 86, 9.0, 15.5)
        arch_gate(60, 86, 11.5, 19.0)
        arch_gate(79, 86, 9.0, 15.5)

        # 3. 中央重檐庑殿顶主殿
        rect(38, 41, 82, 54.5, TIMBER, w=1.2)
        for cx_col in (42, 49, 56, 64, 71, 78):
            line([(cx_col, 42), (cx_col, 54)], (212, 165, 90, 255), w=1.2)
        upturned_roof(60, 42, 24.5, 8.0, fc=ROOF_PALACE, ridge_gold=False, flare=5.0)
        rect(43, 28, 77, 35.5, TIMBER, w=1.1)
        upturned_roof(60, 29, 20.5, 9.5, fc=ROOF_PALACE, ridge_gold=True, flare=4.5)

    elif kind == "pass":
        # 1. 两侧山岩关壁延伸感
        poly([(8, 86), (14, 62), (24, 62), (24, 86)], STONE_DARK, w=1.3)
        poly([(96, 62), (106, 62), (112, 86), (96, 86)], STONE_DARK, w=1.3)
        # 2. 梯形条石关座
        poly([(20, 86), (25, 53), (95, 53), (100, 86)], STONE_MID, w=1.6)
        for by in (61, 69, 77):
            line([(23, by), (97, by)], STONE_DARK, w=0.9)
        crenellations(24, 96, 53, step=5.5, h=3.8, fc=STONE_LIGHT)
        # 拱券关门
        arch_gate(60, 86, 15.0, 22.0)

        # 3. 双层重檐箭楼
        rect(38, 37, 82, 49.5, TIMBER, w=1.2)
        for wx in (44, 52, 60, 68, 76):
            rect(wx - 1.5, 41, wx + 1.5, 45.5, GATE_VOID, w=0.8)  # 箭窗
        upturned_roof(60, 38, 25.0, 7.2, fc=ROOF_DARK, ridge_gold=False, flare=4.5)
        rect(43, 25, 77, 32, TIMBER, w=1.1)
        upturned_roof(60, 26, 20.5, 8.2, fc=ROOF_DARK, ridge_gold=True, flare=4.0)
        flag(28, 53, 25, fcol, facc, flip=True)
        flag(92, 53, 25, fcol, facc, flip=False)

        # 4. 关前拒马鹿角
        for jx in (34, 46, 74, 86):
            line([(jx - 4.5, 88.5), (jx + 4.5, 80.5)], WOOD, w=1.6)
            line([(jx + 4.5, 88.5), (jx - 4.5, 80.5)], WOOD, w=1.6)
            line([(jx - 5.5, 84.5), (jx + 5.5, 84.5)], WOOD, w=1.4)

    elif kind == "city":
        # 1. 左右角楼
        for sgn in (-1, 1):
            tx = 60 + sgn * 34
            rect(tx - 6.5, 48, tx + 6.5, 85, STONE_MID, w=1.2)
            rect(tx - 5.5, 40, tx + 5.5, 48, TIMBER, w=1.0)
            upturned_roof(tx, 41, 7.5, 6.5, fc=ROOF_TILE, ridge_gold=False, flare=2.5)

        # 2. 青砖城墙主体与女墙
        rect(25, 58, 95, 85, BRICK_WALL, w=1.5)
        for by in (66, 75):
            line([(25, by), (95, by)], STONE_DARK, w=0.8)
        crenellations(27, 93, 58, step=5.5, h=3.2, fc=STONE_LIGHT)
        arch_gate(60, 85, 12.0, 17.0)

        # 3. 中央单檐城楼与旗帜
        rect(44, 43, 76, 55, TIMBER, w=1.2)
        upturned_roof(60, 44, 20.0, 8.5, fc=ROOF_TILE, ridge_gold=True, flare=4.0)
        flag(85, 40, 20, fcol, facc, flip=False)

    elif kind == "temple":
        # 1. 左右飞檐配殿与红墙山门
        for sgn in (-1, 1):
            dx = 60 + sgn * 31
            rect(dx - 11, 64, dx + 11, 81, (192, 76, 54, 255), w=1.1)
            upturned_roof(dx, 65, 13.0, 7.0, fc=ROOF_TEMPLE, ridge_gold=False, flare=3.0)
        rect(18, 76, 102, 86, (182, 64, 46, 255), w=1.3)
        rect(52, 72, 68, 86, (164, 52, 36, 255), w=1.2)
        arch_gate(60, 86, 7.5, 10.5)
        upturned_roof(60, 73, 10.5, 5.5, fc=ROOF_TEMPLE, ridge_gold=True, flare=2.5)

        # 2. 五层唐式密檐方塔（居中巍峨矗立）
        poly([(43, 76), (45, 68), (75, 68), (77, 76)], STONE_MID, w=1.3)
        tiers = [(68, 13.0, 11.0), (57, 11.4, 8.8), (47, 9.8, 7.8), (38, 8.4, 7.0), (30, 7.0, 6.2)]
        for yb, hw, th in tiers:
            rect(60 - hw * 0.78, yb - th, 60 + hw * 0.78, yb, (206, 168, 122, 255), w=1.1)
            # 券门/佛龛
            draw.rectangle([P(60 - 2.0, yb - th * 0.65), P(60 + 2.0, yb)], fill=GATE_VOID)
            upturned_roof(60, yb - th + 1.0, hw, 4.4, fc=ROOF_TEMPLE, ridge_gold=False, flare=2.6)
        # 宝顶与相轮塔刹
        poly([(56.5, 21), (60, 16), (63.5, 21)], GOLD, w=1.0)
        line([(60, 16), (60, 4.5)], GOLD, w=2.0)
        for ry in (13, 10.5, 8):
            line([(58.0, ry), (62.0, ry)], GOLD, w=1.3)

    elif kind == "camp":
        # 1. 左右木栅与望楼
        for px in range(16, 105, 5):
            poly([(px - 1.8, 85), (px - 1.8, 68), (px, 63), (px + 1.8, 68), (px + 1.8, 85)], WOOD, w=0.9)
        line([(15, 73), (105, 73)], (88, 56, 32, 255), w=1.8)
        # 望楼
        line([(24, 65), (27, 36)], WOOD, w=1.6)
        line([(34, 65), (31, 36)], WOOD, w=1.6)
        rect(22, 30, 36, 37, WOOD, w=1.1)
        upturned_roof(29, 31, 9.5, 6.0, fc=ROOF_DARK, flare=2.2)

        # 2. 中军大帐
        poly([(42, 85), (45, 56), (79, 56), (82, 85)], (232, 222, 198, 255), w=1.4)
        poly([(44, 57), (62, 41), (80, 57)], fcol, w=1.4)
        poly([(56, 85), (62, 65), (68, 85)], GATE_VOID, w=1.0)
        flag(62, 41, 24, fcol, facc, flip=False)

    return img.resize(size, Image.Resampling.LANCZOS)


def make_war_banner(name, bg_hex="#C93326", border_hex="#F4C83B", size=(96, 154)):
    """生成中国传统竖幅火焰牙边「主将帅旗」（4倍超采样抗锯齿 RGBA）。
    长枪杆直落底边中点 (0.5, 0.0)，锯齿火焰边+鲜明阵营底色+高对比竖排主将名。
    """
    S = 4
    base_w, base_h = 100, 160
    img = Image.new("RGBA", (base_w * S, base_h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    fcol = _hex_rgba(bg_hex, 255)
    bcol = _hex_rgba(border_hex, 255)
    ink = (26, 20, 18, 255)
    pole_col = (108, 68, 38, 255)
    tassel_col = (214, 46, 36, 255) if bg_hex.upper() not in ("#148F77", "#167A70") else bcol

    def P(x, y):
        return (x * S, y * S)

    # 1. 长杆底部接地投影
    d.ellipse([P(36, 151), P(64, 158)], fill=(24, 20, 18, 86))

    # 2. 长矛杆与横梁（杆尖直抵底边中点 x=50）
    d.line([P(50, 12), P(50, 155)], fill=ink, width=max(1, int(4.4 * S)))
    d.line([P(50, 13), P(50, 154)], fill=pole_col, width=max(1, int(2.6 * S)))
    # 顶部枪尖与红缨
    spear = [P(50, 2), P(46.2, 12), P(50, 10.5), P(53.8, 12)]
    d.polygon(spear, fill=(236, 240, 244, 255), outline=ink)
    d.polygon([P(46, 12.5), P(42, 22), P(50, 20), P(58, 22), P(54, 12.5)], fill=tassel_col, outline=ink)

    # 横杆
    d.line([P(19, 22), P(81, 22)], fill=ink, width=max(1, int(4.0 * S)))
    d.line([P(20, 22), P(80, 22)], fill=(196, 152, 74, 255), width=max(1, int(2.2 * S)))
    for tx in (19, 81):
        d.ellipse([P(tx - 2.4, 19.6), P(tx + 2.4, 24.4)], fill=GOLD, outline=ink, width=S)

    # 3. 火焰锯齿牙边旗帜外轮廓（左/下/右锯齿外翻）
    xL, xR, yT, yB = 26.0, 74.0, 23.0, 114.0
    tooth = 6.5
    outer_pts = [(xL, yT), (xR, yT)]
    # 右边向下锯齿
    ys_r = [yT + (yB - yT) * (k / 7.0) for k in range(8)]
    for k in range(7):
        ym = 0.5 * (ys_r[k] + ys_r[k + 1])
        outer_pts.append((xR + tooth, ym))
        outer_pts.append((xR, ys_r[k + 1]))
    # 底边向左锯齿
    xs_b = [xR - (xR - xL) * (k / 4.0) for k in range(5)]
    for k in range(4):
        xm = 0.5 * (xs_b[k] + xs_b[k + 1])
        outer_pts.append((xm, yB + tooth))
        outer_pts.append((xs_b[k + 1], yB))
    # 左边向上锯齿
    ys_l = [yB - (yB - yT) * (k / 7.0) for k in range(8)]
    for k in range(7):
        ym = 0.5 * (ys_l[k] + ys_l[k + 1])
        outer_pts.append((xL - tooth, ym))
        outer_pts.append((xL, ys_l[k + 1]))

    s_outer = [P(x, y) for x, y in outer_pts]
    # 轻微右侧投暗衬出立体感
    s_shad = [P(x + 2.2, y + 2.5) for x, y in outer_pts]
    d.polygon(s_shad, fill=(20, 16, 14, 95))
    d.polygon(s_outer, fill=fcol)
    d.line(s_outer + [s_outer[0]], fill=ink, width=max(1, int(2.2 * S)), joint="curve")

    # 4. 旗面内芯面板（参考图李重进样式：外火焰阵营色齿边 + 明亮亮黄牌面 + 黑色正楷/粗黑体竖排主将名）
    pad_x, pad_y = 32.0, 28.0
    panel = [P(pad_x, pad_y), P(100 - pad_x, pad_y), P(100 - pad_x, yB - 5.0), P(pad_x, yB - 5.0)]
    d.polygon(panel, fill=bcol)
    d.line(panel + [panel[0]], fill=ink, width=max(1, int(1.6 * S)))

    # 5. 竖排书写主将姓名（支持 2-4 字自动匹配字号）
    chars = list(name.strip())
    n = max(1, len(chars))
    avail_h = (yB - 5.0 - pad_y - 6.0) * S
    font_px = min(int(24 * S), int(avail_h / (n * 1.06)))
    font_path = Path(r"C:\Windows\Fonts\msyhbd.ttc")
    if not font_path.exists():
        font_path = Path(r"C:\Windows\Fonts\simkai.ttf")
    fnt = ImageFont.truetype(str(font_path), font_px)

    top_start = (pad_y + 3.0) * S + (avail_h - n * font_px * 1.04) * 0.5
    for idx, ch in enumerate(chars):
        bbox = d.textbbox((0, 0), ch, font=fnt)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        cx = 50 * S - tw * 0.5 - bbox[0]
        cy = top_start + idx * font_px * 1.04 + (font_px - th) * 0.35 - bbox[1] * 0.25
        # 微白高光垫底配醒目墨字，缩小时依旧锐利
        d.text((cx, cy), ch, font=fnt, fill=ink)

    return img.resize(size, Image.Resampling.LANCZOS)


if __name__ == "__main__":
    ROOT = Path(__file__).resolve().parent.parent
    OUT = ROOT / "output" / "landmarks_preview.png"
    OUT.parent.mkdir(exist_ok=True)
    items = [
        ("capital", "#C0392B", "#F5B041"),
        ("pass", "#C0392B", "#F5B041"),
        ("city", "#6C3483", "#D2B4DE"),
        ("temple", "#C0392B", "#F5B041"),
        ("camp", "#2C3E50", "#85929E"),
    ]
    sheet = Image.new("RGBA", (880, 340), (244, 238, 221, 255))
    for i, (k, c1, c2) in enumerate(items):
        sp = make_landmark_sprite(k, c1, c2, size=(144, 116))
        sheet.alpha_composite(sp, (24 + i * 172, 20))
    banners = [
        ("哥舒翰", "#C93326", "#F7D348"),
        ("李嗣业", "#C93326", "#F7D348"),
        ("郭子仪", "#C93326", "#F7D348"),
        ("崔乾祐", "#4B63B8", "#F4C83B"),
        ("安守忠", "#4B63B8", "#F4C83B"),
        ("回纥叶护", "#167A70", "#F7D348"),
    ]
    for i, (bname, bc, tc) in enumerate(banners):
        bn = make_war_banner(bname, bc, tc, size=(92, 148))
        sheet.alpha_composite(bn, (32 + i * 140, 165))
    sheet.save(OUT)
    print(OUT)
