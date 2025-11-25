from flask import Blueprint, request, jsonify
from services.r2_service import upload_fileobj, list_videos_prefix

bp = Blueprint("upload", __name__)


@bp.route("/upload_video", methods=["POST"])
def upload_video():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "no files"}), 400

    saved = []
    try:
        for f in files:
            filename = f.filename
            if not filename:
                continue

            key = f"videos/{filename}"
            upload_fileobj(f.stream, key)
            saved.append(filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"message": "uploaded", "files": saved})


# 🔥 R2 /videos/ 목록 반환
@bp.route("/videos_list")
def videos_list():
    arr = list_videos_prefix("videos/")
    return jsonify(arr)
