# NGC 6334 — Cat's Paw Nebula（猫爪星云）参考笔记

数据：`refs.json`（AstroBin 按 likes 排序，2026-10-10 抓取，候选 68 张，`--fov 1.44`）；best 6 张 + peer 只有 3 张，全部已查看。
我们：ASI2600MC Air（IMX571 OSC，无滤镜）+ 72 mm ED @ 563 mm（≈f/7.8），1.38″/px，视场 2.40°×1.60°（144′×96′），常见一晚 1–2 h。

## 目标类型
- 发射星云（大质量恒星形成区，HII），天蝎座银河盘面，Dec −36.1°，AdP 直径 40′。形态：一个大“掌垫” + 3–4 个圆形“趾”（泡状 HII 区），周围有暗尘埃带和大片暗弱 Hα。
- OSC 宽带应有的样子：朱红/橙红到玫瑰红的单一暖色调星云（比 M8 更偏橙红、粉色更少），层次靠亮度和暗带而不是颜色变化；几乎没有青/蓝；背景是暗灰褐星场 + 暗星云。

## 颜色基准
- 宽带 peer：色相 red≈0.66，rose≈0.30。peer_02（IMX571 OSC + RASA 8，无滤镜）朱红/橙红、很饱和（p90 0.74），是首选颜色基准；peer_00（IMX193 OSC）同色调但淡（sat 0.20）；peer_01（QHY8L OSC）玫瑰红，但标题写 “NB”，可能用了窄带/双窄带滤镜，仅作参考。
- best_03（Maicon Germiniani）是 best 里唯一的自然色风格：洋红-猩红 + 多彩星点；看起来像 HaRGB，宽带 OSC 很难达到这种洋红浓度。
- 偏橙红的可能原因：NGC 6334 前景尘埃消光大，Hβ/OIII 等短波被削弱（与 peer 色相一致）。
- 暗带/小暗团：棕黑；背景：中性到略暖（peer R/G 0.96–1.19，B/G 0.94–1.18）。
- 不要模仿（窄带假色）：best_00（Min Xie，趾内蓝白 OIII）、best_01（Jian Yuan Peng，SHO 橙金 + 亮蓝）、best_02（Steeve Body，HOS 橙红 + 青蓝）、best_04（Logan Carpenter，SHO）、best_05（Claudio Ulloa Saavedra，HSO-LRGB 紫蓝核心）。“趾里的蓝/青色气泡”是 OIII 窄带，宽带 OSC 不应凭空提蓝。

## 关键结构
- 大掌垫 + 3–4 个趾：每个趾是带亮边的圆泡，窄带图里有同心壳层（best_01/02/04），宽带近景（peer_01）也能看到泡内丝状纹理。
- 掌垫内侧边缘一个醒目的小黑暗云团（dark globule）以及趾之间的暗带：几乎所有参考图都很清楚，是视觉锚点。
- 外围大范围暗弱 Hα + 棕黑暗星云：best_05（视场≈我们）满幅都是红/棕色云；宽带短积分只会有很淡的一层。
- 亮度：掌垫/趾中等亮，动态范围比 M8 小，一般不过曝（best_03 clip_high 0.2% 属例外）；难点是信号和对比，而不是 HDR。

## 背景与对比
- peer：bg 0.143，lum_median 0.164，contrast 0.372——背景偏亮、对比低（密集星场）；best：bg 0.095，lum 0.131，contrast 0.476——更暗、更有对比。
- 星点：银河盘面星点极多（peer_00/02）；好作品星点小而多彩（best_00/03），明显缩过星，让爪子成为主角。
- 暗带近黑但留有棕色，不要压成死黑。

## 构图（563 mm，144′×96′）
- 爪子约 40′：占长边约 28%、短边约 42%；四周是星场 + 暗带 + 淡 Hα。best_05（FSQ-106 + IMX571，1.465″/px，视场半径 1.48°）几乎就是我们的视场，是最直接的构图参照：爪子居中，周围留白较多。
- NGC 6357（龙虾星云）在北偏东约 2°：peer_00/peer_02 用 1.8–2.1° 的视场半径才同框；我们 2.4°×1.6° 放不下两者，单独构图。
- 背景提取：爪子只占画面一部分，GradientCorrection 通常可用；但这是低空目标，梯度常非线性（地平线光害/消光），GC 后要看模型，若模型里出现爪子形状或暗带，改 DBE（degree 2，样本避开爪子及其红晕，也避开暗星云）。用 `dbe_auto` 时 AdP 40′ × objectScale 1.6 = 排除直径约 64′，剩余样本足够。

## 常见坑
1. 低空：Dec −36°，北纬 30°/40° 中天仅约 24°/14°；可拍时间短，梯度强，消光让整体偏红偏暗，大气色散让星点在高度方向出现蓝/红边。
2. 照着 SHO/HOO 参考定颜色：把爪子做成橙金 + 蓝，或在趾中心硬提蓝色。
3. 星点淹没星云：不缩星时爪子显得小而淡（peer_00）。
4. 背景灰、对比低：默认 targetMedian 0.20 偏亮；peer 中位 contrast 只有 0.37。
5. 提饱和前降噪不足 → 红色斑驳的单色调噪点。
6. 光学差距：peer_02 用 RASA 8（f/2），同为 IMX571 时它原生像素的信号率约为我们 f/7.8 的 15 倍；一晚 1–2 h 不要追它的饱和度和深度。

