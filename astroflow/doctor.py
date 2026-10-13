"""Setup check: what astroflow needs on this computer, what is missing, and how to install it.

Required: PixInsight 1.9+ with its scripts (WBPP stacks, ImageSolver is loaded by every job), the RC Astro tools
(every recipe runs BlurXTerminator, NoiseXTerminator and StarXTerminator), a data folder, and a job folder PixInsight
accepts. Recommended: the Gaia DR3/SP database (without it SPCC falls back to manual BN+CC). Optional: an AI provider
(only the assistant needs one).

PixInsight is never started. Whether the RC Astro tools are activated and where the Gaia database is come from settings
slot 1 (core-001-pxi.settings): the file the GUI writes when it closes and headless jobs read. Licenses are only tested
for presence; their values never leave this module.

Used by the app (GET /api/setup) and the command line (python -m astroflow doctor).
"""
import os
import plistlib
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import config, pi, settings

RC_TOOLS = ("BlurXTerminator", "NoiseXTerminator", "StarXTerminator")
RC_REPOSITORIES = [f"https://www.rc-astro.com/{t}/PixInsight" for t in RC_TOOLS]
MIN_VERSION = (1, 9)
_XSDT = "{http://www.pixinsight.com/xsdt}"
_GAIA_KEY = "ModuleData/Gaia/DR3SPDatabaseFilePath"

PIXINSIGHT_LINKS = [{"label": "PixInsight 官网（购买 / 申请试用）", "url": "https://pixinsight.com/"},
                    {"label": "下载页（用许可证账号登录）", "url": "https://pixinsight.com/dist/"}]
RC_LINKS = [{"label": "RC Astro 官网", "url": "https://www.rc-astro.com/"}]
GAIA_LINKS = [{"label": "下载页（用 PixInsight 许可证账号登录）", "url": "https://pixinsight.com/dist/"}]
KEY_LINKS = {"DeepSeek": "https://platform.deepseek.com/api_keys", "OpenAI": "https://platform.openai.com/api-keys"}


@dataclass
class Action:
    """Something the app can do for the user: save detected settings, create or pick a folder, open Settings."""
    kind: str                       # apply | create_folder | pick_folder | pick_file | open_settings
    label: str
    setting: str | None = None      # the setting a picked or created path goes to
    value: dict | None = None       # apply: the settings to save; create_folder: {setting: path}
    tab: str | None = None          # open_settings: the tab to show


@dataclass
class Check:
    id: str
    title: str
    level: str                      # required | recommended | optional
    status: str                     # ok | warn | missing | unknown
    summary: str
    steps: list = field(default_factory=list)      # [{"text", "code": [lines to copy]}]
    links: list = field(default_factory=list)      # [{"label", "url"}]
    actions: list = field(default_factory=list)    # [Action]


def _step(text, *code):
    return {"text": text, "code": list(code)}


# ----------------------------------------------------------------------------------------------- PixInsight on disk

def pi_settings_files():
    """Where PixInsight keeps settings slot 1, most likely first."""
    home = Path.home()
    if sys.platform == "win32":
        return [Path(os.environ[v]) / d / "core-001-pxi.settings"
                for v in ("APPDATA", "LOCALAPPDATA") if os.environ.get(v) for d in ("Pleiades", "PixInsight")]
    if sys.platform == "darwin":
        return [home / "Library" / "PixInsight" / "core-001-pxi.settings"]
    return [home / ".PixInsight" / "core-001-pxi.settings", home / ".config" / "Pleiades" / "core-001-pxi.settings"]


def read_pi_settings():
    """Settings slot 1 as {"ModuleData/Gaia/DR3SPDatabaseFilePath00": value, ...}; None when there is no such file
    (PixInsight was never closed normally on this account) or it cannot be read."""
    path = next((p for p in pi_settings_files() if p.is_file()), None)
    if path is None:
        return None
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    values = {}

    def walk(element, prefix):
        for child in element:
            key = prefix + (child.get("k", ""),)
            if child.tag == _XSDT + "i":
                walk(child, key)
            elif child.tag == _XSDT + "v":
                values["/".join(key)] = child.get("v", child.text or "")

    walk(root, ())
    return values


