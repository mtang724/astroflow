---
name: nebula-multiband
description: 彩色相机加多波段/四通道/双窄带滤镜（如 Antlia Quad Band）拍的星云——配方 osc_multiband_nebula：BNCC 而不是宽带 SPCC、星点去品红、参考作品换成同类窄带作品。session.json 的 filter_class 为 osc_multiband 时加载。
---

# 多波段滤镜星云（配方 osc_multiband_nebula，暂定）

滤镜对颜色的含义与来源：`read_knowledge('filters')`。默认值：`show_recipe('osc_multiband_nebula')`。

## 要点
- 数据本质是“彩机窄带”：R ≈ Hα+[NII]+[SII]，G/B ≈ [OIII]（±Hβ）。**宽带 SPCC 不适用**，默认 BNCC（结果近似 HOO 自然色：Hα 红/粉，OIII 青/蓝绿）。
- 星点颜色不真实，常有品红/紫晕：星点图 SCNR 去绿 + 去品红（`scnr` 的 `color: "magenta"`），饱和度克制。
- 参考作品用“彩色传感器 + 窄带/多波段滤镜”的 peer 组（get_references 会按 session 自动切换），不要拿宽带 RGB 作品当颜色标准，也不要模仿 SHO（彩机做不出真 SII 通道）。
- 期望颜色：发射星云以 Hα 红为主；行星状星云内区 OIII 青蓝、外环 Hα 红。
- 新的一晚：FITS 头里没有滤镜信息，问用户用了什么滤镜，写进 `In Processing/<night>/session.json`（filter、filter_class）。
- 这个配方是暂定的：用户提供彩机窄带教程视频后按视频修订。
