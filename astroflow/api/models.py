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
    filter_class: Literal["osc_broadband", "osc_multiband"] = "osc_broadband"


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