## 参数建议（相对默认 nebula recipe）
- stretch：targetMedian 0.16–0.18（peer lum_median 0.164，best 0.131）。
- 背景：GC + 检查模型；梯度复杂时 DBE。
- LHE：radius 162（≈3.7′，趾约 8–10′）合适，amount 0.7–0.8；噪点明显时 0.6。
- saturation：0.65–0.70（peer signal_saturation 0.44，p90 0.57–0.74；best 0.50），但色相保持红/橙红，不要推向洋红或橙黄。
- HT：clipFraction 0.0004 合适；目标 bg≈0.10–0.14，暗带不压死。
- NXT2：0.65/0.90 合适；积分不足 3 h 时 denoise_color 保持 0.9。USM 0.6 合适。
- 星点：starsAmount 0.7–0.8（缩星）；star_sat 不超过 0.56（72ED 色差）。
- 示例：`--set stretch.stretch.targetMedian=0.17 --set starless.sat.boost=0.65 --set combine.recombine.starsAmount=0.75`

## 参考作品清单
| 组 | 标题 | 作者 | likes | 奖项 | 积分 | URL | 可借鉴 |
|---|---|---|---|---|---|---|---|
| best_00 | From the North: Cat's Paw Nebula Wide-Field | Min Xie | 275 | TP | 32.1 h | https://www.astrobin.com/xz5ouc/ | 北半球拍摄的宽视场；背景极暗（0.064）、星点小而彩；配色是窄带，不学 |
| best_01 | NGC 6334 (Cat's Paw, Bear Claw) SHO+RGB stars | Jian Yuan Peng | 233 | TP | 31.0 h | https://www.astrobin.com/dmkjve/ | SHO；可学趾的泡状壳层清晰度 |
| best_02 | NGC 6334 / Tyke's Paw Nebula | Steeve Body | 221 | TP | 37.0 h | https://www.astrobin.com/gqrovm/ | HOS+RGB 极艳；不学颜色 |
| best_03 | Cats Paw Nebula NGC 6334 | Maicon Germiniani | 195 | TP | 未标注 | https://www.astrobin.com/ycmuf0/ | 唯一自然色 best：洋红-猩红、彩色星点、暗团清晰 |
| best_04 | The Cat's Paw Nebula | Logan Carpenter | 194 | TP | 13.6 h | https://www.astrobin.com/r6edlv/ | SHO（IMX571 mono），不学颜色 |
| best_05 | Cat's Paw Nebula - NGC 6334 - HSO-LRGB | Claudio Ulloa Saavedra | 190 | TP | 63.3 h | https://www.astrobin.com/ocostj/ | 视场≈我们：构图参照；HSO 配色不学 |
| peer_00 | NGC 6357 (Lobster Nebula), NGC 6334 (Cat's Paw Nebula) | Nick Large | 229 | - | 4.2 h | https://www.astrobin.com/ttkfx0/ | IMX193 OSC 4.2 h：橙红偏淡、星场主导，短积分的现实水平 |
| peer_01 | First try...Cats Paw Nebula - NB with QHY8L | Daniel Nobre | 208 | - | 未标注 | https://www.astrobin.com/418543/ | 近景玫瑰红、泡内纹理；标题 “NB” 可能是窄带 |
| peer_02 | Paw and Claw ! | AstroRBA | 108 | - | 5.8 h | https://www.astrobin.com/4jjoek/ | IMX571 OSC 无滤镜：宽带颜色基准（朱红/橙红 + 棕黑暗带） |

## 数值指纹（refs.json 中位数）
| 组 | n | background_level | lum_median | contrast_p99_p10 | signal_sat 均值 (p90) | bg_sat | 背景 R/G, B/G | 主导色相（均值） |
|---|---|---|---|---|---|---|---|---|
| peer | 3 | 0.143 | 0.164 | 0.372 | 0.44 (0.57) | 0.22 | 0.97, 1.00 | red 0.66, rose 0.30 |
| best | 6 | 0.095 | 0.131 | 0.476 | 0.50 (0.71) | 0.39 | 1.40, 1.02 | red 0.51, rose 0.29, magenta 0.07, violet 0.03, blue 0.03 |

- 色相是各图 `signal_hue_mix` 的平均（缺失按 0）。peer 只有 3 张，其中两张是带龙虾星云的宽视场，统计意义弱；best 全部含窄带成分。
- 建议目标：bg≈0.11–0.13，lum_median≈0.15，contrast≈0.42，signal_saturation≈0.45，色相以 red/rose 为主（red > rose），背景 R/G≈1.0–1.15。noise_hf 不可比。
