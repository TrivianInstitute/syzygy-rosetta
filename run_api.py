from __future__ import annotations

import importlib.util
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent
MAIN_PATH = ROOT / "main.py"


def validate_main_module() -> None:
    if not MAIN_PATH.exists():
        raise FileNotFoundError(
            f"Expected FastAPI module at {MAIN_PATH}, but it was not found. "
            "Ensure main.py exists in the repository root."
        )

    spec = importlib.util.spec_from_file_location("syzygy_rosetta_main", MAIN_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create import spec for {MAIN_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    app = getattr(module, "app", None)
    if app is None:
        raise AttributeError("main.py loaded, but no `app` object was found.")


if __name__ == "__main__":
    validate_main_module()
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        app_dir=str(ROOT),
        reload_dirs=[str(ROOT)],
    )