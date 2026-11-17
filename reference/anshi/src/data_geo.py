# -*- coding: utf-8 -*-
"""地理与阵营基础数据：阵营、城池/地点、战略通道、古黄河示意线。
坐标为今地近似位置（WGS84，十进制度），coord_confidence: high/medium/low。
"""

FACTIONS = [
    # id, 名称, 主色, 辅色, 说明
    ("TANG", "唐朝官军", "#C0392B", "#F5B041", "唐中央及各节度使官军"),
    ("YAN_AN", "安氏大燕", "#6C3483", "#D2B4DE", "安禄山、安庆绪政权（755-759）"),
    ("YAN_SHI", "史氏大燕", "#2C3E50", "#85929E", "史思明集团（758复叛起）、史朝义政权（759-763）"),
    ("UYGHUR", "回纥援军", "#148F77", "#A3E4D7", "回纥叶护（757）、登里可汗（762）所部"),
    ("FANZHEN", "降唐河朔藩镇", "#D35400", "#6C3483", "762-763年降唐的燕将，名义归唐、实则割据；建议红底紫边"),
]

# id, 地名, 唐代名称/建置, 今地, lat, lon, 类型, 重要度1-5, 初始控制(755-12-15), 是否计入控制区, 坐标可信度
CITIES = [
    ("FANYANG", "范阳", "幽州范阳郡", "北京市西南", 39.88, 116.35, "city", 5, "YAN_AN", True, "high"),
    ("CHANGAN", "长安", "西京京兆府", "陕西西安", 34.27, 108.93, "capital", 5, "TANG", True, "high"),
    ("LUOYANG", "洛阳", "东京河南府", "河南洛阳", 34.67, 112.44, "capital", 5, "TANG", True, "high"),
    ("TAIYUAN", "太原", "北都太原府", "山西太原晋源区（晋阳古城）", 37.70, 112.47, "capital", 5, "TANG", True, "high"),
    ("TONGGUAN", "潼关", "华州潼关", "陕西潼关县港口镇", 34.60, 110.30, "pass", 5, "TANG", True, "high"),
    ("SHANZHOU", "陕州", "陕郡", "河南三门峡陕州区", 34.78, 111.19, "city", 4, "TANG", True, "high"),
    ("LINGBAO", "灵宝西原", "虢州灵宝县西", "河南灵宝市西", 34.56, 110.75, "battlefield", 4, None, False, "medium"),
    ("LINGCHANG", "灵昌津", "滑州灵昌县", "河南滑县西南", 35.45, 114.45, "ford", 3, None, False, "medium"),
    ("HUAZHOU", "滑州", "滑州灵昌郡", "河南滑县", 35.58, 114.52, "city", 3, "TANG", True, "medium"),
    ("BIANZHOU", "汴州", "陈留郡（治浚仪）", "河南开封", 34.80, 114.35, "city", 4, "TANG", True, "high"),
    ("ZHENGZHOU", "郑州", "荥阳郡（治管城）", "河南郑州", 34.75, 113.65, "city", 3, "TANG", True, "high"),
    ("HULAO", "虎牢关", "郑州汜水县（武牢）", "河南荥阳汜水镇", 34.85, 113.22, "pass", 4, "TANG", True, "high"),
    ("HEYANG", "河阳三城", "孟州河阳县", "河南孟州市南黄河岸", 34.87, 112.79, "fortress", 5, "TANG", True, "medium"),
    ("HUAIZHOU", "怀州", "河内郡", "河南沁阳", 35.09, 112.94, "city", 3, "TANG", True, "high"),
    ("MANGSHAN", "邙山", "洛阳北邙", "河南洛阳北", 34.76, 112.50, "battlefield", 3, None, False, "medium"),
    ("PINGYUAN", "平原", "德州平原郡", "山东德州陵城区", 37.33, 116.58, "city", 3, "TANG", True, "high"),
    ("CHANGSHAN", "常山", "恒州常山郡", "河北正定", 38.15, 114.57, "city", 5, "TANG", True, "high"),
    ("TUMEN", "土门（井陉口）", "恒州井陉土门关", "河北鹿泉", 38.08, 114.25, "pass", 4, "TANG", True, "high"),
    ("JIUMEN", "九门", "恒州九门县", "河北藁城西北", 38.10, 114.78, "battlefield", 2, None, False, "medium"),
    ("JIASHAN", "嘉山", "定州曲阳县东", "河北曲阳县东", 38.60, 114.78, "battlefield", 4, None, False, "low"),
    ("BOLING", "博陵", "定州博陵郡", "河北定州", 38.52, 115.00, "city", 3, "TANG", True, "high"),
    ("ZHAOJUN", "赵郡", "赵州", "河北赵县", 37.75, 114.78, "city", 3, "TANG", True, "high"),
    ("NANYANG", "南阳", "邓州南阳县", "河南南阳", 33.00, 112.53, "city", 4, "TANG", True, "high"),
    ("ZHISHUI", "滍水", "汝州叶县滍水", "河南叶县", 33.62, 113.35, "battlefield", 2, None, False, "medium"),
    ("XIANGYANG", "襄阳", "襄州", "湖北襄阳", 32.01, 112.14, "city", 3, "TANG", True, "high"),
    ("YONGQIU", "雍丘", "汴州雍丘县", "河南杞县", 34.55, 114.78, "city", 3, "TANG", True, "high"),
    ("NINGLING", "宁陵", "宋州宁陵县", "河南宁陵", 34.45, 115.31, "city", 2, "TANG", True, "high"),
    ("SUIYANG", "睢阳", "宋州睢阳郡", "河南商丘睢阳区", 34.38, 115.62, "city", 5, "TANG", True, "high"),
    ("LINHUAI", "临淮", "泗州临淮郡", "江苏盱眙北（泗州古城）", 33.03, 118.52, "city", 3, "TANG", True, "medium"),
    ("XUZHOU", "徐州", "彭城郡", "江苏徐州", 34.26, 117.18, "city", 3, "TANG", True, "high"),
    ("CHENTAOXIE", "陈涛斜", "咸阳县东", "陕西咸阳东", 34.36, 108.80, "battlefield", 3, None, False, "low"),
    ("FENGXIANG", "凤翔", "凤翔府（扶风郡）", "陕西凤翔", 34.52, 107.39, "city", 4, "TANG", True, "high"),
    ("LINGWU", "灵武", "灵州灵武郡", "宁夏灵武", 38.10, 106.33, "city", 4, "TANG", True, "medium"),
    ("MAWEI", "马嵬驿", "京兆府兴平县", "陕西兴平西", 34.29, 108.37, "station", 3, None, False, "high"),
    ("CHENGDU", "成都", "蜀郡", "四川成都", 30.66, 104.06, "city", 3, "TANG", True, "high"),
    ("WUGONG", "武功", "京兆府武功县", "陕西武功", 34.26, 108.20, "city", 2, "TANG", True, "high"),
    ("QINGQU", "清渠", "长安城西", "陕西西安西", 34.28, 108.82, "battlefield", 2, None, False, "low"),
    ("XIANGJI", "香积寺", "长安城南", "陕西西安长安区", 34.21, 108.84, "temple", 4, None, False, "high"),
    ("XINDIAN", "新店", "陕州附近", "河南三门峡附近", 34.73, 111.10, "battlefield", 3, None, False, "low"),
    ("XIANGZHOU", "相州（邺城）", "相州邺郡（治安阳）", "河南安阳", 36.10, 114.35, "city", 5, "TANG", True, "high"),
    ("CHOUSIGANG", "愁思冈", "相州安阳县西南", "河南安阳西南", 36.03, 114.28, "battlefield", 2, None, False, "low"),
    ("WEIZHOU_DM", "魏州", "魏州魏郡", "河北大名", 36.28, 115.15, "city", 4, "TANG", True, "high"),
    ("WEIZHOU_WH", "卫州", "卫州汲郡", "河南卫辉", 35.40, 114.07, "city", 3, "TANG", True, "high"),
    ("WENXI", "闻喜", "绛州闻喜县", "山西闻喜", 35.36, 111.22, "city", 2, "TANG", True, "high"),
    ("LIUQUAN", "柳泉驿", "陕州—渑池间", "河南渑池以西（位置存疑）", 34.75, 111.55, "station", 2, None, False, "low"),
    ("ZHAOJUE", "昭觉寺", "洛阳北郊", "河南洛阳北郊（位置存疑）", 34.72, 112.46, "temple", 3, None, False, "low"),
    ("BEIZHOU", "贝州", "清河郡", "河北清河", 37.05, 115.67, "city", 3, "TANG", True, "high"),
    ("XIABO", "下博", "深州下博县", "河北深州东南", 37.93, 115.68, "battlefield", 3, None, False, "medium"),
    ("MOZHOU", "莫州", "莫州文安郡", "河北任丘北莫州镇", 38.82, 116.13, "city", 4, "TANG", True, "medium"),
    ("WENQUANZHA", "温泉栅", "范阳以东", "河北卢龙一带（位置存疑）", 39.95, 118.85, "battlefield", 2, None, False, "low"),
]