def usual_programs():
    """Where the PixInsight installer puts the program."""
    if sys.platform == "win32":
        bases = [os.environ.get("ProgramW6432"), os.environ.get("ProgramFiles")] + [f"{d}:/Program Files" for d in "CDEF"]
        return [Path(b) / "PixInsight" / "bin" / "PixInsight.exe" for b in dict.fromkeys(b for b in bases if b)]
    if sys.platform == "darwin":
        return [Path(a) / "PixInsight" / "PixInsight.app" / "Contents" / "MacOS" / "PixInsight"
                for a in ("/Applications", Path.home() / "Applications")]
    return [Path("/opt/PixInsight/bin/PixInsight")]


def install_root(exe, scripts=None):
    """PixInsight's installation folder (bin/, src/scripts/): from the scripts folder, else from the program."""
    if scripts and scripts.name == "scripts" and scripts.parent.name == "src" and (scripts.parent.parent / "bin").is_dir():
        return scripts.parent.parent
    for d in list(exe.parents)[:5]:
        if (d / "bin").is_dir() and (d / "src" / "scripts").is_dir():
            return d
    return None


def find_pixinsight():
    """PixInsight installations in the usual places: [(program, scripts folder)]."""
    found = []
    for exe in usual_programs():
        root = install_root(exe) if exe.is_file() else None
        if root:
            found.append((exe, root / "src" / "scripts"))
    return found


def resolve_pixinsight_exe(path):
    """The program inside what the user picked: macOS file dialogs return PixInsight.app (a folder), and some people
    pick the installation folder itself."""
    p = Path(path)
    if p.is_dir():
        for inner in (p / "Contents" / "MacOS" / "PixInsight", p / "PixInsight.app" / "Contents" / "MacOS" / "PixInsight",
                      p / "bin" / "PixInsight.exe", p / "bin" / "PixInsight"):
            if inner.is_file():
                return inner.as_posix()
    return path


def pixinsight_version(exe, pis):
    """(major, minor, patch) of the program (macOS bundle), else of the PixInsight that last wrote its settings."""
    plist = exe.parent.parent / "Info.plist"
    texts = []
    if plist.is_file():
        try:
            texts.append(str(plistlib.loads(plist.read_bytes()).get("CFBundleShortVersionString", "")))
        except (OSError, ValueError, plistlib.InvalidFileException):
            pass
    texts.append((pis or {}).get("LastVersion", ""))
    for text in texts:
        m = re.match(r"(\d+)\.(\d+)(?:\.(\d+))?", text)
        if m:
            return tuple(int(x or 0) for x in m.groups())
    return None


def _writable(path):
    """Can this folder be created / written to (checked on the nearest existing parent, nothing is created)?"""
    for d in (path, *path.parents):
        if d.exists():
            return d.is_dir() and os.access(d, os.W_OK)
    return False


# ----------------------------------------------------------------------------------------------- the checks

