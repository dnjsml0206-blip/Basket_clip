from flask import Blueprint, request, jsonify
import os
from services.r2_service import s3, R2_BUCKET

bp = Blueprint("delete_video", __name__)

UPLOAD_DIR = "upload"

def delete_r2(key):
    try:
        s3.delete_object(Bucket=R2_BUCKET, Key=key)
        print("🗑 R2 삭제:", key)
    except Exception as e:
        print("R2 삭제 실패:", e)

@bp.route("/delete_video", methods=["POST"])
def delete_video():
    filename = request.json.get("filename")
    if not filename:
        return jsonify({"error": "No filename"}), 400

    # 로컬 삭제
    local_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(local_path):
        try:
            os.remove(local_path)
        except:
            pass

    # R2 삭제
    delete_r2(filename)

    return jsonify({"status": "ok"})
