---
name: nebula-multiband
description: 彩色相机加 Hα+OIII 双窄带 / 多波段滤镜（L-eXtreme、ALP-T、Antlia 四通道等）拍的星云——配方 osc_multiband_nebula（第4期下）：SPCC 窄带模式、蓝色蒙版把 OIII 调蓝、分通道配平背景。session.json 的 filter_class 为 osc_multiband 时加载。
---

# 彩机双窄带 HOO（配方 osc_multiband_nebula）

来源：教程第4期下（面纱 NGC 6960 + L-eXtreme）。完整流程：`read_knowledge('ep4b')`；滤镜：`read_knowledge('filters')`；默认值：`show_recipe('osc_multiband_nebula')`。

## 要点
- 叠加出来就是 HOO：R ≈ Hα，G/B ≈ OIII，不用拆通道。
- linear：`dbe_auto`（GC 会把大片星云当梯度）→ SPCC 窄带模式（`cc.narrowband` HOO，`cc.bandwidth` = 滤镜带宽，默认 7 nm；失败自动退回 BNCC）→ BXT → NXT 0.30/0.40。
- stretch：EZ 中值 0.24，激进度 16.3（背景更暗）。
- starless：`oiii_blue`（蓝色蒙版，B 提、G 压）→ `sat`（L 蒙版）→ `balance`（分通道配平背景）→ `scnr` 去绿 → `sat2` → NXT 0.65/0.90 → `dark_sky`（反相 L 蒙版压暗背景、降饱和）→ `ht`。
- 星点不处理，screen 合并。

## 判断与调参
- OIII 区还是青绿：`oiii_blue.channels` 的 B 再提一点；蒙版几乎为空时（OIII 色相偏青）改 `maskColor: "cyan"`。
- 背景偏红或偏黄：`balance` 已按背景框配平；仍偏就检查背景框是否落在星云上（`find_background`）。
- 整体太艳：`sat2.boost` 降到 0.58–0.60。
- 参考作品用“彩色传感器 + 窄带/多波段滤镜”的 peer 组；不要用 SHO 作品当颜色标准。
- 新的一晚：FITS 头里没有滤镜信息，问用户用了什么滤镜，写进 `In Processing/<night>/session.json`（filter、filter_class）。另一套 SII+OIII 滤镜的晚上记 `osc_so`，合并后走 `narrowband` 技能里的彩机 SHO。
