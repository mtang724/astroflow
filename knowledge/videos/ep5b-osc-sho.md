# 第5期（下）：彩色相机 SHO 哈勃色后期（PixInsight 进阶教程，BV1vD2CBcEg8，作者：B 站 UP 主氪化金）

素材：玫瑰星云（FITS 头 OBJECT = C 50），ZWO ASI2600MC Pro，焦距约 531 mm，单张 300 s。两块 6 nm 双窄带滤镜各拍一晚：**HO**（Hα+OIII，2025-11-29）和 **SO**（SII+OIII，2025-11-30），各自叠成一张已解拜耳的 RGB 主帧 `HO.xisf` / `SO.xisf`（6248×4176，RGGB）。两张的 FILTER 都是 `NoFilter`，**文件本身分不出哪张是哪块滤镜**。素材在教程资源 `进阶篇/第5期 SHO哈勃色后期处理/彩色/`。
原始材料（转写、截图，只在本机，不进仓库）：`knowledge/videos/ep5b-osc-sho/` 下的 `transcript.txt`、`sheets/`、`frames/`、`keyframes/`。上集（黑白相机 SHO，M16）见 `ep5a-mono-sho.md`。

彩色相机拍 SHO 必须用两块双窄带（一块 HO、一块 SO），只有一块 HO 双窄带只能做 HOO（见第4期下）。

## 原理：两张彩色主帧里各通道装的是什么（02:02–03:57）

拜耳阵列 RGGB：SII（约 672 nm）和 Hα（656.3 nm）都是红光，只落在 R 像素；OIII（500.7 nm）是青色，同时落在 G 和 B 像素。

| 主帧 | R 通道 | G 通道 | B 通道 |
|---|---|---|---|
| HO（Hα+OIII 双窄带） | **Hα** | OIII | OIII |
| SO（SII+OIII 双窄带） | **SII** | OIII | OIII |

所以：H 只来自 HO 的 R，S 只来自 SO 的 R，O 有四份（两张图的 G 和 B）。

## 前段：对齐、拆通道、重组（彩色相机独有）

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 改名 | 两张主帧默认叫 Integration，改成 **HO** 和 **SO** | 01:20–01:30 |
| 星点对齐 | 两晚拍的，位置不重合 → **StarAlignment**：参考图 = **HO**（View），目标 = **SO**（Add Views 只勾 SO），Projective Transformation，Register/Match Images，其余默认。参考选哪张都行。删掉原 SO，把配准结果改名回 SO | 01:31–02:00 |
| 拆 HO | **ChannelExtraction**（RGB）→ HO_R / HO_G / HO_B；HO_R 改名 **HO_H** | 04:06–04:47 |
| HO 的 O | G、B 两份 OIII 分布几乎一样 → **PixelMath** `(HO_G+HO_B)/2`，Create new image，Image Id **HO_O**，Rescale 不勾；删 HO_G、HO_B、HO | 04:48–05:33 |
| 拆 SO | 同上：SO_R 改名 **SO_S**；PixelMath `(SO_G+SO_B)/2` → 新图 **SO_O**；删 SO_G、SO_B、SO | 05:39–06:29 |
| 合并两份 O | PixelMath `(HO_O+SO_O)/2` → 新图 **O**（两块滤镜都拍到了 OIII，平均后得到完整的 O） | 06:29–07:05 |
| 整理 | 剩下三张单通道改名 **S / H / O**，从这里起和黑白相机的素材一样 | 07:08–07:36 |
| 通道合成 | **ChannelCombination**，RGB：**R = S，G = H，B = O**，Inherit astrometric solution ✓；关掉 STF 锁链看 | 08:27–08:36 |

和黑白相机的区别只在前面这几步（拆通道、合并 O）；彩色相机效率更低，而且要两块双窄带。

