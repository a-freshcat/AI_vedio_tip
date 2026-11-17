# 04 · BGM 测拍、纯合成音效与三层混音规范

> 核心原则：**SFX 为画面与音乐律动加质感，绝不喧宾夺主；禁止整轨事后 AGC；最终必须对成片 MP4 实测 LUFS。**

---

## 一、第一步：先测原曲真实结构（对应 Pipeline G2）

禁止拍脑袋定“每幕 8 秒”。拿到用户指定的 MP3 后，先转为 48 kHz 立体声 WAV，用 `librosa` 提取四组物理指标（参考 `reference/huangchao/src/hc_audio_enog.py::_extract_beats`）：

1. **真实拍点与速度**：`tempo, beat_frames = librosa.beat.beat_track(...)`、`beats = librosa.frames_to_time(beat_frames, ...)`。
2. **强冲击点**：`onset_strength` + `onset_detect`。
3. **逐秒 RMS 能量曲线**：识别 Intro 轻前奏、Build 蓄力、**1 秒极静抽空（Pre-Drop）**、Drop 爆发、静谧 Breakdown 与 Outro 衰减。
4. **30–140 Hz Bass 低频能量**：防止把无鼓点的低 Bass Breakdown 当成主攻城高潮，也防止把悲凉退场硬压在 Drop 低音锤击上。

输出 `*_beat_map.png` 并整理真实段落表后，才能进入分幕表制定。以黄巢版 `Enog.mp3`（117.45 BPM / 283 拍 / 146.573s）为例：
- `0–16.05s` Intro（`-19 dB`）→ 曲江赋菊 + 起兵棋盘
- `31.05–32.04s` 1 秒抽空（`-25.2 dB`）→ Whoosh 蓄气转场
- `32.04–78.30s` Drop 1（`-10.1 dB`）→ 刊山入闽、`B_GZ` 广州攻城、北伐跨淮
- `78.30–95.04s` Breakdown（`-20 dB`）→ 洛阳迎降、潼关潜行蓄势
- `96.04–143.50s` Drop 2（`-10.6 dB`）→ `B_TG` 破潼关、称帝、朱温/李克用转折、`B_WMD` 王满渡、全盘反攻，`142.55s` 最后重拍折旗
- `143.50–146.57s` Outro（`-42.7 dB`）→ 古琴尾韵随原曲淡出

---

## 二、两套曲风混音预设（消除旧版文档参数冲突）

旧版 `00` 与 `04` 之所以看起来参数不一致，是因为混用了**交响史诗配乐**与**现代强节拍电音**两类不同动态特征的 BGM。请按音乐类型二选一：

| 参数项 | 预设 A · 管弦 / 交响史诗（《Amazon》《Chaikovsky》） | 预设 B · 现代重节拍 / 电音 / Phonk（《Enog》117.45 BPM） |
| :-- | :-- | :-- |
| 适用场景 | 旋律线条起伏大、需要浓烈战场沉浸感与外部短片对白 | 底鼓清晰紧密、需要清爽不扰乱节拍律动 |
| SFX 归一化峰值 ceiling | `0.58` | **`0.45`**（比旧版回调 > 2.5 dB，防止刺耳抓耳） |
| 音效放置策略 | 按战报密集叠放 + `melee_bed` / `crowd` 氛围层 | **全部通过 `_nearest_beat(beats, t)` 量化对齐拍点**；**禁用**散乱人群叫喊与无拍点连续马蹄 |
| 中频掏槽（`1300–3200 Hz`） | `-26%` | **`-20%`**（保留电音原生明亮质感） |
| 侧链下压下限（`duck_gain`） | `clip(..., 0.68, 1.0)` | **`clip(..., 0.76, 1.0)`**（保留音乐脉冲感不抽搐） |
| `SFX − BGM` 合理区间 | `-3 ~ +2 dB` | **`-9 ~ -1 dB`**（仅静谧 Breakdown 段允许升至约 `+1.5 dB`） |
| 母带 WAV 目标 LUFS | `-13.0 ~ -12.8 LUFS` | **`-13.0 ~ -12.9 LUFS`**（见下方 §4 AAC 掉响度规律） |

