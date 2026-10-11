# NGC 7293 — Helix Nebula（螺旋星云，Caldwell 63）参考笔记

数据：`refs.json`（AstroBin 按 likes 排序，2026-10-10 抓取，候选 51 张，`--fov 1.44`），12 张缩略图已逐张查看，全部是本目标。
我们：ASI2600MC Air（IMX571 OSC，无滤镜）+ 72 mm ED @ 563 mm（≈f/7.8），1.38″/px，视场 2.40°×1.60°（144′×96′），常见一晚 1–2 h。

## 目标类型
- 行星状星云（PN），宝瓶座，Dec −20.8°，离我们最近的亮 PN 之一；AdP 直径 12.8′（主环），外围暗红的外晕/弧环（loops）到约 25′–28′（按 best_05 的比例估算）。面积大、表面亮度低，外晕尤其暗。
- OSC 宽带应有的样子：中心盘青/蓝青（OIII），内环过渡为白-淡粉，主环玫瑰红/深粉红（Hα+[NII]），外晕暗红；中心白矮星可见；背景中性近黑。

## 颜色基准
- 中心盘：青-蓝青。宽带 best_05（IMX571 OSC 无滤镜）、peer_01（2.3 h）、peer_05 都偏青绿/青蓝；窄带 HOO 图更偏纯蓝。
- 主环：rose/粉红-猩红（peer 色相 red 0.44，rose 0.35）。过渡区：白/淡粉。外晕：暗红、很淡。
- 背景：中性（refs 背景 R/G、B/G 基本都是 1.00），饱和度很低（bg_sat≈0.06）。
- 不要模仿：best_00/01/02/04 和 peer_02 里黄-橙色的过渡环来自 SHO/HOO 混合映射，宽带不会出现；peer_00（加了 Ha）偏橙红，peer_04（LP 滤镜）中心偏紫蓝、环偏橙，也不是纯宽带色。best_03（HaOIII+RGB）是颜色最接近宽带的窄带作品。

## 关键结构
- “眼睛”：内环 + 外环两个相互倾斜的环叠成双环；主环内侧的放射状纹理就是彗星结（cometary knots）。顶级作品在高分辨率下可见；我们 1.38″/px + 72 mm 口径最多出放射状纹理，不要靠锐化“造”结。
- 外围弧环/外晕（best_00/02/03/04）需要几十小时（多为窄带）；宽带的 peer_05（16.6 h）和 best_05（12.7 h @ f/4）能看到外晕的一部分。
- 亮度层次：主环远亮于外晕，中心盘中等；best 组 contrast 0.63——高对比、深黑背景。

## 背景与对比
- best：bg 0.065，lum_median 0.073（很暗）；peer：bg 0.098，lum 0.102。contrast：peer 0.48，best 0.63。
- 星点：小、适量、略带颜色；星场稀疏，不需要大幅缩星，但适度缩星会让外晕更干净。

## 构图（563 mm，144′×96′）
- 主环 12.8′ ≈ 560 px，含外晕约 27′ ≈ 1170 px：约占短边（4176 px）的 1/4–1/3。最接近我们的是 peer_03（Nick Large，ZS61，视场半径 1.18°）：星云居中，四周大片空星场。
- best/peer 大多在视场半径 0.5–0.95°：后期裁成约一半视场（≈70′×47′）更接近主流构图。
- 背景提取：背景处处可见，GradientCorrection 可用；但外晕是大尺度低亮信号，要检查 GC 模型中心没有“鼓包”。用 `dbe_auto` 时 AdP 12.8′ × objectScale 1.6 只排除约 20′ 直径 → 外晕会被当背景；应设 objectScale ≥2.5（≥32′）。

## 常见坑
1. 低空：Dec −20.8°，北纬 40° 中天约 29°；秋季窗口短，梯度大，消光使整体偏红。
2. 外晕需要长积分：同为 IMX571 时，我们 f/7.8 的原生像素信号率约为 best_05（f/4）的 1/3.8。一晚 1–2 h 宽带大致是 peer_01（2.3 h）的水平：中心盘 + 主环清楚，外晕基本没有——不要为外晕过度拉伸。
3. 中心青色偏绿或发灰：SPCC 后 OIII 偏青绿是正常的；不要对 starless 做 SCNR（会变紫蓝或发灰），默认 recipe 的 SCNR 只在星点层，保持。
4. LHE 半径过大把主环和外晕压平，或在主环外出现暗圈。
5. NXT 太强抹掉主环内的放射状纹理。
6. 照 SHO 参考做出黄色过渡环。
7. SXT 可能把中心白矮星移走，starless 中心出现小洞——重组后即恢复，检查即可。

## 参数建议（相对默认 nebula recipe）
- stretch：targetMedian 0.10（peer lum_median 0.10；best 0.07）。
- 背景：GC + 检查模型，或 DBE（objectScale ≥2.5）。
- HDR：轻度（`hdr` layers 5–6，amount 0.2–0.3），让主环保有层次，同时能把外晕拉出来。
- LHE：radius ≈64–100 px（≈1.5′–2.3′；osc_galaxy 的 "auto" 对它是 97 px），amount 0.4–0.5。
- saturation：0.60–0.70（peer signal_saturation 0.30，best 0.50；宽带的 best_05 为 0.30）：红色主环和青色中心都要清楚。
- HT：clipFraction 0.0004；目标 bg≈0.07–0.10。
- NXT2：0.65/0.90 可用；若主环纹理被抹掉，降到 0.55。USM：sigma 1.5，amount 0.5。
- 星点：starsAmount 0.85–1.0；star_sat 不超过 0.56（72ED 色差）。
- 示例：`--set stretch.stretch.targetMedian=0.10 --set starless.lhe.params.radius=80 --set starless.lhe.params.amount=0.45 --set starless.sat.boost=0.65 --set starless.usm.params.sigma=1.5`

