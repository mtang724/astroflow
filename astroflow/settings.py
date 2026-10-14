"""User settings: where the data and PixInsight live, which LLM to use, equipment and taste.

Stored as JSON in the per-user config directory (Windows %APPDATA%\\astroflow, macOS ~/Library/Application Support/
astroflow; override with ASTROFLOW_SETTINGS=<file>). API keys are never written there: they live in the OS credential
store (Windows Credential Manager / macOS Keychain) through `keyring`, with the project `.env` (api_key=...) as a
fallback so the command-line setup keeps working.
"""
import copy
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import keyring
import platformdirs

from . import jsonfile

APP = "astroflow"
PROJECT = Path(__file__).resolve().parent.parent


@dataclass
class LLMProvider:
    """Any OpenAI-compatible endpoint: DeepSeek, OpenAI, a local Ollama / LM Studio / vLLM server, ..."""
    name: str
    base_url: str
    planner_model: str
    vision_model: str = ""          # empty: no image input; results are judged on the numbers only
    needs_key: bool = True          # local servers usually accept any key
    tools: bool = True              # the model supports function calling (the agent needs it)


PROVIDER_PRESETS = [
    LLMProvider("DeepSeek", "https://api.deepseek.com", "deepseek-v4-pro", "deepseek-flash"),
    LLMProvider("OpenAI", "https://api.openai.com/v1", "gpt-5", "gpt-5"),
    LLMProvider("Ollama (local)", "http://localhost:11434/v1", "qwen3:32b", "qwen2.5vl:32b", needs_key=False),
    LLMProvider("LM Studio (local)", "http://localhost:1234/v1", "local-model", "", needs_key=False),
]


def _platform_defaults():
    if sys.platform == "win32":
        return {"astro_root": "F:/AstroPhotograph" if Path("F:/AstroPhotograph").exists() else str(Path.home() / "AstroPhotograph"),
                "pixinsight_exe": "C:/Program Files/PixInsight/bin/PixInsight.exe",
                "pixinsight_scripts": "C:/Program Files/PixInsight/src/scripts"}
    if sys.platform == "darwin":
        return {"astro_root": str(Path.home() / "AstroPhotograph"),
                "pixinsight_exe": "/Applications/PixInsight/PixInsight.app/Contents/MacOS/PixInsight",
                "pixinsight_scripts": "/Applications/PixInsight/src/scripts"}
    return {"astro_root": str(Path.home() / "AstroPhotograph"),
            "pixinsight_exe": "/opt/PixInsight/bin/PixInsight",
            "pixinsight_scripts": "/opt/PixInsight/src/scripts"}


@dataclass
class Settings:
    astro_root: str = ""
    pixinsight_exe: str = ""
    pixinsight_scripts: str = ""
    runs_dir: str = ""                                   # empty: <project>/.runs (a path PixInsight accepts)
    llm_active: str = "DeepSeek"
    llm_providers: list = field(default_factory=lambda: [asdict(p) for p in PROVIDER_PRESETS])
    equipment: dict = field(default_factory=lambda: {
        "camera": "ZWO ASI2600MC Air", "sensor": "Sony IMX571 (color)", "pixel_um": 3.76,
        "telescope": "72 mm ED refractor", "focal_mm": 563, "spcc_filters": "Sony Color Sensor"})
    extra_targets: list = field(default_factory=list)  # target folders outside In Processing opened in the app
    preferences: dict = field(default_factory=lambda: {
        "subject_chroma_ratio": [0.8, 1.2],             # colourfulness vs peer references (user feedback 2026-10-10)
        "export_formats": ["png", "jpg", "tif"],
        "language": "auto"})                            # auto (the system's) | zh | en: astroflow.i18n

    def provider(self, name=None):
        name = name or self.llm_active
        for p in self.llm_providers:
            if p["name"] == name:
                return LLMProvider(**{k: v for k, v in p.items() if k in LLMProvider.__dataclass_fields__})
        raise KeyError(f"no LLM provider named {name!r}")

    def upsert_provider(self, provider):
        self.llm_providers = [p for p in self.llm_providers if p["name"] != provider.name] + [asdict(provider)]


