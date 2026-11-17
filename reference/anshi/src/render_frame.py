# -*- coding: utf-8 -*-
"""《安史之乱》B站历史科普风格主渲染引擎（1920×1080）。
融合用户参考图全部核心要素：
1. 全幅唐代华北—中原—关中 3D 立体地形（黄渤海+古海岸线、黄河/渭/汾/淮/大运河、太行/秦岭/恒山）；
2. 全域无缝暖红（唐）vs 冷蓝（燕）势力染色 + 醒目「白光晕 + 深墨实线」战线边界；
3. 黑白靶心城池 `◎` + 朱红重檐关隘城楼 + 竖幅火焰牙边主将帅旗 + 精修步骑小人 + 双描边进攻大箭头；
4. 顶部白字粗黑边大标题（带金黄高亮）+ 底部黑底衬条大字幕，同屏直白推进叙事；
5. 关键战役（T020 灵宝、T040 香积寺等）自动切换至 3D 立体岩石峡谷/台原战术图，--macro 强制输出宏观图。
"""
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patheffects
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from landmarks import make_landmark_sprite, make_war_banner
from sprites import make_sprite
from tactical_map import (
    FACTION_STYLE, FONT_BOLD, FONT_REG, H_PX, SCENES, W_PX,
    _tight_rgba, draw_bilibili_hud, draw_double_stroked_arrow,
    draw_tactical_map, px_to_pt, text_outline,
)
from terrain import (
    CANALS, MOUNTAIN_DISPLAY_LABELS, RIVER_DISPLAY_LABELS, RIVER_LINES,
    build_relief_terrain, compose_macro_map_rgb, fit_aspect_bounds,
    lonlat_to_px, smooth_polyline,
)

ROOT = Path(__file__).resolve().parent.parent
D = json.loads((ROOT / "data" / "anshi_wargame.json").read_text(encoding="utf-8"))
OUTDIR = ROOT / "output"
QADIR = OUTDIR / "qa_960x540"
OUTDIR.mkdir(exist_ok=True)
QADIR.mkdir(exist_ok=True)

city = {c["city_id"]: c for c in D["cities"]}
unit = {u["unit_id"]: u for u in D["units"]}
battle = {b["battle_id"]: b for b in D["battles"]}
events = D["events"]
snaps = {s["tick_id"]: s for s in D["snapshots"]}

# 全幅 16:9 唐代华北—中原—关中宏观视口
MACRO_BOUNDS = fit_aspect_bounds(105.0, 122.8, 32.0, 40.3)
RELIEF = build_relief_terrain(MACRO_BOUNDS, W=W_PX, H=H_PX)

# 核心城池宏观显示名单（筛选战略重镇并错开方位，杜绝密集群互压）
MACRO_CITY_STYLE = {
    "CHANGAN": (-18, -22, "right", "top", True),
    "LUOYANG": (18, -24, "left", "top", True),
    "FANYANG": (22, -16, "left", "top", True),
    "TAIYUAN": (-22, 10, "right", "center", True),
    "FENGXIANG": (-18, 16, "right", "bottom", True),
    "LINGWU": (20, 10, "left", "center", True),
    "SHANZHOU": (0, 24, "center", "bottom", False),
    "BIANZHOU": (20, 18, "left", "bottom", True),
    "YONGQIU": (-16, -20, "right", "top", False),
    "SUIYANG": (20, -20, "left", "top", True),
    "CHANGSHAN": (22, 6, "left", "center", True),
    "BOLING": (-20, 18, "right", "bottom", False),
    "ZHAOJUN": (18, -14, "left", "top", False),
    "XIANGZHOU": (-20, 14, "right", "bottom", True),
    "WEIZHOU_DM": (20, -14, "left", "top", True),
    "BEIZHOU": (22, 0, "left", "center", True),
    "MOZHOU": (20, -14, "left", "top", True),
    "PINGYUAN": (22, 8, "left", "center", True),
    "NANYANG": (0, 22, "center", "bottom", True),
    "XUZHOU": (20, 14, "left", "bottom", False),
    "LINHUAI": (-16, 22, "right", "bottom", False),
    "HEYANG": (-18, 22, "right", "bottom", False),
}

# 雄关要塞图标位置（kind, offset_lbl_dx, offset_lbl_dy, ha, va, disp_name）
MACRO_PASSES = {
    "TONGGUAN": ("pass", -34, -22, "right", "top", "潼关"),
    "TUMEN": ("pass", -38, 18, "right", "center", "井陉土门"),
}

