import json
from pathlib import Path
import config

SYNC_FILE = Path(config.WORK_DIR) / "sync_offsets.json"


def load_sync():
    """싱크 저장 파일 로드"""
    if SYNC_FILE.exists():
        try:
            return json.loads(SYNC_FILE.read_text(encoding="utf-8"))
        except:
            return {}
    return {}


def save_sync(data: dict):
    print("[DEBUG] save_sync called")
    print("[DEBUG] writing to:", SYNC_FILE)
    SYNC_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(SYNC_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_sync(left: str, right: str):
    """싱크 정보 가져오기"""
    key = f"{left}__{right}"
    db = load_sync()
    return db.get(key)


def set_sync(left: str, right: str, offset: float):
    """싱크 정보 저장"""
    key = f"{left}__{right}"
    db = load_sync()
    db[key] = float(offset)
    save_sync(db)
    return True

