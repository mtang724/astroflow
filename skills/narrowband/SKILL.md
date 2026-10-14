---
name: narrowband
description: 窄带配方（教程第4、5期）：黑白 HOO（mono_hoo_nebula）、黑白 SHO 哈勃色（mono_sho_nebula）、彩机两套双窄带合成 SHO（osc_sho_nebula）——通道对齐合成、窄带色彩平衡、颜色蒙版调色、RGB 或还原色星点。目标的主帧是 Hα/OIII/SII（filter_class 为 mono_hoo、mono_sho、osc_sho）时加载。
---

# 窄带（配方 mono_hoo_nebula / mono_sho_nebula / osc_sho_nebula）

来源：`read_knowledge('ep4a')`（黑白 HOO）、`read_knowledge('ep5a')`（黑白 SHO）、`read_knowledge('ep5b')`（彩机 SHO）；滤镜：`read_knowledge('filters')`。

## 怎么选
- 黑白，有 H 和 O → HOO；再有 S → SHO。拍了 R/G/B 时多一个 `rgb_stars` 阶段：RGB 单独去背景、校色、BXT、拉伸、去星，用它的星点替换窄带星点。
- 彩机：一套 Hα+OIII（osc_multiband）→ `nebula-multiband` 技能；Hα+OIII 和 SII+OIII 两套（几晚合并，各叠一张）→ `osc_sho_nebula`。

## 阶段
1. **channels**：所有通道对齐到 H（彩机：对齐到 HO 主帧）→ 裁到共同区域 → 合成（HOO：R=H、G=O、B=O；SHO：R=S、G=H、B=O；彩机 SHO：S = SO 的 R，H = HO 的 R，O = 两张 G/B 的平均）→ 板解析、定位。
2. **linear**：GC → 色彩平衡（HOO：SPCC 窄带模式，带宽 `cc.bandwidth`；SHO：BNCC，白参考取星云亮区，**不做 SPCC**）→ BXT → NXT。
3. **stretch**：EZ（HOO 0.25 / 激进度 44.9；SHO 0.23 / 46.6）。
4. **stars**：SXT（HOO 逐通道去星，免得把红色星云当星点）。
5. **starless**：颜色蒙版调色（`mask: "color"`，`maskColor` blue/yellow/…）、L 蒙版饱和度、对比度曲线、NXT、`ht` 的 `channelShadows: "sky"` 配平背景。
6. **stars_color**：有 RGB 星点就换上；SHO 没有时用 `nb_star_colors` 还原星色。

## 判断与调参
- **SHO 还是绿**：`sat.rgb.G` 再降（-0.08），`gold` 的 S 再提；哈勃色应几乎没有绿。
- **金色不够 / 太橙**：`gold.channels.R` 的第二点上下调。
- **OIII 不够蓝**：`oiii_blue` 的 B 提；蒙版空就换 `maskColor: "cyan"`。
- **背景偏色**：`ht.channelShadows` 已按背景框配平；背景框若落在星云上，结果会怪——看 `find_background` 的框。
- **星点发紫/品红**（窄带常见）：没有 RGB 时 `nb_star_colors` 会去绿；仍偏品红就在 stars_color 加 `scnr` 的 `color: "magenta"`。
- 主帧没有星图信息（没有 FITS 头）时板解析会失败：定位、按目标框白参考都退回整图，结果仍可用。
- 参考作品用窄带 peer 组；HOO 不要拿 SHO 作品比，反之亦然。
