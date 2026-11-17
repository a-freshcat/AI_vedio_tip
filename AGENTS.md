# AGENTS.md — 给接手本项目的 AI 模型

你正在接手一个「历史兵棋科普视频」项目：用 Python（Pillow + NumPy + librosa + FFmpeg）**程序化**生成 1920×1080 的战役推演视频，并与用户指定的 BGM 卡点混音。

## 开工前必读顺序（不要跳）

1. [docs/00_rules.md](docs/00_rules.md) —— 硬性铁律，违反即判废
2. [docs/01_pipeline.md](docs/01_pipeline.md) —— 六阶段流水线 + 每阶段的验收关卡（Gate）
3. [docs/04_audio.md](docs/04_audio.md) —— BGM 测拍、分幕、混音参数（两套预设）
4. [docs/02_pitfalls.md](docs/02_pitfalls.md) —— 已踩过的坑：症状 → 原因 → 修法 → 怎么提前发现
5. 需要写代码时：[reference/huangchao/README.md](reference/huangchao/README.md) —— 已验收成品的完整源码与「概念 → 代码位置」对照表

其余文档按需查：[03 工具链与模块索引](docs/03_toolchain_and_modules.md)、[05 黄巢案例复盘](docs/05_case_huangchao.md)、[06 验收清单](docs/06_acceptance_checklist.md)、[07 交接提示词模板](docs/07_prompt_template.md)。

## 不可协商的 8 条（细节见 00_rules）

1. 全片默认是**全屏立体地形棋盘**；禁止左右分屏 / 常驻人物侧栏。
2. **先测 BGM 再分幕**：librosa 实测 BPM / beats / 能量段落之后，才允许写时间轴。禁止等距假幕次。
3. 每一幕（棋盘和沙盘都算）都必须有**敌我双方**的算子 / 帅旗 / 交互。
4. 流动作战必须逐幕写**收复**：主力离开且无留守的城池要翻回原阵营。
5. 势力边界不能落后于行军箭头；视口覆盖中国西部时必须做全青藏 / 横断 / 四川盆地 / 云贵地形。
6. 仓库里已有的人物多帧精灵，要给完整的多帧转折演出，不能闲置或只放单帧。
7. 写实红线：城不在水上、骑兵不飞墙（步兵爬云梯，破门后骑兵入城）、过河必有桥/渡口。
8. 长渲染前先过：全幕冒烟测试 → 关键帧出图目视检查；成片后用 ebur128 实测 MP4 响度（目标 −13.1 ~ −12.7 LUFS）。

## 沟通约定

- 分幕表（storyboard）定稿前**先给用户确认**再渲染全片，避免整版返工（历史上多次整版被否都源于此）。
- 汇报只写**实测**过的数字（时长、帧数、LUFS、文件大小）；没测的不要写。
- 不要提交 mp3 / mp4 / wav 到仓库（见 `.gitignore`）；媒体文件在 Google Drive `作品/` 与本机 `D:\wargame\` 下。
