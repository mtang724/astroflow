# 第4期（下）：彩色相机 HO 双窄带后期（PixInsight 进阶教程，BV1uimABGEEA，作者：B 站 UP 主氪化金）

素材：NGC 6960（西面纱），彩色相机 + Ha/OIII 双窄带滤镜（SPCC 里选的是 Optolong L-eXtreme）的一张线性 RGB 主帧，6224×4168，BAYERPAT RGGB，FITS 头里没有 FILTER；焦距 750 mm、像元 3.76 µm（≈1.03″/px）；叠加时没有自动裁边。素材在教程资源 `进阶篇/第4期 HOO窄带后期处理/彩色/NGC6960.xisf`。
原始材料（转写、截图，只在本机，不进仓库）：`ep4b-osc-ho-dualband/` 下的 `transcript.txt`、`frames/`、`sheets/`、`keyframes/`。上集（黑白 HOO）的材料在 `ep4a-mono-hoo/`。对应配方：`astroflow/pipeline.py` → `osc_multiband_nebula`（`MULTIBAND_NEB`，在本期之前写的暂定版，差别见后文）。

06:17–09:59 没有讲解（画面字幕说明：非线性阶段的细节看上集 22:33 起，本集素材一般，只快速带过），这段的步骤和参数全部从对话框和 Process Console 日志读出。

## 思路

双窄带滤镜挡掉了 Ha 和 OIII 以外的光，彩色传感器的 R 像素基本只记录 Ha，G、B 像素记录 OIII。所以叠加出来的彩色图本身就等同于黑白相机做完 H→R、O→G、O→B 通道合成的 HOO 图：**不拆通道、不对齐、不做 ChannelCombination，也没有用 PixelMath 重新分配通道**。整体按彩机流程走，比黑白 HOO 简单；非线性阶段加上窄带特有的调色（00:21–01:12，04:13–04:28）。

## 线性阶段

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 查看 | 打开主帧，STF 关锁链自动拉伸 | 00:17–00:21 |
| 裁边 | 叠加时没自动裁，边缘有没完全重合的部分 → DynamicCrop 切掉：6224×4168 → **6140×4096**（每边约 40 px） | 01:12–01:21 |
| 背景提取 | 梯度较大。作者另外试过 GC，效果不好 → **手动 DBE** 打点，重新采样几次直到满意。对话框：Tolerance **3.0**，Shadows relaxation **3.0**，Smoothing factor **0.25**，默认样本半径 **10**，每行 **10** 个样本，最小样本权重 **0.75**；校正方式那一栏折叠着，看不到 | 01:21–01:48（对话框 01:35） |
| 色彩校准 | BNCC 前几期讲过，本期只演示 SPCC | 01:51–02:03 |
| 板解析 | ImageSolver v6.3.1：坐标、时间、焦距、像元都从文件头读出，直接 OK；ICRS、自动星表、自动极限星等、勾 Distortion Correction | 02:03–02:20（对话框 02:05） |
| SPCC | 背景参考：框一块纯背景的 Preview（Left 1234，Top 26，95×78）拖进 Region of Interest。窄带滤镜可以开 Narrowband 模式自己填波长/带宽，但**这块滤镜在 SPCC 列表里有现成的组合曲线**，所以不开窄带模式，R/G/B 分别选 **Sony CMOS R-UVIRcut / Opt. L-eXtreme**、**Sony CMOS G-UVIRcut / Opt. L-eXtreme**、**Sony CMOS B-UVIRcut / Opt. L-eXtreme**（同一列表里还有 Antlia Triband、Antlia-ALP-T、Baader UHC-S、Opt. L-eNhance、Opt. L-Ultimate）。QE 曲线 **Ideal QE curve**（彩机），白参考 **Average Spiral Galaxy**，Catalog **Gaia DR3/SP**，BN 上下限默认（−2.80 / +2.00），Optimize for stars 不勾 | 02:20–02:57（对话框 02:35–02:55） |
| 校准结果 | 开锁链重新 STF：颜色正常（Ha 红、OIII 青绿） | 02:57–03:09 |
| 反卷积 | 导星有点拉线，星点略椭圆 → **BXT**（v2.0.4，AI4）：Sharpen Stars **0.50**，Adjust Star Halos **0.26**，Automatic PSF ✓，Sharpen Nonstellar **0.50**，其余选项不勾。修复后星点明显变圆 | 03:12–03:28 |
| 线性降噪 | **NXT** AI3，Intensity/color separation ✓：明度 **0.30**（信噪比比上集黑白素材差很多，所以比上集的 0.25 高），彩噪 **0.40**（保守取值），Iterations 2；降噪前后变化很小 | 03:31–04:05 |

