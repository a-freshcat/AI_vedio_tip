"""
src/tang_warlords_sprites_128.py
《唐末黄巢起义（874–884）》宿敌群雄 128×128 原生高精度像素精灵模块
- 朱温（ZHU_WEN）：背齐降唐・宣武节度使（暗绯唐式战袍明光铠，捧降书/拔剑/宣武朱旗）
- 李克用（LI_KEYONG）：独眼骁将・沙陀鸦儿军（玄黑鸦羽铁甲，独眼特征，黑底银鸦军旗与强弓长槊）
保持与 `character_director.py` 兼容接口：CHARACTERS, get_warlord_sprite(char_key, frame=0, scale=1)
"""
from __future__ import annotations
import math
from PIL import Image

from huangchao_sprites_ultra import (
    PALETTE,
    PixelCanvas,
    _arm,
    _boots,
    _scroll,
    _spear,
    _sword,
    grid_to_image,
)

CHARACTERS = {
    "ZHU_WEN": {
        "title": "朱温 · 宣武节度使",
        "frames": ["据城观望", "拔剑背齐", "献印降唐", "宣武赤旗"],
    },
    "LI_KEYONG": {
        "title": "李克用 · 沙陀鸦儿军",
        "frames": ["雁门驻马", "独眼挽弓", "鸦军突袭", "跃马追击"],
    },
}


def _warlord_face(p: PixelCanvas, cx: int, y: int, kind: str, feeling: str = "stern") -> None:
    p.poly(
        [
            (cx - 14, y + 6), (cx - 13, y - 4), (cx - 7, y - 9), (cx + 8, y - 8),
            (cx + 14, y - 2), (cx + 15, y + 10), (cx + 11, y + 25), (cx - 12, y + 26),
        ],
        "hair0",
    )
    p.poly(
        [
            (cx - 10, y + 7), (cx + 9, y + 5), (cx + 12, y + 11), (cx + 11, y + 22),
            (cx + 5, y + 29), (cx - 4, y + 30), (cx - 11, y + 24), (cx - 12, y + 16),
        ],
        "skin1",
    )
    p.poly(
        [
            (cx - 9, y + 8), (cx + 7, y + 7), (cx + 10, y + 12), (cx + 8, y + 23),
            (cx + 3, y + 27), (cx - 7, y + 23), (cx - 10, y + 16),
        ],
        "skin3",
    )
    p.poly([(cx - 8, y + 9), (cx + 2, y + 7), (cx + 7, y + 11), (cx + 4, y + 16), (cx - 7, y + 17)], "skin4")

    by = y + 10 if feeling == "angry" else y + 12
    p.line([(cx - 9, by), (cx - 3, by + 1)], "hair0", 3)
    p.line([(cx + 2, by + 1), (cx + 9, by)], "hair0", 3)
    p.line([(cx - 7, y + 16), (cx - 3, y + 16)], "hair0", 2)
    p.dot(cx - 4, y + 16, "eye")

    if kind == "LI_KEYONG":
        # 独眼眼罩与斜带（史称“独眼龙”）
        p.line([(cx - 12, y + 9), (cx + 12, y + 20)], "iron0", 2)
        p.poly([(cx + 2, y + 13), (cx + 10, y + 13), (cx + 10, y + 20), (cx + 3, y + 20)], "iron0")
        p.dot(cx + 6, y + 16, "iron3")
    else:
        p.line([(cx + 4, y + 16), (cx + 8, y + 16)], "hair0", 2)
        p.dot(cx + 7, y + 16, "eye")

    # 鼻梁与短髭
    p.line([(cx + 1, y + 17), (cx + 2, y + 21), (cx + 4, y + 22)], "skin1", 2)
    p.line([(cx - 7, y + 24), (cx - 2, y + 25), (cx + 4, y + 25), (cx + 8, y + 24)], "hair0", 2)
    p.poly([(cx - 5, y + 27), (cx + 5, y + 27), (cx + 3, y + 33), (cx - 4, y + 33)], "hair0")

    # 唐军/沙陀武冠兜鍪
    if kind == "ZHU_WEN":
        p.poly([(cx - 15, y + 7), (cx - 12, y - 5), (cx + 11, y - 5), (cx + 15, y + 7)], "gold1")
        p.rect((cx - 13, y - 8, cx + 12, y - 3), "gold3")
        p.rect((cx - 4, y - 13, cx + 4, y - 7), "red3")
        p.rect((cx - 16, y + 4, cx + 16, y + 8), "red2")
    else:
        p.poly([(cx - 15, y + 7), (cx - 13, y - 7), (cx + 12, y - 7), (cx + 15, y + 7)], "iron0")
        p.line([(cx - 10, y - 5), (cx + 9, y - 5)], "iron3", 2)
        p.poly([(cx - 5, y - 14), (cx + 4, y - 14), (cx + 2, y - 6), (cx - 3, y - 6)], "steel2")
        p.line([(cx, y - 16), (cx - 6, y - 24), (cx - 13, y - 20)], "iron0", 4)
        p.line([(cx, y - 16), (cx + 7, y - 24), (cx + 13, y - 18)], "iron2", 3)


