---
name: astro-workflow
description: 总流程——任何“处理/重新处理/调整某个目标”或“处理新拍的数据”的任务都先加载它：决定先做什么、何时加载哪个类型技能、每个阶段怎么检查、怎么收尾和写报告。
---

# 处理一个目标的总流程

## 1. 摸清目标
1. `inspect_target`：拍摄概况（曝光、总时长、温度）、校准帧是否齐全（calibration_warnings）、星表信息、**类型**和建议配方、已经跑过的阶段。
2. 按类型加载技能：发射/反射星云、行星状星云、超新星遗迹 → `nebula-broadband`；那晚用了多波段滤镜（session.filter_class = osc_multiband）→ `nebula-multiband`；星系 → `galaxy`；彗星 → `comet`。类型是 unknown 时按天体常识判断，第一次 `run_stage` 用 `recipe` 指定。
3. `get_references`：同目标高赞作品（best = IOTD/Top Pick，peer = 同类器材）与数值指纹；有 notes 就读。参考作品用来校准“应该长什么样”，不是照抄配色。
4. 读 `read_knowledge('targets/<目标>/agent')`（以前跑这个目标的经验），有就照着避坑。

## 2. 叠加
- 没有 master 才需要 `stack`（WBPP，5–20 分钟）。calibration_warnings 里有“缺少暗场”（旧目标写作 NO DARKS）：不要直接叠加，告诉用户缺哪个暗场（见 `organize-and-calibrate`）；用户明确说可以不用暗场时再叠加。
- 彗星不走普通 master，见 `comet` 技能。

## 3. 按配方阶段处理（每个阶段一次 PixInsight 任务）
顺序：linear → stretch → stars → starless → stars_color → combine（彗星配方没有 stars 阶段，见 `comet`）。
每跑完一个阶段都检查——加载 `judge-and-tune`：先看返回的数字，再用 `look` 看预览图（可带 `ref:peer_00` 这类参考图一起比较），不满意就带 overrides 重跑这个阶段。
- 重跑一个阶段会作废它之后的阶段，所以从出问题的最早阶段改起。
- 每次只改一两个参数，说明理由；同一阶段最多重跑 3 次。

## 4. 收尾
1. combine 之后用 `compare_with_references(stage='combine')` 再核一次主体色度比（目标见系统提示的用户偏好），不足就回 starless 加饱和度。
2. 小目标（在视场里很小）可以 `export_crop`。
3. `finish`：中文总结写进 Post/report.md——做了什么、关键参数、与参考的差距（来自积分时间还是处理）、需要用户确认或下次拍摄改进的地方。
4. `remember`：这个目标上有用的经验（哪些参数有效、哪里踩坑），下次运行会读到。

## 新拍的数据（任务没有指定目标时）
`organize`（默认只预览；用户要求时 apply=true，外部文件夹用 source=，从存储卡导入用 copy=true）→ `list_targets` → 有暗场、没有 master 的目标 `stack` → 逐个按上面的流程处理 → 最后汇总每个目标的结果与报告路径。

## 回答用户
简洁：每个目标一两行结果 + 成品路径 + 需要用户决定的事。不要罗列每一步的过程。