## 拉伸与去星

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 拉伸 | **EZ Soft Stretch**：Target Median **0.24**（先试 0.25），Expand Low **0.05**，Aggressiveness **16.3**（默认 5），Zero in White Point 不勾；日志：MTF 目标 0.19 = 0.24 − 0.05 | 04:09–04:28（对话框 04:15–04:25） |
| 去星 | **SXT**（v2.3.11，AI11）直接对彩色图：Generate Star Image ✓，Unscreen Stars ✓，Large Overlap ✗。星点图最小化放一边（上集因分离不干净改成拆 R/G/B 分别去星，这里没这样做） | 04:28–04:42 |

## 非线性阶段（05:00 起；06:17 以后无讲解，数值取自对话框和日志）

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 红蓝配色 | 拉伸后是红 + 绿（OIII 偏绿），作者偏好红蓝 → 只在 OIII 区域改色：① 对无星图执行 **BlueMask** 进程图标（PixelMath，生成新灰度图 `BlueMask`，日志显示结果 Rescale 到 [0,1]），表达式见下；② 对 `BlueMask` 执行 **MaskBlur** 图标（PixelMath `gconv($T, 15, 1, 0)`：σ 15 px、长宽比 1、旋转 0），让蒙版变软；③ 蒙版盖回无星图（OIII 区域裸露），确认方向后 **CurvesTransformation 一次**：**B 上提（0.424→0.571）**，**G 下压（0.558→0.450）**；④ 去掉蒙版 | 05:00–05:39（BlueMask 05:05–05:07，MaskBlur 05:09–05:12，CT 05:19–05:35） |
| 第一次调色 | ChannelExtraction 提亮度 → `Image01_L`；**HT 切掉蒙版暗部：Shadows 0.0734**（裁掉 0.14% 像素），Midtones 0.5；作为蒙版（亮处裸露）→ CT：**S 两点（0.320→0.581）、（0.499→0.724）**，**RGB/K（0.442→0.540）** 提亮，R（0.494→0.512）微升，G（0.501→0.491）微降，B 不动 | 05:39–06:35 |
| 背景色平衡 | 不带蒙版的 HT，只动 R、B 的黑点：**R Shadows 0.00506，B Shadows 0.00506**，G 和 RGB/K 不动（日志里 G 通道为 identity）；中途试过 RGB/K 黑点 0.033、0.020，最后清零 | 06:40–07:03 |
| 去绿 | **SCNR**：Green，Average Neutral，Amount **1.00**，Preserve lightness ✓，不带蒙版，作用于整张无星图 | 07:06–07:12 |
| 第二次调色 | 重新提亮度作蒙版，这次**不切暗部** → CT：**S（0.382→0.574）、（0.468→0.646）**，RGB/K（0.514→0.499）略压 | 07:15–07:35 |
| 非线性降噪 | **NXT** AI3：明度 **0.65**，彩噪 **0.90**，Iterations 2，不带蒙版 | 07:42–08:25 |
| （放弃） | HT 单独调 G 中间调、R 黑点，试过没应用（日志里 NXT 之后直接是下一次 ChannelExtraction） | 08:25–08:52 |
| 压暗背景 | 第三次提亮度作蒙版（不切暗部），**反相使用**：画面没显示蒙版方向，但对比应用前后，最暗的四分之一亮度 ×0.75、色度 ×0.67，最亮处亮度只 ×0.94，和用反相 L 蒙版算出的结果一致 → CT：**S（0.532→0.455）** 降饱和，**RGB/K（0.556→0.444）** 压暗。效果：背景更暗、背景彩噪更少 | 09:01–09:20 |
| 对比度 | 不带蒙版的 HT（RGB/K）：**Shadows 0.06582**（只裁 37 个像素，≈0.0001%），**Midtones 0.4228**（前后画面与不带蒙版的 HT 计算一致） | 09:28–09:40 |
| 星点 | 星点图**不做任何处理**（不提饱和、不 SCNR） | 09:43 |
| 合并 | PixelMath 单一 RGB/K 表达式 **`~((~Image01)*(~Image01_stars))`**（screen），应用到无星图 `Image01` | 09:43–09:55 |
| 没做的 | LHE、USM 锐化、范围蒙版提亮暗星云（上集做了）都没做 | — |
| 收尾 | 这是作者早期拍的数据，质量差，所以步骤都快速带过；非线性阶段黑白、彩色没有本质区别，以上集为准 | 09:59–10:37 |

