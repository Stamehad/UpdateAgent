from pathlib import Path
import os

def resolve_storage_dir(storage_dir: str) -> Path:
    base = Path(__file__).resolve().parents[2]  # project root (…/stay_up_to_date_agent)
    # allow ./data relative to project and ~ expansion
    p = Path(os.path.expanduser(storage_dir))
    if not p.is_absolute():
        p = (base / p).resolve()
    return p

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)