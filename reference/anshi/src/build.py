# -*- coding: utf-8 -*-
"""构建脚本：校验数据 → 生成 CSV / JSON / GeoJSON。
用法：python src/build.py   （输出到 data/）
"""
import csv, json, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from data_geo import FACTIONS, CITIES, ROUTES, RIVERS
from data_units import UNITS, RETIRED
from data_battles import BATTLES
from data_timeline import EVENTS, CONTROL_CHANGES, RULERS

OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)
EPOCH = date(755, 12, 16)  # 起兵日 = day 0
PHASES = {1: "叛军攻势与两京沦陷", 2: "战略相持与收复两京", 3: "邺城大战与史思明复叛", 4: "战略反攻与叛乱平定"}

def d(s):
    y, m, dd = map(int, s.split("-"))
    return date(y, m, dd)

def offset(s):
    return (d(s) - EPOCH).days

errors = []
def check(cond, msg):
    if not cond:
        errors.append(msg)

# ---------- 规范化 ----------
factions = [dict(faction_id=f[0], name_zh=f[1], color=f[2], accent=f[3], note=f[4]) for f in FACTIONS]
fac_ids = {f["faction_id"] for f in factions}
cities = [dict(city_id=c[0], name_zh=c[1], tang_name=c[2], modern_location=c[3], lat=c[4], lon=c[5],
               site_type=c[6], importance=c[7], initial_control=c[8] or "", control_tracked=c[9],
               coord_confidence=c[10]) for c in CITIES]
city = {c["city_id"]: c for c in cities}
units = [dict(unit_id=u[0], name_zh=u[1], faction=u[2], commanders=u[3], unit_type=u[4],
              initial_strength=u[5], strength_basis=u[6], note=u[7], retired_date=RETIRED.get(u[0], "")) for u in UNITS]
unit = {u["unit_id"]: u for u in units}
battle = {b["battle_id"]: b for b in BATTLES}

check(len(BATTLES) == 21, f"战役数应为21，实为{len(BATTLES)}")
check(len(city) == len(cities), "城池ID重复")
for c in cities:
    check(29 < c["lat"] < 42 and 103 < c["lon"] < 120, f"坐标越界 {c['city_id']}")
    if c["control_tracked"]:
        check(c["initial_control"] in fac_ids, f"初始控制缺失 {c['city_id']}")
for u in units:
    check(u["faction"] in fac_ids, f"单位阵营错误 {u['unit_id']}")
for r in ROUTES:
    for cid in r[3]:
        check(cid in city, f"路线{r[0]}引用未知地点 {cid}")

# ---------- 战役 ----------
battles_out = []
for b in BATTLES:
    loc = city.get(b["location_id"])
    check(loc is not None, f"{b['battle_id']} 地点未知")
    check(b["start_date"] <= b["end_date"], f"{b['battle_id']} 起止日期颠倒")
    for uid in filter(None, (b["tang_units"] + ";" + b["enemy_units"]).split(";")):
        check(uid in unit, f"{b['battle_id']} 引用未知单位 {uid}")
    row = dict(b)
    row.update(phase_name=PHASES[b["phase"]], location_name=loc["name_zh"] if loc else "",
               lat=loc["lat"] if loc else None, lon=loc["lon"] if loc else None,
               start_offset_days=offset(b["start_date"]), end_offset_days=offset(b["end_date"]),
               duration_days=offset(b["end_date"]) - offset(b["start_date"]) + 1)
    battles_out.append(row)

# ---------- 事件 ----------
events = sorted(EVENTS, key=lambda e: e["date"])  # 稳定排序，同日保持书写顺序
events_out = []
for i, e in enumerate(events, 1):
    for k in ("from_id", "to_id"):
        check(e[k] in city, f"事件 {e['date']} {k} 未知 {e[k]}")
    if e["battle_id"]:
        check(e["battle_id"] in battle, f"事件 {e['date']} 战役未知 {e['battle_id']}")
    uids = [u for u in (e["unit_ids"] or "").split(";") if u]
    for uid in uids:
        check(uid in unit, f"事件 {e['date']} 单位未知 {uid}")
    f, t = city[e["from_id"]], city[e["to_id"]]
    row = dict(tick_id=f"T{i:03d}", **e)
    row.update(day_offset=offset(e["date"]), phase_name=PHASES[e["phase"]],
               primary_unit=uids[0] if uids else "",
               primary_faction=unit[uids[0]]["faction"] if uids else "",
               from_lat=f["lat"], from_lon=f["lon"], to_lat=t["lat"], to_lon=t["lon"],
               battle_name=battle[e["battle_id"]]["name_zh"] if e["battle_id"] else "")
    events_out.append(row)
for a, b2 in zip(events_out, events_out[1:]):
    check(a["date"] <= b2["date"], "事件日期未排序")