BlueMask 进程图标的 PixelMath 表达式（日志原文，换行已合并；符号 E1–E4）：

```
//  Simple Blue Color Mask
E1= 0   ;//  Chrominance Mask= 0, Lightness Mask= 1
E2= 1.0 ;//  Mask Strength (Range= 0 to 1)
//Equations:
E3= iif(CIEh($T)<0.5,0,iif(CIEh($T)<=(2/3),~mtf((CIEh($T)-0.5)/(1/6),~E2)*CIEc($T),iif(CIEh($T)<=(5/6),~mtf(((5/6)-CIEh($T))/(1/6),~E2)*CIEc($T),0)));
E4= iif(CIEh($T)<0.5,0,iif(CIEh($T)<=(2/3),~mtf((CIEh($T)-0.5)/(1/6),~E2)*CIEL($T),iif(CIEh($T)<=(5/6),~mtf(((5/6)-CIEh($T))/(1/6),~E2)*CIEL($T),0)));
iif(E1==0,E3,E4)
```

含义：CIE LCh 色相（0–1）落在 0.5–5/6、中心 2/3 的像素，取其色度 CIEc（E1=0）或明度 CIEL（E1=1）作为蒙版值，其他为 0。E2=1 时 `~mtf(x, 0)` 恒为 1，窗口内不衰减；E2 小于 1 时变成以 2/3 为峰的三角窗。界面上同一组图标还有 RedMask、YellowMask、GreenMask、CyanMask、MagentaMask、HOONormalizationV4、SHONormalizationV3、RGBstars_to_NB_V11、ModifiedSCNR_v4（本集只用到 BlueMask 和 MaskBlur；其他颜色的表达式没有显示，按理只是色相窗口不同）。

## 和上集（黑白 HOO）的区别

