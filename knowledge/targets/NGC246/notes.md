# NGC 246 — Skull Nebula（骷髅星云）参考笔记

数据：`refs.json`（AstroBin 按 likes 排序，2026-10-10 抓取，候选 70 张，`--fov 1.44`），10 张缩略图已逐张查看（peer 只有 4 张）。
我们：ASI2600MC Air（IMX571 OSC，无滤镜）+ 72 mm ED @ 563 mm（≈f/7.8），1.38″/px，视场 2.40°×1.60°（144′×96′），常见一晚 1–2 h。

**注意：10 张里有 6 张不是 NGC 246**（别名 "Skull Nebula" 搜到了其他“骷髅”）：NGC 2467 Skull and Crossbones（best_00/01）、LBN 406 Laughing Skull（best_02、peer_00）、Sh2-68 Flaming Skull（best_03/04）。真正的 NGC 246 只有 best_05、peer_01、peer_02、peer_03 四张；下文结论只基于这四张和可靠常识，比较指纹时应排除其余 6 张。

## 目标类型
- 行星状星云（PN），鲸鱼座，Dec −11.9°，AdP 直径 3.8′——很小；中心星在缩略图里清晰可见。
- OSC 宽带应有的样子：青/蓝青（teal/cyan）的椭圆环（OIII 500.7 nm 落在 Bayer G/B 交界，宽带显示为青色），环上有几个粉红/红色小结（Hα/[NII]），环内有较暗的空洞（“眼眶/嘴”），周围是稀疏星场和小星系。

## 颜色基准
- 环：青-蓝青（best_05 蓝青；peer_02 青色环；peer_03 亮青，但 peer_03 用了 UHC 滤镜，比纯宽带更艳）。
- 粉红小结：best_05 环上有粉红/红色斑点，peer_03 环的一侧有一个小红点——真实存在，但很小，不要放大成大片红。
- peer_01 的环偏淡紫（lavender），很可能是白平衡/背景偏红造成，不作为目标颜色。
- 背景：中性近黑（best_05 背景 R/G、B/G = 1.00）。星点：黄/橙/白，best_05 的亮星有柔和光晕；高银纬星场稀疏。
- 本目标没有窄带参考（窄带的 “Skull” 都是别的天体），颜色只需对照 best_05、peer_02、peer_03；不要拿 NGC 2467 / Sh2-68 的 SHO/HOO 配色当目标。

## 关键结构
- 椭圆亮环，亮度不对称（一侧边缘更亮，peer_03 最明显）。
- 环内的暗区和中心星（骷髅的“眼睛”和“嘴”）：需要足够的分辨率和对比才有“骷髅”感；peer_02/03 的缩略图里已能看到内部明暗斑块。
- 同框小星系：NGC 255（12.5 等，约 1′，在东北约 26′）和 PGC 2689（peer_01 标题），peer_01/03 中可见为小旋涡。

## 背景与对比
- 背景暗而中性：best_05 bg 0.071，peer（本目标）中位 0.067——但 peer_02 的背景被压到 0.015（死黑），不要学。
- 星点多而小，不需要缩星；best_05 星点颜色饱和、亮星略带光晕。
- 目标极小，整幅 fingerprint 基本由星点和背景决定（见“数值指纹”）。

## 构图（563 mm，144′×96′）
- 3.8′ ≈ 165 px，只占 6248 px 长边的约 2.6%：全视场里只是一个小环（best_05 视场半径 1.26°，与我们接近）。
- 两种出图：(a) 全视场 + 小星系（best_05 风格）；(b) 裁成约 600–1200 px 宽（约 14′–28′），让骷髅占画面 15–30%（peer_01/02/03 风格，视场半径 0.53–0.62°）。
- 背景提取：背景处处可见，GradientCorrection 合适，不需要 DBE。

## 常见坑
1. LHE 默认半径 162 px ≈ 整个星云直径（165 px），会把环压平；osc_galaxy 的 "auto" 半径也会被下限 96 px 卡住（0.35×83 px≈29 → 96）。
2. 拉伸过头：为了看清环把背景拉到 0.20 → 灰雾 + 噪点；refs bg≈0.07。
3. 背景压太死（peer_02 bg 0.015）：星点周围出现黑圈，环的暗弱外缘消失。
4. 颜色偏紫/偏蓝：OIII 的青色在白平衡偏红或过度 SCNR 时会变紫（peer_01）。SCNR 只用在星点层（默认 recipe 已如此），不要对 starless 做 SCNR。
5. 去星：SXT 可能把中心星和环上的小结当星点移走，starless 中心出现空洞或环不连续——属正常，但要确认重组后恢复。
6. 低空：Dec −11.9°，北纬 40° 中天约 38°；OIII 青色受大气消光影响，低空时更弱。
7. 一晚 1–2 h @ f/7.8：环的青色和内部空洞能出来（peer_03 3.5 h、peer_01 5.8 h），粉红小结会很弱，不要靠饱和度硬推。
8. 指纹：整幅色相由星点主导（橙/黄），比较时应裁出星云区域，或只看 background_level / background_cast。

## 参数建议（相对默认 nebula recipe）
- stretch：targetMedian 0.08–0.10（refs lum_median 0.07–0.09）。
- BXT：对小目标有帮助（默认 recipe 已有 linear.bxt）。
- LHE：radius 24–32 px，amount ≤0.3——或直接关闭（`--set starless.lhe.enabled=false`）。
- HDR：不需要（动态范围小）。
- saturation：0.6–0.8，只为让环的青色清楚；lum mask 下背景基本不受影响，目标 bg_sat ≤0.10。
- HT：clipFraction 0.0004 合适，目标 bg≈0.07–0.09。
- NXT2：0.65/0.90 合适（画面大部分是空背景）。USM：sigma 1.0–1.5，amount 0.4–0.5（默认 sigma 2 对 165 px 的目标偏粗）。
- 星点：starsAmount 0.9–1.0；star_sat 不超过 0.56（72ED 色差）。
- 示例：`--set stretch.stretch.targetMedian=0.09 --set starless.lhe.params.radius=32 --set starless.lhe.params.amount=0.3 --set starless.usm.params.sigma=1.2`

