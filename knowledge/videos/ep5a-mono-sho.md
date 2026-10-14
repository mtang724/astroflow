# 第5期（上）：黑白相机 SHO 哈勃色后期（PixInsight 进阶教程，BV1vD2CBcEg8，作者：B 站 UP 主氪化金）

素材：M16 鹰状星云（创生之柱），黑白相机窄带，三张已叠加的单通道线性主帧 `H.xisf`（5893×3764）、`S.xisf`、`O.xisf`（均 5986×3804）。没有 FITS 关键字，三张尺寸和旋转角都不同（不同时间拍的）；曝光时间短，信噪比偏低，外圈暗星云尤其差。素材在教程资源 `进阶篇/第5期 SHO哈勃色后期处理/黑白/`。
原始材料（转写、截图，只在本机，不进仓库）：`knowledge/videos/ep5a-mono-sho/` 下的 `transcript.txt`、`sheets/`、`frames/`、`keyframes/`。下集（彩色相机 SHO，双窄带 HO+SO）见 `ep5b-osc-sho.md`。

00:00–04:07 是原理：SHO = **S→R、H→G、O→B**。SII（672.4 nm）和 Hα（656.3 nm）在可见光里都是红色，分不开，所以把 Hα 挪到绿通道、靠颜色区分；SHO 是伪彩色。这个排列是哈勃团队最早用的，色调公认好看，别的排列（HSO、OSH…）也能做。05:35–06:19：Hα 几乎总是最强的信号，放进 G 之后整张图天然**偏绿**，所以 SHO 的调色比其他类型都复杂。

## 线性阶段

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 星点对齐 | **StarAlignment**：参考图 = **H**（View，选哪个通道都行），目标 = S、O（Add Views），Projective Transformation，Register/Match Images，其余默认。删掉对齐前的 S、O，把配准结果改回 **S / O**（去掉后缀） | 04:10–05:03 |
| 裁切 | 视频**没有裁切**，成品仍是参考图 H 的 5893×3764 | — |
| 通道合成 | **ChannelCombination**，RGB：**R = S，G = H，B = O**，Inherit astrometric solution ✓ → 关 STF 锁链拉伸看；关掉三张单通道，图改名 **SHO** | 05:03–06:31 |
| 背景提取 | 强拉伸看梯度：左下偏亮、右上偏暗 → **GC 默认参数**，模型与观察一致，结果可用。整张彩色图做一次（不像第3期每个通道分别做） | 06:31–07:16 |
| 为什么不用 SPCC | SHO 是伪彩色，没有“正确”的颜色；SPCC 会把星点校成白色、背景校成中性灰，结果整张图发绿（打开过 SPCC 对话框演示，未执行）。但仍需要白平衡，平衡的对象是**星云**三个通道的强度 → 用 **BNCC** | 07:18–09:14 |
| 背景选区 | 脚本 **FindBackground 1.2.2**（Gerrit Erdt / Franklin Marek）：Full Image，Standard deviation 过滤，Fast search，Size 50，Spacing rate 2，Search grid width 100，Number of starting points 40 → 点 Search，生成预览 **Background** | 09:14–09:40 |
| BN | BackgroundNeutralization：参考 = SHO→Background；背景读数约 0.001 级 → Upper limit **0.002**，Lower 0，Rescale as needed（目标背景 0.001） | 09:41–10:08 |
| CC | ColorCalibration：**白参考 = 星云主体中最亮、信噪比高的一块**（Preview02，ROI Left **2272**、Top **1276**、**1436×1104**，不框外圈暗区），白参考上限 0.9，**Structure Detection 关**；背景参考 = Background，上限 **0.002**。不能用星点当白参考：星点变白、整图发绿（做法与第2期星系的 BNCC 类似） | 10:10–11:38 |
| CC 后 | 锁链 STF 下不再整体发绿，已带一点哈勃色味道；**星点变成紫色是正常的**（星云平衡后星点必然偏紫） | 11:38–12:07 |
| 反卷积 | **BXT**（屏幕：Sharpen Stars 0.50，Adjust Star Halos **0.26**，Automatic PSF ✓，Sharpen Nonstellar 0.50，Correct Only 不勾，Luminance Only 不勾）。拍摄时有风，星点轻微拉线，BXT 修得回来；柱子顶端也变清楚 | 12:08–12:42 |
| 线性降噪 | **NXT AI3**，Intensity/color separation ✓：彩噪 **0.40**（线性阶段不要高），明度 **0.30**（曝光短、信噪比差），Iterations 2 | 12:44–13:20 |
| **线性去星** | 这份素材没拍 RGB 星点，星点要靠脚本转色，所以**在拉伸前去星**：**SXT**，Generate Star Image ✓，**Unscreen Stars 不勾**，Large Overlap ✓。得到线性的紫色星点图（先最小化，最后处理）和线性的无星图。线性去星的难点是之后星点单独拉伸的力度不好控制 | 13:22–14:47 |

