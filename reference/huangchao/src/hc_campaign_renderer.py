# -*- coding: utf-8 -*-
"""
src/hc_campaign_renderer.py
《唐末黄巢起义（874–884）》全屏 1920×1080 战役向兵棋主渲染引擎与 FFmpeg 封装器

画面体例严格对标《安史之乱》战役版本：
- 取消固定右侧人物立绘栏，回归全屏 1920×1080 3D 立体地形棋盘（无缝红蓝疆界、白光晕战线、
  ◎ 靶心城池、朱红重檐雄关、渡口标点、4x 超采样行军算子、双描边动态箭矢、B站科普大标题与底字幕条）；
- 在三大核心战役节点（B_GZ 广州、B_TG 潼关、B_WMD 王满渡）切换全屏 3D 微缩战术沙盘实时攻防；
- 仅在曲江赋菊（T01）、含元称帝（T12）、朱温叛降四帧转折（T13）、李克用鸦儿军入关四帧转折（T14_LK）及狼虎谷陨落（T16）关键历史节点穿插剧场画面；
- 全片 4,397 帧（146.573s @ 30fps）严格对齐 Enog.mp3 实测拍点与 Drop / Breakdown 音乐曲线。
"""
from __future__ import annotations

import bisect
import json
import math
import re
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from hc_tactical import (
    HuangChaoTacticalRenderer,
    PIL_BOLD_22,
    PIL_BOLD_28,
    PIL_BOLD_36,
    PIL_BOLD_48,
    _draw_bilibili_hud,
    _draw_double_arrow,
    _draw_outlined_text,
    _ease_out,
    _path_pos,
)
from hc_terrain import (
    CANALS,
    LAT0,
    LAT1,
    LON0,
    LON1,
    MOUNTAIN_DISPLAY_LABELS,
    RIVER_DISPLAY_LABELS,
    RIVER_LINES,
    build_relief_terrain,
    compose_macro_from_scores,
    compute_smoothed_faction_scores,
    fit_aspect_bounds,
    smooth_polyline,
)
from huangchao_sprites_ultra import get_huangchao_sprite
from landmarks import make_landmark_sprite, make_war_banner
from sprites import make_sprite
from tang_warlords_sprites_128 import CHARACTERS as WARLORD_META, get_warlord_sprite

ROOT = Path(__file__).resolve().parents[1]
DATA_JSON = ROOT / "data" / "huangchao_wargame.json"
BEAT_JSON = ROOT / "output" / "audio" / "enog_huangchao_beat_map.json"
MIX_WAV = ROOT / "output" / "audio" / "enog_master_mix.wav"
OUT = ROOT / "output"
RAW_MP4 = OUT / "huangchao_video.mp4"
FINAL_MP4 = OUT / "huangchao_enog_complete.mp4"

W_PX, H_PX = 1920, 1080
FPS = 30
TOTAL_FRAMES = 4397

PIL_BADGE = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 19)
PIL_POEM = ImageFont.truetype(r"C:\Windows\Fonts\STZHONGS.TTF", 42)
PIL_CITY = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 18)


def _ll_to_pil(lon: float, lat: float, bounds) -> Tuple[float, float]:
    x0, x1, y0, y1 = bounds
    return (lon - x0) / (x1 - x0) * W_PX, (y1 - lat) / (y1 - y0) * H_PX


def _draw_bullseye_city(d: ImageDraw.ImageDraw, x: float, y: float, fac: str, importance: bool = False) -> None:
    r = 10.5 if importance else 8.0
    col = (43, 91, 132, 255) if fac == "QI" else (204, 54, 48, 255)
    d.ellipse([x - r - 3, y - r - 3, x + r + 3, y + r + 3], fill=(246, 244, 238, 255), outline=(22, 18, 18, 255), width=2)
    d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    d.ellipse([x - r * 0.42, y - r * 0.42, x + r * 0.42, y + r * 0.42], fill=(248, 244, 232, 255))


