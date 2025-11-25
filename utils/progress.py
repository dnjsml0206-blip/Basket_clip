import json
from pathlib import Path
from threading import Lock


class ProgressManager:
    def __init__(self, path: Path):
        self.path = path
        self.lock = Lock()

        if not self.path.exists():
            self.save({
                "progress": 0,
                "status": "idle",
                "video": "",
                "clips": [],
                "videos": [],
                "index": 0,
                "total": 0
            })

    def load(self):
        try:
            with self.lock:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            return {}

    def save(self, data):
        with self.lock:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    # 🔥 수정된 set 함수 (어떤 필드든 저장 가능)
    def set(self, percent=None, status=None, video=None, **kwargs):
        data = self.load()

        if percent is not None:
            data["progress"] = percent
        if status is not None:
            data["status"] = status
        if video is not None:
            data["video"] = video

        # 🔥 videos, index, total, clips 등 자유롭게 저장 가능
        for k, v in kwargs.items():
            data[k] = v

        self.save(data)

