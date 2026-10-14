# 第4期（上）：黑白相机 HOO 窄带后期（PixInsight 进阶教程，BV1uimABGEEA，作者：B 站 UP 主氪化金）

素材：NGC 6992（东面纱星云），黑白相机（图谱 2600，IMX571）。五个叠加好的线性单通道主帧：H、O（Antlia 4.5 nm 窄带）出星云；R、G、B（Antlia V-Pro 宽带，大月亮下拍，梯度很重）只用来取星点。五张尺寸各不相同（H 6224×4168、O 6179×4107、R/G/B 6201×4149），互相没有对齐。素材在教程资源 `进阶篇/第4期 HOO窄带后期处理/黑白/`。
原始材料（转写、截图，只在本机，不进仓库）：`transcript.txt`、`sheets/`、`frames/`、`keyframes/`。对应配方：暂无（见文末“自动化要点”，建议新配方 `mono_hoo_nebula`）。
视频里用的 PixelMath 色彩蒙版图标（BlueMask、MaskBlur 等）屏幕上没有展开，表达式取自作者的工作模板 `基础篇/第1期 前言与软件环境配置/工作模板/KrAu1440.xpsm` 里的同名图标（Bill Blanshan 的 Simple Color Mask）。

## 线性阶段：HOO 主图

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 准备 | 两张图改名 H、O，便于区分 | 00:58–01:10 |
| 星点对齐 | **StarAlignment**：Reference = H（View），Target = O（Add Views），其余默认（Projective Transformation，Register/Match Images）；配准出的新图替换原 O 并改回 O。两通道旋转角和星位都不同，不对齐无法合成；谁对谁都行 | 01:11–02:31 |
| HOO 合成 | 只有两个通道而彩色需要三个 → O 用两次：**ChannelCombination**，RGB 色彩空间，**R = H，G = O，B = O**。Hα 在红端；OIII 是介于绿和蓝之间的青色，分给 G 和 B 颜色还原较好。**没有用任何归一化脚本**（工作区里有 HOONormalizationV4 图标，本期没用） | 02:32–04:33 |
| 查看 | 关掉锁链自动拉伸（未校色前锁链拉伸会偏色） | 04:36–04:50 |
| 裁切 | 左边缘两通道不重合（可能不同夜拍、设备角度变了）→ **DynamicCrop** 裁到两通道完全重合的区域（裁后 6044×4006） | 04:50–05:23 |
| 旋转 | 构图习惯：**Rotation 180°**（Use fast rotations ✓）。纯审美，不影响处理 | 05:26–05:37 |
| 背景提取 | **GC 默认**：模型四周亮、中间暗，与强拉伸时看到的一致；去除后中间那块暗区被修正 → 效果够好，不做手动 DBE | 06:28–07:22 |
| 色彩校准的原则 | 窄带没有严格意义的色彩校准，但必须做色彩平衡，否则无法看。**HOO 可以照常做 BNCC 或 SPCC**（BNCC 做法与前几期相同，本期只演示 SPCC）；SHO 一般不做色彩校准，用别的方法平衡（第5期） | 07:23–08:31 |
| 板解析 | ImageSolver：FITS 头里的信息正确，直接 OK | 08:31–08:56 |
| SPCC（窄带模式） | 背景参考：左上角没有星云处框一个预览（ROI 322,176，68×58）。**QE curve = Sony IMX411/455/461/533/571**（IMX571）。所用 Antlia SHO 滤镜不在列表里 → 勾 **Narrowband filters mode**，自己填波长和带宽：R **656.30**、G **500.70**、B **500.70** nm（正好对应 HOO，默认值不用改），**三个 Bandwidth 都改成 4.50**（滤镜的带宽）。其余：White reference Average Spiral Galaxy，Gaia DR3/SP，Optimize for stars 不勾，Background Neutralization ✓（−2.80 / +2.00）。校准后开锁链自动拉伸，颜色正常 | 09:09–11:15 |
| 反卷积 | **BXT** 2.0.4（AI4）：Sharpen Stars **0.50**，Adjust Star Halos **0.26**，Automatic PSF ✓，Sharpen Nonstellar **0.50**。O 通道光轴差、星点发方，BXT 修好了大部分（变形太重的地方会留瑕疵） | 11:16–11:48 |
| 线性降噪 | **NXT** AI3，Intensity/color separation ✓：Denoise Color **0.40**（先小一点），Denoise Intensity **0.25**（亮区几乎看不到噪声，暗区明显），Iterations 2 | 11:48–12:25 |
| 小结 | 线性阶段与宽带基本相同，差别只在色彩校准；窄带特有的调色在非线性阶段 | 12:28–12:53 |