## 非线性阶段（无星图）

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 拉伸 | **EZ Soft Stretch**：Target Median **0.23**，Expand Low **0.05**，Zero in White Point 不勾，Aggressiveness **46.6**（对话框里先后出现过 37.0、5.00，执行时为 46.6）。拉完是偏黄绿褐的整体色调 | 14:49–15:06 |
| HDR | 中间太亮、和周围对比太大 → **EZ HDR** v0.1.1：HDR Blend **0.30**，HDR Layers **5**（默认）；删掉它生成的两个蒙版。柱子本体不再过曝（喜欢中心亮的可以不做） | 15:09–16:04 |
| 暗部拉伸 | **不做**：外圈暗区信噪比太差，拉起来噪声会爆 | 16:09–16:30 |
| 结构强化 | **LHE**：Kernel Radius **164**，Contrast Limit **1.3**，Amount **0.760**，8-bit，Circular ✓，不加蒙版（局部放大预览调内核和力度） | 16:30–17:20 |
| L 蒙版 | 提出亮度图，**HT 黑点 0.16455696**（midtones 0.5）切掉暗部，避免周围噪声被一起提饱和；盖到图上，确认露出的是有信号的中间部分，关掉蒙版显示 | 17:23–17:52 |
| 第一遍调色（L 蒙版） | **CT**：S 曲线**大幅提高**（屏幕量得约 0.1→0.21、0.2→0.40、0.3→0.55、0.5→0.72、0.8→0.91）；仍偏绿 → **G 压低**约 0.05（0.3→0.25、0.7→0.65）；R 稍提约 +0.02（点 0.491→0.514），B 几乎不动（点 0.496→0.501），RGB/K 稍压暗约 −0.03（点 0.514→0.481）。目标是让中间主体三通道强度平衡，外圈暗区不强求。应用后 Reset | 17:52–19:12 |
| 对比度（L 蒙版） | CT **RGB/K**：暗部拉低、亮部拉高，拉过头后往回收；终值约 (0.27→0.23)、(0.718→0.708)，量得 0.3→0.26、0.5→0.47、0.7→0.69。之后删掉 L 蒙版 | 19:18–19:57 |
| 分色调色的思路 | 平衡后能看出橙、黄、蓝、紫、红多种颜色；SHO 好看的关键是这些颜色**平缓的彩虹过渡**。下一步按颜色分别调 | 20:00–20:35 |
| 黄色区 | 作者的 PixelMath 图标 **YellowMask**（Simple Yellow Color Mask，表达式见下）拖到图上 → 生成灰度蒙版 → **MaskBlur** 图标模糊一次（蒙版太硬）→ 盖到 SHO 上 → **CT**：**G 压低**（黄 = 红 + 绿，压绿让黄偏红/更暖）约 −0.035，**R 提高**（终点 0.48579→0.51680），S 提高（0.5→0.65；量得 0.2→0.30、0.3→0.43、0.7→0.82）。调色没有标准答案，不难看就行 | 20:37–22:06 |
| 蓝色区 | **BlueMask** 图标 → MaskBlur → 盖上 → 放大看核心（蓝色集中在中心）→ **CT**：**B 提高**约 +0.05（0.5→0.55），**G 压低**约 −0.03（压绿会让蓝更偏紫：绿和品红互补），R 几乎不动（点 0.49612→0.50388），S 提高（0.5→0.66；量得 0.2→0.34、0.3→0.47、0.7→0.81） | 22:09–23:23 |
| 其他颜色 | 图标里还有 Red/Green/Cyan/MagentaMask，作者没用，课后自己试 | 23:23–23:40 |
| 全局对比度 | 不加蒙版，CT **RGB/K** S 形：屏幕点 (0.3876→0.2713) 等，量得 0.1→0.06、0.2→0.12、0.3→0.20、0.4→0.29、0.5→0.42、0.6→0.55、0.7→0.68、0.8→0.80、0.9→0.91。经验：饱和度不变时对比度越高看起来越艳，动对比度后如果饱和度被带偏要回头再调 | 23:41–25:20 |
| 取舍 | 高对比把外圈暗星云压没了：那部分全是噪声，保住中间高信噪比的主体反而更好看 | 25:23–25:45 |
| 非线性降噪 | **NXT**：彩噪 **0.90**，明度 **0.60**（噪声明显），Iterations 2 | 25:46–26:18 |
| 锐化 | **不做 USM**：中间细节已经够 | 26:19–26:26 |
| 背景去红 | 背景明显偏红（直方图上 R 超出 G、B）→ **HT 只选 R 通道**，Shadows **0.01265823**（Midtones 0.5）；只动背景的红，不能拉多，否则主体偏色 | 26:26–27:00 |