## 参考作品清单
| 组 | 标题 | 作者 | likes | 奖项 | 积分 | URL | 可借鉴 |
|---|---|---|---|---|---|---|---|
| best_00 | NGC 7293 (Helix Nebula / Caldwell 63) | Alpha Zhang | 756 | TP | 33.0 h | https://www.astrobin.com/r8bwte/ | 窄带（Ha/OIII/SII），黄环不学；外晕弧环与主环层次可参考 |
| best_01 | NGC7293 the Eye of Sauron in H-SHO-RGB from Spain | Nicola Beltraminelli | 732 | IOTD | 44.9 h | https://www.astrobin.com/1c0tnf/ | 背景极暗（0.033），SHO 配色 |
| best_02 | Sauron is watching you : Helix Nebula | Louis Leroux | 607 | IOTD | 63.2 h | https://www.astrobin.com/hsvnn2/ | FSQ-85 + IMX571 mono（视场半径 0.94°）：外晕弧环构图 |
| best_03 | The Helix Halo | Mathew Ludgate | 497 | IOTD | 84.5 h | https://www.astrobin.com/h8hnt0/ | HaOIII+RGB：最接近宽带的颜色（青心、粉白内环、粉红外环） |
| best_04 | The Eye of God: A Deep View into the Helix Nebula | Jonathan Hill | 490 | TP | 670.8 h | https://www.astrobin.com/ixz4v8/ | 多人合成 670 h，外晕最完整 |
| best_05 | NGC 7293 | Daniel Nimmervoll | 455 | IOTD | 12.7 h | https://www.astrobin.com/g43o1l/ | IMX571 OSC 无滤镜，10" f/4：宽带颜色与对比的首选目标 |
| peer_00 | Helix Nebula - NGC 7293 - with a little Ha touch | Daniel Nobre | 289 | TP | 未标注 | https://www.astrobin.com/4to1pq/ | OSC + 少量 Ha：主环偏橙红，外环可见 |
| peer_01 | Window Of Opportunity (Helix Nebula (NGC 7293)) | estabrook | 268 | - | 2.3 h | https://www.astrobin.com/v5avlc/ | IMX183 OSC，500 mm，2.3 h：我们一晚数据的现实目标（青心 + 白内环 + 红环） |
| peer_02 | NGC 7293 - Helix Nebula - Overall Photons Project_1 | patrice_so | 267 | TP | 342.2 h | https://www.astrobin.com/vmampx/ | 多设备 342 h（含 mono），不是真正的 peer |
| peer_03 | NGC7293 (Helix Nebula) | Nick Large | 251 | - | 8.3 h | https://www.astrobin.com/7kr2uu/ | 视场半径 1.18° ≈ 我们：星云小、背景偏亮（0.113） |
| peer_04 | NGC7293 | Douglas Fontana | 236 | - | 未标注 | https://www.astrobin.com/auzwo0/ | IMX294 OSC + LP 滤镜：中心偏紫蓝、环偏橙——LP 色偏 |
| peer_05 | NGC7293 - Helix Nebula | Riccardo Balia | 218 | TP | 16.6 h | https://www.astrobin.com/zctu53/ | IMX294 OSC 16.6 h：宽带最佳示范之一（青心 + 猩红环 + 外晕） |

## 数值指纹（refs.json 中位数）
| 组 | n | background_level | lum_median | contrast_p99_p10 | signal_sat 均值 (p90) | bg_sat | 背景 R/G, B/G | 主导色相（均值） |
|---|---|---|---|---|---|---|---|---|
| peer | 6 | 0.098 | 0.102 | 0.483 | 0.30 (0.58) | 0.06 | 1.00, 1.02 | red 0.44, rose 0.35, cyan 0.10, azure 0.06 |
| best | 6 | 0.065 | 0.073 | 0.634 | 0.50 (0.71) | 0.06 | 0.98, 1.00 | rose 0.51, red 0.28, cyan 0.08, azure 0.07 |

- 色相是各图 `signal_hue_mix` 的平均（缺失按 0）。cyan/azure 是中心盘，red/rose 是主环。
- 建议目标：bg≈0.07–0.09，lum_median≈0.08–0.10，contrast≈0.50–0.55，signal_saturation≈0.30–0.40，色相 rose/red 为主并带约 0.1 的 cyan，背景 R/G≈B/G≈1.0。noise_hf 不可比。

## 补充（2026-10-10）：本次数据用 Antlia 四通道多波段滤镜
- 2026Oct09 这晚的数据是 **彩机 + Antlia Quad Band**（R ≈ Hα+[NII]+[SII]，G/B ≈ [OIII]），不是宽带 RGB。处理配方为 `osc_multiband_nebula`，色彩校准默认 BNCC（见 `knowledge/filters.md`）。
- 参考作品已按坐标过滤重新抓取（之前按俗名搜到的其他“Heart/Skull”天体已剔除），peer 组改为“彩色传感器 + 窄带/多波段滤镜”作品（refs.json 的 `peer_mode: multiband`）。上文提到的 best_NN / peer_NN 文件编号对应的是旧清单，以当前 refs.json 为准。
- 颜色期望因此更接近 HOO 自然色：Hα 红/粉、[OIII] 青蓝；星点颜色不可信，需要去品红/去绿并克制饱和度。上文的“宽带颜色基准”仍可用于判断哪些区域应以 Hα 还是 OIII 为主。
