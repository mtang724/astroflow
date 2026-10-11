# astroflow

Automated deep-sky astrophotography post-processing for a one-shot-colour camera (ZWO ASI2600MC) on Windows:
organise a night's frames with matching calibration, stack with headless WBPP, post-process in headless PixInsight
following recipes learned from tutorial videos, compare every target with top-rated works of the same object, and let
a DeepSeek agent judge each stage (numbers + vision) and tune parameters until the result holds up.

从“拍完的一晚数据”到“成品图”：整理 → 叠加 → 按教程流程后期 → 和高赞作品对比 → DeepSeek agent 判断与调参 → 报告。

## 安装

- Windows，Python 3.12+：`pip install -r requirements.txt`
- PixInsight 1.9.x（含 WBPP），RC Astro 三件套（BXT / NXT / SXT），SPCC 用的 Gaia DR3/SP 数据库（在 PixInsight 界面里配置好）
- 视频学习功能另需 ffmpeg 与 NVIDIA GPU（faster-whisper）
- DeepSeek API key 写在项目根目录 `.env`：`api_key=...`（已在 `.gitignore` 里，不会提交）
- 路径与器材默认值在 `astroflow/config.py`；本机不同的话，在根目录放 `config.local.json` 覆盖（如 `{"ASTRO_ROOT": "F:/AstroPhotograph"}`）

## 日常用法

```powershell
# 1. 整理新拍的目标文件夹（先预览，再执行）；补拍暗场后给已整理的目标补校准帧
python organize.py
python organize.py --apply
python organize.py --refresh --apply

# 暗场后来在 ASIAIR 上补拍：等拍够再导入暗场库、补校准、重新叠加（在 PowerShell 里运行，Git Bash 看不到网络共享）
python -m astroflow.darks --source "\\10.0.0.161\EMMC Images\Autorun\Dark" --exptime 300 --settemp -10 --count 10 --since 2026-10-10 --wait --then restack

# 2. 让 agent 处理一个目标（叠加 + 全流程后期 + 自检 + 报告），或按要求重调
python -m astroflow agent "M8"
python -m astroflow agent "M8" --task "只重做 starless 阶段，饱和度再高一点"
python -m astroflow agent --task "看看哪些目标可以处理，逐个处理"

# 3. 不用 agent：按默认配方跑，或改某个参数只重跑某一段
python -m astroflow process "M8"
python -m astroflow process "M8" --from starless --set starless.sat.boost=0.8

# 其他
python -m astroflow status                 # 每个目标的进度
python -m astroflow refs "NGC 7293"        # 抓同目标高赞作品作参考
python -m astroflow video "<教程.mp4>"      # 新教程视频 → 转写 + 截图，整理进资料库
```

- **每晚用的滤镜写在 `In Processing\<日期>\session.json`**（FITS 头里没有）：无滤镜 `osc_broadband`，Antlia 四通道等多波段 `osc_multiband`，决定配方、色彩校准方式和参考作品分组。
- **运行时请关闭 PixInsight 界面**：无界面任务需要独占 PixInsight（第二个实例读不到 Gaia 星表配置，BXT 也会崩溃），任务会自动排队等待。

## 结果在哪里
`F:\AstroPhotograph\In Processing\<日期>\<目标>\Post\`
- `<目标>_<日期>.png / .jpg / .tif`：成品（PNG/JPG 8 位全分辨率，16 位 TIFF 可进 PS 继续调）；小目标另有 `_crop` 裁切版
- `previews\`：每一阶段的预览图；`report.md`：agent 的处理报告；`NN_*.xisf`：各阶段检查点
- 满意后由你把整个目标文件夹移到 `Processed\`

## 组成
| 部分 | 位置 |
|---|---|
| 整理脚本 | `organize.py` |
| 统一入口 | `python -m astroflow`（`astroflow/__main__.py`） |
| 叠加（WBPP 命令行自动化） | `astroflow/wbpp.py` |
| 后期配方（宽带星云 / 星系 / 多波段星云） | `astroflow/pipeline.py` + `astroflow/pjsr/*.js`（PixInsight 端步骤库） |
| 无界面 PixInsight 运行器（串行锁、看门狗） | `astroflow/pi.py` |
| 指标 / 参考作品 / 星表 / 暗场导入 | `astroflow/metrics.py`、`references.py`、`objects.py`、`darks.py` |
| 视频学习工具 | `astroflow/video.py` |
| DeepSeek agent | `astroflow/agent/`（规划 deepseek-v4-pro，看图 deepseek-flash） |
| 资料库（流程、参数、检查标准、坑、目标笔记） | `knowledge/`（见 `knowledge/README.md`） |
| Claude Code skill / 子 agent | `.claude/skills/astro-postprocess/`、`.claude/agents/astro-reviewer.md` |

## 不在仓库里的东西
教程视频及其截图和转写稿（版权），AstroBin 参考缩略图（他人作品，仅本地比较用；`refs.json` 保留标题、作者和链接），运行日志 `.runs/`，`.env`。