## 线性阶段（之后流程与上集相同，讲得较快）

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 裁切 | 左边有两晚叠加不重合的边 → **DynamicCrop** 只留完全重合区（6248×4176 → **6181×4029**） | 08:38–08:51 |
| 构图 | **Rotation 180°**（作者觉得原方向倒置，个人喜好） | 08:51–09:02 |
| 背景提取 | 低光害 + 6 nm 窄带，几乎没梯度，可不做；作者仍做了：**DBE 手动 8 个点**（每块区域点几个），Tolerance **3.0**，Shadows relaxation **3.0**，Smoothing **0.25**，样本半径 19，Subtract。模型显示只去掉了很少一点 | 09:03–09:43 |
| BN | 背景处建 Preview01 → BackgroundNeutralization，参考 = Preview01；背景读数最大约 0.003 → Upper limit **0.005**（0.004–0.005 均可），Rescale as needed | 09:44–10:08 |
| CC | ColorCalibration：**白参考 = 星云主体**（Preview02，ROI 1668, 904, 2156×2032），**Structure Detection 关**，白参考上限 0.9；背景参考 = Preview01，上限 **0.001**（背景约 0.0002）。控制台白平衡系数 **R 4.79 / G 1.00 / B 3.77**：Hα 远强于 SII、OIII，CC 在星云上把三通道拉平。做完不再发绿，星点偏紫（同上集） | 10:11–10:54 |
| 反卷积 | **BXT** 直接做（屏幕：Sharpen Stars 0.50，Adjust Star Halos 0.26，Sharpen Nonstellar 0.50，Automatic PSF ✓） | 11:01–11:06 |
| 线性降噪 | **NXT AI3**，Intensity/color separation ✓：彩噪 **0.40**，明度 **0.25**（噪声稍多），Iterations 2 | 11:07–11:28 |
| 线性去星 | **SXT**：Generate Star Image ✓，**Unscreen 不勾**，Large Overlap ✓；星点图（线性，紫色）先最小化，最后再处理 | 11:30–11:43 |
| 拉伸 | **EZ Soft Stretch**（v0.11.3）只拉无星图：Target Median **0.25**，Expand Low **0.05**（控制台：实际目标 0.20 = 0.25 − 0.05），屏幕 Aggressiveness 87.3 | 11:44–11:50 |

## 非线性阶段（无星图）

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 结构强化 | **LHE**：Kernel Radius 280 → **222**，Contrast Limit **1.3**，Amount 1.0 → **0.82**，8-bit，Circular ✓，不加蒙版 | 11:51–12:08 |
| 去绿 + 提饱和 | 还偏绿 → 提 **L 蒙版**（CIE L，HT 黑点 **0.142** 切掉暗部，应用到蒙版）盖到图上 → **CT**：先把 **S 曲线大幅提高**（约 0.32→0.59、0.44→0.70）才看得出哪个通道多，再**压 G**（约 0.535→0.470）。拉一遍不够再压一次 G（0.525→0.473） | 12:10–13:04 |
| 对比度 | 关掉蒙版、全局：RGB/K 轻 S 形曲线两次（第一次高端 0.63→0.71；第二次 0.32→0.28、0.65→0.69） | 13:05–13:36 |
| 外圈金边 | **YellowMask**（作者的 PixelMath 图标，Simple Yellow Color Mask，见下）生成黄色蒙版 → **MaskBlur** 图标模糊 → 盖上 → CT：**R 提高**（约 0.44→0.58，保持黄橙色调，不推到纯红）、G 微调（0.475→0.535 后又回 0.514→0.496）、S 稍提（0.486→0.525） | 13:38–14:25 |
| 全局色调（L 蒙版） | 换回 L 蒙版做全局微调：亮度 RGB/K 0.424→0.566；R 0.465→0.535；S 0.357→0.607；B 0.587→0.439；G 0.519→0.486；R 0.499→0.519（屏幕上依次出现的点，按效果目测，没有固定规则） | 14:26–16:16 |
| 全局对比 | 删掉所有蒙版，RGB/K 曲线压暗部（0.29→0.26 一带）、中间稍压（0.55→0.52），S 再微调 | 16:17–16:45 |
| 非线性降噪 | 拉伸和调色后噪声明显 → **NXT AI3**：明度 **0.65**，彩噪 **0.90**，Iterations 2 | 16:59–17:27 |
| 背景去红 | 背景发红 → **HT 只调 R 通道**黑点 0.0177 → **0.0405**，背景变中性灰 | 17:28–17:43 |
| 对比度 | HT RGB/K：黑点约 **0.035**，Midtones 约 **0.487** | 17:44–18:00 |