| 环节 | 上集：黑白 HOO（时间是上集的） | 本集：彩机双窄带 |
|---|---|---|
| 得到 HOO 图 | StarAlignment 把 O 对到 H → ChannelCombination R=H、G=O、B=O → 裁到重合区 → 旋转 180°（01:11–05:37） | 叠加图就是 HOO，只裁边 |
| 背景提取 | GC 就够（06:28–07:22） | GC 不行，手动 DBE |
| SPCC | QE 选 Sony IMX571（黑白传感器）；Antlia 滤镜不在列表 → Narrowband 模式，656.3/500.7/500.7，带宽都改成 4.5 nm（09:52–10:58） | QE 选 Ideal；列表里的 “Sony CMOS X-UVIRcut / Opt. L-eXtreme” 组合曲线，不开窄带模式 |
| 线性 NXT | 明度 0.25，彩噪 0.40（11:52–12:25） | 明度 0.30（信噪比差），彩噪 0.40 |
| RGB 星点 | 另拍 RGB：对齐到 HOO、合成、DBE+GC、SPCC、BXT、拉伸、SXT 只留星点（12:54–20:26） | 没有，直接用双窄带的星点，也不处理 |
| 去星 | 彩色图 SXT 把红色星云带走 → 拆成 R/G/B 分别 SXT 再合并（20:29–22:35） | 直接对彩色图 SXT |
| 暗星云 | RangeSelection 反相蒙版 + CT RGB/K 提亮暗部（22:41–24:06） | 没做 |
| LHE | 不做（面纱本身结构强，再强化太炸）（24:08–24:32） | 不做 |
| 红蓝配色 | GreenMask 提不出 → BlueMask + MaskBlur + CT，B 上 G 下，做了几遍（24:38–26:46） | 同样方法，一遍 |
| 调色 | L 蒙版（HT 切暗部）+ CT 提饱和，分两次（27:04–27:58） | L 蒙版（切暗部）+ 饱和/RGB/K；另加 SCNR 去绿；第二次调色的蒙版不切暗部 |
| 非线性 NXT | 明度 0.6，彩噪 0.9（28:01–28:24） | 明度 0.65，彩噪 0.90 |
| 背景/对比度 | HT 单拉 R 中和偏红的背景，再用 RGB/K 压暗（28:28–29:13） | HT 拉 R、B 黑点（0.005）；反相 L 蒙版 CT 压暗、降饱和；最后 HT 黑点 0.066、中间调 0.423 |
| 锐化 | 不锐化（锐度已够） | 不锐化 |
| 星点 | RGB 星点提饱和（29:32–29:53） | 不处理 |
| 合并 | PixelMath screen，Replace target image（29:55–30:11） | 同 |

## 和 astroflow 现有 `MULTIBAND_NEB` 的区别

`MULTIBAND_NEB` 是在没有彩机窄带教程时按 Antlia 四通道滤镜推测的暂定配方。

| 步骤 | `MULTIBAND_NEB`（暂定） | 本期视频 |
|---|---|---|
| 裁边 | 无（默认输入是 WBPP 自动裁过的主帧） | 输入没自动裁边时先裁 |
| 背景 | `gradient_correction` 默认 | GC 效果差 → 手动 DBE |
| 色彩校准 | `color_calibration` 强制 BNCC；filters.md 认为 SPCC 不适用 | **SPCC + “彩色传感器 × 滤镜”组合曲线**（既不是宽带曲线，也不是窄带模式）；滤镜不在库里时才用窄带模式 |
| BXT | 默认（halos 0） | Adjust Star Halos 0.26（画面所见，没有解释） |
| 线性 NXT | 0.30 / 0.45 | 0.30 / **0.40** |
| 拉伸 | EZ 0.20，aggressiveness 5 | EZ **0.24**，aggressiveness **16.3** |
| 去星 | SXT unscreen | 同 |
| LHE | auto，amount 0.7 | **不做** |
| 红蓝配色 | 无 | **BlueMask + MaskBlur + CT（B↑ G↓）** |
| 饱和度 | `saturation` boost 0.72 两遍（maskClip 0.10，maskMidtones 0.3） | CT 两次：第一次 L 蒙版切 0.073，S 两点 + RGB/K 提亮；第二次 L 蒙版不切，S 两点 + RGB/K 略压 |
| 背景色平衡 | 无 | HT 只拉 R、B 黑点 |
| SCNR（星云图） | 无（只对星点） | 无星图 SCNR 绿 1.0 |
| 顺序 | lhe → sat → ht → nxt2 → usm | 配色 → 调色 1 → 背景色平衡 → SCNR → 调色 2 → NXT → 反相 L 蒙版压暗 → HT |
| 对比度 HT | auto，裁 0.04%，midtones 0.46，在 NXT 之前 | 最后：黑点 0.0658（只裁 ≈0.0001%），midtones **0.423** |
| 非线性 NXT | 0.70 / 0.90 | **0.65** / 0.90 |
| USM | 0.5 | **不做** |
| 星点 | 饱和 0.52、SCNR 0.81、去品红 0.5 | **都不做** |
| 合并 | screen，starsAmount 0.9 | screen，**1.0** |

