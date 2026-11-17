# **《唐末黄巢起义（874–884）》地理坐标、大迂回行军路径与时间轴数据模块**

本档案为《唐末黄巢起义》历史军事地理推演系统的核心数据与编译引擎规格说明。系统完整覆盖起义从萌芽、爆发、避实击虚万里大迂回、攻占两京称帝，至最终撤出关中兵败狼虎谷的全过程。

# **一、 系统全局指标**

* **时间跨度**：公元 0874-11-15（长安曲江落第赋菊）至 0884-07-13（泰山狼虎谷自刎），共 **3,528 天**  
* **空间包围盒**：`21.5°N ~ 41.5°N`，`103.0°E ~ 121.5°E`（南扩至广州与福州，完整覆盖岭南大迂回与桂湘北伐水系）  
* **编译校验结果**：31 座城池/渡口锚点 · 5 段大迂回行军路线（累计 6,275.0 km） · 16 帧双线时间轴 · 36 次势力控制权变更

---

# **二、 地理坐标与河网渡口模块**

地理坐标严格遵循历史地理写实规范：

1. **岸线偏移对齐**：所有临河城市（长安、洛阳、潼关、潭州、江陵、福州、广州等）坐标均对齐至河岸陆地侧，杜绝"城池水上漂浮"现象。  
2. **显式渡口与山道**：单列 `ferry`（采石矶渡口、三江口渡口、王满渡）与 `pass`（仙霞岭古道、灵渠古运河、潼关），确保跨江渡河与翻越五岭具备物理通道支撑。

## **2.1 模块源码 (`src/data_geo.py`)**

n  
from typing import Dict, List, Tuple

LAT\_BOUNDS: Tuple\[float, float\] \= (21.5, 41.5)  
LON\_BOUNDS: Tuple\[float, float\] \= (103.0, 121.5)

FACTIONS: Dict\[str, Dict\[str, str\]\] \= {  
"TANG": {"name": "大唐朝廷/藩镇", "short\_name": "唐", "color": "\#C83E37", "border\_color": "\#7A1C18", "flag\_style": "tang\_crimson"},  
"QI": {"name": "黄巢义军/大齐", "short\_name": "齐", "color": "\#2B5B84", "accent\_color": "\#F6C226", "border\_color": "\#16324A", "flag\_style": "qi\_gold\_flame"},  
"SHATUO": {"name": "沙陀鸦儿军", "short\_name": "沙陀", "color": "\#2A2D34", "border\_color": "\#111317", "flag\_style": "black\_crow"},  
}

