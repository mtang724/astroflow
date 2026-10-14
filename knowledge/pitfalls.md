# 坑与经验（无界面 PixInsight / 本机环境）

- **一次只运行一个 PixInsight 实例**。第二个实例（`-n`）用设置槽 2（`%APPDATA%\Pleiades\core-002-pxi.settings`），里面没有 GUI 里配好的 Gaia DR3/SP 路径 → SPCC 直接失败；BlurXTerminator 在第二个实例里会访问冲突崩溃。`astroflow/pi.py` 用锁串行化，并在检测到用户打开的 PixInsight 时等待（最多 1 小时）。
- WBPP 命令行自动化：`WBPP.js,automationMode=true,dir=...,outputDirectory=...`。只传 Light/Dark/Bias/Flat 子目录（传整个目标目录会把 `_thn.jpg` 缩略图当图像读进去）。自动化模式不读 PixInsight 里保存的 WBPP 设置，未指定的参数一律是 WBPP 出厂默认值（2.9.1 源码 BPP-parameters.js：只有非自动化模式才 loadSettings）。astroflow 显式传：PSF Signal 权重、不做 Local Normalization（第6期：慢且不一定更好）、autocrop。
- WBPP 的 platesolve 用 ImageSolver：本机只有 **Gaia DR3/SP**（SPCC 用），ImageSolver 本地模式只认 Gaia DR3/EDR3/DR2 天体测量库 → 退回在线 VizieR（每个 master 约 3–4 分钟，偶尔更久）。两个 master（原始 + autocrop）都会解析。
- **DynamicCrop 会删除星图解析结果**（"Existing astrometric solution will be deleted"）。SPCC 前不要裁剪；用 WBPP 的 `_autocrop` master（已解析）。无界面下它还会弹确认框把实例卡住 → `crop` 步骤必须 `noGUIMessages = true`（已设置）。
- **模态对话框 = 无界面实例卡死**。参数非法（NaN）、确认框都会让进程空转到超时（曾卡 3 小时）。`pi.py` 的看门狗：CPU 空闲超过 idle_limit（流水线 10 分钟，WBPP 30 分钟，因为在线解析时会空闲等网络）或超时就结束进程，并在错误里列出当时打开的窗口标题（如 `['DynamicCrop', 'PixInsight']`）。有 `noGUIMessages` 参数的进程都要设为 true。
- AdP ImageSolver 作为库 include 时，要先 `#define TITLE`、`SETTINGS_MODULE`，并 include `pjsr/DataType/StdButton/StdIcon/UndoFlag/TextAlign` 头文件（同 AperturePhotometry.js 的写法），否则加载时报错并卡在错误框。
- `UndoFlag_NoSwapFile` 等常量来自 `<pjsr/UndoFlag.jsh>`，未 include 时运行到才报错。
- 无界面运行看不到控制台：runner 用 `console.beginLog()/endLog()` 把控制台写到 `.runs/<job>/console.txt`，出错先看它。
- RC 工具 `executeOn` 失败时不抛异常只返回 false → steps.js 检查返回值并报错。
- 预览：色彩校准前用 unlinked STF（彩机原始数据绿色偏多，linked 会整片发绿）；校准后用 linked 才能看出偏色。
- `organize.py`：暗场/偏置按 FITS 头 SET-TEMP 匹配（±1°C 容差，精确匹配优先），不信文件夹名（本机 Bias Library 的 -5degree 与 0degree 文件夹名是反的）。
- 视频转写：faster-whisper large-v3 在 4090 上 28 分钟视频约 1–2 分钟；PyAV 版本与 faster-whisper 不兼容 → 直接传 numpy 波形。