# 特定样帧宏观定制剧本（突出战线对比、帅旗、进攻箭头与科普大字幕）
MACRO_CUSTOM_FRAMES = {
    "T001": dict(
        tick_ref="T001",
        owner_overrides={},
        title_parts=[("天宝十四载十一月 · ", "#FFFFFF"), ("安禄山范阳起兵", "#FFE04D")],
        subtitle="安禄山以讨杨国忠为名率十五万边骑起兵范阳，大唐承平日久猝然遇变",
        arrows=[
            ((116.20, 39.68), (114.70, 38.22), "YAN_AN", 13.5, 0.12, 1.0, "十五万大军南下", (-112, -24)),
        ],
        banners=[
            (115.05, 39.20, "安禄山", "YAN_AN", 128),
            (117.48, 38.92, "史思明", "YAN_AN", 122),
        ],
        sprites=[
            (115.72, 39.15, "YAN_AN", "cavalry", True, None),
            (116.32, 39.35, "YAN_AN", "mixed", True, None),
        ],
    ),
    "T002": dict(
        tick_ref="T002",
        owner_overrides={"XIANGZHOU": "YAN_AN"},
        title_parts=[("天宝十四载十一月 · ", "#FFFFFF"), ("叛军疾驰太行东麓，河北瓦解", "#FFE04D")],
        subtitle="安禄山日行六十里南下，常山、赵郡、魏州、相州望风归附，平原颜真卿孤城备战",
        arrows=[
            ((116.15, 39.55), (114.48, 36.28), "YAN_AN", 14.0, 0.16, 1.0, "疾驰太行东麓", (95, -24)),
        ],
        banners=[
            (113.55, 36.32, "安禄山", "YAN_AN", 132),
            (117.30, 38.25, "史思明", "YAN_AN", 120),
            (117.75, 37.32, "颜真卿", "TANG", 124),
        ],
        sprites=[
            (114.68, 37.18, "YAN_AN", "cavalry", True, None),
        ],
    ),
    "T003": dict(
        tick_ref="T003",
        owner_overrides={},
        title_parts=[("天宝十四载十二月 · ", "#FFFFFF"), ("灵昌津夜渡黄河，兵临中原", "#FFE04D")],
        subtitle="叛军于灵昌津束草木船踏冰强渡黄河；封常清洛阳急募六万新兵、高仙芝屯守陕州",
        arrows=[
            ((114.35, 36.02), (114.52, 35.22), "YAN_AN", 14.0, -0.10, 1.0, "踏冰渡黄河", (92, 8)),
        ],
        banners=[
            (114.95, 35.68, "安禄山", "YAN_AN", 132),
            (111.88, 35.02, "封常清", "TANG", 128),
            (110.95, 35.22, "高仙芝", "TANG", 124),
            (117.75, 37.32, "颜真卿", "TANG", 120),
        ],
        sprites=[
            (114.48, 35.48, "YAN_AN", "cavalry", False, None),
        ],
    ),
    "T004": dict(
        tick_ref="T004",
        owner_overrides={},
        title_parts=[("天宝十四载十二月 · ", "#FFFFFF"), ("陈留（汴州）陷落", "#FFE04D")],
        subtitle="叛军渡河攻克陈留，太守张介然殉国、降卒近万遭屠，中原门户大开",
        arrows=[
            ((114.48, 35.45), (114.35, 34.86), "YAN_AN", 13.5, 0.14, 1.0, "攻陷陈留", (-76, -4)),
        ],
        banners=[
            (115.35, 34.85, "安禄山", "YAN_AN", 132),
            (111.88, 35.02, "封常清", "TANG", 128),
            (110.95, 35.22, "高仙芝", "TANG", 124),
            (117.75, 37.32, "颜真卿", "TANG", 120),
        ],
        sprites=[],
    ),
    "T005": dict(
        tick_ref="T005",
        owner_overrides={},
        title_parts=[("天宝十四载十二月 · ", "#FFFFFF"), ("连克陈留荥阳，兵逼虎牢", "#FFE04D")],
        subtitle="叛军横扫汴州、郑州平原，前锋直抵东京洛阳东面门户虎牢关",
        arrows=[
            ((114.30, 34.80), (113.28, 34.84), "YAN_AN", 14.0, -0.18, 1.0, "西逼虎牢", (0, 38)),
        ],
        banners=[
            (114.70, 35.25, "安禄山", "YAN_AN", 132),
            (111.88, 35.02, "封常清", "TANG", 128),
            (110.95, 35.22, "高仙芝", "TANG", 124),
            (117.75, 37.32, "颜真卿", "TANG", 120),
        ],
        sprites=[],
    ),
    "T006": dict(
        tick_ref="T006",
        owner_overrides={},
        title_parts=[("天宝十四载十二月 · ", "#FFFFFF"), ("封常清虎牢迎战失利", "#FFE04D")],
        subtitle="封常清仓促所募新军在虎牢关败退，安禄山大军直扑东京洛阳城垣",
        arrows=[
            ((113.62, 34.78), (112.56, 34.68), "YAN_AN", 14.0, -0.16, 1.0, "突破虎牢", (0, 36)),
        ],
        banners=[
            (114.70, 35.25, "安禄山", "YAN_AN", 132),
            (111.88, 35.02, "封常清", "TANG", 128),
            (110.95, 35.22, "高仙芝", "TANG", 124),
            (117.75, 37.32, "颜真卿", "TANG", 120),
        ],
        sprites=[],
    ),
    "T007": dict(
        tick_ref="T007",
        owner_overrides={},
        title_parts=[("天宝十四载十二月丁酉 · ", "#FFFFFF"), ("东京洛阳陷落", "#FFE04D")],
        subtitle="洛阳四战四败后沦陷，李憕卢奕殉国，封常清西撤陕州并与高仙芝合兵",
        arrows=[
            ((113.28, 34.76), (112.50, 34.67), "YAN_AN", 14.0, -0.14, 1.0, "攻克洛阳", (0, 36)),
            ((112.32, 34.62), (111.24, 34.76), "TANG", 11.0, 0.14, 0.92, "西撤陕郡", (0, -34)),
        ],
        banners=[
            (114.70, 35.25, "安禄山", "YAN_AN", 132),
            (111.18, 35.28, "封常清", "TANG", 128),
            (109.52, 34.92, "高仙芝", "TANG", 124),
            (117.75, 37.32, "颜真卿", "TANG", 120),
        ],
        sprites=[],
    ),
    "T008": dict(
        tick_ref="T008",
        owner_overrides={},
        title_parts=[("天宝十四载十二月 · ", "#FFFFFF"), ("退保潼关扼险，哥舒翰受命督师", "#FFE04D")],
        subtitle="封常清、高仙芝弃陕郡退守潼关阻住叛军西进，旋遭谗冤杀，玄宗起用哥舒翰守关",
        arrows=[
            ((111.19, 34.78), (110.35, 34.62), "TANG", 12.5, -0.14, 0.95, "退保潼关", (0, 36)),
        ],
        banners=[
            (109.52, 34.88, "哥舒翰", "TANG", 132),
            (111.72, 35.28, "崔乾祐", "YAN_AN", 126),
            (114.70, 35.25, "安禄山", "YAN_AN", 128),
            (117.75, 37.32, "颜真卿", "TANG", 120),
        ],
        sprites=[],
    ),
    "T009": dict(
        tick_ref="T009",
        owner_overrides={},
        title_parts=[("天宝十四载十二月 · ", "#FFFFFF"), ("常山起义，河北十七郡归唐", "#FFE04D")],
        subtitle="颜杲卿于土门诱杀燕将，河北十七郡同日响应并呼应平原颜真卿，切断范阳—洛阳补给线",
        arrows=[
            ((114.25, 38.08), (114.88, 37.76), "TANG", 13.0, 0.16, 1.0, "切断敌后补给", (88, -22)),
            ((115.62, 39.22), (114.78, 38.28), "YAN_AN", 11.5, -0.14, 0.92, "史思明回救", (62, 38)),
        ],
        banners=[
            (113.50, 38.06, "颜杲卿", "TANG", 132),
            (117.75, 37.32, "颜真卿", "TANG", 128),
            (117.30, 38.25, "史思明", "YAN_AN", 120),
            (114.70, 35.25, "安禄山", "YAN_AN", 126),
            (109.52, 34.88, "哥舒翰", "TANG", 124),
        ],
        sprites=[],
    ),
    "T010": dict(
        tick_ref="T010",
        owner_overrides={},
        title_parts=[("天宝十五载正月 · ", "#FFFFFF"), ("安禄山于洛阳称大燕皇帝", "#FFE04D")],
        subtitle="安禄山前阻潼关天险、后震河北义军，遂于天宝十五载元旦在东京洛阳称大燕皇帝",
        arrows=[
            ((112.05, 34.68), (110.52, 34.62), "YAN_AN", 11.0, -0.12, 0.78, "兵阻潼关", (0, 36)),
        ],
        banners=[
            (114.70, 35.25, "安禄山", "YAN_AN", 136),
            (109.52, 34.88, "哥舒翰", "TANG", 128),
            (113.50, 38.06, "颜杲卿", "TANG", 124),
            (117.75, 37.32, "颜真卿", "TANG", 124),
            (117.30, 38.25, "史思明", "YAN_AN", 120),
        ],
        sprites=[],
    ),
    "T011": dict(
        tick_ref="T011",
        owner_overrides={},
        title_parts=[("天宝十五载正月 · ", "#FFFFFF"), ("常山城破，颜杲卿殉国", "#FFE04D")],
        subtitle="史思明、蔡希德回师急攻常山，苦战六日援绝城破，颜杲卿骂贼不屈殉国",
        arrows=[
            ((115.68, 37.93), (114.57, 38.15), "YAN_AN", 12.5, -0.14, 1.0, "史思明攻陷常山", (96, -12)),
        ],
        banners=[
            (116.25, 38.68, "史思明", "YAN_AN", 126),
            (113.55, 38.02, "颜杲卿", "TANG", 128),
            (111.70, 37.65, "李光弼", "TANG", 124),
            (117.75, 37.32, "颜真卿", "TANG", 122),
            (114.70, 35.25, "安禄山", "YAN_AN", 124),
        ],
        sprites=[],
    ),
    "T016": dict(
        tick_ref="T016",
        owner_overrides={},
        title_parts=[("天宝十五载二至四月 · ", "#FFFFFF"), ("郭李出井陉，复常山赵郡", "#FFE04D")],
        subtitle="李光弼、郭子仪合兵出井陉破史思明于九门，收复常山与赵郡；张巡亦起兵固守雍丘",
        arrows=[
            ((112.47, 37.70), (114.25, 38.08), "TANG", 11.5, -0.10, 0.90, None, (0, 0)),
            ((114.25, 38.08), (114.78, 37.75), "TANG", 13.0, 0.14, 1.0, "会师复常山赵郡", (112, -8)),
            ((115.31, 34.45), (114.78, 34.55), "TANG", 9.0, 0.10, 0.80, "张巡守雍丘", (0, -34)),
        ],
        banners=[
            (113.05, 38.62, "郭子仪", "TANG", 128),
            (111.75, 37.62, "李光弼", "TANG", 126),
            (116.25, 38.68, "史思明", "YAN_AN", 124),
            (115.70, 34.50, "张巡", "TANG", 122),
            (109.52, 34.88, "哥舒翰", "TANG", 122),
        ],
        sprites=[],
    ),
    "T019": dict(
        tick_ref="T019",
        owner_overrides={},
        title_parts=[("天宝十五载五月 · ", "#FFFFFF"), ("嘉山捷后围博陵，朝廷促出关", "#FFE04D")],
        subtitle="郭李大破史思明并围博陵，河北十余郡复归唐；然玄宗、杨国忠猜忌催逼哥舒翰出潼关",
        arrows=[
            ((114.78, 38.60), (115.05, 38.52), "TANG", 10.5, 0.12, 0.82, "进围博陵", (74, 22)),
            ((110.30, 34.60), (111.19, 34.78), "TANG", 13.5, 0.12, 1.0, "诏促哥舒翰东出", (28, 42)),
        ],
        banners=[
            (113.05, 38.62, "郭子仪", "TANG", 124),
            (116.25, 38.68, "史思明", "YAN_AN", 124),
            (109.52, 34.88, "哥舒翰", "TANG", 134),
            (111.65, 35.12, "崔乾祐", "YAN_AN", 128),
        ],
        sprites=[],
    ),
    "T021": dict(
        tick_ref="T021",
        owner_overrides={},
        title_parts=[("天宝十五载六月 · ", "#FFFFFF"), ("灵宝西原大败，潼关失守", "#FFE04D")],
        subtitle="哥舒翰二十万大军在灵宝狭道遭伏与火车破阵，残部八千败回又遭部将劫降，潼关遂陷",
        arrows=[
            ((111.19, 34.78), (110.30, 34.60), "YAN_AN", 13.5, -0.18, 1.0, "崔乾祐破潼关", (24, 40)),
        ],
        banners=[
            (111.15, 35.12, "崔乾祐", "YAN_AN", 132),
            (109.38, 34.85, "哥舒翰", "TANG", 128),
            (113.05, 38.62, "郭子仪", "TANG", 122),
            (116.25, 38.68, "史思明", "YAN_AN", 120),
        ],
        sprites=[],
    ),
    "T022": dict(
        tick_ref="T022",
        owner_overrides={},
        title_parts=[("天宝十五载六月 · ", "#FFFFFF"), ("玄宗惶恐弃京西逃", "#FFE04D")],
        subtitle="潼关败报传至长安，唐玄宗黎明密出延秋门仓皇西逃入蜀，关中门户大开",
        arrows=[
            ((108.93, 34.27), (107.15, 33.42), "TANG", 13.0, -0.16, 1.0, "玄宗仓皇幸蜀", (-28, -38)),
            ((110.30, 34.60), (109.15, 34.34), "YAN_AN", 11.5, -0.14, 0.90, "叛军西逼京畿", (28, 46)),
        ],
        banners=[
            (111.10, 35.12, "崔乾祐", "YAN_AN", 128),
            (113.55, 34.95, "安禄山", "YAN_AN", 126),
            (113.05, 38.62, "郭子仪", "TANG", 120),
        ],
        sprites=[],
    ),
    "T023": dict(
        tick_ref="T023",
        owner_overrides={},
        title_parts=[("天宝十五载六月丙申 · ", "#FFFFFF"), ("马嵬驿兵变", "#FFE04D")],
        subtitle="御驾行至马嵬驿，龙武军愤起哗变诛杀杨国忠，玄宗被迫缢杀杨贵妃以平众怒",
        arrows=[
            ((108.93, 34.27), (107.55, 34.15), "TANG", 12.5, -0.14, 0.95, "马嵬军变 · 幸蜀", (0, -38)),
            ((110.30, 34.60), (109.15, 34.34), "YAN_AN", 11.5, -0.14, 0.85, None, (0, 0)),
        ],
        banners=[
            (108.15, 34.86, "陈玄礼", "TANG", 128),
            (111.10, 35.12, "崔乾祐", "YAN_AN", 126),
            (113.55, 34.95, "安禄山", "YAN_AN", 124),
        ],
        sprites=[],
    ),
    "T024": dict(
        tick_ref="T024",
        owner_overrides={},
        title_parts=[("天宝十五载六月 · ", "#FFFFFF"), ("西京长安沦陷", "#FFE04D")],
        subtitle="叛军长驱西入开远门，大唐盛世西京长安沦于燕军之手，两京俱失",
        arrows=[
            ((110.30, 34.60), (108.93, 34.27), "YAN_AN", 14.0, -0.16, 1.0, "叛军进占长安", (24, 42)),
        ],
        banners=[
            (109.75, 34.95, "崔乾祐", "YAN_AN", 134),
            (113.55, 34.95, "安禄山", "YAN_AN", 126),
            (113.05, 38.62, "郭子仪", "TANG", 124),
            (115.70, 34.50, "张巡", "TANG", 122),
        ],
        sprites=[],
    ),
    "T026": dict(
        tick_ref="T026",
        owner_overrides={},
        title_parts=[("至德元载七月 · ", "#FFFFFF"), ("郭李退保，肃宗灵武即位", "#FFE04D")],
        subtitle="郭子仪、李光弼撤出河北退保太原，太子李亨北上灵武即位为唐肃宗，重立中枢抗贼",
        arrows=[
            ((114.57, 38.15), (112.47, 37.70), "TANG", 12.0, -0.12, 0.90, "郭李撤出河北", (-24, -44)),
            ((108.37, 34.29), (106.33, 38.10), "TANG", 13.5, 0.16, 1.0, "太子北上灵武即位", (66, 18)),
        ],
        banners=[
            (107.18, 37.72, "唐肃宗", "TANG", 136),
            (111.75, 37.75, "郭子仪", "TANG", 128),
            (109.60, 34.95, "崔乾祐", "YAN_AN", 126),
            (116.15, 38.68, "史思明", "YAN_AN", 124),
        ],
        sprites=[],
    ),
    "T030": dict(
        tick_ref="T030",
        owner_overrides={},
        title_parts=[("至德二载正月 · ", "#FFFFFF"), ("陈涛斜失利，安庆绪弑逆", "#FFE04D")],
        subtitle="房琯陈涛斜车战惨败，颜真卿弃平原南渡；洛阳城中安庆绪弑父安禄山自立，叛军内裂",
        arrows=[
            ((108.20, 34.26), (108.80, 34.36), "TANG", 11.0, 0.12, 0.85, "陈涛斜挫败", (-18, 38)),
            ((116.58, 37.33), (117.18, 34.26), "TANG", 10.5, -0.14, 0.82, "颜真卿南渡", (68, 10)),
        ],
        banners=[
            (107.15, 34.95, "郭子仪", "TANG", 126),
            (111.75, 37.75, "李光弼", "TANG", 126),
            (113.55, 34.95, "安庆绪", "YAN_AN", 132),
            (116.15, 38.68, "史思明", "YAN_AN", 124),
            (115.70, 34.50, "张巡", "TANG", 122),
        ],
        sprites=[],
    ),
    "T039": dict(
        tick_ref="T039",
        owner_overrides={},
        title_parts=[("至德二载九月 · ", "#FFFFFF"), ("唐回联军大举东征长安", "#FFE04D")],
        subtitle="广平王李俶统郭子仪、李嗣业并回纥葛勒可汗之子叶护精骑，自凤翔浩荡东向西京",
        arrows=[
            ((106.33, 38.10), (107.39, 34.52), "UYGHUR", 12.0, 0.16, 0.90, "回纥铁骑南下助战", (84, 24)),
            ((107.39, 34.52), (108.84, 34.21), "TANG", 14.0, -0.14, 1.0, "十五万大军逼长安", (-10, -40)),
        ],
        banners=[
            (107.05, 35.15, "郭子仪", "TANG", 132),
            (108.15, 35.02, "李嗣业", "TANG", 128),
            (106.15, 35.45, "回纥叶护", "UYGHUR", 130),
            (109.75, 34.95, "安守忠", "YAN_AN", 128),
            (115.70, 34.50, "张巡", "TANG", 122),
        ],
        sprites=[],
    ),
    "T041": dict(
        tick_ref="T041",
        owner_overrides={},
        title_parts=[("至德二载九月 · ", "#FFFFFF"), ("香积寺大捷，收复西京长安", "#FFE04D")],
        subtitle="唐回联军于香积寺斩首六万级，安守忠残部东逃，广平王率大军克复沦陷年余之西京长安",
        arrows=[
            ((107.39, 34.52), (108.93, 34.27), "TANG", 14.0, -0.14, 1.0, "克复西京长安", (-10, -38)),
            ((108.93, 34.27), (111.19, 34.78), "YAN_AN", 11.0, 0.16, 0.85, "安守忠残部东逃", (48, 46)),
        ],
        banners=[
            (108.15, 34.95, "郭子仪", "TANG", 134),
            (109.35, 34.98, "李嗣业", "TANG", 128),
            (106.95, 35.02, "回纥叶护", "UYGHUR", 128),
            (111.65, 35.22, "安守忠", "YAN_AN", 126),
            (115.70, 34.50, "张巡", "TANG", 122),
        ],
        sprites=[],
    ),
    "T044": dict(
        tick_ref="T045",
        owner_overrides={},
        title_parts=[("至德二载十月 · ", "#FFFFFF"), ("新店破敌，收复东京洛阳", "#FFE04D")],
        subtitle="唐回联军乘胜东出潼关，于新店夹击再破燕军主力，一举收复东京洛阳，安庆绪渡河北遁邺城",
        arrows=[
            ((110.30, 34.60), (112.44, 34.67), "TANG", 14.5, -0.16, 1.0, "乘胜收复东京洛阳", (0, -40)),
            ((112.44, 34.67), (114.35, 36.10), "YAN_AN", 11.5, -0.16, 0.88, "安庆绪北遁邺城", (78, -14)),
        ],
        banners=[
            (111.85, 35.18, "郭子仪", "TANG", 136),
            (110.65, 35.15, "李嗣业", "TANG", 128),
            (109.45, 35.10, "回纥叶护", "UYGHUR", 128),
            (113.55, 36.45, "安庆绪", "YAN_AN", 126),
            (116.15, 38.68, "史思明", "YAN_AN", 124),
        ],
        sprites=[],
    ),
    "T020": dict(
        tick_ref="T021",
        owner_overrides={"TONGGUAN": "YAN_AN"},
        title_parts=[("天宝十五载六月 · ", "#FFFFFF"), ("灵宝西原大败，潼关失守", "#FFE04D")],
        subtitle="哥舒翰被迫出潼关东征中伏，二十万大军崩溃，潼关门户随即失守",
        arrows=[
            # 主攻方向：崔乾祐自陕州西进灵宝夺潼关，箭头微向上拱，短标清亮落于上方空白
            ((111.19, 34.78), (110.30, 34.60), "YAN_AN", 13.0, -0.18, 1.0, "夺取潼关", (0, -40)),
            # 河北侧翼参考：郭子仪、李光弼正围博陵
            ((114.57, 38.15), (115.00, 38.52), "TANG", 9.0, 0.12, 0.72, None, (0, 0)),
        ],
        banners=[
            (109.45, 34.72, "哥舒翰", "TANG", 132),
            (111.10, 35.15, "崔乾祐", "YAN_AN", 132),
            (113.45, 38.05, "郭子仪", "TANG", 122),
            (116.25, 38.75, "史思明", "YAN_AN", 122),
        ],
        sprites=[],
    ),
    "T040": dict(
        tick_ref="T041",
        owner_overrides={"CHANGAN": "TANG", "TONGGUAN": "TANG"},
        title_parts=[("至德二载九月 · ", "#FFFFFF"), ("香积寺大捷，唐军收复长安", "#FFE04D")],
        subtitle="广平王李俶与郭子仪统唐回联军十五万大破安守忠，一举收复西京长安",
        arrows=[
            # 主反攻线：凤翔 -> 长安
            ((107.39, 34.52), (108.93, 34.27), "TANG", 14.0, -0.14, 1.0, "收复长安", (0, 36)),
            # 燕军东撤洛阳方向
            ((110.30, 34.60), (112.35, 34.67), "YAN_AN", 10.0, -0.16, 0.85, "安守忠东遁", (10, 38)),
        ],
        banners=[
            (108.15, 34.95, "郭子仪", "TANG", 132),
            (109.45, 34.98, "李嗣业", "TANG", 128),
            (106.95, 35.02, "回纥叶护", "UYGHUR", 128),
            (111.65, 35.22, "安守忠", "YAN_AN", 128),
            (115.62, 34.68, "张巡", "TANG", 122),
        ],
        sprites=[],
    ),
    "T047": dict(
        tick_ref="T049",
        owner_overrides={},
        title_parts=[("乾元元年六月—十月 · ", "#FFFFFF"), ("史思明复叛，九节度围邺城", "#FFE04D")],
        subtitle="史思明复叛再据范阳河北，唐肃宗命郭子仪、李光弼等九节度使六十万大军合围相州邺城",
        arrows=[
            ((116.35, 39.88), (114.57, 38.15), "YAN_SHI", 12.5, 0.14, 0.92, "史思明复叛南侵", (-98, 22)),
            ((112.44, 34.67), (114.35, 36.10), "TANG", 14.0, -0.14, 1.0, "九节度合围邺城", (76, -26)),
        ],
        banners=[
            (112.05, 35.48, "郭子仪", "TANG", 132),
            (111.35, 37.38, "李光弼", "TANG", 128),
            (114.95, 36.20, "安庆绪", "YAN_AN", 126),
            (117.15, 38.85, "史思明", "YAN_SHI", 132),
        ],
        sprites=[],
    ),
    "T062": dict(
        tick_ref="T062",
        owner_overrides={},
        title_parts=[("上元二年二月—三月 · ", "#FFFFFF"), ("邙山失利，史朝义弑父内乱", "#FFE04D")],
        subtitle="鱼朝恩强逼李光弼出战致邙山败绩；燕军内部史朝义于柳泉驿缢杀史思明自立，叛军离心",
        arrows=[
            ((112.50, 34.76), (111.22, 35.36), "TANG", 11.5, 0.16, 0.90, "李光弼退保闻喜", (-82, 42)),
            ((114.35, 36.10), (112.44, 34.67), "YAN_SHI", 12.5, 0.14, 0.92, "柳泉弑逆 · 史朝义自立", (92, -30)),
        ],
        banners=[
            (110.85, 36.15, "李光弼", "TANG", 130),
            (113.75, 35.25, "史朝义", "YAN_SHI", 134),
            (108.15, 34.95, "郭子仪", "TANG", 126),
        ],
        sprites=[],
    ),
    "T068": dict(
        tick_ref="T071",
        owner_overrides={},
        title_parts=[("宝应元年十月—十一月 · ", "#FFFFFF"), ("昭觉寺大捷，再克洛阳与河北归降", "#FFE04D")],
        subtitle="雍王李适统仆固怀恩、回纥登里可汗东征再复洛阳，薛嵩、张忠志等相继献相卫恒赵降唐",
        arrows=[
            ((111.19, 34.78), (112.44, 34.67), "TANG", 14.0, -0.14, 1.0, "昭觉寺大捷再复洛阳", (-55, -38)),
            ((112.44, 34.67), (115.67, 37.05), "TANG", 13.0, -0.16, 0.95, "联军北追 · 诸将献地", (96, -18)),
        ],
        banners=[
            (111.85, 35.18, "仆固怀恩", "TANG", 132),
            (109.85, 35.15, "回纥可汗", "UYGHUR", 128),
            (113.85, 36.65, "薛嵩", "FANZHEN", 124),
            (116.85, 37.90, "史朝义", "YAN_SHI", 126),
        ],
        sprites=[],
    ),
    "T076": dict(
        tick_ref="T076",
        owner_overrides={},
        title_parts=[("广德元年正月 · ", "#FFFFFF"), ("历时八载安史乱平，河朔藩镇成形", "#FFE04D")],
        subtitle="史朝义于温泉栅穷蹙自缢，八年战火终告平息；然河朔旧将拥兵自重，大唐自此步入藩镇时代",
        arrows=[
            ((116.13, 38.82), (118.85, 39.95), "TANG", 13.5, 0.14, 1.0, "追剿温泉栅 · 大乱平定", (155, -24)),
        ],
        banners=[
            (108.15, 34.95, "郭子仪", "TANG", 134),
            (117.18, 34.85, "李光弼", "TANG", 130),
            (114.95, 36.65, "田承嗣", "FANZHEN", 128),
            (114.70, 39.25, "李怀仙", "FANZHEN", 128),
        ],
        sprites=[],
    ),
}


