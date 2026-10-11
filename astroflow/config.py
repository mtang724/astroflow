"""Paths and machine-specific settings. Override any value in config.local.json at the project root."""
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
PJSR_DIR = Path(__file__).resolve().parent / "pjsr"
KNOWLEDGE = PROJECT / "knowledge"

ASTRO_ROOT = Path(r"F:\AstroPhotograph")
IN_PROCESSING = ASTRO_ROOT / "In Processing"
PROCESSED = ASTRO_ROOT / "Processed"

PI_EXE = Path(r"C:\Program Files\PixInsight\bin\PixInsight.exe")
PI_SCRIPTS = Path(r"C:\Program Files\PixInsight\src\scripts")
WBPP_JS = PI_SCRIPTS / "BatchPreprocessing" / "WBPP.js"

# Equipment defaults used when FITS headers are missing (ASI2600MC Air on a 72 mm ED refractor).
CAMERA = {"name": "ZWO ASI2600MC Air", "pixel_um": 3.76, "sensor": "Sony IMX571 (color)",
          "spcc_filters": "Sony Color Sensor"}

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_PLANNER_MODEL = "deepseek-v4-pro"   # text-only, strongest reasoning
DEEPSEEK_VISION_MODEL = "deepseek-flash"     # accepts images: used to judge previews

_local = PROJECT / "config.local.json"
if _local.exists():
    for k, v in json.loads(_local.read_text(encoding="utf-8")).items():
        globals()[k] = Path(v) if isinstance(v, str) and (":" in v or "/" in v) else v


def env(key, default=None):
    """Read a value from the project .env file (KEY=value lines), without exporting it."""
    path = PROJECT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                if k.strip() == key:
                    return v.strip().strip('"').strip("'")
    return default
