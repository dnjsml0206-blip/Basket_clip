from flask import Blueprint, request, jsonify
from pathlib import Path
from services.yolo_service import YoloHighlighter
from utils.progress import ProgressManager
from services.coord_service import BasketCoordService
from services.r2_service import download_to_path
import threading
import config
import time
import json

bp = Blueprint("yolo", __name__)

progress = ProgressManager(Path("progress.json"))
coords = BasketCoordService(Path("basket_coords.json"))


# ===============================
# 단일 영상 YOLO (기존 유지, 내부는 R2 사용)
# ===============================
@bp.route("/process_yolo")
def process_yolo():
    video = request.args.get("video")
    if not video:
        return "영상 파일을 지정해주세요.", 400

    # multi와 형식 맞추기 위해 videos=[video] 형태로 그대로 사용해도 됨
    progress.set(0, "running", video, videos=[video], index=0, total=1, clips=[])

    def worker():
        _run_single_yolo(video, 0, 1)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"message": "YOLO Started"})


# ===============================
# 🔥 Multi YOLO 분석
# ===============================
@bp.route("/process_yolo_multi", methods=["POST"])
def process_yolo_multi():
    data = request.get_json()
    videos = data.get("videos")

    if not videos or not isinstance(videos, list):
        return jsonify({"error": "videos must be a list"}), 400

    progress.set(
        0,
        "multi_running",
        video=None,
        videos=videos,
        index=0,
        total=len(videos),
        clips=[]
    )

    threading.Thread(target=_multi_worker, daemon=True).start()

    return jsonify({"message": "multi yolo started", "count": len(videos)})


def _run_single_yolo(video_name: str, index: int, total: int):
    """
    R2 → TMP_DIR 로 다운로드 → YOLO 실행 → tmp 삭제
    """
    # 1) R2에서 다운로드
    from config import TMP_DIR
    from services.r2_service import download_to_path

    tmp_path = TMP_DIR / f"yolo_{video_name}"
    key = f"videos/{video_name}"

    try:
        print(f"R2에서 다운로드: {key} -> {tmp_path}")
        download_to_path(key, tmp_path)
    except Exception as e:
        print("R2 다운로드 실패:", e)
        progress.set(
            0, f"error_download:{video_name}",
            video=video_name,
            videos=[video_name],
            index=index,
            total=total
        )
        return

    # 2) YOLO 수행
    yolo = YoloHighlighter("mixup100epo.pt", progress, coords)
    try:
        yolo.run(tmp_path)
    finally:
        # 3) 임시 파일 삭제
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _multi_worker():
    while True:
        p = progress.load()
        videos = p.get("videos", [])
        index = p.get("index", 0)
        total = p.get("total", 1)

        if index >= total:
            progress.set(100, "done_all", video=None, videos=videos, index=total, total=total)
            return

        video_name = videos[index]
        print(f"🔥 ({index+1}/{total}) 영상 분석 시작 → {video_name}")

        # 상태 running 으로 변경
        progress.set(
            0, "running",
            video=video_name,
            videos=videos,
            index=index,
            total=total
        )

        # 실제 분석
        _run_single_yolo(video_name, index, total)

        # 중지 체크
        p = progress.load()
        if p.get("status") == "stopped":
            print("🟥 Multi YOLO 중지됨")
            return

        # 다음 영상 준비
        progress.set(
            0,
            "multi_running",
            video=None,
            videos=videos,
            index=index + 1,
            total=total,
            clips=[]
        )

        time.sleep(0.3)


# ===============================
# 🔥 Multi progress 상태 반환
# ===============================
@bp.route("/progress_multi")
def progress_multi():
    p = progress.load()

    return jsonify({
        "progress": p.get("progress", 0),
        "status": p.get("status", ""),
        "current_video": p.get("video"),
        "current_index": p.get("index", 0),
        "total": p.get("total", 1),
        "videos": p.get("videos", []),
        "clips": p.get("clips", []),
    })


# ===============================
# 🔥 중지
# ===============================
@bp.route("/stop", methods=["POST"])
def stop():
    p = progress.load()
    progress.set(
        p.get("progress", 0),
        "stopped",
        video=p.get("video", ""),
        videos=p.get("videos", []),
        index=p.get("index", 0),
        total=p.get("total", 1)
    )
    return jsonify({"message": "stopped"})
