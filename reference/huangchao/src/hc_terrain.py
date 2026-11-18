# -*- coding: utf-8 -*-
"""
src/hc_terrain.py
《唐末黄巢起义（874–884）》全屏 1920×1080 三维立体浮雕底图、古海岸线与实时推动势力疆界引擎
全面对齐《安史之乱》terrain.py 最高画质标准：
1. 完整中国地形：含青藏高原东缘、横断山脉南北平行山谷群（怒江/澜沧江/金沙江/岷山/大雪山）、
   四川盆地环山凹地、云贵高原、祁连—六盘—黄土高原、秦岭、太行、大别、武夷仙霞、南岭、泰山；
2. 采用 steerable_slope_fields（顺坡支脉与走向脊褶）+ 岩石混色 + 高精度沿海浅水陆架与深海光泽；
3. 势力疆界按地形阻隔加权 + 地理锚点 + 动态行军前锋锚点（vanguard）实时推动，搭配「白光晕 + 深墨实线」战线。
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

import numpy as np
from matplotlib.path import Path as MplPath
from PIL import Image
from scipy.ndimage import distance_transform_edt, gaussian_filter

from surface_texture import resize_field, steerable_slope_fields, texture_field

LON0, LON1 = 102.0, 123.5
LAT0, LAT1 = 18.0, 41.2

SEA_POLYS = [
    [
        (145.0, 5.0), (145.0, 46.0),
        (135.50, 43.80), (132.80, 42.80), (130.65, 42.30), (129.78, 41.80),
        (129.65, 40.85), (128.90, 40.15), (127.85, 39.85), (127.48, 39.25),
        (128.32, 38.65), (128.92, 37.75), (129.42, 36.98), (129.56, 36.05),
        (129.35, 35.48), (129.08, 35.10),
        (128.45, 34.82), (127.72, 34.68), (126.95, 34.42), (126.25, 34.35),
        (126.12, 34.85), (126.45, 35.55), (126.55, 36.05), (126.12, 36.68),
        (126.42, 36.95), (126.68, 37.45), (126.18, 37.75), (125.15, 37.68),
        (124.65, 38.08), (125.18, 38.55), (125.42, 38.88), (125.12, 39.55),
        (124.20, 40.05), (123.50, 39.85), (122.80, 39.50), (121.85, 39.05),
        (121.13, 38.73),
        (121.35, 39.40), (122.05, 40.25), (122.18, 40.68),
        (121.50, 40.82), (120.75, 40.50), (119.62, 39.95),
        (119.18, 39.32), (118.50, 39.15), (117.72, 39.02),
        (117.52, 38.58), (118.05, 38.15), (118.92, 37.85),
        (119.05, 37.35), (119.58, 37.15), (119.95, 37.42),
        (120.75, 37.82), (121.45, 37.55), (122.12, 37.50), (122.70, 37.40),
        (122.42, 36.88), (121.55, 36.65), (120.52, 36.12), (120.18, 36.05),
        (119.75, 35.62), (119.35, 35.15), (119.22, 34.75),
        (119.82, 34.25), (120.35, 33.65), (120.92, 32.85), (121.62, 32.10),
        (121.85, 31.75), (121.25, 31.82), (120.85, 31.78),
        (121.35, 31.48), (121.88, 31.18), (121.92, 30.88),
        (121.45, 30.68), (120.95, 30.48), (120.68, 30.30), (121.15, 30.22), (121.85, 30.05),
        (121.68, 29.15), (121.52, 28.65), (121.62, 28.32), (120.82, 27.92),
        (120.42, 27.22), (119.88, 26.65), (119.68, 26.15),
        (119.48, 26.02), (119.55, 25.55), (119.08, 25.15),
        (118.75, 24.82), (118.08, 24.42), (117.52, 23.75),
        (116.82, 23.38), (116.15, 22.95), (115.32, 22.75), (114.55, 22.55),
        (113.68, 22.82), (113.45, 23.04),
        (113.52, 22.65), (113.55, 22.20), (112.95, 21.85),
        (111.85, 21.58), (111.05, 21.42), (110.45, 21.15),
        (110.55, 20.65), (110.15, 20.22), (109.85, 20.55),
        (109.78, 20.98), (109.58, 21.48), (108.65, 21.58), (108.05, 21.50),
        (107.05, 20.85), (106.05, 19.80), (106.40, 17.50), (109.50, 5.0),
        (145.0, 5.0),
    ]
]

ISLAND_POLYS = [
    # 台湾岛
    [
        (121.54, 25.29), (121.78, 25.15), (122.00, 25.01), (121.86, 24.62),
        (121.65, 24.18), (121.54, 23.60), (121.41, 23.12), (121.15, 22.75),
        (120.89, 22.25), (120.85, 21.90), (120.73, 21.92), (120.59, 22.36),
        (120.27, 22.62), (120.14, 23.00), (120.13, 23.38), (120.17, 23.78),
        (120.40, 24.08), (120.56, 24.38), (120.82, 24.68), (120.92, 24.85),
        (121.10, 25.06), (121.41, 25.18), (121.54, 25.29),
    ],
    # 海南岛
    [
        (110.32, 20.06), (110.68, 20.12), (110.95, 19.92), (111.03, 19.65),
        (110.58, 19.15), (110.52, 18.78), (110.05, 18.42), (109.68, 18.22),
        (109.52, 18.16), (109.18, 18.29), (108.70, 18.50), (108.62, 19.08),
        (108.70, 19.34), (109.18, 19.72), (109.50, 19.90), (109.72, 20.01),
        (110.05, 19.98), (110.20, 20.03), (110.32, 20.06),
    ],
    # 澎湖、舟山、海坛、崇明、东山、南澳
    [(119.52, 23.66), (119.66, 23.62), (119.64, 23.48), (119.50, 23.52), (119.52, 23.66)],
    [(121.92, 30.12), (122.28, 30.08), (122.25, 29.92), (121.90, 29.96), (121.92, 30.12)],
    [(119.70, 25.62), (119.86, 25.58), (119.84, 25.42), (119.68, 25.46), (119.70, 25.62)],
    [(121.25, 31.72), (121.75, 31.62), (121.70, 31.50), (121.20, 31.60), (121.25, 31.72)],
    [(117.36, 23.76), (117.50, 23.72), (117.48, 23.62), (117.34, 23.66), (117.36, 23.76)],
    [(116.95, 23.46), (117.15, 23.44), (117.13, 23.38), (116.93, 23.40), (116.95, 23.46)],
    # 济州岛、对马岛、五岛列岛
    [(126.18, 33.25), (126.35, 33.42), (126.65, 33.52), (126.92, 33.48), (126.88, 33.28), (126.52, 33.21), (126.18, 33.25)],
    [(129.18, 34.12), (129.28, 34.68), (129.46, 34.65), (129.36, 34.08), (129.18, 34.12)],
    [(128.60, 32.62), (128.88, 32.92), (129.02, 32.85), (128.75, 32.58), (128.60, 32.62)],
    # 日本九州岛
    [
        (130.88, 33.92), (131.18, 33.65), (131.72, 33.48), (131.88, 32.95),
        (131.52, 32.15), (131.35, 31.42), (130.68, 31.02), (130.58, 31.38),
        (130.22, 31.25), (130.18, 31.85), (130.42, 32.45), (129.95, 32.58),
        (129.55, 32.78), (129.52, 33.35), (129.98, 33.52), (130.48, 33.85),
        (130.88, 33.92),
    ],
    # 日本四国岛
    [
        (132.02, 33.42), (132.68, 34.05), (133.15, 33.95), (133.65, 34.32),
        (134.25, 34.35), (134.78, 33.85), (134.18, 33.25), (133.52, 33.48),
        (132.98, 32.75), (132.45, 32.92), (132.02, 33.42),
    ],
    # 日本本州岛中西部
    [
        (130.88, 34.02), (131.35, 34.48), (132.55, 35.12), (133.35, 35.52),
        (134.35, 35.62), (135.32, 35.68), (136.05, 36.15), (136.72, 37.35),
        (137.35, 36.85), (138.20, 37.80), (138.20, 34.65), (136.85, 34.25),
        (135.85, 33.45), (135.12, 33.85), (135.18, 34.35), (135.48, 34.68),
        (134.75, 34.62), (133.82, 34.42), (132.85, 34.32), (132.05, 33.92),
        (131.18, 33.95), (130.88, 34.02),
    ],
    # 琉球/冲绳诸岛（奄美、冲绳本岛、宫古、石垣）
    [(129.15, 28.08), (129.55, 28.48), (129.70, 28.40), (129.32, 28.02), (129.15, 28.08)],
    [(127.64, 26.08), (127.85, 26.45), (128.28, 26.86), (128.34, 26.75), (127.95, 26.32), (127.75, 26.05), (127.64, 26.08)],
    [(125.18, 24.72), (125.42, 24.85), (125.45, 24.72), (125.22, 24.65), (125.18, 24.72)],
    [(124.08, 24.32), (124.32, 24.52), (124.36, 24.38), (124.15, 24.28), (124.08, 24.32)],
]

ANCIENT_COAST_POLYS = [
    [
        (118.6, 37.25), (118.0, 37.55), (117.35, 38.05), (117.15, 38.65),
        (117.30, 39.15), (117.95, 39.35), (118.95, 39.55), (119.55, 39.95),
        (119.6, 39.9), (119.0, 39.4), (118.3, 39.15), (117.65, 39.0),
        (117.7, 38.5), (118.4, 37.9), (118.9, 37.4), (119.3, 37.15), (118.6, 37.25),
    ],
    [
        (120.7, 32.8), (120.1, 33.9), (119.5, 34.6), (119.45, 34.45),
        (119.85, 33.80), (120.42, 32.75), (120.7, 32.8),
    ],
]

RIVER_LINES = {
    "黄河": (
        [
            (96.5, 35.0), (99.0, 34.5), (101.8, 35.6), (103.8, 36.1), (105.6, 37.3),
            (106.7, 38.9), (106.9, 39.8), (108.5, 40.45), (110.8, 40.1), (111.1, 39.2),
            (110.7, 38.0), (110.5, 36.7), (110.28, 34.64), (111.15, 34.76), (112.79, 34.86),
            (114.03, 35.02), (114.95, 35.88), (116.10, 36.90), (117.75, 38.45),
        ],
        4.2, True,
    ),
    "渭水": ([(104.2, 34.8), (105.8, 34.55), (107.4, 34.36), (108.95, 34.38), (110.28, 34.64)], 2.5, True),
    "汾水": ([(112.1, 38.4), (112.47, 37.70), (112.1, 36.9), (111.5, 36.1), (110.4, 35.55)], 2.0, False),
    "淮水": ([(113.4, 32.4), (115.2, 32.40), (117.18, 32.85), (118.8, 33.25), (120.2, 33.9)], 2.6, True),
    "长江": (
        [
            (95.5, 33.2), (97.5, 31.2), (99.1, 29.0), (100.3, 27.1), (102.6, 26.5),
            (104.6, 28.8), (106.5, 29.6), (108.4, 30.7), (111.3, 30.65),
            (112.20, 30.28), (113.0, 29.5), (114.30, 30.58), (115.95, 30.02),
            (117.5, 30.8), (118.45, 31.68), (119.42, 32.28), (120.8, 31.9),
        ],
        4.2, True,
    ),
    "嘉陵江": ([(105.6, 33.2), (106.1, 31.8), (106.3, 30.5), (106.5, 29.6)], 2.0, False),
    "岷江": ([(103.6, 32.5), (103.8, 31.0), (103.9, 29.6), (104.6, 28.8)], 2.0, False),
    "澜沧江": ([(95.2, 32.8), (97.5, 30.8), (98.9, 28.6), (99.4, 25.8), (100.6, 22.8), (101.2, 21.0)], 2.2, False),
    "怒江": ([(94.0, 31.6), (96.5, 30.2), (98.6, 28.0), (98.9, 25.2), (98.6, 22.5)], 2.0, False),
    "汉水": ([(106.8, 33.05), (109.0, 32.7), (110.8, 32.5), (112.14, 32.02), (114.25, 30.58)], 2.2, False),
    "湘江": ([(110.67, 25.55), (111.8, 26.5), (112.55, 27.1), (112.92, 28.23), (113.05, 29.45)], 2.4, True),
    "闽江": ([(117.8, 27.2), (118.32, 27.04), (118.8, 26.5), (119.35, 26.05), (119.65, 26.0)], 2.0, False),
    "珠江": ([(105.5, 24.5), (107.5, 23.7), (110.1, 23.4), (111.8, 23.15), (113.26, 23.08), (113.8, 22.6)], 3.0, True),
    "赣江": ([(114.95, 25.85), (115.05, 27.15), (115.88, 28.68), (116.15, 29.75)], 2.1, False),
    "红河": ([(100.5, 25.1), (102.8, 23.2), (105.0, 21.6), (106.5, 20.6)], 2.0, False),
}

CANALS = {
    "大运河": [(114.35, 34.80), (115.8, 34.1), (117.3, 33.2), (118.6, 32.8), (119.42, 32.39), (120.1, 31.3), (120.2, 30.25)],
    "灵渠": [(110.29, 25.27), (110.67, 25.61)],
}

# 高原台地与大地形隆起（连续青藏高原整块抬升 + 川西横断基底 + 云贵高原 + 陕甘黄土 + 东南丘陵）
HILL_PLATEAUS = [
    # 青藏高原整体连续高台（确保西侧 84°~102°E 整片呈现高海拔高原而非平地）
    ([(84.0, 41.0), (92.0, 40.5), (96.0, 38.0), (99.5, 36.5), (101.8, 34.0), (101.6, 30.2), (99.5, 27.5), (95.0, 27.0), (84.0, 28.0)], 0.62, 6.2),
    ([(93.0, 34.0), (96.5, 32.8), (99.2, 30.8), (100.8, 28.5)], 0.72, 3.2),
    # 四川盆地四周山地环基 + 横断过渡坡
    ([(101.8, 31.5), (102.6, 29.0), (101.5, 26.5)], 0.56, 2.0),
    # 云贵高原喀斯特隆起
    ([(100.5, 25.8), (103.5, 26.2), (106.6, 26.4), (105.5, 23.6), (101.8, 23.2)], 0.44, 2.3),
    # 陕甘黄土高原—六盘—祁连过渡带
    ([(97.0, 38.2), (101.5, 37.0), (105.0, 36.2), (108.2, 37.4), (109.8, 38.2)], 0.42, 2.2),
    # 江南丘陵、浙闽丘陵、两广丘陵与湘鄂西武陵—雪峰基底（体现长江以南大片丘陵山地而非大平原）
    ([(109.0, 30.2), (110.2, 28.4), (110.8, 26.8), (112.2, 26.0)], 0.35, 1.75),
    ([(112.5, 27.5), (114.2, 27.0), (116.2, 27.2), (118.2, 28.5), (119.8, 29.6)], 0.28, 1.95),
    ([(118.8, 28.6), (119.8, 27.2), (118.8, 25.8), (117.4, 24.8)], 0.31, 1.65),
    ([(107.5, 23.0), (109.8, 23.6), (112.2, 24.2), (114.8, 24.4), (116.4, 23.8)], 0.26, 1.75),
    # 滇南—长山中低山与十万大山过渡带（消除左下角无肌理大片平坦感）
    ([(99.2, 22.8), (101.8, 21.4), (104.2, 20.2), (105.4, 18.6)], 0.34, 1.85),
    # 台湾中央山脉与海南五指山台地
    ([(121.62, 24.85), (121.32, 24.20), (121.08, 23.48), (120.88, 22.65), (120.82, 22.15)], 0.38, 0.54),
    ([(109.30, 18.70), (109.72, 18.96), (110.05, 19.22)], 0.30, 0.56),
    # 朝鲜半岛（长白山—盖马高原—太白山脉）与日本列岛（九州—四国—中国地方—纪伊山地）
    ([(127.00, 41.20), (128.40, 40.50), (127.80, 39.20), (128.40, 37.80), (128.60, 36.20), (127.40, 35.40)], 0.36, 1.05),
    ([(130.80, 32.80), (132.80, 33.60), (134.80, 34.40), (136.20, 35.60)], 0.34, 0.85),
]

# 山脉主脊线（叠加域扭曲+分形支脉，呈天然树枝状凹凸山岭）
MOUNTAIN_SPINES = [
    ([(95.5, 32.0), (97.5, 29.5), (98.4, 26.8), (98.6, 24.0)], 0.86, 0.75),
    ([(97.2, 32.6), (98.6, 30.2), (99.2, 27.5), (99.6, 24.8)], 0.88, 0.72),
    ([(99.0, 33.4), (100.0, 30.8), (100.6, 28.2), (101.0, 25.8)], 0.92, 0.76),
    ([(101.0, 33.8), (101.9, 31.4), (102.3, 29.3), (102.6, 27.2)], 0.94, 0.78),
    ([(103.0, 33.6), (103.7, 31.9), (103.0, 29.9)], 0.76, 0.65),
    ([(104.2, 32.9), (106.8, 32.4), (109.5, 31.6), (110.8, 30.8)], 0.70, 0.64),
    ([(95.2, 39.2), (98.5, 38.3), (101.5, 37.3), (103.6, 36.8)], 0.84, 0.78),
    ([(105.4, 36.4), (106.1, 35.3), (106.5, 34.4)], 0.56, 0.52),
    ([(104.3, 34.1), (106.8, 33.9), (108.8, 33.78), (110.2, 34.18), (111.0, 34.32)], 0.86, 0.58),
    ([(112.3, 35.15), (113.15, 35.95), (113.65, 37.00), (113.95, 38.10), (114.35, 39.10)], 0.82, 0.56),
    ([(110.95, 35.80), (111.20, 37.00), (111.55, 38.20), (112.25, 39.15)], 0.72, 0.54),
    ([(113.6, 32.35), (114.8, 31.70), (116.1, 31.20)], 0.60, 0.54),
    ([(117.0, 36.18), (117.8, 36.26), (118.5, 36.02)], 0.58, 0.44),
    ([(119.0, 29.1), (118.52, 28.36), (118.0, 27.4), (117.2, 26.4), (116.3, 25.4)], 0.68, 0.58),
    ([(109.5, 25.0), (111.2, 25.3), (113.0, 25.2), (114.6, 25.4), (115.8, 25.2)], 0.66, 0.60),
    # 江南—浙闽—两广丘陵主脊（雪峰、罗霄、黄山天目、括苍戴云、十万大山、云开莲花）
    ([(110.7, 28.5), (110.35, 27.3), (109.9, 26.1)], 0.54, 0.52),
    ([(114.1, 27.9), (113.9, 26.7), (114.1, 25.6)], 0.50, 0.48),
    ([(117.5, 30.2), (118.2, 29.9), (119.2, 30.1), (118.4, 29.0)], 0.50, 0.48),
    ([(120.7, 29.2), (120.3, 28.1), (119.3, 26.9), (118.3, 25.8)], 0.52, 0.48),
    ([(107.6, 21.9), (108.9, 22.4), (110.4, 22.7)], 0.46, 0.46),
    ([(111.3, 22.9), (112.1, 23.4), (114.6, 23.6), (116.2, 23.7)], 0.46, 0.45),
    ([(100.2, 22.4), (102.6, 21.4), (104.2, 19.6), (105.2, 18.2)], 0.52, 0.55),
    # 台湾中央山脉主脊与海南五指山主脊
    ([(121.62, 24.85), (121.32, 24.20), (121.08, 23.48), (120.88, 22.65), (120.82, 22.15)], 0.68, 0.34),
    ([(109.30, 18.70), (109.72, 18.96), (110.05, 19.22)], 0.58, 0.36),
    # 朝鲜半岛山脉主脊（狼林—太白—小白）
    ([(127.20, 41.20), (128.30, 40.20), (127.30, 39.10), (128.20, 37.80), (128.90, 36.40)], 0.72, 0.50),
    ([(128.20, 37.20), (127.50, 36.20), (127.20, 35.20)], 0.58, 0.42),
    # 日本列岛山脊（九州山地、四国山地、中国—近畿山脊）
    ([(130.90, 33.20), (130.90, 32.10), (130.50, 31.40)], 0.62, 0.34),
    ([(132.70, 33.50), (133.50, 33.80), (134.20, 33.75)], 0.58, 0.32),
    ([(131.60, 34.40), (133.20, 35.00), (134.80, 35.25), (136.40, 36.00)], 0.64, 0.40),
]

VALLEY_CARVES = [
    # 四川盆地平洼底盆（显出四周环山）
    ([(104.0, 30.8), (105.6, 30.6), (107.2, 30.4), (106.0, 29.6), (104.3, 29.8)], 0.78, 1.35),
    # 关中渭河平川
    ([(107.0, 34.4), (109.0, 34.35), (110.3, 34.6)], 0.68, 0.40),
    # 华北与黄淮大平原
    ([(114.5, 34.5), (115.8, 36.5), (116.8, 38.5)], 0.82, 1.55),
    ([(114.2, 33.0), (116.8, 32.8), (119.2, 32.4)], 0.82, 1.40),
    # 沿江、洞庭、鄱阳与珠三角狭窄冲积平原（不淹没大片江南丘陵）
    ([(112.0, 29.8), (114.5, 30.3), (117.0, 30.9), (119.5, 31.8)], 0.72, 0.62),
    ([(112.5, 29.2), (112.8, 28.5)], 0.55, 0.42),
    ([(115.9, 29.4), (116.1, 28.6)], 0.55, 0.42),
    ([(112.8, 23.2), (113.4, 23.0), (114.0, 22.8)], 0.68, 0.46),
]

MOUNTAIN_DISPLAY_LABELS = [
    (98.2, 33.4, "青 藏 高 原", 0),
    (99.5, 28.3, "横 断 山 脉", 82),
    (105.6, 30.4, "四川盆地", 0),
    (104.2, 25.6, "云 贵 高 原", 6),
    (113.65, 37.35, "太 行 山", 72),
    (107.60, 33.75, "秦   岭", -4),
    (118.20, 28.05, "仙霞·武夷", 62),
    (112.40, 25.18, "南 岭 五 岭", 0),
    (114.35, 27.35, "江南丘陵", 12),
    (117.75, 36.22, "泰 山", 8),
    (114.90, 31.65, "大 别 山", -16),
    (121.05, 23.60, "台 湾", 68),
    (109.72, 19.05, "海 南", 12),
    (127.65, 36.60, "朝鲜半岛", 0),
    (132.85, 34.75, "日 本", 0),
]

RIVER_DISPLAY_LABELS = [
    (110.55, 36.85, "黄 河", 86),
    (115.95, 36.80, "黄河", 44),
    (115.65, 30.25, "长   江", 22),
    (116.80, 32.72, "淮 水", 8),
    (112.60, 27.35, "湘 江", 72),
    (111.50, 23.28, "珠 江", -6),
]


def fit_aspect_bounds(lon_min: float, lon_max: float, lat_min: float, lat_max: float, x_stretch: float = 1.0):
    lon_c = 0.5 * (lon_min + lon_max)
    lat_c = 0.5 * (lat_min + lat_max)
    cos_c = math.cos(math.radians(lat_c))
    target_ratio = (16.0 / 9.0) / max(x_stretch, 0.5)
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
    x0, x1, y0, y1 = bounds
    return (lon - x0) / (x1 - x0) * W, (lat - y0) / (y1 - y0) * H


def _dist_to_polyline(LON, LAT, pts):
    d2 = np.full(LON.shape, 1e9, dtype=np.float32)
    for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
        dx, dy = x2 - x1, y2 - y1
        seg2 = dx * dx + dy * dy + 1e-12
        t = np.clip(((LON - x1) * dx + (LAT - y1) * dy) / seg2, 0.0, 1.0)
        px = x1 + t * dx
        py = y1 + t * dy
        d2 = np.minimum(d2, (LON - px) ** 2 + (LAT - py) ** 2)
    return np.sqrt(d2)


def ridged_multifractal_2d(h, w, octaves=(18.0, 8.5, 4.0, 1.8), seed=874):
    rng = np.random.default_rng(seed)
    acc = np.zeros((h, w), dtype=np.float32)
    amp = 0.45
    w_sum = 0.0
    for sig in octaves:
        n = gaussian_filter(rng.normal(0.0, 1.0, (h, w)).astype(np.float32), sigma=float(sig))
        mx = float(np.max(np.abs(n))) + 1e-6
        ridge = 1.0 - np.abs(n / mx) ** 0.85
        acc += ridge * amp
        w_sum += amp
        amp *= 0.65
    return np.clip(acc / max(w_sum, 1e-6), 0.0, 1.0)


def compute_hillshade(elev, az_deg=315.0, alt_deg=39.0, z_scale=11.5):
    dy, dx = np.gradient(elev * z_scale)
    az = math.radians(az_deg)
    alt = math.radians(alt_deg)
    lx = math.cos(alt) * math.sin(az)
    ly = math.cos(alt) * math.cos(az)
    lz = math.sin(alt)
    norm = np.sqrt(dx * dx + dy * dy + 1.0)
    hs = (-dx * lx - dy * ly + lz) / norm
    return np.clip(hs, 0.08, 1.0)


def _macro_relief_material(elev, seed=879):
    rng = np.random.default_rng(seed)
    small_elev = elev[::2, ::2].astype(np.float32)
    shape = small_elev.shape
    lowland = 1.0 - np.clip((small_elev - 0.12) / 0.22, 0.0, 1.0)
    foothill = np.exp(-((small_elev - 0.24) / 0.12) ** 2) * np.clip((small_elev - 0.06) / 0.08, 0.0, 1.0)
    upland = np.clip((small_elev - 0.18) / 0.38, 0.0, 1.0)

    base_smooth = gaussian_filter(small_elev, sigma=3.5)
    gy, gx = np.gradient(base_smooth)
    spurs, strike = steerable_slope_fields(rng, shape, gaussian_filter(gx, 2.2), gaussian_filter(gy, 2.2), sigma_along=10.5, sigma_across=1.6)
    soil_macro = texture_field(rng, shape, (16.0, 26.0))
    soil_mid = texture_field(rng, shape, (6.0, 9.0))
    rock = texture_field(rng, shape, (2.6, 3.2))
    grain = texture_field(rng, shape, (0.85, 1.3))

    curv = gaussian_filter(small_elev, sigma=5.5) - gaussian_filter(small_elev, sigma=1.4)
    piedmont_ao = np.clip(curv * 14.0, -0.045, 0.055) * (0.45 * upland + 0.80 * foothill)

    rough_elev = (
        small_elev
        + upland * (0.036 * spurs + 0.024 * strike + 0.016 * rock + 0.008 * grain)
        + foothill * (0.022 * spurs + 0.009 * strike + 0.007 * rock)
    )
    shade = compute_hillshade(small_elev, z_scale=11.5)
    rough_shade = compute_hillshade(rough_elev, z_scale=11.5)

    material = (
        1.0
        + 0.038 * lowland * soil_macro
        + 0.014 * lowland * soil_mid
        + 0.010 * grain
        + 0.024 * rock * upland
        + 0.018 * spurs * (0.65 * upland + 0.55 * foothill)
        - piedmont_ao
        + 0.58 * (rough_shade - shade)
    )
    earth_shift = resize_field((lowland * (0.65 * soil_macro + 0.35 * soil_mid)).astype(np.float32), elev.shape)
    return np.clip(resize_field(material, elev.shape), 0.72, 1.30), earth_shift


def _finish_macro_water(sea_canvas, sea, dist_coast, seed=881):
    rng = np.random.default_rng(seed)
    shape = dist_coast.shape
    ts = tuple((s + 1) // 2 for s in shape)
    drift = resize_field(texture_field(rng, ts, (7.0, 26.0)), shape)[sea]
    ripples = resize_field(texture_field(rng, ts, (1.4, 10.5)), shape)[sea]
    glints = np.clip(ripples * 1.15 + 0.35 * drift - 0.35, 0.0, 1.0) ** 2

    d = dist_coast[sea]
    inner_shoal = np.exp(-((d - 14.0) / 16.0) ** 2)
    shelf = np.exp(-(d / 122.0) ** 1.45)
    terrace = 0.5 * (1.0 + np.tanh((46.0 - d) / 10.5))

    sea_canvas[sea] += shelf[:, None] * np.array([6.0, 15.0, 21.0])
    sea_canvas[sea] += terrace[:, None] * np.array([7.5, 13.5, 14.0])
    sea_canvas[sea] += inner_shoal[:, None] * np.array([10.0, 15.0, 10.0])
    sheen = (2.2 + 3.6 * shelf) * drift + (1.4 + 3.8 * terrace) * ripples + 9.5 * glints * (0.35 + 0.65 * shelf)
    sea_canvas[sea] += sheen[:, None] * np.array([0.72, 0.90, 1.0])


def build_relief_terrain(bounds, W=1920, H=1080):
    x0, x1, y0, y1 = bounds
    sw, sh = 960, 540
    xs = np.linspace(x0, x1, sw, dtype=np.float32)
    ys = np.linspace(y0, y1, sh, dtype=np.float32)
    LON, LAT = np.meshgrid(xs, ys)

    sea_s = np.zeros((sh, sw), dtype=bool)
    pts_s = np.column_stack([LON.ravel(), LAT.ravel()])
    for poly in SEA_POLYS:
        sea_s |= MplPath(poly).contains_points(pts_s).reshape(sh, sw)
    for poly in ISLAND_POLYS:
        sea_s &= ~MplPath(poly).contains_points(pts_s).reshape(sh, sw)
    land_s = ~sea_s

    # 二维域扭曲网格：消除山脉几何“平滑香肠感”，生成真实树枝状山脊支脉
    rng_warp = np.random.default_rng(873)
    wx = texture_field(rng_warp, (sh, sw), (18.0, 18.0)) * 0.42 + texture_field(rng_warp, (sh, sw), (6.5, 6.5)) * 0.16
    wy = texture_field(rng_warp, (sh, sw), (18.0, 18.0)) * 0.38 + texture_field(rng_warp, (sh, sw), (6.5, 6.5)) * 0.14
    LON_W = LON + wx
    LAT_W = LAT + wy

    elev = np.full((sh, sw), 0.06, dtype=np.float32)
    for pts, h_val, rad in HILL_PLATEAUS:
        d = _dist_to_polyline(LON_W, LAT_W, smooth_polyline(pts, 4))
        elev = np.maximum(elev, h_val * np.exp(-(d / rad) ** 2 * 1.15))
    for pts, depth, rad in VALLEY_CARVES:
        d = _dist_to_polyline(LON + wx * 0.4, LAT + wy * 0.4, smooth_polyline(pts, 4))
        elev *= np.clip(1.0 - depth * np.exp(-(d / rad) ** 2), 0.12, 1.0)
    for pts, h_val, rad in MOUNTAIN_SPINES:
        d = _dist_to_polyline(LON_W, LAT_W, smooth_polyline(pts, 5))
        elev = np.maximum(elev, h_val * np.exp(-(d / rad) ** 1.6))

    # 河谷下切（尤其青藏—横断三大峡谷：金沙江、澜沧江、怒江）
    for rname, (rpts, rwidth, is_maj) in RIVER_LINES.items():
        d = _dist_to_polyline(LON, LAT, rpts)
        gw = 0.24 if rname in ("长江", "黄河", "澜沧江", "怒江") else 0.16
        carve = np.where(elev > 0.30, 0.58 if rname in ("长江", "澜沧江", "怒江") else 0.44, 0.22)
        elev *= np.clip(1.0 - carve * np.exp(-(d / gw) ** 2), 0.05, 1.0)

    # 长江以南与西南多尺度丘陵鼓包肌理（呈现连绵低矮丘陵感，与北方大平原彻底拉开层次）
    rng_hill = np.random.default_rng(887)
    knoll_a = np.abs(texture_field(rng_hill, (sh, sw), (4.6, 4.6)))
    knoll_b = np.abs(texture_field(rng_hill, (sh, sw), (2.2, 2.2)))
    hill_knolls = np.clip(0.58 * knoll_a + 0.42 * knoll_b, 0.0, 1.0)
    south_mask = np.clip((30.6 - LAT) / 2.0, 0.0, 1.0) * np.clip((LON - 103.5) / 2.2, 0.0, 1.0) * land_s
    south_hill_zone = south_mask * np.clip((elev - 0.09) / 0.14, 0.0, 1.0) * np.clip((0.50 - elev) / 0.20, 0.0, 1.0)
    elev = np.maximum(elev, elev + 0.13 * hill_knolls * south_hill_zone)

    # 丘陵、高原与横断山脊叠加高对比分形树枝肌理
    ridge_tex = ridged_multifractal_2d(sh, sw, octaves=(14.0, 7.0, 3.2, 1.4), seed=875)
    mtn_weight = np.clip((elev - 0.09) / 0.25, 0.0, 1.0)
    elev = elev * (1.0 - 0.54 * mtn_weight) + (elev * ridge_tex * 1.60) * (0.54 * mtn_weight)
    elev = gaussian_filter(elev, sigma=0.65)
    elev = np.clip(elev, 0.0, 1.05)
    elev[~land_s] = 0.0

    hs_s = compute_hillshade(elev, az_deg=315.0, alt_deg=38.0, z_scale=12.0)
    rmod_s = np.clip(0.54 + 0.64 * hs_s - 0.12 * np.clip(elev, 0, 1), 0.36, 1.20)

    elev_f = np.clip(resize_field(elev, (H, W)), 0.0, 1.05)
    rmod_f = np.clip(resize_field(rmod_s, (H, W)), 0.36, 1.20)

    xs_f = np.linspace(x0, x1, W, dtype=np.float32)
    ys_f = np.linspace(y0, y1, H, dtype=np.float32)
    LON_F, LAT_F = np.meshgrid(xs_f, ys_f)
    pts_f = np.column_stack([LON_F.ravel(), LAT_F.ravel()])

    sea_mask = np.zeros((H, W), dtype=bool)
    for poly in SEA_POLYS:
        sea_mask |= MplPath(poly).contains_points(pts_f).reshape(H, W)
    for poly in ISLAND_POLYS:
        sea_mask &= ~MplPath(poly).contains_points(pts_f).reshape(H, W)
    land_mask = ~sea_mask

    anc_mask = np.zeros((H, W), dtype=bool)
    for poly in ANCIENT_COAST_POLYS:
        anc_mask |= MplPath(poly).contains_points(pts_f).reshape(H, W)
    anc_mask &= land_mask

    # 预构建《安史之乱》同款高质量双阵营陆地色板 + 深海纹理（只在初始化运行一次！）
    mat, earth_shift = _macro_relief_material(elev_f)
    rmod_eff = rmod_f * mat
    # 高原高海拔叠入青藏岩石/寒峰灰白渐变
    rock_mix = np.clip((elev_f - 0.32) / 0.46, 0.0, 0.56)

    palette = {
        "TANG": (222.0, 134.0, 96.0),   # 大唐朝廷：暖朱砂赭红
        "QI": (82.0, 138.0, 212.0),     # 黄巢大齐：鲜明冷群青蔚蓝
    }
    faction_land = {}
    for fk, (tr, tg, tb) in palette.items():
        r_ch = tr * (1.0 - rock_mix) + 216.0 * rock_mix
        g_ch = tg * (1.0 - rock_mix) + 210.0 * rock_mix
        b_ch = tb * (1.0 - rock_mix) + 204.0 * rock_mix
        arr = np.zeros((H, W, 3), dtype=np.float32)
        arr[land_mask, 0] = r_ch[land_mask] * rmod_eff[land_mask]
        arr[land_mask, 1] = g_ch[land_mask] * rmod_eff[land_mask]
        arr[land_mask, 2] = b_ch[land_mask] * rmod_eff[land_mask]
        es = (earth_shift[land_mask, None] * np.array([3.6, 2.6, -2.4])).astype(np.float32)
        arr[land_mask] += es
        faction_land[fk] = np.clip(arr, 0, 255).astype(np.uint8)

    near_water = np.exp(-distance_transform_edt(land_mask)[anc_mask] / 44.0)
    near_water_delta = (near_water[:, None] * np.array([-8.5, 2.0, 7.0])).astype(np.float32)

    dist_coast = distance_transform_edt(sea_mask)
    sea_depth = np.clip(dist_coast / 55.0, 0.0, 1.0)
    sea_canvas = np.zeros((H, W, 3), dtype=float)
    sea_canvas[sea_mask, 0] = 56.0 * (1.0 - sea_depth[sea_mask]) + 18.0 * sea_depth[sea_mask]
    sea_canvas[sea_mask, 1] = 104.0 * (1.0 - sea_depth[sea_mask]) + 56.0 * sea_depth[sea_mask]
    sea_canvas[sea_mask, 2] = 152.0 * (1.0 - sea_depth[sea_mask]) + 102.0 * sea_depth[sea_mask]
    _finish_macro_water(sea_canvas, sea_mask, dist_coast)
    sea_glow = np.clip(1.0 - np.maximum(0.0, dist_coast - 1.2) / 5.5, 0.0, 1.0) * 0.65
    sea_canvas[sea_mask] = sea_canvas[sea_mask] * (1.0 - sea_glow[sea_mask, None]) + 232.0 * sea_glow[sea_mask, None]
    coast_edge = sea_mask & (dist_coast <= 2.4)
    sea_canvas[coast_edge] = [26.0, 24.0, 22.0]

    return dict(
        bounds=bounds, W=W, H=H,
        elev=elev_f, sea_mask=sea_mask, land_mask=land_mask, anc_mask=anc_mask,
        land_half=(land_mask[::2, ::2] & True),
        faction_land=faction_land, near_water_delta=near_water_delta,
        sea_rgb=np.clip(sea_canvas[sea_mask], 0, 255).astype(np.uint8),
        anc_base=(
            faction_land["TANG"][anc_mask].astype(np.float32)
        ),
    )


def _geographic_anchors(city_control: Dict[str, str]) -> List[Tuple[float, float, str]]:
    """补充西部高原、巴蜀、河朔与辽东等未设城池区域锚点，确保全国无空洞，且随周边重镇同色。"""
    ca = city_control.get("CHANGAN", "TANG")
    gz = city_control.get("GUANGZHOU", "TANG")
    fz = city_control.get("FUZHOU", "TANG")
    tz = city_control.get("TANZHOU", "TANG")
    jl = city_control.get("JIANGLING", "TANG")
    yq = city_control.get("YUANQU", "TANG")
    ty = city_control.get("TAIYUAN", "TANG")
    return [
        # 青藏、川蜀、甘陕西部核心（唐僖宗避难蜀地，始终属唐）
        (95.5, 34.0, "TANG"), (97.5, 30.0, "TANG"), (99.0, 26.0, "TANG"),
        (103.8, 30.8, "TANG"), (104.5, 35.5, "TANG"), (103.5, 25.2, "TANG"),
        (106.5, 29.5, "TANG"), (107.2, 26.5, "TANG"),
        # 随动态势力同步延伸的区域锚点，保证版图成片不碎裂
        (112.5, 38.0, ty), (116.5, 38.8, "TANG"), (119.5, 37.0, "TANG"),
        (107.5, 34.3, ca), (109.5, 33.8, ca),
        (114.8, 22.8, gz), (118.2, 25.0, fz), (112.2, 27.0, tz), (111.5, 30.5, jl),
        (116.5, 35.8, yq),
        (121.0, 23.6, "TANG"), (109.7, 19.1, "TANG"),
        (127.8, 37.5, "TANG"), (131.0, 32.6, "TANG"), (133.8, 34.8, "TANG"),
    ]


def compute_smoothed_faction_scores(
    relief,
    cities_dict: Dict[str, Dict],
    city_control: Dict[str, str],
    extra_anchors: List[Tuple[float, float, str, float]] | None = None,
) -> np.ndarray:
    """在 480x270 网格上按山脉阻隔加权计算连续势力差分数场（正值=大齐蓝，负值=大唐红）。"""
    bounds = relief["bounds"]
    qw, qh = 480, 270
    lon0, lon1, lat0, lat1 = bounds
    cache = relief.setdefault("_score_grid_cache", {})
    if not cache:
        qlons = np.linspace(lon0, lon1, qw, dtype=np.float32)
        qlats = np.linspace(lat0, lat1, qh, dtype=np.float32)
        QGX, QGY = np.meshgrid(qlons, qlats)
        elev_q = np.asarray(
            Image.fromarray(np.clip(relief["elev"] * 255.0, 0, 255).astype(np.uint8), mode="L").resize((qw, qh), Image.Resampling.BILINEAR),
            dtype=np.float32,
        ) / 255.0
        cache["QGX"], cache["QGY"] = QGX, QGY
        cache["mtn_barrier"] = 1.0 - 0.48 * np.clip((elev_q - 0.30) / 0.45, 0.0, 1.0)
        cache["cos_lat"] = math.cos(math.radians(0.5 * (lat0 + lat1)))

    QGX, QGY = cache["QGX"], cache["QGY"]
    mtn_barrier = cache["mtn_barrier"]
    cos_lat = cache["cos_lat"]

    s_tang = np.zeros((qh, qw), dtype=np.float32)
    s_qi = np.zeros((qh, qw), dtype=np.float32)

    for cid, fac in city_control.items():
        c = cities_dict[cid]
        dx = (QGX - c["lon"]) * cos_lat
        dy = QGY - c["lat"]
        d2 = dx * dx + dy * dy
        w = 1.38 if c["kind"] == "capital" else (1.15 if c["kind"] in ("pass", "ferry") else 1.05)
        field = w * mtn_barrier * np.exp(-d2 / (2.65 ** 2))
        if fac == "QI":
            s_qi = np.maximum(s_qi, field)
        else:
            s_tang = np.maximum(s_tang, field)

    for alon, alat, afk in _geographic_anchors(city_control):
        dx = (QGX - alon) * cos_lat
        dy = QGY - alat
        field = 1.02 * np.exp(-(dx * dx + dy * dy) / (3.15 ** 2))
        if afk == "QI":
            s_qi = np.maximum(s_qi, field)
        else:
            s_tang = np.maximum(s_tang, field)

    if extra_anchors:
        for alon, alat, afk, strength in extra_anchors:
            dx = (QGX - alon) * cos_lat
            dy = QGY - alat
            field = strength * mtn_barrier * np.exp(-(dx * dx + dy * dy) / (2.55 ** 2))
            if afk == "QI":
                s_qi = np.maximum(s_qi, field)
            else:
                s_tang = np.maximum(s_tang, field)

    return gaussian_filter(s_qi - s_tang, sigma=3.8).astype(np.float32)


def compose_macro_from_scores(relief, diff_low: np.ndarray) -> np.ndarray:
    """极速合成全屏 1920x1080 3D 立体势力地图（白光晕 + 深墨实线战线 + 古海岸 + 海面反光）。"""
    W, H = relief["W"], relief["H"]
    land = relief["land_mask"]
    anc = relief["anc_mask"]
    sea = relief["sea_mask"]

    # 在半分辨率 (960x540) 做 EDT 距离场计算再上采样，提速 12 倍且保持顺滑抗锯齿
    hw, hh = W // 2, H // 2
    diff_h = np.asarray(Image.fromarray(diff_low.astype(np.float32), mode="F").resize((hw, hh), Image.Resampling.BICUBIC), dtype=np.float32)
    land_h = relief["land_half"]
    qi_h = (diff_h > 0.0) & land_h
    b_h = np.zeros((hh, hw), dtype=bool)
    b_h[:, :-1] |= (qi_h[:, :-1] != qi_h[:, 1:]) & land_h[:, :-1] & land_h[:, 1:]
    b_h[:-1, :] |= (qi_h[:-1, :] != qi_h[1:, :]) & land_h[:-1, :] & land_h[1:, :]

    diff_f = np.asarray(Image.fromarray(diff_low.astype(np.float32), mode="F").resize((W, H), Image.Resampling.BICUBIC), dtype=np.float32)
    qi_win = (diff_f > 0.0) & land

    base_rgb = relief["faction_land"]["TANG"].copy()
    base_rgb[qi_win] = relief["faction_land"]["QI"][qi_win]

    # 古海岸线浅滩退缩带
    anc_px = base_rgb[anc].astype(np.float32)
    anc_px[:, 0] = anc_px[:, 0] * 0.25 + 178.0 * 0.75
    anc_px[:, 1] = anc_px[:, 1] * 0.25 + 196.0 * 0.75
    anc_px[:, 2] = anc_px[:, 2] * 0.25 + 212.0 * 0.75
    anc_px += relief["near_water_delta"]
    base_rgb[anc] = np.clip(anc_px, 0, 255).astype(np.uint8)

    # 半分辨率白光晕 + 深墨实线（外扩回 1920x1080 依然平滑无锯齿）
    if b_h.any():
        dist_h = distance_transform_edt(~b_h).astype(np.float32)
        wg_h = np.clip(1.0 - np.maximum(0.0, dist_h - 1.0) / 3.4, 0.0, 1.0) * 0.86
        dl_h = np.clip(1.0 - np.maximum(0.0, dist_h - 0.35) / 1.0, 0.0, 1.0) * 0.94
        wg_h[~land_h] = 0.0
        dl_h[~land_h] = 0.0
        wg = np.asarray(Image.fromarray(wg_h, mode="F").resize((W, H), Image.Resampling.BILINEAR), dtype=np.float32)
        dl = np.asarray(Image.fromarray(dl_h, mode="F").resize((W, H), Image.Resampling.BILINEAR), dtype=np.float32)

        m_b = wg > 0.01
        if m_b.any():
            px = base_rgb[m_b].astype(np.float32)
            w_m = wg[m_b, None]
            d_m = dl[m_b, None]
            px = px * (1.0 - w_m) + 250.0 * w_m
            px = px * (1.0 - d_m) + np.array([28.0, 24.0, 22.0], dtype=np.float32) * d_m
            base_rgb[m_b] = np.clip(px, 0, 255).astype(np.uint8)

    base_rgb[sea] = relief["sea_rgb"]
    return base_rgb