# ---------- 控制权变更（自动推算 from_faction） ----------
state = {c["city_id"]: c["initial_control"] for c in cities if c["control_tracked"]}
changes_out = []
for n, (dt, prec, cid, to, cause, bid) in enumerate(sorted(CONTROL_CHANGES, key=lambda x: x[0]), 1):
    check(cid in state, f"控制变更引用未跟踪地点 {cid}")
    check(to in fac_ids, f"控制变更阵营错误 {to}")
    frm = state.get(cid, "")
    check(frm != to, f"{dt} {cid} 控制方未变化（{frm}→{to}）")
    state[cid] = to
    changes_out.append(dict(change_id=f"C{n:03d}", date=dt, date_precision=prec, day_offset=offset(dt),
                            city_id=cid, city_name=city[cid]["name_zh"], from_faction=frm,
                            to_faction=to, cause=cause, battle_id=bid or ""))

# ---------- 每帧控制快照（供动画直接读取） ----------
snapshots, st, ci = [], {c["city_id"]: c["initial_control"] for c in cities if c["control_tracked"]}, 0
for ev in events_out:
    while ci < len(changes_out) and changes_out[ci]["date"] <= ev["date"]:
        st[changes_out[ci]["city_id"]] = changes_out[ci]["to_faction"]; ci += 1
    counts = {f: 0 for f in fac_ids}
    for v in st.values(): counts[v] += 1
    snapshots.append(dict(tick_id=ev["tick_id"], date=ev["date"], control=dict(st), city_count=counts))

rulers_out = [dict(side=r[0], ruler=r[1], start=r[2], end=r[3], note=r[4]) for r in RULERS]
routes_out = [dict(route_id=r[0], name_zh=r[1], route_type=r[2], waypoints=";".join(r[3]), note=r[4]) for r in ROUTES]

if errors:
    print("校验失败：\n  " + "\n  ".join(errors)); sys.exit(1)

# ---------- 输出 ----------
def write_csv(name, rows):
    with open(OUT / name, "w", newline="", encoding="utf-8-sig") as fp:  # BOM 让 Excel 正确识别中文
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})

write_csv("factions.csv", factions)
write_csv("cities.csv", cities)
write_csv("routes.csv", routes_out)
write_csv("units.csv", units)
write_csv("battles.csv", battles_out)
write_csv("events.csv", events_out)
write_csv("control_changes.csv", changes_out)
write_csv("rulers.csv", rulers_out)

bundle = dict(
    meta=dict(title="安史之乱兵棋推演时间轴数据", version="1.0", epoch="0755-12-16",
              calendar="儒略历（历史学惯例换算），日期均为 ISO 8601 四位年",
              end="0763-02-17", total_days=offset("0763-02-17"), phases=PHASES,
              notes="兵力为史载/号称/推估，见 strength_basis；date_precision 与 confidence 字段标明可信度"),
    factions=factions, cities=cities, routes=routes_out,
    rivers=[dict(river_id=r[0], name_zh=r[1], coords=r[2], confidence=r[3]) for r in RIVERS],
    rulers=rulers_out, units=units, battles=battles_out, events=events_out,
    control_changes=changes_out, snapshots=snapshots)
(OUT / "anshi_wargame.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")

# GeoJSON（可直接拖入 QGIS / Mapbox / kepler.gl）
feats = [dict(type="Feature", geometry=dict(type="Point", coordinates=[c["lon"], c["lat"]]),
              properties={k: v for k, v in c.items() if k not in ("lat", "lon")}) for c in cities]
for r in ROUTES:
    feats.append(dict(type="Feature", geometry=dict(type="LineString",
                      coordinates=[[city[x]["lon"], city[x]["lat"]] for x in r[3]]),
                      properties=dict(route_id=r[0], name_zh=r[1], route_type=r[2], note=r[4])))
for r in RIVERS:
    feats.append(dict(type="Feature", geometry=dict(type="LineString", coordinates=[[lo, la] for la, lo in r[2]]),
                      properties=dict(river_id=r[0], name_zh=r[1], confidence=r[3])))
for b in battles_out:
    feats.append(dict(type="Feature", geometry=dict(type="Point", coordinates=[b["lon"], b["lat"]]),
                      properties=dict(battle_id=b["battle_id"], name_zh=b["name_zh"], start=b["start_date"],
                                      end=b["end_date"], winner=b["winner_faction"], layer="battle")))
(OUT / "anshi_map.geojson").write_text(json.dumps(dict(type="FeatureCollection", features=feats),
                                                  ensure_ascii=False, indent=1), encoding="utf-8")

print(f"OK: {len(factions)} 阵营 / {len(cities)} 地点 / {len(routes_out)} 通道 / {len(units)} 算子 / "
      f"{len(battles_out)} 战役 / {len(events_out)} 事件帧 / {len(changes_out)} 控制变更 / 总跨度 {bundle['meta']['total_days']} 天")
print("终局控制统计:", snapshots[-1]["city_count"])