## 自动化要点

起点不变：WBPP 的彩色主帧（R≈Ha，G/B≈OIII），不需要任何通道拆分或合成。

**线性阶段（`linear`）**
- 裁边：WBPP 的 `integration_autocrop` 已裁过时跳过。没裁过时，现有 `crop_common` 帮不上（它只认值为 0 的空边，叠加不完全重合的边是有数据的，只是帧数少）；可以用 `crop` 的 `pixels`（视频约每边 40 px），或新做一个按边缘噪声/帧数图找边的裁切。必须在板解析之前裁（DynamicCrop 会删掉星图解析结果）。
- 背景：先 `gradient_correction`（存模型图）；模型里出现星云结构时改 `dbe_auto`（需要 `locate_object`，满幅星云 `objectScale` 要大）。手动 DBE 打点无法自动化，视频的 DBE 参数（容差 3.0、阴影松弛 3.0、平滑 0.25、半径 10、每行 10、最小权重 0.75）只作参考。
- 色彩校准：给 `spcc` 加滤镜曲线选项（新增），例如 `"filterCurves": "Opt. L-eXtreme"`：
  - 从 PixInsight 的 `library/filters.xspd` 读 `<Filter name="Sony CMOS R-UVIRcut / Opt. L-eXtreme" channel="R" data="...">` 以及对应的 G、B 条目，设置 SpectrophotometricColorCalibration 的 `redFilterTrCurve`/`redFilterName`、`greenFilterTrCurve`/`greenFilterName`、`blueFilterTrCurve`/`blueFilterName`，`narrowbandMode = false`。`deviceQECurveName` 用 Ideal QE curve，`whiteReferenceName` 用 Average Spiral Galaxy，背景 ROI 用 `find_background` 的框，Gaia DR3/SP（这些参数名都在本机 ColorCalibration 模块里确认过）。
  - 库里 Sony CMOS 的组合有：Antlia-ALP-T、Antlia Triband、Baader UHC-S、Opt. L-eNhance、Opt. L-eXtreme、Opt. L-Ultimate；改机单反用 “Canon Full Spectrum X / …” 条目。传感器族按相机选（Sony 传感器的 ZWO/QHY/ToupTek 彩机用 Sony CMOS）；名字匹配要容忍空格和连字符（库里 Sony 是 `Antlia-ALP-T`，Canon 是 `Antlia ALP-T`）。
  - 库里没有的滤镜：`narrowbandMode = true`，`redFilterWavelength` 656.3，`greenFilterWavelength`/`blueFilterWavelength` 500.7，三个 `*FilterBandwidth` 填滤镜 FWHM（上集 4.5 nm）。FWHM 不知道时（例如 Antlia 四通道）保留 BNCC 兜底。滤镜名从 `session.json` 的 `filter` 字段来。
- `bxt`：默认参数（视频画面上 halos 0.26，没有解释，不必跟）。
- `nxt`：`{"denoise": 0.30, "denoise_color": 0.40, "iterations": 2}`。

**拉伸与去星**
- `stretch`：`{"method": "ez_soft", "targetMedian": 0.24, "expandLow": 0.05, "aggressiveness": 16.3}`（移植版已支持 aggressiveness：累计直方图从 total/10000×aggressiveness 处开始拟合黑点）。
- `sxt`：`{"unscreen": true}`，不变。