def _to_px(lon, lat):
    return lonlat_to_px(lon, lat, MACRO_BOUNDS, W_PX, H_PX)


def _est_box(x, y, text, font_px, ha="center", va="center"):
    u = sum(0.56 if ord(c) < 128 else 1.02 for c in text)
    w = u * font_px + 12.0
    h = font_px * 1.25 + 8.0
    x0 = x - w * 0.5 if ha == "center" else (x if ha == "left" else x - w)
    y0 = y - h * 0.5 if va == "center" else (y if va == "bottom" else y - h)
    return (x0, y0, x0 + w, y0 + h)


def _overlaps(a, b, pad=4.0):
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])


def _draw_macro_river(ax, raw_pts, dark_px, core_px, is_canal=False, zorder=10):
    sm = smooth_polyline(raw_pts, steps=8)
    pts = [_to_px(lon, lat) for lon, lat in sm]
    xs, ys = zip(*pts)
    ls = (0, (9.0, 4.5)) if is_canal else "-"
    if not is_canal:
        ax.plot(xs, ys, color="#191614", lw=px_to_pt(dark_px), solid_capstyle="round", solid_joinstyle="round", zorder=zorder)
        ax.plot(xs, ys, color="#93BFFD", lw=px_to_pt(core_px), solid_capstyle="round", solid_joinstyle="round", zorder=zorder + 0.1)
    else:
        ax.plot(xs, ys, color="#191614", lw=px_to_pt(dark_px), ls=ls, solid_capstyle="butt", zorder=zorder)
        ax.plot(xs, ys, color="#83DCD0", lw=px_to_pt(core_px), ls=ls, solid_capstyle="butt", zorder=zorder + 0.1)


