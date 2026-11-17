"""步骤 1：使用 librosa.onset.onset_detect 与 beat_track 提取《Amazon》BGM 卡点时间数组，
输出结构化的节拍与剧情卡点配置 output/audio/amazon_beats.json，并绘制卡点规划核对图。
"""
import json
import subprocess
from pathlib import Path

import librosa
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import wavfile

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
AUD = ROOT / "output" / "audio"
AUD.mkdir(parents=True, exist_ok=True)
SRC_MP3 = Path(r"D:\下载\amazon.mp3")
SRC_WAV = AUD / "amazon_48k.wav"

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]


def ensure_wav():
    if not SRC_WAV.exists():
        cmd = [
            imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
            "-i", str(SRC_MP3), "-ar", "48000", "-ac", "2", str(SRC_WAV),
        ]
        subprocess.run(cmd, check=True)


def nearest(arr, target, lo=None, hi=None):
    cand = [float(x) for x in arr if (lo is None or x >= lo) and (hi is None or x <= hi)]
    if not cand:
        return float(target)
    return min(cand, key=lambda x: abs(x - target))


def main():
    ensure_wav()
    y, sr = librosa.load(str(SRC_WAV), sr=22050, mono=True)
    oenv = librosa.onset.onset_strength(y=y, sr=sr)
    onset_frames = librosa.onset.onset_detect(onset_envelope=oenv, sr=sr, delta=0.18, wait=4, backtrack=False)
    onsets = librosa.frames_to_time(onset_frames, sr=sr)
    onset_strs = [float(oenv[min(int(f), len(oenv) - 1)]) for f in onset_frames]

    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=oenv, sr=sr)
    tempo_bpm = float(np.atleast_1d(tempo)[0])
    beats = librosa.frames_to_time(beat_frames, sr=sr)

    # 筛选前 50 秒内的显著强卡点（strength >= 9.0）用于精准剧情触发
    strong_onsets = [float(t) for t, s in zip(onsets, onset_strs) if t <= 50.0 and s >= 9.0]

    # 从检测到的真实节拍与卡点中锚定开篇剧情时间线（0.00s -> ~46.00s，连续无剪接原曲推进）
    c_t002 = nearest(beats, 4.90)          # 4.899s：前奏结束、第一重落爆发
    c_t003 = nearest(beats, 9.80)          # 9.799s：第 2 小节重拍，凌冰渡河
    c_t005 = nearest(beats, 14.68)         # 14.675s：第 4 小节重拍，横扫中原
    c_t007 = nearest(beats, 19.55)         # 19.551s：第 6 小节重拍，兵临洛阳
    c_b03_in = nearest(strong_onsets, 22.59)  # 22.593s：第 7 小节低音抽空悬疑过渡切入 B03
    c_b03_drop = nearest(beats, 24.43)     # 24.427s：第 8 小节低音炸裂回归，全军冲锋
    c_t008 = nearest(beats, 33.88)         # 33.878s：第 12 小节重拍，转战退保潼关
    c_t009 = nearest(strong_onsets, 37.55) # 37.547s：强烈打击乐冲击，常山十七郡起义
    c_t010 = nearest(strong_onsets, 40.61) # 40.612s：重拍切换，安禄山洛阳称帝
    c_end = 46.00                          # 43.65s 尾拍后留韵淡出结束

    # B03 内部动作精确锚定到 librosa 检测出的强卡点（相对 b03_act 的偏移在后续计算）
    b03_abs_cues = {
        "arrows_done": c_b03_drop,                             # 24.427s 箭矢路径画满＋骑兵全速冲锋
        "charge_start": c_b03_drop - 0.85,                     # 提前半拍余起步加速，落重拍撞线
        "front_kills": [
            nearest(strong_onsets, 25.96),                     # 25.960s 正面第 1 斩 (str=11.95)
            nearest(strong_onsets, 26.86),                     # 26.865s 正面第 2 斩 (str=9.45)
            nearest(strong_onsets, 27.77),                     # 27.771s 正面第 3 斩 (str=14.09)
        ],
        "chase_north_kill": nearest(strong_onsets, 29.00),     # 29.002s (Bar 10.1) 北路追砍倒地
        "chase_south_kill": nearest(strong_onsets, 30.21),     # 30.209s 南路追砍倒地
        "volley": nearest(strong_onsets, 30.84),               # 30.836s (强峰 str=16.09) 叛军箭雨齐射
        "wall_deaths": [
            nearest(beats, 31.44),                             # 31.440s 城头第 1 名守军中箭
            nearest(strong_onsets, 31.74),                     # 31.742s 城头第 2 名守军中箭
        ],
        "gate_slash": nearest(strong_onsets, 32.07),           # 32.067s 先锋冲抵东门挥刀
        "smoke_start": nearest(strong_onsets, 31.74),          # 31.742s 东门破城火起
        "banner_fall": nearest(strong_onsets, 32.97),          # 32.972s 李憕帅旗折断倾倒
    }

    payload = {
        "source_mp3": str(SRC_MP3),
        "source_wav": str(SRC_WAV),
        "tempo_bpm": round(tempo_bpm, 3),
        "beats": [round(float(t), 4) for t in beats if t <= 60.0],
        "onsets": [round(float(t), 4) for t in onsets if t <= 60.0],
        "onset_strengths": [round(float(s), 3) for t, s in zip(onsets, onset_strs) if t <= 60.0],
        "strong_onsets": [round(float(t), 4) for t in strong_onsets],
        "story_timeline": {
            "T001": 0.0,
            "T002": c_t002,
            "T003": c_t003,
            "T005": c_t005,
            "T007": c_t007,
            "B03": c_b03_in,
            "T008": c_t008,
            "T009": c_t009,
            "T010": c_t010,
            "END": c_end,
        },
        "b03_abs_cues": b03_abs_cues,
    }
    out_json = AUD / "amazon_beats.json"
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"Tempo: {tempo_bpm:.2f} BPM | beats(0-60s): {len(payload['beats'])} | onsets(0-60s): {len(payload['onsets'])}")
    print("Story cues:", payload["story_timeline"])
    print("B03 abs cues:", payload["b03_abs_cues"])
    print(f"Saved {out_json}")

    # 绘制前 47 秒波形＋卡点强度＋剧情/动作触发点核对图
    sr_w, x_w = wavfile.read(str(SRC_WAV))
    m_w = x_w[:int(c_end * sr_w)].mean(axis=1).astype(np.float32) / 32768.0
    tt_w = np.arange(len(m_w)) / float(sr_w)
    fig, ax = plt.subplots(2, 1, figsize=(16, 7), sharex=True)
    ax[0].plot(tt_w[::40], m_w[::40], lw=0.4, color="#2C4966")
    ax[0].set_ylabel("Amazon 波形")
    for k, v in payload["story_timeline"].items():
        if k == "END":
            continue
        ax[0].axvline(v, color="#D62828", lw=1.4)
        ax[0].text(v + 0.1, 0.84, k, color="#D62828", fontsize=10, fontweight="bold")
    for name, val in b03_abs_cues.items():
        vals = val if isinstance(val, list) else [val]
        for tv in vals:
            ax[1].axvline(tv, color="#E76F51", ls="--", lw=1.0)
    t_env = librosa.times_like(oenv, sr=sr)
    mask = t_env <= c_end
    ax[1].plot(t_env[mask], oenv[mask], color="#264653", lw=1.0, label="Onset 强度")
    for ts in strong_onsets:
        if ts <= c_end:
            ax[1].axvline(ts, color="#2A9D8F", alpha=0.25, lw=0.8)
    ax[1].set_ylabel("Onset 能量")
    ax[1].set_xlabel("时间 (s)")
    fig.suptitle("《Amazon》0–46 秒 librosa 卡点提取与《安史之乱》剧情对齐图")
    fig.tight_layout()
    fig.savefig(AUD / "amazon_beat_map.png", dpi=100)
    print(f"Saved {AUD / 'amazon_beat_map.png'}")


if __name__ == "__main__":
    main()
