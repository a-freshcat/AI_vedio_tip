"""
src/data_geo.py
《唐末黄巢起义（874–884）》地理坐标、河网渡口与阵营定义模块
- 地理边界向南扩展至 21.5°N（覆盖福州、广州及桂湘北伐水系）
- 严格执行“岸线偏移对齐”规则：所有临河城池坐标均落在陆地侧岸线，杜绝“水上漂浮”
- 显式定义长江、黄河、淮河、湘桂水系的关键渡口与山岭关隘节点，保障行军路径物理写实
"""

from typing import Dict, List, Tuple

# 地理包围盒（覆盖华北、关中、中原、江淮、闽浙、岭南、雷州半岛、海南岛、台湾岛及辽东湾）
LAT_BOUNDS: Tuple[float, float] = (18.0, 41.2)
LON_BOUNDS: Tuple[float, float] = (102.0, 123.5)

# 势力阵营配色与旗帜样式
FACTIONS: Dict[str, Dict[str, str]] = {
    "TANG": {
        "name": "大唐朝廷/藩镇",
        "short_name": "唐",
        "color": "#C83E37",       # 晚唐朱红
        "border_color": "#7A1C18",
        "flag_style": "tang_crimson",
    },
    "QI": {
        "name": "黄巢义军/大齐",
        "short_name": "齐",
        "color": "#2B5B84",       # 宏观版图冷蓝（与唐朱红形成高对比战线）
        "accent_color": "#F6C226",# 个人状态栏/大齐明黄
        "border_color": "#16324A",
        "flag_style": "qi_gold_flame",
    },
    "SHATUO": {
        "name": "沙陀鸦儿军",
        "short_name": "沙陀",
        "color": "#2A2D34",       # 玄黑鸦军
        "border_color": "#111317",
        "flag_style": "black_crow",
    },
}

