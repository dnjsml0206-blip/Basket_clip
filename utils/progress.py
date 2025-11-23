import json
from pathlib import Path


class ProgressManager:
    def __init__(self, json_path: Path):
        self.json_path = json_path

        if not self.json_path.exists():
            self.json_path.write_text("{}", encoding="utf-8")

    def set(self, percent: int, status: str, video: str, clips=None):
        data = {
            "progress": percent,   # 👈 여기
            "status": status,
            "video": video
        }
        
        if clips is not None:
            data["clips"] = clips

        self.json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def load(self):
        try:
            return json.loads(self.json_path.read_text(encoding="utf-8"))
        except Exception:
            return {"progress": 0, "status": "none"}  # 👈 여기

