---
name: comet
description: 彗星（目标名像 C/2025 R3、C2025-R3、12P/...，或 inspect_target 类型为 comet）——少帧、混合曝光、有云、有卫星轨迹也能用：按星和按彗核分别叠加（comet_stack），再跑 comet 配方。处理任何彗星时加载。
---

# 彗星

方法、每个判断的来历和教训：`read_knowledge('comets')`（knowledge/comets.md）。参考作品要按日期筛（彗星几天就变样），`get_references` 拿到后看标题日期是否接近。

## 流程
1. 先要有 WBPP 的 Output/registered（`stack`，只用到配准好的单帧）。
2. `comet_stack`（10–15 分钟）：每帧背景 → 星点测光统一亮度 → 白平衡 → SXT 去星（并补回被误删的彗发、去掉 SXT 造成的背景偏移）→ 灵活背景去云带 → 权重（噪声 × 透明度；云、卫星轨迹、无数据处为 0）→ 彗星层（按彗核对齐）+ 星点层（按星对齐）。
   - 看返回的每帧 relative_weight、cloud_fraction、trails；需要时 `look(images=['weights'])`（黑 = 被剔除）。
3. `run_stage` 依次跑 comet 配方：linear（第一次带 `recipe='comet'`）→ stretch → starless → stars_color → combine。
   - **不要在彗星图上跑 SXT**：它会把明亮的彗发当成星。配方里星点是用两层做 screen 逆运算分出来的（split_stars）。

## 检查
- 彗发完整、没有圆盘状色晕（彗发周围出现有边界的圆 = 去星修复出了问题，报告给用户）。
- 彗尾连贯，没有被云掩膜切断；没有卫星轨迹残留；星点圆、不拖线。
- 天空中性且暗（参考作品的天空中位约 0.09；`ht.skyTarget` 控制），主体色度比按用户偏好。
- 彗发应偏青绿（C2），离子尾偏蓝；尘埃尾偏白/黄。

## 常用调整
- 颜色淡：`starless.sat.boost` 0.80→0.85；天空太亮/太暗：`starless.ht.skyTarget`。
- 噪声重：`linear.nxt.params.denoise` 0.45→0.55，或 `starless.nxt2`。
- 改了叠加后面的步骤要重跑叠加时 `comet_stack(reuse_sxt=true)`，省掉 PixInsight 去星。

## 给用户的拍摄建议（如果数据有这些问题）
统一曝光、不要混 Bin2；多拍几帧比单帧更长更有用（云和轨迹按帧剔除）；补平场。
