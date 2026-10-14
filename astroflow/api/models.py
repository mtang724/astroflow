"""Request and response models: the API contract the TypeScript client is generated from (desktop/src/renderer/
src/api/schema.d.ts via openapi-typescript)."""
from typing import Any, Literal

from pydantic import BaseModel, Field


class Ok(BaseModel):
    ok: bool = True


# ----------------------------------------------------------------------------------------------- settings
class Provider(BaseModel):
    name: str
    base_url: str
    planner_model: str
    vision_model: str = ""
    needs_key: bool = True
    tools: bool = True
    has_key: bool = False                  # response only: the key itself never leaves the backend


class SettingsOut(BaseModel):
    astro_root: str
    pixinsight_exe: str
    pixinsight_scripts: str
    runs_dir: str
    llm_active: str
    llm_providers: list[Provider]
    equipment: dict[str, Any]
    preferences: dict[str, Any]
    extra_targets: list[str]
    settings_file: str
    checks: dict[str, bool]                # do the configured paths exist?
    language: Literal["zh", "en"]          # the language in use (preferences.language, "auto" resolved)


class SettingsPatch(BaseModel):
    astro_root: str | None = None
    pixinsight_exe: str | None = None
    pixinsight_scripts: str | None = None
    runs_dir: str | None = None
    llm_active: str | None = None
    llm_providers: list[Provider] | None = None
    equipment: dict[str, Any] | None = None
    preferences: dict[str, Any] | None = None
    extra_targets: list[str] | None = None


class KeyIn(BaseModel):
    key: str = Field("", description="empty removes the stored key")


class ProviderRenameIn(BaseModel):
    old: str
    new: str


class LLMTestIn(BaseModel):
    provider: str


class LLMTestOut(BaseModel):
    ok: bool
    reply: str = ""
    error: str = ""
    seconds: float = 0


# ----------------------------------------------------------------------------------------------- setup check
class SetupStep(BaseModel):
    text: str
    code: list[str] = []                   # lines to copy (repository addresses)


class SetupLink(BaseModel):
    label: str
    url: str


class SetupAction(BaseModel):
    kind: Literal["apply", "create_folder", "pick_folder", "pick_file", "open_settings"]
    label: str
    setting: str | None = None             # the setting a picked or created path goes to
    value: dict[str, str] | None = None    # apply: the settings to save; create_folder: {setting: path}
    tab: str | None = None                 # open_settings: the tab to show


class SetupCheck(BaseModel):
    id: str
    title: str
    level: Literal["required", "recommended", "optional"]
    status: Literal["ok", "warn", "missing", "unknown"]
    summary: str
    steps: list[SetupStep] = []
    links: list[SetupLink] = []
    actions: list[SetupAction] = []


class SetupReport(BaseModel):
    ready: bool                            # nothing required is missing: stacking and processing can run
    checks: list[SetupCheck]
    notes: list[str] = []


# ----------------------------------------------------------------------------------------------- targets
class TargetSummary(BaseModel):
    name: str
    path: str
    night: str
    nights: list[str] = []                 # the nights it holds (several: a multi-night target)
    staged: bool = False                   # in In Processing (can be archived to Processed)
    lights: int
    darks: int
    bias: int
    flats: int
    master: bool                           # the recipe's start image exists (comets: the nucleus-aligned stack)
    registered: bool = False               # WBPP's registered frames exist
    type: str
    recipe: str | None
    stages_done: list[str]
    finished: bool
    filter_class: str | None = None


class StageInfo(BaseModel):
    stage: str
    done: bool
    seconds: float | None = None
    previews: list[str]
    overrides: dict[str, Any] | None = None


class ReferenceImage(BaseModel):
    group: str
    title: str | None = None
    author: str | None = None
    likes: int | None = None
    url: str | None = None
    file: str


class TargetDetail(TargetSummary):
    session: dict[str, Any]
    acquisition: dict[str, Any]
    calibration_warnings: list[str]
    catalogue: dict[str, Any] | None = None
    stages: list[StageInfo]
    finals: list[str]
    references: list[ReferenceImage]
    report: str | None = None


class PathIn(BaseModel):
    path: str


class RecipeIn(BaseModel):
    path: str
    recipe: str


class SessionIn(BaseModel):
    path: str
    filter: str = ""
    filter_class: Literal["osc_broadband", "osc_multiband", "osc_so"] = "osc_broadband"


# ----------------------------------------------------------------------------------------------- recipes
class Field_(BaseModel):
    key: str
    value: Any
    type: Literal["bool", "int", "float", "str"]
    default: Any = None
    edited: bool = False


class Step(BaseModel):
    id: str
    op: str
    optional: bool
    fields: list[Field_]


class Stage(BaseModel):
    stage: str
    steps: list[Step]


class ParamIn(BaseModel):
    path: str
    stage: str
    step_id: str
    key: str
    value: Any = None                      # null removes the edit


# ----------------------------------------------------------------------------------------------- jobs / actions
class Job(BaseModel):
    id: str
    kind: str
    title: str
    target: str | None = None
    state: Literal["queued", "running", "done", "failed", "cancelled"]
    progress: str = ""                     # for people: where the job is and what it is doing
    stage: str | None = None               # pipeline stage being run (the pipeline view marks it)
    error: str | None = None
    queued_at: float
    started_at: float | None = None
    finished_at: float | None = None


class JobDetail(Job):
    log: list[str]
    result: Any = None


class ProcessIn(BaseModel):
    path: str
    recipe: str | None = None
    start: str | None = Field(None, description="run this stage and everything after it")
    stage: str | None = Field(None, description="run only this stage")


