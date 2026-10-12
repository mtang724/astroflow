"""Write the backend's OpenAPI schema; the desktop app generates its TypeScript API types from it (npm run gen:api)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astroflow.api.app import create_app  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
out.write_text(json.dumps(create_app("schema-only").openapi(), indent=1), encoding="utf-8")
print(f"wrote {out}")
