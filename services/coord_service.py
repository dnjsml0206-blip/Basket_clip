import json
from pathlib import Path


class BasketCoordService:
    def __init__(self, json_path: Path):
        self.json_path = json_path

        if not self.json_path.exists():
            self.json_path.write_text("{}", encoding="utf-8")

    # 골대 좌표 저장
    def save(self, video_name: str, coords: dict):
        """coords = {x1, y1, x2, y2} 형태"""
        try:
            data = json.loads(self.json_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

        data[video_name] = {
            "x1": coords["x1"],
            "y1": coords["y1"],
            "x2": coords["x2"],
            "y2": coords["y2"],
        }

        self.json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # 골대 좌표 불러오기
    def load(self, video_name: str):
        try:
            data = json.loads(self.json_path.read_text(encoding="utf-8"))
        except Exception:
            return None

        return data.get(video_name)