# 战略通道：id, 名称, 类型, 依次经过的地点id, 说明
ROUTES = [
    ("R01", "崤函通道", "road", ["CHANGAN", "TONGGUAN", "LINGBAO", "SHANZHOU", "XINDIAN", "LUOYANG"], "东西大动脉，两京生命线"),
    ("R02", "河阳—怀州道", "road", ["LUOYANG", "MANGSHAN", "HEYANG", "HUAIZHOU"], "洛阳北渡黄河要道"),
    ("R03", "井陉道", "pass_road", ["TAIYUAN", "TUMEN", "CHANGSHAN"], "太行八陉之一，唐军出击河北的通道"),
    ("R04", "通济渠（汴河）漕运线", "canal", ["LUOYANG", "HULAO", "ZHENGZHOU", "BIANZHOU", "YONGQIU", "NINGLING", "SUIYANG", "XUZHOU", "LINHUAI"], "江淮财赋入京生命线（徐州为近似陆路连接）"),
    ("R05", "河北太行东麓驿道", "road", ["FANYANG", "BOLING", "CHANGSHAN", "ZHAOJUN", "XIANGZHOU", "WEIZHOU_WH", "LINGCHANG"], "安禄山南下主轴"),
    ("R06", "河北东路", "road", ["FANYANG", "MOZHOU", "XIABO", "BEIZHOU", "WEIZHOU_DM", "HUAZHOU"], "762年唐军北追路线"),
    ("R07", "灵武—凤翔—长安道", "road", ["LINGWU", "FENGXIANG", "WUGONG", "CHANGAN"], "肃宗行在与反攻出发线（示意）"),
    ("R08", "入蜀道", "road", ["CHANGAN", "MAWEI", "CHENGDU"], "玄宗幸蜀路线（示意，未绘出秦岭栈道细节）"),
    ("R09", "宛洛—汉水道", "road", ["LUOYANG", "ZHISHUI", "NANYANG", "XIANGYANG"], "叛军南下江汉企图的路线"),
]

# 唐代黄河下游示意线（低精度，仅供动画底图参考，正式制图请以谭其骧《中国历史地图集》第五册校准）
RIVERS = [
    ("HUANGHE_TANG", "唐代黄河（示意）", [
        (34.80, 110.30), (34.75, 111.20), (34.88, 112.10), (34.86, 112.79), (34.92, 113.40),
        (35.15, 114.00), (35.50, 114.50), (35.90, 114.95), (36.30, 115.40), (36.90, 115.90),
        (37.45, 116.40), (37.95, 116.85), (38.35, 117.30), (38.50, 117.70)], "low"),
]
