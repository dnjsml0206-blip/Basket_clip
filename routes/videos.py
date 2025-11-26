from flask import Blueprint, jsonify
from services.r2_service import s3, R2_BUCKET

bp = Blueprint("videos", __name__)

@bp.route("/videos_list")
def videos_list():
    resp = s3.list_objects_v2(Bucket=R2_BUCKET)

    arr = []
    for item in resp.get("Contents", []):
        key = item["Key"]
        if key.lower().endswith((".mp4", ".mov", ".avi", ".mkv")):
            arr.append(key)

    return jsonify(arr)
