# 03 · 工具链、跨平台字体与双参考模块索引

> 本仓库提供两套经真实渲染验证的参考工程：
> - **`reference/huangchao/`（首选主模板）**：单首电音 BGM 卡点（18 幕 / 4,397 帧）、西部高原 3D 地貌、96 档前锋推进战线、128×128 主角与名将四帧精灵。
> - **`reference/anshi/`（扩展场景参考）**：多段 BGM 接缝拼接、外部 AI 短片无缝嵌合（`_load_external_clip`）、河心岛与浮桥沙盘（`_draw_island_and_bridges`）。

---

## 一、Python 技术栈与系统工具

| 类别 | 工具 / Python 库 | 在流水线中的职责 |
| :-- | :-- | :-- |
| **视频编码与音频测量** | `FFmpeg`（通过 `imageio_ffmpeg.get_ffmpeg_exe()` 调用） | BGM 转 48 kHz WAV；`rawvideo rgb24` 管道实时编码 `h264 (yuv420p)`；`aac 256k` 封装；`-c:v copy` 无损重混/拼接；`ebur128` 实测成片 LUFS |
| **音乐节拍与能量分析** | `librosa` | 提取 `beat_track` 拍点与 BPM、`onset_strength`/`onset_detect`、逐秒 RMS 与低频 Bass 能量分布 |
| **信号合成与混音** | `NumPy` + `SciPy` (`scipy.io.wavfile`, `scipy.ndimage.gaussian_filter`, 滤波器) | `sfx_synth.py` 48 kHz 音效合成、4 总线空间混响、`1300–3200 Hz` 带通挖空、瞬态侧链闪避与 `tanh` 软饱和；高斯平滑势力场 |
| **帧绘制与诊断图** | `Pillow (PIL)` + `Matplotlib`（`Agg`） | 4× 超采样兵棋精灵与建筑、3D 地形叠加、HUD 字幕合成；`*_beat_map.png` 与 `*_mix_timeline.png` 核对图 |
| **工程编译与校验** | 标准库（`json`, `csv`, `math`, `pathlib`, `subprocess`, `bisect`, `re`） | 经纬度校验、控制权快照编译、`GeoJSON` 导出与 Haversine 里程统计 |

---

## 二、跨平台中文字体加载规范（解决旧版跨系统报错）

旧版参考脚本（如 `hc_campaign_renderer.py`、`hc_tactical.py`）硬编码了 `C:\Windows\Fonts\msyhbd.ttc`，而 `huangchao_sprites_ultra.py` 硬编码了 `/usr/share/fonts/...`。新建工程请统一放入公共辅助函数：

```python
from pathlib import Path
from PIL import ImageFont

def get_cjk_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """按 Windows → macOS → Linux 顺序探测中文字体；缺失时显式报错，不静默变方块字。"""
    candidates = (
        [
            r"C:\Windows\Fonts\msyhbd.ttc",
            r"C:\Windows\Fonts\simhei.ttf",
            "/System/Library/Fonts/PingFang.ttc",
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        ]
        if bold
        else [
            r"C:\Windows\Fonts\STZHONGS.TTF",
            r"C:\Windows\Fonts\msyh.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]
    )
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    raise FileNotFoundError(f"未找到可用的中文字体，请安装黑体/思源字体；已探测: {candidates}")
```

---

## 三、「做新项目时该直接抄哪个模块」速查表

| 你的需求 | 直接参考哪个文件 / 函数 | 说明 |
| :-- | :-- | :-- |
| **数据校验 + JSON/GeoJSON 编译** | `reference/huangchao/src/build.py::validate_and_compile` | 流动作战版更轻量，自动输出 `city_control` 逐事件快照与路线里程 |
| **多维度战役/兵力表 + CSV 输出** | `reference/anshi/src/build.py` + `data_units.py` + `data_battles.py` | 需要导出 8 张 `.csv` 表与每帧 `snapshots` 时选用 |
| **全国含西部高原/横断峡谷 3D 地形** | `reference/huangchao/src/hc_terrain.py::build_relief_terrain` | 含 `ridged_multifractal_2d`、域扭曲与顺坡河流雕刻 |
| **96 档不滞后势力疆界插值** | `hc_terrain.py::compute_smoothed_faction_scores` + `hc_campaign_renderer.py::_draw_macro` | 三段场 `s0 -> s_mid -> s1`，注入箭头 `45%~75%` 锚点 |
| **双向多军 3D 战术沙盘 + 云梯攻城** | `reference/huangchao/src/hc_tactical.py` (`Actor`, `HuangChaoTacticalRenderer`) | 简化清晰版 `Actor` 骨架；需多场连战可扩展见 `reference/anshi/src/battle_anim.py` |
| **河心岛与浮桥 / 城池防漂浮** | `reference/anshi/src/tactical_map.py::_draw_island_and_bridges` | 河阳三城等特殊跨河据点直接借鉴 |
| **主角多阶段 128×128 像素精灵** | `reference/huangchao/src/huangchao_sprites_ultra.py` (`PixelCanvas`, `get_huangchao_sprite`) | 5 阶段 × 4 帧、`_face` 面部锚点、`MaxFilter(3)` 轮廓保护 |
| **关键名将四帧像素转折** | `reference/huangchao/src/tang_warlords_sprites_128.py` (`get_warlord_sprite`) | 朱温 / 李克用 128×128 × 4 帧标准模板 |
| **普通兵卒与建筑 4× 超采样** | `reference/huangchao/src/sprites.py`、`landmarks.py` | 两套仓库通用的稳健基础图元 |
| **单曲 BGM 测拍 + 三层混音** | `reference/huangchao/src/hc_audio_enog.py` + `sfx_synth.py` | 电子强节拍（预设 B）与 18 幕响度对照表完整实现 |
| **外部 AI 短片 + 多曲无损拼合** | `reference/anshi/src/render_part2_amazon_clip.py::_load_external_clip` + `render_xiaban_chaikovsky_clip.py` | 重采样 external MP4、`clip_bus` 并入与 0.45 s crossfade |
| **全屏主渲染循环 + rawvideo 管道** | `reference/huangchao/src/hc_campaign_renderer.py::HuangChaoCampaignEngine` + `main()` | 直接复用即可替换为新作剧本 |
