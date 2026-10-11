# M8 / NGC 6523 — Lagoon Nebula（礁湖星云）参考笔记

数据：`refs.json`（AstroBin 按 likes 排序，2026-10-10 抓取，候选 69 张，`--fov 1.44`），12 张缩略图已逐张查看。
我们：ASI2600MC Air（IMX571 OSC，无滤镜）+ 72 mm ED @ 563 mm（≈f/7.8），1.38″/px，视场 2.40°×1.60°（144′×96′），常见一晚 1–2 h。

## 目标类型
- 发射星云（HII 区）+ 年轻星团 NGC 6530 + 暗星云/Bok 球（B88、B89、B296），位于人马座银河中心方向的密集星场与尘埃中。AdP 目录直径 90′（实际约 90′×40′，东西向长）。
- OSC 宽带应有的样子：粉红/玫瑰红的 Hα(+Hβ) 主体，沙漏（Hourglass）一带的核心发白、偏淡紫，四周是暖棕色尘埃 + 极密的小星点——背景不是黑的。
- M8 很亮，宽带几小时就能出好图：peer_04（IMX571 OSC 无滤镜 4.1 h）获 IOTD，best_05（IMX571 OSC 2.5 h）获 Top Pick。

## 颜色基准
- Hα 主体：rose/粉红到偏红的洋红（peer 色相 rose≈0.50，red≈0.39，magenta≈0.05）。peer_02、peer_04、best_05 是最好的宽带基准；peer_01 偏深红，已略过头。
- 核心/沙漏：白 → 淡粉 → 淡紫（lavender），深积分有极淡的青色调；要亮但有层次，不是饱和红块，也不是 SHO 那种亮蓝。
- 暗带与 Bok 球：近黑、略带棕；NGC 6530：蓝白色星点群。
- 背景：暖棕/金棕色尘埃 + 星场（peer 背景 R/G≈1.19，B/G≈1.02，background_saturation≈0.30）。这是银河中心方向被红化的星光和尘埃，是真实颜色，最终图不要中和成灰。注意 checklists.md 的“背景 R/G、B/G 0.95–1.05”是线性阶段对真正天空背景的要求，不适用于 M8 成品里的尘埃区。
- M20（若入画）：中心粉红，北侧大片蓝色反射星云；NGC 6559 一带：粉红 + 小块蓝色反射 + 黑色暗星云（peer_05、best_05）。
- 不要模仿（窄带假色）：best_00（Bray Falls，SHO+RGB）、best_03（Jason Wehbe，SHO）、best_04（Kay Ogetay，SHO）的橙金/洋红/亮蓝配色，以及 SNR G007.5-01.7 的蓝色丝状结构；best_02（LRGB+Ha+OIII）核心外那圈青色壳层来自 OIII 窄带，宽带最多是很淡的痕迹。

## 关键结构
- 沙漏（Hourglass，由 Herschel 36 照亮）亮核：全图最亮，好作品里内部仍有层次，不是一团白。
- “礁湖”暗带：穿过星云中部，把西侧亮区与东侧 NGC 6530 分开；加上大量 Bok 球黑点（peer_01、peer_02 最清楚）。
- 外壳 Hα 的亮边与卷曲丝状结构（peer_01/02）；外壳之外还有更暗的大范围 Hα 和暗星云脉络（peer_00/05）。
- 亮度层次：核心最亮但不过曝（refs clip_high 中位 0.02–0.04%），外壳中等，尘埃背景本身不暗（bg≈0.15）。

## 背景与对比
- 背景亮且有纹理：peer background_level 0.153、lum_median 0.211；best 0.124 / 0.179。contrast_p99_p10：peer 0.45，best 0.57。
- 暗星云脉络和尘埃颜色要保留，不是平滑的灰底。
- 星点：密集、细小、颜色丰富（蓝白/橙黄）。高分作品普遍缩星（best_05、peer_04/05），让暗带和 Bok 球显出来；peer_03（STARRY Version）不缩星、噪点高、对比低（0.40），是反面例子。