class HuangChaoCampaignEngine:
    def __init__(self) -> None:
        self.payload = json.loads(DATA_JSON.read_text(encoding="utf-8"))
        self.cities = self.payload["cities"]
        self.routes = {r["route_id"]: r for r in self.payload["routes"]}
        self.bounds = fit_aspect_bounds(LON0 + 2.6, LON1 + 2.4, LAT0 - 1.4, LAT1 - 0.1, x_stretch=1.22)

        print("Building 1920x1080 3D relief terrain...", flush=True)
        self.relief = build_relief_terrain(self.bounds, W=W_PX, H=H_PX)
        self.tactical = HuangChaoTacticalRenderer()

        # 预建固定宏观地理叠层（河流/运河/海岸注记/山川名称），只画一次
        self.geo_overlay = self._build_static_geo_layer()

        # 地标建筑与战旗缓存
        self.landmarks = {
            ("capital", "TANG"): make_landmark_sprite("capital", "#C93326", "#F7D348", size=(102, 82)),
            ("capital", "QI"): make_landmark_sprite("capital", "#2B5B84", "#F6C226", size=(102, 82)),
            ("pass", "TANG"): make_landmark_sprite("pass", "#C93326", "#F7D348", size=(86, 68)),
            ("pass", "QI"): make_landmark_sprite("pass", "#2B5B84", "#F6C226", size=(86, 68)),
        }
        self.banners = {
            "黄巢": make_war_banner("黄巢", "#2B5B84", "#F6C226", size=(66, 108)),
            "王仙芝": make_war_banner("王仙芝", "#356B9C", "#F6C226", size=(62, 102)),
            "尚让": make_war_banner("尚让", "#2B5B84", "#F6C226", size=(60, 98)),
            "宋威": make_war_banner("宋威", "#C93326", "#F7D348", size=(60, 98)),
            "高骈": make_war_banner("高骈", "#C93326", "#F7D348", size=(62, 100)),
            "张承范": make_war_banner("张承范", "#C93326", "#F7D348", size=(60, 98)),
            "王铎": make_war_banner("王铎", "#C93326", "#F7D348", size=(62, 100)),
            "朱温": make_war_banner("朱温", "#C93326", "#F7D348", size=(64, 104)),
            "李克用": make_war_banner("李克用", "#242730", "#CBD5E1", size=(68, 110)),
        }
        palette_units = {
            "QI": ("#2B5B84", "#F6C226", {"cavalry": (76, 62), "infantry": (70, 58), "heavy_inf": (74, 60), "militia": (72, 60)}),
            "TANG": ("#C93326", "#F7D348", {"cavalry": (76, 62), "infantry": (70, 58), "heavy_inf": (74, 60), "militia": (72, 60)}),
            "SHATUO": ("#2A2D34", "#CBD5E1", {"cavalry": (80, 64), "infantry": (70, 58), "heavy_inf": (74, 60), "militia": (72, 60)}),
        }
        self.macro_units = {
            (fac, utype, flip): make_sprite(utype, c_main, c_acc, flip=flip, size=sz)
            for fac, (c_main, c_acc, sz_map) in palette_units.items()
            for utype, sz in sz_map.items()
            for flip in (False, True)
        }

        # 定义 18 幕势力控制权快照与宏观导演脚本（严格反映流动作战收复态，绝不保留虚假旧蓝区）
        tl = {e["event_id"]: e for e in self.payload["timeline"]}
        init_ctrl = {cid: c["init_faction"] for cid, c in self.cities.items()}

        def ctrl_at(eid: str) -> Dict[str, str]:
            return dict(tl[eid]["city_control"])

        t15_ctrl = ctrl_at("T15")

        self.act_specs: Dict[str, Dict] = {
            "T01": dict(ctrl_prev=init_ctrl, ctrl_cur=init_ctrl, day=0, route_id=None, focus="QUJIANG"),
            "T02": dict(
                ctrl_prev=init_ctrl, ctrl_cur=ctrl_at("T02"), day=207, route_id="R01_SHANDONG_TO_HUAI", focus="YUANQU",
                title=[("乾符二年五月 · ", "#FFFFFF"), ("黄巢冤句起兵，响应中原", "#FFE04D")],
                sub="关东旱蝗大饥，黄巢散家财于曹州冤句聚众数千起兵，与王仙芝会师痛击官军",
                arrow=((115.38, 35.15), (114.31, 34.80), "QI", -0.14, "冤句起兵转战中原"),
                banners=[("黄巢", 115.95, 35.75), ("王仙芝", 114.70, 35.65), ("宋威", 113.20, 34.95)],
                units=[
                    ("QI", "militia", True, (115.48, 35.15), (114.45, 34.92)),
                    ("QI", "infantry", True, (115.10, 35.30), (114.35, 35.05)),
                    ("TANG", "cavalry", False, (113.10, 34.70), (113.95, 34.78)),
                    ("TANG", "heavy_inf", False, (113.55, 34.25), (114.10, 34.55)),
                ],
            ),
            "T03": dict(
                ctrl_prev=ctrl_at("T02"), ctrl_cur=ctrl_at("T03"), day=766, route_id="R01_SHANDONG_TO_HUAI", focus="QIZHOU",
                title=[("乾符三年冬 · ", "#FFFFFF"), ("怒斥招安，蕲州分军，朝廷收复曹濮", "#FFE04D")],
                sub="王仙芝动摇欲受官职，黄巢怒斥不从并率部转战江淮，原曹州冤句一带随即被唐军收复",
                arrow=((114.31, 34.80), (115.43, 30.23), "QI", 0.16, "分军南下蕲州黄梅"),
                banners=[("黄巢", 115.95, 31.15), ("王仙芝", 114.40, 30.65), ("宋威", 115.20, 34.85)],
                units=[
                    ("QI", "infantry", False, (114.35, 34.40), (115.40, 30.55)),
                    ("QI", "cavalry", False, (114.55, 33.90), (115.55, 30.25)),
                    ("TANG", "cavalry", False, (114.00, 35.20), (115.25, 35.10)),
                    ("TANG", "heavy_inf", True, (116.40, 30.80), (115.80, 30.40)),
                ],
            ),
            "T04": dict(
                ctrl_prev=ctrl_at("T03"), ctrl_cur=ctrl_at("T04"), day=1191, route_id="R01_SHANDONG_TO_HUAI", focus="HUANGMEI",
                title=[("乾符五年正月 · ", "#FFFFFF"), ("接掌全军，自号“冲天大将军”", "#FFE04D")],
                sub="王仙芝败亡黄梅后尚让率余部归附，黄巢甩开中原追兵渡江准备南下大迂回",
                arrow=((115.43, 30.23), (118.47, 31.66), "QI", -0.15, "东出皖南渡长江"),
                banners=[("黄巢", 116.25, 30.65), ("尚让", 115.05, 29.75), ("高骈", 119.50, 32.95)],
                units=[
                    ("QI", "cavalry", False, (115.93, 30.08), (118.25, 31.50)),
                    ("QI", "heavy_inf", False, (115.55, 30.35), (117.75, 31.20)),
                    ("TANG", "cavalry", True, (119.45, 32.60), (118.65, 31.95)),
                    ("TANG", "infantry", False, (114.40, 33.50), (115.45, 31.40)),
                ],
            ),
            "T05": dict(
                ctrl_prev=ctrl_at("T04"), ctrl_cur=ctrl_at("T05"), day=1369, route_id="R02_DETOUR_TO_LINGNAN", focus="XIANXIA_PASS",
                title=[("乾符五年秋 · ", "#FFFFFF"), ("避实击虚！刊山开道七百里入闽", "#FFE04D")],
                sub="高骈严防淮南而疏于东南，齐军弃守江北旧地、劈山穿行仙霞岭古道直插福建腹地",
                arrow=((118.47, 31.66), (118.52, 28.36), "QI", -0.18, "刊山开道入闽"),
                banners=[("黄巢", 117.75, 28.65), ("高骈", 119.50, 32.95)],
                units=[
                    ("QI", "infantry", False, (118.76, 30.95), (118.42, 27.65)),
                    ("QI", "militia", False, (118.30, 30.30), (118.10, 27.35)),
                    ("TANG", "heavy_inf", False, (118.90, 32.40), (118.55, 31.20)),
                    ("TANG", "infantry", True, (119.20, 26.80), (118.75, 27.45)),
                ],
            ),
            "T06": dict(
                ctrl_prev=ctrl_at("T05"), ctrl_cur=ctrl_at("T06"), day=1486, route_id="R02_DETOUR_TO_LINGNAN", focus="FUZHOU",
                title=[("乾符五年十二月 · ", "#FFFFFF"), ("兵锋抵海破福州，席卷粤东", "#FFE04D")],
                sub="连克建州、福州后沿东南海疆长驱南下直逼岭南广州，江浙后方由唐廷收复",
                arrow=((118.52, 28.36), (113.95, 23.28), "QI", -0.20, "横扫闽粤直扑广州"),
                banners=[("黄巢", 118.60, 25.45), ("高骈", 119.50, 32.95)],
                units=[
                    ("QI", "cavalry", True, (119.30, 26.08), (114.60, 23.45)),
                    ("QI", "infantry", True, (118.60, 25.40), (114.15, 23.15)),
                    ("TANG", "cavalry", True, (114.05, 23.35), (113.50, 23.15)),
                    ("TANG", "heavy_inf", False, (118.20, 29.80), (118.60, 28.10)),
                ],
            ),
            "B_GZ": dict(ctrl_prev=ctrl_at("T06"), ctrl_cur=ctrl_at("T07"), day=1772, tactical="B_GZ"),
            "T08": dict(
                ctrl_prev=ctrl_at("T07"), ctrl_cur=ctrl_at("T08"), day=1805, route_id="R03_NORTHERN_EXPEDITION", focus="LINGQU_PASS",
                title=[("乾符六年十月 · ", "#FFFFFF"), ("灵渠编筏北伐，一日破潭州", "#FFE04D")],
                sub="岭南疫起，齐军弃广东全军经桂州灵渠编大筏顺湘江北上，一日破潭州重创唐军",
                arrow=((110.67, 25.61), (112.98, 28.95), "QI", -0.12, "灵渠湘江水陆北伐"),
                banners=[("黄巢", 111.75, 27.35), ("尚让", 113.55, 29.85), ("高骈", 116.80, 30.80)],
                units=[
                    ("QI", "infantry", False, (110.67, 25.61), (112.90, 29.35)),
                    ("QI", "cavalry", False, (111.35, 26.25), (113.20, 29.80)),
                    ("TANG", "heavy_inf", True, (113.80, 29.40), (112.95, 28.55)),
                    ("TANG", "cavalry", False, (113.30, 23.60), (112.80, 24.40)),
                ],
            ),
            "T09": dict(
                ctrl_prev=ctrl_at("T08"), ctrl_cur=ctrl_at("T09"), day=2069, route_id="R03_NORTHERN_EXPEDITION", focus="SANJIANGKOU",
                title=[("广明元年七月 · ", "#FFFFFF"), ("采石矶渡江、三江口跨淮六十万", "#FFE04D")],
                sub="高骈拥兵扬州坐视，六十万齐军复跨长江、淮河直扑东都，湘鄂故地随后重归唐廷",
                arrow=((117.18, 32.95), (113.40, 34.45), "QI", 0.14, "六十万大军北指两京"),
                banners=[("黄巢", 116.25, 33.45), ("高骈", 119.85, 32.55)],
                units=[
                    ("QI", "cavalry", True, (117.18, 32.95), (113.80, 34.35)),
                    ("QI", "heavy_inf", True, (117.45, 32.10), (114.20, 33.85)),
                    ("TANG", "heavy_inf", True, (119.40, 32.45), (118.85, 32.20)),
                    ("TANG", "cavalry", False, (112.80, 34.40), (113.60, 34.25)),
                ],
            ),
            "T10": dict(
                ctrl_prev=ctrl_at("T09"), ctrl_cur=ctrl_at("T10"), day=2194, route_id="R04_CAPTURE_TWO_CAPITALS", focus="LUOYANG",
                title=[("广明元年十一月 · ", "#FFFFFF"), ("东都洛阳迎降，直逼潼关", "#FFE04D")],
                sub="洛阳留守迎降，齐军整肃直抵关中东大门潼关；唐将张承范急赴潼关抢修防线",
                arrow=((114.31, 34.80), (111.05, 34.62), "QI", -0.06, "东都迎降，西向潼关"),
                banners=[("黄巢", 112.85, 35.25), ("尚让", 111.20, 34.25), ("张承范", 109.90, 34.20)],
                units=[
                    ("QI", "cavalry", True, (112.45, 34.67), (110.85, 34.58)),
                    ("QI", "heavy_inf", True, (113.20, 34.45), (111.35, 34.50)),
                    ("TANG", "heavy_inf", False, (109.20, 34.30), (110.22, 34.54)),
                    ("TANG", "cavalry", False, (109.85, 34.70), (110.25, 34.58)),
                ],
            ),
            "T11_PRE": dict(
                ctrl_prev=ctrl_at("T10"), ctrl_cur=ctrl_at("T10"), day=2210, route_id="R04_CAPTURE_TWO_CAPITALS", focus="TONGGUAN",
                title=[("广明元年十二月 · ", "#FFFFFF"), ("兵临天险潼关，暗遣奇兵绕禁谷", "#FFE04D")],
                sub="张承范死守天险，齐军正面列阵对峙，密遣林言轻骑潜行绕道南侧禁谷奇袭合围",
                arrow=((111.10, 34.55), (110.30, 34.54), "QI", 0.24, "禁谷奇袭绕后合围"),
                banners=[("尚让", 111.30, 35.00), ("张承范", 109.75, 34.25)],
                units=[
                    ("QI", "cavalry", True, (111.00, 34.35), (110.42, 34.48)),
                    ("QI", "infantry", True, (111.25, 34.70), (110.55, 34.62)),
                    ("TANG", "heavy_inf", False, (109.65, 34.35), (110.22, 34.52)),
                    ("TANG", "cavalry", False, (109.30, 34.28), (110.05, 34.45)),
                ],
            ),
            "B_TG": dict(ctrl_prev=ctrl_at("T10"), ctrl_cur=ctrl_at("T12"), day=2210, tactical="B_TG"),
            "T12": dict(ctrl_prev=ctrl_at("T12"), ctrl_cur=ctrl_at("T12"), day=2254),
            "T13": dict(
                ctrl_prev=ctrl_at("T12"), ctrl_cur=ctrl_at("T13"), day=2861, route_id="R04_CAPTURE_TWO_CAPITALS", focus="TONGZHOU",
                title=[("中和二年秋 · ", "#FFFFFF"), ("朱温同州叛降，两京围城急转直下", "#FFE04D")],
                sub="诸道勤王兵合围，洛阳与淮右故地尽失；守将朱温据同州叛齐降唐，长安孤悬绝境",
                arrow=((109.94, 34.80), (109.05, 34.35), "TANG", -0.15, "朱温叛降断绝粮道"),
                banners=[("朱温", 110.25, 35.40), ("王铎", 111.80, 34.75), ("黄巢", 108.45, 34.10)],
                units=[
                    ("TANG", "cavalry", True, (109.94, 34.80), (109.25, 34.45)),
                    ("TANG", "heavy_inf", True, (111.60, 34.65), (110.35, 34.55)),
                    ("QI", "heavy_inf", False, (108.95, 34.27), (109.35, 34.38)),
                ],
            ),
            "T14_LK": dict(
                ctrl_prev=ctrl_at("T13"), ctrl_cur=ctrl_at("T14"), day=3012, route_id="R04_CAPTURE_TWO_CAPITALS", focus="CHANGAN",
                title=[("中和三年春 · ", "#FFFFFF"), ("李克用沙陀鸦儿军入关破京师", "#FFE04D")],
                sub="十八路诸侯会师关中，李克用亲率黑衣沙陀鸦儿军破梁田坡、收复长安，黄巢东走中原",
                arrow=((112.90, 38.80), (109.10, 34.45), "TANG", -0.18, "沙陀鸦儿军南下收复京畿"),
                banners=[("李克用", 111.35, 36.75), ("王铎", 109.85, 35.15), ("黄巢", 108.55, 34.10)],
                units=[
                    ("SHATUO", "cavalry", True, (112.20, 37.80), (109.25, 34.45)),
                    ("SHATUO", "heavy_inf", False, (111.40, 36.20), (109.65, 34.65)),
                    ("TANG", "cavalry", True, (110.20, 34.70), (109.35, 34.35)),
                    ("QI", "cavalry", False, (109.10, 34.25), (112.40, 34.20)),
                ],
            ),
            "B_WMD": dict(ctrl_prev=ctrl_at("T14"), ctrl_cur=ctrl_at("T14"), day=3068, tactical="B_WMD"),
            "T15_REV": dict(
                ctrl_prev=ctrl_at("T14"), ctrl_cur=t15_ctrl, day=3472, route_id="R05_RETREAT_TO_LANGHUGU", focus="LANGHUGU",
                title=[("中和四年 · ", "#FFFFFF"), ("群镇反攻尽复中原，残部孤悬泰山", "#FFE04D")],
                sub="王满渡大败后朱温与李克用东西合围收复陈蔡汴梁，黄巢仅携千余残骑孤军东走泰山",
                arrow=((114.03, 34.86), (117.52, 36.15), "TANG", -0.14, "沙陀汴军两路合围东追"),
                banners=[("李克用", 113.55, 35.55), ("朱温", 114.35, 34.25), ("黄巢", 117.85, 36.75)],
                units=[
                    ("SHATUO", "cavalry", False, (113.85, 35.05), (116.85, 36.05)),
                    ("TANG", "cavalry", False, (114.35, 34.65), (116.60, 35.75)),
                    ("QI", "cavalry", False, (115.60, 34.90), (117.52, 36.15)),
                ],
            ),
            "T16": dict(ctrl_prev=t15_ctrl, ctrl_cur=ctrl_at("T16"), day=3528),
        }

        # 预计算 17 幕三点连续势力场（起点 s0 -> 前锋推进态 s_mid -> 终点 s1），确保战线与箭头/算子同步扩张不滞后
        print("Precomputing 3-stage frontline fields (no lag behind vanguard)...", flush=True)
        cache_scores = {}
        self.act_scores = {}
        for aid, sp in self.act_specs.items():
            k0 = (tuple(sorted(sp["ctrl_prev"].items())), None)
            k1 = (tuple(sorted(sp["ctrl_cur"].items())), None)
            if k0 not in cache_scores:
                cache_scores[k0] = compute_smoothed_faction_scores(self.relief, self.cities, sp["ctrl_prev"])
            if k1 not in cache_scores:
                cache_scores[k1] = compute_smoothed_faction_scores(self.relief, self.cities, sp["ctrl_cur"])
            arr = sp.get("arrow")
            if arr:
                (lo1, la1), (lo2, la2), afac, _, _ = arr
                mid_lon = 0.45 * lo1 + 0.55 * lo2
                mid_lat = 0.45 * la1 + 0.55 * la2
                extra = [
                    (mid_lon, mid_lat, afac, 1.38),
                    (0.25 * lo1 + 0.75 * lo2, 0.25 * la1 + 0.75 * la2, afac, 1.32),
                ]
                mid_ctrl = dict(sp["ctrl_prev"])
                for k_c, v_c in sp["ctrl_cur"].items():
                    if v_c == afac:
                        mid_ctrl[k_c] = v_c
                s_mid = compute_smoothed_faction_scores(self.relief, self.cities, mid_ctrl, extra_anchors=extra)
            else:
                s_mid = cache_scores[k1]
            self.act_scores[aid] = (cache_scores[k0], s_mid, cache_scores[k1])

    def _build_static_geo_layer(self) -> Image.Image:
        layer = Image.new("RGBA", (W_PX, H_PX), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer, "RGBA")
        for rname, (pts, w_px, _) in RIVER_LINES.items():
            spts = [_ll_to_pil(lo, la, self.bounds) for lo, la in smooth_polyline(pts, 6)]
            d.line(spts, fill=(44, 62, 74, 210), width=int(w_px * 2.1 + 3), joint="curve")
            d.line(spts, fill=(92, 160, 206, 240), width=int(w_px * 1.9), joint="curve")
        for cname, cpts in CANALS.items():
            spts = [_ll_to_pil(lo, la, self.bounds) for lo, la in smooth_polyline(cpts, 4)]
            d.line(spts, fill=(68, 128, 168, 180), width=3, joint="curve")
        for lon, lat, lbl, _ in RIVER_DISPLAY_LABELS:
            x, y = _ll_to_pil(lon, lat, self.bounds)
            _draw_outlined_text(d, (x, y), lbl, PIL_BADGE, (186, 228, 252, 240), sw=3)
        for lon, lat, lbl, _ in MOUNTAIN_DISPLAY_LABELS:
            x, y = _ll_to_pil(lon, lat, self.bounds)
            _draw_outlined_text(d, (x, y), lbl, PIL_CITY, (92, 72, 54, 205), sw=2)
        return layer

    def _paste(self, canvas: Image.Image, sp: Image.Image, cx: float, cy: float) -> None:
        w, h = sp.size
        canvas.alpha_composite(sp, (int(cx - w * 0.5), int(cy - h * 0.5)))

    def _draw_macro(self, aid: str, u: float, sub_step: int) -> Image.Image:
        sp = self.act_specs[aid]
        s0, s_mid, s1 = self.act_scores[aid]
        # 疆界随行军 96 档超细腻过渡，先导压缩在 u/0.72 内完成，确保先锋抵达即刻同步翻色且无顿挫
        t_lead = min(1.0, max(0.0, u / 0.72))
        q_step = int(round(t_lead * 96))
        bg_key = (aid, q_step)
        if not hasattr(self, "_macro_bg_cache"):
            self._macro_bg_cache = {}
        bg = self._macro_bg_cache.get(bg_key)
        if bg is None:
            tq = q_step / 96.0
            if tq <= 0.5:
                a = _ease_out(tq / 0.5)
                diff = s0 * (1.0 - a) + s_mid * a
            else:
                a = _ease_out((tq - 0.5) / 0.5)
                diff = s_mid * (1.0 - a) + s1 * a
            rgb = compose_macro_from_scores(self.relief, diff)
            bg = Image.fromarray(np.flipud(rgb), mode="RGB").convert("RGBA")
            bg.alpha_composite(self.geo_overlay)
            # 只缓存当前幕背景防止内存膨胀
            if len(self._macro_bg_cache) > 110:
                self._macro_bg_cache.clear()
            self._macro_bg_cache[bg_key] = bg

        im = bg.copy()
        d = ImageDraw.Draw(im, "RGBA")

        # 历史已走大迂回轨迹留痕
        r_order = ["R01_SHANDONG_TO_HUAI", "R02_DETOUR_TO_LINGNAN", "R03_NORTHERN_EXPEDITION", "R04_CAPTURE_TWO_CAPITALS", "R05_RETREAT_TO_LANGHUGU"]
        cur_rid = sp.get("route_id")
        r_idx = r_order.index(cur_rid) if cur_rid in r_order else -1
        for i, rid in enumerate(r_order):
            if r_idx >= 0 and i < r_idx:
                pts = [_ll_to_pil(lo, la, self.bounds) for la, lo in self.routes[rid]["waypoints"]]
                d.line(pts, fill=(28, 22, 18, 120), width=5, joint="curve")
                d.line(pts, fill=(238, 186, 68, 165), width=2, joint="curve")

        # 31 座城池 ◎ + 关隘城楼 + 都城皇阙 + 渡口（城池归属与先锋箭矢同步在 u=0.36 切换）
        cur_ctrl = sp["ctrl_cur"] if u >= 0.36 else sp["ctrl_prev"]
        key_show = {"CHANGAN", "LUOYANG", "YUANQU", "QIZHOU", "HUANGMEI", "CAISHI_FERRY", "FUZHOU", "GUANGZHOU", "TANZHOU", "SANJIANGKOU", "YANGZHOU", "TONGZHOU", "WANGMANDU", "LANGHUGU"}
        if sp.get("focus"):
            key_show.add(sp["focus"])

        for cid, c in self.cities.items():
            x, y = _ll_to_pil(c["lon"], c["lat"], self.bounds)
            fac = cur_ctrl[cid]
            kind = c["kind"]
            if cid == sp.get("focus"):
                pulse = 18 + int(4 * math.sin(u * math.pi * 6))
                d.ellipse([x - pulse, y - pulse, x + pulse, y + pulse], outline=(255, 224, 96, 235), width=3)
            if kind == "capital":
                self._paste(im, self.landmarks[("capital", "QI" if fac == "QI" else "TANG")], x, y - 16)
            elif kind == "pass":
                self._paste(im, self.landmarks[("pass", "QI" if fac == "QI" else "TANG")], x, y - 12)
            elif kind == "ferry":
                d.ellipse([x - 8, y - 8, x + 8, y + 8], fill=(92, 194, 236, 255), outline=(22, 26, 34, 255), width=2)
            else:
                _draw_bullseye_city(d, x, y, fac, importance=(cid in key_show))

            if cid in key_show or kind in ("capital", "pass"):
                _draw_outlined_text(d, (x + 15, y - 2), c["name"], PIL_CITY, (255, 236, 136, 255) if cid == sp.get("focus") else (250, 246, 236, 255), anchor="lm", sw=3)

        # 双描边动态进攻箭头
        arr = sp.get("arrow")
        arr_lbl_info = None
        if arr:
            (lon1, lat1), (lon2, lat2), afac, rad, lbl = arr
            p1 = _ll_to_pil(lon1, lat1, self.bounds)
            p2 = _ll_to_pil(lon2, lat2, self.bounds)
            col = "#2B5B84" if afac == "QI" else "#D63227"
            a_prog = _ease_out(min(1.0, u / 0.82))
            _draw_double_arrow(d, p1, p2, rad, col, a_prog, sw=12)
            if lbl and u >= 0.42:
                mx = 0.5 * (p1[0] + p2[0])
                my = max(p1[1], p2[1]) + 56
                if my > H_PX - 175:
                    my = min(p1[1], p2[1]) - 56
                arr_lbl_info = (max(240.0, min(W_PX - 240.0, mx)), max(125.0, my), lbl)

        # 行军小人与主将竖幅帅旗（敌我双方阵列均有足底阴影与拍点行军起伏）
        for u_idx, (ufac, utype, uflip, ll0, ll1) in enumerate(sp.get("units", [])):
            p0 = _ll_to_pil(ll0[0], ll0[1], self.bounds)
            p1 = _ll_to_pil(ll1[0], ll1[1], self.bounds)
            px, py = _path_pos([(0.0, p0[0], p0[1]), (1.0, p1[0], p1[1])], _ease_out(min(1.0, u / 0.88)))
            py_bob = py - (5 if ((sub_step + u_idx) % 2 == 1) else 0)
            d.ellipse([px - 22, py + 12, px + 22, py + 25], fill=(12, 14, 18, 115))
            self._paste(im, self.macro_units[(ufac, utype, uflip)], px, py_bob)
        for bname, blon, blat in sp.get("banners", []):
            bx, by = _ll_to_pil(blon, blat, self.bounds)
            if bname in self.banners:
                self._paste(im, self.banners[bname], bx, by)

        if arr_lbl_info is not None:
            lx, ly, lbl = arr_lbl_info
            tb = d.textbbox((0, 0), lbl, font=PIL_BOLD_28)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
            d.rounded_rectangle([lx - tw * 0.5 - 16, ly - th * 0.5 - 8, lx + tw * 0.5 + 16, ly + th * 0.5 + 10], radius=8, fill=(14, 18, 28, 185), outline=(245, 200, 80, 210), width=2)
            _draw_outlined_text(d, (lx, ly), lbl, PIL_BOLD_28, (255, 234, 128, 255), anchor="mm", sw=3)

        # 紧凑图例角标（顺便自然收纳左下角非核心区域）
        day_cur = sp["day"]
        d.rounded_rectangle([28, H_PX - 134, 494, H_PX - 80], radius=10, fill=(14, 16, 22, 192), outline=(180, 146, 68, 210), width=2)
        d.rectangle([44, H_PX - 117, 66, H_PX - 97], fill=(43, 91, 132, 240), outline=(246, 194, 38, 255), width=2)
        d.text((76, H_PX - 107), "黄巢大齐", font=PIL_BADGE, fill=(242, 244, 248, 255), anchor="lm")
        d.rectangle([178, H_PX - 117, 200, H_PX - 97], fill=(204, 54, 48, 240), outline=(248, 244, 232, 255), width=2)
        d.text((210, H_PX - 107), "大唐/藩镇", font=PIL_BADGE, fill=(242, 244, 248, 255), anchor="lm")
        d.text((318, H_PX - 107), f"Day {day_cur}/3528", font=PIL_BADGE, fill=(252, 216, 98, 255), anchor="lm")

        _draw_bilibili_hud(im, sp["title"], sp["sub"])
        return im.convert("RGB")

    def _draw_cutscene(self, aid: str, u: float, sub_step: int) -> Image.Image:
        """五大关键节点全屏剧场穿插（绝不常驻全片）。"""
        s0, s_mid, s1 = self.act_scores[aid]
        # 转折剧场底图亦同步随推进插值，避免疆域僵死
        if aid in ("T13", "T14_LK"):
            tq = min(1.0, u / 0.85)
            diff = (s0 * (1.0 - tq * 2.0) + s_mid * (tq * 2.0)) if tq <= 0.5 else (s_mid * (1.0 - (tq - 0.5) * 2.0) + s1 * ((tq - 0.5) * 2.0))
        else:
            diff = s1
        rgb = compose_macro_from_scores(self.relief, diff)
        bg = Image.fromarray(np.flipud(rgb), mode="RGB").convert("RGBA")
        bg.alpha_composite(self.geo_overlay)
        # 使用 alpha_composite 保留底图疆域暗影质感（避免 Draw.rectangle 覆写成纯黑）
        veil_a = 148 if aid == "T14_LK" else 172
        veil = Image.new("RGBA", (W_PX, H_PX), (12, 14, 24, veil_a))
        bg = Image.alpha_composite(bg, veil)
        d = ImageDraw.Draw(bg, "RGBA")

        if aid == "T01":
            f_idx = min(3, int(u * 4))
            sp = get_huangchao_sprite("S1_SCHOLAR", frame=f_idx, scale=1).resize((420, 420), resample=Image.Resampling.NEAREST)
            d.ellipse([W_PX // 2 - 220, 625, W_PX // 2 + 220, 685], fill=(10, 11, 16, 200), outline=(228, 178, 68, 180), width=3)
            self._paste(bg, sp, W_PX // 2, 435)
            _draw_outlined_text(d, (W_PX // 2, 745), "「 他年我若为青帝，报与桃花一处开 」", PIL_POEM, (255, 224, 118, 255), sw=4)
            _draw_bilibili_hud(
                bg,
                [("乾符元年冬 · ", "#FFFFFF"), ("长安曲江，黄巢落第赋菊", "#FFE04D")],
                "屡试不第的曹州士子黄巢掷笔碎榜，埋下十年后倾覆大唐帝国的烈火",
            )
            return bg.convert("RGB")

        if aid == "T12":
            palace = make_landmark_sprite("capital", "#2B5B84", "#F6C226", size=(340, 265))
            self._paste(bg, palace, W_PX // 2, 285)
            f_idx = min(2, int(u * 3))
            sp = get_huangchao_sprite("S4_EMPEROR", frame=f_idx, scale=1).resize((384, 384), resample=Image.Resampling.NEAREST)
            d.ellipse([W_PX // 2 - 200, 665, W_PX // 2 + 200, 725], fill=(16, 12, 10, 210), outline=(246, 194, 38, 220), width=3)
            self._paste(bg, sp, W_PX // 2, 500)
            _draw_outlined_text(d, (W_PX // 2, 790), "建国号「大齐」  ·  改元金统  ·  全盛版图跨关中荆湖岭南", PIL_BOLD_36, (255, 224, 118, 255), sw=4)
            _draw_bilibili_hud(
                bg,
                [("金统元年正月 · ", "#FFFFFF"), ("含元殿大齐称帝", "#FFE04D")],
                "昔日曲江落第举子金冕龙袍登含元殿，大齐国号立于长安皇城之巅",
            )
            return bg.convert("RGB")

        if aid == "T13":
            # 前 26% 展示全屏同州翻红断粮道，后 74% 切入朱温四帧完整叛降演进双雄对峙短镜头
            if u < 0.26:
                return self._draw_macro("T13", u / 0.26, sub_step)
            pu = (u - 0.26) / 0.74
            zw_idx = min(3, int(pu * 4))
            hc_idx = 1 if pu < 0.45 else 3
            hc = get_huangchao_sprite("S4_EMPEROR", frame=hc_idx, scale=1).resize((352, 352), resample=Image.Resampling.NEAREST)
            zw = get_warlord_sprite("ZHU_WEN", frame=zw_idx, scale=1).transpose(Image.Transpose.FLIP_LEFT_RIGHT).resize((352, 352), resample=Image.Resampling.NEAREST)
            d.ellipse([W_PX // 2 - 500, 625, W_PX // 2 - 160, 675], fill=(10, 12, 18, 195), outline=(72, 142, 204, 190), width=2)
            d.ellipse([W_PX // 2 + 160, 625, W_PX // 2 + 500, 675], fill=(18, 10, 12, 195), outline=(228, 72, 64, 210), width=3)
            self._paste(bg, hc, W_PX // 2 - 330, 470)
            self._paste(bg, zw, W_PX // 2 + 330, 470)
            # 中央裂痕与状态徽章
            d.line([(W_PX // 2, 310), (W_PX // 2 - 18, 450), (W_PX // 2 + 16, 520), (W_PX // 2, 640)], fill=(238, 72, 64, 220), width=5)
            zw_pose = WARLORD_META["ZHU_WEN"]["frames"][zw_idx]
            _draw_outlined_text(d, (W_PX // 2, 460), "同州倒戈", PIL_BOLD_48, (238, 72, 64, 255), sw=5)
            _draw_outlined_text(d, (W_PX // 2 - 330, 710), "大齐皇帝 · 黄巢（长安孤悬）", PIL_BOLD_28, (252, 214, 96, 255), sw=4)
            _draw_outlined_text(d, (W_PX // 2 + 330, 710), f"朱温 · {zw_pose}", PIL_BOLD_28, (248, 128, 118, 255), sw=4)
            _draw_outlined_text(d, (W_PX // 2, 785), "两京故地陆续收复  ·  同州粮道断绝  ·  五代乱局萌芽", PIL_BOLD_22, (232, 224, 212, 240), sw=3)
            _draw_bilibili_hud(
                bg,
                [("中和二年秋 · ", "#FFFFFF"), ("大将朱温同州叛降，长安陷入合围", "#FFE04D")],
                "朱温据同州拔剑背齐、献印降唐，关东归属重返大唐而长安已成绝境孤城",
            )
            return bg.convert("RGB")

        if aid == "T14_LK":
            # 沙陀鸦儿军四帧完整转折序列 + 底层关中沙陀玄甲骑兵突进 & 李克用/黄巢对峙
            lk_idx = min(3, int(u * 4))
            # 底层行军箭头与沙陀黑甲骑兵顺着地图冲入关中
            p1 = _ll_to_pil(112.90, 38.80, self.bounds)
            p2 = _ll_to_pil(109.10, 34.45, self.bounds)
            _draw_double_arrow(d, p1, p2, -0.18, "#2A2D34", _ease_out(min(1.0, u / 0.85)), sw=11)
            for k_u in range(3):
                t_c = max(0.0, min(1.0, u * 1.15 - k_u * 0.12))
                cx_u, cy_u = _path_pos([(0.0, p1[0], p1[1]), (1.0, p2[0], p2[1])], _ease_out(t_c))
                self._paste(bg, self.macro_units[("SHATUO", "cavalry", True)], cx_u + k_u * 26, cy_u - k_u * 14 - (4 if (sub_step + k_u) % 2 else 0))
            self._paste(bg, self.banners["李克用"], p2[0] + 68, p2[1] - 42)

            # 前景双雄四帧动态演绎（李克用独眼挽弓→鸦军突袭 vs 黄巢焚宫撤出长安）
            lk = get_warlord_sprite("LI_KEYONG", frame=lk_idx, scale=1).resize((368, 368), resample=Image.Resampling.NEAREST)
            hc = get_huangchao_sprite("S4_EMPEROR", frame=2 if u < 0.5 else 3, scale=1).transpose(Image.Transpose.FLIP_LEFT_RIGHT).resize((332, 332), resample=Image.Resampling.NEAREST)
            d.ellipse([W_PX // 2 - 510, 622, W_PX // 2 - 150, 676], fill=(14, 16, 24, 210), outline=(203, 213, 225, 220), width=3)
            d.ellipse([W_PX // 2 + 165, 622, W_PX // 2 + 495, 676], fill=(12, 16, 24, 195), outline=(72, 142, 204, 190), width=2)
            self._paste(bg, lk, W_PX // 2 - 330, 465)
            self._paste(bg, hc, W_PX // 2 + 330, 480)
            lk_pose = WARLORD_META["LI_KEYONG"]["frames"][lk_idx]
            _draw_outlined_text(d, (W_PX // 2, 460), "玄甲克京", PIL_BOLD_48, (226, 232, 240, 255), sw=5)
            _draw_outlined_text(d, (W_PX // 2 - 330, 712), f"李克用 · {lk_pose}", PIL_BOLD_28, (226, 234, 248, 255), sw=4)
            _draw_outlined_text(d, (W_PX // 2 + 330, 712), "黄巢 · 放弃长安东走中原", PIL_BOLD_28, (252, 214, 96, 255), sw=4)
            _draw_outlined_text(d, (W_PX // 2, 785), "梁田坡大捷收复长安  ·  关中全境重归大唐  ·  决战王满渡", PIL_BOLD_22, (232, 228, 216, 245), sw=3)
            _draw_bilibili_hud(
                bg,
                [("中和三年春 · ", "#FFFFFF"), ("李克用率沙陀鸦儿军入关复长安", "#FFE04D")],
                "黑衣玄甲的李克用沙陀鸦儿军南下破梁田坡、收复长安，黄巢退出关中东走陈蔡",
            )
            return bg.convert("RGB")

        # T16 泰山狼虎谷横剑折旗落幕（142.55s = u ~ 0.53 帅旗应声折断）
        f_idx = 0 if u < 0.20 else (1 if u < 0.38 else (2 if u < 0.52 else 3))
        sp = get_huangchao_sprite("S5_LANGHUGU", frame=f_idx, scale=1).resize((416, 416), resample=Image.Resampling.NEAREST)
        self._paste(bg, sp, W_PX // 2, 470)
        _draw_outlined_text(d, (W_PX // 2, 760), "十年万里转战倾唐祚  ·  大齐大唐俱成往事", PIL_POEM, (242, 232, 206, 255), sw=4)
        _draw_bilibili_hud(
            bg,
            [("中和四年六月 · ", "#FFFFFF"), ("泰山狼虎谷横剑折旗，起义落幕", "#FFE04D")],
            "黄巢于泰山狼虎谷自刎陨落，十年农民大战争彻底摧毁了大唐中央统治根基",
        )
        return bg.convert("RGB")

    def render_at(self, aid: str, mode: str, u: float, sub_step: int) -> Image.Image:
        if mode == "tactical":
            bid = self.act_specs[aid]["tactical"]
            return self.tactical.render(bid, u)
        if mode == "cutscene":
            return self._draw_cutscene(aid, u, sub_step)
        return self._draw_macro(aid, u, sub_step)


def _measure_lufs(mp4_path: Path) -> str:
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.run(
        [ff, "-hide_banner", "-i", str(mp4_path), "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    )
    m_i = re.search(r"Integrated loudness:\s*\r?\n\s*I:\s*([-\d.]+)\s*LUFS", proc.stderr)
    m_p = re.search(r"True peak:\s*\r?\n\s*Peak:\s*([-\d.]+)\s*dBFS", proc.stderr)
    return f"I={m_i.group(1) if m_i else '?'} LUFS | TP={m_p.group(1) if m_p else '?'} dBFS"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    meta = json.loads(BEAT_JSON.read_text(encoding="utf-8"))
    acts = meta["acts"]
    beats: List[float] = meta["beats"]

    engine = HuangChaoCampaignEngine()
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd_v = [
        ff, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W_PX}x{H_PX}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
        str(RAW_MP4),
    ]
    proc = subprocess.Popen(cmd_v, stdin=subprocess.PIPE)
    assert proc.stdin is not None

    t0 = time.perf_counter()
    starts = [a["t0"] for a in acts]
    for f in range(TOTAL_FRAMES):
        t = f / float(FPS)
        idx = max(0, min(len(acts) - 1, bisect.bisect_right(starts, t) - 1))
        a = acts[idx]
        u = max(0.0, min(1.0, (t - a["t0"]) / max(1e-6, a["t1"] - a["t0"])))
        sub_step = bisect.bisect_right(beats, t)
        img = engine.render_at(a["id"], a["mode"], u, sub_step)
        proc.stdin.write(img.tobytes())

        if (f + 1) % 600 == 0 or f == TOTAL_FRAMES - 1:
            el = time.perf_counter() - t0
            print(f"  Rendered {f + 1}/{TOTAL_FRAMES} frames ({el:.1f}s elapsed, {(f + 1) / el:.1f} fps)", flush=True)

    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg encode failed: rc={rc}")
    print(f"Saved video: {RAW_MP4} ({RAW_MP4.stat().st_size / 1048576:.2f} MB)")

    subprocess.run([
        ff, "-y", "-loglevel", "error",
        "-i", str(RAW_MP4), "-i", str(MIX_WAV),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
        "-movflags", "+faststart", str(FINAL_MP4),
    ], check=True)
    print(f"Saved FINAL campaign MP4: {FINAL_MP4} ({FINAL_MP4.stat().st_size / 1048576:.2f} MB)")

    info = subprocess.run([ff, "-hide_banner", "-i", str(FINAL_MP4)], capture_output=True, text=True).stderr
    for ln in info.splitlines():
        if "Duration:" in ln or "Stream #" in ln:
            print(" ", ln)
    print("Final MP4 Loudness:", _measure_lufs(FINAL_MP4))


if __name__ == "__main__":
    main()