def _check_pixinsight(s, pis, found):
    exe = Path(s.pixinsight_exe)
    if exe.is_file():
        version = pixinsight_version(exe, pis)
        shown = ".".join(map(str, version)) if version else ""
        if version and version[:2] < MIN_VERSION:
            return Check("pixinsight", "PixInsight", "required", "missing",
                         f"装的是 {shown}，需要 1.9 或更新",
                         steps=[_step("在 PixInsight 里点 Resources → Updates → Check for Updates，装好更新后重启；"
                                      "大版本升级要到下载页下载新的安装包"),
                                _step("装好后回到这里点“重新检查”")],
                         links=PIXINSIGHT_LINKS)
        return Check("pixinsight", "PixInsight", "required", "ok", f"{shown + '：' if shown else ''}{exe}")
    actions = []
    if found:
        f_exe, f_scripts = found[0]
        actions.append(Action("apply", "使用找到的 PixInsight",
                              value={"pixinsight_exe": f_exe.as_posix(), "pixinsight_scripts": f_scripts.as_posix()}))
    actions.append(Action("pick_file", "手动选择 PixInsight 程序…", setting="pixinsight_exe"))
    if found:
        return Check("pixinsight", "PixInsight", "required", "missing",
                     f"设置里的路径不对（{exe}），但在 {found[0][0]} 找到了 PixInsight", actions=actions)
    where = ("macOS 选 /Applications/PixInsight/PixInsight.app" if sys.platform == "darwin"
             else r"Windows 一般是 C:\Program Files\PixInsight\bin\PixInsight.exe")
    return Check("pixinsight", "PixInsight", "required", "missing",
                 "没有找到 PixInsight。叠加和出图都在 PixInsight 里完成，必须先装它",
                 steps=[_step("PixInsight 是付费软件：在官网购买许可证，或者先申请试用许可证"),
                        _step("用许可证账号登录下载页，下载 1.9 或更新版本的安装包并安装"),
                        _step("打开一次 PixInsight，按提示输入许可证完成激活"),
                        _step(f"回到这里点“重新检查”。装在别的位置的话点“手动选择”（{where}）")],
                 links=PIXINSIGHT_LINKS, actions=actions)


def _check_scripts(s, root, found):
    scripts = Path(s.pixinsight_scripts)
    need = {"WBPP（叠加）": scripts / "BatchPreprocessing" / "WBPP.js",
            "ImageSolver（板解析，每个任务都会加载）": scripts / "AdP" / "ImageSolver.js"}
    lacking = [name for name, p in need.items() if not p.is_file()]
    if not lacking:
        return Check("scripts", "PixInsight 脚本（WBPP、ImageSolver）", "required", "ok", str(scripts))
    title = "PixInsight 脚本（WBPP、ImageSolver）"
    if not Path(s.pixinsight_exe).is_file() and not found:
        return Check("scripts", title, "required", "missing", "装好 PixInsight 后会自动找到")
    actions = []
    guess = (root / "src" / "scripts") if root else (found[0][1] if found else None)
    if guess and guess != scripts and (guess / "BatchPreprocessing" / "WBPP.js").is_file():
        actions.append(Action("apply", "使用找到的脚本目录", value={"pixinsight_scripts": guess.as_posix()}))
    actions.append(Action("pick_folder", "手动选择脚本目录…", setting="pixinsight_scripts"))
    if not scripts.is_dir():
        return Check("scripts", title, "required", "missing", f"脚本目录不存在：{scripts}",
                     steps=[_step("脚本目录是 PixInsight 安装目录下的 src/scripts")], actions=actions)
    return Check("scripts", title, "required", "missing", f"脚本目录里缺 {'、'.join(lacking)}",
                 steps=[_step("这些脚本随 PixInsight 一起安装。在 PixInsight 里点 Resources → Updates → "
                              "Check for Updates，装好全部更新后重启 PixInsight"),
                        _step("还是没有的话，重新安装 PixInsight（1.9 或更新）"),
                        _step("回到这里点“重新检查”")],
                 links=PIXINSIGHT_LINKS, actions=actions)


