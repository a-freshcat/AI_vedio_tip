# -*- coding: utf-8 -*-
"""《安史之乱》续集片段（Part 2：T011 常山陷落 — B05 嘉山大捷 — B06 灵宝西原大败 — T026 肃宗灵武即位）
卡点提取（Amazon 46.00s–114.43s）、固定 30fps 主循环 FFmpeg 管道渲染与避让混音导出。

输出：
1. output/audio/amazon_part2_beats.json      —— 46–114.43s librosa 卡点与剧情时间轴
2. output/audio/amazon_part2_beat_map.png  —— 续集波形/卡点分布图
3. output/audio/amazon_part2_mix_timeline.png —— SFX 与压低+侧链闪避后 Amazon BGM 对比图
4. output/opening_clip_anshi_part2_amazon.mp4 —— 1920×1080 30fps 续集成片（可与 Part 1 无缝拼合）
5. output/anshi_full_114s_amazon.mp4       —— 将 Part 1 (0-46s) 与 Part 2 (46-114.43s) 无损拼接成的 1 分 54 秒合集
"""
import json
import shutil
import subprocess
from pathlib import Path
import sys
import time

import librosa
import numpy as np
from PIL import Image
from scipy.io import wavfile

import imageio_ffmpeg

sys.path.insert(0, str(Path(__file__).parent))
from battle_anim import B05Animator, B06Animator
import render_amazon_beat_clip as r1
import render_frame as rf
import sfx_synth as S
from sfx_synth import SR
from tactical_map import H_PX, W_PX
from terrain import compose_macro_from_scores, compute_smoothed_faction_scores

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
AUD = OUT / "audio"
AUD.mkdir(parents=True, exist_ok=True)
SRC_WAV = AUD / "amazon_48k.wav"
FPS = 30
BGM_OFFSET_SEC = 46.00     # 无缝衔接 Part 1 的 46.00s 终点
UPLOAD_DIR = Path("C:/Users/handsomeboys/.gemini/antigravity/brain/883511d4-c1d5-463f-8aff-52b28f91ca4b/.user_uploaded")
CLIP1_SUZONG_MP4 = UPLOAD_DIR / "media_1794839854425_858f8fda.mp4"    # 唐肃宗即位 · 2.00s (60f)
CLIP2_GESHUHAN_MP4 = UPLOAD_DIR / "media_1794839884051_fea3123b.mp4"  # 哥舒翰出潼关 · 6.00s (180f)
CLIP3_ANLUSHAN_MP4 = UPLOAD_DIR / "media_1794839891349_7f8d3b93.mp4"  # 安禄山遇害 · 4.00s (120f)


def _load_external_clip(mp4_path, target_frames, sr=SR, fps=FPS, sfx_peak=0.58):
    """从外部 MP4 解码指定帧数的 1920x1080 RGB 画面与 48kHz 立体声音效。"""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    p = str(mp4_path)
    v_proc = subprocess.run([
        ff, "-y", "-loglevel", "error", "-i", p,
        "-vf", f"fps={fps},scale={W_PX}:{H_PX}:flags=lanczos,setsar=1",
        "-frames:v", str(target_frames),
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ], capture_output=True, check=True)
    frame_bytes = W_PX * H_PX * 3
    raw_v = np.frombuffer(v_proc.stdout, dtype=np.uint8)
    n_got = len(raw_v) // frame_bytes
    frames = raw_v[:n_got * frame_bytes].reshape((n_got, H_PX, W_PX, 3)).copy()
    if 0 < n_got < target_frames:
        pad = np.repeat(frames[-1:], target_frames - n_got, axis=0)
        frames = np.concatenate([frames, pad], axis=0)

    n_aud = int(round((target_frames / float(fps)) * sr))
    a_proc = subprocess.run([
        ff, "-y", "-loglevel", "error", "-i", p,
        "-ac", "2", "-ar", str(sr),
        "-f", "f32le", "-",
    ], capture_output=True, check=True)
    aud = np.frombuffer(a_proc.stdout, dtype=np.float32).reshape((-1, 2)).T.astype(np.float64)
    if aud.shape[1] < n_aud:
        aud = np.pad(aud, ((0, 0), (0, n_aud - aud.shape[1])))
    else:
        aud = aud[:, :n_aud]
    pk = float(np.max(np.abs(aud)))
    if pk > 1e-6 and sfx_peak is not None:
        aud = np.tanh((aud / pk) * 1.35) / np.tanh(1.35) * sfx_peak
    aud = S.fade(aud, 0.04, 0.06)
    return frames, aud


def nearest(arr, target):
    cand = [float(x) for x in arr]
    return min(cand, key=lambda x: abs(x - target))


