from flask import Blueprint, request, jsonify, send_from_directory
from pathlib import Path
from services.export_service import ExportManager
import threading
import config

# 🔥 Blueprint 이름 고정
bp = Blueprint("export", __name__)

# 🔥 config 기준 절대경로
RESULT_DIR = config.RESULT_DIR
RESULT_DIR.mkdir(parents=True, exist_ok=True)

LOCAL_VIDEOS = config.LOCAL_VIDEOS

export_manager = ExportManager()


@bp.route("/export", methods=["POST"])
def export_video():
    data = request.get_json()
    video = data["video"]
    clips = data["clips"]

    job_id = export_manager.create_job(video, clips)

    # 🔥 결과 파일 절대경로
    output = RESULT_DIR / f"highlight_{job_id}.mp4"

    # 🔥 백그라운드 ffmpeg 실행
    threading.Thread(
        target=export_manager.worker,
        args=(job_id, LOCAL_VIDEOS / video, output),
        daemon=True
    ).start()

    # 프론트에서 /results/highlight_xxx.mp4 로 접근할 수 있도록 전송
    return jsonify({
        "job_id": job_id,
        "file": f"/results/highlight_{job_id}.mp4"
    })


@bp.route("/export_progress")
def export_progress():
    job_id = request.args.get("job_id")
    return jsonify(export_manager.jobs.get(job_id))


@bp.route("/export_stop", methods=["POST"])
def export_stop():
    job_id = request.json.get("job_id")
    export_manager.stop(job_id)
    return jsonify({"message": "stopping"})


# 🔥 최종 결과 파일 제공
@bp.route("/results/<path:filename>")
def serve_result_file(filename):
    return send_from_directory(RESULT_DIR, filename)
