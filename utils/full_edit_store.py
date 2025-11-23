# utils/full_edit_store.py

import json
from pathlib import Path

SESSION_DIR = Path("results/full_edits")
SESSION_DIR.mkdir(parents=True, exist_ok=True)


def _session_file(left_video: str, right_video: str) -> Path:
    # 좌/우 조합 별로 하나의 JSON 파일
    safe = f"{left_video}__{right_video}.json"
    # 윈도우에서 문제될 수 있는 문자 있으면 더 치환해도 됨
    return SESSION_DIR / safe


def save_full_edit(left_video: str, right_video: str, segments):
    f = _session_file(left_video, right_video)
    data = {
        "left_video": left_video,
        "right_video": right_video,
        "segments": segments,
    }
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_full_edit(left_video: str, right_video: str):
    f = _session_file(left_video, right_video)
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return data.get("segments", [])
    except Exception:
        return []