def extract_part2_beats():
    y, sr = librosa.load(str(SRC_WAV), sr=22050, mono=True)
    oenv = librosa.onset.onset_strength(y=y, sr=sr)
    on_frames = librosa.onset.onset_detect(onset_envelope=oenv, sr=sr, delta=0.18, wait=4, backtrack=False)
    onsets = librosa.frames_to_time(on_frames, sr=sr)
    ostrs = [float(oenv[min(int(f), len(oenv) - 1)]) for f in on_frames]
    tempo, b_frames = librosa.beat.beat_track(onset_envelope=oenv, sr=sr)
    beats = librosa.frames_to_time(b_frames, sr=sr)

    strong = [float(t) for t, s in zip(onsets, ostrs) if 45.0 <= t <= 116.0 and s >= 8.0]
    beats_seg = [float(t) for t in beats if 45.0 <= t <= 116.0]

    # 绝对曲库时间戳 (46.00s .. 114.43s)
    t_t011 = 46.000
    t_t016 = nearest(beats_seg, 50.99)
    t_b05  = nearest(strong, 56.47)
    t_t019 = nearest(beats_seg, 63.81)                 # 63.808s 腾出 65.70-71.70s 嵌入哥舒翰出潼关 6s
    t_b06  = nearest(strong, 71.70)
    t_clip2 = round(float(t_b06) - 6.000, 4)           # 65.7032s -> 6.00s 恰好切入 71.703s B06
    t_t021 = nearest(beats_seg, 89.72)
    t_t022 = nearest(beats_seg, 94.60)
    t_t023 = nearest(beats_seg, 99.47)
    t_t024 = nearest(strong, 102.52)
    t_t026 = nearest(beats_seg, 106.49)
    t_clip1 = round(float(nearest(beats_seg, 113.82)) - 2.000, 4)  # 111.824s -> 2.00s 接肃宗即位定格收束
    t_end  = nearest(beats_seg, 114.43)

    b05_cues_abs = {
        "arrows_done": nearest(beats_seg, 58.28),
        "front_kills": [
            nearest(strong, 59.51),
            nearest(strong, 60.12),
            nearest(strong, 61.35),
        ],
        "chase_kill": nearest(strong, 62.56),
        "chase_gate_slash": nearest(strong, 63.16),
    }
    b06_cues_abs = {
        "fire_start": nearest(beats_seg, 82.69),       # 第 32 小节重拍大爆炸回归！
        "volley": nearest(strong, 83.73),
        "ambush_kills": [
            nearest(strong, 84.82),
            nearest(strong, 85.45),
            nearest(strong, 86.05),
        ],
        "chase_kills": [
            nearest(strong, 86.66),
            nearest(strong, 87.28),
            nearest(strong, 88.49),
        ],
    }

    # 转为相对 Part 2 视频片头的秒数（t_rel = t_abs - BGM_OFFSET_SEC）
    rel2 = lambda x: round(float(x) - BGM_OFFSET_SEC, 4)
    timeline = {
        "T011": rel2(t_t011),
        "T016": rel2(t_t016),
        "B05":  rel2(t_b05),
        "T019": rel2(t_t019),
        "CLIP2_GESHUHAN": rel2(t_clip2),
        "B06":  rel2(t_b06),
        "T021": rel2(t_t021),
        "T022": rel2(t_t022),
        "T023": rel2(t_t023),
        "T024": rel2(t_t024),
        "T026": rel2(t_t026),
        "CLIP1_SUZONG": rel2(t_clip1),
        "END":  rel2(t_end),
    }

    meta = {
        "bgm_offset_sec": BGM_OFFSET_SEC,
        "abs_timeline": {
            "T011": t_t011, "T016": t_t016, "B05": t_b05, "T019": t_t019, "CLIP2_GESHUHAN": t_clip2,
            "B06": t_b06, "T021": t_t021, "T022": t_t022, "T023": t_t023, "T024": t_t024,
            "T026": t_t026, "CLIP1_SUZONG": t_clip1, "END": t_end,
        },
        "story_timeline": timeline,
        "b05_abs_cues": b05_cues_abs,
        "b06_abs_cues": b06_cues_abs,
    }
    out_json = AUD / "amazon_part2_beats.json"
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)

    # 绘图核对
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    sr_w, x_w = wavfile.read(str(SRC_WAV))
    i0, i1 = int(BGM_OFFSET_SEC * sr_w), int((t_end + 0.5) * sr_w)
    m_w = x_w[i0:i1].mean(axis=1).astype(np.float32) / 32768.0
    tt_w = np.arange(len(m_w)) / float(sr_w) + BGM_OFFSET_SEC
    fig, ax = plt.subplots(2, 1, figsize=(16, 7), sharex=True)
    ax[0].plot(tt_w[::40], m_w[::40], lw=0.4, color="#2C4966")
    for k, v in meta["abs_timeline"].items():
        if k == "END":
            continue
        ax[0].axvline(v, color="#D62828", lw=1.3)
        ax[0].text(v + 0.12, 0.84, k, color="#D62828", fontsize=9, fontweight="bold")
    for grp in [b05_cues_abs, b06_cues_abs]:
        for val in grp.values():
            for tv in (val if isinstance(val, list) else [val]):
                ax[1].axvline(tv, color="#E76F51", ls="--", lw=1.0)
    t_env = librosa.times_like(oenv, sr=sr)
    msk = (t_env >= BGM_OFFSET_SEC) & (t_env <= t_end + 0.5)
    ax[1].plot(t_env[msk], oenv[msk], color="#264653", lw=0.9)
    ax[0].set_ylabel("Amazon 波形")
    ax[1].set_ylabel("Onset 能量")
    ax[1].set_xlabel("原曲时间 (s)")
    fig.suptitle("《Amazon》46–114.4s librosa 卡点提取与 Part 2 剧情对齐图")
    fig.tight_layout()
    fig.savefig(AUD / "amazon_part2_beat_map.png", dpi=95)
    print(f"Saved {out_json} | duration={timeline['END']:.2f}s | b05={b05_cues_abs} | b06={b06_cues_abs}")
    return meta


