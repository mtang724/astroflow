# The Python backend (astroflow.api) as a one-folder app for the desktop package: fast start, and Electron can stop
# the whole process tree. Build from the repository root:  pyinstaller packaging/backend.spec --noconfirm
# Output: dist/astroflow-backend/  (electron-builder copies it into the app's resources/backend)
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

root = Path(SPECPATH).parent  # noqa: F821 - provided by PyInstaller


def knowledge_files():
    """The knowledge base text only: never the tutorial frames/transcripts or other people's reference images."""
    keep = []
    for p in (root / "knowledge").rglob("*"):
        rel = p.relative_to(root)
        parts = rel.parts
        if not p.is_file() or "refs" in parts or any(x in parts for x in ("frames", "keyframes", "sheets")):
            continue
        if p.suffix in (".md", ".json") or (p.suffix == ".txt" and "transcript" not in p.name):
            keep.append((str(p), str(rel.parent)))
    return keep


datas = [
    (str(root / "astroflow" / "pjsr"), "astroflow/pjsr"),
    (str(root / "skills"), "skills"),
] + knowledge_files() + copy_metadata("keyring")

hiddenimports = (
    collect_submodules("uvicorn")             # loops / protocols are imported by name at run time
    + collect_submodules("websockets")
    + collect_submodules("keyring.backends")  # Windows Credential Manager / macOS Keychain
    + collect_submodules("astroflow")
)

a = Analysis(  # noqa: F821
    [str(root / "packaging" / "backend_entry.py")],
    pathex=[str(root)],
    hookspath=[str(root / "packaging" / "hooks")],
    datas=datas,
    hiddenimports=hiddenimports,
    # astropy.visualization is unused and breaks the build: its wcsaxes module calls pytest.importorskip at import
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "faster_whisper", "ctranslate2", "torch", "PySide6",
              "astropy.visualization", "astropy.samp"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="astroflow-backend",
    console=True,          # stdout carries the readiness line; Electron hides the window (windowsHide)
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="astroflow-backend", upx=False)  # noqa: F821