def settings_path():
    env = os.environ.get("ASTROFLOW_SETTINGS")
    return Path(env) if env else Path(platformdirs.user_config_dir(APP, appauthor=False, roaming=True)) / "settings.json"


def load(path=None):
    path = Path(path) if path else settings_path()
    data = {**asdict(Settings()), **_platform_defaults()}
    legacy = PROJECT / "config.local.json"          # the command-line era override file
    if legacy.exists():
        old = json.loads(legacy.read_text(encoding="utf-8"))
        for key_old, key_new in (("ASTRO_ROOT", "astro_root"), ("PI_EXE", "pixinsight_exe"),
                                 ("PI_SCRIPTS", "pixinsight_scripts")):
            if key_old in old:
                data[key_new] = str(old[key_old])
    if path.exists():
        data.update(_read_settings_file(path))
    known = Settings.__dataclass_fields__
    return Settings(**{k: v for k, v in data.items() if k in known})


def _read_settings_file(path):
    """The saved settings; a damaged file is set aside (settings.json.broken) so the app starts with the defaults
    and the user can fix the paths in Settings, instead of every request failing."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except ValueError:
        pass
    print(f"astroflow: {path} is not valid settings JSON; moved it to {path.name}.broken and using defaults",
          file=sys.stderr)
    os.replace(path, path.with_name(path.name + ".broken"))
    return {}


def save(s, path=None):
    path = Path(path) if path else settings_path()
    jsonfile.write(path, asdict(s))
    global _current
    _current = s


_current = None


def get():
    """The settings in effect (loaded once; `save` and `reload` replace them)."""
    global _current
    if _current is None:
        _current = load()
    return _current


def reload():
    global _current
    _current = load()
    return _current


# ----------------------------------------------------------------------------------------------- secrets

def _dotenv(key):
    p = PROJECT / ".env"
    if not p.exists():
        return None
    for line in p.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
    return None


def get_api_key(provider_name):
    """Key for a provider: OS credential store first; else the project .env (api_key=... for DeepSeek, as in the
    command-line era), which is then copied into the credential store so the installed app finds it too."""
    try:
        key = keyring.get_password(APP, provider_name)
    except keyring.errors.KeyringError:
        key = None
    if key:
        return key
    if provider_name == "DeepSeek":
        key = _dotenv("api_key") or _dotenv("DEEPSEEK_API_KEY")
    else:
        key = _dotenv(f"{provider_name.upper().replace(' ', '_')}_API_KEY")
    if key:
        try:
            keyring.set_password(APP, provider_name, key)
        except keyring.errors.KeyringError:
            pass                                   # no usable credential store: keep reading .env
    return key


def set_api_key(provider_name, key):
    if key:
        keyring.set_password(APP, provider_name, key)
    else:
        try:
            keyring.delete_password(APP, provider_name)
        except keyring.errors.KeyringError:        # nothing stored (PasswordDeleteError) or no usable store
            pass


def has_api_key(provider_name):
    return bool(get_api_key(provider_name))


def rename_provider(old, new):
    """Rename a provider; its key in the credential store (stored under the name) moves along."""
    s = copy.deepcopy(get())
    names = [p["name"] for p in s.llm_providers]
    if old not in names:
        raise KeyError(f"no LLM provider named {old!r}")
    if new in names:
        raise ValueError(f"there is already a provider named {new!r}")
    key = get_api_key(old)
    if key:
        set_api_key(new, key)
    s.llm_providers = [{**p, "name": new} if p["name"] == old else p for p in s.llm_providers]
    if s.llm_active == old:
        s.llm_active = new
    save(s)
    if key:
        set_api_key(old, "")
    return s