YellowMask / BlueMask 图标的 PixelMath（控制台截图，单表达式，Create new image，灰度，执行时 Rescale 到 [0,1]）。E1 = 0 选色度蒙版（乘 CIEc），= 1 选亮度蒙版（乘 CIEL）；E2 = 蒙版强度，1.0 时 `~mtf(…, ~E2)` 在色相窗内恒为 1，蒙版 = 色相窗 × 色度。

```
//  Simple Yellow Color Mask
E1= 0   ;//  Chrominance Mask= 0, Lightness Mask= 1
E2= 1.0 ;//  Mask Strength (Range= 0 to 1)
//Equations:
E3= iif(CIEh($T)<0,0,iif(CIEh($T)<=(1/6),
~mtf((CIEh($T)-0)/(1/6),~E2)*
CIEc($T),iif(CIEh($T)<=(1/3),~mtf(((1/3)-
CIEh($T))/(1/6),~E2)*CIEc($T),0)));
E4= iif(CIEh($T)<0,0,iif(CIEh($T)<=(1/6),
~mtf((CIEh($T)-0)/(1/6),~E2)*
CIEL($T),iif(CIEh($T)<=(1/3),~mtf(((1/3)-
CIEh($T))/(1/6),~E2)*CIEL($T),0)));
iif(E1==0,E3,E4)
```

```
//  Simple Blue Color Mask
E1= 0   ;//  Chrominance Mask= 0, Lightness Mask= 1
E2= 1.0 ;//  Mask Strength (Range= 0 to 1)
//Equations:
E3= iif(CIEh($T)<0.5,0,iif(CIEh($T)<=(2/3),
~mtf((CIEh($T)-0.5)/(1/6),~E2)*
CIEc($T),iif(CIEh($T)<=(5/6),~mtf(((5/6)-
CIEh($T))/(1/6),~E2)*CIEc($T),0)));
E4= iif(CIEh($T)<0.5,0,iif(CIEh($T)<=(2/3),
~mtf((CIEh($T)-0.5)/(1/6),~E2)*
CIEL($T),iif(CIEh($T)<=(5/6),~mtf(((5/6)-
CIEh($T))/(1/6),~E2)*CIEL($T),0)));
iif(E1==0,E3,E4)
```

即黄色窗 CIE h ∈ [0, 1/3]（0°–120°，峰值 60°），蓝色窗 [1/2, 5/6]（180°–300°，峰值 240°）；与 `ColorMask` 脚本的同名预设相同。**MaskBlur** 图标视频里没打开；作者图标集（`knowledge/pi_icon_set_from_M42_project.txt`）里是 `gconv($T, 15, 1, 0)`（sigma 15 px）。

