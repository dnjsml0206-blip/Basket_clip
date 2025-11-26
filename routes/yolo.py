from flask import Blueprint, request, jsonify
from services.yolo_service import YoloHighlighter
from utils.progress import ProgressManager
from services.coord_service import BasketCoordService
from services.r2_service import download_to_path
import threading
import json
import time
from pathlib import Path
import tempfile

bp = Blueprint("yolo", __name__)

progress = ProgressManager(Path("progress.json"))
coords = BasketCoordService(Path("basket_coords.json"))

# =======================================
# 🔥 단일
# =======================================
@bp.route("/process_yolo")
def process_yolo():
    video = request.args.get("video")
    if not video:
        return "no video", 400

    # R2 → temp 영상 다운로드
    tmp_path = Path(tempfile.gettempdir()) / f"yolo_{video}"
    download_to_path(video, tmp_path)

    progress.set(0, "running", video)

    yolo = YoloHighlighter("mixup100epo.pt", progress, coords)
    threading.Thread(target=yolo.run, args=(tmp_path,), daemon=True).start()

    return jsonify({"message": "YOLO started"})


# =======================================
# 🔥 Multi YOLO 분석
# =======================================
@bp.route("/process_yolo_multi", methods=["POST"])
def process_yolo_multi():
    data = request.get_json()
    videos = data.get("videos")

    if not videos:
        return jsonify({"error": "no videos"}), 400

    progress.set(
        0, "multi_running",
        video=None,
        videos=videos,
        index=0,
        total=len(videos)
    )

    threading.Thread(target=_multi_worker, daemon=True).start()
    return jsonify({"message": "multi started"})


def _multi_worker():
    while True:
        p = progress.load()
        videos = p["videos"]
        idx = p["index"]
        total = p["total"]

        if idx >= total:
            progress.set(100, "done_all", videos=videos, index=idx, total=total)
            return

        video_name = videos[idx]
        tmp_path = Path(tempfile.gettempdir()) / f"yolo_{video_name}"

        download_to_path(video_name, tmp_path)

        progress.set(0, "running", video_name, videos=videos, index=idx, total=total)

        yolo = YoloHighlighter("mixup100epo.pt", progress, coords)
        yolo.run(tmp_path)

        p = progress.load()
        if p["status"] == "stopped":
            return

        progress.set(0, "multi_running", videos=videos, index=idx+1, total=total)
        time.sleep(0.2)


@bp.route("/progress_multi")
def progress_multi():
    return jsonify(progress.load())


@bp.route("/stop", methods=["POST"])
def stop():
    p = progress.load()
    progress.set(
        p["progress"], "stopped",
        video=p["video"],
        videos=p.get("videos", []),
        index=p.get("index", 0),
        total=p.get("total", 1)
    )
    return jsonify({"message": "stopped"})
