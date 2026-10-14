# 滤镜与对处理的影响

彩色相机的滤镜写在 `In Processing/<night>/session.json` 的 `filter` / `filter_class` 字段（FITS 头里没有记录，应用里在目标概览的“这一晚的滤镜”选）。黑白相机不用记：每张帧的 FILTER 关键字就是滤镜，WBPP 按滤镜分别叠加，主帧文件名里带滤镜（`..._FILTER-Ha_mono.xisf`）。agent 的 `inspect_target` 会读出这些，据此选配方和参考作品分组。

## 彩色相机

### 无滤镜（宽带 RGB）—— `osc_broadband`
- 配方：星云 `osc_broadband_nebula`（第1期），星系 `osc_galaxy`（第2期）。
- SPCC 宽带：Sony Color Sensor R/G/B-UVIRcut + Ideal QE + Average Spiral Galaxy。

### Hα + OIII 双窄带 / 多波段（L-eXtreme、ALP-T、Antlia 四通道等）—— `osc_multiband`
- 数据本身就是 HOO：R ≈ Hα（四通道还有 [NII]、[SII]），G/B ≈ OIII（±Hβ）。
- 配方 `osc_multiband_nebula`（第4期下，面纱 + L-eXtreme）：DBE 去背景（GC 会把大片星云当梯度）；**SPCC 窄带模式**：R 656.3、G/B 500.7 nm，带宽按滤镜（默认 7 nm，步骤参数 `bandwidth`），失败时 BNCC；拉伸更猛（EZ 0.24，激进度 16.3）；蓝色蒙版把 OIII 从青绿调蓝；L 蒙版提饱和；去绿；分通道配平背景、压暗。星点不另外处理。
  - 视频里用的是 SPCC 宽带模式 + 滤镜库里“Sony CMOS + L-eXtreme”的组合曲线；滤镜库里有组合曲线的只有少数型号（Antlia ALP-T、Triband，Baader UHC-S，Optolong L-eNhance / L-eXtreme / L-Ultimate），所以配方统一用窄带模式。
- Antlia 四通道（2026Oct09 用过）：通带 Hα 656.3 + [NII] + [SII] 671.6/673.1，OIII 495.9/500.7，FWHM 未查到。
- 参考作品：peer 组用“彩色传感器 + 窄带/多波段滤镜”的作品。

### SII + OIII 双窄带 —— `osc_so`
- 单独用很少见：配合 Hα + OIII 那一套，两套各拍若干晚，做 SHO 哈勃色（第5期下）。
- 合并几晚时，两套滤镜的帧按 `BAND_HO` / `BAND_SO` 分开，WBPP 各叠出一张主帧（`..._BAND-HO.xisf`、`..._BAND-SO.xisf`）。
- 配方 `osc_sho_nebula`：两张对齐裁切后，SII = SO 的 R，Hα = HO 的 R，OIII = 两张 G、B 共四个通道的平均，按 R = SII、G = Hα、B = OIII 合成，之后和黑白 SHO 相同。

## 黑白相机
- L/R/G/B 宽带：`mono_lrgb_galaxy` / `mono_lrgb_nebula`（第3期）。
- Hα + OIII（可加 R/G/B 拍星点）：`mono_hoo_nebula`（第4期上）。HOO = R Hα、G OIII、B OIII；SPCC 窄带模式；拍了 R/G/B 就用它们的星点替换窄带星点（窄带星点只有红、蓝、白）。
- SII + Hα + OIII：`mono_sho_nebula`（第5期上）。SHO = R SII、G Hα、B OIII；**不做 SPCC**（伪彩色，SPCC 会让整图发绿、星点变白），用 BNCC 平衡；靠黄色、蓝色蒙版调出金 + 蓝；没拍 R/G/B 时，星点颜色由三条谱线混合还原（R = Hα 与 SII，G = Hα 与 OIII，B = OIII）再去绿。
- 滤镜名的识别（`astroflow/mono.py`）：L/Lum/Luminance/Clear、R/Red、G/Green、B/Blue、H/Ha/H-alpha、O/OIII/O3、S/SII/S2，前面带品牌、后面带带宽（`Antlia SII 3nm`）都可以。

## 窄带的期望颜色
- HOO：Hα 红到粉，OIII 青到蓝；背景中性偏暗。
- SHO（哈勃色）：几乎没有绿色，主体金黄到橙红，OIII 强的地方蓝；核心常偏蓝白。
- 发射星云（IC 1805）以 Hα 为主；行星状星云内区 OIII、外环 Hα；NGC 246 主要是 OIII。

来源：Antlia Quadband 零售页 https://agenaastro.com/antlia-quadband-anti-light-pollution-filter-2-mounted-quadlp-2.html ；Antlia ALP-T 双窄带规格 https://deep-space-astronomy.ch/en/product/filtre-antlia-alp-t-dualband-5nm-ha-et-oiii-2-monte/ ；视频第4、5期（`videos/ep4a-mono-hoo.md` 等）。