CITIES: Dict\[str, Dict\] \= {  
"CHANGAN": {"name": "长安", "modern": "陕西西安", "lat": 34.27, "lon": 108.95, "kind": "capital", "init\_faction": "TANG", "coord\_confidence": "high", "note": "大唐西京 / 大齐都城，渭水南岸平原"},  
"QUJIANG": {"name": "曲江池", "modern": "西安东南", "lat": 34.21, "lon": 108.99, "kind": "camp", "init\_faction": "TANG", "coord\_confidence": "high", "note": "874年黄巢落第赋菊《不第后赋菊》个人起点"},  
"TONGGUAN": {"name": "潼关", "modern": "陕西潼关", "lat": 34.54, "lon": 110.29, "kind": "pass", "init\_faction": "TANG", "coord\_confidence": "high", "note": "黄河拐弯南岸台地，关中东大门"},  
"TONGZHOU": {"name": "同州", "modern": "陕西大荔", "lat": 34.80, "lon": 109.94, "kind": "city", "init\_faction": "TANG", "coord\_confidence": "high", "note": "渭北重镇，882年朱温据同州叛齐降唐"},  
"LIANGTIANPO": {"name": "梁田坡", "modern": "陕西渭南东", "lat": 34.51, "lon": 109.62, "kind": "camp", "init\_faction": "QI", "coord\_confidence": "high", "note": "883年李克用沙陀鸦儿军大败齐军决战地"},  
"TAIYUAN": {"name": "太原", "modern": "山西太原", "lat": 37.87, "lon": 112.53, "kind": "capital", "init\_faction": "TANG", "coord\_confidence": "high", "note": "河东节度使治所，汾水西岸"},  
"LUOYANG": {"name": "洛阳", "modern": "河南洛阳", "lat": 34.67, "lon": 112.45, "kind": "capital", "init\_faction": "TANG", "coord\_confidence": "high", "note": "大唐东都，洛水北岸"},  
"YUANQU": {"name": "冤句(曹州)", "modern": "山东菏泽西南", "lat": 35.15, "lon": 115.38, "kind": "camp", "init\_faction": "TANG", "coord\_confidence": "high", "note": "875年黄巢散家财聚众起兵之地"},  
"CHANGYUAN": {"name": "长垣(匡城)", "modern": "河南长垣", "lat": 35.20, "lon": 114.67, "kind": "camp", "init\_faction": "TANG", "coord\_confidence": "high", "note": "王仙芝率先起兵响应点"},  
"BIAN": {"name": "汴州", "modern": "河南开封", "lat": 34.80, "lon": 114.31, "kind": "city", "init\_faction": "TANG", "coord\_confidence": "high", "note": "宣武军治所，大运河与黄河枢纽"},  
"WANGMANDU": {"name": "王满渡", "modern": "河南中牟北", "lat": 34.86, "lon": 114.03, "kind": "ferry", "init\_faction": "TANG", "coord\_confidence": "medium", "note": "884年5月黄巢主力被李克用半渡而击溃败处"},  
"CHENZHOU": {"name": "陈州", "modern": "河南淮阳", "lat": 33.73, "lon": 114.88, "kind": "city", "init\_faction": "TANG", "coord\_confidence": "high", "note": "883-884年黄巢围攻近三百日未克之坚城"},  
"CAIZHOU": {"name": "蔡州", "modern": "河南汝南", "lat": 33.01, "lon": 114.36, "kind": "city", "init\_faction": "TANG", "coord\_confidence": "high", "note": "秦宗权据守并与黄巢合流处"},  
"LANGHUGU": {"name": "狼虎谷", "modern": "山东莱芜西南", "lat": 36.15, "lon": 117.52, "kind": "camp", "init\_faction": "TANG", "coord\_confidence": "high", "note": "884年7月黄巢英雄末路自刎陨落处"},  
"QIZHOU": {"name": "蕲州", "modern": "湖北蕲春", "lat": 30.23, "lon": 115.43, "kind": "city", "init\_faction": "TANG", "coord\_confidence": "high", "note": "876年底王仙芝欲受唐招安、黄巢怒而分军之地"},  
"HUANGMEI": {"name": "黄梅", "modern": "湖北黄梅", "lat": 30.08, "lon": 115.93, "kind": "camp", "init\_faction": "TANG", "coord\_confidence": "high", "note": "878年初王仙芝战死，黄巢接掌全军号冲天大将军"},  
"YANGZHOU": {"name": "扬州", "modern": "江苏扬州", "lat": 32.39, "lon": 119.42, "kind": "city", "init\_faction": "TANG", "coord\_confidence": "high", "note": "淮南节度使高骈驻地，长江北岸"},  
"CAISHI\_FERRY": {"name": "采石矶渡口", "modern": "安徽马鞍山", "lat": 31.66, "lon": 118.47, "kind": "ferry", "init\_faction": "TANG", "coord\_confidence": "high", "note": "长江天堑核心渡江节点（南北往返必经渡口）"},  
"XUANZHOU": {"name": "宣州", "modern": "安徽宣城", "lat": 30.95, "lon": 118.76, "kind": "city", "init\_faction": "TANG", "coord\_confidence": "high", "note": "江南转战重镇，在此折向浙东入闽"},  
"SANJIANGKOU": {"name": "三江口渡口", "modern": "安徽怀远淮河岸", "lat": 32.95, "lon": 117.18, "kind": "ferry", "init\_faction": "TANG", "coord\_confidence": "high", "note": "880年北伐渡过淮河之关键津渡"},  
"QUZHOU": {"name": "衢州", "modern": "浙江衢州", "lat": 28.94, "lon": 118.87, "kind": "city", "init\_faction": "TANG", "coord\_confidence": "high", "note": "浙西入闽咽喉，仙霞岭北麓"},  
"XIANXIA\_PASS": {"name": "仙霞岭古道", "modern": "浙闽交界江山浦城间", "lat": 28.36, "lon": 118.52, "kind": "pass", "init\_faction": "TANG", "coord\_confidence": "high", "note": "黄巢"刊山开道七百里"破天险入福建之壮举"},  
"JIANZHOU": {"name": "建州", "modern": "福建建瓯", "lat": 27.04, "lon": 118.32, "kind": "city", "init\_faction": "TANG", "coord\_confidence": "high", "note": "闽北重镇，沿建溪南下福州"},  
"FUZHOU": {"name": "福州", "modern": "福建福州", "lat": 26.08, "lon": 119.30, "kind": "city", "init\_faction": "TANG", "coord\_confidence": "high", "note": "878年12月攻克，闽江北岸陆地"},  
"CHAOZHOU": {"name": "潮州", "modern": "广东潮州", "lat": 23.66, "lon": 116.63, "kind": "city", "init\_faction": "TANG", "coord\_confidence": "high", "note": "粤东门户，韩江西岸"},  
"GUANGZHOU": {"name": "广州", "modern": "广东广州", "lat": 23.14, "lon": 113.26, "kind": "city", "init\_faction": "TANG", "coord\_confidence": "high", "note": "879年9月攻克南海重镇，珠江北岸陆地"},  
"GUIZHOU": {"name": "桂州", "modern": "广西桂林", "lat": 25.27, "lon": 110.29, "kind": "city", "init\_faction": "TANG", "coord\_confidence": "high", "note": "879年10月北伐起点，漓江西岸"},  
"LINGQU\_PASS": {"name": "灵渠古运河", "modern": "广西兴安", "lat": 25.61, "lon": 110.67, "kind": "pass", "init\_faction": "TANG", "coord\_confidence": "high", "note": "连通珠江与长江水系的千年古渠，编大筏顺湘江北下"},  
"TANZHOU": {"name": "潭州(长沙)", "modern": "湖南长沙", "lat": 28.23, "lon": 112.98, "kind": "city", "init\_faction": "TANG", "coord\_confidence": "high", "note": "879年11月一日攻破湖南重镇，湘江东岸"},  
"JIANGLING": {"name": "江陵(荆南)", "modern": "湖北荆州", "lat": 30.35, "lon": 112.19, "kind": "city", "init\_faction": "TANG", "coord\_confidence": "high", "note": "长江北岸中游重镇，五十万大军在此受挫后东向"},  
"EZHOU": {"name": "鄂州", "modern": "湖北武昌", "lat": 30.55, "lon": 114.31, "kind": "city", "init\_faction": "TANG", "coord\_confidence": "high", "note": "长江南岸重镇，由此顺江东下至采石矶渡江"},  
}