def render_part2_video_pipe(meta):
    t0 = time.time()
    st = meta["story_timeline"]
    total_sec = float(st["END"])
    total_frames = int(round(total_sec * FPS))

    # 预计算宏观疆域场
    macro_ticks = ["T010", "T011", "T012", "T013", "T016", "T019", "T021", "T022", "T023", "T024", "T025", "T026"]
    scores_by_tick = {}
    for tk in macro_ticks:
        cfg = rf.MACRO_CUSTOM_FRAMES.get(tk)
        ref = cfg["tick_ref"] if cfg else tk
        snap = rf.snaps[ref]
        ov = cfg.get("owner_overrides") if cfg else None
        scores_by_tick[tk] = compute_smoothed_faction_scores(rf.RELIEF, rf.D["cities"], snap["control"], owner_overrides=ov)

    # B05 时间映射（相对 Part 2）
    b05_in = float(st["B05"])
    b05_dis = 0.55
    b05_act = b05_in + b05_dis
    b05_end = float(st["T019"])
    b05_dur = b05_end - b05_act
    rel05 = lambda t_abs: (float(t_abs) - BGM_OFFSET_SEC) - b05_act
    c5 = meta["b05_abs_cues"]
    b05_cues = {
        "charge_start": 0.40,
        "front_kills": [rel05(x) for x in c5["front_kills"]],
        "chase_turn": max(2.2, rel05(c5["chase_kill"]) - 1.68),
        "chase_kill": rel05(c5["chase_kill"]),
        "chase_gate_slash": rel05(c5["chase_gate_slash"]),
        "arrows_dim_at": rel05(c5["arrows_done"]) + 0.15,
        "arrows_restore_at": max(rel05(c5["chase_gate_slash"]) + 0.12, b05_dur - 0.55),
        "action_end": b05_dur,
    }
    b05_hits = [float(x) - BGM_OFFSET_SEC for x in ([c5["arrows_done"]] + c5["front_kills"] + [c5["chase_kill"], c5["chase_gate_slash"]])]

    # B06 时间映射（相对 Part 2）
    b06_in = float(st["B06"])
    b06_dis = 0.60
    b06_act = b06_in + b06_dis
    b06_end = float(st["T021"])
    b06_dur = b06_end - b06_act
    rel06 = lambda t_abs: (float(t_abs) - BGM_OFFSET_SEC) - b06_act
    c6 = meta["b06_abs_cues"]
    b06_cues = {
        "arrows_done": 2.30,
        "march_start": 0.80,
        "fire_start": rel06(c6["fire_start"]),
        "volley": rel06(c6["volley"]),
        "ambush_kills": [rel06(x) for x in c6["ambush_kills"]],
        "chase_kills": [rel06(x) for x in c6["chase_kills"]],
        "arrows_dim_at": 2.90,
        "arrows_restore_at": b06_dur - 1.15,
        "action_end": b06_dur,
    }
    b06_hits = [float(x) - BGM_OFFSET_SEC for x in ([c6["fire_start"], c6["volley"]] + c6["ambush_kills"] + c6["chase_kills"])]

    segments = [
        {"kind": "MACRO", "id": "T011", "t0": st["T011"], "t1": st["T016"], "move_end": st["T011"] + 2.40, "chain": ["T010", "T011"], "dis_in": 0.45, "const": False},
        {"kind": "MACRO", "id": "T016", "t0": st["T016"], "t1": st["B05"],  "move_end": st["T016"] + 2.42, "chain": ["T011", "T012", "T013", "T016"], "dis_in": 0.0, "const": False},
        {"kind": "TAC",   "id": "B05",  "t0": b05_in,     "t1": b05_end,    "act": b05_act, "dis": b05_dis, "arr_dur": rel05(c5["arrows_done"]), "hits": b05_hits},
        {"kind": "MACRO", "id": "T019", "t0": st["T019"], "t1": st["CLIP2_GESHUHAN"], "move_end": st["T019"] + 1.45, "chain": ["T019", "T019"], "dis_in": 0.40, "const": True},
        {"kind": "CLIP",  "id": "CLIP2_GESHUHAN", "clip_key": "CLIP2", "t0": st["CLIP2_GESHUHAN"], "t1": st["B06"], "dis_in": 0.0},
        {"kind": "TAC",   "id": "B06",  "t0": b06_in,     "t1": b06_end,    "act": b06_act, "dis": b06_dis, "arr_dur": 2.30, "hits": b06_hits},
        {"kind": "MACRO", "id": "T021", "t0": st["T021"], "t1": st["T022"], "move_end": st["T021"] + 2.15, "chain": ["T019", "T021"], "dis_in": 0.45, "const": False},
        {"kind": "MACRO", "id": "T022", "t0": st["T022"], "t1": st["T023"], "move_end": st["T022"] + 1.85, "chain": ["T022", "T022"], "dis_in": 0.0, "const": True},
        {"kind": "MACRO", "id": "T023", "t0": st["T023"], "t1": st["T024"], "move_end": st["T023"] + 1.50, "chain": ["T023", "T023"], "dis_in": 0.0, "const": True},
        {"kind": "MACRO", "id": "T024", "t0": st["T024"], "t1": st["T026"], "move_end": st["T024"] + 1.95, "chain": ["T023", "T024"], "dis_in": 0.0, "const": False},
        {"kind": "MACRO", "id": "T026", "t0": st["T026"], "t1": st["CLIP1_SUZONG"], "move_end": st["T026"] + 2.55, "chain": ["T024", "T025", "T026"], "dis_in": 0.0, "const": False},
        {"kind": "CLIP",  "id": "CLIP1_SUZONG",   "clip_key": "CLIP1", "t0": st["CLIP1_SUZONG"], "t1": st["END"], "dis_in": 0.20},
    ]

    clip2_frames, _ = _load_external_clip(CLIP2_GESHUHAN_MP4, 180)
    clip1_frames, _ = _load_external_clip(CLIP1_SUZONG_MP4, 60)
    clips_frames = {"CLIP2": clip2_frames, "CLIP1": clip1_frames}

    overlays = {s["id"]: r1._extract_macro_overlays(s["id"]) for s in segments if s["kind"] == "MACRO"}
    const_bg = {}
    for s in segments:
        if s["kind"] == "MACRO" and s["const"]:
            bg_raw, _ = compose_macro_from_scores(rf.RELIEF, scores_by_tick[s["chain"][0]], detail_background=True)
            const_bg[s["id"]] = np.ascontiguousarray(bg_raw[::-1])

    anim_b05 = B05Animator(arrow_renderer=r1._render_tactical_arrows_rgba, cues=b05_cues)
    anim_b06 = B06Animator(arrow_renderer=r1._render_tactical_arrows_rgba, cues=b06_cues)
    anims = {"B05": (anim_b05, anim_b05.frame(0.0, arrow_prog=0.0)), "B06": (anim_b06, anim_b06.frame(0.0, arrow_prog=0.0))}

    # 若 Part 1 最后一帧已输出，用它做 T011 开头短淡入过渡
    prev_seg_end = None
    p1_ref = OUT / "frame_T010.png"
    if p1_ref.exists():
        with Image.open(p1_ref) as im_p1:
            prev_seg_end = np.asarray(im_p1.convert("RGB"))

    raw_mp4 = OUT / "opening_clip_anshi_part2_amazon_video.mp4"
    ff_cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W_PX}x{H_PX}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        str(raw_mp4),
    ]
    proc = subprocess.Popen(ff_cmd, stdin=subprocess.PIPE)

    seg_idx = 0
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
                print(f"  [Frame {frame:4d} | t={t:6.2f}s (BGM {t+BGM_OFFSET_SEC:6.2f}s)] -> {segments[seg_idx]['id']} ({time.time() - t0:.1f}s)")

            seg = segments[seg_idx]
            if seg["kind"] == "MACRO":
                tk = seg["id"]
                below, above = overlays[tk]
                t_rel = t - seg["t0"]
                move_dur = max(0.05, seg["move_end"] - seg["t0"])
                e = r1._ease_io(t_rel / move_dur)
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
                    img = r1._alpha_over(bg, below)
                    arr_rgba = r1._render_macro_arrows_rgba(tk, e)
                    if arr_rgba is not None:
                        img = r1._alpha_over(img, arr_rgba)
                    img = r1._alpha_over(img, above)
                    if seg["dis_in"] > 0 and t_rel < seg["dis_in"] and prev_seg_end is not None:
                        w = r1._ease_io(t_rel / seg["dis_in"])
                        img = np.clip(prev_seg_end.astype(np.float32) * (1.0 - w) + img.astype(np.float32) * w, 0, 255).astype(np.uint8)
                    cur_hold_frame = img
                    if is_static_hold:
                        cur_hold_seg = tk
            elif seg["kind"] == "CLIP":
                clip_arr = clips_frames[seg["clip_key"]]
                idx_f = min(len(clip_arr) - 1, max(0, int(round((t - seg["t0"]) * FPS))))
                img = clip_arr[idx_f]
                if seg.get("dis_in", 0.0) > 0 and (t - seg["t0"]) < seg["dis_in"] and prev_seg_end is not None:
                    w = r1._ease_io((t - seg["t0"]) / seg["dis_in"])
                    img = np.clip(prev_seg_end.astype(np.float32) * (1.0 - w) + img.astype(np.float32) * w, 0, 255).astype(np.uint8)
                cur_hold_frame = img
            else:
                bid = seg["id"]
                anim, first_fr = anims[bid]
                if t < seg["act"]:
                    w = r1._ease_io((t - seg["t0"]) / seg["dis"])
                    src = prev_seg_end if prev_seg_end is not None else first_fr
                    img = np.clip(src.astype(np.float32) * (1.0 - w) + first_fr.astype(np.float32) * w, 0, 255).astype(np.uint8)
                else:
                    t_tac = t - seg["act"]
                    arr_prog = r1._ease_io(min(1.0, t_tac / max(0.2, seg["arr_dur"])))
                    img = anim.frame(t_tac, arrow_prog=arr_prog)
                    img = r1._beat_punch(img, t, seg["hits"], boost=0.065, width=0.11)
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
        "beats": {s["id"]: {"start_sec": float(s["t0"]), "end_sec": float(s["t1"])} for s in segments},
        "b05_action_start_sec": float(b05_act),
        "b05_events": [(float(et), str(ek), float(ex)) for et, ek, ex in anim_b05.events],
        "b06_action_start_sec": float(b06_act),
        "b06_events": [(float(et), str(ek), float(ex)) for et, ek, ex in anim_b06.events],
    }
    with open(AUD / "amazon_part2_sync_timing.json", "w", encoding="utf-8") as fh:
        json.dump(timing_out, fh, ensure_ascii=False, indent=2)
    print(f"Piped Part 2 video: {raw_mp4} ({total_frames} frames @ {FPS}fps = {total_sec:.2f}s) in {time.time() - t0:.1f}s")
    return timing_out