## 星点（线性星点 → 宽带色 → 单独拉伸）

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 拆通道 | 线性星点图 SHO_stars 做 **ChannelExtraction**（RGB）→ SHO_stars_R / _G / _B | 27:02–27:50 |
| 转宽带色 | 脚本 **SetiAstro → NB to RGB Star Combination**（NBtoRGBStars v1.6，Franklin Marek）：**Ha Stars = SHO_stars_G**，**OIII Stars = SHO_stars_B**，**SII Stars = SHO_stars_R**（按 SHO 的通道分配），OSC 不选，Green Channel Blend Ratio 不勾，Apply Star Stretch 不勾，Show Preview 不勾 → Execute → 新图 **NBtoRGB_stars**（接近白色的星点），删掉三张单通道 | 27:50–28:24 |
| 拉伸 | 自动 STF 太猛不能用 → **HT RGB/K** 手动：Midtones **0.03544304**（黑点 0、白点 1）应用两次，再用 **0.29620253** 补一次；参照物是 SHO_stars 在线性阶段的 STF 预览（星点不要拉得那么密） | 28:24–29:31 |
| 饱和度 | **CT S 曲线**提一次，让星点有些颜色 | 29:32–29:47 |
| 合并 | 图标 **StarRemake**（PixelMath）：`~((~SHO)*(~NBtoRGB_stars))`，Replace target image，应用到 SHO | 29:50–30:16 |
| 回调 | 合并后星点太亮太大 → 撤销合并，星点图撤回到较弱的拉伸，重新提饱和（CT S：终点 0.48579→0.66150，量得 0.2→0.35、0.3→0.49、0.5→0.68、0.7→0.82），再合并。星点大小靠 HT 力度控制 | 30:16–30:50 |
| 提醒 | 脚本算出来的星点颜色和真正拍的 RGB 星点差别很大，只是没时间拍 RGB 星点时的替代；有条件就拍 RGB 星点替换（第4期的做法） | 30:50–31:59 |

以前几期都在拉伸后去星（非线性去星），星点不用单独拉伸；本期因为要在线性阶段把窄带星点转色，才改为线性去星，代价就是上面这一步不好控制。

成品（30:55 截图，1:3 局部，按屏幕像素粗算 HSV）：有色像素里橙色（色相 15°–40°）约 74%，红 16%，金黄 5%，蓝 5%（核心），**绿约 0**；亮部平均饱和度约 0.43；背景深棕偏中性。

## 和前几期的区别

| 方面 | 第3期（黑白 LRGB） | 第4期上（黑白 HOO） | 本期（黑白 SHO） |
|---|---|---|---|
| 通道 → RGB | L + R/G/B，LRGBCombination | H→R，O→G 和 B（颜色大致合乎可见光） | **S→R，H→G，O→B**（伪彩色，合成后整体偏绿） |
| 对齐/裁切 | StarAlignment 到 L，裁到公共区 | StarAlignment 到 H，裁到重合区，旋转 180° | StarAlignment 到 H，**未裁切** |
| 去背景 | 每个通道分别做（ADBE / GC） | 合成后 GC | 合成后 GC |
| 色彩校准 | BNCC（SPCC 需滤镜曲线） | **SPCC 窄带模式**（656.3/500.7/500.7 nm + 带宽） | **SPCC 作废，只能 BNCC**；白参考 = 星云亮区，关结构检测 |
| BXT / NXT | 只对 L（NXT 0.25 / 彩噪 0） | 对 HOO（NXT 0.25 / 0.40） | 对 SHO（NXT 0.30 / 0.40） |
| 去星 | 非线性 SXT | 非线性、HOO 逐通道 SXT；星点换成 **RGB 宽带星点** | **线性 SXT（Unscreen 关）**；没拍 RGB → 星点用 NBtoRGBStars 转色、HT 单独拉伸 |
| 拉伸 | EZ 0.24 + L 匹配亮度 | EZ 0.25（Aggressiveness 44.9） | EZ 0.23（Aggressiveness 46.6）+ **EZ HDR** |
| 结构 | LHE 512 / 1.3 / 1.0（范围蒙版） | 试了 LHE 不用；反相范围蒙版提暗部 | LHE 164 / 1.3 / 0.76；暗部不提（信噪比差） |
| 调色 | L 蒙版 CT 提饱和 | BlueMask + MaskBlur → CT 提 B 压 G（OIII 青绿变蓝）；L 蒙版 S 曲线 | L 蒙版先**压 G 平衡三通道** + 大幅提 S → 对比度 → **YellowMask 区压 G 提 R**、**BlueMask 区提 B 压 G** → 全局 S 形对比 |
| 背景色 | — | HT 分通道黑点配平背景 | HT **只调 R 通道黑点**去背景偏红 |

