# 第6期：多天素材叠加与筛片（PixInsight 进阶教程，BV1cxqpBsEFK，作者：B 站 UP 主氪化金）

素材：M42，黑白相机 ATR2600M（IMX571，6224×4168）+ D60（焦距 280 mm，约 2.77″/px），NINA 拍摄，L/R/G/B 各 300 s，增益 100、偏置 400、制冷 −10 °C。拍了两晚：12-13 晚到 12-14 凌晨、12-14 晚到 12-15 凌晨（所以文件名里有 13/14/15 三个日期），光照帧共 153 张（L 63，R/G/B 各 30）；平场每晚每个滤镜 30 张，都在天亮收摊时拍，两晚曝光不同；暗场 50×300 s、偏置 50 张，2024-12-01 拍（装 H 滤镜、盖镜头盖），两晚共用。视频里的 WBPP 是 2.8.9（本机装的是 2.9.1）。
原始材料（转写、截图，只在本机，不进仓库）：`transcript.txt`、`sheets/`、`frames/`；教程素材在本机 `H:\BaiduYunDownloads\PixInsight资源\进阶篇\第6期 多天素材叠加与筛片\M42\`（24 GB，只读，是没整理过的 LIGHT/FLAT/DARK/BIAS 四个文件夹）。

## 为什么要按晚分开（00:35–03:20）

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 直接导入的结果 | WBPP 左下角 Directory 选 M42 根目录：四类帧和 L/R/G/B 都能自动认出，但两晚被当成同一晚，每个滤镜只有一组 60 张的平场（两晚混在一起） | 00:48–01:24（01:15 截图） |
| 平场必须分晚 | 平场记录的是当晚的光学状态（灰尘、暗角）。换场地、搬设备、构图偏一两度、灰尘被抖动，都会让它变，所以一晚的平场只能校准同一晚的光照帧 | 01:24–02:20 |
| 偏置、暗场可以共用 | 不见光，只要曝光、增益、制冷温度每晚相同，就能跨晚复用 | 02:20–03:20 |

## 整理目录、检查校准帧（03:20–12:02）

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 看图工具 | ZWO 的 ASIFitsView（随 ASIStudio 安装）可以在资源管理器里直接打开 FITS 并按方向键连续翻，比拖进 PI 省事 | 03:20–03:54 |
| 偏置 | 曝光 0 s（最短快门），只记录读出噪声；检查有无漏光、直方图应贴左。拍时装 H 滤镜挡光，文件名里的 H 不代表要按滤镜各拍一份，一份就够 | 03:54–04:54 |
| 暗场 | 与光照帧同为 300 s，H 滤镜 + 镜头盖；检查无漏光 | 04:54–05:24 |
| 光照帧分晚 | 资源管理器按创建时间排序，找时间断开的地方（前一张是收摊前的凌晨 04:2x，后一张已是当晚 20:xx），在这里一分为二；过了零点的帧仍算前一晚（整晚赤道仪没动，光学状态相同）。建 `DATE_12-13/LIGHT`、`DATE_12-14/LIGHT` | 05:24–09:00 |
| 平场分晚 | 平场在天亮收摊时拍：12-14 早上的归 `DATE_12-13/FLAT`，12-15 早上的归 `DATE_12-14/FLAT` | 09:00–10:20 |
| 最终布局 | `M42/BIAS`、`M42/DARK` 放外层共用；`M42/DATE_12-13/{LIGHT,FLAT}`、`M42/DATE_12-14/{LIGHT,FLAT}`。`DATE_` 前缀之后给 WBPP 当分组关键字 | 10:20–10:32（10:35 截图） |
| 平场检查 | 逐张看直方图：均值约半满（16 位三万多）即可，关键是峰整体落在直方图中间；峰贴左（欠曝）或贴右（过曝）的删掉；整组都欠曝就没法补救。屏幕上的两张均值为 35675、32157 | 10:32–12:02（11:05、11:45 截图） |

## 筛片一：肉眼看光照帧（12:02–15:55）

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 看什么 | 放大到能看清星点形状，按住方向键逐张翻：星点圆的留，拖成线的用底部垃圾桶删掉；轻微椭圆（跟踪、大气）要求不高可以留 | 12:02–13:29 |
| 第一晚 | 91 张都没有拖线，全留。有些帧星点明显肥大：拍摄中检测到跑焦后重新自动对焦，留到后面按星点大小筛 | 13:29–13:59 |
| 第二晚 | 后半夜起雾，水汽让星点拖成乱线，这种帧一律删：共删 3 张（12-15 的 L 01:53:56、L 01:59:32、B 01:48:18），62 → 59 | 14:00–15:55（14:45、14:55 截图） |

## 筛片二：SubframeSelector（15:55–22:08）

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 测量 | Process → All Processes → SubframeSelector；Add Files 加入两晚剩下的 150 张光照帧；Routine = Measure Subframes，System Parameters 全默认（Subframe scale 1.0 arcsec/px，所以 FWHM 实际是像素；Camera gain 1.0；16-bit），执行 | 15:55–17:06（16:35 截图） |
| 表达式 | Expressions 窗口的 Approval、Weighting 都空着：150/150 Approved，不自动剔除、不加权 | 17:15 截图 |
| 看哪些指标 | SNR：光污染重、天快亮时明显偏低；FWHM：跑焦；Stars：过云、起雾时骤降。Stars 只能在同一滤镜内比（不同滤镜的星点数本来就不同） | 17:06–19:00、21:40–22:08 |
| 排序 | 表头排序选 FWHM、Descending：最大 4.41（B，第一晚第一张 20:34，高度 25°，Stars 2096），其后 G 4.10、R 3.93、L 3.83……都是第一晚开头、高度 22–29° 的帧；大多数帧在 1.x–2.x | 19:00–20:04（20:05 截图） |
| 对比 | 双击文件名打开，STF 自动拉伸；挑同一滤镜里 FWHM 最小的 B 帧（1.35，12-15 00:55）对比，跨滤镜比会有偏差。第二晚画面方向与第一晚差约 180°，先用 Rotation 转到同一方向。FWHM 小的星点亮而集中，大的虚而弱 | 20:04–21:24（21:15 截图） |
| 结果 | 只演示怎么看，没有再删帧：WBPP 里的帧数等于肉眼筛完的数（B 29、G 30、L 61、R 30），其余好坏交给 WBPP 的权重 | 26:05 截图 |

## WBPP（22:08–27:13）

| 环节 | 做法 | 依据（时间） |
|---|---|---|
| 重置 | Reset：Reset all parameters → to factory-default values，勾 Clear all file lists、Purge cache。下面没特别说明的都是出厂默认 | 22:08–22:31（22:25 截图） |
| 分组关键字 | 右侧 Grouping Keywords 输入 `DATE`（即文件夹前缀）点 +，模式 Pre ✓、Post 不勾；清空文件后重新导入根目录，表里多出 DATE 列，平场、光照帧都分成 12-13、12-14 两组 | 22:31–24:27（23:55 截图） |
| 分组结果 | 平场 8 组，各 30 张（B 0.50/1.10 s，G 0.50/1.40 s，L 0.50/0.42 s，R 1.10/2.60 s，前者 12-13、后者 12-14）；光照帧 8 组（12-13：B 18、G 18、L 37、R 18；12-14：B 11、G 12、L 24、R 12）；偏置、暗场各一组，DATE 为空，服务两晚 | 23:55、24:05 截图 |
| 校准 | Dark Auto、Flat Auto，Optimize Master Dark 不勾；平场只减偏置（没有平场暗），光照帧用暗场 + 平场；Output Pedestal 为 Automatic（Limit 0.00010，表中显示 AUTO 0.01%） | 24:05 截图 |
| Lights 页 | Calibration exposure tolerance 2；Linear Defects Correction 关；Subframe Weighting 开，Weights = PSF Signal Weight；Image Registration 开（Reuse last reference frames 不勾）；**Local Normalization 关**；Image Integration 开，Autocrop ✓、Automatic integration mode ✓；**Astrometric Solution 关**；Registration Reference Image 为 Mode auto | 24:31–25:30（24:35、25:15 截图） |
| 关 LN 的理由 | 不一定提升画质，有时反而变差，因素材而异；而且很耗时 | 24:40–25:00 |
| 关解析的理由 | 做 SPCC 时还要再跑 ImageSolver，WBPP 里解了不一定用得上，白耗时间 | 25:01–25:30 |
| 坏点 | Calibration 页 Cosmetic Correction：Automatic ✓，High sigma **10 → 3**；这只改了选中的那一组，要再点 Apply to all groups，8 组光照帧都变成 AUTO (3) | 25:30–26:00（25:55 截图） |
| Post-Calibration | 两晚按滤镜合成 4 组：B 29 张 2 h 25 min、G 30 张 2 h 30 min、L 61 张 5 h 05 min、R 30 张 2 h 30 min，共 12 h 30 min；Exposure tolerance 2；Drizzle 关（Scale 1、Drop shrink 0.90、Square、Grid 16，均默认）；Fast Integration 关 | 26:02–26:19（26:05 截图） |
| 全局选项 | Detect masters from path、Generate rejection maps、Save groups on exit 勾，其余不勾（默认） | 24:35 截图 |
| 输出与运行 | Output Directory 选素材根目录或新建 `output`；Run 前的诊断提示中间文件需要 56.63 GiB（可用 235.68 GiB），确认空间够再继续 | 26:19–26:46（26:35 截图） |
| 结果 | 跑两个多小时，出 4 张 masterLight（每个滤镜一张），接第3期的黑白 LRGB 后期 | 26:46–27:13 |

视频没有打开 Subframe Weighting、Image Integration 的齿轮设置，剔除算法等都是出厂默认（Automatic integration mode 下由 WBPP 自动选）。

## 和 astroflow 的对照

用教程素材（H: 只读）做了三项实测，结果写在下表里：
- organize 试运行（`scan` + `match_calibration`，不写盘）：分成 2025-12-13（91 张：L 37、R/G/B 各 18）和 2025-12-14（62 张：L 26、R/G/B 各 12）两晚，和视频的分法一样；每晚配到本晚 4 个滤镜的平场（12-13：B/G/L 0.5 s、R 1.1 s；12-14：L 0.425 s、B 1.1 s、G 1.4 s、R 2.6 s）；暗场、偏置两晚相同（2024 年拍的，−10 °C、增益 100/偏置 400 都对得上），没有警告。
- framecheck.measure 测完 153 张（23 s），再按 `_flag` 的规则分别以「全部帧」和「同滤镜帧」为参照打标记。
- 每个（晚, 滤镜）抽 3 张平场，用 frameio.read_luminance 取中位数。

| 环节 | 视频 | astroflow 现在 | 建议 |
|---|---|---|---|
| 分晚 | 按收摊时的时间断档手工分，零点后的帧仍算前一晚；文件夹 `DATE_xx` | organize.read_meta：本地时间（organize.local_time，NINA 读文件名）减 12 h 定夜，实测与视频分法一致 | 保持 |
| 目标名 | — | 两晚的 OBJECT 分别是 `M 42` 和 `m42`。已提交版本的 organize.target_of 只把 `M 42` 改成 `M42`，`m42` 原样留着，两晚会变成名字不同的目标，而 multinight.combine 要求同名 | 工作区里尚未提交的改动已经不分大小写（`M 42`/`m42`/`Messier 42` → `M42`），保留，并用这组 OBJECT 加测试 |
| 平场按晚 + 滤镜 | `DATE` 关键字 Pre：每晚每滤镜一组平场，只校本晚 | organize._flat_for（同相机/尺寸/binning/滤镜，同一晚，增益和曝光不限）；multinight._layout 放进 `Flat/NIGHT_<night>/`；wbpp.wbpp_args 传 `keywords=NIGHT pre` | 保持（等价于视频的 DATE + Pre；WBPP 新加关键字默认就是 Pre） |
| 暗场/偏置共用 | 放外层，不带 DATE，服务两晚 | multinight.SHARABLE + _same_frames：每晚相同就只放一份在 `Dark/`、`Bias/`；organize._dark_for/_bias_for 不看滤镜，所以 FILTER=H 的暗场、偏置也能配上 | 保持 |
| 叠加分组 | Post 不勾：两晚按滤镜合成 4 张 master | `keywords=NIGHT pre` 同样只在校准阶段分晚 | 保持 |
| 平场检查 | 看直方图，均值约半满、峰在中间，偏的删 | 没有这项检查 | 在 organize.match_calibration 的 warnings 里加：每个（晚, 滤镜）抽 2–3 张平场，用 frameio.read_luminance 取中位数（0–1，RAW/FITS 通用），低于约 0.2 或高于约 0.8 时提示偏暗/偏亮。本素材实测 0.46–0.55 |
| 比较范围 | 星点数（看 FWHM 时也是）只和同一滤镜比 | 已提交版本的 framecheck._flag 以全部帧为参照：黑白 LRGB 的 L 天空亮度约是 RGB 的 2.5–3 倍，实测标出 19 张，背景标记全落在 L 上（+176–472%，其实是在和 RGB 比），RGB 帧傍晚的亮背景反而漏掉 | 工作区里尚未提交的 `_peers`（同滤镜同曝光，不足 5 张再放宽）就是视频的做法，保留。按同滤镜实测标出 21 张：两张起雾帧（FWHM 23/34 px，偏心率 0.92/0.99）+ 19 张两晚开头 20:12–21:06 的低空帧（背景亮 +60–197%，或 FWHM 大 +27–57%，后者只在第一晚，正是 SubframeSelector 里 FWHM 排前几名的那批；视频没删它们，交给加权） |
| 漏标的一张 | 删了 L 12-15 01:59:32（星点核心清楚，后面拖着一段淡淡的锯齿） | FWHM 2.83 px 正常，偏心率 0.655 未超限；星点数是 L 中位数的 52%，阈值 FLAG_STARS = 0.5，差一点 | 候选：FLAG_STARS 改 0.6（本素材次低的是 61%，不会多标）。只有这一组数据支持，先用其他目标验证再改 |
| 坏帧怎么处理 | 肉眼删明显坏帧；SubframeSelector 只看不设表达式；其余靠 WBPP 加权 | framecheck 只标记，exclude 移到 `Excluded/Light`（可恢复）；wbpp_args 传 `frameSelectionInteractive=false`，没开 frame selection | 保持；不要在命令行开 `frameSelection.*`（阈值是绝对值，换器材就不通用） |
| 子帧加权 | Subframe Weighting 开，PSF Signal Weight | 没传，用默认（M51 的 WBPP 日志里 `II.weightMode = PSFSignalWeight`） | 结果相同；建议在 wbpp.wbpp_args 显式传 `subframeWeightingEnabled=true`、`subframesWeightsMethod=0`（0 = PSF Signal） |
| Local Normalization | 关（不一定更好，耗时） | wbpp_args 只传 `localNormalizationInteractiveMode=false`，LN 本身用默认 = 开（M51 日志里 LocalNormalization 跑了） | wbpp.wbpp_args 默认加 `localNormalization=false`；需要时用 `extra={"localNormalization": True}` 打开 |
| 板解析 | 关（做 SPCC 时还要再解） | wbpp.wbpp_args 默认 `platesolve=true`（每张 master 在线解 3–4 分钟）。黑白配方在 `crop_common` 之后自己跑 `plate_solve`（裁切会删掉解析结果），WBPP 的解析白做了；彩机配方的 `locate_object` 在色彩校准之前，要用 master 自带的解析 | 黑白多滤镜目标（mono.py 认得出 L/R/G/B）调 wbpp.run 时传 `platesolve=False`，彩机保留；或者给彩机配方在 `locate` 前加 `plate_solve`，然后 WBPP 一律 `platesolve=false` |
| Cosmetic Correction | Automatic，High sigma 3，应用到所有组 | 默认 Automatic、High sigma 10（M51 日志 `IC.cosmeticHighSigma = 10`）。命令行没有这个参数：它存在每个光照组的 ccData 里，自动化模式一开始就清空分组 | 用 WBPP 的事件脚本：wbpp_args 加 `usePipelineScript=true`、`pipelineScriptFile=<新文件 astroflow/pjsr/wbpp_events.js>`，脚本内容 `if (env.event == "pipeline start") engine.applyCCData({enabled: true, highSigma: 3});`（BPP-engine.js 的 applyCCData 作用于全部 pre 光照组，ImageCalibration 执行时才读 ccData）。**未验证**：跑一次确认日志里 `IC.cosmeticHighSigma = 3`，并留意执行缓存会不会沿用旧的校准结果 |
| 参考帧/叠加/裁切/drizzle | 参考帧 auto；Automatic integration mode；Autocrop ✓；Drizzle 关 | 不传参考帧（默认 auto）；`integrate=true`、`autocrop=true`；不开 drizzle | 保持。两晚画面方向不同时，autocrop 只留两晚重合的区域 |
| 没传的参数从哪来 | 视频先重置成出厂默认再改 | wbpp.py 的文档字符串和 `knowledge/pitfalls.md` 写的是沿用上次在 GUI 保存的设置。按本机 WBPP 2.9.1 源码：BPP-main.js 先置 `automationMode` 再调 importParameters，BPP-parameters.js 的 importParameters 在 automationMode 下跳过 setDefaultParameters/loadSettings，而引擎创建时已是出厂默认，所以命令行模式下没传的参数是出厂默认 | 改正这两处说明；配方在意的参数（上面的 LN、加权、解析、CC）都显式传 |
