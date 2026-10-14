---
name: mono-lrgb
description: 黑白相机 L/R/G/B 主帧的配方 mono_lrgb_galaxy / mono_lrgb_nebula（PixInsight 进阶教程第3期，M51）：通道对齐与裁切、各通道单独去背景、RGB 合成与 BNCC、BXT/降噪只做 L、L 按彩色图亮度拉伸后 LRGB 合成。目标是黑白相机拍的（每个滤镜一个主帧）时加载。
---

# 黑白相机 LRGB（配方 mono_lrgb_galaxy / mono_lrgb_nebula）

来源：教程视频第 3 期（M51）。完整流程：`read_knowledge('ep3')`；默认值：`show_recipe('mono_lrgb_galaxy')`。
WBPP 对黑白相机按滤镜分别叠加（`..._FILTER-L_mono.xisf` 等），有 R、G、B 主帧时自动用这两个配方；星系用 galaxy，星云用 nebula（后半段同宽带星云配方）。

## 阶段
1. **channels**：R/G/B 对齐到 L → 裁到四个通道都有数据的区域 → 板解析 → 定位目标 → 每个通道单独去背景（星系 `dbe_auto`，星云 GC）→ 合成彩色图。输出 `10_rgb`、`10_lum`。没有 L 时用 R/G/B 的平均当 L。
2. **color**：BNCC（星系以星系本体为白参考，关结构检测）。SPCC 需要所用滤镜的曲线，默认不用。
3. **lum**：（星系先补一次 GC）→ BXT → NXT 0.25，彩噪 0（单通道）。
4. **stretch**：RGB EZ Soft Stretch 0.24；L 拉到和 RGB 的 CIE L* 中值一样亮；LRGBCombination 只用 L，Saturation 0.40。
5. 之后 stars → starless → stars_color → combine，同彩机。

## 判断与调参
- **颜色发灰、被冲淡**：L 太亮或饱和度不够 → `stretch.lrgb.saturation` 调低（0.35 更浓），或者降 L 的拉伸（`stretch.stretch_l.matchScale` 小于 1，比如 0.9）。
- **过曝**：视频里是 L 拉过头了；这里 L 自动匹配 RGB 亮度，仍过曝就降 `stretch.stretch.targetMedian`（0.20），或 `matchScale` 0.9。
- **彩色星点边缘错位（红/蓝边）**：对齐失败或通道不是同一视场 → 看 `channels` 阶段 `align_channels` 的结果。
- **背景模型里有星系形状**：`dbe` 的 `objectScale` 调大。
- **小星系不锐化**：视频里 USM 让图显得假，`usm` 默认关闭；星系够大、细节不够时再打开。
- RGB 噪声多是正常的（RGB 拍得短）：LRGB 合成后由 L 提信噪比，非线性降噪的彩噪可以高（0.9）。