def _banner(p: PixelCanvas, x: int, y: int, kind: str, phase: int = 0) -> None:
    p.line([(x, y), (x, y + 108)], "brown0", 6)
    p.line([(x - 2, y + 4), (x - 2, y + 106)], "brown4", 2)
    p.rect((x - 4, y - 4, x + 4, y + 2), "gold1")
    wave = (phase % 4 - 1) * 3
    if kind == "ZHU_WEN":
        p.poly(
            [
                (x + 3, y + 5), (x + 24, y + 5 + wave), (x + 44, y + 10 + wave),
                (x + 36, y + 24 + wave), (x + 44, y + 38 + wave), (x + 23, y + 35 + wave), (x + 3, y + 32),
            ],
            "red0",
        )
        p.poly(
            [(x + 6, y + 8), (x + 24, y + 8 + wave), (x + 38, y + 13 + wave), (x + 31, y + 24 + wave), (x + 38, y + 34 + wave), (x + 7, y + 30)],
            "red3",
        )
        p.line([(x + 12, y + 19), (x + 28, y + 19 + wave)], "gold4", 3)
        p.line([(x + 20, y + 12), (x + 20, y + 28 + wave)], "gold4", 3)
    else:
        p.poly(
            [
                (x + 3, y + 5), (x + 24, y + 5 + wave), (x + 45, y + 11 + wave),
                (x + 36, y + 25 + wave), (x + 45, y + 39 + wave), (x + 24, y + 36 + wave), (x + 3, y + 33),
            ],
            "hair0",
        )
        p.poly(
            [(x + 6, y + 8), (x + 24, y + 9 + wave), (x + 38, y + 14 + wave), (x + 31, y + 24 + wave), (x + 38, y + 34 + wave), (x + 7, y + 30)],
            "iron0",
        )
        # 鸦羽剪影徽记
        p.line([(x + 13, y + 22), (x + 21, y + 15 + wave), (x + 31, y + 22 + wave)], "steel2", 3)
        p.line([(x + 17, y + 25), (x + 25, y + 20 + wave)], "iron4", 2)


def _bow(p: PixelCanvas, cx: int, cy: int) -> None:
    p.line([(cx + 12, cy - 26), (cx + 25, cy - 12), (cx + 27, cy), (cx + 25, cy + 12), (cx + 12, cy + 26)], "brown0", 4)
    p.line([(cx + 13, cy - 25), (cx + 24, cy - 11), (cx + 26, cy), (cx + 24, cy + 11), (cx + 13, cy + 25)], "gold3", 2)
    p.line([(cx + 12, cy - 26), (cx + 12, cy + 26)], "ivory2", 1)
    p.line([(cx - 4, cy), (cx + 38, cy)], "ivory3", 2)
    p.poly([(cx + 35, cy - 3), (cx + 44, cy), (cx + 35, cy + 3)], "steel3")


