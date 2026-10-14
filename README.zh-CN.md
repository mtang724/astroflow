# astroflow

[English](README.md) | **简体中文**

天文摄影后期自动化：Windows 和 macOS 桌面应用（也有命令行）。把一晚的拍摄数据配上合适的校准帧整理好，用无界面的 WBPP 叠加，再在无界面的 PixInsight 里按教程整理出的配方出图；彩色相机、黑白相机（LRGB）都支持，隔着云拍的彗星也能处理。每个目标都会和同一天体的高赞作品对比，AI 助手（任何 OpenAI 兼容模型：DeepSeek、OpenAI，或本地的 Ollama / LM Studio）检查每个阶段的结果，调参数直到满意。

从“拍完的一晚数据”到“成品图”：导入整理 → 单帧检查 → 叠加（几晚也能合成一张）→ 按目标类型的配方出片（每一步参数可调）→ 和高赞作品对比 → AI 助手判断与调参 → 分享图。

**[下载](https://github.com/mtang724/astroflow/releases) · [使用说明](docs/user-guide.md) · [0.2.1 发布说明](docs/releases/v0.2.1.md)**

![astroflow 主界面](docs/images/overview.png)

## 桌面应用（Windows / macOS）

- **导入新数据**：选一个拍摄文件夹（ASIAIR、NINA、SharpCap 等的导出，存储卡，或已经分好 Light/Dark/Bias/Flat 的目标文件夹）。FITS 和单反 / 微单的 RAW 文件（CR2、CR3、NEF、ARW、DNG、RAF …）都行。按文件头认出帧类型（RAW 看文件夹名），按目标和日期整理，暗场 / 偏置 / 平场先用同一批拍的，缺的再从校准帧库找；只有校准帧的文件夹会放进校准帧库并补给缺它们的目标。先看计划再执行（默认复制，不动原文件）。
- **目标页**：
  - 概览：成品、拍摄数据、校准帧与警告、这一晚用的滤镜、下一步该做什么；同一目标拍了几晚时，一键合并叠加（每晚用自己的平场）
  - 单帧检查：每帧的缩略图、星点数、星点大小和背景，标出被云、风、跑焦、天亮影响的帧，一键排除（可恢复）
  - 处理流程：每个阶段、每个步骤的参数，改了就保存，可以只重跑一个阶段或从某阶段跑到最后；调好的参数可以存成“我的风格”，套用到同类目标
  - 图像：各阶段预览、成品、参考作品，可以缩放、两张图对比
  - AI 助手：用一句话说想要的效果，它会调用工具处理，过程逐步可见
  - 分享图：裁成 3:4（小红书）、16:9（B站）等比例，可加拍摄信息和署名
- **黑白相机 LRGB**：WBPP 按滤镜叠出 L/R/G/B 主帧后自动用黑白配方：通道对齐与裁切、各自去背景、合成彩色、L 单独去卷积降噪，再按亮度合成（教程第 3 期）。
- **全部处理**：把还没出图的目标排队，一个接一个叠加、出图；在后台跑完时弹出系统通知。
- **任务栏**：一次只跑一个 PixInsight 任务，实时日志，随时停止（会结束 PixInsight 进程）。
- **中文 / English 界面**：设置里切换，默认跟随系统；AI 助手也用同一种语言回答。
- **自动更新**：启动时检查 GitHub 上的新版本。Windows 下载后重启即装好（或下次关闭时自动安装）；macOS 预览版打开下载页。
- **磁盘空间和归档**：看每个目标占多少空间，一键删掉可以再生成的中间文件（保留原始帧、叠加结果和成品）；处理完的目标一键归档到 `Processed\`。
- **检查运行环境**：第一次打开时检查 PixInsight、WBPP、RC Astro 插件（是否激活）、Gaia 数据库、数据目录和 AI 模型，缺什么列出来并一步步说明怎么装；能自动处理的（找到的 PixInsight 路径、创建数据目录）点一下就好。
- **设置**：数据根目录、PixInsight 位置、AI 服务商（任何 OpenAI 兼容接口，包括本地模型）；API 密钥存放在系统钥匙串（Windows 凭据管理器 / macOS 钥匙串），不会写进文件，界面上也不显示。

安装包：`desktop/dist/astroflow-<版本>-setup.exe`（Windows），`.dmg`（macOS，由 GitHub Actions 在 Mac 上构建）。
开发、架构和打包见 [`desktop/README.md`](desktop/README.md)。

## 准备

- PixInsight 1.9.x（含 WBPP），RC Astro 三件套（BXT / NXT / SXT），SPCC 用的 Gaia DR3/SP 数据库（在 PixInsight 界面里配置好）
- 从源码运行：Python 3.12+ 与 `pip install -r requirements.txt`；桌面应用另需 Node 24（`cd desktop && npm install && npm run dev`）
- 视频学习（可选，NVIDIA GPU）：`pip install -r requirements-video.txt` 与 ffmpeg

## 命令行

```powershell
# 导入拍摄数据（先预览，再 --apply 执行）；--source 导入别处的文件夹，--copy 不移动光照帧；--refresh 用校准帧库补全已整理的目标
python -m astroflow organize [--apply] [--refresh] [--source <文件夹>] [--copy]

# 暗场后来在 ASIAIR 上补拍：等拍够再导入暗场库、补校准、重新叠加（在 PowerShell 里运行，Git Bash 看不到网络共享）
python -m astroflow.darks --source "\\<ASIAIR 的 IP>\EMMC Images\Autorun\Dark" --exptime 300 --settemp -10 --count 10 --since 2026-10-10 --wait --then restack

# 让 AI 处理一个目标（叠加 + 全流程后期 + 自检 + 报告），或按要求重调
python -m astroflow agent "M8"
python -m astroflow agent "M8" --task "只重做 starless 阶段，饱和度再高一点"

# 不用 AI：按默认配方跑，或改某个参数只重跑某一段
python -m astroflow process "M8"
python -m astroflow process "M8" --from starless --set starless.sat.boost=0.8

# 彗星（少帧、混合曝光、有云也行）：WBPP 之后，按星和彗核分别叠加，再用 comet 配方收尾
python -m astroflow comet "F:\AstroPhotograph\C2025-R3"

python -m astroflow doctor                 # 检查这台电脑缺什么组件、怎么装
python -m astroflow status                 # 每个目标的进度
python -m astroflow refs "NGC 7293"        # 抓同目标高赞作品作参考
python -m astroflow video "<教程.mp4>"      # 新教程视频 → 转写 + 截图，整理进资料库
```

- **每晚用的滤镜**记在 `In Processing\<日期>\session.json`（FITS 头里没有；应用里在目标概览页选）：无滤镜 `osc_broadband`，Antlia 四通道等多波段 `osc_multiband`。它决定配方、色彩校准方式和参考作品分组。黑白相机不用记：每个滤镜一张主帧（`..._FILTER-L_mono.xisf`），配方据此选 `mono_lrgb_*`。
- **运行时请关闭 PixInsight 界面**：无界面任务需要独占 PixInsight（第二个实例读不到 Gaia 星表配置，BXT 也会崩溃），任务会自动排队等待。

## 结果在哪里
`<数据根目录>\In Processing\<日期>\<目标>\Post\`
- `<目标>_<日期>.png / .jpg / .tif`：成品（PNG/JPG 8 位全分辨率，16 位 TIFF 可进 PS 继续调）；小目标另有 `_crop` 裁切版
- `previews\`：每一阶段的预览图；`report.md`：AI 的处理报告；`NN_*.xisf`：各阶段检查点
- `params.json`：你在应用里改过的参数。以后每次运行都会用（应用、AI 助手、命令行都一样）；`state.json`：各阶段的运行记录
- `share\`：分享图
- 满意后在应用里“归档”，整个目标文件夹移到 `Processed\`

## 组成
| 部分 | 位置 |
|---|---|
| 桌面应用（Electron + React） | `desktop/`（见 `desktop/README.md`） |
| 本地 API（应用的后端） | `astroflow/api/`（FastAPI，只监听本机，每次启动一个令牌） |
| 应用服务：任务队列、目标、可调参数、我的风格、全部处理 | `astroflow/services/` |
| 设置（路径、AI 服务商、偏好；密钥进系统钥匙串） | `astroflow/settings.py`，`config.py` 读它 |
| 环境检查（缺什么组件、怎么装；不启动 PixInsight，读它的设置槽 1） | `astroflow/doctor.py` |
| 整理 | `astroflow/organize.py`（根目录 `organize.py` 兼容旧命令），读 FITS 和相机 RAW：`astroflow/frameio.py` |
| 单帧检查、多晚合并、磁盘空间与归档、分享图 | `astroflow/framecheck.py`、`multinight.py`、`storage.py`、`share.py` |
| 黑白相机：每个滤镜一张主帧 | `astroflow/mono.py` |
| 统一命令行入口 | `python -m astroflow`（`astroflow/__main__.py`） |
| 叠加（WBPP 命令行自动化） | `astroflow/wbpp.py` |
| 后期配方（宽带星云 / 星系 / 多波段星云 / 彗星 / 黑白 LRGB） | `astroflow/pipeline.py` + `astroflow/pjsr/*.js`（PixInsight 端步骤库） |
| 彗星叠加（云、卫星轨迹、彗核运动、去星） | `astroflow/comet.py`，方法与教训见 `knowledge/comets.md` |
| 无界面 PixInsight 运行器（串行锁、看门狗、可取消） | `astroflow/pi.py`，`astroflow/jobctx.py` |
| 指标 / 参考作品 / 星表 / 暗场导入 | `astroflow/metrics.py`、`references.py`、`objects.py`、`darks.py` |
| AI agent（任何 OpenAI 兼容模型；不支持工具调用的本地模型走提示词模式） | `astroflow/agent/`（`session.py`、`tools.py`、`skills.py`） |
| 技能：沉淀下来的处理经验，agent 按需加载（同 Claude Agent Skills 格式） | `skills/<名字>/SKILL.md` |
| 资料库（流程、参数、检查标准、坑、目标笔记） | `knowledge/`（见 `knowledge/README.md`） |
| 测试 | `tests/`（`python -m pytest -q`） |
| 使用说明、发布说明、计划 | `docs/`（`user-guide.md`、`releases/`、`plans/`，截图在 `docs/images/`） |
| 打包 | `packaging/backend.spec`（PyInstaller），`desktop/electron-builder.yml`，`.github/workflows/desktop.yml` |
| Claude Code skill / 子 agent | `.claude/skills/astro-postprocess/`、`.claude/agents/astro-reviewer.md` |

## 不在仓库里的东西
教程视频及其截图和转写稿（版权），AstroBin 参考缩略图（他人作品，仅本地比较用；`refs.json` 保留标题、作者和链接），运行日志 `.runs/`，`.env`，打包输出。

## 致谢

后期配方的流程和默认参数整理自 B 站 UP 主氪化金的《PixInsight 进阶教程》第 1 期（[BV14LthzDEyh](https://www.bilibili.com/video/BV14LthzDEyh)）、第 2 期（[BV1C3tozEEAD](https://www.bilibili.com/video/BV1C3tozEEAD)）和第 3 期（[BV1AUbbz5EUu](https://www.bilibili.com/video/BV1AUbbz5EUu)），感谢作者的分享。

## 版权

© 2026 Ming，保留所有权利。可以在 GitHub 上查看代码，也可以下载发布页的安装包个人、非商业地使用；未经书面许可，不得复制、修改、再分发代码，也不得用于商业用途。需要授权请在 Issues 里联系。详见 [LICENSE](LICENSE)。
