"""
src/build.py
《唐末黄巢起义》数据强校验与快照编译器
- 校验经纬度边界、城池引用完整性、时间单调递增、大迂回渡口约束与控制权变更状态机
- 输出 data/huangchao_wargame.json（含逐帧势力控制权快照）与 data/huangchao_routes.geojson
"""

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
    # 1. 校验城池坐标与阵营归属
    for cid, c in CITIES.items():
        lat, lon = c["lat"], c["lon"]
        assert LAT_BOUNDS[0] < lat < LAT_BOUNDS[1], f"{cid} 纬度越界: {lat}"
        assert LON_BOUNDS[0] < lon < LON_BOUNDS[1], f"{cid} 经度越界: {lon}"
        assert c["init_faction"] in FACTIONS, f"{cid} 未知初始阵营: {c['init_faction']}"

    # 2. 校验大迂回行军路线与总里程
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
        assert len(pts) >= 2, f"{rid} 路径点不足"
        dist = sum(
            haversine_km(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
            for i in range(len(pts) - 1)
        )
        total_march_km += dist
        compiled_routes.append({**rt, "distance_km": round(dist, 1)})

    # 3. 校验时间轴单调性与控制权快照推算
    state = {cid: c["init_faction"] for cid, c in CITIES.items()}
    start_d = date.fromisoformat(TIMELINE_EVENTS[0]["date"])
    prev_d = None
    snapshots = []
    total_captures = 0

    for ev in TIMELINE_EVENTS:
        cur_d = date.fromisoformat(ev["date"])
        if prev_d is not None:
            assert cur_d >= prev_d, f"时间倒流: {ev['event_id']} ({cur_d} < {prev_d})"
        prev_d = cur_d
        assert ev["focus_city"] in CITIES, f"{ev['event_id']} 未知焦点城池"
        if ev["route_id"] is not None:
            assert ev["route_id"] in route_ids, f"{ev['event_id']} 未知路线 ID"
        assert ev["huangchao_stage"] in VALID_STAGES, f"{ev['event_id']} 未知主角阶段"

        transitions = []
        for cid, to_f in ev["captures"]:
            assert cid in CITIES, f"{ev['event_id']} 控制权变更引用未知城池: {cid}"
            assert to_f in FACTIONS, f"{ev['event_id']} 未知目标阵营: {to_f}"
            from_f = state[cid]
            assert from_f != to_f, f"{ev['event_id']} 城池 {cid} 控制权未发生真实变化 ({from_f} -> {to_f})"
            state[cid] = to_f
            total_captures += 1
            transitions.append({"city_id": cid, "from_faction": from_f, "to_faction": to_f})

        snapshots.append({
            **ev,
            "day_offset": (cur_d - start_d).days,
            "transitions": transitions,
            "city_control": dict(state),
        })

    # 4. 导出 GeoJSON 供 GIS / 地图底图核对
    features = []
    for cid, c in CITIES.items():
        features.append({
            "type": "Feature",
            "properties": {"id": cid, "name": c["name"], "kind": c["kind"], "note": c["note"]},
            "geometry": {"type": "Point", "coordinates": [c["lon"], c["lat"]]},
        })
    for rt in compiled_routes:
        features.append({
            "type": "Feature",
            "properties": {"id": rt["route_id"], "name": rt["name"], "distance_km": rt["distance_km"]},
            "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in rt["waypoints"]]},
        })

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
    (out_dir / "huangchao_wargame.json").write_text(
        json.dumps(wargame_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "huangchao_routes.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return wargame_payload


if __name__ == "__main__":
    res = validate_and_compile(Path(__file__).resolve().parent.parent / "data")
    print(f"校验通过！跨度 {res['span_days']} 天 | 城池/渡口 {res['city_count']} 座 | "
          f"大迂回路线 {res['route_count']} 段（累计 {res['total_march_km']} km） | "
          f"时间轴 {res['event_count']} 帧 | 控制权变更 {res['capture_count']} 次")