YellowMask 图标的 PixelMath（控制台显示，单表达式，Create new image，Gray，Rescale ✓）：

```
E1= 0   ;//  Chrominance Mask= 0, Lightness Mask= 1
E2= 1.0 ;//  Mask Strength (Range= 0 to 1)
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
（Symbols：E1–E5。MaskBlur 图标在作者图标集里是 `gconv($T, 15, 1, 0)`，见 `knowledge/pi_icon_set_from_M42_project.txt`；视频里没打开看 sigma。）

## 星点（线性星点 → 宽带色）

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 拆通道 | 线性星点图 Image13_stars 做 ChannelExtraction → stars_R / stars_G / stars_B | 18:06–18:17 |
| 转宽带色 | 脚本 **SetiAstro → NB to RGB Star Combination**（v1.6）：**Ha = stars_G，OIII = stars_B，SII = stars_R**（SHO 合成里 G=H、B=O、R=S）；不选 OSC 图像，Green Channel Blend Ratio 不勾，Apply Star Stretch 不勾 → 新图 NBtoRGB_stars。脚本内部：PixelMath 合成 → SCNR → `mtf(0.01, $T)` → SCNR → `mtf(~0.01, $T)` | 18:17–18:36 |
| 拉伸 | 星点仍是线性 → **HT 两次**：Midtones **0.04303797**，再 **0.34430380**（黑点 0、白点 1，按星点大小亮度目测） | 18:38–18:58 |
| 饱和度 | CT 的 S 曲线提高（如 0.54→0.75） | 18:59–19:04 |
| 合并 | PixelMath 应用到无星图（Replace target）：`~((~Image13)*(~NBtoRGB_stars))`，之后删掉星点图 | 19:05–19:22 |

成品（19:28）：外圈金橙、内部蓝紫、背景中性深灰、星点接近白色。

## 和上集（黑白相机 SHO）的区别

| 方面 | 上集（黑白 SHO） | 本集（彩色 SHO） |
|---|---|---|
| 主帧 | 三张单通道：S、H、O 各一张 | 两张 RGB：HO（Hα+OIII 双窄带）、SO（SII+OIII 双窄带） |
| 对齐 | StarAlignment 把 S、O 配准到 H | StarAlignment 把 **SO 配准到 HO**（拆通道之前做，六个通道一起对齐） |
| 得到 S/H/O | 主帧本身就是 | **H = HO 的 R；S = SO 的 R；O = (HO_G+HO_B)/2 与 (SO_G+SO_B)/2 再平均** |
| 合成 | ChannelCombination R=S、G=H、B=O | 相同 |
| 信噪比 | 每个通道用满全部像素 | S、H 只来自 1/4 的 R 像素，O 有两晚数据，S 最弱（CC 把 R 放大约 4.8 倍，后面要更强的降噪） |
| 之后 | GC → BNCC → BXT → NXT → 线性去星 → EZ → EZ HDR → 调色 … | 同一套；本素材梯度极小改用手动 DBE，多了裁切和旋转，没做 EZ HDR，星点同样用 NB to RGB 脚本 |

## 自动化要点

**1. App 必须知道、但文件里没有的信息**
- 哪张主帧是 HO 双窄带、哪张是 SO 双窄带。两张都是 `FILTER=NoFilter`，文件名只是作者手改的。来源：导入时每晚记录的滤镜（`In Processing/<night>/session.json` 的 `filter`），要能表示"彩机 + Hα/OIII 双窄带"和"彩机 + SII/OIII 双窄带"两类（如 `filter_class`: `osc_dualband_ho` / `osc_dualband_so`，或记录 `bands: ["Ha","OIII"]` / `["SII","OIII"]`）。用滤镜轮、NINA 等把滤镜名写进 FILTER 的，再用别名表（类似 `mono.channel()`）把名字映射到 HO / SO；认不出时问用户，不要猜。
- 每张主帧 R 通道是哪条线（HO→Hα，SO→SII），G/B 都是 OIII。这由滤镜类别决定，不由文件决定。

**2. 叠加必须把两套滤镜分开**
- 现在的多晚合并（`multinight`，`keywords=NIGHT pre`）只按晚校准、**所有晚一起积分**，会把 HO 晚和 SO 晚叠成一张，结果作废。WBPP 也不会按 FILTER 分开（两者都是 NoFilter）。
- 做法：按滤镜类别分组，每组一张主帧。两种实现：(a) 每套滤镜各建一个合并目标、各跑一次 WBPP；(b) 一个目标里加路径关键字（如 `Light/BAND_HO/NIGHT_x/`、`Light/BAND_SO/NIGHT_y/`，和 NIGHT 一样从路径读），积分阶段也按 BAND 分组（WBPP 关键字用于 post 或两阶段都用，命令行写法待验证），主帧名里带上 BAND。平场同理：同一晚换过滤镜时，平场也要按 BAND 配。
- 结果记成 `state.json` 的 `masters: {"HO": ..., "SO": ...}`（现在 `mono.masters()` 只认 L/R/G/B，要扩展或另写 `dualband.masters()`）。WBPP 的 autocrop 对两张主帧各裁各的，尺寸不同，所以配方里仍要配准（和视频一样）。
- 只有 HO 主帧时走第4期下的 HOO 配方；HO 和 SO 都有时选下面的新配方（`objects.recipe_for` 按 filter_class 增加分支）。参考作品分组用 SHO 作品（`filters.md` 里"彩机做不出 SII"那条只适用于四通道多波段滤镜）。

**3. 新配方 `osc_dualband_sho`（各阶段 = 一次 PixInsight）**
- `channels`：input `master:HO`（main），aux `SO: master:SO`
  1. `align_channels`：reference `"main"`，windows `["main","SO"]`（已有，RGB 窗口可用，需测试）。
  2. **新 op `dualband_split`**（或通用的 `pixelmath_new`：PixelMath Create new image，Gray，f32，Rescale 关，新窗口登记进 ctx.win，之后关闭源窗口）：
     - `S` = `SO[0]`
     - `H` = `main[0]`
     - `O` = `((main[1]+main[2])/2 + (SO[1]+SO[2])/2)/2`（即视频的 `(HO_G+HO_B)/2`、`(SO_G+SO_B)/2`、`(HO_O+SO_O)/2`）
     - 关闭 `main` 和 `SO`（否则 `combine_rgb` 新建的 `main` 会和旧窗口重名）。可选参数（视频没做）：合并前用 LinearFit 把 SO 的 O 对齐到 HO 的 O（两晚天光、透明度不同）。
  3. `crop_common`：windows `["S","H","O"]`，margin 4（代替手动 DynamicCrop）。
  4. `combine_rgb`：red `"S"`，green `"H"`，blue `"O"`；加参数 `lum: false`，不生成平均 L（此配方用不到）。
  5. `plate_solve`（裁切会删解析结果，所以裁完再解）→ `locate_object`（optional）。
  旋转 180° 只是作者个人构图，不进配方。
- `linear`：`find_background` → `gradient_correction`（上集用 GC；本素材梯度极小，视频的手动 8 点 DBE 等价于极低阶模型；也可用 `dbe_auto` degree 1–2）→ `find_background` → `color_calibration` `method: "bncc"`，`bncc: {"whiteROI": "object", "structureDetection": false}`（视频：BN 上限 0.005，CC 背景上限 0.001，白参考上限 0.9；现有按背景框统计算上限即可）→ `bxt`（默认）→ `nxt` `{"denoise": 0.25, "denoise_color": 0.40, "iterations": 2}` → `sxt` `unscreen: false`（**线性去星**；stage 加 `stars_output`，星点保持线性）。
- `stars_rgb`（新阶段，输入线性星点）：**新 op `nb_stars_rgb`**，复刻 SetiAstro NB to RGB Star Combination（本机装的是 v1.4，视频是 v1.6，公式待对照 v1.6）。SHO 星点图的通道：Ha = `$T[1]`，OIII = `$T[2]`，SII = `$T[0]`；参数 `haToOiiRatio` 默认 0.3：
  - PixelMath（三表达式，不 rescale）：R `0.5*$T[1] + 0.5*$T[0]`；G `0.3*$T[1] + ~0.3*$T[2]`；B `$T[2]`
  - SCNR（Green，Average Neutral，Amount 1.00，Preserve lightness）→ PixelMath `mtf(0.01, $T)` → SCNR（同上）→ PixelMath `mtf(~0.01, $T)`
  - 参数 `ha`/`oiii`/`sii` 指定通道号，这样 HOO 星点（无 SII 时 R 用 Ha）也能用。
- `stretch`：`ez_soft`，`targetMedian` **0.25**，`expandLow` 0.05（视频 EZ v0.11.3 的 Aggressiveness 显示 87.3，和移植版的 5 刻度不同，先用移植版默认）。星点：视频用 HT 两次 midtones 0.043 → 0.344（目测）。建议默认用 `stretch` 的 `alsoOn: ["stars"]`（彗星配方已有）把无星图的同一条拉伸用到线性星点上，星点亮度和星云一致、不靠目测；视频数值作为可选覆盖（`ht` 对 stars 窗口跑两次）。
- `starless`：
  - `lhe` `{"radius": 222, "slopeLimit": 1.3, "amount": 0.82}`，无蒙版（大星云用固定值，或 `auto` 配 `radiusMax: 222`）。
  - `saturation`：`mask: "lum"`，`maskClip` 0.14，`boost` 约 0.74（视频 S 曲线 0.44→0.70），`rgb: {"G": -0.065}`；再一遍只压 G（`boost` 0.5，`rgb: {"G": -0.05}`）。
  - `curves`（无蒙版）对比度：K `[[0,0],[0.32,0.28],[0.65,0.69],[1,1]]`。
  - **新蒙版类型 `hue`**（`afWithMask` 增加 `mask: "yellow"` 等，用上面 YellowMask 的 PixelMath，E1=0、E2=1.0，Rescale ✓，再 `gconv($T, 15, 1, 0)` 模糊），配 `curves` R `[[0,0],[0.44,0.58],[1,1]]`、S `[[0,0],[0.486,0.525],[1,1]]`：SHO 外圈金边变暖。
  - 视频 14:26–16:45 的连串目测微调（亮度、R/B/G、S）不写死，交给 agent 按成品和参考作品调（亮度可用 `curves` K、饱和度用 `saturation`）。
  - `nxt` `{"denoise": 0.65, "denoise_color": 0.90, "iterations": 2}`。
  - **背景中性**：视频只拉高 R 的黑点（0.0405）去掉背景偏红。`ht` 现在只改 RGB/K 行，需要加 `channel: "R"`（写 HT.H 第 0 行），更通用的是加 `neutralizeSky: true`：每个通道各取黑点，让三个通道的天空中值相等。
  - `ht` RGB/K：`shadows` 约 0.035（或 `"sky"`），`midtones` 0.487。
- `stars_color`：`saturation` `mask: false`，`boost` 约 0.72（视频 S 0.54→0.75）；不再 SCNR（脚本里已做两次）。
- `combine`：`recombine` `mode: "screen"`，表达式 `~((~main)*(~stars))`，与视频 `~((~Image13)*(~NBtoRGB_stars))` 相同。

**4. 测试**
- 用教程的 `HO.xisf` / `SO.xisf`（作为 recorded masters，不拷贝）跑全流程：检查 SO 配准到 HO 后偏移为 0、公共区约 6181×4029、CC 系数量级与视频相近（R 约 ×4.8，B 约 ×3.8）、成品外圈金橙内部蓝、背景中性。
- HO/SO 标反时 S 和 H 互换，CC 前的合成图会以 R 为主而不是 G。可做成一条检查：CC 前星云区域 G（Hα）应明显强于 R（SII，本素材 CC 系数 R ≈ 4.8 倍于 G），反过来就提示用户两张主帧可能标反。