def build_part2_sfx_and_mix(meta, timing):
    B = {k: v["start_sec"] for k, v in timing["beats"].items()}
    TOTAL = float(timing["duration_sec"])
    N = int(round(TOTAL * SR))
    rng = np.random.default_rng(756)

    def bus():
        return np.zeros((2, N))

    amb, drums, battle, rout = bus(), bus(), bus(), bus()
    b05_act = float(timing["b05_action_start_sec"])
    b06_act = float(timing["b06_action_start_sec"])
    b06_fire = float(meta["b06_abs_cues"]["fire_start"]) - BGM_OFFSET_SEC

    # 1. 环境风声（灵宝峡谷对峙期阴冷朔风加重，长安沦陷后悲凉）
    w = S.wind_bed(rng, TOTAL)
    w *= S.envelope_points(N, [
        (0.0, 0.08), (B["B05"], 0.07), (B["T019"], 0.12),
        (b06_fire, 0.09), (B["T021"], 0.13), (B["T023"], 0.15), (TOTAL, 0.11),
    ])
    amb += w

    # 2. T011 常山破城、T016 郭李出井陉
    for k in range(5):
        S.place(drums, S.war_drum(rng, 58), B["T011"] + 0.61 * k, 0.50, -0.1)
    S.place(battle, S.distance(S.melee_bed(rng, 3.2, 7.0) + 0.5 * S.crowd(rng, 3.2, 32), 0.65), B["T011"] + 0.5, 0.7)

    for k in range(6):
        S.place(drums, S.war_drum(rng, 62, bright=1.25), B["T016"] + 0.61 * k, 0.58, 0.1)
    S.place(drums, S.war_horn(rng, 128, 2.1, 4), B["T016"] + 0.15, 0.45, -0.25)
    S.place(battle, S.gallop(rng, 4.2, 12, rumble=0.55), B["T016"] + 0.35, 0.48)

    # 3. B05 嘉山大捷（唐军涉水冲锋、三连斩、追砍奔逃史思明）
    S.place(amb, S.whoosh(rng, 0.6), B["B05"] - 0.15, 0.15)
    S.place(drums, S.war_drum(rng, 52), b05_act + 1.26, 0.92, -0.2)
    ch5 = S.gallop(rng, 6.2, 16, rumble=0.72, period=(0.28, 0.35))
    ch5 *= S.envelope_points(ch5.shape[1], [(0, 0.15), (0.6, 1.0), (5.0, 0.8), (6.2, 0.15)])
    S.place(battle, ch5, b05_act + 0.85, 0.65)
    S.place(battle, S.crowd(rng, 4.8, 85, murmur=0.40), b05_act + 1.5, 0.62)
    for ev_t, ev_kind, ev_x in timing["b05_events"]:
        abs_t = b05_act + ev_t
        pan = float(np.clip((ev_x / 1920.0) * 2.0 - 1.0, -0.85, 0.85))
        if ev_kind == "slash":
            S.place(battle, S.blade_cleave(rng), abs_t - 0.04, 0.90, pan)
            S.place(battle, S.sword_clash(rng), abs_t, 0.48, pan)
        elif ev_kind == "death":
            S.place(battle, S.body_fall(rng), abs_t + 0.04, 0.76, pan)
            S.place(battle, S.shout(rng, 0.38, rng.uniform(135, 200), "a", "fall"), abs_t, 0.55, pan)
        elif ev_kind == "gong_retreat":
            for k in range(5):
                S.place(rout, S.gong_clang(rng, 560), abs_t + k * 0.25, 0.40 * (1 - 0.08 * k), 0.45)

    # 4. T019 逼出潼关（前段宏观微鼓）+ CLIP2 哥舒翰出潼关 6s 原生剧场音效 + B06 灵宝西原潜行
    for k in range(2):
        S.place(drums, S.war_drum(rng, 50), B["T019"] + 1.15 * k, 0.48, 0.0)
    march = S.running_retreat(rng, 8.8, n_people=14, recede=False)
    march = S.distance(S.fade(march, 0.8, 0.8), 0.45)
    S.place(battle, march, b06_act + 1.0, 0.40)

    # 5. B06 爆发阶段（82.69s 火攻烈焰 + 南山箭雨 + 伏兵追砍溃兵）
    S.place(drums, S.war_drum(rng, 44), b06_fire, 1.0, 0.0)
    S.place(drums, S.war_horn(rng, 82, 2.3, 5), b06_fire + 0.08, 0.50, 0.25)
    S.place(battle, S.fade(S.fire(rng, 7.6, crackle_rate=28.0), 0.3, 1.6), b06_fire, 0.72)
    ch6 = S.gallop(rng, 6.2, 16, rumble=0.78, period=(0.28, 0.34))
    S.place(battle, S.fade(ch6, 0.3, 1.0), b06_fire + 0.8, 0.65)
    S.place(battle, S.fade(S.crowd(rng, 6.0, 95, f0_range=(155, 290), contour="rise"), 0.3, 1.0), b06_fire + 0.6, 0.68)

    for ev_t, ev_kind, ev_x in timing["b06_events"]:
        abs_t = b06_act + ev_t
        pan = float(np.clip((ev_x / 1920.0) * 2.0 - 1.0, -0.85, 0.85))
        if ev_kind == "slash":
            S.place(battle, S.blade_cleave(rng), abs_t - 0.04, 0.92, pan)
            S.place(battle, S.sword_clash(rng), abs_t, 0.50, pan)
        elif ev_kind == "death":
            S.place(battle, S.body_fall(rng), abs_t + 0.04, 0.78, pan)
            S.place(battle, S.shout(rng, 0.40, rng.uniform(145, 220), "o", "fall"), abs_t, 0.58, pan)
        elif ev_kind == "volley":
            S.place(battle, S.arrow_volley(rng, 34), abs_t - 0.10, 0.90, 0.15)
            S.place(battle, S.arrow_volley(rng, 22), abs_t + 0.30, 0.55, 0.0)

    # 灵宝大溃逃：鸣金＋惊呼＋西逃潼关脚步渐远
    r0 = b06_fire + 3.4
    for k in range(6):
        S.place(rout, S.gong_clang(rng, 520), r0 + k * 0.25, 0.42 * (1 - 0.07 * k), -0.35)
    S.place(rout, S.fade(S.running_retreat(rng, 5.2, 28), 0.25, 0.9), r0 + 0.25, 0.80)

    # 6. T021-T024 潼关陷、幸蜀马嵬、长安陷；T026 肃宗即位鼓角重振
    S.place(drums, S.war_drum(rng, 44), B["T021"], 0.92, 0.0)
    S.place(drums, S.war_horn(rng, 84, 2.2, 4), B["T021"] + 0.15, 0.45, -0.25)
    S.place(battle, S.distance(S.gallop(rng, 3.2, 10, rumble=0.45), 0.55), B["T021"] + 0.4, 0.52)
    S.place(battle, S.fade(S.gallop(rng, 3.8, 12, rumble=0.5), 0.3, 0.8), B["T022"] + 0.4, 0.50)
    S.place(battle, S.distance(S.crowd(rng, 2.2, 35, f0_range=(160, 280), contour="rise"), 0.55), B["T023"] + 0.25, 0.58)
    S.place(drums, S.war_drum(rng, 44), B["T024"], 0.90, -0.2)
    S.place(drums, S.war_horn(rng, 92, 2.4, 4), B["T024"] + 0.10, 0.46, -0.3)
    S.place(battle, S.distance(S.gallop(rng, 3.5, 14, rumble=0.6) + 0.45 * S.crowd(rng, 3.5, 45), 0.55), B["T024"] + 0.30, 0.58)

    t26 = B["T026"]
    for dt in [0.00, 1.22, 2.44]:
        S.place(drums, S.war_drum(rng, 56, bright=1.25), t26 + dt, 0.82 if dt == 0.0 else 0.55, -0.2)
    S.place(drums, S.war_horn(rng, 131, 3.0, 4), t26 + 0.25, 0.50, -0.3)
    S.place(battle, S.distance(S.gallop(rng, 4.0, 10, rumble=0.5), 0.50), t26 + 0.60, 0.46)

    # 7. 音效整合（与 Part 1 同校准参数：峰值控在 0.58，不压死 Amazon）
    amb = S.reverb(amb, rng, 1.0, 0.15)
    drums = S.reverb(drums, rng, 1.8, 0.26)
    battle = S.reverb(battle, rng, 1.4, 0.22)
    rout = S.reverb(rout, rng, 1.6, 0.25)
    sfx_raw = amb * 0.90 + drums * 0.78 + battle * 0.92 + rout * 0.94
    sfx_raw = S.filt(sfx_raw, "high", 30.0)
    sfx_ref = np.percentile(np.abs(sfx_raw), 99.7) + 1e-9
    sfx = np.tanh((sfx_raw / sfx_ref * 0.68) * 1.25) / np.tanh(1.25)
    sfx = S.norm(sfx, 0.58)

    # 嵌入两段上传视频原生音效（保留其内部张弛层次，峰值控至 0.58 并参与闪避触发）
    _, clip2_aud = _load_external_clip(CLIP2_GESHUHAN_MP4, 180)
    _, clip1_aud = _load_external_clip(CLIP1_SUZONG_MP4, 60)
    clip_bus = np.zeros_like(sfx)
    S.place(clip_bus, clip2_aud, B["CLIP2_GESHUHAN"], 1.0)
    S.place(clip_bus, clip1_aud, B["CLIP1_SUZONG"], 1.0)
    sfx = sfx + clip_bus
    pk_sfx = float(np.max(np.abs(sfx)))
    if pk_sfx > 0.60:
        sfx = np.tanh((sfx / pk_sfx) * 1.15) / np.tanh(1.15) * 0.58

    # 8. 读取 Amazon BGM (46.00s -> +TOTAL) 做中频空让 + 动态侧链闪避
    sr_b, x_b = wavfile.read(str(SRC_WAV))
    assert sr_b == SR
    s0 = int(round(BGM_OFFSET_SEC * SR))
    bgm_full = x_b[s0:s0 + N].T.astype(np.float64) / 32768.0
    if bgm_full.shape[1] < N:
        bgm_full = np.pad(bgm_full, ((0, 0), (0, N - bgm_full.shape[1])))

    mid_pocket = S.filt(bgm_full, "band", (1300.0, 3200.0), order=2)
    bgm = bgm_full - 0.26 * mid_pocket

    base_curve = 1.023 * S.envelope_points(N, [
        (0.0, 0.28),
        (B["B05"], 0.36),             # 嘉山大捷小抬推进
        (B["T019"], 0.32),            # 音乐本身进入 64-82s 低响度悬疑段
        (b06_fire - 0.2, 0.36),
        (b06_fire + 0.2, 0.38),       # 灵宝爆发火攻，仍明显让位给 SFX
        (B["T021"], 0.26),
        (B["T023"], 0.25),
        (B["T024"], 0.29),
        (B["T026"], 0.31),            # 灵武即位小幅提振收尾
        (TOTAL - 2.2, 0.28),
        (TOTAL, 0.0),
    ])

    trans_sfx = S.filt(battle, "high", 1200.0) + drums * 0.9 + rout * 0.85 + clip_bus * 0.95
    sfx_mono_abs = np.max(np.abs(trans_sfx), axis=0)
    hop_sc = 240
    sc_ds = np.maximum.reduceat(sfx_mono_abs[:(N // hop_sc) * hop_sc], np.arange(0, (N // hop_sc) * hop_sc, hop_sc))
    sc_ds = sc_ds / (np.percentile(sc_ds, 99.0) + 1e-9)
    sc_env_ds = np.zeros_like(sc_ds)
    cur = 0.0
    for i, v in enumerate(sc_ds):
        c = 0.35 if v > cur else 0.045
        cur = (1.0 - c) * cur + c * min(1.0, v)
        sc_env_ds[i] = cur
    sc_env = np.interp(np.arange(N), np.arange(len(sc_env_ds)) * hop_sc, sc_env_ds)
    duck_gain = np.clip(1.0 - 0.32 * sc_env, 0.68, 1.0)
    bgm_ducked = bgm * base_curve * duck_gain

    mix = sfx + bgm_ducked
    mix = np.tanh(mix * 1.08) / np.tanh(1.08)
    mix = S.fade(mix, 0.05, 0.70)
    pk_mix = float(np.max(np.abs(mix)))
    if pk_mix > 0.89:
        mix = mix * (0.89 / pk_mix)

    def to16(x):
        return (np.clip(x, -1.0, 1.0).T * 32767.0).astype(np.int16)

    wav_out = AUD / "amazon_part2_sfx_bgm_mix.wav"
    wavfile.write(wav_out, SR, to16(mix))
    stems_dir = AUD / "amazon_part2_stems"
    stems_dir.mkdir(parents=True, exist_ok=True)
    wavfile.write(stems_dir / "sfx_all.wav", SR, to16(sfx))
    wavfile.write(stems_dir / "bgm_ducked.wav", SR, to16(bgm_ducked))

    seg_names = ["T011", "T016", "B05", "T019", "CLIP2_GESHUHAN", "B06", "T021", "T022", "T023", "T024", "T026", "CLIP1_SUZONG"]
    starts = [B[k] for k in seg_names] + [TOTAL]
    print("=== Part 2 Beat Loudness Balance (SFX vs Duck-Tamed Amazon BGM) ===")
    for nm, a, b in zip(seg_names, starts[:-1], starts[1:]):
        i0, i1 = int(a * SR), int(b * SR)
        r_sfx = 20 * np.log10(np.sqrt(np.mean(sfx[:, i0:i1] ** 2)) + 1e-9)
        r_bgm = 20 * np.log10(np.sqrt(np.mean(bgm_ducked[:, i0:i1] ** 2)) + 1e-9)
        r_mix = 20 * np.log10(np.sqrt(np.mean(mix[:, i0:i1] ** 2)) + 1e-9)
        print(f"  {nm:5s} {a:6.2f}-{b:6.2f}s | SFX {r_sfx:6.1f} dB | BGM {r_bgm:6.1f} dB | Mix {r_mix:6.1f} dB (SFX-BGM={r_sfx-r_bgm:+.1f} dB)")

    raw_mp4 = OUT / "opening_clip_anshi_part2_amazon_video.mp4"
    part2_mp4 = OUT / "opening_clip_anshi_part2_amazon.mp4"
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([
        ff, "-y", "-loglevel", "error", "-i", str(raw_mp4), "-i", str(wav_out),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", str(part2_mp4),
    ], check=True)
    print(f"Saved Part 2 MP4: {part2_mp4} ({part2_mp4.stat().st_size / 1048576:.2f} MB)")

    # 把 Part 1 (0-46s) 与 Part 2 (46-114.43s) 无缝拼接为完整 1 分 54 秒长片（音轨全程无断点混音）
    p1_raw = OUT / "opening_clip_anshi_amazon_video.mp4"
    p1_sfx_wav = AUD / "amazon_stems" / "sfx_all.wav"
    p1_bgm_wav = AUD / "amazon_stems" / "bgm_ducked.wav"
    full_mp4 = OUT / "anshi_full_114s_amazon.mp4"
    if p1_raw.exists() and p1_sfx_wav.exists() and p1_bgm_wav.exists():
        # 视频无损拼合两个 H.264 母版；音频直接用 Part 1 未淡出端 + Part 2 平滑衔接，避免 46s 出现音量坑
        lst_v = AUD / "concat_video.txt"
        lst_v.write_text(f"file '{p1_raw.as_posix()}'\nfile '{raw_mp4.as_posix()}'\n", encoding="utf-8")
        full_v = OUT / "anshi_full_114s_video.mp4"
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst_v), "-c:v", "copy", str(full_v)], check=True)

        _, s1 = wavfile.read(str(p1_sfx_wav))
        _, b1 = wavfile.read(str(p1_bgm_wav))
        n1 = int(round(BGM_OFFSET_SEC * SR))
        s1f = s1[:n1].T.astype(np.float64) / 32767.0
        # Part 1 BGM 在 44..46s 去掉单独片尾淡出，直接平滑接回原曲在 46.00s 的响度水平
        b1f = b1[:n1].T.astype(np.float64) / 32767.0
        # 用连续原曲 43.5..46.5s 重建衔接区 2 秒避免 46s 处跌落
        bridge_s0 = int(43.5 * SR)
        bridge_n = n1 - bridge_s0
        if bridge_n > 0:
            raw_br = x_b[bridge_s0:n1].T.astype(np.float64) / 32768.0
            raw_br = raw_br - 0.26 * S.filt(raw_br, "band", (1300.0, 3200.0), order=2)
            env_br = np.linspace(0.25, 0.28 * 1.023, bridge_n)
            xf = np.linspace(0.0, 1.0, min(int(0.5 * SR), bridge_n))
            b1f[:, bridge_s0:bridge_s0 + len(xf)] = b1f[:, bridge_s0:bridge_s0 + len(xf)] * (1.0 - xf) + (raw_br[:, :len(xf)] * env_br[:len(xf)]) * xf
            b1f[:, bridge_s0 + len(xf):] = raw_br[:, len(xf):] * env_br[len(xf):]

        full_sfx = np.concatenate([s1f, sfx], axis=1)
        full_bgm = np.concatenate([b1f, bgm_ducked], axis=1)
        full_mix = np.tanh((full_sfx + full_bgm) * 1.08) / np.tanh(1.08)
        full_mix = S.fade(full_mix, 0.10, 0.70)
        pk_f = float(np.max(np.abs(full_mix)))
        if pk_f > 0.89:
            full_mix = full_mix * (0.89 / pk_f)
        full_wav = AUD / "amazon_full_114s_mix.wav"
        wavfile.write(full_wav, SR, to16(full_mix))
        subprocess.run([
            ff, "-y", "-loglevel", "error", "-i", str(full_v), "-i", str(full_wav),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", str(full_mp4),
        ], check=True)
        print(f"Saved seamless full 114s MP4: {full_mp4} ({full_mp4.stat().st_size / 1048576:.2f} MB)")
        shangban_mp4 = OUT / "anshi_shangban_amazon.mp4"
        shutil.copy2(full_mp4, shangban_mp4)
        print(f"Updated 上半 MP4: {shangban_mp4} ({shangban_mp4.stat().st_size / 1048576:.2f} MB)")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    fig, axs = plt.subplots(4, 1, figsize=(16, 9), sharex=True)
    tt = np.arange(N) / float(SR)
    axs[0].plot(tt[::50], bgm_ducked[0, ::50], lw=0.4, color="#457B9D")
    axs[0].set_ylabel("Amazon BGM")
    axs[1].plot(tt[::50], sfx[0, ::50], lw=0.4, color="#E63946")
    axs[1].set_ylabel("战争音效 SFX")
    axs[2].plot(tt[::90], duck_gain[::90], lw=0.8, color="#2A9D8F")
    axs[2].set_ylim(0.55, 1.05)
    axs[2].set_ylabel("Sidechain 闪避")
    axs[3].specgram(mix.mean(0), NFFT=2048, Fs=SR, noverlap=1024, cmap="magma")
    axs[3].set_ylim(0, 8000)
    axs[3].set_ylabel("混音频谱")
    axs[3].set_xlabel("Part 2 时间 (s)")
    for ax in axs:
        for nm, a in zip(seg_names, starts[:-1]):
            ax.axvline(a, color="#D62828", lw=0.9)
    for nm, a in zip(seg_names, starts[:-1]):
        axs[0].text(a + 0.12, axs[0].get_ylim()[1] * 0.80, nm, color="#D62828", fontsize=9)
    fig.suptitle("《安史之乱》Part 2（常山→嘉山→灵宝→长安→灵武）混音核对图")
    fig.tight_layout()
    fig.savefig(AUD / "amazon_part2_mix_timeline.png", dpi=95)
    print("Saved amazon_part2_mix_timeline.png")


def main():
    meta = extract_part2_beats()
    timing = render_part2_video_pipe(meta)
    build_part2_sfx_and_mix(meta, timing)


if __name__ == "__main__":
    main()
