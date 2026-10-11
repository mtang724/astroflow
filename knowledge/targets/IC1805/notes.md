# IC 1805 / Sh2-190 — Heart Nebula（心形星云）参考笔记

数据：`refs.json`（AstroBin 按 likes 排序，2026-10-10 抓取，候选 115 张，`--fov 1.44`），12 张缩略图已逐张查看。
我们：ASI2600MC Air（IMX571 OSC，无滤镜）+ 72 mm ED @ 563 mm（≈f/7.8），1.38″/px，视场 2.40°×1.60°（144′×96′），常见一晚 1–2 h。

**注意：有 3 张不是本目标**（别名 "Heart Nebula" 搜到了别的 “heart”）：best_00（Heart of Hydra）、best_02（船底座 η Carinae 星云的 “heart”）、peer_05（蛇夫座 ρ Oph 的 IC 4604）。下文结论和“本目标”指纹已排除它们，用 refs 比较指纹时也应排除。best 组剩下的 4 张（best_01/03/04/05）全部是 SHO/HSO 窄带。

## 目标类型
- 大型发射星云（HII），仙后座银河，Dec +61.5°；中心是疏散星团 Melotte 15。AdP 只给核心 60′；心形主体约 1.5–1.7°（按 peer_02 中心形与魂状星云相距 2.5° 的比例估算）。
- 西北偏西约 1.0° 是 Fish Head（IC 1795 / NGC 896），东南偏东约 2.5° 是魂状星云 IC 1848。
- OSC 宽带应有的样子：心形外壁是最亮的红/鲑鱼红-玫瑰红 Hα 边，心形内部是低亮度的灰粉/中性灰，中央 Melotte 15 附近有带亮边的尘埃柱；星场极密。宽带记录 Hα 的效率低，这是“信号弱”的目标。

## 颜色基准
- 外壁/亮边：红 → 鲑鱼红 → 玫瑰红。纯 RGB 深积分（peer_03，64 h）偏玫瑰/洋红；带三通道光害滤镜（peer_00/01，Antlia Triband，AstroBin 标为 LP）偏橙红/鲑鱼红；无滤镜 3 h（peer_02）是深红。
- 心形内部：灰粉/中性灰（peer_00/01 中央大片近中性灰），不是蓝色。
- 中央尘埃柱：柱体棕黑，被照亮的边缘暖白/淡橙（peer_00）。Fish Head：亮粉红结 + 暗带（peer_02/03）。
- peer_03 里心形旁有一小块蓝色反射云——短积分宽带基本记录不到，不要“补”出来。
- 背景：中性略暖（peer R/G≈1.07，B/G≈1.05），暗灰褐 + 密集星场。
- 不要模仿（窄带假色）：best_01（Nicola Beltraminelli，HS-HSO）、best_03（Christoph Lichtblau，金边蓝心）、best_04（Alan Pham，SHO）、best_05（Bogdan Jarzyna，Hubble palette）的金黄/橙色外壁 + 青蓝内部，完全来自 SII/OIII 映射。

## 关键结构
- 心形外壁一圈亮边；东侧（多数图的左侧）外壁有柱状/指状尘埃突起，内侧被照亮（best_01/04/05、peer_00）。
- 中央 Melotte 15 一带的尘埃柱与亮边：心形内部唯一的高对比结构。
- 心形内部的暗尘埃团与暗带（peer_01）；Fish Head 的亮结及横穿它的暗带（best_03 右上）。
- 亮度层次：动态范围小，难点是暗弱而不是过曝；星点亮度远超星云（peer_04）。

## 背景与对比
- peer（本目标 5 张）：bg 0.151，lum_median 0.177，contrast 0.353——背景偏亮、对比低（星云铺满 + 星场密）。
- 星点：银河星场非常密；peer_04（2.5 h）星点几乎压过星云；高分作品都缩过星或星点很小。
- 暗带近黑但保留棕色调，不要压成死黑。