## 构图（563 mm，144′×96′）
- M8 约 90′×40′，横放占长边约 60%；画面基本被星云 + 尘埃星场填满，几乎没有“干净天空”。
- M20 在 M8 北偏西约 1.43°：只有竖构图（长边沿南北）才能同框，两者都贴边。
- NGC 6559 / IC 4685 在 M8 以东约 1.4–1.5°，IC 1274 约 1.8°：横构图只能勉强装下 NGC 6559 一带（从 M8 西缘算起约 2.3°），IC 1274 会被切掉。
- 三者同框（best_05、peer_04/05，视场半径 1.6–1.9°）在我们的视场（半径 1.44°）里放不下。
- 背景提取：GradientCorrection 容易把棕色尘埃和 Hα 外晕当梯度减掉。先看 `previews/10_gc_model.jpg`，模型里出现星云形状或红/棕色块就改 DBE：低阶（1–2），样本只放在画面两端/四角的暗星场，避开 M8 外晕、M20、NGC 6559。
- 若借用 osc_galaxy 的 `locate_object` + `dbe_auto`：AdP 里 M8 是 90′ 的圆（无轴比），默认 objectScale 1.6 的排除圆直径 144′≈整个长边，只剩约 12 个角落样本 → 报 “too few background samples”。需 objectScale≈1.0，或覆盖 locate 的 `axisRatio≈2.2`、`posAngle≈90`，让排除区成为东西向椭圆。

## 常见坑
1. 沙漏/核心最先过曝：拉伸后看 clip_high（refs ≤0.1%），必要时用 HDR 压核心。
2. 背景提取或 BackgroundNeutralization 的取样落在尘埃上 → 尘埃被扣成灰绿/灰紫。BN 参考取最暗的暗星云区；SPCC 后成品保留暖色（R/G≈1.1–1.2）。
3. 颜色跑偏：宽带 M8 应偏 rose/粉红；白平衡偏红会变成单调深红（peer_01），偏黄会变橙。
4. 低空：Dec −24.4°，北纬 30°/40° 中天高度约 36°/26°；梯度强，大气消光让整体偏红偏暗，星点在高度方向有色散（蓝/红边）。
5. 星点压过暗带：需要缩星；SXT 后检查暗带和 Bok 球处有没有残影或空洞。
6. 一晚 1–2 h @ f/7.8：外围暗弱 Hα 和暗星云边界会噪，不要为了外晕把 bg 拉到 0.17 以上。

## 参数建议（相对默认 nebula recipe）
- stretch：targetMedian 0.20 合适（peer lum_median 0.21）。
- 背景：见“构图”；倾向 DBE，至少要核查 GC 模型。
- HDR：默认 recipe 没有这一步；建议对核心加 `hdr`（layers 5–6，amount 0.3–0.5），目标是沙漏内部可见层次。
- LHE：radius 162（≈3.7′，与暗带/亮边尺度相当）合适；amount 0.8 可保留，噪点明显时降到 0.6。
- saturation：boost 0.60 合适（peer signal_saturation 0.40，最艳的 peer_04 为 0.52）；不建议更高，以免尘埃背景发橙。
- HT：clipFraction 0.0004 合适；不要为了“中性”把背景 R/G 修到 1.0。
- NXT2：0.65/0.90 可用；M8 信号强，可降到 0.55 保住 Bok 球边缘。USM 0.6 合适。
- 星点：star_sat 不超过默认 0.56（72ED 双分离色差，亮星易有蓝紫晕）；重组 starsAmount 0.75–0.85（缩星）。
- 示例：`--set combine.recombine.starsAmount=0.8 --set starless.nxt2.params.denoise=0.55`