## 线性阶段：RGB 星点图

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 为什么换星点 | 窄带星点只剩红、蓝、白几种颜色，恒星本是全光谱，宽带才有五颜六色的星色 → 习惯把星点换成 RGB 宽带拍的 | 12:54–13:54 |
| 对齐 | StarAlignment（先 Reset 清掉上次设置）：Reference = **处理到一半的 HOO**（View），Targets = R、G、B（Add Views）；关掉原图，留配准结果 | 14:13–14:57 |
| 合成 | ChannelCombination RGB，R/G/B 各选对应图，命名 RGB；关锁链查看 | 15:00–15:22 |
| 背景提取 | 月光梯度很重。① GC：模型看着对，但去完左上偏紫、中间偏绿 → 撤销；② SetiAstro **AutomaticDBE**：在星云处挖出一个暗洞 → 撤销；③ **手动 DBE**：星很密，**采样半径改 12**（Resize All），点只打在纯背景上，避开星云和星点（Tolerance 3.000，Shadows relaxation 3.000，Smoothing factor 0.250，Samples per row 10，Minimum sample weight 0.750）；④ 还有一点不平 → **再跑一次 GC**，背景平整 | 15:25–17:49 |
| SPCC（宽带） | ImageSolver → 背景预览（ROI 768,225，67×65）→ SPCC：**不开 Narrowband**，QE 同上，R/G/B 滤镜选 **Antlia V Pro Series R/G/B**（列表里有），其余同上 | 17:49–18:47 |
| 反卷积 | BXT 直接应用，星点更细更圆。**RGB 不做 NXT** | 18:49–19:10 |

## 拉伸与去星

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| HOO 拉伸 | **EZ Soft Stretch** v0.11.3，看预览细调：Target Median **0.25**，Expand Low **0.05**，**Aggressiveness 44.9**（默认 5；试过 0.24 / 55） | 19:11–19:42 |
| RGB 拉伸 | EZ Soft Stretch：Target Median **0.23**（默认 0.20，试过 0.25），Expand Low 0.05，Aggressiveness 5 | 19:43–20:01 |
| RGB 去星 | **SXT** 2.3.11（AI11）：Generate Star Image ✓，Unscreen Stars ✓，Large Overlap ✗。**只要它的星点图**（RGB_stars），无星 RGB 关掉 | 20:02–20:29 |
| HOO 去星 | 整张彩色图直接 SXT 时，一些红色星云被当成星点分走 → 撤销。改为 **ChannelExtraction（RGB）拆成 HOO_R / HOO_G / HOO_B，三张分别 SXT**（同上设置）：G、B 的星点图里几乎没有星云，R 仍带一点（可以接受）。三张无星图再用 **ChannelCombination** 合回，命名 HOO（无星）。HOO 自己的星点图不用 | 20:29–22:35 |

## 非线性阶段（无星 HOO）

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 暗部星云提亮 | **RangeSelection** 蒙版：Lower **0.35**，Upper 1.0，Fuzziness 0，Smoothness **65**，Lightness ✓；盖到 HOO 上后**反相**（亮的主体被保护，暗部露出）。**CT RGB/K**：先在背景亮度处（0.235）打一个固定点，再把暗星云所在亮度抬高。最终点 **(0.23514, 0.23514)、(0.29457, 0.34625)**（试过 0.302→0.496，太猛）。右下的 Hα 细丝更明显 | 22:37–24:06 |
| 结构强化 | 打开 LHE（Kernel Radius 280，Contrast Limit 1.3，Amount 1.0）试了**不用**：面纱星云本身结构丰富，再强化就过头 | 24:08–24:32 |
| HO 配色：红绿 → 红蓝 | 合成后 OIII 偏青绿，红绿搭配看着怪 → 窄带专用的**颜色蒙版调色**（宽带一般不用）。PixelMath 色彩蒙版图标：GreenMask 拖到图上几乎提不出东西，**BlueMask** 提到了 OIII 区域 → 蒙版边缘太硬，用 **MaskBlur** 图标模糊（`gconv` σ 15）→ 蒙版盖到 HOO（**不反相**，作用在 OIII 区）→ **CT：提 B、压 G**。第一遍 B (0.43928→0.55297)、G (0.52972→0.47028)；第二遍 B (0.45220→0.54780)、G (0.53747→0.47028)。B 越高越蓝，按喜好定；喜欢红绿也可以不做 | 24:35–26:55 |
| 饱和度 | 提出 L（HOO_L）做 **L 蒙版**：HT 把暗部切掉（Shadows **0.119**，背景约 26% 像素被裁到 0）→ 盖上 → **CT S 通道**：第一遍两点 (0.41, 0.56)、(0.4935, 0.6434)（先试的 0.32→0.60 让红色过饱和）；第二遍再补一点 (0.4522, 0.5581) | 27:00–27:58 |
| 非线性降噪 | NXT AI3：Denoise Color **0.90**，Denoise Intensity **0.60**，Iterations 2 | 28:01–28:25 |
| 对比度 / 背景色 | **HT**：背景偏红 → 先分通道小幅移动黑点把背景配平（读数 R **0.0101**、G **0.0051**、B **0.0203**；要缓，移多了整图偏色），再在 RGB/K 把黑点拉到 **0.0405**（裁 0.0001% 像素，中间调 0.5），背景更暗、主体更突出 | 28:28–29:13 |
| 锐化 | **不做**：BXT 之后已经够锐，再锐化会过头 | 29:14–29:23 |

