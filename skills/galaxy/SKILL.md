---
name: galaxy
description: 星系目标的配方 osc_galaxy（PixInsight 进阶教程第2期，M31）：DBE 避开星系、BNCC 以星系为白参考、EZ HDR 压核心、范围蒙版下的 LHE 与二次饱和度。处理任何星系时加载。
---

# 星系（配方 osc_galaxy）

来源：教程视频第 2 期（M31）。完整流程：`read_knowledge('ep2')`；默认值：`show_recipe('osc_galaxy')`。

## 和星云配方的区别（为什么）
- **背景**：GradientCorrection 会把大星系当背景减掉 → 用 `dbe_auto`（多项式背景，避开星表椭圆 × objectScale 1.8）。检查 `10_gc_model`/模型预览里不能出现星系形状。
- **色彩**：SPCC 优先；退回 BNCC 时以星系本体为白参考（whiteROI = object，structureDetection 关）。
- **线性降噪更轻**（0.25）：星系信噪比高，细节更重要。
- **核心**：`hdr`（EZ HDR 移植，5 层，强度 0.3）压亮核心；拉伸目标中值 0.20，核心过曝就降到 0.15–0.18。
- **LHE**：半径按星系大小自动（0.35×半长轴，上限可设 radiusMax），通过范围蒙版只作用在星系上。
- **饱和度两次**：HT 对比之后再加一次（sat2）。

## 经验
- M101 这类小星系在视场里不大：用 `export_crop` 出裁切版。
- 星系颜色：核心暖黄、旋臂偏蓝、HII 区粉红点；背景要中性灰、不偏绿。
- 一晚 1–2 h 的星系达不到参考作品的深度是正常的，报告里写明差距来源。
