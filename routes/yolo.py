from flask import Blueprint, request, jsonify, session
from pathlib import Path
from services.yolo_service import YoloHighlighter
from utils.progress import ProgressManager
from services.coord_service import BasketCoordService
import threading
import config
import json

LOCAL_VIDEOS = config.LOCAL_VIDEOS

bp = Blueprint("yolo", __name__)

progress = ProgressManager(Path("progress.json"))
coords = BasketCoordService(Path("basket_coords.json"))


@bp.route("/process_yolo")
def process_yolo():
    video = request.args.get("video")
    if not video:
        return "영상 파일을 지정해주세요.", 400

    progress.set(0, "running", video)

    yolo = YoloHighlighter("mixup100epo.pt", progress, coords)

    threading.Thread(target=yolo.run, args=(LOCAL_VIDEOS / video,)).start()

    return jsonify({"message": "YOLO Started"})


@bp.route("/progress")
def get_progress():
    p = progress.load()
    
    # YOLO 분석 완료 시 세션에 클립 저장
    if p.get("status") == "done":
        session["clips"] = p.get("clips", [])
        session["video"] = p.get("video")

    return jsonify({
        "progress": p.get("progress", 0),
        "status": p.get("status", "idle"),
        "video": p.get("video"),
        "clips": p.get("clips", [])
    })



# 🔥 추가: 분석 중지용 (beforeunload에서 호출)
@bp.route("/stop", methods=["POST"])
def stop():
    p = progress.load()
    # 지금 진행률 유지하면서 상태만 stopped로
    progress.set(p.get("percent", 0), "stopped", p.get("video", ""))
    return jsonify({"message": "stopped"})
