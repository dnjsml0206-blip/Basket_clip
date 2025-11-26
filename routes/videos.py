from flask import Blueprint, Response, abort
from services.r2_service import s3, R2_BUCKET
import mimetypes

bp = Blueprint("videos", __name__)

# 기존 videos_list는 그대로 두고 이걸 아래에 추가
@bp.route("/videos/<path:filename>")
def serve_video(filename):
    try:
        obj = s3.get_object(Bucket=R2_BUCKET, Key=filename)
        data = obj["Body"].read()

        mime, _ = mimetypes.guess_type(filename)
        mime = mime or "video/mp4"

        return Response(data, mimetype=mime)

    except Exception as e:
        print("❌ Failed to load video from R2:", filename, e)
        abort(404)
