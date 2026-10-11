# M101 / NGC 5457 — Pinwheel Galaxy（风车星系）参考笔记

数据：`refs.json`（AstroBin 按 likes 排序，2026-10-10 抓取，候选 45 张，`--fov 1.44`），12 张缩略图已逐张查看，全部是本目标。
我们：ASI2600MC Air（IMX571 OSC，无滤镜）+ 72 mm ED @ 563 mm（≈f/7.8），1.38″/px，视场 2.40°×1.60°（144′×96′），常见一晚 1–2 h。

## 目标类型
- 正向（face-on）晚型旋涡星系（SAB(rs)cd），大熊座，Dec +54.3°；AdP 直径 21.9′，暗弱外旋臂延伸到约 28′ 以上。总星等亮（7.9）但面积大、表面亮度低。
- 旋臂上有许多巨型 HII 区：NGC 5447/5449/5450/5451/5453/5455/5461/5462/5471 都在 M101 盘内（距核心 3′–12′，NGC 5471 在外臂）。
- 类型为 galaxy → objects.py 会选 `osc_galaxy` recipe；下面的建议相对默认 nebula recipe 给出，并注明与 osc_galaxy 的差别。
- OSC 宽带应有的样子：暖黄/奶白的小核心，内臂有细的棕色尘埃带，外臂蓝（azure），旋臂上点缀淡粉红 HII 结，背景中性近黑。

## 颜色基准
- 核心：暖黄/奶油/桃色（best_01/04/05 黄白，best_00 偏橙桃）；不应偏绿或纯白。
- 旋臂：蓝为主（peer 色相 azure≈0.59，cyan≈0.10，blue≈0.09），外缘最蓝；内臂的棕色尘埃带在 best_01、peer_04 最清楚。
- HII 区：小的粉红-洋红点。best_00（HOORGB）、best_01（LRGB+Ha）里的鲜艳洋红是加了 Ha；纯 RGB 的 peer_00/01 只有很淡的粉点。宽带只应做到淡粉，不要“画”出洋红斑块。
- 背景：中性（12 张 refs 的背景 R/G、B/G 中位都是 1.00），best 的背景饱和度仅 0.04。
- 伴星系：NGC 5474（南偏东约 44′，偏心亮核的蓝色小旋涡）和 NGC 5477（东约 22′，14 等小矮星系）；peer_01/05 视场里还有若干黄色椭圆星系与侧向星系。
- 没有窄带假色的问题，但要避免把旋臂做成紫色（best_02 偏紫蓝）或整体偏青绿。

## 关键结构
- 多条细长旋臂且不对称：一侧外臂更松散、延伸更远（多数参考图里伸向左/左下），外缘有零散的蓝色星团块与 HII 结。
- 小而亮的核心 + 紧绕的内臂和细尘埃带（best_01、best_04 是示范）。
- 外臂极暗：refs 普遍 ≥10 h；peer_02（3 h + LP 滤镜）只剩核心和内臂，几乎无色。
- 亮度层次：核心最亮但不能过曝，内臂中等，外臂接近背景——需要平滑的拉伸曲线。

## 背景与对比
- 背景暗而中性：peer bg 0.090，best 0.081；lum_median 都约 0.092。contrast：peer 0.40，best 0.49。
- 星系颜色本来就淡：signal_saturation 只有 0.14–0.16（星云 refs 约 0.40），效果来自“黄核 vs 蓝臂”的对比，而不是高饱和。
- 星点：小、颜色丰富（橙/黄/蓝白）；高银纬星场稀疏，不必大幅缩星；best_03/04/05 的衍射芒来自反射镜，不必模仿。

## 构图（563 mm，144′×96′）
- M101 只占长边约 15–20%（全分辨率 ≈950–1250 px），是小目标。最接近我们构图的是 peer_01（IMX571，1.49″/px，视场半径 1.0°）和 peer_05（IMX571，视场半径 1.1°）。
- 两种出图：宽视场 “M101 and friends”（NGC 5474、NGC 5477 都在视场内），或后期裁成约 1/2–1/3（best 组视场半径 0.53–0.88°，M101 占画面 40–60%）。
- 背景提取：背景处处可见，GradientCorrection 合适；确认外臂（直径约 30′）没有进梯度模型。osc_galaxy 的 `dbe_auto`（AdP 21.9′ × objectScale 1.8 → 排除直径约 39′）也可以；该 recipe 是按“星系填满画面（M31）”设计的，对我们的 M101 并非必须。

## 常见坑
1. 用 nebula 默认拉伸（targetMedian 0.20）：背景发灰、外臂噪点暴露；refs 的 lum_median ≈0.09。
2. 积分短 + f/7.8：peer_05（IMX571 @ f/5，5.2 h）原生像素信号率约为我们的 2.4 倍，它的星系仍然小而淡（contrast 0.17）。一晚 1–2 h 的外臂和 HII 区不要硬拉，宁可接受深度差距。
3. 核心过曝，或 LHE 在星系边缘造成暗圈/光晕。
4. 偏绿：OSC 星系常见；SPCC（white reference: Average Spiral Galaxy）之后仍偏绿，可对 starless 轻度 SCNR（≤0.5）。
5. NXT 太强抹掉 HII 结和尘埃带，星系变“塑料”。
6. SXT 可能把 NGC 5477 或恒星状的 HII 结（如 NGC 5471）当成星点移走 → 重组后核对。