def _check_rc_astro(root, pis, installed):
    title = "RC Astro 插件（BlurXTerminator、NoiseXTerminator、StarXTerminator）"
    if root is None:
        return Check("rc_astro", title, "required", "unknown",
                     "找不到 PixInsight 的安装目录（bin、src/scripts），没法检查" if installed else "装好 PixInsight 后才能检查")
    absent, inactive = [], []
    for tool in RC_TOOLS:
        if not any((root / "bin" / f"{tool}-pxm{ext}").is_file() for ext in (".dll", ".dylib", ".so")):
            absent.append(tool)
        elif pis is not None and not pis.get(f"ModuleData/{tool}/{tool}.license"):
            inactive.append(tool)
    activate = [_step("在 PixInsight 里点 Process → All Processes，分别打开没激活的工具，按提示输入购买时用的邮箱和许可证密钥"),
                _step("关掉 PixInsight（它关掉时才会保存激活信息），回到这里点“重新检查”")]
    if absent:
        return Check("rc_astro", title, "required", "missing",
                     f"没装：{'、'.join(absent)}。每个配方都要用这三个工具（去卷积、降噪、去星）",
                     steps=[_step("在 RC Astro 官网购买这三个工具，许可证密钥会发到邮箱"),
                            _step("在 PixInsight 里点 Resources → Updates → Manage Repositories，点 Add，"
                                  "把下面三个地址分别加进去：", *RC_REPOSITORIES),
                            _step("点 Resources → Updates → Check for Updates，装好后按提示重启 PixInsight"),
                            *activate],
                     links=RC_LINKS)
    if pis is None:
        return Check("rc_astro", title, "required", "unknown",
                     "已经装上，但没找到 PixInsight 的设置文件，确认不了有没有激活",
                     steps=[_step("打开一次 PixInsight，确认三个工具都已激活，然后关掉它"), _step("回到这里点“重新检查”")])
    if inactive:
        return Check("rc_astro", title, "required", "missing",
                     f"装上了但没激活：{'、'.join(inactive)}。没激活的工具在无界面模式下会卡在激活窗口",
                     steps=activate, links=RC_LINKS)
    return Check("rc_astro", title, "required", "ok", "三个工具都已安装并激活")


def _check_gaia(pis, installed):
    title = "Gaia DR3/SP 数据库"
    if not installed:
        return Check("gaia", title, "recommended", "unknown", "装好 PixInsight 后才能检查")
    if pis is None:
        return Check("gaia", title, "recommended", "unknown", "没找到 PixInsight 的设置文件，确认不了有没有配置",
                     steps=[_step("打开一次 PixInsight 再关掉，然后回到这里点“重新检查”")])
    files = [Path(v) for k, v in sorted(pis.items()) if k.startswith(_GAIA_KEY) and v]
    gone = [f for f in files if not f.is_file()]
    folder = r"D:\GaiaSP" if sys.platform == "win32" else "~/Documents/GaiaSP"
    configure = [_step("在 PixInsight 里点 Process → All Processes → Gaia，再点窗口底部的扳手图标（Preferences）"),
                 _step("数据库选 Gaia DR3/SP，把下载的 .xpsd 文件全部加进来，点 OK"),
                 _step("关掉 PixInsight（它关掉时才会保存设置），回到这里点“重新检查”")]
    if not files:
        return Check("gaia", title, "recommended", "missing",
                     "没有配置。SPCC 色彩校准用不了，会改用手动背景中和 + 色彩校准，颜色没那么准",
                     steps=[_step("用 PixInsight 许可证账号登录下载页，下载 Gaia DR3/SP 数据库文件（gdr3sp-*.xpsd）"),
                            _step(f"把文件放进一个以后不会挪动的文件夹，比如 {folder}"),
                            *configure],
                     links=GAIA_LINKS)
    if gone:
        return Check("gaia", title, "recommended", "warn",
                     f"配置了 {len(files)} 个文件，其中 {len(gone)} 个找不到了（被挪动或删除了？）：{gone[0]}",
                     steps=[_step("把数据库文件放回原处；或者在 Gaia 的设置里删掉旧路径，重新添加现在的文件"), *configure],
                     links=GAIA_LINKS)
    return Check("gaia", title, "recommended", "ok", f"已配置 {len(files)} 个数据库文件，在 {files[0].parent}")


def _check_data_root(s):
    title = "数据根目录"
    root = Path(s.astro_root) if s.astro_root else None
    if root and root.is_dir():
        return Check("data_root", title, "required", "ok", str(root))
    actions = []
    if root and root.is_absolute() and _writable(root):
        actions.append(Action("create_folder", "创建这个文件夹", setting="astro_root", value={"astro_root": str(root)}))
    actions.append(Action("pick_folder", "选择已有的文件夹…", setting="astro_root"))
    return Check("data_root", title, "required", "missing",
                 f"文件夹不存在：{root}" if root else "还没有选",
                 steps=[_step("选一个空间充足的文件夹，放拍摄数据和处理结果。astroflow 会在里面建 In Processing、"
                              "Processed，校准帧库（Dark Library、Bias Library、Flat）可以以后再加")],
                 actions=actions)


