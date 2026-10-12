---
name: nebula-broadband
description: 彩色相机（OSC）无滤镜宽带拍的星云——发射、反射、行星状星云、超新星遗迹——的配方 osc_broadband_nebula（PixInsight 进阶教程第1期）：每步做什么、默认参数、常见调整。处理这类目标时加载。
---

# 宽带星云（配方 osc_broadband_nebula）

来源：用户提供的教程视频第 1 期（IC 434）。完整流程和每个参数的出处：`read_knowledge('ep1')`；看配方当前默认值：`show_recipe('osc_broadband_nebula')`。

## 阶段与要点
1. **linear**：find_background → GradientCorrection（看 `10_gc_model`）→ 色彩校准（SPCC 优先，失败自动退回 BNCC）→ BXT（默认）→ NXT 0.30 / 色彩 0.40。
2. **stretch**：EZ Soft Stretch，目标中值 0.20。
3. **stars**：SXT（unscreen），星点单独处理。
4. **starless**：LHE（半径 162、对比限制 1.3、强度 0.8）→ 饱和度 0.72×2（亮度蒙版）→ HT 黑点 → NXT 0.65/0.90 → USM。
5. **stars_color**：星点饱和度 0.56 + SCNR 去绿 0.81。
6. **combine**：screen 合并，starsAmount 1.0（星多的银河区域可降到 0.85–0.9）。

## 这类目标的经验
- 满屏星云不需要背景蒙版；GC 足够。小目标（行星状星云）在 2.4°×1.6° 视场里很小：`locate_object` 会定位，成品可 `export_crop`。
- M8 这类银河中心目标：背景本身是暖棕色尘埃，不要把它中和成灰（见 `read_knowledge('targets/M8')`）。
- 72ED 双分离有色差：星点饱和度要克制。
- 发射星云宽带下应是粉红/洋红/红；不要追求窄带那种金/蓝配色。