## 构图（563 mm，144′×96′）
- 心形 ≈1.5–1.7°：在 2.4°×1.6° 视场里短边基本被填满（peer_01 视场半径 1.18°，心形铺满全幅）。心形 + Fish Head（中心距约 1.0°）沿长边约 2.0°，长边大致东西向（稍旋转）即可同框。Heart & Soul 同框（peer_02/03，视场半径 3.1–3.3°）我们做不到。
- 背景提取：星云铺满画面 → 不要用 GradientCorrection/ABE（会把心形内部的弥漫 Hα 当背景扣掉，心形变空、发灰）。用 DBE：低阶（1，至多 2），样本只放在心形外（画面左右两端和四角的暗星场），心形内部不放。
- `dbe_auto`：AdP 60′ 圆 × objectScale 1.6 → 排除直径 96′ = 整个短边，只剩左右两端和四角的样本 → 宜 degree 1（至多 2）。

## 常见坑
1. 宽带 Hα 弱：Bayer 只有 1/4 像素是红色；f/7.8 下原生像素信号率约为 peer_02（SpaceCat 51，f/4.9，同为 IMX571）的 1/2.5。peer_04（2.5 h）只有星点 + 淡红。一晚 1–2 h 只能得到类似 peer_04 的效果，像样的心形大约要 6–10 h；或在输出时缩小尺寸提高每像素 SNR。
2. 过度拉伸 → 红色斑驳色噪 + 灰雾背景。
3. GC/ABE 把星云当梯度（见“构图”）。
4. 星点压过星云：必须缩星。
5. 照 SHO 参考把心形内部做成青蓝。
6. 有利条件：Dec +61.5°，北纬 40° 中天高度约 68°，几乎整年可拍；梯度主要来自光害/月光，而不是低空。

## 参数建议（相对默认 nebula recipe）
- stretch：targetMedian 0.17–0.18（peer lum_median 0.177）。
- 背景：用 DBE 代替 GC（见上），检查模型里没有心形。
- linear NXT：0.35–0.40（信号弱）。
- LHE：radius 162–250（外壁和暗带是大尺度结构），amount 0.5–0.6（防止放大噪点）。
- saturation：0.50–0.60；目标 signal_saturation≈0.33、p90≈0.5（peer）。recipe 里饱和度在 NXT2 之前，色噪多时宁可少提，依靠 nxt2 的 denoise_color。
- HT：clipFraction 0.0004 合适；目标 bg≈0.13–0.15。
- NXT2：0.70–0.75 / 0.90。USM：0.4–0.5（噪点多时再降）。
- 星点：starsAmount 0.6–0.75；star_sat 不超过 0.56（72ED 色差）。
- 示例：`--set stretch.stretch.targetMedian=0.17 --set linear.nxt.params.denoise=0.38 --set starless.lhe.params.amount=0.55 --set starless.nxt2.params.denoise=0.72 --set combine.recombine.starsAmount=0.7`