def _check_runs():
    title = "任务临时目录"
    runs = config.RUNS
    if config.pixinsight_path_ok(runs) and _writable(runs):
        return Check("runs_dir", title, "required", "ok", str(runs))
    example = r"D:\astroflow-runs" if sys.platform == "win32" else "/Users/Shared/astroflow/runs"
    why = ("PixInsight 不接受带空格或中文的路径" if not config.pixinsight_path_ok(runs) else "这个位置不能写入")
    return Check("runs_dir", title, "required", "missing", f"{why}：{runs}",
                 steps=[_step(f"选一个路径里没有空格和中文、可以写入的文件夹，比如 {example}")],
                 actions=[Action("pick_folder", "选择文件夹…", setting="runs_dir")])


def _check_ai(s):
    title = "AI 模型"
    try:
        p = s.provider()
    except KeyError:
        p = None
    if p and (not p.needs_key or settings.has_api_key(p.name)):
        where = "：本机服务，用“测试连接”确认它在运行" if not p.needs_key else ""
        return Check("ai", title, "optional", "ok", f"{p.name}（{p.planner_model}）{where}")
    link = KEY_LINKS.get(p.name) if p else None
    return Check("ai", title, "optional", "missing",
                 f"{p.name if p else '默认服务商'} 还没有 API 密钥。只有 AI 助手需要；导入、叠加、出图和调参数都不受影响",
                 steps=[_step("在服务商网站申请 API 密钥"),
                        _step("打开 设置 → AI 模型，粘贴密钥，点“保存密钥”，再点“测试连接”"),
                        _step("不想用云端服务的话，可以在同一页添加本机的 Ollama 或 LM Studio，设为默认")],
                 links=[{"label": f"申请 {p.name} 密钥", "url": link}] if link else [],
                 actions=[Action("open_settings", "打开 AI 模型设置", tab="ai")])


def run():
    """The setup report: {"ready": nothing required is missing, "checks": [...], "notes": [...]}."""
    s = settings.get()
    pis = read_pi_settings()
    found = find_pixinsight()
    exe, scripts = Path(s.pixinsight_exe), Path(s.pixinsight_scripts)
    installed = exe.is_file() or bool(found)
    root = install_root(exe, scripts) if exe.is_file() else (install_root(found[0][0]) if found else None)
    checks = [_check_pixinsight(s, pis, found), _check_scripts(s, root, found), _check_rc_astro(root, pis, installed),
              _check_gaia(pis, installed), _check_data_root(s), _check_runs(), _check_ai(s)]
    notes = []
    if pi.running_instances() and any(c.status != "ok" for c in checks if c.id in ("rc_astro", "gaia")):
        notes.append("PixInsight 正开着。激活插件、配置 Gaia 以后先关掉它：它关掉时才把设置写进文件，这里才查得到")
    ready = not any(c.level == "required" and c.status == "missing" for c in checks)
    return {"ready": ready, "checks": [asdict(c) for c in checks], "notes": notes}


def print_report(report):
    marks = {"ok": "✓", "warn": "!", "missing": "✗", "unknown": "?"}
    levels = {"required": "必需", "recommended": "推荐", "optional": "可选"}
    for c in report["checks"]:
        print(f"{marks[c['status']]} {c['title']}  [{levels[c['level']]}]  {c['summary']}")
        for i, step in enumerate(c["steps"], 1):
            print(f"    {i}. {step['text']}")
            for line in step["code"]:
                print(f"         {line}")
        for link in c["links"]:
            print(f"    {link['label']}：{link['url']}")
    for note in report["notes"]:
        print(f"注意：{note}")
    print("必需组件都齐了。" if report["ready"] else "还缺必需组件，补齐前叠加和出图会失败。")