## 参考作品清单
| 组 | 标题 | 作者 | likes | 奖项 | 积分 | URL | 可借鉴 |
|---|---|---|---|---|---|---|---|
| best_00 | NGC2467 Skull and Crossbones Nebula | zaki ffcamera | 423 | IOTD | 15.1 h | https://www.astrobin.com/sbaz4d/ | [非本目标：NGC 2467] 排除 |
| best_01 | The Skull and Crossbones Nebula (NGC 2467) | Bruno Rota Sargi | 413 | IOTD | 7.2 h | https://www.astrobin.com/h8u4d4/ | [非本目标：NGC 2467] 排除 |
| best_02 | The Laughing Skull Nebula LBN406 | Brian Diaz | 391 | TP | 17.8 h | https://www.astrobin.com/s17ska/ | [非本目标：LBN 406] 排除 |
| best_03 | Serpens Cloud, vdB123 and Flaming Skull nebula Sh2-68 | Leo Shatz | 348 | IOTD | 10.7 h | https://www.astrobin.com/45aet6/ | [非本目标：Sh2-68] 排除 |
| best_04 | Flaming Skull Nebula SH2-68 with cometary like tail | Franklin Marek | 260 | TP | 49.8 h | https://www.astrobin.com/wtnjs0/ | [非本目标：Sh2-68] 排除 |
| best_05 | ngc246 | Philippe BERNHARD | 226 | IOTD | 未标注 | https://www.astrobin.com/iqq52n/ | 唯一的本目标 best：视场与我们接近；青蓝环 + 粉红结，黑中性背景，彩色星点 |
| peer_00 | LBN 406 - Laughing Skull Nebula | Itto Ogami | 445 | - | 18.0 h | https://www.astrobin.com/1tm0gy/ | [非本目标：LBN 406] 排除 |
| peer_01 | NGC 246 (Skull Nebula), NGC 255 & PGC 2689 | Nick Large | 128 | - | 5.8 h | https://www.astrobin.com/31h2ce/ | IMX193 OSC，61 mm，5.8 h：星系同框构图；环偏紫、背景偏灰（0.133） |
| peer_02 | NGC246 - Skull Nebula | Miloš Maco | 52 | - | 未标注 | https://www.astrobin.com/6ge909/ | 8" Dob + IMX482 OSC：青环 + 粉红内部；背景压死（0.015）不学 |
| peer_03 | Skull Nebula | KiwiAstro | 46 | - | 3.5 h | https://www.astrobin.com/xdeu3o/ | IMX294 OSC + UHC 3.5 h：青色最鲜明（UHC 增强），环亮度不对称清楚 |

## 数值指纹（refs.json 中位数）
| 组 | n | background_level | lum_median | contrast_p99_p10 | signal_sat 均值 (p90) | bg_sat | 背景 R/G, B/G | 主导色相（均值） |
|---|---|---|---|---|---|---|---|---|
| best 本目标（best_05） | 1 | 0.071 | 0.094 | 0.419 | 0.13 (0.29) | 0.06 | 1.00, 1.00 | orange 0.54, red 0.18, azure 0.15 |
| peer 本目标 | 3 | 0.067 | 0.068 | 0.145 | 0.16 (0.30) | 0.15 | 1.03, 0.88 | cyan 0.36, azure 0.14, yellow 0.13, red 0.13, orange 0.11 |
| best 全部 | 6 | 0.121 | 0.146 | 0.396 | 0.27 (0.49) | 0.13 | 1.00, 0.98 | red 0.50, orange 0.27, azure 0.08（由 NGC 2467/Sh2-68 主导，不可用） |
| peer 全部 | 4 | 0.096 | 0.101 | 0.207 | 0.14 (0.23) | 0.13 | 1.01, 0.94 | cyan 0.28, orange 0.20, red 0.20, azure 0.10 |

- 色相是各图 `signal_hue_mix` 的平均（缺失按 0）；目标太小，orange/yellow/red 主要来自恒星，cyan/azure 才是星云（以及蓝白星）。
- 建议目标：bg≈0.07–0.09，lum_median≈0.08–0.10，背景 R/G≈B/G≈1.0、bg_sat ≤0.10；颜色要在裁剪后的星云区域判断（环应为 cyan/azure）。noise_hf 不可比（peer_01/02 的缩略图被平滑）。

## 补充（2026-10-10）：本次数据用 Antlia 四通道多波段滤镜
- 2026Oct09 这晚的数据是 **彩机 + Antlia Quad Band**（R ≈ Hα+[NII]+[SII]，G/B ≈ [OIII]），不是宽带 RGB。处理配方为 `osc_multiband_nebula`，色彩校准默认 BNCC（见 `knowledge/filters.md`）。
- 参考作品已按坐标过滤重新抓取（之前按俗名搜到的其他“Heart/Skull”天体已剔除），peer 组改为“彩色传感器 + 窄带/多波段滤镜”作品（refs.json 的 `peer_mode: multiband`）。上文提到的 best_NN / peer_NN 文件编号对应的是旧清单，以当前 refs.json 为准。
- 颜色期望因此更接近 HOO 自然色：Hα 红/粉、[OIII] 青蓝；星点颜色不可信，需要去品红/去绿并克制饱和度。上文的“宽带颜色基准”仍可用于判断哪些区域应以 Hα 还是 OIII 为主。
