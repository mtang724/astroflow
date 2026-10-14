"""English messages of the backend (astroflow.i18n). A tuple is (singular, plural), chosen by the value n."""

MESSAGES = {
    # punctuation used to join lists
    "、": ", ",
    "，": ", ",

    # importing (organize)
    "随数据": "with the data",
    "校准帧库": "calibration library",
    "目标已有": "already in the target",
    "多处": "several places",
    "增益 {gain}": "gain {gain}",
    "这台相机": "this camera",
    "新目标": "New target",
    "补全已有目标": "Completes a target",
    "加入校准帧库": "To the calibration library",
    "{n} 个文件读不了：{files}": ("{n} file could not be read: {files}", "{n} files could not be read: {files}"),
    "{n} 个文件看不出是光照帧还是校准帧（文件头没有 IMAGETYP，文件名和文件夹名也看不出）：{files}": (
        ("{n} file is neither recognisably a light nor a calibration frame (no IMAGETYP in its header, nothing in its "
         "file or folder name): {files}"),
        ("{n} files are neither recognisably lights nor calibration frames (no IMAGETYP in their headers, nothing in "
         "their file or folder names): {files}")),
    "跳过了 {n} 张 ASIAIR 预览图（Preview_*）": ("Skipped {n} ASIAIR preview (Preview_*)",
                                         "Skipped {n} ASIAIR previews (Preview_*)"),
    "平场和光照帧的旋转角度不同：光照帧 {lights}，平场 {flats}":
        "Flats and lights were taken at different rotator angles: lights {lights}, flats {flats}",
    "没有找到可用的图像（FITS 或相机 RAW 文件）": "No usable images found (FITS or camera RAW files)",
    "缺少暗场：{need}": "No darks: {need}",
    "缺少偏置：{need}": "No bias: {need}",
    "导入的文件夹里有 {frames} 没有用上（没有和它们相配的光照帧）":
        "Not used from the imported folder: {frames} (no lights they match)",
    "{kind}：{target}  {night}  -> {dest}  （要复制 {n} 个文件）": (
        "{kind}: {target}  {night}  -> {dest}  ({n} file to copy)",
        "{kind}: {target}  {night}  -> {dest}  ({n} files to copy)"),
    "光照帧": "Lights",
    "暗场": "Darks",
    "偏置": "Bias",
    "平场": "Flats",
    "（注意）{note}": "(Note) {note}",
    "暗场 {dark} °C，光照帧 {light} °C（在 {tolerance} °C 容差内）":
        "Darks at {dark} °C, lights at {light} °C (within the {tolerance} °C tolerance)",
    "缺少这一晚的平场：{night}，滤镜 {filter}": "No flats from this night: {night}, filter {filter}",
    "缺少这一晚的平场：{night}": "No flats from this night: {night}",
    "相机没有记录温度，暗场是 {night} 拍的，不是同一晚，可能不完全匹配":
        "The camera records no temperature and the darks were shot on {night}, another night: they may not match "
        "exactly",

    # checking single frames
    "读不了这一帧：{error}": "Cannot read this frame: {error}",
    "星点只有其他帧的 {share}（云、雾或结露）": "Only {share} of the stars the other frames have (clouds, haze or dew)",
    "星点比其他帧大 {more}（跑焦、视宁度差或有风）": "Stars {more} larger than in the other frames (focus, seeing or wind)",
    "星点被拉长（跟踪不准或有风）": "Elongated stars (tracking or wind)",
    "背景比其他帧亮 {more}（月光、云或天亮）": "Sky {more} brighter than in the other frames (moon, clouds or dawn)",

    # processing everything, jobs
    "已完成": "Finished",
    "已出图": "Processed",
    "认不出是什么天体，先在“处理流程”里选配方": "Unknown object: choose a recipe under “Processing” first",
    "已合并进多晚目标，处理合并的那个": "Part of a multi-night target: that one is processed",
    "没有光照帧": "No light frames",
    "正在处理": "Being processed",
    "叠加": "stack",
    "彗星叠加": "comet stack",
    "处理": "process",
    "数据根目录": "Data folder",
    "导入 {what}": "Import {what}",
    "{target}: 单帧检查": "{target}: frame check",
    "{target}: 合并 {n} 晚": ("{target}: combine {n} night", "{target}: combine {n} nights"),
    "清理 {target}": "Free space: {target}",
    "清理 {n} 个目标": ("Free space: {n} target", "Free space: {n} targets"),
    "{target}: 归档到 Processed": "{target}: archive to Processed",
    "{path} 已经存在": "{path} already exists",
    "{done}/{n} 帧": ("{done}/{n} frame", "{done}/{n} frames"),
    "{done}/{n} 个文件": ("{done}/{n} file", "{done}/{n} files"),
    "需要完整路径：{path}": "A full path is needed: {path}",
    "没能创建 {path}：{error}": "Could not create {path}: {error}",
    "这个目标还没有成品图": "This target has no finished image yet",

    # share pictures
    "{n} 分钟": ("{n} min", "{n} min"),
    "{n} 小时": ("{n} hour", "{n} hours"),
    "{first} 至 {last}（{n} 晚）": ("{first} to {last} ({n} night)", "{first} to {last} ({n} nights)"),
    "（{time}）": " ({time})",

    # the AI assistant
    "已取消。": "Cancelled.",
    "达到最大轮数，已停止。请查看日志。": "Stopped after the maximum number of turns. See the log.",
    "# {target} 后期报告": "# {target} processing report",
    "- 配方: {recipe}": "- Recipe: {recipe}",
    "- 完成时间: {time}": "- Finished: {time}",
    "- 成品: {files}": "- Finals: {files}",
    "无": "none",
    "## 总结": "## Summary",
    "## 待确认 / 问题": "## To check / issues",
    "## 各阶段参数与指标": "## Parameters and metrics per stage",

    # setup check (doctor)
    "必需": "required",
    "推荐": "recommended",
    "可选": "optional",
    "注意：{note}": "Note: {note}",
    "必需组件都齐了。": "Everything required is in place.",
    "还缺必需组件，补齐前叠加和出图会失败。": "Required components are missing: stacking and processing fail until they are in place.",
    "PixInsight 官网（购买 / 申请试用）": "PixInsight website (buy / request a trial)",
    "下载页（用许可证账号登录）": "Downloads (sign in with your license account)",
    "RC Astro 官网": "RC Astro website",
    "下载页（用 PixInsight 许可证账号登录）": "Downloads (sign in with your PixInsight license account)",
    "装的是 {version}，需要 1.9 或更新": "Version {version} is installed; 1.9 or later is needed",
    "在 PixInsight 里点 Resources → Updates → Check for Updates，装好更新后重启；大版本升级要到下载页下载新的安装包":
        "In PixInsight choose Resources → Updates → Check for Updates and restart after installing them; a major "
        "upgrade needs the new installer from the downloads page",
    "装好后回到这里点“重新检查”": "Then come back here and click “Check again”",
    "使用找到的 PixInsight": "Use the PixInsight found",
    "手动选择 PixInsight 程序…": "Choose the PixInsight program…",
    "设置里的路径不对（{wrong}），但在 {found} 找到了 PixInsight":
        "The path in Settings is wrong ({wrong}), but PixInsight was found at {found}",
    "macOS 选 /Applications/PixInsight/PixInsight.app": "on macOS choose /Applications/PixInsight/PixInsight.app",
    "Windows 一般是 {path}": "on Windows usually {path}",
    "没有找到 PixInsight。叠加和出图都在 PixInsight 里完成，必须先装它":
        "PixInsight was not found. Stacking and processing run in PixInsight: install it first",
    "PixInsight 是付费软件：在官网购买许可证，或者先申请试用许可证":
        "PixInsight is commercial software: buy a license on its website, or request a trial license first",
    "用许可证账号登录下载页，下载 1.9 或更新版本的安装包并安装":
        "Sign in to the downloads page with your license account, download version 1.9 or later and install it",
    "打开一次 PixInsight，按提示输入许可证完成激活": "Open PixInsight once and enter the license when asked",
    "回到这里点“重新检查”。装在别的位置的话点“手动选择”（{where}）":
        "Come back here and click “Check again”. Installed elsewhere? Click “Choose” ({where})",
    "PixInsight 脚本（WBPP、ImageSolver）": "PixInsight scripts (WBPP, ImageSolver)",
    "WBPP（叠加）": "WBPP (stacking)",
    "ImageSolver（板解析，每个任务都会加载）": "ImageSolver (plate solving, loaded by every job)",
    "装好 PixInsight 后会自动找到": "Found automatically once PixInsight is installed",
    "使用找到的脚本目录": "Use the scripts folder found",
    "手动选择脚本目录…": "Choose the scripts folder…",
    "脚本目录不存在：{path}": "The scripts folder does not exist: {path}",
    "脚本目录是 PixInsight 安装目录下的 src/scripts": "The scripts folder is src/scripts in PixInsight's installation folder",
    "脚本目录里缺 {missing}": "Missing from the scripts folder: {missing}",
    "这些脚本随 PixInsight 一起安装。在 PixInsight 里点 Resources → Updates → Check for Updates，装好全部更新后重启 PixInsight":
        "These scripts come with PixInsight. In PixInsight choose Resources → Updates → Check for Updates, install "
        "all updates and restart PixInsight",
    "还是没有的话，重新安装 PixInsight（1.9 或更新）": "If they are still missing, reinstall PixInsight (1.9 or later)",
    "回到这里点“重新检查”": "Come back here and click “Check again”",
    "RC Astro 插件（BlurXTerminator、NoiseXTerminator、StarXTerminator）":
        "RC Astro tools (BlurXTerminator, NoiseXTerminator, StarXTerminator)",
    "找不到 PixInsight 的安装目录（bin、src/scripts），没法检查":
        "PixInsight's installation folder (bin, src/scripts) was not found: cannot check",
    "装好 PixInsight 后才能检查": "Can be checked once PixInsight is installed",
    "在 PixInsight 里点 Process → All Processes，分别打开没激活的工具，按提示输入购买时用的邮箱和许可证密钥":
        "In PixInsight choose Process → All Processes, open each tool that is not activated and enter the e-mail "
        "and license key of your purchase",
    "关掉 PixInsight（它关掉时才会保存激活信息），回到这里点“重新检查”":
        "Close PixInsight (it saves the activation when it closes), then come back here and click “Check again”",
    "没装：{tools}。每个配方都要用这三个工具（去卷积、降噪、去星）":
        "Not installed: {tools}. Every recipe uses these three tools (deconvolution, noise reduction, star removal)",
    "在 RC Astro 官网购买这三个工具，许可证密钥会发到邮箱":
        "Buy the three tools on the RC Astro website; the license keys arrive by e-mail",
    "在 PixInsight 里点 Resources → Updates → Manage Repositories，点 Add，把下面三个地址分别加进去：":
        "In PixInsight choose Resources → Updates → Manage Repositories, click Add and add each of these addresses:",
    "点 Resources → Updates → Check for Updates，装好后按提示重启 PixInsight":
        "Choose Resources → Updates → Check for Updates and restart PixInsight when asked",
    "已经装上，但没找到 PixInsight 的设置文件，确认不了有没有激活":
        "Installed, but PixInsight's settings file was not found: cannot tell whether they are activated",
    "打开一次 PixInsight，确认三个工具都已激活，然后关掉它":
        "Open PixInsight once, make sure all three tools are activated, then close it",
    "装上了但没激活：{tools}。没激活的工具在无界面模式下会卡在激活窗口":
        "Installed but not activated: {tools}. A tool that is not activated stops headless jobs at its activation "
        "dialog",
    "三个工具都已安装并激活": "All three tools are installed and activated",
    "Gaia DR3/SP 数据库": "Gaia DR3/SP database",
    "没找到 PixInsight 的设置文件，确认不了有没有配置": "PixInsight's settings file was not found: cannot tell whether it is set up",
    "打开一次 PixInsight 再关掉，然后回到这里点“重新检查”":
        "Open PixInsight once and close it, then come back here and click “Check again”",
    "在 PixInsight 里点 Process → All Processes → Gaia，再点窗口底部的扳手图标（Preferences）":
        "In PixInsight choose Process → All Processes → Gaia, then click the wrench icon (Preferences) at the bottom",
    "数据库选 Gaia DR3/SP，把下载的 .xpsd 文件全部加进来，点 OK":
        "Choose the Gaia DR3/SP database, add all the downloaded .xpsd files and click OK",
    "关掉 PixInsight（它关掉时才会保存设置），回到这里点“重新检查”":
        "Close PixInsight (it saves its settings when it closes), then come back here and click “Check again”",
    "没有配置。SPCC 色彩校准用不了，会改用手动背景中和 + 色彩校准，颜色没那么准":
        "Not set up. SPCC colour calibration cannot run, so manual background neutralization and colour calibration "
        "are used instead: colours are less accurate",
    "用 PixInsight 许可证账号登录下载页，下载 Gaia DR3/SP 数据库文件（gdr3sp-*.xpsd）":
        "Sign in to the downloads page with your PixInsight license account and download the Gaia DR3/SP database "
        "files (gdr3sp-*.xpsd)",
    "把文件放进一个以后不会挪动的文件夹，比如 {folder}": "Put the files in a folder that will stay put, for example {folder}",
    "配置了 {n} 个文件，其中 {gone} 个找不到了（被挪动或删除了？）：{first}": (
        "{n} file is set up and {gone} of them is gone (moved or deleted?): {first}",
        "{n} files are set up and {gone} of them are gone (moved or deleted?): {first}"),
    "把数据库文件放回原处；或者在 Gaia 的设置里删掉旧路径，重新添加现在的文件":
        "Put the database files back, or remove the old paths in Gaia's preferences and add the files where they "
        "are now",
    "已配置 {n} 个数据库文件，在 {folder}": ("{n} database file set up, in {folder}", "{n} database files set up, in {folder}"),
    "创建这个文件夹": "Create this folder",
    "选择已有的文件夹…": "Choose an existing folder…",
    "文件夹不存在：{path}": "The folder does not exist: {path}",
    "还没有选": "Not chosen yet",
    "选一个空间充足的文件夹，放拍摄数据和处理结果。astroflow 会在里面建 In Processing、Processed，校准帧库（Dark Library、Bias Library、Flat）可以以后再加":
        "Choose a folder with plenty of space for your data and results. astroflow creates In Processing and "
        "Processed in it; the calibration library (Dark Library, Bias Library, Flat) can be added later",
    "任务临时目录": "Job folder",
    "PixInsight 不接受带空格或中文的路径": "PixInsight does not accept paths with spaces or Chinese characters",
    "这个位置不能写入": "This place cannot be written to",
    "选一个路径里没有空格和中文、可以写入的文件夹，比如 {example}":
        "Choose a writable folder whose path has no spaces or Chinese characters, for example {example}",
    "选择文件夹…": "Choose a folder…",
    "AI 模型": "AI model",
    "：本机服务，用“测试连接”确认它在运行": ": a local server, use “Test connection” to see that it runs",
    "默认服务商": "The default provider",
    "{provider} 还没有 API 密钥。只有 AI 助手需要；导入、叠加、出图和调参数都不受影响":
        "{provider} has no API key yet. Only the AI assistant needs one; importing, stacking, processing and tuning "
        "work without it",
    "在服务商网站申请 API 密钥": "Get an API key on the provider's website",
    "打开 设置 → AI 模型，粘贴密钥，点“保存密钥”，再点“测试连接”":
        "Open Settings → AI model, paste the key, click “Save key”, then “Test connection”",
    "不想用云端服务的话，可以在同一页添加本机的 Ollama 或 LM Studio，设为默认":
        "To stay off cloud services, add a local Ollama or LM Studio on the same page and make it the default",
    "申请 {provider} 密钥": "Get a {provider} key",
    "打开 AI 模型设置": "Open the AI model settings",
    "PixInsight 正开着。激活插件、配置 Gaia 以后先关掉它：它关掉时才把设置写进文件，这里才查得到":
        "PixInsight is open. After activating tools or setting up Gaia, close it: it writes its settings when it "
        "closes, and only then can they be checked here",
}