class CometIn(BaseModel):
    path: str
    reuse_sxt: bool = False


class CropIn(BaseModel):
    path: str
    width: int
    height: int
    cx: float | None = None
    cy: float | None = None


class OrganizeIn(BaseModel):
    sources: list[str] | None = Field(None, description="folders to import; none: new folders put in the data root")
    copy_lights: bool = True               # False: lights are moved (calibration frames are always copied)


class FrameSet(BaseModel):
    count: int
    detail: str                            # "12 × 300 s · ISO 3200"
    origin: Literal["import", "library", "target", "mixed", ""]   # where the frames come from


class OrganizeRow(BaseModel):
    kind: Literal["target", "fill", "library"]   # a target's frames | an existing target completed | the library
    target: str
    night: str
    dest: str
    exists: bool = False                   # the destination folder is there already (imported before)
    sources: list[str]
    lights: FrameSet
    darks: FrameSet
    bias: FrameSet
    flats: FrameSet
    to_copy: int                           # files not at their destination yet
    warnings: list[str]


class OrganizePlan(BaseModel):
    rows: list[OrganizeRow]
    imported: dict[str, int]               # frames taken from the chosen folders, by kind
    notes: list[str]                       # files that were not used and why


class ReferencesIn(BaseModel):
    path: str
    refresh: bool = False


# ----------------------------------------------------------------------------------------------- frame check
class FrameRow(BaseModel):
    name: str                              # path under Light/ (multi-night: NIGHT_<night>/<file>)
    path: str
    excluded: bool
    measured: bool
    error: str | None = None
    thumb: str
    time: str | None = None
    exptime: float | None = None
    stars: int | None = None
    fwhm: float | None = None              # arcsec when the pixel scale is known, else pixels (fwhm_unit)
    ecc: float | None = None
    background: float | None = None        # median sky, fraction of the sensor's full scale
    flags: list[str]                       # why the frame looks worse than the others


class FrameSummary(BaseModel):
    total: int
    measured: int
    excluded: int
    suspicious: int
    stars: float | None = None             # medians of the kept frames
    fwhm: float | None = None
    ecc: float | None = None
    background: float | None = None


class FrameReport(BaseModel):
    frames: list[FrameRow]
    fwhm_unit: Literal["arcsec", "px"]
    scale: float | None = None
    restack: bool                          # frames were excluded or restored after the master was made
    summary: FrameSummary


class FrameCheckIn(BaseModel):
    path: str
    force: bool = False                    # measure every frame again, not only new ones


class FramesIn(BaseModel):
    path: str
    names: list[str]


# ----------------------------------------------------------------------------------------------- disk space
class StoragePart(BaseModel):
    id: Literal["frames", "masters", "wbpp_frames", "checkpoints", "results"]
    bytes: int
    files: int
    removable: bool


class StorageUsage(BaseModel):
    path: str
    name: str
    night: str
    nights: list[str] = []
    total: int
    removable: int
    parts: list[StoragePart]


class CleanupIn(BaseModel):
    paths: list[str]


class ArchiveIn(BaseModel):
    path: str
    clean: bool = False                    # also delete what can be made again


# ----------------------------------------------------------------------------------------------- process everything
class BatchRow(BaseModel):
    path: str
    name: str
    night: str
    nights: list[str] = []
    steps: list[Literal["stack", "comet", "process"]]
    skip: str | None = None                # why nothing will be done


class BatchIn(BaseModel):
    paths: list[str]


class BatchOut(BaseModel):
    jobs: list[Job]
    skipped: list[BatchRow]


# ----------------------------------------------------------------------------------------------- several nights
class NightInfo(BaseModel):
    night: str
    path: str
    lights: int


class NightsOut(BaseModel):
    name: str
    nights: list[NightInfo]                # the target's nights in In Processing
    combined: str | None = None            # its multi-night target, when made
    included: list[str] = []               # the nights that one holds
    missing: list[str] = []                # of those, nights whose folders are gone (their frames stay in it)


class CombineIn(BaseModel):
    nights: list[str]                      # night target folders (same target name)


# ----------------------------------------------------------------------------------------------- styles
class Preset(BaseModel):
    name: str
    recipe: str
    source: str | None = None              # the target it was saved from
    saved: str | None = None
    edits: int


class PresetIn(BaseModel):
    path: str
    name: str


# ----------------------------------------------------------------------------------------------- sharing
Aspect = Literal["3:4", "4:5", "1:1", "16:9", "original"]


class ShareInfo(BaseModel):
    source: str | None                     # the finished image (None: not processed yet)
    width: int = 0
    height: int = 0
    caption: list[str] = []                # suggested lines
    signature: str = ""                    # the one used last time
    crops: dict[str, list[float]] = {}     # default crop per aspect, fractions [x0, y0, x1, y1]


class ShareSpec(BaseModel):
    path: str
    aspect: Aspect = "3:4"
    crop: list[float] | None = Field(None, min_length=4, max_length=4)
    caption: list[str] = []
    signature: str = ""


class ShareOut(BaseModel):
    file: str
    width: int
    height: int


# ----------------------------------------------------------------------------------------------- agent
class AgentCreateIn(BaseModel):
    target: str | None = None
    provider: str | None = None


class AgentEvent(BaseModel):
    kind: str
    data: dict[str, Any]
    t: float


class AgentSessionOut(BaseModel):
    sid: str
    target: str | None
    provider: str
    model: str
    vision: bool
    native_tools: bool
    job_id: str | None
    events: list[AgentEvent]


class AgentMessageIn(BaseModel):
    text: str
