# -*- coding: utf-8 -*-
"""《安史之乱》Amazon BGM 卡点剪辑与混音主流水线（严格遵循三步合拍生成架构）：
1. 读取 extract_amazon_beats.py 由 librosa 提取的卡点/重拍 JSON（output/audio/amazon_beats.json）；
2. 固定步长主循环 `for frame in range(total_frames): t = frame / FPS` 驱动宏观推进、B03 追砍砍杀与镜头转场，
   通过 subprocess.Popen 管道向 FFmpeg stdin 实时喂入 1920×1080 RGB24 字节流；
3. 保留非旋律类战鼓/号角/冰裂/劈砍/倒地/箭雨/火烧/鸣金/溃逃等战争音效并对齐卡点，
   对高响度 (-9 LUFS) 的 Amazon BGM 做电平压低、中频避让与动态侧链闪避（ducking）混流，封装输出
   output/opening_clip_anshi_amazon.mp4。
"""
import json
import subprocess
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image
from scipy.io import wavfile

import imageio_ffmpeg

sys.path.insert(0, str(Path(__file__).parent))
from battle_anim import B03Animator
import render_frame as rf
import sfx_synth as S
from sfx_synth import SR
from tactical_map import FACTION_STYLE, FONT_BOLD, H_PX, W_PX, draw_double_stroked_arrow, px_to_pt, text_outline
from terrain import compose_macro_from_scores, compute_smoothed_faction_scores

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
AUD = OUT / "audio"
BEATS_JSON = AUD / "amazon_beats.json"
FPS = 30


def _ease_io(u):
    u = float(np.clip(u, 0.0, 1.0))
    return u * u * (3.0 - 2.0 * u)


def _new_transparent_fig():
    fig = rf.plt.figure(figsize=(19.2, 10.8), dpi=100, frameon=False)
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    fig.patch.set_visible(False)
    ax.patch.set_visible(False)
    return fig, ax


def _fig_rgba(fig):
    fig.canvas.draw()
    return np.asarray(fig.canvas.buffer_rgba(), dtype=np.uint8).copy()


def _alpha_over(dst_rgb, src_rgba):
    a = src_rgba[..., 3:4].astype(np.float32) * (1.0 / 255.0)
    out = dst_rgb.astype(np.float32) * (1.0 - a) + src_rgba[..., :3].astype(np.float32) * a
    return np.clip(out, 0, 255).astype(np.uint8)


def _extract_macro_overlays(tick_id):
    ev = next(e for e in rf.events if e["tick_id"] == tick_id)
    fig, ax = _new_transparent_fig()
    try:
        rf._draw_macro(ax, tick_id, ev, detail_background=True, arrow_progress=1.0)
        children = list(ax.get_children())
        orig_vis = [ch.get_visible() for ch in children]
        for ch in children:
            ch.set_visible(0.5 < ch.get_zorder() < 26.8)
        below = _fig_rgba(fig)
        for ch, vis in zip(children, orig_vis):
            z = ch.get_zorder()
            ch.set_visible(vis and (abs(z - 29.0) < 0.2 or z >= 46.0))
        above = _fig_rgba(fig)
        return below, above
    finally:
        rf.plt.close(fig)