# 核心城池、关隘、渡口与个人转折地标（共 36 个高精度地理节点）
# kind: capital(都城) | pass(雄关/山道) | city(州府重镇) | ferry(大河渡口) | camp(起兵/决战/陨落点)
CITIES: Dict[str, Dict] = {
    # --- 一、关中与河东核心区 ---
    "CHANGAN": {
        "name": "长安", "modern": "陕西西安", "lat": 34.27, "lon": 108.95,
        "kind": "capital", "init_faction": "TANG", "coord_confidence": "high",
        "note": "大唐西京 / 大齐都城，渭水南岸平原",
    },
    "QUJIANG": {
        "name": "曲江池", "modern": "西安东南", "lat": 34.21, "lon": 108.99,
        "kind": "camp", "init_faction": "TANG", "coord_confidence": "high",
        "note": "874年黄巢落第赋菊《不第后赋菊》个人起点",
    },
    "TONGGUAN": {
        "name": "潼关", "modern": "陕西潼关", "lat": 34.54, "lon": 110.29,
        "kind": "pass", "init_faction": "TANG", "coord_confidence": "high",
        "note": "黄河拐弯南岸台地，关中东大门",
    },
    "TONGZHOU": {
        "name": "同州", "modern": "陕西大荔", "lat": 34.80, "lon": 109.94,
        "kind": "city", "init_faction": "TANG", "coord_confidence": "high",
        "note": "渭北重镇，882年朱温据同州叛齐降唐",
    },
    "LIANGTIANPO": {
        "name": "梁田坡", "modern": "陕西渭南东", "lat": 34.51, "lon": 109.62,
        "kind": "camp", "init_faction": "TANG", "coord_confidence": "high",
        "note": "883年李克用沙陀鸦儿军大败齐军决战地",
    },
    "TAIYUAN": {
        "name": "太原", "modern": "山西太原", "lat": 37.87, "lon": 112.53,
        "kind": "capital", "init_faction": "TANG", "coord_confidence": "high",
        "note": "河东节度使治所，汾水西岸",
    },

    # --- 二、中原与山东起兵区 ---
    "LUOYANG": {
        "name": "洛阳", "modern": "河南洛阳", "lat": 34.67, "lon": 112.45,
        "kind": "capital", "init_faction": "TANG", "coord_confidence": "high",
        "note": "大唐东都，洛水北岸",
    },
    "YUANQU": {
        "name": "冤句(曹州)", "modern": "山东菏泽西南", "lat": 35.15, "lon": 115.38,
        "kind": "camp", "init_faction": "TANG", "coord_confidence": "high",
        "note": "875年黄巢散家财聚众起兵之地",
    },
    "CHANGYUAN": {
        "name": "长垣(匡城)", "modern": "河南长垣", "lat": 35.20, "lon": 114.67,
        "kind": "camp", "init_faction": "TANG", "coord_confidence": "high",
        "note": "王仙芝率先起兵响应点",
    },
    "BIAN": {
        "name": "汴州", "modern": "河南开封", "lat": 34.80, "lon": 114.31,
        "kind": "city", "init_faction": "TANG", "coord_confidence": "high",
        "note": "宣武军治所，大运河与黄河枢纽",
    },
    "WANGMANDU": {
        "name": "王满渡", "modern": "河南中牟北", "lat": 34.86, "lon": 114.03,
        "kind": "ferry", "init_faction": "TANG", "coord_confidence": "medium",
        "note": "884年5月黄巢主力被李克用半渡而击溃败处",
    },
    "CHENZHOU": {
        "name": "陈州", "modern": "河南淮阳", "lat": 33.73, "lon": 114.88,
        "kind": "city", "init_faction": "TANG", "coord_confidence": "high",
        "note": "883-884年黄巢围攻近三百日未克之坚城",
    },
    "CAIZHOU": {
        "name": "蔡州", "modern": "河南汝南", "lat": 33.01, "lon": 114.36,
        "kind": "city", "init_faction": "TANG", "coord_confidence": "high",
        "note": "秦宗权据守并与黄巢合流处",
    },
    "LANGHUGU": {
        "name": "狼虎谷", "modern": "山东莱芜西南", "lat": 36.15, "lon": 117.52,
        "kind": "camp", "init_faction": "TANG", "coord_confidence": "high",
        "note": "884年7月黄巢英雄末路自刎陨落处",
    },

    # --- 三、江淮与长江关键渡口 ---
    "QIZHOU": {
        "name": "蕲州", "modern": "湖北蕲春", "lat": 30.23, "lon": 115.43,
        "kind": "city", "init_faction": "TANG", "coord_confidence": "high",
        "note": "876年底王仙芝欲受唐招安、黄巢怒而分军之地",
    },
    "HUANGMEI": {
        "name": "黄梅", "modern": "湖北黄梅", "lat": 30.08, "lon": 115.93,
        "kind": "camp", "init_faction": "TANG", "coord_confidence": "high",
        "note": "878年初王仙芝战死，黄巢接掌全军号冲天大将军",
    },
    "YANGZHOU": {
        "name": "扬州", "modern": "江苏扬州", "lat": 32.39, "lon": 119.42,
        "kind": "city", "init_faction": "TANG", "coord_confidence": "high",
        "note": "淮南节度使高骈驻地，长江北岸",
    },
    "CAISHI_FERRY": {
        "name": "采石矶渡口", "modern": "安徽马鞍山", "lat": 31.66, "lon": 118.47,
        "kind": "ferry", "init_faction": "TANG", "coord_confidence": "high",
        "note": "长江天堑核心渡江节点（南北往返必经渡口）",
    },
    "XUANZHOU": {
        "name": "宣州", "modern": "安徽宣城", "lat": 30.95, "lon": 118.76,
        "kind": "city", "init_faction": "TANG", "coord_confidence": "high",
        "note": "江南转战重镇，在此折向浙东入闽",
    },
    "SANJIANGKOU": {
        "name": "三江口渡口", "modern": "安徽怀远淮河岸", "lat": 32.95, "lon": 117.18,
        "kind": "ferry", "init_faction": "TANG", "coord_confidence": "high",
        "note": "880年北伐渡过淮河之关键津渡",
    },

    # --- 四、浙闽仙霞古道与岭南大迂回区 ---
    "QUZHOU": {
        "name": "衢州", "modern": "浙江衢州", "lat": 28.94, "lon": 118.87,
        "kind": "city", "init_faction": "TANG", "coord_confidence": "high",
        "note": "浙西入闽咽喉，仙霞岭北麓",
    },
    "XIANXIA_PASS": {
        "name": "仙霞岭古道", "modern": "浙闽交界江山浦城间", "lat": 28.36, "lon": 118.52,
        "kind": "pass", "init_faction": "TANG", "coord_confidence": "high",
        "note": "黄巢“刊山开道七百里”破天险入福建之壮举",
    },
    "JIANZHOU": {
        "name": "建州", "modern": "福建建瓯", "lat": 27.04, "lon": 118.32,
        "kind": "city", "init_faction": "TANG", "coord_confidence": "high",
        "note": "闽北重镇，沿建溪南下福州",
    },
    "FUZHOU": {
        "name": "福州", "modern": "福建福州", "lat": 26.08, "lon": 119.30,
        "kind": "city", "init_faction": "TANG", "coord_confidence": "high",
        "note": "878年12月攻克，闽江北岸陆地",
    },
    "CHAOZHOU": {
        "name": "潮州", "modern": "广东潮州", "lat": 23.66, "lon": 116.63,
        "kind": "city", "init_faction": "TANG", "coord_confidence": "high",
        "note": "粤东门户，韩江西岸",
    },
    "GUANGZHOU": {
        "name": "广州", "modern": "广东广州", "lat": 23.14, "lon": 113.26,
        "kind": "city", "init_faction": "TANG", "coord_confidence": "high",
        "note": "879年9月攻克南海重镇，珠江北岸陆地",
    },

    # --- 五、桂湘水系北伐通道 ---
    "GUIZHOU": {
        "name": "桂州", "modern": "广西桂林", "lat": 25.27, "lon": 110.29,
        "kind": "city", "init_faction": "TANG", "coord_confidence": "high",
        "note": "879年10月北伐起点，漓江西岸",
    },
    "LINGQU_PASS": {
        "name": "灵渠古运河", "modern": "广西兴安", "lat": 25.61, "lon": 110.67,
        "kind": "pass", "init_faction": "TANG", "coord_confidence": "high",
        "note": "连通珠江与长江水系的千年古渠，编大筏顺湘江北下",
    },
    "TANZHOU": {
        "name": "潭州(长沙)", "modern": "湖南长沙", "lat": 28.23, "lon": 112.98,
        "kind": "city", "init_faction": "TANG", "coord_confidence": "high",
        "note": "879年11月一日攻破湖南重镇，湘江东岸",
    },
    "JIANGLING": {
        "name": "江陵(荆南)", "modern": "湖北荆州", "lat": 30.35, "lon": 112.19,
        "kind": "city", "init_faction": "TANG", "coord_confidence": "high",
        "note": "长江北岸中游重镇，五十万大军在此受挫后东向",
    },
    "EZHOU": {
        "name": "鄂州", "modern": "湖北武昌", "lat": 30.55, "lon": 114.31,
        "kind": "city", "init_faction": "TANG", "coord_confidence": "high",
        "note": "长江南岸重镇，由此顺江东下至采石矶渡江",
    },
}

ISLAND_LANDMARKS: Dict[str, Dict] = {
    "QIONGZHOU": {"name": "琼州", "modern": "海南海口琼山", "lat": 19.98, "lon": 110.35, "note": "唐岭南道琼管经略使治所"},
    "ZHENZHOU": {"name": "振州", "modern": "海南三亚崖州", "lat": 18.38, "lon": 109.20, "note": "唐代海南岛南端州治"},
    "LIUQIU": {"name": "流求(台湾)", "modern": "台湾台南嘉南", "lat": 23.25, "lon": 120.38, "note": "东南海疆重镇"},
    "PENGHU": {"name": "澎湖", "modern": "台湾澎湖列岛", "lat": 23.57, "lon": 119.58, "note": "台海津要"},
}