共同点：先 BXT 后 NXT；非线性 NXT 彩噪 0.90；不做 USM；星点 screen 合并。和第4期相比，本期的调色量大得多：HOO 只需把 OIII 调蓝，SHO 要先把 Hα 的绿压掉，再把 S/H 混合区推向金橙、O 区推向蓝。

## 自动化要点

**1. 输入与配方选择**
- `mono.py` 已能把滤镜名认成 `H`/`O`/`S`（工作区里的未提交改动）。黑白目标同时有 S、H、O 主帧时选新配方 **`mono_sho_nebula`**；只有 H、O 时走第4期的 `mono_hoo_nebula`。另有 R/G/B 主帧时星点优先换成 RGB 星点（视频建议，做法同第4期），没有才走下面的脚本转色。`default_recipe` 的判断顺序：S+H+O → SHO，H+O → HOO，再看 R/G/B。
- 教程素材没有 FITS 关键字，测试时用 `state.json` 的 `masters: {"H": ..., "S": ..., "O": ...}`（`mono.masters(recorded)` 现在过滤 `CHANNELS`，H/O/S 已包含）。三张尺寸不同，必须配准。
- `objects`/参考作品：SHO 目标的参考组用 SHO 作品，不要拿宽带作品比较颜色。

**2. `channels` 阶段（一次 PixInsight）**
- input `master:H`（`main`，视频的参考图），aux `S: master:S`、`O: master:O`。
- `align_channels`：`reference: "main"`，`windows: ["main","S","O"]`（StarAlignment，Projective，Register/Match；现有 op）。配准后 S、O 变成 H 的 5893×3764。
- `crop_common`：`windows: ["main","S","O"]`，margin 4。视频没裁，但配准留下的空边会干扰 GC 和 BN，自动化应该裁。
- `combine_rgb`：`red: "S"`，`green: "main"`，`blue: "O"`，**新参数 `lum: null`**（与 `ep4a-mono-hoo.md` 的提法一致）：不生成三通道平均的 L 窗口（现在没有 L 就会自动生成）。对应 PixelMath：R=`S`，G=`H`，B=`O`，Create new image，RGB，f32，不 rescale。
- `plate_solve`、`locate_object`（optional，裁切后再解；CC 白参考框和色彩指标要用到天体位置）。

**3. `linear` 阶段**
- `find_background` → `gradient_correction`（默认参数）→ `find_background`。
- `color_calibration`，**`method: "bncc"` 必须固定**（`color_calibration` 默认先试 SPCC，SHO 不能用）；`bncc: {"whiteROI": ..., "structureDetection": false}`。视频的白参考是星云中心最亮的一块（约占画面 24%×29%），不是整个天体。现有 `whiteROI: "object"` 对 M16 这类大星云会把外圈噪声区也框进去 → 建议加 **`whiteROI: "bright"`**：在平滑后的亮度图上取最亮的连续区域（如 > 第 90 百分位的像素外接框，限制在 `object` 框内），没解析时也能用。BN/CC 上限视频为 0.002/0.002，现有按背景框统计计算即可。
- `bxt`：默认（视频屏幕上 Adjust Star Halos 是 0.26，不是 RC 默认 0；先用默认，留作可调参数）。
- `nxt`：`{"denoise": 0.30, "denoise_color": 0.40, "iterations": 2}`。
- **线性去星**：`sxt` `unscreen: false`，`largeOverlap: true`；stage 加 `stars_output: "12_stars_linear"`（线性星点）。现有配方都在 `stars` 阶段对 `20_stretched` 去星，这里要把去星挪进 `linear`，并去掉后面的 `stars` 阶段（ep5b 彩机配方同样需要）。