def _draw_bullseye_city(ax, px, py, owner, major=True):
    """参考图同款高辨识度 `◎` 黑白双圈靶心城池点。"""
    r_outer = 11.5 if major else 8.5
    r_mid = 8.2 if major else 6.0
    r_dot = 4.2 if major else 3.2
    core_col = FACTION_STYLE.get(owner, FACTION_STYLE["TANG"])["banner_bg"] if owner else "#24201E"
    ax.scatter([px], [py], s=(r_outer * 2.1) ** 2, fc="#FFFFFF", ec="#141110", lw=px_to_pt(2.6), zorder=20)
    ax.scatter([px], [py], s=(r_mid * 1.9) ** 2, fc="#141110", ec="none", zorder=20.2)
    ax.scatter([px], [py], s=(r_dot * 2.3) ** 2, fc="#FFFFFF", ec="none", zorder=20.4)
    ax.scatter([px], [py], s=(r_dot * 1.4) ** 2, fc=core_col, ec="none", zorder=20.6)


def _place_macro_banner(ax, lon, lat, name, faction, h_px=132, zorder=28):
    px, py = _to_px(lon, lat)
    # 防止北端帅旗（如史思明）超出顶部裁切线
    py = min(py, H_PX - 92.0 - h_px)
    py = max(py, 118.0)
    st = FACTION_STYLE.get(faction, FACTION_STYLE["TANG"])
    raw = make_war_banner(name, st["banner_bg"], st["banner_trim"], size=(100, 160))
    crop = _tight_rgba(raw, thresh=30)
    cw, ch = crop.size
    w_px = max(40, int(round(cw * (h_px / max(ch, 1)))))
    arr = np.asarray(crop.resize((w_px, h_px), Image.Resampling.LANCZOS), dtype=np.uint8)
    ax.add_artist(AnnotationBbox(OffsetImage(arr, zoom=1.0), (px, py), box_alignment=(0.5, 0.0), frameon=False, zorder=zorder))
    return (px - w_px * 0.5, py, px + w_px * 0.5, py + h_px)


