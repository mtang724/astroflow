# Replaces pyinstaller-hooks-contrib's astropy hook. astroflow only uses astropy.io.fits, and importing every astropy
# submodule breaks the build (astropy.visualization.wcsaxes calls pytest.importorskip at import time, whose Skipped
# exception escapes PyInstaller's error handling).
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

SKIP = (".tests", "astropy.visualization", "astropy.samp", "astropy.conftest")

datas = collect_data_files("astropy", excludes=["**/tests/**"])
datas += [p for p in collect_data_files("astropy", include_py_files=True, excludes=["**/tests/**"])
          if p[0].endswith(("_parsetab.py", "_lextab.py"))]          # unit / coordinate parsers load these as files
datas += copy_metadata("astropy") + copy_metadata("numpy")
hiddenimports = collect_submodules("astropy", filter=lambda name: not any(s in name for s in SKIP))
hiddenimports += ["numpy.lib.recfunctions"]