````

---

## 三、 万里大迂回行军路径模块

### 3.1 战略阶段概览

| 路线 ID | 战略阶段 | 时间区间 | 关键渡口 / 山隘 | 对应主角阶段 | 估算里程 |
|---|---|---|---|---|---|
| `R01_SHANDONG_TO_HUAI` | 冤句起兵与淮西分军 | 0875-06-10 ~ 0878-02-18 | 大别山北麓通道 | `S2_REBEL` | ~891.5 km |
| `R02_DETOUR_TO_LINGNAN` | 刊山开道万里南下 | 0878-03-01 ~ 0879-09-22 | 采石矶渡口、仙霞岭古道 | `S3_CHONGTIAN` | ~1,654.4 km |
| `R03_NORTHERN_EXPEDITION` | 湘桂水陆并进北伐 | 0879-10-25 ~ 0880-07-15 | 灵渠古运河、采石矶、三江口 | `S3_CHONGTIAN` | ~1,656.8 km |
| `R04_CAPTURE_TWO_CAPITALS` | 破潼关入长安称帝 | 0880-08-01 ~ 0881-01-16 | 潼关禁谷迂回 | `S4_EMPEROR` | ~966.2 km |
| `R05_RETREAT_TO_LANGHUGU` | 撤出关中与狼虎谷终局 | 0883-04-10 ~ 0884-07-13 | 王满渡黄河故道 | `S5_LANGHUGU` | ~1,106.1 km |

### 3.2 模块源码 (`src/data_routes.py`)

