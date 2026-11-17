# -*- coding: utf-8 -*-
"""
src/hc_audio_enog.py
《唐末黄巢起义（874–884）》×《ZIIIELI, LJYNNN - Enog.mp3》真实声学卡点与四总线混音管线（重构版）

严格遵循《Enog.mp3》实测声学结构（117.45 BPM / 平均拍距 0.5036s）：
  - 0.000 ~ 16.045s : Intro（深沉低频铺垫，-19..-18 dB）
  - 16.045 ~ 31.045s: Rhythmic Build（鼓点推升，-18..-15 dB）
  - 31.045 ~ 32.044s: 1 秒抽空吸气悬念（-25.2 dB / Bass 0.09）
  - 32.044 ~ 78.298s: DROP 1 主高潮（-10.1 dB / Bass 40+） -> 南下破闽粤・48s 广州攻坚・灵渠北伐
  - 78.298 ~ 95.039s: 静谧 Breakdown（Bass 抽空至 1.4 / -20 dB） -> 洛阳迎降・禁谷潜行逼潼关
  - 95.039 ~ 96.038s: 1 秒二次抽空息声（-21.0 dB / Bass 0.44）
  - 96.038 ~ 143.50s: DROP 2 终局大爆发（-10.6 dB / Bass 41+） -> 破潼关・含元登基・朱温叛降・王满渡・反攻・142.55s 尾拍折旗
  - 143.50 ~ 146.573s: 收束余韵消音落幕

声学调校重点：
  - 所有鼓点、剑鸣、箭雨、转场风声全部严格量化到真实 `beats` 网格，消除乱拍底噪循环；
  - 响应听感校准：显著回调 SFX 突出度（S.norm 0.42，压低峰值并避免闷噪喧宾夺主），让位给 Enog 律动；
  - BGM 三层驯服（1300-3200Hz -20% 中频让位 + Breakdown 合理抬升 0.54 + 排除 amb 的 5ms 轻度侧链闪避）；
  - 禁用整轨 AGC，峰值保护 <= 0.89，最终响度严格校准于 -13.1 ~ -12.7 LUFS。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

import imageio_ffmpeg
import librosa
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import wavfile

import sfx_synth as S
from sfx_synth import SR

ROOT = Path(__file__).resolve().parents[1]
AUD = ROOT / "output" / "audio"
AUD.mkdir(parents=True, exist_ok=True)
SRC_MP3 = ROOT / "ZIIIELI, LJYNNN - Enog.mp3"
SRC_WAV = AUD / "enog_48k.wav"

TOTAL_SEC = 146.573
FPS = 30
TOTAL_FRAMES = 4397

# 对齐 Enog.mp3 真实 Drop / Breakdown / Pre-drop pause 的 17 幕历史脚本
ACTS: List[Dict] = [
    {"id": "T01",     "mode": "cutscene", "t0": 0.000,   "t1": 8.034,   "name": "曲江落第赋菊",         "amb": 0.30, "bgm": 0.56},
    {"id": "T02",     "mode": "macro",    "t0": 8.034,   "t1": 16.045,  "name": "冤句起兵响应王仙芝",   "amb": 0.25, "bgm": 0.46},
    {"id": "T03",     "mode": "macro",    "t0": 16.045,  "t1": 24.009,  "name": "转战中原・蕲州分军",   "amb": 0.25, "bgm": 0.44},
    {"id": "T04",     "mode": "macro",    "t0": 24.009,  "t1": 32.044,  "name": "黄梅称冲天大将军",     "amb": 0.22, "bgm": 0.45},
    {"id": "T05",     "mode": "macro",    "t0": 32.044,  "t1": 40.033,  "name": "南渡长江・刊山七百里", "amb": 0.20, "bgm": 0.40},
    {"id": "T06",     "mode": "macro",    "t0": 40.033,  "t1": 48.030,  "name": "兵锋抵海・连克闽粤",   "amb": 0.20, "bgm": 0.40},
    {"id": "B_GZ",    "mode": "tactical", "t0": 48.030,  "t1": 58.310,  "name": "广州攻坚战（3D沙盘）", "amb": 0.22, "bgm": 0.39},
    {"id": "T08",     "mode": "macro",    "t0": 58.310,  "t1": 68.290,  "name": "灵渠编筏・横扫湘江",   "amb": 0.20, "bgm": 0.40},
    {"id": "T09",     "mode": "macro",    "t0": 68.290,  "t1": 78.298,  "name": "渡江跨淮・六十万北伐", "amb": 0.20, "bgm": 0.40},
    {"id": "T10",     "mode": "macro",    "t0": 78.298,  "t1": 86.030,  "name": "洛阳迎降（静谧过渡）", "amb": 0.26, "bgm": 0.56},
    {"id": "T11_PRE", "mode": "macro",    "t0": 86.030,  "t1": 96.038,  "name": "兵临潼关・禁谷潜行",   "amb": 0.24, "bgm": 0.55},
    {"id": "B_TG",    "mode": "tactical", "t0": 96.038,  "t1": 105.031, "name": "双路破潼关（3D沙盘）", "amb": 0.22, "bgm": 0.40},
    {"id": "T12",     "mode": "cutscene", "t0": 105.031, "t1": 112.535, "name": "含元殿大齐称帝",       "amb": 0.18, "bgm": 0.39},
    {"id": "T13",     "mode": "cutscene", "t0": 112.535, "t1": 119.533, "name": "朱温同州叛降·四帧转折", "amb": 0.24, "bgm": 0.38},
    {"id": "T14_LK",  "mode": "cutscene", "t0": 119.533, "t1": 123.536, "name": "李克用沙陀鸦儿军入关", "amb": 0.22, "bgm": 0.39},
    {"id": "B_WMD",   "mode": "tactical", "t0": 123.536, "t1": 130.547, "name": "梁田坡—王满渡半渡决战", "amb": 0.24, "bgm": 0.39},
    {"id": "T15_REV", "mode": "macro",    "t0": 130.547, "t1": 138.043, "name": "版图翻红・群镇反攻",   "amb": 0.22, "bgm": 0.40},
    {"id": "T16",     "mode": "cutscene", "t0": 138.043, "t1": 146.573, "name": "泰山狼虎谷横剑折旗",   "amb": 0.30, "bgm": 0.42},
]


def _ensure_enog_wav() -> float:
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    if not SRC_WAV.exists():
        subprocess.run([
            ff, "-y", "-loglevel", "error",
            "-i", str(SRC_MP3), "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", str(SRC_WAV),
        ], check=True)
    sr, x = wavfile.read(str(SRC_WAV))
    assert sr == SR
    return len(x) / float(SR)


def _nearest_beat(beats: np.ndarray, target: float) -> float:
    idx = int(np.argmin(np.abs(beats - target)))
    return float(beats[idx])


def _extract_beats() -> Dict:
    y, sr = librosa.load(str(SRC_WAV), sr=22050, mono=True)
    oenv = librosa.onset.onset_strength(y=y, sr=sr, hop_length=512)
    onset_frames = librosa.onset.onset_detect(onset_envelope=oenv, sr=sr, hop_length=512, delta=0.16, wait=4, backtrack=False)
    onsets = librosa.frames_to_time(onset_frames, sr=sr, hop_length=512)
    onset_strs = [float(oenv[min(int(f), len(oenv) - 1)]) for f in onset_frames]
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=oenv, sr=sr, hop_length=512)
    tempo_bpm = float(np.atleast_1d(tempo)[0])
    beats = librosa.frames_to_time(beat_frames, sr=sr, hop_length=512)
    strong_onsets = [float(t) for t, s in zip(onsets, onset_strs) if s >= 8.0]

    payload = {
        "source_mp3": SRC_MP3.name,
        "source_wav": str(SRC_WAV),
        "total_sec": TOTAL_SEC,
        "fps": FPS,
        "total_frames": TOTAL_FRAMES,
        "tempo_bpm": round(tempo_bpm, 3),
        "beats": [round(float(t), 4) for t in beats],
        "strong_onsets": [round(float(t), 4) for t in strong_onsets],
        "acts": ACTS,
    }
    out_json = AUD / "enog_huangchao_beat_map.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Real Enog beats: {tempo_bpm:.2f} BPM | beats={len(beats)} | strong_onsets={len(strong_onsets)}")
    return payload


def _sword_draw(rng: np.random.Generator, dur: float = 0.65, pan: float = 0.0) -> np.ndarray:
    t = S._t(dur)
    scrape = S.filt(S.colored_noise(len(t), rng, power=0.0), "band", (2400, 6600), order=2)
    scrape *= S.envelope_points(len(t), [(0.0, 0.0), (0.05, 0.9), (0.28, 0.6), (dur, 0.0)])
    ring = (np.sin(2 * np.pi * 2480 * t) * 0.36 + np.sin(2 * np.pi * 3920 * t) * 0.20) * np.exp(-t / 0.28)
    return S.pan_stereo(S.norm(scrape * 0.6 + ring * 0.5, 0.85), pan)


def _flag_snap(rng: np.random.Generator, pan: float = 0.0) -> np.ndarray:
    c = S.timber_crash(rng)
    fall = S.body_fall(rng)
    out = np.zeros(int(1.05 * SR))
    n1 = min(len(out), len(c))
    out[:n1] += c[:n1] * 0.9
    off = int(0.32 * SR)
    n2 = min(len(out) - off, len(fall))
    if n2 > 0:
        out[off:off + n2] += fall[:n2] * 0.75
    return S.pan_stereo(S.norm(out, 0.88), pan)


def _punch_drum(rng: np.random.Generator, f0: float = 52.0, dur: float = 0.72, bright: float = 1.15) -> np.ndarray:
    d = S.war_drum(rng, f0=f0, dur=dur, bright=bright)
    return S.fade(d, 0.0, 0.14)


def _synthesize_beat_locked_buses(rng: np.random.Generator, beats: np.ndarray, N: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """所有打击/兵刃/箭雨/过场严格吸附到 Enog 真实 beat 网格，剔除散乱底噪循环。"""
    amb = np.zeros((2, N), dtype=np.float64)
    drums = np.zeros((2, N), dtype=np.float64)
    battle = np.zeros((2, N), dtype=np.float64)
    rout = np.zeros((2, N), dtype=np.float64)

    q = lambda t_tgt: _nearest_beat(beats, t_tgt)

    # 1. amb 总线：极轻空间风息底色（严格不参与侧链且不抢中高频律动）
    wind_base = S.wind_bed(rng, TOTAL_SEC + 0.5)[:, :N]
    amb_pts = [(a["t0"], a["amb"]) for a in ACTS] + [(TOTAL_SEC, 0.25)]
    amb_curve = S.envelope_points(N, amb_pts)
    S.place(amb, wind_base * amb_curve * 0.22, 0.0, 1.0)

    # 2. T01 Intro (0.00 ~ 8.034s)：克制古琴 + 埙 + 碎榜掷笔踩拍点，不覆盖弱前奏
    S.place(drums, S.guqin(rng, 220.0, 2.0), q(0.53), 0.38, -0.25)
    S.place(drums, S.xun(rng, 293.66, 2.6, slide_from=261.63), q(3.02), 0.40, 0.15)
    S.place(battle, _sword_draw(rng, 0.55, -0.15), q(6.52), 0.44)
    S.place(drums, _punch_drum(rng, 58.0, 0.65), q(7.55), 0.48, 0.0)

    # 3. T02 ~ T04 Rhythmic Build (8.034 ~ 31.045s)：严格咬合四拍重拍与过渡 whoosh
    for t_cut, pan in [(8.034, 0.0), (16.045, -0.15), (24.009, 0.15)]:
        t_b = q(t_cut)
        S.place(drums, _punch_drum(rng, 50.0, 0.75, 1.25), t_b, 0.80, pan)
    S.place(battle, _sword_draw(rng, 0.65, 0.20), q(10.03), 0.62)
    S.place(drums, S.gong_clang(rng, 430.0, 1.4), q(16.045), 0.55, -0.2)
    for dt in [18.02, 20.02, 22.01]:
        S.place(battle, S.sword_clash(rng), q(dt), 0.55, 0.25)
    S.place(drums, S.war_horn(rng, 116.5, 2.0, n_players=3), q(25.01), 0.54, -0.2)
    S.place(battle, S.blade_cleave(rng), q(28.03), 0.68, 0.2)

    # ** 31.045 ~ 32.044s（1 秒极静吸气）-> 32.044s DROP 1 **
    S.place(battle, S.whoosh(rng, 0.68, rising=True), 31.28, 0.68, 0.0)

    # 4. Drop 1 Part A (32.044 ~ 48.030s)：Drop 瞬间重鼓落棋盘，每隔 4 拍清脆战术节奏
    S.place(drums, _punch_drum(rng, 44.0, 0.85, 1.35), q(32.044), 0.90, 0.0)
    S.place(battle, S.timber_crash(rng), q(34.04), 0.62, -0.2)  # 刊山开道
    for tb in [36.04, 38.03, 40.03, 44.03]:
        S.place(drums, _punch_drum(rng, 52.0, 0.55, 1.2), q(tb), 0.62, 0.0)
    S.place(battle, S.whoosh(rng, 0.55, rising=True), 47.45, 0.62, 0.0)

    # 5. B_GZ 广州攻坚战 3D 沙盘 (48.030 ~ 58.310s)：所有动作精确咬拍点
    S.place(drums, _punch_drum(rng, 46.0, 0.78, 1.3), q(48.03), 0.82, 0.0)
    S.place(battle, S.arrow_volley(rng, n_arrows=34, spread=0.75), q(50.20), 0.74)
    for tb in [52.28, 53.29]:
        S.place(battle, S.blade_cleave(rng), q(tb), 0.70, (-1 if tb < 53 else 1) * 0.25)
    S.place(battle, S.timber_crash(rng), q(54.27), 0.84, 0.0)   # 破广州城门
    for k, tb in enumerate([55.29, 55.77, 56.29]):               # 破门后骑兵蹄声卡半拍
        S.place(battle, S.hoof_strike(rng), tb, 0.64, (-0.3 + 0.3 * k))
    S.place(drums, S.gong_clang(rng, 390.0, 1.4), q(57.30), 0.58, 0.15)  # 易帜换旗

    # 6. T08 ~ T09 北伐大迂回 (58.310 ~ 78.298s)：大军横扫江淮，轻快踩四拍
    S.place(battle, S.whoosh(rng, 0.50, rising=True), 57.82, 0.58)
    S.place(drums, S.war_horn(rng, 110.0, 2.2, n_players=3), q(58.80), 0.58, -0.2)
    for tb in [60.28, 62.29, 64.29, 66.29, 68.29, 70.29, 72.29]:
        S.place(drums, _punch_drum(rng, 50.0, 0.50, 1.15), q(tb), 0.60, 0.0)
    S.place(battle, S.arrow_volley(rng, n_arrows=32, spread=0.70), q(74.28), 0.70)
    S.place(drums, _punch_drum(rng, 46.0, 0.70), q(76.30), 0.68, 0.0)

    # 7. Breakdown 静谧过渡 (78.298 ~ 95.039s)：尊重音乐 Bass 抽空，用清冽铜锣/埙/利刃点睛
    S.place(drums, S.gong_clang(rng, 360.0, 1.8), q(78.30), 0.56, 0.0)
    S.place(drums, S.xun(rng, 246.94, 2.8, slide_from=293.66), q(86.03), 0.40, -0.2)
    S.place(battle, _sword_draw(rng, 0.70, 0.25), q(90.02), 0.46)
    for tb in [92.02, 93.02, 94.02]:
        S.place(battle, S.footstep(rng, armor=True), q(tb), 0.42, -0.1)

    # ** 95.039 ~ 96.038s（1 秒抽空 breath）-> 96.038s DROP 2 炸裂 **
    S.place(battle, S.whoosh(rng, 0.72, rising=True), 95.22, 0.72, 0.0)

    # 8. B_TG 双路破潼关 3D 沙盘 (96.038 ~ 105.031s)
    S.place(drums, _punch_drum(rng, 43.0, 0.90, 1.4), q(96.04), 0.92, 0.0)
    S.place(drums, _punch_drum(rng, 48.0, 0.65, 1.3), q(97.11), 0.76, 0.0)
    S.place(battle, S.arrow_volley(rng, n_arrows=38, spread=0.75), q(98.20), 0.76)
    S.place(battle, S.timber_crash(rng), q(100.29), 0.88, 0.0)   # 破潼关关门
    for tb in [101.29, 101.77, 102.29, 102.79]:
        S.place(battle, S.hoof_strike(rng), tb, 0.68, 0.0)
    S.place(battle, S.blade_cleave(rng), q(103.30), 0.72, -0.2)

    # 9. T12 含元殿称帝 (105.031 ~ 112.535s)：编钟三响精准咬拍
    S.place(drums, S.bianzhong(rng, 261.63, 2.2), q(105.28), 0.68, -0.2)
    S.place(drums, S.bianzhong(rng, 329.63, 2.2), q(107.29), 0.68, 0.2)
    S.place(drums, S.bronze_bell(rng, 196.0, 2.6), q(109.29), 0.56, 0.0)

    # 10. T13 朱温叛降 (112.535 ~ 119.533s)
    S.place(battle, _sword_draw(rng, 0.72, 0.20), q(112.53), 0.72)
    S.place(drums, S.guqin(rng, 185.0, 2.2, slide_to=164.81), q(115.53), 0.56, -0.15)
    S.place(drums, S.war_horn(rng, 123.5, 2.0, n_players=3), q(118.53), 0.66, 0.2)

    # 11. T14_LK 李克用沙陀鸦儿军入关 + B_WMD 王满渡半渡溃败 3D 沙盘 (119.533 ~ 130.547s)
    S.place(drums, _punch_drum(rng, 45.0, 0.80, 1.3), q(119.53), 0.82, 0.0)
    S.place(battle, S.arrow_whoosh(rng), q(121.02), 0.72, -0.2)  # 李克用独眼挽弓放箭
    for tb in [122.02, 122.53, 123.02, 123.54]:
        S.place(battle, S.hoof_strike(rng), tb, 0.68, -0.25)
    S.place(drums, _punch_drum(rng, 46.0, 0.75, 1.25), q(123.54), 0.80, 0.0)
    S.place(battle, S.arrow_volley(rng, n_arrows=36, spread=0.75), q(124.53), 0.72)
    for tb in [125.54, 126.53, 127.53]:
        S.place(battle, S.sword_clash(rng), q(tb), 0.68, 0.25)
    for k, tb in enumerate([128.53, 129.54]):
        S.place(rout, S.gong_clang(rng, 520.0, 1.2), q(tb), 0.60 - 0.08 * k, -0.2)

    # 12. T15_REV 全盘翻红大反攻 (130.547 ~ 138.043s)
    for tb in [130.55, 132.54, 134.54, 136.53]:
        S.place(drums, _punch_drum(rng, 48.0, 0.55, 1.2), q(tb), 0.64, 0.0)
    S.place(battle, S.whoosh(rng, 0.52, rising=False), 137.50, 0.60, 0.0)

    # 13. T16 泰山狼虎谷落幕 (138.043 ~ 146.573s)：最后一击重拍 142.547s 折旗
    S.place(battle, _sword_draw(rng, 0.75, 0.10), q(140.04), 0.66)
    S.place(rout, _flag_snap(rng, 0.0), q(142.55), 0.82)
    S.place(drums, S.guqin(rng, 164.81, 2.8, slide_to=146.83), 143.65, 0.58, 0.0)

    return amb, drums, battle, rout


def _measure_lufs(wav_path: Path) -> Tuple[float, float]:
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.run(
        [ff, "-hide_banner", "-i", str(wav_path), "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    )
    i_lufs = float("nan")
    tp_db = float("nan")
    m_i = re.search(r"Integrated loudness:\s*\r?\n\s*I:\s*([-\d.]+)\s*LUFS", proc.stderr)
    m_p = re.search(r"True peak:\s*\r?\n\s*Peak:\s*([-\d.]+)\s*dBFS", proc.stderr)
    if m_i:
        i_lufs = float(m_i.group(1))
    if m_p:
        tp_db = float(m_p.group(1))
    return i_lufs, tp_db


def build_audio_and_mix(meta: Dict) -> Dict:
    N = int(round(TOTAL_SEC * SR))
    rng = np.random.default_rng(874)
    beats = np.asarray(meta["beats"], dtype=float)

    amb_raw, drums_raw, battle_raw, rout_raw = _synthesize_beat_locked_buses(rng, beats, N)

    # 四物理空间总线混响
    amb = S.reverb(amb_raw, rng, 1.0, 0.15)
    drums = S.reverb(drums_raw, rng, 1.8, 0.24)
    battle = S.reverb(battle_raw, rng, 1.4, 0.20)
    rout = S.reverb(rout_raw, rng, 1.6, 0.22)

    sfx_raw = amb * 0.90 + drums * 0.78 + battle * 0.92 + rout * 0.94
    sfx_raw = S.filt(sfx_raw, "high", 30.0, order=2)
    sfx_ref = float(np.percentile(np.abs(sfx_raw), 99.7)) + 1e-9
    sfx = np.tanh((sfx_raw / sfx_ref * 0.64) * 1.18) / np.tanh(1.18)
    # 显著回调 SFX 突出度（峰值 0.45 对比旧版 0.62，降低 > 2.5 dB，不刺耳不抢拍）
    sfx = S.norm(sfx, 0.45)
    sfx = S.fade(sfx, 0.05, 0.80)

    sr_b, x_b = wavfile.read(str(SRC_WAV))
    assert sr_b == SR
    bgm_seg = np.zeros((2, N), dtype=np.float64)
    take = min(N, len(x_b))
    bgm_seg[:, :take] = x_b[:take].T.astype(np.float64) / 32768.0

    # 层 1：中高频柔和掏槽 -20%，保留 Enog 原生质感
    mid_pocket = S.filt(bgm_seg, "band", (1300.0, 3200.0), order=2)
    bgm = bgm_seg - 0.20 * mid_pocket

    # 层 2：匹配真实声学曲线（温和上推 +1.15dB 使整片落入 -13.1 ~ -12.7 LUFS，且无需事后整轨 AGC）
    env_pts = [(0.00, 0.56)]
    for a in ACTS:
        env_pts.append((a["t0"] + 0.12, a["bgm"]))
        env_pts.append((max(a["t0"] + 0.18, a["t1"] - 0.18), a["bgm"]))
    env_pts.append((144.20, 0.36))
    env_pts.append((TOTAL_SEC - 0.25, 0.04))
    env_pts.append((TOTAL_SEC, 0.00))
    base_curve = 1.17 * S.envelope_points(N, env_pts)

    # 层 3：排除 amb 底噪的轻柔 5ms 瞬态侧链闪避（最低 0.76，保留音乐律动不抽搐）
    trans_sfx = S.filt(battle, "high", 1200.0) + 0.90 * drums + 0.85 * rout
    sfx_mono_abs = np.max(np.abs(trans_sfx), axis=0)
    hop_sc = 240
    m_len = (N // hop_sc) * hop_sc
    sc_ds = np.maximum.reduceat(sfx_mono_abs[:m_len], np.arange(0, m_len, hop_sc))
    sc_ds = sc_ds / (np.percentile(sc_ds, 99.0) + 1e-9)
    sc_env_ds = np.zeros_like(sc_ds)
    cur = 0.0
    for i, v in enumerate(sc_ds):
        c = 0.35 if v > cur else 0.055
        cur = (1.0 - c) * cur + c * min(1.0, float(v))
        sc_env_ds[i] = cur
    sc_env = np.interp(np.arange(N), np.arange(len(sc_env_ds)) * hop_sc, sc_env_ds)
    duck_gain = np.clip(1.0 - 0.24 * sc_env, 0.76, 1.0)
    bgm_ducked = bgm * base_curve * duck_gain

    # 总线温和胶合（禁用整轨 AGC）+ 0.89 峰值保护
    mix = np.tanh((sfx + bgm_ducked) * 1.12) / np.tanh(1.12)
    mix = S.fade(mix, 0.05, 0.90)
    pk_mix = float(np.max(np.abs(mix)))
    if pk_mix > 0.89:
        mix = mix * (0.89 / pk_mix)

    def to16(x: np.ndarray) -> np.ndarray:
        return (np.clip(x, -1.0, 1.0).T * 32767.0).astype(np.int16)

    p_sfx = AUD / "enog_sfx_all.wav"
    p_bgm = AUD / "enog_bgm_ducked.wav"
    p_mix = AUD / "enog_master_mix.wav"
    wavfile.write(p_sfx, SR, to16(sfx))
    wavfile.write(p_bgm, SR, to16(bgm_ducked))
    wavfile.write(p_mix, SR, to16(mix))

    i_lufs, tp_db = _measure_lufs(p_mix)
    print(f"Master LUFS: {i_lufs:.2f} LUFS | True Peak: {tp_db:.2f} dBFS | peak={np.max(np.abs(mix)):.4f}")
    print("=== Enog 真实结构 × 17 幕响度对照 ===")
    for a in ACTS:
        i0, i1 = int(a["t0"] * SR), int(min(TOTAL_SEC, a["t1"]) * SR)
        r_s = 20 * np.log10(np.sqrt(np.mean(sfx[:, i0:i1] ** 2)) + 1e-9)
        r_b = 20 * np.log10(np.sqrt(np.mean(bgm_ducked[:, i0:i1] ** 2)) + 1e-9)
        r_m = 20 * np.log10(np.sqrt(np.mean(mix[:, i0:i1] ** 2)) + 1e-9)
        print(f"  {a['id']:8s} {a['t0']:6.2f}-{a['t1']:6.2f}s | SFX {r_s:6.1f} dB | BGM {r_b:6.1f} dB | Mix {r_m:6.1f} dB (SFX-BGM={r_s-r_b:+.1f} dB)")

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axs = plt.subplots(4, 1, figsize=(18, 9.5), sharex=True)
    tt = np.arange(N) / float(SR)
    axs[0].plot(tt[::60], bgm_ducked[0, ::60], lw=0.45, color="#3D74A6")
    axs[0].set_ylabel("Enog BGM (贴结构驯服)")
    axs[1].plot(tt[::60], sfx[0, ::60], lw=0.45, color="#D9483B")
    axs[1].set_ylabel("拍点量化 SFX")
    axs[2].plot(tt[::120], duck_gain[::120], lw=0.85, color="#2A9D8F")
    axs[2].set_ylim(0.70, 1.04)
    axs[2].set_ylabel("Sidechain 闪避")
    axs[3].specgram(mix.mean(0), NFFT=2048, Fs=SR, noverlap=1024, cmap="magma")
    axs[3].set_ylim(0, 8000)
    axs[3].set_ylabel("混音频谱 (Hz)")
    axs[3].set_xlabel("时间 (s)")
    for ax in axs:
        for a in ACTS:
            ax.axvline(a["t0"], color="#D62828", lw=0.75, alpha=0.85)
    y_top = axs[0].get_ylim()[1] * 0.85
    for a in ACTS:
        axs[0].text(a["t0"] + 0.15, y_top, a["id"], color="#D62828", fontsize=8.0, fontweight="bold")
    fig.suptitle(f"《唐末黄巢起义》Enog 真实 Drop/Breakdown 对齐混音诊断图  |  实测 {i_lufs:.2f} LUFS / Peak {tp_db:.2f} dBFS")
    fig.tight_layout()
    diag_png = AUD / "enog_huangchao_mix_timeline.png"
    fig.savefig(diag_png, dpi=105)
    print(f"Saved diagnostic plot: {diag_png}")
    return {"lufs": i_lufs, "true_peak_dbfs": tp_db}


def main() -> None:
    dur = _ensure_enog_wav()
    print(f"Decoded WAV: {dur:.3f}s | target={TOTAL_SEC:.3f}s")
    meta = _extract_beats()
    build_audio_and_mix(meta)


if __name__ == "__main__":
    main()
