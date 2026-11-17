# -*- coding: utf-8 -*-
"""兵棋算子（部队）定义。
unit_type: cavalry 骑兵 / infantry 步兵 / mixed 步骑混编 / levy 新募兵 / militia 义军团练 / heavy_inf 陌刀重步
strength 为该算子首次登场时的兵力（人），basis: recorded 史载 / claimed 号称 / estimated 推估
"""

# id, 名称, 阵营, 主将, 兵种, 初始兵力, 兵力依据, 说明
UNITS = [
    ("U_AN_MAIN", "安禄山南下主力", "YAN_AN", "安禄山", "mixed", 150000, "recorded", "同罗、奚、契丹、室韦及三镇精兵，号称二十万"),
    ("U_SHI_SM", "史思明河北军", "YAN_AN", "史思明、蔡希德", "cavalry", 30000, "estimated", "回镇河北、平定颜氏起义的机动兵团"),
    ("U_CUI_QY", "崔乾祐陕郡军", "YAN_AN", "崔乾祐", "mixed", 20000, "estimated", "灵宝前出部队史载不满万人，伏兵与后续兵力不详"),
    ("U_LINGHU", "令狐潮部", "YAN_AN", "令狐潮、李庭望、杨朝宗", "mixed", 40000, "recorded", "进攻雍丘、宁陵"),
    ("U_WU_LX", "武令珣南阳兵团", "YAN_AN", "武令珣、田承嗣、阿史那承庆", "mixed", 30000, "estimated", "南下江汉方向"),
    ("U_AN_SZ", "安守忠长安驻军", "YAN_AN", "安守忠、李归仁、张通儒", "cavalry", 100000, "recorded", "香积寺战前约十万"),
    ("U_YIN_ZQ", "尹子奇睢阳兵团", "YAN_AN", "尹子奇", "mixed", 130000, "recorded", "进攻睢阳"),
    ("U_TY_SIEGE", "太原围城军", "YAN_AN", "史思明、蔡希德、高秀岩、牛廷玠", "mixed", 100000, "recorded", "四路合围太原"),
    ("U_YAN_ZHUANG", "严庄洛阳军", "YAN_AN", "严庄、张通儒", "mixed", 150000, "recorded", "新店之战倾洛阳之众"),
    ("U_AN_QX", "安庆绪邺城残部", "YAN_AN", "安庆绪", "mixed", 60000, "estimated", "北逃邺城后收拾残兵"),
    ("U_SHI_ARMY", "史思明大燕主力", "YAN_SHI", "史思明", "cavalry", 130000, "recorded", "救邺时号十三万，精选五万南下"),
    ("U_SHI_CY", "史朝义大燕军", "YAN_SHI", "史朝义", "mixed", 100000, "recorded", "昭觉寺战前约十万"),
    ("U_FENG", "封常清洛阳新募军", "TANG", "封常清", "levy", 60000, "recorded", "十日内招募的市井子弟"),
    ("U_GAO", "高仙芝陕郡军", "TANG", "高仙芝", "mixed", 50000, "recorded", "飞骑、彍骑及新募兵"),
    ("U_GESHU", "哥舒翰潼关军", "TANG", "哥舒翰", "mixed", 200000, "claimed", "号二十万，实际约十八万"),
    ("U_YAN_GQ", "颜杲卿常山义军", "TANG", "颜杲卿、袁履谦", "militia", 5000, "estimated", "守兵寡少，未经训练"),
    ("U_YAN_ZQ", "颜真卿平原义军", "TANG", "颜真卿", "militia", 10000, "estimated", "河北起义盟主"),
    ("U_LGB", "李光弼河东/朔方军", "TANG", "李光弼", "mixed", 10000, "recorded", "出井陉时朔方兵五千、太原弩手三千等"),
    ("U_GZY", "郭子仪朔方军", "TANG", "郭子仪", "mixed", 100000, "claimed", "与李光弼会师后合兵十余万"),
    ("U_LUJ", "鲁炅南阳军", "TANG", "鲁炅", "mixed", 50000, "recorded", "滍水战前约五万（岭南、黔中、山南兵）"),
    ("U_ZX", "张巡部", "TANG", "张巡、雷万春、南霁云", "infantry", 2000, "estimated", "雍丘时约二三千人"),
    ("U_FANG", "房琯三路军", "TANG", "房琯", "mixed", 50000, "estimated", "分南中北三军，以牛车两千乘为前驱"),
    ("U_SY", "睢阳守军", "TANG", "张巡、许远", "infantry", 6800, "recorded", "张巡三千余人与许远所部合兵"),
    ("U_YUANSHUAI", "广平王元帅府联军", "TANG", "李俶、郭子仪、李嗣业、王思礼、仆固怀恩", "mixed", 150000, "recorded", "号二十万；含李嗣业陌刀军"),
    ("U_UYGHUR_757", "回纥叶护精骑", "UYGHUR", "叶护太子", "cavalry", 4000, "recorded", ""),
    ("U_NINE", "九节度使联军", "TANG", "郭子仪、李光弼等九节度使，鱼朝恩观军容", "mixed", 600000, "claimed", "史载步骑六十万，不立元帅"),
    ("U_PGHE", "仆固怀恩反攻兵团", "TANG", "雍王李适（元帅）、仆固怀恩、仆固瑒", "mixed", 100000, "estimated", "朔方、河东、镇西北庭、泽潞等军"),
    ("U_MALIN", "镇西北庭行营", "TANG", "马璘", "heavy_inf", 3000, "estimated", "昭觉寺破栅先锋"),
    ("U_UYGHUR_762", "回纥登里可汗军", "UYGHUR", "登里可汗", "cavalry", 40000, "estimated", ""),
    ("U_FZ_XUESONG", "薛嵩（相卫）", "FANZHEN", "薛嵩", "mixed", None, "", "762年降唐"),
    ("U_FZ_ZHANGZZ", "张忠志/李宝臣（成德）", "FANZHEN", "张忠志", "mixed", None, "", "762年降唐，赐名李宝臣"),
    ("U_FZ_TIANCS", "田承嗣（魏博）", "FANZHEN", "田承嗣", "mixed", None, "", "763年莫州献城降唐"),
    ("U_FZ_LIHX", "李怀仙（幽州）", "FANZHEN", "李怀仙", "mixed", None, "", "763年范阳降唐"),
]

# 算子退场日期（覆灭/主将死/并入他部），动画在此日后不再显示该算子
RETIRED = {
    "U_FENG": "0756-01-24", "U_GAO": "0756-01-24", "U_YAN_GQ": "0756-02-12", "U_SHI_SM": "0757-02-01",
    "U_CUI_QY": "0756-07-20", "U_GESHU": "0756-07-10", "U_YAN_ZQ": "0756-11-20", "U_FANG": "0756-11-19",
    "U_AN_MAIN": "0757-01-29", "U_ZX": "0757-02-10", "U_LINGHU": "0757-02-10", "U_TY_SIEGE": "0757-03-10",
    "U_LUJ": "0757-06-10", "U_WU_LX": "0757-06-10", "U_GZY": "0757-10-25", "U_AN_SZ": "0757-11-14", "U_SY": "0757-11-24",
    "U_YIN_ZQ": "0757-12-03", "U_YAN_ZHUANG": "0757-12-03", "U_UYGHUR_757": "0758-01-15",
    "U_NINE": "0759-04-07", "U_AN_QX": "0759-04-14", "U_SHI_ARMY": "0761-04-18",
    "U_SHI_CY": "0763-02-17", "U_PGHE": "0763-02-17", "U_MALIN": "0763-02-17", "U_UYGHUR_762": "0763-02-17",
}