```python
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
            (35.15, 115.38), (35.20, 114.67), (34.80, 114.31), (33.73, 114.88),
            (33.01, 114.36), (31.50, 115.10), (30.23, 115.43), (30.08, 115.93),
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
            (30.08, 115.93), (30.90, 117.60), (31.66, 118.47), (30.95, 118.76),
            (29.80, 119.00), (28.94, 118.87), (28.36, 118.52), (27.04, 118.32),
            (26.08, 119.30), (24.90, 118.50), (23.66, 116.63), (23.25, 114.80), (23.14, 113.26),
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
            (23.14, 113.26), (24.10, 111.50), (25.27, 110.29), (25.61, 110.67),
            (26.90, 112.60), (28.23, 112.98), (29.40, 113.10), (30.35, 112.19),
            (30.55, 114.31), (31.66, 118.47), (32.30, 117.80), (32.95, 117.18),
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
            (32.95, 117.18), (33.73, 114.88), (34.80, 114.31), (34.67, 112.45),
            (34.60, 111.20), (34.54, 110.29), (34.51, 109.62), (34.27, 108.95),
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
            (34.27, 108.95), (34.51, 109.62), (34.54, 110.29), (34.67, 112.45),
            (33.73, 114.88), (34.86, 114.03), (35.15, 115.38), (36.15, 117.52),
        ],
    },
]
````

---

# **四、 双线个人传记时间轴模块**

每一帧事件除驱动宏观/微观地图演进外，均直接绑定黄巢 `64×64` 精修像素精灵（`huangchao_sprites_refined.py`）的阶段状态 huangchao\_stage、动作帧索引 sprite\_frames 与特写模式 portrait\_mode。

## **4.1 模块源码 (src/data\_timeline.py)**

n  
from typing import Dict, List

TIMELINE\_EVENTS: List\[Dict\] \= \[  
{"event\_id": "T01", "date": "0874-11-15", "date\_precision": "month", "era\_title": "乾符元年冬 · 落第赋菊", "camera": "portrait\_pip", "focus\_city": "QUJIANG", "route\_id": None, "captures": \[\], "huangchao\_stage": "S1\_SCHOLAR", "sprite\_frames": \[0, 1, 2, 3\], "portrait\_mode": "full\_panel", "headline": "不第后赋菊：他年我若为青帝，报与桃花一处开", "subtitle": "屡试不第的曹州士子黄巢立于长安曲江秋风中，掷笔碎榜，埋下倾覆大唐的火种。"},  
{"event\_id": "T02", "date": "0875-06-10", "date\_precision": "day\_approx", "era\_title": "乾符二年五月 · 冤句起兵", "camera": "macro", "focus\_city": "YUANQU", "route\_id": "R01\_SHANDONG\_TO\_HUAI", "captures": \[("YUANQU", "QI"), ("CHANGYUAN", "QI")\], "huangchao\_stage": "S2\_REBEL", "sprite\_frames": \[0, 1, 2, 3\], "portrait\_mode": "pip\_corner", "headline": "散家财聚众数千，冤句盐枭拔剑起义", "subtitle": "关东旱蝗大饥，黄巢在曹州冤句树起黑底赤心义旗，响应王仙芝转战中原。"},  
{"event\_id": "T03", "date": "0876-12-20", "date\_precision": "month", "era\_title": "乾符三年冬 · 蕲州分军", "camera": "micro", "focus\_city": "QIZHOU", "route\_id": "R01\_SHANDONG\_TO\_HUAI", "captures": \[("QIZHOU", "QI")\], "huangchao\_stage": "S2\_REBEL", "sprite\_frames": \[1, 2\], "portrait\_mode": "pip\_corner", "headline": "怒斥招安：王仙芝欲降唐廷，黄巢痛殴仙芝分军独立", "subtitle": "当王仙芝动摇欲受朝廷官职时，黄巢拒不妥协，率部北上独立转战，性格决绝初现。"},  
{"event\_id": "T04", "date": "0878-02-18", "date\_precision": "day", "era\_title": "乾符五年正月 · 冲天大将军", "camera": "micro", "focus\_city": "HUANGMEI", "route\_id": "R01\_SHANDONG\_TO\_HUAI", "captures": \[("HUANGMEI", "QI")\], "huangchao\_stage": "S3\_CHONGTIAN", "sprite\_frames": \[0, 1\], "portrait\_mode": "pip\_corner", "headline": "王仙芝黄梅战死，黄巢接掌全军自号"冲天大将军"", "subtitle": "尚让率余部归附，众推黄巢为黄王，建元王霸，身披玄铁明光铠开启万里转战。"},  
{"event\_id": "T05", "date": "0878-08-15", "date\_precision": "month", "era\_title": "乾符五年秋 · 刊山开道入闽", "camera": "macro", "focus\_city": "XIANXIA\_PASS", "route\_id": "R02\_DETOUR\_TO\_LINGNAN", "captures": \[("XUANZHOU", "QI"), ("QUZHOU", "QI"), ("JIANZHOU", "QI")\], "huangchao\_stage": "S3\_CHONGTIAN", "sprite\_frames": \[1, 2\], "portrait\_mode": "map\_leader", "headline": "避实击虚！南渡长江，刊山开道七百里越仙霞岭", "subtitle": "在浙西遭唐军阻击后，黄巢果断放弃硬拼，劈山开路直插福建腹地。"},  
{"event\_id": "T06", "date": "0878-12-10", "date\_precision": "month", "era\_title": "乾符五年十二月 · 攻克福州", "camera": "macro", "focus\_city": "FUZHOU", "route\_id": "R02\_DETOUR\_TO\_LINGNAN", "captures": \[("FUZHOU", "QI")\], "huangchao\_stage": "S3\_CHONGTIAN", "sprite\_frames": \[2, 3\], "portrait\_mode": "map\_leader", "headline": "兵锋抵海：破福州城，沿东南沿海长驱南下", "subtitle": "唐廷误判义军已远遁蛮荒，殊不知黄巢正在完成一场史无前例的战略大迂回。"},  
{"event\_id": "T07", "date": "0879-09-22", "date\_precision": "day", "era\_title": "乾符六年九月 · 破广州控南海", "camera": "micro", "focus\_city": "GUANGZHOU", "route\_id": "R02\_DETOUR\_TO\_LINGNAN", "captures": \[("CHAOZHOU", "QI"), ("GUANGZHOU", "QI")\], "huangchao\_stage": "S3\_CHONGTIAN", "sprite\_frames": \[3, 0\], "portrait\_mode": "pip\_corner", "headline": "一举攻克岭南首府广州，切断唐廷海外财赋命脉", "subtitle": "求任天平节度使遭拒后，黄巢挥师急袭攻陷广州，大军休整蓄势。"},  
{"event\_id": "T08", "date": "0879-10-25", "date\_precision": "month", "era\_title": "乾符六年十月 · 灵渠编筏北伐", "camera": "macro", "focus\_city": "LINGQU\_PASS", "route\_id": "R03\_NORTHERN\_EXPEDITION", "captures": \[("GUIZHOU", "QI"), ("TANZHOU", "QI"), ("JIANGLING", "QI")\], "huangchao\_stage": "S3\_CHONGTIAN", "sprite\_frames": \[1, 2, 3\], "portrait\_mode": "map\_leader", "headline": "发布《北伐檄文》！经桂州灵渠编大筏顺湘江横扫荆湖", "subtitle": "岭南疫起，黄巢果断挥师北指中原，一日破潭州（长沙），号称五十万众。"},  
{"event\_id": "T09", "date": "0880-07-15", "date\_precision": "day\_approx", "era\_title": "广明元年七月 · 渡江饮马淮水", "camera": "macro", "focus\_city": "SANJIANGKOU", "route\_id": "R03\_NORTHERN\_EXPEDITION", "captures": \[("EZHOU", "QI")\], "huangchao\_stage": "S3\_CHONGTIAN", "sprite\_frames": \[2, 3\], "portrait\_mode": "map\_leader", "headline": "采石矶北渡长江、三江口跨淮水，六十万大军直扑两京", "subtitle": "万里大迂回闭环完成，淮南高骈闭壁不敢出战，关东藩镇望风瓦解。"},  
{"event\_id": "T10", "date": "0880-11-17", "date\_precision": "day", "era\_title": "广明元年十一月 · 洛阳迎降", "camera": "macro", "focus\_city": "LUOYANG", "route\_id": "R04\_CAPTURE\_TWO\_CAPITALS", "captures": \[("LUOYANG", "QI")\], "huangchao\_stage": "S3\_CHONGTIAN", "sprite\_frames": \[0, 1\], "portrait\_mode": "pip\_corner", "headline": "东都洛阳不战而下，留守刘允章率百官出城迎降", "subtitle": "齐军纪律严明、秋毫无犯，兵锋直指关中最后一道天险——潼关。"},  
{"event\_id": "T11", "date": "0880-12-03", "date\_precision": "day", "era\_title": "广明元年十二月 · 攻破潼关", "camera": "micro", "focus\_city": "TONGGUAN", "route\_id": "R04\_CAPTURE\_TWO\_CAPITALS", "captures": \[("TONGGUAN", "QI")\], "huangchao\_stage": "S3\_CHONGTIAN", "sprite\_frames": \[2, 3\], "portrait\_mode": "pip\_corner", "headline": "双路夹击破潼关！唐僖宗仓皇逃往蜀地成都", "subtitle": "尚让正面强攻、林言绕禁谷奇袭，天险潼关一日而破。"},  
{"event\_id": "T12", "date": "0881-01-16", "date\_precision": "day", "era\_title": "金统元年正月 · 含元殿称帝", "camera": "ai\_clip", "focus\_city": "CHANGAN", "route\_id": "R04\_CAPTURE\_TWO\_CAPITALS", "captures": \[("CHANGAN", "QI"), ("TONGZHOU", "QI")\], "huangchao\_stage": "S4\_EMPEROR", "sprite\_frames": \[0, 1, 2\], "portrait\_mode": "full\_panel", "headline": "金冕龙袍登含元殿！建国号"大齐"，年号金统", "subtitle": "昔日长安落第举子终登九五，树起明黄赤龙大齐帅旗。"},  
{"event\_id": "T13", "date": "0882-09-15", "date\_precision": "month", "era\_title": "中和二年秋 · 朱温叛降与孤城", "camera": "macro", "focus\_city": "TONGZHOU", "route\_id": "R04\_CAPTURE\_TWO\_CAPITALS", "captures": \[("TONGZHOU", "TANG")\], "huangchao\_stage": "S4\_EMPEROR", "sprite\_frames": \[3\], "portrait\_mode": "pip\_corner", "headline": "大将朱温据同州降唐，长安粮道断绝陷入四面合围", "subtitle": "政令不出长安城门，大齐帝国迅速由盛转衰，孤城危机四伏。"},  
{"event\_id": "T14", "date": "0883-04-10", "date\_precision": "day", "era\_title": "中和三年四月 · 梁田坡败绩", "camera": "micro", "focus\_city": "LIANGTIANPO", "route\_id": "R05\_RETREAT\_TO\_LANGHUGU", "captures": \[("CHANGAN", "TANG"), ("TONGGUAN", "TANG"), ("LUOYANG", "TANG")\], "huangchao\_stage": "S5\_LANGHUGU", "sprite\_frames": \[0\], "portrait\_mode": "pip\_corner", "headline": "二十八岁李克用率沙陀"鸦儿军"入关，黄巢败退撤出长安", "subtitle": "黑衣骑兵突袭梁田坡，黄巢焚宫室东出潼关，帝业倾颓。"},  
{"event\_id": "T15", "date": "0884-05-18", "date\_precision": "day", "era\_title": "中和四年五月 · 王满渡溃败", "camera": "micro", "focus\_city": "WANGMANDU", "route\_id": "R05\_RETREAT\_TO\_LANGHUGU", "captures": \[\], "huangchao\_stage": "S5\_LANGHUGU", "sprite\_frames": \[0, 1\], "portrait\_mode": "pip\_corner", "headline": "围陈州三百日无果，王满渡遭李克用半渡而击全军瓦解", "subtitle": "尚让等核心大将相继降唐，黄巢仅率千余残骑向泰山突围。"},  
{"event\_id": "T16", "date": "0884-07-13", "date\_precision": "day", "era\_title": "中和四年六月 · 狼虎谷落幕", "camera": "portrait\_pip", "focus\_city": "LANGHUGU", "route\_id": "R05\_RETREAT\_TO\_LANGHUGU", "captures": \[("YUANQU", "TANG"), ("CHANGYUAN", "TANG"), ("QIZHOU", "TANG"), ("HUANGMEI", "TANG"), ("XUANZHOU", "TANG"), ("QUZHOU", "TANG"), ("JIANZHOU", "TANG"), ("FUZHOU", "TANG"), ("CHAOZHOU", "TANG"), ("GUANGZHOU", "TANG"), ("GUIZHOU", "TANG"), ("TANZHOU", "TANG"), ("JIANGLING", "TANG"), ("EZHOU", "TANG")\], "huangchao\_stage": "S5\_LANGHUGU", "sprite\_frames": \[1, 2, 3\], "portrait\_mode": "full\_panel", "headline": "泰山狼虎谷横剑自刎，明黄大齐帅旗折断", "subtitle": "历经十年万里转战，黄巢于泰山深谷悲壮自刎，大唐帝国亦随之名存实亡。"},  
\]

````

---

## 五、 强校验与快照编译器

自动验证空间边界、渡口引用、时间单调递增与控制权真实翻转，输出编译后的结构化推演档案：`data/huangchao_wargame.json`。

### 5.1 编译器源码 (`src/build.py`)

```python
import json
import math
from datetime import date
from pathlib import Path
from data_geo import LAT_BOUNDS, LON_BOUNDS, FACTIONS, CITIES
from data_routes import MARCH_ROUTES
from data_timeline import TIMELINE_EVENTS