**4. `stretch` 阶段**（input `10_linear` = 线性无星图，aux `stars: 12_stars_linear`；输出 `20_stretched` 和 `outputs: {"stars": "21_stars"}`）
- 先对 `stars` 做下面第 5 条的 `nb_stars_rgb`，再拉伸，这样星点能和无星图用同一条曲线。
- `stretch` `ez_soft`：`targetMedian` **0.23**，`expandLow` 0.05，`aggressiveness` **46.6**。移植版默认 5，这个值只决定估计黑点时跳过多少暗像素；EZ 新版（视频里对话框出现过 5.00、37.0、46.6，下集 87.3）是否同一刻度、同一含义没核实，要拿素材对一次（对比视频拉伸后的中值/黑点与移植版输出）。
- `hdr`：`layers` 5，`amount` 0.30（现有 op，第2期参数相同）。

**5. 星点：转色、拉伸、提饱和**（转色和拉伸在 `stretch` 阶段，提饱和在 `stars_color` 阶段，输入 `21_stars`）
- **新 op `nb_stars_rgb`**：复刻 SetiAstro NBtoRGBStars（本机装的是 v1.4，视频是 v1.6，公式要对照 v1.6 确认）。SHO 星点图：Ha = `$T[1]`，OIII = `$T[2]`，SII = `$T[0]`；`haToOiiRatio` 0.3（不勾 Green Channel Blend Ratio 时的默认）：
  - PixelMath（三表达式，不 rescale，truncate）：R `0.5*$T[1] + 0.5*$T[0]`；G `0.3*$T[1] + ~0.3*$T[2]`；B `$T[2]`
  - SCNR（Green，Average Neutral，Amount 1.00，Preserve lightness）→ PixelMath `mtf(0.01, $T)` → SCNR（同上）→ PixelMath `mtf(~0.01, $T)`
  - 参数 `ha`/`oiii`/`sii` 给通道号，没有 SII 时 R 用 Ha（HOO 也能用）。
- 拉伸：视频用 HT midtones 0.0354 两次（第三次 0.296 后来撤回了一部分，见下）。自动化不靠目测：建议用 `stretch` 的 `alsoOn: ["stars"]`（彗星配方已有）把无星图的同一条曲线用到星点上，再加 `starsScale`（< 1 时减弱）控制星点大小；视频的两次 0.0354 作为可选覆盖（新增 `ht` 对 `stars` 窗口执行、`passes: 2`）。
- `saturation`：`target: "stars"`，`mask: false`，`boost` **0.68**（S 曲线 0.5→0.68）；不再 SCNR（脚本里做过两次）。
- `recombine`：`mode: "screen"`（即 `~((~main)*(~stars))`，与视频 StarRemake 相同），`starsAmount` 1.0；视频觉得星点偏大，`starsAmount` 0.8–0.9 或减弱星点拉伸可作为默认微调。