## 参考作品清单
| 组 | 标题 | 作者 | likes | 奖项 | 积分 | URL | 可借鉴 |
|---|---|---|---|---|---|---|---|
| best_00 | Messier 8 and SNR G007.5-01.7 - SHO + RGB | Bray Falls | 820 | IOTD | 57.5 h | https://www.astrobin.com/nu8p6d/ | SHO 配色不学；可学外壳/暗带层次与核心控制 |
| best_01 | A deep look at the Milky Way Core, 135mm HaRGB Mosaic | Jakob Sahner | 746 | IOTD | 103.3 h | https://www.astrobin.com/kgjlxo/ | 135 mm 银河中心拼接，构图与我们无关 |
| best_02 | Trifid, Lagoon and the Supernova remnant | Massimo Di Fusco | 578 | TP | 81.9 h | https://www.astrobin.com/426psk/ | 最接近自然色的 best；青色壳层来自 OIII |
| best_03 | Shockwaves Between Star birth and Star death | Jason Wehbe | 562 | IOTD | 77.4 h | https://www.astrobin.com/y1i382/ | SHO，颜色不学 |
| best_04 | Lagoon / Trifid / Chinese Dragon / Sh2-34 / SNR | Kay Ogetay | 517 | IOTD | 19.8 h | https://www.astrobin.com/j2q291/ | SHO 广角（Redcat），颜色不学 |
| best_05 | The Lagoon and the Trifid | Christoph Lichtblau | 440 | TP | 2.5 h | https://www.astrobin.com/zw8osg/ | IMX571 OSC 2.5 h：粉红主体 + 金棕尘埃 + 小星点，首选风格 |
| peer_00 | M8 & M20 - 2600MC - Spacecat 51 | Itto Ogami | 492 | - | 15.0 h | https://www.astrobin.com/rz6ynj/ | 250 mm 广角；中性棕尘埃，暗星云脉络清楚 |
| peer_01 | The Lagoon nebula | Christoph Lichtblau | 414 | - | 1.2 h | https://www.astrobin.com/g86elx/ | 近景（半径 0.62°）；Bok 球与亮边清楚，红色略过饱和 |
| peer_02 | The Lagoon nebula with its dark clouds surrounding | Christoph Lichtblau | 400 | - | 3.7 h | https://www.astrobin.com/5ikfgc/ | 粉红外壳 + 白/淡紫核心 + 暗云：颜色最佳基准 |
| peer_03 | STARRY Version - Lagoon And Trifid | Itto Ogami | 389 | - | 4.0 h | https://www.astrobin.com/jit318/ | 不缩星、噪点高、对比低：反面参考 |
| peer_04 | The Trifid (M20) and Lagoon (M8) Nebulas | Michael Kalika | 381 | IOTD | 4.1 h | https://www.astrobin.com/1mbsgg/ | IMX571 OSC 无滤镜获 IOTD；饱和度上限参考 |
| peer_05 | M8, M20 | wsg | 328 | - | 15.4 h | https://www.astrobin.com/l7at8j/ | 视场最接近我们（半径 1.6°）；核心淡紫，NGC 6559 暗星云 |

## 数值指纹（refs.json 中位数）
| 组 | n | background_level | lum_median | contrast_p99_p10 | signal_sat 均值 (p90) | bg_sat | 背景 R/G, B/G | 主导色相（均值） |
|---|---|---|---|---|---|---|---|---|
| peer | 6 | 0.153 | 0.211 | 0.447 | 0.40 (0.56) | 0.30 | 1.19, 1.02 | rose 0.50, red 0.39, magenta 0.05 |
| best | 6 | 0.124 | 0.179 | 0.570 | 0.39 (0.58) | 0.34 | 1.40, 1.16 | rose 0.40, red 0.37, magenta 0.08, azure 0.06, blue 0.03 |
| best 去掉 best_01 | 5 | 0.127 | 0.171 | 0.570 | 0.40 (0.59) | 0.39 | 1.50, 1.17 | rose 0.45, red 0.27, magenta 0.09, azure 0.07 |

- 色相是各图 `signal_hue_mix` 的平均（缺失按 0）。best 的 azure/blue/violet 来自 SHO 的 OIII 映射，best 背景 R/G 1.4–1.5 是窄带红底，都不是我们的目标。
- 建议目标：bg≈0.14–0.16，lum_median≈0.20，contrast≈0.45–0.50，signal_saturation≈0.40，背景 R/G≈1.1–1.2。noise_hf 受缩略图压缩影响，不可比。
