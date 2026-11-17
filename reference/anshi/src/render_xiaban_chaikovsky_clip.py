# -*- coding: utf-8 -*-
"""《安史之乱》下半（含尾声篇）—— 指定 BGM：Chaikovsky.mp3 (48.00s -> 133.07s)
涵盖片段：
  CLIP1_SUZONG (唐肃宗即位 2s) -> T030 -> CLIP3_ANLUSHAN (安禄山遇害 4s) ->
  B10 (太原保卫战) -> B11 (睢阳保卫战) -> T039 -> B13 (香积寺决战) ->
  T041 (收复长安) -> T044 (收复洛阳) -> T047 (史思明复叛·九节度围邺) ->
  B15 (邺城之溃) -> B16 (河阳大捷) -> T062 (邙山·史朝义弑逆) ->
  T068 (昭觉寺再复洛阳) -> B21 (莫州—温泉栅终局) -> T076 (八载乱平·藩镇成形)

输出：
1. output/audio/chaikovsky_xiaban_beats.json
2. output/audio/chaikovsky_xiaban_beat_map.png
3. output/audio/chaikovsky_xiaban_mix_timeline.png
4. output/anshi_xiaban_chaikovsky.mp4     —— 1920x1080 30fps 独立下半成片 (85.07s)
5. output/anshi_xiaban_amazon.mp4         —— 同步更新对应最新“下半”成片副本
6. output/anshi_complete_full_series.mp4  —— 拼合新版上半 (114.43s) + 下半自 T030 起 (83.07s) 完整全篇 (197.50s / 03:17.50)
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
import librosa
import numpy as np
from PIL import Image
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).parent))
from battle_anim import B10Animator, B11Animator, B13Animator, B15Animator, B16Animator, B21Animator
import render_amazon_beat_clip as r1
import render_frame as rf
import render_part2_amazon_clip as p2
import sfx_synth as S
from sfx_synth import SR
from tactical_map import H_PX, W_PX
from terrain import compose_macro_from_scores, compute_smoothed_faction_scores

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
AUD = OUT / "audio"
AUD.mkdir(parents=True, exist_ok=True)
SRC_WAV = AUD / "chaikovsky_48k.wav"
FPS = 30
BGM_OFFSET_SEC = 48.00


def _ensure_src_wav():
    if not SRC_WAV.exists():
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run([
            ff, "-y", "-loglevel", "error", "-i", r"D:\下载\Chaikovsky.mp3",
            "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", str(SRC_WAV),
        ], check=True)
    _, x = wavfile.read(str(SRC_WAV))
    return len(x) / float(SR)


def nearest(arr, target):
    cand = [float(x) for x in arr]
    return min(cand, key=lambda x: abs(x - target))


def extract_chaikovsky_beats():
    bgm_end_sec = _ensure_src_wav()
    y, sr = librosa.load(str(SRC_WAV), sr=22050, mono=True)
    oenv = librosa.onset.onset_strength(y=y, sr=sr)
    on_frames = librosa.onset.onset_detect(onset_envelope=oenv, sr=sr, delta=0.18, wait=4, backtrack=False)
    onsets = librosa.frames_to_time(on_frames, sr=sr)
    ostrs = [float(oenv[min(int(f), len(oenv) - 1)]) for f in on_frames]
    _, b_frames = librosa.beat.beat_track(onset_envelope=oenv, sr=sr)
    beats = librosa.frames_to_time(b_frames, sr=sr)

    beats_seg = [float(t) for t in beats if 47.5 <= t <= bgm_end_sec - 0.5]
    strong = [float(t) for t, s in zip(onsets, ostrs) if 47.5 <= t <= bgm_end_sec - 0.5 and s >= 6.0]
    all_b = strong if len(strong) > 20 else beats_seg

    # 绝对曲库时间戳 (48.00s .. 133.07s, 共 85.07s)
    t_clip1 = 48.000
    t_t030 = 50.000                                  # CLIP1 恰好 60 帧 (2.00s) 切入 T030
    t_clip3 = nearest(beats_seg, 52.13)              # 52.129s -> +0.86s 动手落于 53s 陡升前缘，+2.04s 倒榻精准命中 54.172s 强拍！
    t_b10 = round(float(t_clip3) + 4.000, 4)         # 56.129s（120 帧精准接回 56.169s 重拍切入太原！）
    t_b11 = nearest(beats_seg, 64.67)                # 64.668s -> 睢阳保卫战
    t_t039 = nearest(beats_seg, 74.16)               # 74.165s -> 广平王东征
    t_b13 = nearest(beats_seg, 76.67)                # 76.672s -> 香积寺决战与收复长安
    t_t041 = nearest(beats_seg, 88.17)               # 88.166s -> 收复西京长安
    t_t044 = nearest(beats_seg, 90.67)               # 90.674s -> 收复东京洛阳
    t_t047 = nearest(beats_seg, 93.16)               # 93.158s -> 史思明复叛·九节度围邺
    t_b15 = nearest(beats_seg, 96.18)                # 96.177s -> 相州（邺城）九节度之溃
    t_b16 = nearest(beats_seg, 104.68)               # 104.676s -> 河阳三城保卫战
    t_t062 = nearest(beats_seg, 113.17)              # 113.174s -> 邙山失利·史朝义弑逆
    t_t068 = nearest(beats_seg, 116.68)              # 116.680s -> 昭觉寺大捷再复洛阳
    t_b21 = nearest(beats_seg, 120.16)               # 120.163s -> 莫州—温泉栅平叛终局
    t_t076 = nearest(beats_seg, 129.17)              # 129.173s -> 八载乱平·河朔藩镇成形
    t_end = float(bgm_end_sec)

    b10_cues_abs = {
        "arrows_done": nearest(beats_seg, 57.68),
        "volley": nearest(beats_seg, 58.17),
        "tunnel_smoke": nearest(beats_seg, 58.68),
        "sally_kills": [nearest(beats_seg, 60.16), nearest(beats_seg, 61.16), nearest(beats_seg, 62.16)],
        "chase_kills": [nearest(beats_seg, 63.18), nearest(beats_seg, 63.67)],
    }
    b11_cues_abs = {
        "arrows_done": nearest(beats_seg, 66.66),
        "defender_volley": nearest(beats_seg, 67.18),
        "volley_kill": nearest(beats_seg, 67.66),
        "sally_kill": nearest(beats_seg, 69.17),
        "breach_smoke": nearest(beats_seg, 71.17),
        "wall_deaths": [nearest(beats_seg, 72.17), nearest(beats_seg, 72.68), nearest(beats_seg, 73.17)],
        "banner_fall": nearest(beats_seg, 73.68),
    }
    b13_cues_abs = {
        "arrows_done": nearest(beats_seg, 78.67),
        "modao_hold": nearest(beats_seg, 80.18),
        "east_ambush_kills": [nearest(beats_seg, 81.17), nearest(beats_seg, 81.68), nearest(beats_seg, 82.67)],
        "modao_kills": [nearest(beats_seg, 83.67), nearest(beats_seg, 84.17)],
        "chase_kills": [nearest(beats_seg, 85.17), nearest(beats_seg, 85.68), nearest(beats_seg, 86.68)],
    }
    b15_cues_abs = {
        "arrows_done": nearest(beats_seg, 98.17),
        "volley": nearest(beats_seg, 98.66),
        "raid_smoke": nearest(beats_seg, 99.17),
        "front_kills": [nearest(beats_seg, 100.17), nearest(beats_seg, 100.68), nearest(beats_seg, 101.68)],
        "chase_kills": [nearest(beats_seg, 102.68), nearest(beats_seg, 103.68)],
    }
    b16_cues_abs = {
        "arrows_done": nearest(beats_seg, 106.67),
        "volley": nearest(beats_seg, 107.16),
        "front_kills": [nearest(beats_seg, 108.16), nearest(beats_seg, 109.16), nearest(beats_seg, 109.67)],
        "chase_kills": [nearest(beats_seg, 111.18), nearest(beats_seg, 112.18)],
    }
    b21_cues_abs = {
        "arrows_done": nearest(beats_seg, 122.16),
        "fanyang_volley": nearest(beats_seg, 122.67),
        "chase_kills": [nearest(beats_seg, 124.67), nearest(beats_seg, 126.18), nearest(beats_seg, 127.69)],
        "banner_fall": nearest(beats_seg, 128.17),
    }

    rel3 = lambda x: round(float(x) - BGM_OFFSET_SEC, 4)
    abs_tl = {
        "CLIP1_SUZONG": t_clip1, "T030": t_t030, "CLIP3_ANLUSHAN": t_clip3,
        "B10": t_b10, "B11": t_b11, "T039": t_t039, "B13": t_b13,
        "T041": t_t041, "T044": t_t044, "T047": t_t047,
        "B15": t_b15, "B16": t_b16, "T062": t_t062, "T068": t_t068,
        "B21": t_b21, "T076": t_t076, "END": t_end,
    }
    timeline = {k: rel3(v) for k, v in abs_tl.items()}
    meta = {
        "bgm_offset_sec": BGM_OFFSET_SEC,
        "bgm_end_sec": t_end,
        "abs_timeline": abs_tl,
        "story_timeline": timeline,
        "b10_abs_cues": b10_cues_abs,
        "b11_abs_cues": b11_cues_abs,
        "b13_abs_cues": b13_cues_abs,
        "b15_abs_cues": b15_cues_abs,
        "b16_abs_cues": b16_cues_abs,
        "b21_abs_cues": b21_cues_abs,
    }
    out_json = AUD / "chaikovsky_xiaban_beats.json"
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    sr_w, x_w = wavfile.read(str(SRC_WAV))
    i0, i1 = int(BGM_OFFSET_SEC * sr_w), min(len(x_w), int(t_end * sr_w))
    m_w = x_w[i0:i1].mean(axis=1).astype(np.float32) / 32768.0
    tt_w = np.arange(len(m_w)) / float(sr_w) + BGM_OFFSET_SEC
    fig, ax = plt.subplots(2, 1, figsize=(18, 7), sharex=True)
    ax[0].plot(tt_w[::45], m_w[::45], lw=0.4, color="#2C4966")
    for k, v in abs_tl.items():
        if k == "END":
            continue
        ax[0].axvline(v, color="#D62828", lw=1.2)
        ax[0].text(v + 0.12, 0.82, k, color="#D62828", fontsize=8, rotation=90, va="top", fontweight="bold")
    for grp in [b10_cues_abs, b11_cues_abs, b13_cues_abs, b15_cues_abs, b16_cues_abs, b21_cues_abs]:
        for val in grp.values():
            for tv in (val if isinstance(val, list) else [val]):
                ax[1].axvline(tv, color="#E76F51", ls="--", lw=0.9)
    t_env = librosa.times_like(oenv, sr=sr)
    msk = (t_env >= BGM_OFFSET_SEC) & (t_env <= t_end)
    ax[1].plot(t_env[msk], oenv[msk], color="#264653", lw=0.9)
    ax[0].set_ylabel("Chaikovsky 波形")
    ax[1].set_ylabel("Onset 能量")
    ax[1].set_xlabel("原曲时间 (s)")
    fig.suptitle("《Chaikovsky》48.0–133.1s librosa 卡点提取与安史之乱下半全篇对齐图")
    fig.tight_layout()
    fig.savefig(AUD / "chaikovsky_xiaban_beat_map.png", dpi=95)
    print(f"Saved {out_json} | total_sec={timeline['END']:.2f}s | all_b_cnt={len(all_b)}")
    return meta


def render_xiaban_video_pipe(meta):
    t0 = time.time()
    st = meta["story_timeline"]
    total_sec = float(st["END"])
    total_frames = int(round(total_sec * FPS))

    macro_ticks = [
        "T026", "T027", "T028", "T029", "T030",
        "T035", "T036", "T039", "T040", "T041",
        "T043", "T044", "T046", "T047",
        "T060", "T061", "T062", "T066", "T067", "T068",
        "T072", "T073", "T074", "T075", "T076",
    ]
    scores_by_tick = {}
    for tk in macro_ticks:
        cfg = rf.MACRO_CUSTOM_FRAMES.get(tk)
        ref = cfg["tick_ref"] if cfg else tk
        snap = rf.snaps[ref]
        ov = cfg.get("owner_overrides") if cfg else None
        scores_by_tick[tk] = compute_smoothed_faction_scores(rf.RELIEF, rf.D["cities"], snap["control"], owner_overrides=ov)

    def make_tac_timing(bid, dis, next_key, abs_cues):
        tin = float(st[bid])
        act = tin + dis
        tend = float(st[next_key])
        dur = tend - act
        rel = lambda ta: (float(ta) - BGM_OFFSET_SEC) - act
        hits = []
        for val in abs_cues.values():
            for x in (val if isinstance(val, list) else [val]):
                hits.append(float(x) - BGM_OFFSET_SEC)
        return tin, act, tend, dur, rel, hits

    # B10
    b10_in, b10_act, b10_end, b10_dur, rel10, b10_hits = make_tac_timing("B10", 0.50, "B11", meta["b10_abs_cues"])
    c10 = meta["b10_abs_cues"]
    b10_cues = {
        "arrows_done": max(1.00, rel10(c10["arrows_done"])),
        "siege_advance": 0.65,
        "volley": rel10(c10["volley"]),
        "tunnel_smoke": rel10(c10["tunnel_smoke"]),
        "sally_kills": [rel10(x) for x in c10["sally_kills"]],
        "chase_turn": max(rel10(c10["sally_kills"][2]) + 0.14, rel10(c10["chase_kills"][0]) - 0.72),
        "chase_kills": [rel10(x) for x in c10["chase_kills"]],
        "arrows_dim_at": max(1.15, rel10(c10["arrows_done"]) + 0.15),
        "arrows_restore_at": max(rel10(c10["chase_kills"][1]) + 0.20, b10_dur - 0.65),
        "action_end": b10_dur,
    }

    # B11
    b11_in, b11_act, b11_end, b11_dur, rel11, b11_hits = make_tac_timing("B11", 0.50, "T039", meta["b11_abs_cues"])
    c11 = meta["b11_abs_cues"]
    b11_cues = {
        "arrows_done": max(1.05, rel11(c11["arrows_done"])),
        "siege_press": 0.65,
        "defender_volley": rel11(c11["defender_volley"]),
        "volley_kill": rel11(c11["volley_kill"]),
        "sally_kill": rel11(c11["sally_kill"]),
        "reinforce_assault": max(rel11(c11["sally_kill"]) + 0.60, rel11(c11["breach_smoke"]) - 1.15),
        "breach_smoke": rel11(c11["breach_smoke"]),
        "wall_deaths": [rel11(x) for x in c11["wall_deaths"]],
        "banner_fall": rel11(c11["banner_fall"]),
        "arrows_dim_at": max(1.25, rel11(c11["arrows_done"]) + 0.15),
        "arrows_restore_at": max(rel11(c11["banner_fall"]) + 0.10, b11_dur - 0.42),
        "action_end": b11_dur,
    }

    # B13
    b13_in, b13_act, b13_end, b13_dur, rel13, b13_hits = make_tac_timing("B13", 0.55, "T041", meta["b13_abs_cues"])
    c13 = meta["b13_abs_cues"]
    b13_cues = {
        "arrows_done": max(1.10, rel13(c13["arrows_done"])),
        "clash_start": 0.65,
        "modao_hold": rel13(c13["modao_hold"]),
        "east_ambush_kills": [rel13(x) for x in c13["east_ambush_kills"]],
        "pincer_swing": rel13(c13["east_ambush_kills"][2]) + 0.30,
        "modao_kills": [rel13(x) for x in c13["modao_kills"]],
        "rout_turn": rel13(c13["modao_kills"][1]) + 0.28,
        "chase_kills": [rel13(x) for x in c13["chase_kills"]],
        "arrows_dim_at": max(1.25, rel13(c13["arrows_done"]) + 0.15),
        "arrows_restore_at": max(rel13(c13["chase_kills"][2]) + 0.20, b13_dur - 0.60),
        "action_end": b13_dur,
    }

    # B15
    b15_in, b15_act, b15_end, b15_dur, rel15, b15_hits = make_tac_timing("B15", 0.50, "B16", meta["b15_abs_cues"])
    c15 = meta["b15_abs_cues"]
    b15_cues = {
        "arrows_done": max(1.05, rel15(c15["arrows_done"])),
        "siege_press": 0.65,
        "volley": rel15(c15["volley"]),
        "raid_smoke": rel15(c15["raid_smoke"]),
        "front_kills": [rel15(x) for x in c15["front_kills"]],
        "chase_turn": max(rel15(c15["front_kills"][2]) + 0.16, rel15(c15["chase_kills"][0]) - 0.68),
        "chase_kills": [rel15(x) for x in c15["chase_kills"]],
        "arrows_dim_at": max(1.20, rel15(c15["arrows_done"]) + 0.12),
        "arrows_restore_at": max(rel15(c15["chase_kills"][1]) + 0.22, b15_dur - 0.55),
        "action_end": b15_dur,
    }

    # B16
    b16_in, b16_act, b16_end, b16_dur, rel16, b16_hits = make_tac_timing("B16", 0.50, "T062", meta["b16_abs_cues"])
    c16 = meta["b16_abs_cues"]
    b16_cues = {
        "arrows_done": max(1.05, rel16(c16["arrows_done"])),
        "siege_press": 0.60,
        "volley": rel16(c16["volley"]),
        "front_kills": [rel16(x) for x in c16["front_kills"]],
        "chase_turn": max(rel16(c16["front_kills"][2]) + 0.18, rel16(c16["chase_kills"][0]) - 0.72),
        "chase_kills": [rel16(x) for x in c16["chase_kills"]],
        "arrows_dim_at": max(1.20, rel16(c16["arrows_done"]) + 0.12),
        "arrows_restore_at": max(rel16(c16["chase_kills"][1]) + 0.22, b16_dur - 0.55),
        "action_end": b16_dur,
    }

    # B21
    b21_in, b21_act, b21_end, b21_dur, rel21, b21_hits = make_tac_timing("B21", 0.50, "T076", meta["b21_abs_cues"])
    c21 = meta["b21_abs_cues"]
    b21_cues = {
        "arrows_done": max(1.05, rel21(c21["arrows_done"])),
        "pursuit_start": 0.60,
        "fanyang_volley": rel21(c21["fanyang_volley"]),
        "chase_kills": [rel21(x) for x in c21["chase_kills"]],
        "banner_fall": rel21(c21["banner_fall"]),
        "arrows_dim_at": max(1.20, rel21(c21["arrows_done"]) + 0.12),
        "arrows_restore_at": max(rel21(c21["banner_fall"]) + 0.10, b21_dur - 0.50),
        "action_end": b21_dur,
    }

    segments = [
        {"kind": "CLIP",  "id": "CLIP1_SUZONG",   "clip_key": "CLIP1", "t0": st["CLIP1_SUZONG"], "t1": st["T030"], "dis_in": 0.0},
        {"kind": "MACRO", "id": "T030",           "t0": st["T030"],           "t1": st["CLIP3_ANLUSHAN"], "move_end": st["T030"] + 1.65, "chain": ["T026", "T027", "T028", "T029", "T030"], "dis_in": 0.35},
        {"kind": "CLIP",  "id": "CLIP3_ANLUSHAN", "clip_key": "CLIP3", "t0": st["CLIP3_ANLUSHAN"], "t1": st["B10"], "dis_in": 0.0},
        {"kind": "TAC",   "id": "B10",            "t0": b10_in, "t1": b10_end, "act": b10_act, "dis": 0.50, "arr_dur": b10_cues["arrows_done"], "hits": b10_hits},
        {"kind": "TAC",   "id": "B11",            "t0": b11_in, "t1": b11_end, "act": b11_act, "dis": 0.50, "arr_dur": b11_cues["arrows_done"], "hits": b11_hits},
        {"kind": "MACRO", "id": "T039",           "t0": st["T039"], "t1": st["B13"], "move_end": st["T039"] + 1.95, "chain": ["T035", "T036", "T039"], "dis_in": 0.40},
        {"kind": "TAC",   "id": "B13",            "t0": b13_in, "t1": b13_end, "act": b13_act, "dis": 0.55, "arr_dur": b13_cues["arrows_done"], "hits": b13_hits},
        {"kind": "MACRO", "id": "T041",           "t0": st["T041"], "t1": st["T044"], "move_end": st["T041"] + 1.95, "chain": ["T039", "T040", "T041"], "dis_in": 0.40},
        {"kind": "MACRO", "id": "T044",           "t0": st["T044"], "t1": st["T047"], "move_end": st["T044"] + 1.95, "chain": ["T041", "T043", "T044"], "dis_in": 0.0},
        {"kind": "MACRO", "id": "T047",           "t0": st["T047"], "t1": st["B15"],  "move_end": st["T047"] + 2.25, "chain": ["T044", "T046", "T047"], "dis_in": 0.0},
        {"kind": "TAC",   "id": "B15",            "t0": b15_in, "t1": b15_end, "act": b15_act, "dis": 0.50, "arr_dur": b15_cues["arrows_done"], "hits": b15_hits},
        {"kind": "TAC",   "id": "B16",            "t0": b16_in, "t1": b16_end, "act": b16_act, "dis": 0.50, "arr_dur": b16_cues["arrows_done"], "hits": b16_hits},
        {"kind": "MACRO", "id": "T062",           "t0": st["T062"], "t1": st["T068"], "move_end": st["T062"] + 2.40, "chain": ["T060", "T061", "T062"], "dis_in": 0.40},
        {"kind": "MACRO", "id": "T068",           "t0": st["T068"], "t1": st["B21"],  "move_end": st["T068"] + 2.40, "chain": ["T062", "T066", "T067", "T068"], "dis_in": 0.0},
        {"kind": "TAC",   "id": "B21",            "t0": b21_in, "t1": b21_end, "act": b21_act, "dis": 0.50, "arr_dur": b21_cues["arrows_done"], "hits": b21_hits},
        {"kind": "MACRO", "id": "T076",           "t0": st["T076"], "t1": st["END"],  "move_end": st["T076"] + 2.40, "chain": ["T072", "T073", "T074", "T075", "T076"], "dis_in": 0.40},
    ]

    overlays = {s["id"]: r1._extract_macro_overlays(s["id"]) for s in segments if s["kind"] == "MACRO"}
    clip1_frames, _ = p2._load_external_clip(p2.CLIP1_SUZONG_MP4, 60)
    clip3_frames, _ = p2._load_external_clip(p2.CLIP3_ANLUSHAN_MP4, 120)
    clips_frames = {"CLIP1": clip1_frames, "CLIP3": clip3_frames}

    anims = {}
    for bid, cls, cues in [
        ("B10", B10Animator, b10_cues),
        ("B11", B11Animator, b11_cues),
        ("B13", B13Animator, b13_cues),
        ("B15", B15Animator, b15_cues),
        ("B16", B16Animator, b16_cues),
        ("B21", B21Animator, b21_cues),
    ]:
        an = cls(arrow_renderer=r1._render_tactical_arrows_rgba, cues=cues)
        anims[bid] = (an, an.frame(0.0, arrow_prog=0.0))

    raw_mp4 = OUT / "anshi_xiaban_chaikovsky_video.mp4"
    tail_mp4 = OUT / "anshi_xiaban_from_t030_video.mp4"
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    ff_base = [
        ff, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W_PX}x{H_PX}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
    ]
    proc = subprocess.Popen(ff_base + [str(raw_mp4)], stdin=subprocess.PIPE)
    proc_tail = subprocess.Popen(ff_base + [str(tail_mp4)], stdin=subprocess.PIPE)

    seg_idx = 0
    cur_hold_frame = None
    cur_hold_seg = None
    prev_seg_end = None
    fade_out_sec = 1.00
    t030_start_frame = int(round(st["T030"] * FPS))

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
            if seg["kind"] == "CLIP":
                clip_arr = clips_frames[seg["clip_key"]]
                idx_f = min(len(clip_arr) - 1, max(0, int(round((t - seg["t0"]) * FPS))))
                img = clip_arr[idx_f]
                cur_hold_frame = img
            elif seg["kind"] == "MACRO":
                tk = seg["id"]
                below, above = overlays[tk]
                t_rel = t - seg["t0"]
                move_dur = max(0.05, seg["move_end"] - seg["t0"])
                e = r1._ease_io(t_rel / move_dur)
                is_static_hold = (t >= seg["move_end"] and t_rel >= seg["dis_in"])
                if is_static_hold and cur_hold_seg == tk and cur_hold_frame is not None:
                    img = cur_hold_frame
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
                    img = r1._beat_punch(img, t, seg["hits"], boost=0.068, width=0.11)
                    cur_hold_frame = img

            if t >= total_sec - fade_out_sec:
                fo = 1.0 - r1._ease_io((t - (total_sec - fade_out_sec)) / fade_out_sec)
                img = np.clip(img.astype(np.float32) * fo, 0, 255).astype(np.uint8)

            b_img = img.tobytes()
            proc.stdin.write(b_img)
            if frame >= t030_start_frame:
                proc_tail.stdin.write(b_img)
    finally:
        for pr in (proc, proc_tail):
            if pr.stdin:
                pr.stdin.close()
            ret = pr.wait()
            if ret != 0:
                raise RuntimeError(f"FFmpeg video pipe failed with code {ret}")

    timing_out = {
        "fps": FPS,
        "total_frames": total_frames,
        "t030_start_frame": t030_start_frame,
        "duration_sec": total_sec,
        "beats": {s["id"]: {"start_sec": float(s["t0"]), "end_sec": float(s["t1"])} for s in segments},
        "tac_actions": {
            bid: {
                "act": float({"B10": b10_act, "B11": b11_act, "B13": b13_act, "B15": b15_act, "B16": b16_act, "B21": b21_act}[bid]),
                "events": [(float(et), str(ek), float(ex)) for et, ek, ex in anims[bid][0].events],
            }
            for bid in ["B10", "B11", "B13", "B15", "B16", "B21"]
        },
    }
    with open(AUD / "chaikovsky_xiaban_sync_timing.json", "w", encoding="utf-8") as fh:
        json.dump(timing_out, fh, ensure_ascii=False, indent=2)
    print(f"Piped 下半 video: {raw_mp4} ({total_frames} frames @ {FPS}fps = {total_sec:.2f}s) in {time.time() - t0:.1f}s")
    return timing_out


def _place_battle_events(battle, rout, drums, rng, events, act_t, retreat_dur=3.0):
    for ev_t, ev_kind, ev_x in events:
        abs_t = act_t + ev_t
        pan = float(np.clip((ev_x / 1920.0) * 2.0 - 1.0, -0.85, 0.85))
        if ev_kind == "slash":
            S.place(battle, S.blade_cleave(rng), abs_t - 0.04, 0.90, pan)
            S.place(battle, S.sword_clash(rng), abs_t, 0.50, pan)
        elif ev_kind == "death":
            S.place(battle, S.body_fall(rng), abs_t + 0.04, 0.78, pan)
            S.place(battle, S.shout(rng, 0.38, rng.uniform(145, 225), "o", "fall"), abs_t, 0.56, pan)
        elif ev_kind == "volley":
            S.place(battle, S.arrow_volley(rng, 32), abs_t - 0.10, 0.86, pan)
        elif ev_kind == "tunnel_blast":
            S.place(battle, S.timber_crash(rng), abs_t - 0.05, 0.95, pan)
            S.place(drums, S.war_drum(rng, 38, bright=0.80), abs_t, 0.85, pan)
            S.place(battle, S.fade(S.fire(rng, 2.2), 0.12, 1.0), abs_t + 0.05, 0.65, pan)
        elif ev_kind == "breach_blast":
            S.place(battle, S.timber_crash(rng), abs_t - 0.05, 0.96, pan)
            S.place(battle, S.shield_thud(rng), abs_t + 0.02, 0.78, pan)
            S.place(battle, S.fade(S.fire(rng, 2.4), 0.10, 1.1), abs_t + 0.08, 0.68, pan)
        elif ev_kind == "banner_fall":
            S.place(battle, S.timber_crash(rng), abs_t - 0.05, 0.92, pan)
            S.place(drums, S.war_horn(rng, 76, 2.1, 4), abs_t + 0.08, 0.50, pan)
            S.place(rout, S.distance(S.crowd(rng, 1.6, 24, f0_range=(155, 250), contour="fall"), 0.55), abs_t + 0.10, 0.52, pan)
        elif ev_kind == "gong_retreat":
            for k in range(5):
                S.place(rout, S.gong_clang(rng, 540), abs_t + k * 0.25, 0.42 * (1 - 0.08 * k), pan)
            S.place(rout, S.fade(S.running_retreat(rng, retreat_dur, 24), 0.25, 0.9), abs_t + 0.22, 0.74, pan)


def build_xiaban_sfx_and_mix(meta, timing):
    B = {k: v["start_sec"] for k, v in timing["beats"].items()}
    TOTAL = float(timing["duration_sec"])
    N = int(round(TOTAL * SR))
    rng = np.random.default_rng(763)

    def bus():
        return np.zeros((2, N))

    amb, drums, battle, rout = bus(), bus(), bus(), bus()
    ta = timing["tac_actions"]

    # 1. 环境风声
    w = S.wind_bed(rng, TOTAL)
    w *= S.envelope_points(N, [
        (0.0, 0.05), (B["T030"], 0.09), (B["B10"], 0.08), (B["B11"], 0.11),
        (B["B13"], 0.08), (B["B15"], 0.15), (B["B16"], 0.10), (B["B21"], 0.09), (TOTAL, 0.05),
    ])
    amb += w

    # 2. T030（安庆绪弑逆前奏）+ B10 太原 + B11 睢阳
    S.place(drums, S.war_drum(rng, 46, bright=0.85), B["T030"] + 0.05, 0.78, -0.15)
    S.place(battle, S.distance(S.fire(rng, 1.5), 0.55), B["T030"] + 0.25, 0.42, -0.35)

    for k in range(3):
        S.place(drums, S.war_drum(rng, 58), B["B10"] + 0.55 * k, 0.54, 0.15)
    S.place(battle, S.fade(S.gallop(rng, 2.0, 10, rumble=0.45), 0.2, 0.6), ta["B10"]["act"] + 0.55, 0.52, 0.35)
    S.place(battle, S.fade(S.melee_bed(rng, 3.4, 8.0), 0.3, 0.8), ta["B10"]["act"] + 2.40, 0.68, 0.15)
    _place_battle_events(battle, rout, drums, rng, ta["B10"]["events"], ta["B10"]["act"], retreat_dur=2.4)

    for k in range(3):
        S.place(drums, S.war_drum(rng, 48, bright=0.85), B["B11"] + 0.58 * k, 0.56, -0.35)
    S.place(battle, S.distance(S.melee_bed(rng, 3.8, 9.0) + 0.45 * S.crowd(rng, 3.8, 28), 0.72), ta["B11"]["act"] + 4.40, 0.72, 0.0)
    _place_battle_events(battle, rout, drums, rng, ta["B11"]["events"], ta["B11"]["act"], retreat_dur=2.2)

    # 3. T039 + B13 香积寺 + T041/T044 收复两京
    for k in range(3):
        S.place(drums, S.war_drum(rng, 64, bright=1.35), B["T039"] + 0.58 * k, 0.68, 0.0)
    S.place(drums, S.war_horn(rng, 124, 2.0, 4), B["T039"] + 0.15, 0.54, -0.20)
    S.place(battle, S.fade(S.gallop(rng, 2.3, 12, rumble=0.58), 0.2, 0.5), B["T039"] + 0.20, 0.58)

    S.place(drums, S.war_drum(rng, 66, bright=1.40), B["B13"] + 0.10, 0.82, 0.0)
    S.place(battle, S.fade(S.gallop(rng, 3.8, 14, rumble=0.60), 0.25, 0.7), ta["B13"]["act"] + 0.50, 0.64, 0.40)
    S.place(battle, S.fade(S.melee_bed(rng, 4.8, 10.5), 0.35, 0.9), ta["B13"]["act"] + 2.90, 0.78, 0.0)
    _place_battle_events(battle, rout, drums, rng, ta["B13"]["events"], ta["B13"]["act"], retreat_dur=2.8)

    for tk in ("T041", "T044"):
        for k in range(3):
            S.place(drums, S.war_drum(rng, 68, bright=1.42), B[tk] + 0.58 * k, 0.70, 0.0)
        S.place(drums, S.war_horn(rng, 138, 2.0, 4), B[tk] + 0.10, 0.52, 0.15)
        S.place(battle, S.distance(S.crowd(rng, 2.0, 32, f0_range=(175, 300), contour="rise"), 0.56), B[tk] + 0.35, 0.54)

    # 4. 尾声篇：T047 围邺 -> B15 邺城之溃（大风沙尘+火烧粮道） -> B16 河阳大捷 -> T062/T068 -> B21 -> T076
    for k in range(4):
        S.place(drums, S.war_drum(rng, 52, bright=1.05), B["T047"] + 0.65 * k, 0.62, 0.0)
    S.place(drums, S.war_horn(rng, 110, 2.2, 4), B["T047"] + 0.20, 0.52, 0.20)
    S.place(battle, S.fade(S.gallop(rng, 2.6, 12, rumble=0.52), 0.25, 0.6), B["T047"] + 0.35, 0.52)

    S.place(drums, S.war_drum(rng, 44, bright=0.90), B["B15"] + 0.10, 0.78, -0.15)
    S.place(battle, S.fade(S.gallop(rng, 3.8, 15, rumble=0.68), 0.25, 0.7), ta["B15"]["act"] + 1.80, 0.70, 0.25)
    S.place(battle, S.fade(S.melee_bed(rng, 4.2, 9.5), 0.3, 0.8), ta["B15"]["act"] + 2.40, 0.74, -0.20)
    _place_battle_events(battle, rout, drums, rng, ta["B15"]["events"], ta["B15"]["act"], retreat_dur=2.8)

    for k in range(3):
        S.place(drums, S.war_drum(rng, 62, bright=1.30), B["B16"] + 0.58 * k, 0.68, -0.10)
    S.place(battle, S.fade(S.gallop(rng, 3.8, 14, rumble=0.58), 0.25, 0.7), ta["B16"]["act"] + 1.40, 0.66, 0.0)
    S.place(battle, S.fade(S.melee_bed(rng, 4.0, 9.0), 0.3, 0.8), ta["B16"]["act"] + 2.40, 0.72, 0.15)
    _place_battle_events(battle, rout, drums, rng, ta["B16"]["events"], ta["B16"]["act"], retreat_dur=2.6)

    S.place(drums, S.war_drum(rng, 44, bright=0.80), B["T062"] + 0.08, 0.84, -0.25)
    S.place(drums, S.war_horn(rng, 82, 2.2, 4), B["T062"] + 0.25, 0.48, 0.15)
    S.place(battle, S.distance(S.crowd(rng, 2.0, 26, f0_range=(150, 240), contour="fall"), 0.58), B["T062"] + 0.60, 0.48)

    for k in range(4):
        S.place(drums, S.war_drum(rng, 66, bright=1.40), B["T068"] + 0.62 * k, 0.72, 0.0)
    S.place(drums, S.war_horn(rng, 134, 2.3, 4), B["T068"] + 0.15, 0.56, -0.15)
    S.place(battle, S.fade(S.gallop(rng, 3.0, 14, rumble=0.60), 0.25, 0.7), B["T068"] + 0.35, 0.58)

    S.place(battle, S.fade(S.gallop(rng, 4.6, 14, rumble=0.55), 0.25, 0.8), ta["B21"]["act"] + 0.55, 0.64, 0.10)
    S.place(battle, S.fade(S.melee_bed(rng, 3.5, 8.0), 0.3, 0.8), ta["B21"]["act"] + 3.00, 0.68, 0.20)
    _place_battle_events(battle, rout, drums, rng, ta["B21"]["events"], ta["B21"]["act"], retreat_dur=2.2)

    S.place(drums, S.war_drum(rng, 58, bright=1.15), B["T076"] + 0.08, 0.82, 0.0)
    S.place(drums, S.war_horn(rng, 142, 2.6, 4), B["T076"] + 0.20, 0.50, 0.0)
    S.place(battle, S.distance(S.crowd(rng, 2.4, 28, f0_range=(175, 285), contour="rise"), 0.58), B["T076"] + 0.55, 0.46)

    # 5. SFX 校准与柔和限幅至 0.58 + 嵌入上传片段原生音轨（视频1肃宗、视频3安禄山遇害）
    amb = S.reverb(amb, rng, 1.0, 0.15)
    drums = S.reverb(drums, rng, 1.8, 0.26)
    battle = S.reverb(battle, rng, 1.4, 0.22)
    rout = S.reverb(rout, rng, 1.6, 0.25)
    sfx_raw = amb * 0.90 + drums * 0.78 + battle * 0.92 + rout * 0.94
    sfx_raw = S.filt(sfx_raw, "high", 30.0)
    sfx_ref = np.percentile(np.abs(sfx_raw), 99.7) + 1e-9
    sfx = np.tanh((sfx_raw / sfx_ref * 0.68) * 1.25) / np.tanh(1.25)
    sfx = S.norm(sfx, 0.58)

    _, clip1_aud = p2._load_external_clip(p2.CLIP1_SUZONG_MP4, 60)
    _, clip3_aud = p2._load_external_clip(p2.CLIP3_ANLUSHAN_MP4, 120)
    clip_bus = np.zeros_like(sfx)
    S.place(clip_bus, clip1_aud, B["CLIP1_SUZONG"], 1.0)
    S.place(clip_bus, clip3_aud, B["CLIP3_ANLUSHAN"], 1.0)
    sfx = sfx + clip_bus
    pk_sfx = float(np.max(np.abs(sfx)))
    if pk_sfx > 0.60:
        sfx = np.tanh((sfx / pk_sfx) * 1.15) / np.tanh(1.15) * 0.58
    sfx = S.fade(sfx, 0.04, 1.20)

    # 6. Chaikovsky 48.00-133.07s：中频空让 (-2.5dB 1.3-3.2kHz) + 响度包络控制 + 瞬态侧链闪避
    _, x_b = wavfile.read(str(SRC_WAV))
    i0 = int(round(BGM_OFFSET_SEC * SR))
    bgm_seg = np.zeros((2, N))
    take = min(N, max(0, len(x_b) - i0))
    if take > 0:
        bgm_seg[:, :take] = x_b[i0:i0 + take].T.astype(np.float64) / 32768.0
    mid_pocket = S.filt(bgm_seg, "band", (1300.0, 3200.0), order=2)
    bgm = bgm_seg - 0.26 * mid_pocket

    # 注意 Chaikovsky 48-52.8s 本身较轻 (-21dB)，53.1s 后持续饱满 (-10dB RMS)
    # 所以前奏 48-52.8s 略抬至 0.42 维持存在感，53.1s 后稳定压在 0.23-0.28（~ -21..-20dB RMS），绝不盖过 SFX
    base_curve = S.envelope_points(N, [
        (0.0, 0.72),                   # 48.0s 原曲前奏偏轻 (-21dB)，抬至 -24dB 保持弦乐存在感
        (B["CLIP3_ANLUSHAN"] + 0.65, 0.72),  # 52.8s 遇害悬念推进
        (B["CLIP3_ANLUSHAN"] + 1.05, 0.25),  # 53.2s 骤强后迅速压稳，突出安禄山惨叫与战场音效
        (B["B10"], 0.24),
        (B["B11"], 0.22),
        (B["T039"], 0.27),
        (B["B13"], 0.28),              # 香积寺小抬
        (B["T047"], 0.24),
        (B["B15"], 0.24),
        (B["B16"], 0.26),
        (B["T062"], 0.24),
        (B["B21"], 0.26),
        (B["T076"], 0.28),
        (TOTAL - 2.6, 0.26),
        (TOTAL - 0.15, 0.05),
        (TOTAL, 0.0),
    ])

    trans_sfx = S.filt(battle, "high", 1200.0) + drums * 0.9 + rout * 0.85 + clip_bus * 1.15
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

    mix = np.tanh((sfx + bgm_ducked) * 1.08) / np.tanh(1.08)
    mix = S.fade(mix, 0.05, 1.25)
    pk_mix = float(np.max(np.abs(mix)))
    if pk_mix > 0.89:
        mix = mix * (0.89 / pk_mix)

    def to16(x):
        return (np.clip(x, -1.0, 1.0).T * 32767.0).astype(np.int16)

    wav_out = AUD / "chaikovsky_xiaban_sfx_bgm_mix.wav"
    wavfile.write(wav_out, SR, to16(mix))
    stems_dir = AUD / "chaikovsky_xiaban_stems"
    stems_dir.mkdir(parents=True, exist_ok=True)
    wavfile.write(stems_dir / "sfx_all.wav", SR, to16(sfx))
    wavfile.write(stems_dir / "bgm_ducked.wav", SR, to16(bgm_ducked))

    seg_names = list(B.keys())
    starts = [B[k] for k in seg_names] + [TOTAL]
    print("=== Chaikovsky 下半 Loudness Balance (SFX vs Duck-Tamed BGM) ===")
    for nm, a, b in zip(seg_names, starts[:-1], starts[1:]):
        i0s, i1s = int(a * SR), int(b * SR)
        r_sfx = 20 * np.log10(np.sqrt(np.mean(sfx[:, i0s:i1s] ** 2)) + 1e-9)
        r_bgm = 20 * np.log10(np.sqrt(np.mean(bgm_ducked[:, i0s:i1s] ** 2)) + 1e-9)
        r_mix = 20 * np.log10(np.sqrt(np.mean(mix[:, i0s:i1s] ** 2)) + 1e-9)
        print(f"  {nm:14s} {a:6.2f}-{b:6.2f}s | SFX {r_sfx:6.1f} dB | BGM {r_bgm:6.1f} dB | Mix {r_mix:6.1f} dB (SFX-BGM={r_sfx-r_bgm:+.1f} dB)")

    raw_mp4 = OUT / "anshi_xiaban_chaikovsky_video.mp4"
    xiaban_mp4 = OUT / "anshi_xiaban_chaikovsky.mp4"
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([
        ff, "-y", "-loglevel", "error", "-i", str(raw_mp4), "-i", str(wav_out),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", str(xiaban_mp4),
    ], check=True)
    shutil.copy2(xiaban_mp4, OUT / "anshi_xiaban_amazon.mp4")
    print(f"Saved 下半 MP4: {xiaban_mp4} ({xiaban_mp4.stat().st_size / 1048576:.2f} MB) + copied to anshi_xiaban_amazon.mp4")

    # 7. 拼接新版上半 (0-114.43s, 含哥舒翰出潼关 6s + 唐肃宗即位 2s) + 下半自 T030 起 (83.07s) -> 完整全集 (197.50s)
    p1_raw = OUT / "opening_clip_anshi_amazon_video.mp4"
    p2_raw = OUT / "opening_clip_anshi_part2_amazon_video.mp4"
    tail_raw = OUT / "anshi_xiaban_from_t030_video.mp4"
    p1_sfx_w = AUD / "amazon_stems" / "sfx_all.wav"
    p1_bgm_w = AUD / "amazon_stems" / "bgm_ducked.wav"
    p2_sfx_w = AUD / "amazon_part2_stems" / "sfx_all.wav"
    p2_bgm_w = AUD / "amazon_part2_stems" / "bgm_ducked.wav"
    complete_mp4 = OUT / "anshi_complete_full_series.mp4"

    if all(p.exists() for p in [p1_raw, p2_raw, tail_raw, p1_sfx_w, p1_bgm_w, p2_sfx_w, p2_bgm_w]):
        lst = AUD / "concat_full_series.txt"
        lst.write_text(f"file '{p1_raw.as_posix()}'\nfile '{p2_raw.as_posix()}'\nfile '{tail_raw.as_posix()}'\n", encoding="utf-8")
        full_v = OUT / "anshi_complete_full_series_video.mp4"
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "copy", str(full_v)], check=True)

        _, x_amz = wavfile.read(str(AUD / "amazon_48k.wav"))
        _, s1 = wavfile.read(str(p1_sfx_w))
        _, b1 = wavfile.read(str(p1_bgm_w))
        _, s2 = wavfile.read(str(p2_sfx_w))
        _, b2 = wavfile.read(str(p2_bgm_w))

        n1 = int(round(46.00 * SR))
        s1f = s1[:n1].T.astype(np.float64) / 32767.0
        b1f = b1[:n1].T.astype(np.float64) / 32767.0
        br1_s0 = int(43.5 * SR)
        if n1 > br1_s0:
            raw_br1 = x_amz[br1_s0:n1].T.astype(np.float64) / 32768.0
            raw_br1 = raw_br1 - 0.26 * S.filt(raw_br1, "band", (1300.0, 3200.0), order=2)
            env_br1 = np.linspace(0.25, 0.28 * 1.023, n1 - br1_s0)
            xf1 = np.linspace(0.0, 1.0, min(int(0.5 * SR), n1 - br1_s0))
            b1f[:, br1_s0:br1_s0 + len(xf1)] = b1f[:, br1_s0:br1_s0 + len(xf1)] * (1.0 - xf1) + (raw_br1[:, :len(xf1)] * env_br1[:len(xf1)]) * xf1
            b1f[:, br1_s0 + len(xf1):] = raw_br1[:, len(xf1):] * env_br1[len(xf1):]

        s2f = s2.T.astype(np.float64) / 32767.0
        b2f = b2.T.astype(np.float64) / 32767.0
        # 下半自 T030 样本起点切出（消除 CLIP1_SUZONG 重复），并用 0.40s 柔和淡入切换 BGM 至 Chaikovsky
        cut_s = int(round(float(B["T030"]) * SR))
        s3_tail = sfx[:, cut_s:].copy()
        b3_tail = bgm_ducked[:, cut_s:].copy()
        fi = min(int(0.45 * SR), b3_tail.shape[1])
        b3_tail[:, :fi] *= np.linspace(0.0, 1.0, fi) ** 1.2

        full_sfx = np.concatenate([s1f, s2f, s3_tail], axis=1)
        full_bgm = np.concatenate([b1f, b2f, b3_tail], axis=1)
        full_mix = np.tanh((full_sfx + full_bgm) * 1.08) / np.tanh(1.08)
        full_mix = S.fade(full_mix, 0.10, 1.50)
        pk_f = float(np.max(np.abs(full_mix)))
        if pk_f > 0.89:
            full_mix = full_mix * (0.89 / pk_f)

        full_wav = AUD / "anshi_complete_full_series_mix.wav"
        wavfile.write(full_wav, SR, to16(full_mix))
        subprocess.run([
            ff, "-y", "-loglevel", "error", "-i", str(full_v), "-i", str(full_wav),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", str(complete_mp4),
        ], check=True)
        print(f"Saved 完整全篇 MP4: {complete_mp4} ({complete_mp4.stat().st_size / 1048576:.2f} MB)")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    fig, axs = plt.subplots(4, 1, figsize=(18, 9), sharex=True)
    tt = np.arange(N) / float(SR)
    axs[0].plot(tt[::55], bgm_ducked[0, ::55], lw=0.4, color="#457B9D")
    axs[0].set_ylabel("Chaikovsky BGM")
    axs[1].plot(tt[::55], sfx[0, ::55], lw=0.4, color="#E63946")
    axs[1].set_ylabel("战争/剧场 SFX")
    axs[2].plot(tt[::95], duck_gain[::95], lw=0.8, color="#2A9D8F")
    axs[2].set_ylim(0.55, 1.05)
    axs[2].set_ylabel("Sidechain 闪避")
    axs[3].specgram(mix.mean(0), NFFT=2048, Fs=SR, noverlap=1024, cmap="magma")
    axs[3].set_ylim(0, 8000)
    axs[3].set_ylabel("混音频谱")
    axs[3].set_xlabel("下半时间 (s)")
    for ax in axs:
        for nm, a in zip(seg_names, starts[:-1]):
            ax.axvline(a, color="#D62828", lw=0.8)
    for nm, a in zip(seg_names, starts[:-1]):
        axs[0].text(a + 0.10, axs[0].get_ylim()[1] * 0.80, nm, color="#D62828", fontsize=8, rotation=90, va="top")
    fig.suptitle("《安史之乱》下半+尾声篇（Chaikovsky 48–133s + 原声剧场片段）混音核对图")
    fig.tight_layout()
    fig.savefig(AUD / "chaikovsky_xiaban_mix_timeline.png", dpi=95)
    print("Saved chaikovsky_xiaban_mix_timeline.png")


def main():
    meta = extract_chaikovsky_beats()
    timing = render_xiaban_video_pipe(meta)
    build_xiaban_sfx_and_mix(meta, timing)


if __name__ == "__main__":
    main()
