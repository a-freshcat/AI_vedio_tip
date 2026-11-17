# making-history · 历史兵棋视频制作工作流与参考库

> 供 AI 模型与作者在新建 / 重制「历史兵棋科普视频」时直接拉取使用的标准规范仓。
> 用 Python（Pillow + NumPy + SciPy + librosa + FFmpeg）程序化生成 `1920×1080 @ 30 fps` 全屏 3D 地形推演 + 战术沙盘视频，并与 BGM 实测拍点混音成片。

## 给 AI 模型的阅读入口

请直接从 **[AGENTS.md](AGENTS.md)** 开始阅读，它规定了不可协商的 8 条红线与文档阅读顺序：

| 文档 / 目录 | 作用 |
| :-- | :-- |
| [AGENTS.md](AGENTS.md) | AI 模型入口：阅读顺序、8 条硬红线、沟通约定 |
| [docs/00_rules.md](docs/00_rules.md) | 画面版式、战场调度、物理写实、音频、工程五域硬性铁律 |
| [docs/01_pipeline.md](docs/01_pipeline.md) | 六阶段流水线 + G1–G6 逐关验收机制 |
| [docs/02_pitfalls.md](docs/02_pitfalls.md) | 安史版 & 黄巢版累计踩坑库（症状 → 原因 → 修法 → 提前发现） |
| [docs/03_toolchain_and_modules.md](docs/03_toolchain_and_modules.md) | Python 技术栈、跨平台字体加载与双参考项目模块抄用索引 |
| [docs/04_audio.md](docs/04_audio.md) | BGM 测拍、两套曲风混音预设（交响 A / 电音 B）、4 总线混音与 AAC 响度修正 |
| [docs/05_case_huangchao.md](docs/05_case_huangchao.md) | 最新验收基准《唐末黄巢起义》复盘与 7 张实机抽帧剖析 |
| [docs/06_acceptance_checklist.md](docs/06_acceptance_checklist.md) | G1–G6 逐项打勾验收单 |
| [docs/07_prompt_template.md](docs/07_prompt_template.md) | 开新项目 / 审查重置半成品的即拷即用提示词模板 |
| [tools/qa_tools.py](tools/qa_tools.py) | 自动化校验脚本（控制权快照排查 / 全幕冒烟 / `ebur128` 响度 / 成片抽帧） |
| [reference/huangchao/](reference/huangchao/README.md) | **首选主参考**：完整 14 个脚本 + 数据 + 节拍/混音图 + 7 张抽帧样本 |
| [reference/anshi/](reference/anshi/README.md) | **扩展场景参考**：18 个脚本 + 数据 + 外部短片嵌合 / 多曲拼接 / 河心岛浮桥 |

## Git 与 Google Drive 分工

- **本仓库（Git / GitHub）**：存放全部方法论文档、校验脚本与两套参考项目的精炼源码 / 数据 / 轻量级诊断图与抽帧样本（唯一文档与代码真源）。
- **Google Drive**：存放高体积的原始配乐 `.mp3`、中间 `.wav` 与最终 `.mp4` 成片（`作品/`），以及同步一份 `making_history/` 在线文档副本。