## 星点与合并

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 星点调色 | RGB_stars：**CT S 通道**提饱和（两点 (0.30, 0.567)、(0.496, 0.739)），不用太高；不做 SCNR | 29:32–29:53 |
| 合并 | PixelMath **`~((~HOO)*(~RGB_stars))`**，Replace target image | 29:53–30:11 |
| 收尾 | 合并后背景略黄 → HT 再微调：R 黑点 **0.0127**、G 黑点 **0.0076**、B 中间调 **0.4911**，背景色更平衡 | 30:13–30:37 |
| 没拍 RGB 时 | 直接用 HOO 自己的星点，省掉整个换星流程 | 30:50–31:09 |

## 与前几期的不同
- **对比第1期（彩机宽带）**：起点是两张没对齐的单通道 → 先对齐、合成（H→R，O→G+B）、裁到重合区；SPCC 用**窄带模式**（谱线波长 + 滤镜带宽），不用宽带滤镜曲线；多了一张 **RGB 星点图**（单独去梯度、校色、BXT、拉伸、去星，只留星点）；HOO 去星时**逐通道 SXT**；非线性阶段**不做 LHE、不做 USM**，多了**色彩蒙版把 OIII 从青绿调成蓝**、**分通道 HT 配平背景**；EZ 拉伸更猛（中值 0.25，Aggressiveness 44.9，第1期 0.20 / 5）；星点不做 SCNR。
- **对比第3期（黑白 LRGB）**：对齐方式相同，但参考图是 H，合成前只裁 H/O 的重合区，RGB 后来对齐到已裁好的 HOO 上；没有 L，也没有 LRGBCombination，BXT/NXT 直接做在合成后的彩色 HOO 上；背景是**合成后**在彩色图上去（第3期每个通道单独去）；色彩校准用 SPCC 窄带模式（第3期 BNCC）。
- 相同的部分：先 BXT 后 NXT，线性降噪温和、非线性降噪较强；L 蒙版 + S 曲线提饱和；screen 合并星点。

## 自动化要点

建议新配方 `mono_hoo_nebula`：起点 `master:H` + `master:O`，`master:R/G/B` 可选（有就换 RGB 星点，没有就用 HOO 自己的星点）。`mono.masters` 已能认出 H/O；`default_recipe` 要先看 H+O（无 S），再看 R/G/B，否则有 R/G/B 时会误选 LRGB 配方。

**channels（10_hoo + 10_rgb）**
- 对齐：现有 `align_channels`，`reference: "main"`（H），`windows: ["main", "O", "R", "G", "B"]`（有 RGB 就一起配准到 H；视频是后来对齐到 HOO，几何结果相同）。
- 裁切：现有 `crop_common`，同一组窗口，`margin: 4`。视频只裁 H/O 重合区；把 R/G/B 也算进去可避免星点图边上出现无星条带。
- 旋转 180° 是构图喜好，不自动做；需要时可加一个 `rotate` op（Rotation：`angle` 180，`optimizeFast` true），放在板解析之前（裁切、旋转都会删除星图解析结果）。
- 板解析/定位：现有 `plate_solve`（target main）、`locate_object`。
- HOO 合成：扩展现有 `combine_rgb`：`{"red": "main", "green": "O", "blue": "O", "lum": null, "solution": "main"}`，即 PixelMath 三个表达式 `<H id>` / `<O id>` / `<O id>`（`useSingleExpression` false，新建 RGB 图，`rescale` false）。要改的地方：同一窗口出现两次时只关闭一次；`lum: null` 时不生成平均 L；加 `output` 参数（默认 main），以便 R/G/B 合成到另一个窗口。
- RGB 合成：`{"op": "combine_rgb", "red": "R", "green": "G", "blue": "B", "lum": null, "output": "RGB", "solution": "main"}`。
- 背景：HOO 用现有 `gradient_correction`（默认）。RGB：视频里 GC 单独失败、ADBE 在星云处挖洞、手动 DBE + GC 成功 → 用现有 `dbe_auto`（target "RGB"，degree 2，`objectScale` 1.6–1.8，避开星云）后再 `gradient_correction`。
- 输出：main → `10_hoo`，`outputs: {"RGB": "10_rgb"}`（stage 的 `outputs` 要支持任意窗口名）。