def _place_macro_sprite(ax, lon, lat, faction, ut, flip=False, zorder=24):
    px, py = _to_px(lon, lat)
    st = FACTION_STYLE.get(faction, FACTION_STYLE["TANG"])
    raw = make_sprite(ut, st["unit_c"], st["unit_a"], flip=flip, size=(130, 104))
    crop = _tight_rgba(raw, thresh=60)
    cw, ch = crop.size
    th = 52
    tw = max(24, int(round(cw * (th / max(ch, 1)))))
    arr = np.asarray(crop.resize((tw, th), Image.Resampling.LANCZOS), dtype=np.uint8)
    ax.add_artist(AnnotationBbox(OffsetImage(arr, zoom=1.0), (px, py), frameon=False, zorder=zorder))


def _build_generic_macro_cfg(tick_id, ev):
    """为除 T020/T040 外的任意时间轴事件自动构建宏观渲染配置。"""
    yy, mm, dd = ev["date"].split("-")
    frm, to = city[ev["from_id"]], city[ev["to_id"]]
    pfk = ev.get("primary_faction") or "TANG"
    arrows = []
    if frm is not to:
        arrows.append(((frm["lon"], frm["lat"]), (to["lon"], to["lat"]), pfk, 12.5, 0.16, 1.0, None, (0, 0)))
    banners = []
    uids = [u for u in (ev.get("unit_ids") or "").split(";") if u]
    if uids:
        u0 = unit[uids[0]]
        cmd0 = u0["commanders"].split("、")[0]
        banners.append((to["lon"] - 0.35, to["lat"] + 0.25, cmd0, u0["faction"], 128))
    return dict(
        tick_ref=tick_id,
        owner_overrides={},
        title_parts=[(f"公元{int(yy)}年{int(mm)}月 · ", "#FFFFFF"), (f"{to['name_zh']}", "#FFE04D")],
        subtitle=ev["description"],
        arrows=arrows,
        banners=banners,
        sprites=[],
    )