**6. `starless` 阶段：把偏绿的 SHO 调成金/蓝**（顺序按视频）
1. `lhe`：`{"radius": 164, "slopeLimit": 1.3, "amount": 0.76}`，无蒙版（大星云可用 `radius: "auto"` 配 `radiusMax: 164`）。
2. 三通道平衡（L 蒙版）：现有 `saturation` 可表达：`mask: "lum"`，`maskClip` **0.165**，`maskMidtones` **0.5**（视频的 L 蒙版只切黑点，不提亮），`boost` **0.72**，`rgb: {"R": 0.02, "G": -0.05, "B": 0.005}`；外加 `curves` K `[[0,0],[0.514,0.481],[1,1]]`（同一蒙版）。注意现有 `saturation` 只在 x=0.5 放一个点，视频的 S 曲线在暗端抬得更多（0.1→0.21、0.2→0.40），如要贴近可直接用 `curves` 写 S：`[[0,0],[0.1,0.21],[0.2,0.40],[0.3,0.55],[0.5,0.72],[0.8,0.905],[1,1]]`。
3. 对比度（同一 L 蒙版）：`curves` K `[[0,0],[0.27,0.23],[0.718,0.708],[1,1]]`。
4. **新蒙版类型：色彩蒙版**（与 `ep4a-mono-hoo.md` 同一个 op，命名沿用那边）：`afWithMask` 增加 `mask: "color"`，参数 `maskColor`（预设名）、`maskStrength`（E2，默认 1.0）、`maskBlur`（默认 15），可选 `hueRange: [lo, hi]`（CIE h，0–1，自定义色相窗）和 `maskMode: "chroma"|"lightness"`（E1，默认 chroma）。实现：PixelMath（Create new image，Gray，f32，**rescale ✓**）用上面 YellowMask 的结构，把 `0`、`1/6`、`1/3` 换成 `lo`、`(lo+hi)/2`、`hi`（跨 0 的范围如红色 300°–60° 按 `ColorMask` 脚本拆成两段）；再 PixelMath `gconv($T, 15, 1, 0)` 模糊；预设 `yellow` = [0, 1/3]，`blue` = [1/2, 5/6]，另备 red [5/6, 1/6]、green [1/6, 1/2]、cyan [1/3, 2/3]、magenta [2/3, 1]。
5. 黄区：`curves` + `mask: "color"`, `maskColor: "yellow"`：R `[[0,0],[0.486,0.517],[1,1]]`，G `[[0,0],[0.5,0.465],[1,1]]`，S `[[0,0],[0.2,0.30],[0.3,0.43],[0.5,0.65],[0.7,0.82],[1,1]]`。效果：外圈从黄绿变金橙。
6. 蓝区：`curves` + `mask: "color"`, `maskColor: "blue"`：B `[[0,0],[0.5,0.55],[1,1]]`，G `[[0,0],[0.5,0.47],[1,1]]`，R `[[0,0],[0.496,0.504],[1,1]]`，S `[[0,0],[0.2,0.335],[0.3,0.467],[0.5,0.66],[0.7,0.807],[1,1]]`。效果：核心蓝色更纯、偏一点紫。
7. 全局对比度（无蒙版）：`curves` K `[[0,0],[0.2,0.116],[0.3876,0.2713],[0.6,0.55],[0.8,0.795],[1,1]]`。
8. `nxt`：`{"denoise": 0.60, "denoise_color": 0.90, "iterations": 2}`。
9. `usm`：`enabled: false`。
10. **背景去红**：`ht` 现在只写 RGB/K 行。视频只把 **R 通道**黑点设为 **0.0127**。用 `ep4a-mono-hoo.md` 提的 `channelShadows: "sky"` 实现：在 `find_background` 框里量各通道天空中值 m_k，t = min(m_k)，通道黑点 c_k = (m_k − t)/(1 − t) 写进 HT 的 R/G/B 行（本期只有 R 偏高，结果等同只调 R）；RGB/K 行不动，midtones 0.5。
- 曲线数值是从视频截图的曲线像素量出来的近似值（±0.01），反映方向和幅度；视频本身是目测调的，素材不同时应交给 agent 按成品指标微调。建议的检查指标（`metrics.py`）：星云区**绿色色相（65°–160°）占比接近 0**；金橙（15°–65°）为主、核心有蓝（195°–250°）；背景 R/G/B 中值差 < 0.005；主体饱和度与参考 SHO 作品相当（偏好见用户记忆：0.8–1.2 倍）。
- 可选替代（视频没用）：作者图标里还有 `SHONormalizationV3`（Bill Blanshan 的 SHO 归一化 PixelMath）和 `ModifiedSCNR_v4`，也是把 SHO 从偏绿调成金蓝的常见做法；先按视频的色彩蒙版方案实现，归一化留作以后的比较项。

**7. 测试**
- 用教程的 H/S/O 三张主帧（作为 recorded masters，不拷贝）跑全流程：S、O 配准到 H 后偏移 0、公共区接近 5893×3764；CC 前合成图明显偏绿（G = Hα 最强），CC 后锁链 STF 不再偏绿、星点偏紫；成品绿色占比约 0、外圈金橙、核心蓝、星点接近白色、背景不偏红。
- 星点：NBtoRGB 后星点的 R/G/B 中值应接近（白色），screen 合并后星点大小不明显大于原图（与线性星点图的 STF 预览对比）。

视频里没读到或不确定的值：GC 对话框没展示（按默认）；MaskBlur 的 sigma 没在视频里显示（取作者图标集的 15）；星点回调时撤回到哪一步看不清（屏幕先后出现 0.0354 两次和 0.296 一次，最终大概是去掉了 0.296 那一次）；各 CT 曲线只有部分点的数值显示在屏幕上，其余是按曲线像素量的。
