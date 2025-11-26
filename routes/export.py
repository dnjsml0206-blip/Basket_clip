from flask import Blueprint, request, jsonify, send_from_directory
from pathlib import Path
from services.export_service import ExportManager
import threading
import config

bp = Blueprint("export", __name__)

RESULT_DIR = config.RESULT_DIR
RESULT_DIR.mkdir(exist_ok=True)

export_manager = ExportManager()


@bp.route("/export", methods=["POST"])
def export_video():
    data = request.get_json()
    video = data["video"]
    clips = data["clips"]

    job_id = export_manager.create_job(video, clips)

    out_path = RESULT_DIR / f"highlight_{job_id}.mp4"

    threading.Thread(
        target=export_manager.worker,
        args=(job_id, video, out_path),
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


@bp.route("/results/<path:filename>")
def serve_result(filename):
    return send_from_directory(RESULT_DIR, filename)
