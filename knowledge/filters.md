# 滤镜与对处理的影响

每晚用的滤镜写在 `In Processing/<night>/session.json` 的 `filter` 字段（FITS 头里没有记录）。agent 的 `inspect_target` 会读出来，据此选配方和参考作品分组。

## 无滤镜（宽带 RGB）
- 配方：星云 `osc_broadband_nebula`（第1期），星系 `osc_galaxy`（第2期）。
- SPCC 宽带：Sony Color Sensor R/G/B-UVIRcut + Ideal QE + Average Spiral Galaxy。

## Antlia 四通道（Quad Band）抗光害多波段滤镜 —— 2026Oct09 使用
- 通带（零售商资料）：红端 Hα 656.3 nm + [NII] 654.8/658.4 + [SII] 671.6/673.1；青绿端 [OIII] 495.9/500.7（是否含 Hβ 486.1 未确认）。峰值透过约 92%，OD4 截止 300–1050 nm，为 f/2 快镜设计（带宽比 3–5 nm 双窄带宽，具体 FWHM 未查到——**待用户确认型号与带宽**）。
- 对彩机的含义：R 通道 ≈ Hα+[NII]+[SII]，G/B 通道 ≈ [OIII]（+Hβ）。数据本质是“彩机多波段窄带”，不是宽带。
- 色彩校准：**SPCC 宽带模式不适用**。默认用 BNCC（背景框 BN + 星点白参考 CC），结果近似“HOO”自然色：Hα 红/粉，OIII 青/蓝绿。SPCC 窄带模式（narrowbandMode，R=656.3、G=B=500.7，带宽按滤镜 FWHM）可作为对照，但带宽不准会偏色。
- 星点：窄带下星点颜色不真实，常见品红/紫色晕 → 星点图做 SCNR 去绿 + 去品红（`scnr` 的 `color: "magenta"`），饱和度克制。
- 背景：光害梯度小，但月光/天光残余仍需 GC。
- 目标颜色期望：发射星云（IC 1805）以 Hα 红为主、OIII 弱；行星状星云 NGC 7293（Helix）内区 OIII 青蓝、外环 Hα 红；NGC 246（Skull）主要是 OIII 青绿的壳层、少量 Hα 红。
- 参考作品：peer 组改为“彩色传感器 + 窄带/多波段滤镜”的作品（`references.fetch(..., peer="multiband")`），不要拿宽带 RGB 作品当颜色标准；SHO 映射作品也不适合（彩机多波段做不出真 SII 通道）。
- 配方：`osc_multiband_nebula`（暂定，等用户提供彩机窄带教程视频后按视频修订）。

来源：Antlia Quadband 零售页 https://agenaastro.com/antlia-quadband-anti-light-pollution-filter-2-mounted-quadlp-2.html ；Antlia ALP-T 双窄带规格 https://deep-space-astronomy.ch/en/product/filtre-antlia-alp-t-dualband-5nm-ha-et-oiii-2-monte/
