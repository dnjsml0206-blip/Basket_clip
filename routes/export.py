from flask import Blueprint, request, jsonify, send_file, abort
from pathlib import Path
from services.export_service import ExportManager
import threading
import config
import os

bp = Blueprint("export", __name__)

# 결과 임시 저장 디렉터리
RESULT_DIR = config.TMP_DIR / "results"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

export_manager = ExportManager()


@bp.route("/export", methods=["POST"])
def export_video():
    data = request.get_json()
    video = data["video"]
    clips = data["clips"]

    job_id = export_manager.create_job(video, clips)

    output = RESULT_DIR / f"highlight_{job_id}.mp4"

    threading.Thread(
        target=export_manager.worker,
        args=(job_id, video, output),
        daemon=True
    ).start()

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


# 🔥 결과 파일 제공 후 바로 삭제 (영구 저장 X)
@bp.route("/results/<path:filename>")
def serve_result_file(filename):
    full = RESULT_DIR / filename
    if not full.exists():
        abort(404)

    # send_file 후 파일 삭제
    resp = send_file(full, as_attachment=True, download_name=filename)
    try:
        os.remove(full)
    except Exception:
        pass
    return resp
