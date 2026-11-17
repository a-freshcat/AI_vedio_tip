# 参考成品 B · 《安史之乱（755–763）》

> 本目录保留《安史之乱》战役向原型的 `src/`（18 个模块）、`data/`（8 张 `.csv` + `.json` / `.geojson`）以及《Amazon》《Chaikovsky》声学节拍与混音诊断参考。
> 做新作时默认以 **`../huangchao/`** 为首要渲染/电音卡点模板；遇到**多 BGM 无损接缝拼合**、**外部 AI 生成短片无缝嵌合**或**河心岛与多浮桥复杂沙盘**时，重点查阅本目录以下模块。

---

## 与黄巢版互补的核心参考点

| 场景需求 | 参考文件与位置 | 说明 |
| :-- | :-- | :-- |
| **外部 AI 短片无缝嵌合** | `src/render_part2_amazon_clip.py::_load_external_clip` | 用 FFmpeg `lanczos` 重采样 MP4 为精确帧数，并把原声并入 `clip_bus` 触发 BGM 侧链闪避 |
| **多首 BGM 分段无损拼接** | `src/render_xiaban_chaikovsky_clip.py::render_xiaban_video_pipe`, `build_xiaban_sfx_and_mix` | 保存 `sfx_all` / `bgm_ducked` stems，交界处做 0.45~0.5 s crossfade；合集从下半 `T030` 切入避免重复片头 |
| **9 场复杂 3D 沙盘动画器架构** | `src/battle_anim.py` (`BattleAnimatorBase`, `B03Animator`..`B21Animator`) | 城池攻防云梯 `draw_siege_ladder`、洛阳/太原/睢阳/香积寺/邺城/莫州完整战术编排 |
| **河心岛（中潭岛）+ 南北浮桥建模** | `src/tactical_map.py::_draw_island_and_bridges` | 河阳之战（`B16`）临河三城与河心岛不漂浮的标准几何实现 |
| **A/B 配色地形样式快速拼图对比** | `src/render_background_comparison.py` | 低成本本地拼图验证底图样式 |
| **交响史诗配乐参考诊断图** | `audio/amazon_beat_map.png`, `audio/chaikovsky_xiaban_mix_timeline.png` | 管弦曲风大动态跨度下的 `envelope_points` + `-26%` 中频掏槽参考（预设 A） |

> 注：本目录中 `extract_amazon_beats.py`、`render_xiaban_chaikovsky_clip.py` 等原始脚本里含当时本机 `D:\下载\*.mp3` 与历史上传目录路径；移植到新工程时请参照 `docs/00_rules.md` E2 改为 `ROOT` 相对路径与跨平台字体加载。