## 参数建议（相对默认 nebula recipe）
- stretch：targetMedian 0.10（默认 0.20 约亮一倍）。
- linear NXT：0.25/0.40（同 osc_galaxy）。
- HDR：`hdr` layers 5、amount 0.3（osc_galaxy 已有），保住核心。
- LHE：radius ≈100–166 px（≈2.3–3.8′；osc_galaxy 的 "auto" = 0.35×半长轴 ≈166 px），amount 0.4–0.6，经 range mask（rangeLow 0.16）只作用于星系。
- saturation：0.45–0.55（osc_galaxy 是 0.62 + 0.56 两遍，短积分时可能放大色噪）；目标 signal_saturation≈0.15–0.20，background_saturation ≤0.10。
- HT：clipFraction 0.00015–0.0004，目标 bg≈0.08–0.09。
- NXT2：0.50–0.55 / 0.80（保 HII 结）。USM：sigma 1.5，amount 0.5（结构比星云细）。
- 星点：starsAmount 1.0（不缩或极轻），star_sat 0.54，SCNR 0.5。
- 示例：`--set stretch.stretch.targetMedian=0.10 --set starless.lhe.params.amount=0.5 --set starless.nxt2.params.denoise=0.55 --set starless.usm.params.sigma=1.5`

## 参考作品清单
| 组 | 标题 | 作者 | likes | 奖项 | 积分 | URL | 可借鉴 |
|---|---|---|---|---|---|---|---|
| best_00 | DSC2 Presents: M 101 and NGC 5474 in HOORGB (600+ hours) | Mikołaj Wadowski | 444 | TP | 610.3 h | https://www.astrobin.com/8hgecz/ | 多人合成；外臂延展与伴星系构图；洋红 HII 来自 Ha |
| best_01 | The Pinwheel Galaxy M101 (Sb) | Brian Diaz | 421 | TP | 67.2 h | https://www.astrobin.com/ffl79g/ | CDK14 LRGB+Ha：黄核 + 尘埃带 + HII 的细节上限 |
| best_02 | M101 LRGB by Insight Observatory - To my mom | Daniel Nobre | 308 | TP | 未标注 | https://www.astrobin.com/khy0ff/ | 背景纯黑；旋臂偏紫，色调不学 |
| best_03 | Messier 101 | Marc | 304 | IOTD | 21.1 h | https://www.astrobin.com/pr2cup/ | 黄核/蓝臂/粉 HII 平衡得好 |
| best_04 | M 101 | Jens Zippel | 288 | TP | 9.5 h | https://www.astrobin.com/347019/ | 9.5 h 外臂已很完整；颜色克制自然 |
| best_05 | M101 the Pinwheel Galaxy | tommy_nawratil | 263 | TP | 10.6 h | https://www.astrobin.com/347204/ | 与 best_04 同风格；伴星系清楚 |
| peer_00 | NGC 5457 (M101) in RGB | Armin Unterwandling | 551 | - | 15.0 h | https://www.astrobin.com/cen7y3/ | IMX533 OSC，1.379″/px（=我们）：纯 RGB 颜色基准 |
| peer_01 | M101 and Friends - Ultracat 108 - Mark 3 | Itto Ogami | 505 | - | 17.0 h | https://www.astrobin.com/uyy7rl/ | IMX571 OSC，视场半径 1.0°：最接近我们的构图 |
| peer_02 | M101 | Armin Unterwandling | 455 | - | 3.0 h | https://www.astrobin.com/pfv71x/ | 3 h + LP：几乎无色、外臂缺失——短积分反面参考 |
| peer_03 | NGC5457 | Armin Unterwandling | 435 | - | 11.2 h | https://www.astrobin.com/ys2yx9/ | 干净，但饱和与对比偏低（0.33） |
| peer_04 | Pinwheel Galaxy in Ursa Major | Theodore Arampatzoglou | 413 | - | 13.9 h | https://www.astrobin.com/1j2b8x/ | mono L + OSC 颜色；蓝臂 + 棕尘埃带最鲜明 |
| peer_05 | M101 & Friends Mark 2 - 130mm Stellarvue f/5 - 2600MC | Itto Ogami | 394 | - | 5.2 h | https://www.astrobin.com/x2ca98/ | IMX571 OSC 5.2 h 宽视场：星系小、对比低（0.17） |

## 数值指纹（refs.json 中位数）
| 组 | n | background_level | lum_median | contrast_p99_p10 | signal_sat 均值 (p90) | bg_sat | 背景 R/G, B/G | 主导色相（均值） |
|---|---|---|---|---|---|---|---|---|
| peer | 6 | 0.090 | 0.092 | 0.398 | 0.16 (0.28) | 0.14 | 1.00, 1.00 | azure 0.59, cyan 0.10, blue 0.09, red 0.08 |
| best | 6 | 0.081 | 0.092 | 0.489 | 0.14 (0.29) | 0.04 | 1.00, 1.00 | azure 0.39, red 0.20, blue 0.15, orange 0.08, cyan 0.06 |

- 色相是各图 `signal_hue_mix` 的平均（缺失按 0）。“signal”（最亮 20% 像素）主要是星系盘和星点：azure 来自旋臂，red/orange 来自核心、HII 和黄色恒星。
- 建议目标：bg≈0.08–0.09，lum_median≈0.09–0.10，contrast≈0.45，signal_saturation≈0.15–0.18，bg_sat ≤0.10，背景 R/G≈B/G≈1.0。peer_02/05 的 noise_hf=0（缩略图被平滑），噪声不可比。
