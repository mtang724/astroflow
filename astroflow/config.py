"""Paths and machine-specific values, read from the user settings (astroflow/settings.py) at access time, so a change
made in the desktop app's Settings dialog applies everywhere without restarting.

    config.ASTRO_ROOT, config.IN_PROCESSING, config.PROCESSED, config.PI_EXE, config.PI_SCRIPTS, config.WBPP_JS,
    config.RUNS, config.CAMERA                      -> computed from settings.get()
    config.PROJECT, config.PJSR_DIR, config.SKILLS   -> where the code and its read-only resources live
    config.KNOWLEDGE                                 -> the knowledge base (written to: references, agent notes)
"""
import os
import shutil
import sys
from pathlib import Path

from . import settings

PROJECT = settings.PROJECT
PJSR_DIR = Path(__file__).resolve().parent / "pjsr"
SKILLS = PROJECT / "skills"
FROZEN = getattr(sys, "frozen", False)          # running from the packaged desktop app (PyInstaller)

_knowledge = None


def __getattr__(name):
    if name == "KNOWLEDGE":
        return _knowledge_dir()
    s = settings.get()
    if name == "ASTRO_ROOT":
        return Path(s.astro_root)
    if name == "IN_PROCESSING":
        return Path(s.astro_root) / "In Processing"
    if name == "PROCESSED":
        return Path(s.astro_root) / "Processed"
    if name == "PI_EXE":
        return Path(s.pixinsight_exe)
    if name == "PI_SCRIPTS":
        return Path(s.pixinsight_scripts)
    if name == "WBPP_JS":
        return Path(s.pixinsight_scripts) / "BatchPreprocessing" / "WBPP.js"
    if name == "RUNS":
        return Path(s.runs_dir) if s.runs_dir else _default_runs()
    if name == "CAMERA":
        e = s.equipment
        return {"name": e.get("camera"), "pixel_um": e.get("pixel_um"), "sensor": e.get("sensor"),
                "spcc_filters": e.get("spcc_filters")}
    raise AttributeError(f"module 'astroflow.config' has no attribute {name!r}")


def _knowledge_dir():
    """A source checkout uses its own knowledge/. The installed app's folder is read-only, so it works on a per-user
    copy, seeded from the bundled one: files a newer version adds are copied over, the user's are never replaced."""
    global _knowledge
    if _knowledge is None:
        bundled = PROJECT / "knowledge"
        if not FROZEN:
            _knowledge = bundled
        else:
            import platformdirs
            _knowledge = Path(platformdirs.user_data_dir(settings.APP, appauthor=False)) / "knowledge"
            for src in bundled.rglob("*"):
                dst = _knowledge / src.relative_to(bundled)
                if src.is_file() and not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
    return _knowledge


def pixinsight_path_ok(path):
    """PixInsight's -r= argument (how jobs start) breaks on paths with spaces or non-ASCII characters."""
    return " " not in str(path) and str(path).isascii()


def _default_runs():
    """Where PixInsight job scripts are written: a path PixInsight accepts (pixinsight_path_ok). An installed app's own
    folder is read-only, so: the source checkout when it qualifies, else the per-user cache folder (~/Library/Caches/
    astroflow on macOS - Application Support has a space), else - a user name with a space or Chinese characters -
    a shared folder. When nothing qualifies, Settings shows a warning and the user picks a folder."""
    import platformdirs

    if not FROZEN and pixinsight_path_ok(PROJECT) and os.access(PROJECT, os.W_OK):
        return PROJECT / ".runs"
    candidates = [Path(platformdirs.user_cache_dir(settings.APP, appauthor=False)) / "runs",
                  Path.home() / ".astroflow" / "runs"]
    if sys.platform == "win32":
        candidates.append(Path(os.environ.get("PUBLIC", "C:/Users/Public")) / "astroflow" / "runs")
    elif sys.platform == "darwin":
        candidates.append(Path("/Users/Shared/astroflow/runs"))
    return next((c for c in candidates if pixinsight_path_ok(c)), candidates[0])


def env(key, default=None):
    """A value from the project .env file (KEY=value lines), without exporting it. API keys: use settings.get_api_key."""
    return settings._dotenv(key) or default
