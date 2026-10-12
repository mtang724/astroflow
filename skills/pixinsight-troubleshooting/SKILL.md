---
name: pixinsight-troubleshooting
description: 无界面 PixInsight 任务失败、卡住、结果异常时的排查——一次只能一个实例、设置槽 2、模态对话框卡死、DynamicCrop 删星图解析、RC 工具静默失败、console.txt 在哪里。任何 run_stage / stack / comet_stack 报 PixInsight 错误时加载。
---

# PixInsight 排查

完整清单：`read_knowledge('pitfalls')`。

## 先看哪里
- 每个任务一个目录 `<runs>/<目标>-<阶段>-<时间>/`：`console.txt`（PixInsight 控制台全文，出错先看它）、`pi.log`（步骤进度）、`job.json`、`result.json`。工具报错信息里通常带着目录。

## 常见原因
- **另一个 PixInsight 开着**（用户的界面）：无界面任务会等它关闭；第二个实例用设置槽 2，那里没有 Gaia 数据库路径（SPCC 失败）、BlurXTerminator 会崩溃。请用户关掉 PixInsight 界面。
- **模态对话框**：参数非法或确认框会让无界面实例卡住；看门狗在 CPU 空闲超过限制后结束进程，并报告当时打开的窗口标题（如 `['DynamicCrop', 'PixInsight']`）——说明是哪个步骤弹了框，改参数而不是重试。
- **DynamicCrop 会删除星图解析**：裁切只能在 SPCC 之后（非线性阶段或成品导出时）。
- **RC 工具（BXT/NXT/SXT）失败不抛异常**：步骤会检查返回值并报“did not run”，看 console.txt 里的原因（GPU、授权、内存）。
- **彗星**：SXT 会把彗发当星，不要在彗星图上跑 SXT（comet 配方已经避开）。

## 处理原则
- 同一个错误连续两次就停下，在 finish 里写明错误和 console.txt 的关键行，交给用户。
- 不要通过关掉检查（比如去掉看门狗、改用第二实例）来“绕过”错误。