def _build_zhu_wen(frame: int):
    f = frame % 4
    p = PixelCanvas()
    cx = 74
    _banner(p, 16, 12, "ZHU_WEN", phase=f)
    _boots(p, cx, 2 if f == 3 else 0, True)

    # 唐绯袍与明光胸甲
    p.poly([(cx - 21, 74), (cx + 20, 74), (cx + 24, 105), (cx + 10, 108), (cx - 14, 109), (cx - 24, 103)], "red0")
    p.poly([(cx - 18, 76), (cx + 17, 76), (cx + 20, 102), (cx + 8, 104), (cx - 16, 104)], "red2")
    p.poly([(cx - 22, 55), (cx - 13, 48), (cx + 13, 48), (cx + 22, 56), (cx + 19, 82), (cx - 20, 82)], "red1")
    p.poly([(cx - 18, 56), (cx - 11, 52), (cx + 11, 52), (cx + 18, 57), (cx + 16, 78), (cx - 18, 78)], "gold1")
    for x in (cx - 8, cx + 8):
        p.ell((x - 7, 59, x + 7, 75), "gold3")
        p.ell((x - 4, 62, x + 4, 71), "gold5")
    p.rect((cx - 21, 79, cx + 20, 85), "gold0")
    p.rect((cx - 5, 79, cx + 6, 85), "gold4")

    _arm(p, (cx - 18, 57), (cx - 30, 68), (20, 75), "emperor")
    p.rect((15, 72, 23, 78), "skin2")
    if f == 2:
        _arm(p, (cx + 18, 57), (cx + 29, 63), (cx + 35, 59), "emperor")
        _scroll(p, cx + 31, 47, torn=False)
    elif f == 1:
        _arm(p, (cx + 18, 57), (cx + 28, 50), (cx + 36, 42), "emperor")
        _sword(p, (cx + 36, 42), (121, 14))
    else:
        _arm(p, (cx + 18, 57), (cx + 29, 68), (cx + 31, 78), "emperor")
        _sword(p, (cx + 31, 78), (cx + 39, 112))

    _warlord_face(p, cx, 27, "ZHU_WEN", feeling="angry" if f == 1 else "stern")
    return [[key for key in row] for row in _img_grid(p.finish())]


def _build_li_keyong(frame: int):
    f = frame % 4
    p = PixelCanvas()
    cx = 72
    _banner(p, 14, 11, "LI_KEYONG", phase=f)
    _boots(p, cx, 4 if f in (2, 3) else 0, True)

    # 玄黑沙陀鸦儿军重铠与暗银披风
    wind = (f % 4) * 3
    p.poly([(cx - 16, 52), (cx - 25, 61), (cx - 31 - wind, 88), (cx - 38 - wind, 112), (cx - 20, 108), (cx - 11, 68)], "hair0")
    p.poly([(cx - 22, 76), (cx + 21, 76), (cx + 22, 104), (cx + 9, 107), (cx - 16, 106)], "iron0")
    for xx in (cx - 13, cx - 4, cx + 5, cx + 13):
        p.poly([(xx - 4, 80), (xx + 4, 80), (xx + 5, 96), (xx, 100), (xx - 4, 96)], "iron1")
        p.dot(xx, 93, "steel2")

    p.poly([(cx - 23, 55), (cx - 13, 48), (cx + 13, 48), (cx + 23, 56), (cx + 20, 82), (cx - 21, 82)], "hair0")
    p.poly([(cx - 19, 56), (cx - 11, 52), (cx + 11, 52), (cx + 19, 57), (cx + 16, 78), (cx - 18, 78)], "iron1")
    for x in (cx - 8, cx + 8):
        p.ell((x - 7, 59, x + 7, 75), "iron2")
        p.ell((x - 4, 62, x + 4, 71), "steel1")
    p.rect((cx - 22, 79, cx + 21, 85), "iron0")
    p.line([(cx - 20, 80), (cx + 19, 80)], "steel2", 2)

    _arm(p, (cx - 18, 57), (cx - 30, 68), (18, 75), "general")
    p.rect((13, 72, 21, 78), "skin2")
    if f == 1:
        _arm(p, (cx + 18, 57), (cx + 30, 58), (cx + 36, 56), "general")
        _bow(p, cx + 18, 58)
    elif f == 2:
        _arm(p, (cx + 18, 57), (cx + 30, 56), (cx + 37, 59), "general")
        _spear(p, (22, 74), (112, 52))
    else:
        _arm(p, (cx + 18, 57), (cx + 28, 49), (cx + 35, 42), "general")
        _spear(p, (44, 112), (109, 20))

    _warlord_face(p, cx, 27, "LI_KEYONG", feeling="angry" if f in (1, 2, 3) else "stern")
    return [[key for key in row] for row in _img_grid(p.finish())]


_REV = {col: k for k, col in PALETTE.items()}


def _img_grid(image: Image.Image):
    px = image.load()
    return [[_REV.get(px[x, y], "ink" if px[x, y][3] else "none") for x in range(image.width)] for y in range(image.height)]


def get_warlord_sprite(char_key: str, frame: int = 0, scale: int = 1) -> Image.Image:
    if char_key == "ZHU_WEN":
        grid = _build_zhu_wen(frame)
    elif char_key == "LI_KEYONG":
        grid = _build_li_keyong(frame)
    else:
        raise ValueError(f"Unknown warlord char_key={char_key!r}")
    return grid_to_image(grid, scale=scale)
