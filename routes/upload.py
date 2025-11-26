from flask import Blueprint, request, jsonify
from services.r2_service import r2_upload_bytes, r2_list_videos

bp = Blueprint("upload", __name__)

@bp.route("/upload_video", methods=["POST"])
def upload_video():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "no files"}), 400

    saved = []
    for f in files:
        filename = f.filename

        ok = r2_upload_bytes(f, filename)
        if not ok:
            return jsonify({"error": f"failed to upload {filename}"}), 500

        saved.append(filename)

    return jsonify({"message": "uploaded", "files": saved})


# 🔥 R2 영상 목록 반환
@bp.route("/videos_list")
def videos_list():
    return jsonify(r2_list_videos())