**color（11_hoo + 11_rgb）**
- 两张图已配准，`find_background` 找到的背景框对两张都适用。
- HOO：现有 `color_calibration`，`spcc` 子参数（SPCC 进程参数名已核对）：`narrowbandMode` true，`narrowbandOptimizeStars` false，`redFilterWavelength` 656.3，`redFilterBandwidth` = Hα 带宽，`greenFilterWavelength` 500.7，`greenFilterBandwidth` = OIII 带宽，`blueFilterWavelength` 500.7，`blueFilterBandwidth` = OIII 带宽；背景 ROI 由现有 `spcc` op 按背景框设置。带宽不能写死成视频的 4.5：新增 `mono.bandwidth(filter_name)` 从滤镜名读（如 `Ha 7nm` → 7.0），读不到就用设置项。QE 曲线：只改 `deviceQECurveName` 不会换曲线，要连同 `deviceQECurve` 数据一起从 SPCC 的滤镜库取（视频 `Sony IMX411/455/461/533/571`）；拿不到就保持默认 Ideal QE。SPCC 失败时退回 BNCC（现有逻辑）。
- HOO 的 BXT/NXT：现有 `bxt`，`params: {"sharpen_stars": 0.50, "adjust_halos": 0.26, "sharpen_nonstellar": 0.50}`（视频读数，现有配方用 BXT 默认）；现有 `nxt`，`{"denoise": 0.25, "denoise_color": 0.40, "iterations": 2}`。
- RGB：`color_calibration`（target "RGB"）。宽带 SPCC 需要所用滤镜的曲线（`redFilterName`/`redFilterTrCurve` 等，滤镜因人而异），默认 `method: "bncc"`，只用来定星色，足够。然后 `bxt`（同上）。RGB 不做 NXT。

**stretch（20_hoo + 20_rgb）**
- 现有 `stretch`：HOO `{"method": "ez_soft", "targetMedian": 0.25, "expandLow": 0.05, "aggressiveness": 44.9}`；RGB `{"target": "RGB", "method": "ez_soft", "targetMedian": 0.23, "expandLow": 0.05, "aggressiveness": 5}`。`AF.ezSoftStretch` 里 aggressiveness 决定黑点拟合从累计直方图的哪一段开始（44.9 → 黑点更高，背景更暗）。

**stars（30_starless + 31_stars）**
- 新 op `sxt_channels`（或给 `sxt` 加 `perChannel: true`）：ChannelExtraction（`colorSpace` RGB，`sampleFormat` SameAsSource）拆成三张 → 每张 StarXTerminator（`stars` true，`unscreen` true，`overlap` 0.20）→ 三张无星图用 PixelMath 三个表达式（`<R无星>` / `<G无星>` / `<B无星>`）合回 main；三张星点图同样合成 `stars`（screen 是逐通道运算，合起来就是 HOO 的星点图，没拍 RGB 时直接用它）。
- 有 RGB 时：现有 `sxt`（target "RGB"，unscreen true）→ 它的星点图替换 `stars`（现有 `sxt` 会关掉旧 stars 窗口），再关掉无星的 RGB 窗口（`sxt` 加 `keep: "stars"` 参数，或加一个 `close` op）。