VALID_STAGES = {"S1_SCHOLAR", "S2_REBEL", "S3_CHONGTIAN", "S4_EMPEROR", "S5_LANGHUGU"}

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

def validate_and_compile(out_dir: Path) -> dict:
    for cid, c in CITIES.items():
        lat, lon = c["lat"], c["lon"]
        assert LAT_BOUNDS[0] < lat < LAT_BOUNDS[1], f"{cid} 纬度越界: {lat}"
        assert LON_BOUNDS[0] < lon < LON_BOUNDS[1], f"{cid} 经度越界: {lon}"
        assert c["init_faction"] in FACTIONS, f"{cid} 未知初始阵营: {c['init_faction']}"

    route_ids = set()
    total_march_km = 0.0
    compiled_routes = []
    for rt in MARCH_ROUTES:
        rid = rt["route_id"]
        assert rid not in route_ids, f"重复路线 ID: {rid}"
        route_ids.add(rid)
        assert rt["stage_key"] in VALID_STAGES, f"{rid} 未知主角阶段: {rt['stage_key']}"
        for cid in rt["city_sequence"]:
            assert cid in CITIES, f"{rid} 引用未知城池: {cid}"
        pts = rt["waypoints"]
        dist = sum(haversine_km(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]) for i in range(len(pts) - 1))
        total_march_km += dist
        compiled_routes.append({**rt, "distance_km": round(dist, 1)})

    state = {cid: c["init_faction"] for cid, c in CITIES.items()}
    start_d = date.fromisoformat(TIMELINE_EVENTS[0]["date"])
    prev_d = None
    snapshots = []
    total_captures = 0

    for ev in TIMELINE_EVENTS:
        cur_d = date.fromisoformat(ev["date"])
        if prev_d is not None:
            assert cur_d >= prev_d, f"时间倒流: {ev['event_id']}"
        prev_d = cur_d
        assert ev["focus_city"] in CITIES
        if ev["route_id"] is not None:
            assert ev["route_id"] in route_ids
        assert ev["huangchao_stage"] in VALID_STAGES

        transitions = []
        for cid, to_f in ev["captures"]:
            from_f = state[cid]
            assert from_f != to_f, f"{ev['event_id']} 城池 {cid} 控制权未发生真实变化"
            state[cid] = to_f
            total_captures += 1
            transitions.append({"city_id": cid, "from_faction": from_f, "to_faction": to_f})

        snapshots.append({**ev, "day_offset": (cur_d - start_d).days, "transitions": transitions, "city_control": dict(state)})

    out_dir.mkdir(parents=True, exist_ok=True)
    wargame_payload = {
        "project": "唐末黄巢起义 (874-884)",
        "span_days": (prev_d - start_d).days,
        "city_count": len(CITIES),
        "route_count": len(compiled_routes),
        "total_march_km": round(total_march_km, 1),
        "event_count": len(snapshots),
        "capture_count": total_captures,
        "factions": FACTIONS,
        "cities": CITIES,
        "routes": compiled_routes,
        "timeline": snapshots,
    }
    (out_dir / "huangchao_wargame.json").write_text(json.dumps(wargame_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return wargame_payload

if __name__ == "__main__":
    result = validate_and_compile(Path("./data"))
    print(f"数据模块编译成功！共处理 {result['city_count']} 个节点，{result['event_count']} 帧时间轴，累计行军 {result['total_march_km']} km。")
````