**无星图（`starless`），按视频顺序**
1. 红蓝配色（新增蒙版类型）：在 `afWithMask` 里加 `mask: "hue"`，参数 `hue: "blue"`、`maskBlur: 15`。生成方法：PixelMath，`createNewImage` 灰度 f32，`rescale = true`，`symbols = "E1, E2, E3, E4"`，表达式用上面的 BlueMask 原文；再对蒙版执行 PixelMath `gconv($T, 15, 1, 0)`（`rescale` 关，truncate）。σ 15 px 对应 6140 px 宽，其他尺寸按宽度缩放。然后用现有 `curves`：
   `{"op": "curves", "mask": "hue", "hue": "blue", "maskBlur": 15, "channels": {"B": [[0,0],[0.424,0.571],[1,1]], "G": [[0,0],[0.558,0.450],[1,1]]}}`
2. 调色 1，现有 `curves`（L 蒙版就是 `CIEL($T)`，与 ChannelExtraction 亮度相同）：
   `{"op": "curves", "mask": "lum", "maskClip": 0.073, "maskMidtones": 0.5, "channels": {"S": [[0,0],[0.320,0.581],[0.499,0.724],[1,1]], "K": [[0,0],[0.442,0.540],[1,1]], "R": [[0,0],[0.494,0.512],[1,1]], "G": [[0,0],[0.501,0.491],[1,1]]}}`
3. 背景色平衡（扩展 `ht`）：现有 `ht` 只写 RGB/K 一行，要加分通道黑点，例如 `"channelShadows": {"R": 0.00506, "B": 0.00506}`（写进 HT.H 的 R、B 行）。更通用的做法是 `"balance": "background"`：用 `find_background` 框里各通道背景中值 b_c，令 shadows_c = (b_c − min b)/(1 − min b)，把三个通道的背景对齐。视频的数值是目测的，很小。
4. 去绿：现有 `scnr`，`{"op": "scnr", "target": "main", "params": {"amount": 1.0}}`（默认就是 Green、Average Neutral、Preserve lightness）。
5. 调色 2：`{"op": "curves", "mask": "lum", "maskClip": 0, "channels": {"S": [[0,0],[0.382,0.574],[0.468,0.646],[1,1]], "K": [[0,0],[0.514,0.499],[1,1]]}}`
6. `nxt2`：`{"denoise": 0.65, "denoise_color": 0.90, "iterations": 2}`。
7. 压暗背景：现有 `curves` 加反相蒙版，`{"op": "curves", "mask": "inverse_lum", "maskClip": 0, "channels": {"S": [[0,0],[0.532,0.455],[1,1]], "K": [[0,0],[0.556,0.444],[1,1]]}}`
8. 对比度：现有 `ht`，视频值 shadows 0.0658、midtones 0.4228。通用写法：`{"shadows": "auto", "clipFraction": 0.0000015, "midtones": 0.42, "maxShadows": 0.08}`（37 / 6140×4096 ≈ 1.5e-6）。
9. 删掉 `lhe` 和 `usm`（或 `"enabled": false`）。

**星点与合并**
- `stars_color`：视频什么都不做 → `star_sat`、`scnr`、`demagenta` 默认 `"enabled": false`；星点明显发品红时再由 agent 打开。
- `recombine`：`{"mode": "screen", "starsAmount": 1.0}`，即 `~((~main)*(~stars))`。

**说明**
- 曲线的点位都是作者对这张图目测调的，换图要按参考作品判断（主体色度约为同类作品的 0.8–1.2 倍）。视频这张数据质量差，作者自己说以上集为准；非线性阶段可以和上集的数值互相参照。
- 配方要按滤镜分开：双窄带（Ha/OIII）走本期流程；四通道等多波段滤镜仍是 R≈Ha+[NII]+[SII]、G/B≈OIII，流程相同，只是色彩校准要看 SPCC 库里有没有对应曲线。