def _draw_macro(
    ax, tick_id, ev, *,
    detail_background=True, smoothed_scores=None, control_override=None,
    arrow_progress=1.0, subtitle_override=None,
):
    cfg = MACRO_CUSTOM_FRAMES.get(tick_id) or _build_generic_macro_cfg(tick_id, ev)
    snap = snaps[cfg["tick_ref"]]
    ax.set_xlim(0, W_PX)
    ax.set_ylim(0, H_PX)
    ax.set_aspect("equal")
    ax.axis("off")

    ctrl_base = control_override if control_override is not None else snap["control"]
    ov_base = {} if control_override is not None else cfg.get("owner_overrides")

    # 1. 全图 3D 浮雕＋暖红/冷蓝无缝势力划分＋白晕战线＋古海岸线
    map_rgb, _ = compose_macro_map_rgb(
        RELIEF, D["cities"], ctrl_base, owner_overrides=ov_base,
        detail_background=detail_background, smoothed_scores=smoothed_scores,
    )
    ax.imshow(map_rgb, extent=[0, W_PX, 0, H_PX], origin="lower", interpolation="bilinear", zorder=0)

    # 2. 河流与运河（深黑边 + 冰蓝水体）
    for rname, (rpts, w_px, is_maj) in RIVER_LINES.items():
        if rname == "黄河":
            _draw_macro_river(ax, rpts, dark_px=8.8, core_px=4.8, zorder=10.5)
        else:
            _draw_macro_river(ax, rpts, dark_px=w_px + 2.4, core_px=w_px * 0.85, zorder=10.0)
    for cname, cpts in CANALS.items():
        _draw_macro_river(ax, cpts, dark_px=5.0, core_px=2.6, is_canal=True, zorder=10.2)

    # 已占位碰撞表（包含顶部大标题、底部字幕、帅旗与关隘图标，确保文本零重影）
    occupied = [(0.0, 955.0, 1180.0, H_PX), (0.0, 0.0, W_PX, 116.0)]

    # 先摆出雄关城楼、箭头、精修小人与帅旗，并记录占据区域
    ctrl = dict(ctrl_base)
    if ov_base:
        ctrl.update(ov_base)

    for slon, slat, sfk, sut, sflip, _ in cfg.get("sprites", []):
        _place_macro_sprite(ax, slon, slat, sfk, sut, flip=sflip, zorder=25)
    for blon, blat, bname, bfk, bh in cfg.get("banners", []):
        bbox_b = _place_macro_banner(ax, blon, blat, bname, bfk, h_px=bh, zorder=29)
        occupied.append(bbox_b)

    aprog = float(np.clip(arrow_progress, 0.0, 1.0))
    for (lon1, lat1), (lon2, lat2), afk, sw, rad, al, albl, lbl_off in cfg.get("arrows", []):
        p1 = _to_px(lon1, lat1)
        p2 = _to_px(lon2, lat2)
        col = FACTION_STYLE.get(afk, FACTION_STYLE["TANG"])["arrow"]
        curve = draw_double_stroked_arrow(
            ax, p1, p2, col, shaft_px=sw, head_w_px=sw * 2.4, head_l_px=sw * 2.6,
            rad=rad, alpha=al, zorder=27, progress=aprog,
        )
        if albl and aprog >= 0.55:
            lbl_al = min(1.0, (aprog - 0.55) / 0.30) * al
            mid = curve[len(curve) // 2]
            lx, ly = mid[0] + lbl_off[0], mid[1] + lbl_off[1]
            ax.text(
                lx, ly, albl,
                fontproperties=FONT_BOLD, fontsize=px_to_pt(27), color="#FFE97D", alpha=lbl_al,
                ha="center", va="center", zorder=32, path_effects=text_outline(4.0, "#12100E"),
            )
            occupied.append(_est_box(lx, ly, albl, 27.0))

    # 雄关要塞图标与标签
    for pid, (pk, ldx, ldy, lha, lva, dname) in MACRO_PASSES.items():
        c = city[pid]
        px, py = _to_px(c["lon"], c["lat"])
        owner = ctrl.get(pid, "TANG")
        st = FACTION_STYLE.get(owner, FACTION_STYLE["TANG"])
        raw = make_landmark_sprite(pk, st["banner_bg"], st["banner_trim"], size=(160, 128))
        crop = _tight_rgba(raw, thresh=40)
        cw, ch = crop.size
        tw = 66
        th = max(24, int(round(ch * (tw / max(cw, 1)))))
        arr = np.asarray(crop.resize((tw, th), Image.Resampling.LANCZOS), dtype=np.uint8)
        py_icon = py - 24.0 if pid == "TONGGUAN" else py - 8.0
        ax.add_artist(AnnotationBbox(OffsetImage(arr, zoom=1.0), (px, py_icon), box_alignment=(0.5, 0.0), frameon=False, zorder=23))
        occupied.append((px - tw * 0.5, py_icon, px + tw * 0.5, py_icon + th))
        ax.text(
            px + ldx, py + ldy, dname,
            fontproperties=FONT_BOLD, fontsize=px_to_pt(27), color="#FFE04D" if pid == "TONGGUAN" else "#FFFFFF",
            ha=lha, va=lva, zorder=24, path_effects=text_outline(3.8, "#12100E"),
        )
        occupied.append(_est_box(px + ldx, py + ldy, dname, 27.0, ha=lha, va=lva))

    # 3. 渤海「古海岸线」标识 + 大山脉字样 + 水系名
    gc_x, gc_y = _to_px(119.3, 38.2)
    ax.text(gc_x, gc_y, "古海岸线", fontproperties=FONT_BOLD, fontsize=px_to_pt(28), color="#FFFFFF",
            ha="center", va="center", zorder=18, path_effects=text_outline(3.6, "#102845"))
    sea_x, sea_y = _to_px(120.2, 39.2)
    ax.text(sea_x, sea_y, "渤  海", fontproperties=FONT_BOLD, fontsize=px_to_pt(32), color="#A7CEFC",
            ha="center", va="center", zorder=18, path_effects=text_outline(3.6, "#0B1E36"))

    for lon, lat, mtxt, rot in MOUNTAIN_DISPLAY_LABELS:
        mx, my = _to_px(lon, lat)
        box_m = _est_box(mx, my, mtxt.replace(" ", ""), 38.0)
        if any(_overlaps(box_m, ob, pad=2.0) for ob in occupied):
            continue
        ax.text(mx, my, mtxt, fontproperties=FONT_BOLD, fontsize=px_to_pt(38), color="#FFF7E4",
                ha="center", va="center", rotation=rot, zorder=19, path_effects=text_outline(4.6, "#161210"))
        occupied.append(box_m)

    # 4. 重点城池（◎ 靶心 + 自动避让防撞地名）
    for cid, (dx, dy, ha, va, is_maj) in MACRO_CITY_STYLE.items():
        c = city[cid]
        px, py = _to_px(c["lon"], c["lat"])
        top_lim = H_PX - 32 if cid == "FANYANG" else H_PX - 65
        if not (65 <= px <= W_PX - 65 and 126 <= py <= top_lim):
            continue
        owner = ctrl.get(cid)
        _draw_bullseye_city(ax, px, py, owner, major=is_maj)
        occupied.append((px - 14, py - 14, px + 14, py + 14))

    for cid, (dx, dy, ha, va, is_maj) in MACRO_CITY_STYLE.items():
        c = city[cid]
        px, py = _to_px(c["lon"], c["lat"])
        top_lim = H_PX - 32 if cid == "FANYANG" else H_PX - 65
        if not (65 <= px <= W_PX - 65 and 126 <= py <= top_lim):
            continue
        fs = 30.0 if is_maj else 25.0
        col = "#FFE97D" if cid in ("CHANGAN", "LUOYANG", "FANYANG", "TAIYUAN") else "#FFFFFF"
        cands = [(dx, dy, ha, va), (0, 22, "center", "bottom"), (0, -22, "center", "top"), (22, 0, "left", "center"), (-22, 0, "right", "center")]
        lbl_top = H_PX - 30.0 if cid == "FANYANG" else H_PX - 55.0
        placed = False
        for cdx, cdy, cha, cva in cands:
            box = _est_box(px + cdx, py + cdy, c["name_zh"], fs, ha=cha, va=cva)
            if box[1] < 118.0 or box[3] > lbl_top:
                continue
            if not any(_overlaps(box, ob, pad=4.0) for ob in occupied):
                ax.text(
                    px + cdx, py + cdy, c["name_zh"],
                    fontproperties=FONT_BOLD, fontsize=px_to_pt(fs), color=col,
                    ha=cha, va=cva, zorder=22, path_effects=text_outline(4.0, "#12100E"),
                )
                occupied.append(box)
                placed = True
                break
        if not placed and is_maj:
            # 重点名城即便紧凑也按首选偏移绘制（带描边保证可读）
            ax.text(
                px + dx, py + dy, c["name_zh"],
                fontproperties=FONT_BOLD, fontsize=px_to_pt(fs), color=col,
                ha=ha, va=va, zorder=22, path_effects=text_outline(4.0, "#12100E"),
            )

    # 水系名置最后，若与城池或帅旗碰车自动退让
    for lon, lat, rtxt, rot in RIVER_DISPLAY_LABELS:
        rx, ry = _to_px(lon, lat)
        box_r = _est_box(rx, ry, rtxt, 24.0)
        if any(_overlaps(box_r, ob, pad=4.0) for ob in occupied):
            continue
        ax.text(rx, ry, rtxt, fontproperties=FONT_BOLD, fontsize=px_to_pt(24), color="#E6F2FF",
                ha="center", va="center", rotation=rot, zorder=19, path_effects=text_outline(3.2, "#101824"))
        occupied.append(box_r)

    # 5. B站科普顶部大标题 + 底部大字幕
    draw_bilibili_hud(ax, cfg["title_parts"], cfg["subtitle"] if subtitle_override is None else subtitle_override)


def _save_fig_and_qa(fig, out_path):
    fig.savefig(out_path, dpi=100, facecolor="#123966")
    plt.close(fig)
    qa_path = QADIR / out_path.name
    Image.open(out_path).resize((960, 540), Image.Resampling.LANCZOS).save(qa_path)
    print(f"Rendered: {out_path} (+ {qa_path})")


def render(tick=None, force_macro=False, out_suffix="", detail_background=True):
    if tick is None:
        tick = "T020"
    ev = next(e for e in events if e["tick_id"] == tick)
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, frameon=False)
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])

    if (not force_macro) and ev["camera"] == "micro" and ev.get("battle_id") in SCENES:
        draw_tactical_map(ax, ev["battle_id"], detail_background=detail_background)
    else:
        _draw_macro(ax, tick, ev, detail_background=detail_background)

    out_path = OUTDIR / f"frame_{tick}{out_suffix}.png"
    _save_fig_and_qa(fig, out_path)


if __name__ == "__main__":
    args = sys.argv[1:]
    macro_only = "--macro" in args
    detail_bg = "--baseline" not in args
    ticks = [a for a in args if not a.startswith("--")] or ["T020", "T040"]
    for tk in ticks:
        ev = next(e for e in events if e["tick_id"] == tk)
        if macro_only:
            sfx = "_macro" if (ev["camera"] == "micro" and ev.get("battle_id") in SCENES) else ""
            render(tk, force_macro=True, out_suffix=sfx, detail_background=detail_bg)
        else:
            render(tk, force_macro=False, detail_background=detail_bg)
            if ev["camera"] == "micro" and ev.get("battle_id") in SCENES:
                render(tk, force_macro=True, out_suffix="_macro", detail_background=detail_bg)
