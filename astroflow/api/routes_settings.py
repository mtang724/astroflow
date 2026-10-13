"""Settings: paths, LLM providers (keys go to the OS credential store and never come back), connection test."""
import copy
import time
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .. import config, doctor, settings
from ..agent.llm import LLM
from .models import KeyIn, LLMTestIn, LLMTestOut, Ok, Provider, ProviderRenameIn, SettingsOut, SettingsPatch

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _out(s):
    providers = [Provider(**p, has_key=settings.has_api_key(p["name"])) for p in s.llm_providers]
    return SettingsOut(**{k: v for k, v in asdict(s).items() if k != "llm_providers"}, llm_providers=providers,
                       settings_file=settings.settings_path().as_posix(),
                       checks={"astro_root": Path(s.astro_root).is_dir(),
                               "pixinsight_exe": Path(s.pixinsight_exe).is_file(),
                               "pixinsight_scripts": Path(s.pixinsight_scripts).is_dir(),
                               "runs_dir": config.pixinsight_path_ok(config.RUNS)})


@router.get("", response_model=SettingsOut)
def get_settings():
    return _out(settings.get())


@router.patch("", response_model=SettingsOut)
def patch_settings(patch: SettingsPatch):
    s = copy.deepcopy(settings.get())          # validate on a copy: a rejected change must not linger in memory
    changes = patch.model_dump(exclude_unset=True)
    if "llm_providers" in changes:
        changes["llm_providers"] = [{k: v for k, v in p.items() if k != "has_key"} for p in changes["llm_providers"]]
        if not changes["llm_providers"]:
            raise HTTPException(400, "keep at least one LLM provider")
    if changes.get("pixinsight_exe"):       # macOS dialogs return PixInsight.app; some pick the install folder
        changes["pixinsight_exe"] = doctor.resolve_pixinsight_exe(changes["pixinsight_exe"])
    removed = {p["name"] for p in s.llm_providers}
    for k, v in changes.items():
        setattr(s, k, v)
    if s.llm_active not in {p["name"] for p in s.llm_providers}:
        raise HTTPException(400, f"llm_active {s.llm_active!r} is not one of the providers")
    settings.save(s)
    for name in removed - {p["name"] for p in s.llm_providers}:     # a deleted provider takes its key along
        settings.set_api_key(name, "")
    return _out(s)


@router.post("/providers/rename", response_model=SettingsOut)
def rename_provider(body: ProviderRenameIn):
    """Rename an LLM provider; its stored key moves to the new name."""
    new = body.new.strip()
    if not new:
        raise HTTPException(400, "the name cannot be empty")
    try:
        return _out(settings.rename_provider(body.old, new))
    except KeyError as e:
        raise HTTPException(404, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@router.get("/presets", response_model=list[Provider])
def presets():
    return [Provider(**asdict(p)) for p in settings.PROVIDER_PRESETS]


@router.put("/keys/{provider}", response_model=Ok)
def set_key(provider: str, body: KeyIn):
    settings.set_api_key(provider, body.key.strip())
    return Ok()


@router.post("/test-llm", response_model=LLMTestOut)
def test_llm(body: LLMTestIn):
    t0 = time.time()
    try:
        reply = LLM(settings.get().provider(body.provider)).ping()
        return LLMTestOut(ok=True, reply=reply[:200], seconds=round(time.time() - t0, 2))
    except Exception as e:
        return LLMTestOut(ok=False, error=f"{type(e).__name__}: {e}"[:500], seconds=round(time.time() - t0, 2))