def _render_macro_arrows_rgba(tick_id, progress):
    prog = float(np.clip(progress, 0.0, 1.0))
    if prog <= 0.03:
        return None
    cfg = rf.MACRO_CUSTOM_FRAMES[tick_id]
    if not cfg.get("arrows"):
        return None
    fig, ax = _new_transparent_fig()
    try:
        ax.set_xlim(0, W_PX)
        ax.set_ylim(0, H_PX)
        ax.set_aspect("equal")
        ax.axis("off")
        for (lon1, lat1), (lon2, lat2), afk, sw, rad, al, albl, lbl_off in cfg["arrows"]:
            p1 = rf._to_px(lon1, lat1)
            p2 = rf._to_px(lon2, lat2)
            col = FACTION_STYLE.get(afk, FACTION_STYLE["TANG"])["arrow"]
            curve = draw_double_stroked_arrow(
                ax, p1, p2, col, shaft_px=sw, head_w_px=sw * 2.4, head_l_px=sw * 2.6,
                rad=rad, alpha=al, zorder=27, progress=prog,
            )
            if albl and prog >= 0.55:
                lbl_al = min(1.0, (prog - 0.55) / 0.30) * al
                mid = curve[len(curve) // 2]
                ax.text(
                    mid[0] + lbl_off[0], mid[1] + lbl_off[1], albl,
                    fontproperties=FONT_BOLD, fontsize=px_to_pt(27), color="#FFE97D", alpha=lbl_al,
                    ha="center", va="center", zorder=32, path_effects=text_outline(4.0, "#12100E"),
                )
        return _fig_rgba(fig)
    finally:
        rf.plt.close(fig)


def _render_tactical_arrows_rgba(bid, progress):
    from tactical_map import SCENES
    prog = float(np.clip(progress, 0.0, 1.0))
    if prog <= 0.03:
        return None
    sc = SCENES[bid]
    fig, ax = _new_transparent_fig()
    try:
        ax.set_xlim(0, W_PX)
        ax.set_ylim(0, H_PX)
        ax.set_aspect("equal")
        ax.axis("off")
        for p1, p2, afac, sw, rad, al, albl in sc.get("arrows", []):
            st = FACTION_STYLE[afac]
            curve = draw_double_stroked_arrow(
                ax, p1, p2, st["arrow"], shaft_px=sw, head_w_px=sw * 2.4, head_l_px=sw * 2.6,
                rad=rad, alpha=al, zorder=28, progress=prog,
            )
            if albl and prog >= 0.55:
                lbl_al = min(1.0, (prog - 0.55) / 0.30) * al
                mid = curve[len(curve) // 2]
                dy_off = 165.0 if bid == "B15" else (-38.0 if (afac == "TANG" and bid == "B06") or (afac == "YAN_AN" and bid == "B11") else 34.0)
                ax.text(
                    mid[0], mid[1] + dy_off, albl,
                    fontproperties=FONT_BOLD, fontsize=px_to_pt(28), color="#FFFFFF", alpha=lbl_al,
                    ha="center", va="center", zorder=40, path_effects=text_outline(4.0, "#12100E"),
                )
        return _fig_rgba(fig)
    finally:
        rf.plt.close(fig)


def _beat_punch(img, t, hit_times, boost=0.065, width=0.11):
    """卡点命中微脉冲提亮：在不加杂乱遮罩的前提下让重击/劈砍精准落在鼓点上。"""
    k = 0.0
    for th in hit_times:
        dt = t - th
        if 0.0 <= dt < width:
            k = max(k, (1.0 - dt / width) ** 1.6)
    if k <= 0.005:
        return img
    arr = img.astype(np.float32) * (1.0 + boost * k)
    return np.clip(arr, 0, 255).astype(np.uint8)


def render_video_pipe(meta):
    """步骤 2 + 3A：固定步长主循环读取卡点，并通过 FFmpeg stdin 管道实时直出无声视频。"""
    t0 = time.time()
    st = meta["story_timeline"]
    cues_abs = meta["b03_abs_cues"]
    total_sec = float(st["END"])
    total_frames = int(round(total_sec * FPS))

    macro_ticks = ["T001", "T002", "T003", "T004", "T005", "T006", "T007", "T008", "T009", "T010"]
    scores_by_tick = {}
    for tk in macro_ticks:
        cfg = rf.MACRO_CUSTOM_FRAMES[tk]
        snap = rf.snaps[cfg["tick_ref"]]
        scores_by_tick[tk] = compute_smoothed_faction_scores(
            rf.RELIEF, rf.D["cities"], snap["control"], owner_overrides=cfg.get("owner_overrides"),
        )

    # 规划与 Amazon 重拍锁定的叙事片段 (name, start_s, end_s, move_end_s, meta)
    b03_in = float(st["B03"])
    b03_dis = 0.55
    b03_act = b03_in + b03_dis
    b03_end = float(st["T008"])
    b03_dur = b03_end - b03_act

    # 把 librosa 绝对卡点换算为相对 b03_act 的时间坐标
    rel = lambda abs_t: float(abs_t) - b03_act
    b03_cues = {
        "charge_start": max(0.25, rel(cues_abs["charge_start"])),
        "front_kills": [rel(x) for x in cues_abs["front_kills"]],
        "chase_north_turn": max(2.2, rel(cues_abs["chase_north_kill"]) - 2.65),
        "chase_north_kill": rel(cues_abs["chase_north_kill"]),
        "chase_south_turn": max(2.1, rel(cues_abs["chase_north_kill"]) - 2.75),
        "chase_south_kill": rel(cues_abs["chase_south_kill"]),
        "mix_arrive": rel(cues_abs["volley"]) - 0.14,
        "volley": rel(cues_abs["volley"]),
        "wall_deaths": [rel(x) for x in cues_abs["wall_deaths"]],
        "smoke_start": rel(cues_abs["smoke_start"]),
        "gate_slash": rel(cues_abs["gate_slash"]),
        "banner_fall": rel(cues_abs["banner_fall"]),
        "arrows_dim_at": rel(cues_abs["arrows_done"]) + 0.12,
        "arrows_restore_at": max(rel(cues_abs["banner_fall"]) + 0.12, b03_dur - 0.90),
        "action_end": b03_dur,
    }
    b03_hits = (
        [float(cues_abs["arrows_done"])]
        + [float(x) for x in cues_abs["front_kills"]]
        + [float(cues_abs["chase_north_kill"]), float(cues_abs["chase_south_kill"]),
           float(cues_abs["volley"]), float(cues_abs["gate_slash"]), float(cues_abs["banner_fall"])]
    )

    segments = [
        {"kind": "MACRO", "id": "T001", "t0": st["T001"], "t1": st["T002"], "move_end": 2.40, "chain": ["T001", "T001"], "dis_in": 0.0},
        {"kind": "MACRO", "id": "T002", "t0": st["T002"], "t1": st["T003"], "move_end": st["T002"] + 2.44, "chain": ["T001", "T002"], "dis_in": 0.0},
        {"kind": "MACRO", "id": "T003", "t0": st["T003"], "t1": st["T005"], "move_end": st["T003"] + 2.42, "chain": ["T002", "T003"], "dis_in": 0.0},
        {"kind": "MACRO", "id": "T005", "t0": st["T005"], "t1": st["T007"], "move_end": st["T005"] + 2.44, "chain": ["T003", "T004", "T005"], "dis_in": 0.0},
        {"kind": "MACRO", "id": "T007", "t0": st["T007"], "t1": st["B03"],  "move_end": st["T007"] + 1.81, "chain": ["T005", "T006", "T007"], "dis_in": 0.0},
        {"kind": "B03",   "id": "B03",  "t0": b03_in,     "t1": b03_end},
        {"kind": "MACRO", "id": "T008", "t0": st["T008"], "t1": st["T009"], "move_end": st["T008"] + 1.83, "chain": ["T007", "T008"], "dis_in": 0.45},
        {"kind": "MACRO", "id": "T009", "t0": st["T009"], "t1": st["T010"], "move_end": st["T009"] + 1.53, "chain": ["T008", "T009"], "dis_in": 0.0},
        {"kind": "MACRO", "id": "T010", "t0": st["T010"], "t1": st["END"],  "move_end": st["T010"] + 1.81, "chain": ["T009", "T010"], "dis_in": 0.0},
    ]

    # 预抽取各宏观图层与 B03 动画器
    overlays = {s["id"]: _extract_macro_overlays(s["id"]) for s in segments if s["kind"] == "MACRO"}
    const_bg = {}
    for s in segments:
        if s["kind"] == "MACRO" and s["chain"][0] == s["chain"][-1]:
            bg_raw, _ = compose_macro_from_scores(rf.RELIEF, scores_by_tick[s["chain"][0]], detail_background=True)
            const_bg[s["id"]] = np.ascontiguousarray(bg_raw[::-1])

    anim = B03Animator(arrow_renderer=_render_tactical_arrows_rgba, cues=b03_cues)
    b03_first = anim.frame(0.0, arrow_prog=0.0)
    b03_arrow_dur = float(cues_abs["arrows_done"]) - b03_act

    # 步骤 3：直接用 subprocess.Popen 打开 FFmpeg 原始 RGB 管道
    raw_mp4 = OUT / "opening_clip_anshi_amazon_video.mp4"
    ff_cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W_PX}x{H_PX}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        str(raw_mp4),
    ]
    proc = subprocess.Popen(ff_cmd, stdin=subprocess.PIPE)

    seg_idx = 0
    prev_seg_end = None
    cur_hold_frame = None
    cur_hold_seg = None

    try:
        for frame in range(total_frames):
            t = frame / float(FPS)
            while seg_idx < len(segments) - 1 and t >= segments[seg_idx]["t1"] - 1e-6:
                if cur_hold_frame is not None:
                    prev_seg_end = cur_hold_frame
                seg_idx += 1
                cur_hold_frame = None
                cur_hold_seg = None
                print(f"  [Frame {frame:4d} | t={t:6.2f}s] -> Segment {segments[seg_idx]['id']} (elapsed {time.time() - t0:.1f}s)")

            seg = segments[seg_idx]
            if seg["kind"] == "MACRO":
                tk = seg["id"]
                below, above = overlays[tk]
                t_rel = t - seg["t0"]
                move_dur = max(0.05, seg["move_end"] - seg["t0"])
                e = _ease_io(t_rel / move_dur)
                is_static_hold = (t >= seg["move_end"] and t_rel >= seg["dis_in"])
                if is_static_hold and cur_hold_seg == tk and cur_hold_frame is not None:
                    img = cur_hold_frame
                else:
                    if tk in const_bg:
                        bg = const_bg[tk]
                    else:
                        ch = seg["chain"]
                        sp = e * (len(ch) - 1)
                        i0 = min(len(ch) - 2, int(sp))
                        frac = sp - i0
                        s_cur = (1.0 - frac) * scores_by_tick[ch[i0]] + frac * scores_by_tick[ch[i0 + 1]]
                        bg_raw, _ = compose_macro_from_scores(rf.RELIEF, s_cur, detail_background=True)
                        bg = np.ascontiguousarray(bg_raw[::-1])
                    img = _alpha_over(bg, below)
                    arr_rgba = _render_macro_arrows_rgba(tk, e)
                    if arr_rgba is not None:
                        img = _alpha_over(img, arr_rgba)
                    img = _alpha_over(img, above)
                    if seg["dis_in"] > 0 and t_rel < seg["dis_in"] and prev_seg_end is not None:
                        w = _ease_io(t_rel / seg["dis_in"])
                        img = np.clip(prev_seg_end.astype(np.float32) * (1.0 - w) + img.astype(np.float32) * w, 0, 255).astype(np.uint8)
                    if is_static_hold:
                        cur_hold_frame = img
                        cur_hold_seg = tk
                    else:
                        cur_hold_frame = img
            else:
                if t < b03_act:
                    w = _ease_io((t - b03_in) / b03_dis)
                    src = prev_seg_end if prev_seg_end is not None else b03_first
                    img = np.clip(src.astype(np.float32) * (1.0 - w) + b03_first.astype(np.float32) * w, 0, 255).astype(np.uint8)
                else:
                    t_b03 = t - b03_act
                    arr_prog = _ease_io(min(1.0, t_b03 / max(0.2, b03_arrow_dur)))
                    img = anim.frame(t_b03, arrow_prog=arr_prog)
                    img = _beat_punch(img, t, b03_hits, boost=0.065, width=0.11)
                    cur_hold_frame = img

            proc.stdin.write(img.tobytes())
    finally:
        if proc.stdin:
            proc.stdin.close()
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"FFmpeg video pipe failed with code {ret}")

    timing_out = {
        "fps": FPS,
        "total_frames": total_frames,
        "duration_sec": total_sec,
        "beats": {s["id"]: {"start_sec": float(s["t0"]), "end_sec": float(s["t1"]), "move_end_sec": float(s.get("move_end", s["t1"]))} for s in segments},
        "b03_dissolve_start_sec": float(b03_in),
        "b03_action_start_sec": float(b03_act),
        "b03_events": [(float(et), str(ek), float(ex)) for et, ek, ex in anim.events],
    }
    with open(AUD / "amazon_beat_sync_timing.json", "w", encoding="utf-8") as fh:
        json.dump(timing_out, fh, ensure_ascii=False, indent=2)
    print(f"Piped video done: {raw_mp4} ({total_frames} frames @ {FPS}fps = {total_sec:.2f}s) in {time.time() - t0:.1f}s")
    return timing_out


