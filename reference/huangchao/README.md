# 参考成品 A · 《唐末黄巢起义（874–884）》

> 本目录包含终版已验收工程的全部代码、地理/时间轴数据、音频拍点与混音诊断图、9 张实机抽帧样张（无大体积 `.mp3` / `.wav` / `.mp4`，成品视频在 Google Drive `作品/唐末黄巢起义/` 与本机 `D:\wargame\huangchao\output\huangchao_enog_complete.mp4`）。

---

## 一、核心指标（终版实测）

- 历史跨度：`3528 天`（31 座城池/渡口、4 处离岛地标、5 段大迂回路线累计 `6275.0 km`、16 帧控制权快照、66 次控制权变更）
- 配乐卡点：`ZIIIELI, LJYNNN - Enog.mp3`（`117.454 BPM`，`283` 拍，`146.573s / 4,397 帧 @ 30 fps`）
- 18 幕时长配比：`macro` `85.22s (58.1%)` | `tactical` `26.28s (17.9%)` | `cutscene` `35.07s (23.9%)`
- 成片实测：`1920×1080` `h264 (yuv420p)` + `261 kb/s aac 48000 Hz stereo`，`24.59 MB`，`I = -13.0 LUFS | TP = -0.9 dBFS`

---

## 二、「概念 → 代码位置」精准速查表

| 你要查找什么 | 文件与符号 |
| :-- | :-- |
| 城池初始阵营（修正梁田坡为 `TANG`）与 `ISLAND_LANDMARKS` | `src/data_geo.py` |
| 流动作战逐幕占领与朝廷收复状态机 | `src/data_timeline.py` |
| 史实数据完整性编译与里程计算 | `src/build.py::validate_and_compile` |
| 高精度东亚海岸线（含朝鲜半岛）+ 台琼/日韩/琉球 `ISLAND_POLYS` 扣海 + 南方丘陵 `hill_knolls` + `x_stretch` | `src/hc_terrain.py::build_relief_terrain`, `fit_aspect_bounds`, `compute_smoothed_faction_scores` |
| 18 幕导演脚本（敌我双阵营算子与帅旗）+ 三段前锋场预计算 | `src/hc_campaign_renderer.py::HuangChaoCampaignEngine.__init__` (`act_specs`, `act_scores`, `macro_units`) |
| 96 档超平滑疆界过渡 + 箭头标签防遮挡绘制 | `src/hc_campaign_renderer.py::HuangChaoCampaignEngine._draw_macro` |
| 朱温 4 帧叛降 / 李克用 4 帧入关 / 曲江 / 称帝 / 狼虎谷剧场 | `src/hc_campaign_renderer.py::HuangChaoCampaignEngine._draw_cutscene` |
| 三场双向多军 3D 战术沙盘（`B_GZ` / `B_TG` / `B_WMD`） | `src/hc_tactical.py::Actor`, `HuangChaoTacticalRenderer._build_actors_*`, `render` |
| 黄巢 128×128 五阶段×四帧主角精灵（含面部锚点 `MaxFilter`） | `src/huangchao_sprites_ultra.py::PixelCanvas`, `get_huangchao_sprite` |
| 朱温 / 李克用 128×128 四帧转折精灵 | `src/tang_warlords_sprites_128.py::get_warlord_sprite` |
| Enog 实测测拍 + SFX 量化 + 四总线三层安全混音 | `src/hc_audio_enog.py::_extract_beats`, `_synthesize_beat_locked_buses`, `build_audio_and_mix` |
| 48 kHz 纯合成古战场音效库 | `src/sfx_synth.py` |

---

## 三、目视验证抽帧样本（`frames/`）与诊断图（`audio/`）

- [`frames/01_T04_macro_both_sides.jpg`](frames/01_T04_macro_both_sides.jpg)：`T04` 宏观棋盘（山东已翻红归唐、高骈淮南阻击对峙、清晰圆角标签与完整西部山脉）
- [`frames/02_B_GZ_siege_two_sides.jpg`](frames/02_B_GZ_siege_two_sides.jpg)：`B_GZ` 广州双向攻防（唐守将+云梯+破门入骑+珠江双木桥）
- [`frames/03_B_TG_pass_flank.jpg`](frames/03_B_TG_pass_flank.jpg)：`B_TG` 潼关（尚让正面强攻 vs 张承范守军 + 林言禁谷绕后）
- [`frames/04_T13_zhuwen_4frame.jpg`](frames/04_T13_zhuwen_4frame.jpg)：`T13` 朱温「献印降唐」与孤城黄巢对峙
- [`frames/05_T14_LK_likeyong_4frame.jpg`](frames/05_T14_LK_likeyong_4frame.jpg)：`T14_LK` 李克用「独眼挽弓」与沙陀黑骑南下关中
- [`frames/06_B_WMD_bridges.jpg`](frames/06_B_WMD_bridges.jpg)：`B_WMD` 王满渡（李克用/朱温北岸桥头箭矢合围尚让、黄巢）
- [`frames/07_T15_REV_reclaimed.jpg`](frames/07_T15_REV_reclaimed.jpg)：`T15_REV` 全国收复翻红仅余泰山孤蓝点（含台琼及朝鲜半岛/日本海疆）
- [`frames/08_T06_coast_islands_hills.jpg`](frames/08_T06_coast_islands_hills.jpg)：`T06` 升级东亚全岸线 + 朝鲜半岛/日本列岛/琉球/台琼完整露出 + 左下角收紧
- [`frames/09_T08_jiangnan_hills.jpg`](frames/09_T08_jiangnan_hills.jpg)：`T08` 长江以南江南/浙闽/两广丘陵与东亚海疆完整地形对比
- [`audio/enog_huangchao_beat_map.json`](audio/enog_huangchao_beat_map.json) & [`audio/enog_huangchao_mix_timeline.png`](audio/enog_huangchao_mix_timeline.png)：18 幕时间真源与混音四合一诊断图
