# -*- coding: utf-8 -*-
"""
tools/qa_tools.py
历史兵棋视频工程跨关验收命令行工具（对应 docs/01_pipeline.md 的 G1 / G4 / G6）。

用法示例：
  python tools/qa_tools.py check-control reference/huangchao/data/huangchao_wargame.json
  python tools/qa_tools.py smoke --src-dir reference/huangchao/src --engine hc_campaign_renderer:HuangChaoCampaignEngine --beat-json reference/huangchao/audio/enog_huangchao_beat_map.json
  python tools/qa_tools.py check-lufs path/to/final.mp4
  python tools/qa_tools.py extract-samples path/to/final.mp4 path/to/qa_out --times 10 54 117.2 121.5
"""
from __future__ import annotations

import argparse
import bisect
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg


def cmd_check_control(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
    cities = data.get("cities", {})
    if isinstance(cities, dict):
        init_alt = [
            f"{cid}({c.get('name', cid)}):{c['init_faction']}"
            for cid, c in cities.items()
            if c.get("init_faction") == args.attacker
        ]
    else:
        init_alt = [
            f"{c['city_id']}({c.get('name', c['city_id'])}):{c.get('init_faction')}"
            for c in cities
            if c.get("init_faction") == args.attacker
        ]
    print(f"=== Initial {args.attacker} ({len(init_alt)}) ===")
    print(" ", ", ".join(init_alt) if init_alt else "<none>")

    seq = data.get("timeline") or data.get("snapshots") or []
    for ev in seq:
        eid = ev.get("event_id") or ev.get("tick_id") or "?"
        day = ev.get("day_offset", ev.get("day"))
        when = f"Day {day:4d}" if isinstance(day, int) else str(ev.get("date", "?"))
        ctrl = ev.get("city_control") or ev.get("control") or {}
        held = [cid for cid, fac in ctrl.items() if fac == args.attacker]
        print(f"  {eid:6s} {when:10s} | {args.attacker}={len(held):2d}: {', '.join(held)}")
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    src_dir = Path(args.src_dir).resolve()
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    mod_name, cls_name = args.engine.split(":")
    mod = importlib.import_module(mod_name)
    eng = getattr(mod, cls_name)()

    meta = json.loads(Path(args.beat_json).read_text(encoding="utf-8"))
    acts = meta["acts"]
    out_dir = Path(args.save_dir) if args.save_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    for a in acts:
        for u in (0.15, 0.55, 0.92):
            im = eng.render_at(a["id"], a["mode"], u, 1)
            if out_dir and abs(u - 0.55) < 1e-6:
                p = out_dir / f"smoke_{a['id']}_{a['mode']}.png"
                im.save(p)
    print(f"SMOKE_OK acts={len(acts)} points={len(acts) * 3}")
    return 0


def cmd_check_lufs(args: argparse.Namespace) -> int:
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    target = str(Path(args.media_path))

    info = subprocess.run([ff, "-hide_banner", "-i", target], capture_output=True, text=True).stderr
    for ln in info.splitlines():
        if "Duration:" in ln or "Stream #" in ln:
            print(" ", ln.strip())

    proc = subprocess.run(
        [ff, "-hide_banner", "-i", target, "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    m_i = re.search(r"Integrated loudness:\s*\r?\n\s*I:\s*([-\d.]+)\s*LUFS", proc.stderr)
    m_p = re.search(r"True peak:\s*\r?\n\s*Peak:\s*([-\d.]+)\s*dBFS", proc.stderr)
    lufs = float(m_i.group(1)) if m_i else float("nan")
    tp = float(m_p.group(1)) if m_p else float("nan")
    in_range = -13.1 <= lufs <= -12.7
    print(f"Integrated Loudness: {lufs:.2f} LUFS | True Peak: {tp:.2f} dBFS | Target [-13.1, -12.7]: {'PASS' if in_range else 'OUT_OF_RANGE'}")
    return 0 if in_range else 2


def cmd_extract_samples(args: argparse.Namespace) -> int:
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for ts in args.times:
        tag = str(ts).replace(".", "_")
        dst = out_dir / f"frame_t{tag}s.png"
        subprocess.run(
            [ff, "-y", "-loglevel", "error", "-ss", str(ts), "-i", str(args.mp4_path), "-frames:v", "1", str(dst)],
            check=True,
        )
        print("Saved", dst)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Making-History QA Tools (G1/G4/G6)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ctrl = sub.add_parser("check-control", help="G1: inspect per-event faction city control for lingering territory bugs")
    p_ctrl.add_argument("json_path")
    p_ctrl.add_argument("--attacker", default="QI")
    p_ctrl.set_defaults(func=cmd_check_control)

    p_smk = sub.add_parser("smoke", help="G4: render u=0.15/0.55/0.92 across all acts in beat_map.json")
    p_smk.add_argument("--src-dir", required=True)
    p_smk.add_argument("--engine", default="hc_campaign_renderer:HuangChaoCampaignEngine")
    p_smk.add_argument("--beat-json", required=True)
    p_smk.add_argument("--save-dir", default="")
    p_smk.set_defaults(func=cmd_smoke)

    p_lufs = sub.add_parser("check-lufs", help="G5/G6: measure FFmpeg ebur128 integrated loudness and true peak")
    p_lufs.add_argument("media_path")
    p_lufs.set_defaults(func=cmd_check_lufs)

    p_ext = sub.add_parser("extract-samples", help="G6: extract still frames from final MP4 for visual inspection")
    p_ext.add_argument("mp4_path")
    p_ext.add_argument("out_dir")
    p_ext.add_argument("--times", nargs="+", required=True)
    p_ext.set_defaults(func=cmd_extract_samples)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