---

## 三、SFX 四物理总线 + 三层安全混音链

1. **四总线独立空间混响**（`48000 Hz`，均出自 `sfx_synth.py`）：
   - `amb`（环境风沙）：`reverb(1.0s, wet=0.15)` × `0.90`
   - `drums`（战鼓/铜锣/号角/古琴/埙）：`reverb(1.8s, wet=0.24~0.26)` × `0.78`
   - `battle`（劈砍/箭雨/马蹄）：`reverb(1.4s, wet=0.20~0.22)` × `0.92`
   - `rout`（鸣金/溃退/折旗）：`reverb(1.6s, wet=0.22~0.25)` × `0.94`
2. **分位数防失真整形**（禁止直接用 `max(|x|)` 归一化，避免单次刀鸣压扁整条音轨）：
   - `30 Hz` 二阶高通滤除次声直流；
   - 以 `np.percentile(np.abs(sfx_raw), 99.7)` 为基准走 `tanh` 软饱和，再 `S.norm(sfx, target_peak)`。
3. **BGM 让位三防线**：
   - **层 1（中高频掏槽）**：`bgm = bgm_seg - k * filt(bgm_seg, "band", (1300.0, 3200.0), order=2)`；
   - **层 2（分段动态包络 `envelope_points`）**：按实测段落独立写系数，不拿同一系数乘全曲（如交响前奏极轻时抬至 `0.72`、爆发瞬间收压至 `0.22–0.28`）；
   - **层 3（排除 `amb` 的 5 ms 瞬态侧链闪避）**：**严禁把持续风噪 `amb` 放进侧链触发源**！触发源只用 `highpass(battle, 1200 Hz) + 0.9 * drums + 0.85 * rout`（有外部短片时加 `clip_bus`），步长 `hop_sc=240`（5 ms）、快攻 `0.35` / 慢释 `0.045~0.055`。

---

## 四、0.89 峰值保护、禁用整轨 AGC 与 AAC 掉响度修正

- `mix = np.tanh((sfx + bgm_ducked) * gain) / np.tanh(gain)`（`gain = 1.08 ~ 1.12`），`fade`，峰值超过 `0.89` 时等比缩回 `0.89`。**绝不在混音后做全轨自动增益**。
- **实测经验（WAV → AAC `-0.1 LUFS` 偏差）**：黄巢版实测母带 WAV `-13.10 LUFS` 经 `256k AAC` 压缩后会变成 `-13.2 LUFS`（刚好跌出 `-13.1 ~ -12.7`）。
  - 做法：把母带 WAV 控制在 **`-13.00 ~ -12.90 LUFS`**，封装后必须再对最终 MP4 跑 `ffmpeg ebur128` 实测（黄巢终版实测：母带 `-13.00 LUFS / peak 0.8900`，成片 **`I = -13.0 LUFS / TP = -0.9 dBFS`**）。
  - **省时技巧**：如果只是响度微偏 `0.1~0.3 dB`，改完 `hc_audio_*.py` 跑 3 秒生成新 `master_mix.wav` 后，直接用已编码的无声视频 `-c:v copy` 重新封装（1 秒完成），**不要重跑 8 分钟的视频渲染**！

---

## 五、必出双诊断产物（G5 验收依据）

1. 终端打印每幕 `t0–t1`、`SFX dB`、`BGM dB`、`Mix dB` 与 `SFX − BGM` 差值表；
2. 保存四合一诊断图 `*_mix_timeline.png`（压限后 BGM 波形、SFX 总轨、`duck_gain` 轨迹、8 kHz 内混音频谱，叠画红线分幕边界），对应示例见 `reference/huangchao/audio/enog_huangchao_mix_timeline.png` 与 `reference/anshi/audio/`。
