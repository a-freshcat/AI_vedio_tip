"""
src/data_routes.py
《唐末黄巢起义》“万里大迂回”分段行军路径与水网渡口约束模块
- 严格遵循避坑规范：所有跨长江、淮河、黄河行军必须经过显式渡口节点（ferry/pass），绝不出现“踏水凌波”直线穿河
- 分为五大战略行军阶段（R01 ~ R05），每条路线包含精细地理路径点 waypoints 与行军叙事元数据
"""

from typing import Dict, List

MARCH_ROUTES: List[Dict] = [
    {
        "route_id": "R01_SHANDONG_TO_HUAI",
        "name": "第一阶段：冤句起兵与淮西分军",
        "date_range": ("0875-06-10", "0878-02-18"),
        "stage_key": "S2_REBEL",
        "color": "#D9383A",
        "style": "dashed_rebel",
        "summary": "曹州冤句起兵，转战豫皖鄂；蕲州怒斥王仙芝受招安而分军，黄梅战后接掌全军号冲天大将军。",
        "city_sequence": ["YUANQU", "CHANGYUAN", "BIAN", "CHENZHOU", "CAIZHOU", "QIZHOU", "HUANGMEI"],
        "crossings": [],
        "waypoints": [
            (35.15, 115.38),  # 冤句
            (35.20, 114.67),  # 长垣
            (34.80, 114.31),  # 汴州外围
            (33.73, 114.88),  # 陈州
            (33.01, 114.36),  # 蔡州
            (31.50, 115.10),  # 大别山北麓通道
            (30.23, 115.43),  # 蕲州（分军转折点）
            (30.08, 115.93),  # 黄梅（王仙芝战死，黄巢统帅）
        ],
    },
    {
        "route_id": "R02_DETOUR_TO_LINGNAN",
        "name": "第二阶段：避实击虚 · 刊山开道万里南下",
        "date_range": ("0878-03-01", "0879-09-22"),
        "stage_key": "S3_CHONGTIAN",
        "color": "#E67E22",
        "style": "solid_detour",
        "summary": "采石矶南渡长江，经宣州、衢州，刊山开道七百里越仙霞岭入闽克福州，长驱直下攻破广州。",
        "city_sequence": ["HUANGMEI", "CAISHI_FERRY", "XUANZHOU", "QUZHOU", "XIANXIA_PASS", "JIANZHOU", "FUZHOU", "CHAOZHOU", "GUANGZHOU"],
        "crossings": [
            {"river": "长江", "node": "CAISHI_FERRY", "coord": (31.66, 118.47), "method": "渡江舟师"},
            {"river": "仙霞山脉", "node": "XIANXIA_PASS", "coord": (28.36, 118.52), "method": "刊山开道七百里"},
        ],
        "waypoints": [
            (30.08, 115.93),  # 黄梅
            (30.90, 117.60),  # 皖江北岸走廊
            (31.66, 118.47),  # 采石矶渡口（南渡长江）
            (30.95, 118.76),  # 宣州
            (29.80, 119.00),  # 浙西河谷
            (28.94, 118.87),  # 衢州
            (28.36, 118.52),  # 仙霞岭古道（刊山开道）
            (27.04, 118.32),  # 建州
            (26.08, 119.30),  # 福州
            (24.90, 118.50),  # 闽粤沿海陆道
            (23.66, 116.63),  # 潮州
            (23.25, 114.80),  # 东江北岸走廊
            (23.14, 113.26),  # 广州（控制南海门户）
        ],
    },
    {
        "route_id": "R03_NORTHERN_EXPEDITION",
        "name": "第三阶段：湘桂水陆并进 · 北伐中原",
        "date_range": ("0879-10-25", "0880-07-15"),
        "stage_key": "S3_CHONGTIAN",
        "color": "#2B5B84",
        "style": "bold_offensive",
        "summary": "因岭南疫病果断北伐，经桂州、灵渠编筏顺湘江破潭州，东下鄂州再由采石矶北渡长江、三江口渡淮。",
        "city_sequence": ["GUANGZHOU", "GUIZHOU", "LINGQU_PASS", "TANZHOU", "JIANGLING", "EZHOU", "CAISHI_FERRY", "SANJIANGKOU"],
        "crossings": [
            {"river": "湘桂分水岭", "node": "LINGQU_PASS", "coord": (25.61, 110.67), "method": "灵渠编筏顺流"},
            {"river": "长江", "node": "CAISHI_FERRY", "coord": (31.66, 118.47), "method": "北渡长江"},
            {"river": "淮河", "node": "SANJIANGKOU", "coord": (32.95, 117.18), "method": "渡淮入中原"},
        ],
        "waypoints": [
            (23.14, 113.26),  # 广州
            (24.10, 111.50),  # 贺江-桂江走廊
            (25.27, 110.29),  # 桂州
            (25.61, 110.67),  # 灵渠古运河
            (26.90, 112.60),  # 衡州湘江东岸
            (28.23, 112.98),  # 潭州(长沙)
            (29.40, 113.10),  # 岳州东岸
            (30.35, 112.19),  # 江陵(荆南)
            (30.55, 114.31),  # 鄂州
            (31.66, 118.47),  # 采石矶渡口（北渡长江）
            (32.30, 117.80),  # 滁州-濠州陆道
            (32.95, 117.18),  # 三江口渡口（北渡淮河）
        ],
    },
    {
        "route_id": "R04_CAPTURE_TWO_CAPITALS",
        "name": "第四阶段：饮马黄河 · 破潼关入长安称帝",
        "date_range": ("0880-08-01", "0881-01-16"),
        "stage_key": "S4_EMPEROR",
        "color": "#F6C226",
        "style": "imperial_spearhead",
        "summary": "六十万大军席卷中原，洛阳望风而降，正面强攻与禁谷迂回双箭头夹击攻破潼关，入长安含元殿即位建元大齐。",
        "city_sequence": ["SANJIANGKOU", "CHENZHOU", "BIAN", "LUOYANG", "TONGGUAN", "CHANGAN"],
        "crossings": [
            {"river": "潼关天险", "node": "TONGGUAN", "coord": (34.54, 110.29), "method": "禁谷迂回夹击破关"},
        ],
        "waypoints": [
            (32.95, 117.18),  # 三江口渡口
            (33.73, 114.88),  # 陈州外围
            (34.80, 114.31),  # 汴州
            (34.67, 112.45),  # 东都洛阳
            (34.60, 111.20),  # 陕州黄河以南驿道
            (34.54, 110.29),  # 潼关
            (34.51, 109.62),  # 渭南走廊
            (34.27, 108.95),  # 长安含元殿
        ],
    },
    {
        "route_id": "R05_RETREAT_TO_LANGHUGU",
        "name": "第五阶段：撤出关中 · 陈州苦战与狼虎谷终局",
        "date_range": ("0883-04-10", "0884-07-13"),
        "stage_key": "S5_LANGHUGU",
        "color": "#8E2430",
        "style": "broken_retreat",
        "summary": "梁田坡败于李克用鸦儿军后东撤河南，围陈州三百日无果；王满渡遭半渡而击溃散，东奔泰山狼虎谷悲壮落幕。",
        "city_sequence": ["CHANGAN", "LIANGTIANPO", "TONGGUAN", "LUOYANG", "CHENZHOU", "WANGMANDU", "LANGHUGU"],
        "crossings": [
            {"river": "黄河故道", "node": "WANGMANDU", "coord": (34.86, 114.03), "method": "半渡受阻东撤山东"},
        ],
        "waypoints": [
            (34.27, 108.95),  # 长安
            (34.51, 109.62),  # 梁田坡
            (34.54, 110.29),  # 潼关东出
            (34.67, 112.45),  # 洛阳
            (33.73, 114.88),  # 陈州（围城三百日）
            (34.86, 114.03),  # 王满渡（决战溃散）
            (35.15, 115.38),  # 途经故里曹州外围
            (36.15, 117.52),  # 泰山狼虎谷（自刎终局）
        ],
    },
]
