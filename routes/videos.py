# routes/videos.py (이미 있다면 전체 교체)

from flask import Blueprint, redirect, abort
from services.r2_service import generate_presigned_video_url

bp = Blueprint("videos", __name__)


@bp.route("/videos/<path:filename>")
def serve_video(filename):
    try:
        url = generate_presigned_video_url(filename)
    except Exception as e:
        print("presigned URL 생성 실패:", e)
        abort(404)
    return redirect(url)
