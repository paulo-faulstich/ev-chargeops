import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.main import app

target = Path(__file__).parents[3] / "packages" / "api-client" / "openapi.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
