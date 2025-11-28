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
    # 🔥 수정: video_name 인자 추가
    threading.Thread(target=yolo.run, args=(tmp_path, video), daemon=True).start()

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
        # 🔥 수정: video_name 인자 추가
        yolo.run(tmp_path, video_name)

        p = progress.load()
        if p["status"] == "stopped":
            return

        progress.set(0, "multi_running", videos=videos, index=idx+1, total=total)
        time.sleep(0.2)


@bp.route("/progress_multi")
def progress_multi():
    data = progress.load()

    # index.html은 current_video를 기대함 → 필드 맞춰줌
    if "current_video" not in data:
        # progress.json 안에 video 필드가 이미 있음
        data["current_video"] = data.get("video")

    return jsonify(data)


@bp.route("/stop", methods=["POST"])
def stop():
    job_id = request.json.get("job_id")

    # progress.json 읽기
    try:
        with open("progress.json", "r") as f:
            p = json.load(f)
    except:
        p = {}

    # 기본값 안전하게 설정
    progress = p.get("progress", 0)
    status = p.get("status", "stopped")
    video = p.get("video", None)

    # 업데이트 처리
    update_progress(
        job_id,
        progress,
        "stopped",
        video=video
    )

    return jsonify({"status": "stopped"})