## 参考作品清单
| 组 | 标题 | 作者 | likes | 奖项 | 积分 | URL | 可借鉴 |
|---|---|---|---|---|---|---|---|
| best_00 | NEW TYPE OF NEBULA DISCOVERED: The Heart of Hydra | Marcel Drechsler | 720 | IOTD | 360.2 h | https://www.astrobin.com/950d0s/ | [非本目标] 排除 |
| best_01 | Melotte 15 in HS-HSO with RGB stars | Nicola Beltraminelli | 645 | IOTD | 39.8 h | https://www.astrobin.com/nmjd33/ | 中心区特写；可学尘埃柱/外壁的立体层次，配色不学 |
| best_02 | The heart of the Eta Carina Nebula | Christoph Lichtblau | 404 | TP | 5.8 h | https://www.astrobin.com/vwwzyg/ | [非本目标] 排除 |
| best_03 | The heart nebula IC 1805 + 3D stereo picture | Christoph Lichtblau | 403 | TP | 11.2 h | https://www.astrobin.com/bftcvd/ | 完整心形 + Fish Head 构图（视场半径 1.16°）；SHO 不学 |
| best_04 | Melotte 15 - A Peek Inside The Heart | Alan Pham | 400 | IOTD | 27.8 h | https://www.astrobin.com/328006/ | 中心特写，SHO |
| best_05 | Melotte 15 - The Center of the Heart Nebula (Hubble Palette) | Bogdan Jarzyna | 391 | IOTD | 未标注 | https://www.astrobin.com/ahf224/ | 中心特写，SHO |
| peer_00 | Melotte 15 - SVX130T f/5 - 2600MC - Antlia Triband RGB Ultra | Itto Ogami | 671 | - | 7.8 h | https://www.astrobin.com/wnwo5m/ | IMX571 OSC + 三通道滤镜：中心区色调（鲑鱼红外壁 + 灰色内部 + 暖白亮边） |
| peer_01 | Heart Nebula Close Up (IC 1805) - SVX130T f/5 - 2600MC - Antlia Triband | Itto Ogami | 480 | - | 7.8 h | https://www.astrobin.com/lhmzu2/ | 构图最接近我们（心形铺满）；颜色基准 |
| peer_02 | Heart & Soul Nebulas - SpaceCat51 & 2600MC - 3 Hours | Itto Ogami | 404 | - | 3.0 h | https://www.astrobin.com/0eu9if/ | 无滤镜 3 h @ f/4.9 已能看出心形；深红 |
| peer_03 | The Heart and the Soul (LRGB) | Justin Tolboe | 316 | IOTD | 64.1 h | https://www.astrobin.com/2rge8j/ | IMX571 彩色 + LRGB 64 h：宽带上限（玫瑰/洋红，内部淡粉） |
| peer_04 | Sh2-190 | Armin Unterwandling | 270 | - | 2.5 h | https://www.astrobin.com/gemb1l/ | IMX533 OSC 2.5 h：星点淹没星云——短积分的现实 |
| peer_05 | IC4604 Into the Heart of the Rho Ophiuchi Nebula | Emanuel Polichronis | 245 | - | 2.0 h | https://www.astrobin.com/hszac3/ | [非本目标] 排除 |

## 数值指纹（refs.json 中位数）
| 组 | n | background_level | lum_median | contrast_p99_p10 | signal_sat 均值 (p90) | bg_sat | 背景 R/G, B/G | 主导色相（均值） |
|---|---|---|---|---|---|---|---|---|
| peer 本目标 | 5 | 0.151 | 0.177 | 0.353 | 0.33 (0.51) | 0.15 | 1.07, 1.05 | red 0.62, rose 0.34 |
| peer 全部 | 6 | 0.161 | 0.210 | 0.370 | 0.35 (0.51) | 0.17 | 1.07, 1.04 | red 0.51, rose 0.28, cyan 0.16（cyan 全部来自 peer_05） |
| best 本目标（全窄带） | 4 | 0.133 | 0.246 | 0.496 | 0.43 (0.74) | 0.35 | 1.28, 1.21 | orange 0.39, red 0.31, cyan 0.25 |
| best 全部 | 6 | 0.123 | 0.231 | 0.474 | 0.43 (0.72) | 0.41 | 1.31, 1.12 | red 0.28, orange 0.26, rose 0.26, cyan 0.16 |

- 色相是各图 `signal_hue_mix` 的平均（缺失按 0）。best 的 orange/cyan 是 SHO 色相，只能借鉴亮度/对比，不能作颜色目标。
- 建议目标：bg≈0.13–0.15，lum_median≈0.17，contrast≈0.38–0.42（略高于 peer，靠缩星和暗带），signal_saturation≈0.33，色相 red/rose，背景 R/G≈1.05。noise_hf 不可比。

## 补充（2026-10-10）：本次数据用 Antlia 四通道多波段滤镜
- 2026Oct09 这晚的数据是 **彩机 + Antlia Quad Band**（R ≈ Hα+[NII]+[SII]，G/B ≈ [OIII]），不是宽带 RGB。处理配方为 `osc_multiband_nebula`，色彩校准默认 BNCC（见 `knowledge/filters.md`）。
- 参考作品已按坐标过滤重新抓取（之前按俗名搜到的其他“Heart/Skull”天体已剔除），peer 组改为“彩色传感器 + 窄带/多波段滤镜”作品（refs.json 的 `peer_mode: multiband`）。上文提到的 best_NN / peer_NN 文件编号对应的是旧清单，以当前 refs.json 为准。
- 颜色期望因此更接近 HOO 自然色：Hα 红/粉、[OIII] 青蓝；星点颜色不可信，需要去品红/去绿并克制饱和度。上文的“宽带颜色基准”仍可用于判断哪些区域应以 Hα 还是 OIII 为主。