**starless（40_starless_final）**
- 暗部提亮：现有 `curves` + 现有蒙版 `mask: "inverse_range"`（`rangeLow` 0.35，`rangeHigh` 1.0，`rangeFuzziness` 0，`rangeSmoothness` 65），`channels: {"K": [[0,0],[s,s],[s+0.059,s+0.111],[1,1]]}`，s = 天空背景中值（视频 s = 0.235，点 (0.29457, 0.34625)）。需要给 `curves` 加 `relativeTo: "sky"`：点坐标按背景框中值平移，因为固定点必须落在本图的背景亮度上。
- LHE：`{"op": "lhe", "enabled": false, "params": {"radius": 280, "slopeLimit": 1.3, "amount": 1.0}}`；结构丰富的目标（如面纱）不做，由 agent 看图决定是否打开。
- OIII 调蓝：给 `afWithMask` 加蒙版类型 `mask: "color"`，参数 `maskColor`（"blue"，可选 red/yellow/green/cyan/magenta），`maskStrength`（E2，默认 1.0），`maskBlur`（默认 15）。做法：PixelMath 在主图上新建灰度图（`createNewImage` true，`newImageColorSpace` Gray，`rescale` true，`useSingleExpression` true，`symbols` "E1,E2,E3,E4,E5"），BlueMask 表达式（色度蒙版，E1 = 0）：
  `E1=0; E2=1.0; E3=iif(CIEh($T)<0.5,0,iif(CIEh($T)<=(2/3),~mtf((CIEh($T)-0.5)/(1/6),~E2)*CIEc($T),iif(CIEh($T)<=(5/6),~mtf(((5/6)-CIEh($T))/(1/6),~E2)*CIEc($T),0))); E3`
  E2 = 1 时就是：色相在 0.5–5/6 的像素取 CIE c（色度），其余为 0，再 rescale 到 0–1。其他颜色只换色相窗口（CIEh 0–1）：红 5/6–1/6（峰 0），黄 0–1/3（峰 1/6），绿 1/6–1/2（峰 1/3），青 1/3–2/3（峰 1/2），蓝 1/2–5/6（峰 2/3），品红 2/3–1（峰 5/6）。再在蒙版窗口上执行 MaskBlur：PixelMath `gconv($T, 15, 1, 0)`（σ 15，aspect 1，角度 0，替换原图）。蒙版不反相。然后两步现有 `curves`：第一步 `{"B": [[0,0],[0.43928,0.55297],[1,1]], "G": [[0,0],[0.52972,0.47028],[1,1]]}`，第二步 `{"B": [[0,0],[0.45220,0.54780],[1,1]], "G": [[0,0],[0.53747,0.47028],[1,1]]}`。蓝色蒙版几乎为空时（OIII 色相落在青区）改用 "cyan"，由 agent 看蒙版覆盖率决定。
- 饱和度：现有 `saturation`，`mask: "lum"`，`maskClip` 0.12，`maskMidtones` 0.5（视频只切黑点，没动中间调；op 默认是 0.3），两步：`boost` 0.65、0.60（视频的 S 曲线在 x = 0.5 处约 0.65 和 0.60）。要完全照视频可用 `curves` 的 S 通道：`[[0,0],[0.41,0.56],[0.4935,0.6434],[1,1]]`，再 `[[0,0],[0.4522,0.5581],[1,1]]`。
- 降噪：现有 `nxt`，`{"denoise": 0.60, "denoise_color": 0.90, "iterations": 2}`。
- 背景配平 + 对比度：给 `ht` 加 `channelShadows: "sky"`：按背景框量出每个通道的天空中值 m_k，取 t = min(m_k)，通道黑点 c_k = (m_k − t)/(1 − t)，写进 HT 的 R/G/B 行（视频手调结果 R 0.0101、G 0.0051、B 0.0203）；K 行黑点视频为 0.0405（只裁 0.0001% 像素），用现有 `shadows: "auto"` 配 `clipFraction` 0.000001，`midtones` 0.5。
- USM：`enabled: false`。

**stars_color（41_stars_final）**
- 现有 `saturation`，`mask: false`，`boost` 0.74（视频两点 (0.30, 0.567)、(0.496, 0.739)）。视频没做 SCNR（RGB 星点已校色）→ 不放 `scnr`。

**combine（50_final）**
- 现有 `recombine`，`mode: "screen"`，`starsAmount` 1.0，即 `~((~main)*(~stars))`（视频 `~((~HOO)*(~RGB_stars))`）。
- 合并后再做一次背景配平：`ht` + `channelShadows: "sky"`（视频手调：R 黑点 0.0127、G 黑点 0.0076、B 中间调 0.4911）。

**不在本期用到的图标**：工作区里的 HOONormalizationV4、RGBstars_to_NB（都是 Bill Blanshan 的 PixelMath）本期都没用；合成就是普通的 ChannelCombination，星点就是普通的 screen 合并。