def build_sfx_and_mix_amazon(meta, timing):
    """按锁拍后的精确时间轴生成战争音效，并与压低＋动态闪避的 Amazon BGM 混流封装。"""
    B = {k: v["start_sec"] for k, v in timing["beats"].items()}
    TOTAL = float(timing["duration_sec"])
    N = int(round(TOTAL * SR))
    rng = np.random.default_rng(755)

    def bus():
        return np.zeros((2, N))

    amb, drums, battle, rout = bus(), bus(), bus(), bus()
    b03_start = B["B03"]
    b03_act = float(timing["b03_action_start_sec"])
    b03_drop = float(meta["b03_abs_cues"]["arrows_done"])
    t8_start = B["T008"]

    # 1. 环境风声（保留）
    w = S.wind_bed(rng, TOTAL)
    w *= S.envelope_points(N, [
        (0, 0.08), (b03_start, 0.06), (b03_act + 8.5, 0.11),
        (t8_start, 0.14), (B["T009"], 0.09), (B["T010"], 0.12), (TOTAL, 0.14),
    ])
    amb += w

    # 2. T001 范阳起兵（前奏 3s 后战鼓蓄势，重击卡在 4.899s 爆发落拍上）
    for dt in [3.10, 3.65, 4.15, 4.52]:
        S.place(drums, S.war_drum(rng, 58), dt, 0.55 + 0.1 * dt / 4.9, 0.0)
    S.place(drums, S.war_drum(rng, 48), B["T002"], 1.0, 0.0)
    S.place(drums, S.war_horn(rng, 98, 2.2, 4), B["T002"] + 0.05, 0.50, -0.25)
    S.place(battle, S.crowd(rng, 1.8, 28), 3.30, 0.35)

    # 3. T002 叛军铁骑南下（横扫河北，按节拍重鼓）
    S.place(amb, S.whoosh(rng, 0.65), B["T002"] - 0.20, 0.14)
    g = S.gallop(rng, 4.4, 14, rumble=0.65)
    g *= S.envelope_points(g.shape[1], [(0, 0.2), (0.5, 1.0), (3.6, 0.9), (4.4, 0.35)])
    S.place(battle, g, B["T002"] + 0.1, 0.50)
    for k in range(7):
        S.place(drums, S.war_drum(rng, 60), B["T002"] + 0.61 * k, 0.45, 0)

    # 4. T003 灵昌津踏冰渡河（冰裂对齐节拍与 12.21s 强峰）
    gi = S.gallop(rng, 4.2, 10, ice=True, rumble=0.35)
    gi = S.fade(gi, 0.3, 0.6)
    S.place(battle, gi, B["T003"] + 0.15, 0.60)
    for tt in [0.45, 1.45, 2.41, 3.55]:
        S.place(battle, S.ice_crack(rng), B["T003"] + tt, 0.78, rng.uniform(-0.55, 0.55))

    # 5. T005 连克陈留荥阳、兵逼虎牢
    far = S.melee_bed(rng, 3.8, 6.5) + 0.55 * S.crowd(rng, 3.8, 30)
    far = S.distance(S.fade(far, 0.4, 0.8), 0.72)
    S.place(battle, far, B["T005"] + 0.1, 0.72)
    for k in range(5):
        S.place(drums, S.war_drum(rng, 55), B["T005"] + 0.61 * k, 0.42, 0)

    # 6. T007 兵临洛阳 + 悬疑抽空过渡
    for k in range(4):
        S.place(drums, S.war_drum(rng, 56), B["T007"] + 0.61 * k, 0.58 + 0.08 * k, rng.uniform(-0.2, 0.2))
    S.place(drums, S.war_horn(rng, 87, 1.8, 5), B["T007"] + 0.15, 0.42, 0.3)

    # 7. B03 东京洛阳保卫战：全卡点动作音效
    S.place(amb, S.whoosh(rng, 0.6), b03_start - 0.18, 0.16)
    S.place(drums, S.war_drum(rng, 46), b03_drop, 1.0, 0.0)             # 24.427s 重拍爆发鼓
    ch_len = max(2.0, (t8_start - 1.2) - (b03_drop - 0.5))
    ch = S.gallop(rng, ch_len, 16, rumble=0.78, period=(0.28, 0.35))
    ch *= S.envelope_points(ch.shape[1], [(0, 0.15), (0.6, 1.0), (ch_len - 1.2, 0.85), (ch_len, 0.2)])
    S.place(battle, ch, b03_drop - 0.5, 0.68)

    me_dur = max(2.0, (t8_start - 1.0) - (b03_drop + 0.8))
    me = S.melee_bed(rng, me_dur, 10)
    me *= S.envelope_points(me.shape[1], [(0, 0), (0.3, 0.85), (me_dur - 1.0, 0.7), (me_dur, 0.15)])
    S.place(battle, me, b03_drop + 0.8, 0.52)

    cr_dur = max(2.0, (t8_start - 0.8) - (b03_drop + 0.5))
    cr = S.crowd(rng, cr_dur, 95, murmur=0.42)
    cr *= S.envelope_points(cr.shape[1], [(0, 0.2), (0.6, 1.0), (cr_dur - 1.0, 0.85), (cr_dur, 0.2)])
    S.place(battle, cr, b03_drop + 0.5, 0.65)

    # 追砍紧迫奔逃脚步
    chase_steps = S.running_retreat(rng, 4.2, n_people=10, recede=False)
    chase_steps = S.fade(chase_steps, 0.2, 0.4)
    S.place(battle, chase_steps, b03_act + 3.2, 0.56)

    # 逐帧卡点动作事件（slash / death / volley / banner_fall）
    for ev_t, ev_kind, ev_x in timing["b03_events"]:
        abs_t = b03_act + ev_t
        pan = float(np.clip((ev_x / 1920.0) * 2.0 - 1.0, -0.85, 0.85))
        if ev_kind == "slash":
            S.place(battle, S.blade_cleave(rng), abs_t - 0.04, 0.92, pan)
            S.place(battle, S.sword_clash(rng), abs_t, 0.52, pan)
        elif ev_kind == "death":
            S.place(battle, S.body_fall(rng), abs_t + 0.04, 0.78, pan)
            cry = S.shout(rng, rng.uniform(0.32, 0.48), rng.uniform(140, 210), rng.choice(["a", "o"]), contour="fall")
            S.place(battle, cry, abs_t, 0.58, pan)
        elif ev_kind == "volley":
            S.place(battle, S.arrow_volley(rng, 32), abs_t - 0.10, 0.88, -0.25)
            S.place(battle, S.arrow_volley(rng, 18), abs_t + 0.35, 0.52, -0.35)
        elif ev_kind == "banner_fall":
            S.place(battle, S.timber_crash(rng), abs_t, 0.95, pan)
            S.place(drums, S.war_drum(rng, 44), abs_t + 0.04, 0.85, pan * 0.4)

    smoke_abs = float(meta["b03_abs_cues"]["smoke_start"])
    S.place(battle, S.fade(S.fire(rng, 4.0), 0.5, 1.4), smoke_abs, 0.46)

    # 8. 鸣金溃逃：紧接城破旗倒延续到 T008 退保潼关
    r0 = float(meta["b03_abs_cues"]["banner_fall"]) - 0.15
    for k in range(7):
        S.place(rout, S.gong_clang(rng, 540), r0 + k * 0.25, 0.46 * (1 - 0.06 * k), -0.30)
    pc = S.crowd(rng, 3.2, 46, f0_range=(170, 330), vowels="aou", shout_len=(0.4, 1.0), contour="rise", murmur=0.25)
    pc *= S.envelope_points(pc.shape[1], [(0, 0.4), (0.4, 1.0), (1.6, 0.8), (3.2, 0)])
    S.place(rout, S.distance(pc, np.linspace(0.0, 0.85, pc.shape[1])), r0 + 0.15, 0.58)
    run = S.fade(S.running_retreat(rng, 4.2, 26), 0.25, 0.65)
    S.place(rout, run, r0 + 0.30, 0.82)
    hr = S.distance(S.gallop(rng, 3.4, 10, rumble=0.4), np.linspace(0.15, 0.95, int(3.4 * SR)))
    S.place(rout, S.fade(hr, 0.25, 0.8), r0 + 0.70, 0.48)

    # 9. T009 常山起义 + T010 称帝重鼓
    t9 = B["T009"]
    for dt in [0.00, 0.61, 1.22, 1.83]:
        S.place(drums, S.war_drum(rng, 64, bright=1.35), t9 + dt, 0.58, 0.2)
    S.place(drums, S.war_horn(rng, 131, 1.8, 3), t9 + 0.10, 0.36, -0.2)
    S.place(battle, S.distance(S.crowd(rng, 2.0, 42), 0.45), t9 + 0.35, 0.45)

    t10 = B["T010"]
    for dt in [0.00, 1.22, 2.42, 3.04]:
        S.place(drums, S.war_drum(rng, 44), t10 + dt, 0.88 if dt < 0.1 else 0.55, 0.0)

    # 10. 音效分轨混响与整形
    amb = S.reverb(amb, rng, 1.0, 0.15)
    drums = S.reverb(drums, rng, 1.8, 0.26)
    battle = S.reverb(battle, rng, 1.4, 0.22)
    rout = S.reverb(rout, rng, 1.6, 0.25)
    sfx_raw = amb * 0.90 + drums * 0.78 + battle * 0.92 + rout * 0.94
    sfx_raw = S.filt(sfx_raw, "high", 30.0)
    sfx_ref = np.percentile(np.abs(sfx_raw), 99.7) + 1e-9
    sfx = np.tanh((sfx_raw / sfx_ref * 0.68) * 1.25) / np.tanh(1.25)
    sfx = S.norm(sfx, 0.58)

    # 11. 读取并驯服 Amazon BGM（-9 LUFS 过响 → 基础压低 + 中频空出 + 动态侧链闪避，绝不喧宾夺主）
    sr_b, x_b = wavfile.read(str(Path(meta["source_wav"])))
    assert sr_b == SR
    bgm_full = x_b[:N].T.astype(np.float64) / 32768.0
    if bgm_full.shape[1] < N:
        bgm_full = np.pad(bgm_full, ((0, 0), (0, N - bgm_full.shape[1])))

    # 中高频轻微掏槽（1.3~3.2 kHz 降 ~2.5 dB）让刀剑劈砍/箭矢/呼喊自然浮在最前
    mid_pocket = S.filt(bgm_full, "band", (1300.0, 3200.0), order=2)
    bgm = bgm_full - 0.26 * mid_pocket

    # 基础电平：前奏(0~4s)与悬疑空档自身原本低 10~15 dB，略抬系数保持呼吸；B03 爆发推到 ~-20 dB，微升 +0.2 dB
    base_curve = 1.023 * S.envelope_points(N, [
        (0.0, 0.56),
        (3.8, 0.50),
        (B["T002"], 0.28),
        (b03_start - 0.3, 0.27),
        (b03_start + 0.1, 0.40),
        (b03_drop - 0.2, 0.38),
        (b03_drop + 0.1, 0.40),
        (t8_start - 0.2, 0.36),
        (t8_start + 0.2, 0.21),  # T008 退保潼关压低 BGM，留给溃逃与悲凉风声
        (B["T009"], 0.28),       # T009 常山起义小幅抬头
        (B["T010"], 0.27),
        (TOTAL - 2.0, 0.25),
        (TOTAL, 0.0),
    ])

    # 计算音效瞬时脉冲能量包络（高通瞬态+鼓点+溃逃锣声），只在砍杀/鼓/锣瞬间动态下压 ~3 dB，避免被底噪连续压死
    trans_sfx = S.filt(battle, "high", 1200.0) + drums * 0.9 + rout * 0.85
    sfx_mono_abs = np.max(np.abs(trans_sfx), axis=0)
    hop_sc = 240  # 5ms 步长
    sc_ds = np.maximum.reduceat(sfx_mono_abs[:(N // hop_sc) * hop_sc], np.arange(0, (N // hop_sc) * hop_sc, hop_sc))
    sc_ds = sc_ds / (np.percentile(sc_ds, 99.0) + 1e-9)
    sc_env_ds = np.zeros_like(sc_ds)
    cur = 0.0
    a_att, a_rel = 0.35, 0.045
    for i, v in enumerate(sc_ds):
        c = a_att if v > cur else a_rel
        cur = (1.0 - c) * cur + c * min(1.0, v)
        sc_env_ds[i] = cur
    sc_env = np.interp(np.arange(N), np.arange(len(sc_env_ds)) * hop_sc, sc_env_ds)
    duck_gain = np.clip(1.0 - 0.32 * sc_env, 0.68, 1.0)    # 瞬态撞击瞬间压低 ~3.3 dB 后迅速回弹
    bgm_ducked = bgm * base_curve * duck_gain

    # 12. 最终立体声总线合成与软限幅（仅做峰值防破保护，不再整轨拉升，避免把 BGM 跟着拽高）
    mix = sfx + bgm_ducked
    mix = np.tanh(mix * 1.08) / np.tanh(1.08)
    mix = S.fade(mix, 0.10, 0.60)
    pk_mix = float(np.max(np.abs(mix)))
    if pk_mix > 0.89:
        mix = mix * (0.89 / pk_mix)

    def to16(x):
        return (np.clip(x, -1.0, 1.0).T * 32767.0).astype(np.int16)

    wav_out = AUD / "amazon_sfx_bgm_mix.wav"
    wavfile.write(wav_out, SR, to16(mix))
    stem_dir = AUD / "amazon_stems"
    stem_dir.mkdir(exist_ok=True)
    for name_s, arr_s in [("bgm_ducked", bgm_ducked), ("sfx_all", sfx), ("ambience", amb),
                          ("drums_horns", drums), ("battle", battle), ("rout", rout)]:
        wavfile.write(stem_dir / f"{name_s}.wav", SR, to16(arr_s))

    # 分段打印 BGM vs SFX 响度对比核对（确保 BGM 绝不喧宾夺主）
    seg_names = ["T001", "T002", "T003", "T005", "T007", "B03", "T008", "T009", "T010"]
    starts = [B[k] for k in seg_names] + [TOTAL]
    print("=== Beat Loudness Balance (SFX vs Duck-Tamed Amazon BGM) ===")
    for nm, a, b in zip(seg_names, starts[:-1], starts[1:]):
        i0, i1 = int(a * SR), int(b * SR)
        r_sfx = 20 * np.log10(np.sqrt(np.mean(sfx[:, i0:i1] ** 2)) + 1e-9)
        r_bgm = 20 * np.log10(np.sqrt(np.mean(bgm_ducked[:, i0:i1] ** 2)) + 1e-9)
        r_mix = 20 * np.log10(np.sqrt(np.mean(mix[:, i0:i1] ** 2)) + 1e-9)
        print(f"  {nm:5s} {a:6.2f}-{b:6.2f}s | SFX {r_sfx:6.1f} dB | BGM {r_bgm:6.1f} dB | Mix {r_mix:6.1f} dB (SFX-BGM={r_sfx-r_bgm:+.1f} dB)")

    # 步骤 3B：无损封装最终视频 + Amazon 混音音轨
    raw_mp4 = OUT / "opening_clip_anshi_amazon_video.mp4"
    final_mp4 = OUT / "opening_clip_anshi_amazon.mp4"
    mux_cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
        "-i", str(raw_mp4), "-i", str(wav_out),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
        str(final_mp4),
    ]
    subprocess.run(mux_cmd, check=True)
    print(f"Saved final Amazon-synced MP4: {final_mp4} ({final_mp4.stat().st_size / 1048576:.2f} MB)")

    # 混音分轨核对图
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    fig, axs = plt.subplots(4, 1, figsize=(16, 9), sharex=True)
    tt = np.arange(N) / float(SR)
    axs[0].plot(tt[::40], bgm_ducked[0, ::40], lw=0.4, color="#457B9D", label="Amazon BGM (压低＋闪避)")
    axs[0].set_ylabel("Amazon BGM")
    axs[1].plot(tt[::40], sfx[0, ::40], lw=0.4, color="#E63946", label="战争音效总轨")
    axs[1].set_ylabel("战争音效 SFX")
    axs[2].plot(tt[::80], duck_gain[::80], lw=0.8, color="#2A9D8F")
    axs[2].set_ylim(0.45, 1.05)
    axs[2].set_ylabel("Sidechain 闪避")
    axs[3].specgram(mix.mean(0), NFFT=2048, Fs=SR, noverlap=1024, cmap="magma")
    axs[3].set_ylim(0, 8000)
    axs[3].set_ylabel("混音频谱")
    axs[3].set_xlabel("时间 (s)")
    for ax in axs:
        for nm, a in zip(seg_names, starts[:-1]):
            ax.axvline(a, color="#D62828", lw=0.9)
    for nm, a in zip(seg_names, starts[:-1]):
        axs[0].text(a + 0.08, axs[0].get_ylim()[1] * 0.80, nm, color="#D62828", fontsize=9)
    fig.suptitle("《安史之乱》Amazon 音乐卡点＋战场音效侧链闪避混音核对图")
    fig.tight_layout()
    fig.savefig(AUD / "amazon_mix_timeline.png", dpi=95)
    print(f"Saved {AUD / 'amazon_mix_timeline.png'}")


def main():
    with open(BEATS_JSON, "r", encoding="utf-8") as fh:
        meta = json.load(fh)
    timing = render_video_pipe(meta)
    build_sfx_and_mix_amazon(meta, timing)


if __name__ == "__main__":
    main()
