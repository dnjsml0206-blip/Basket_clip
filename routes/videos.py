from flask import Blueprint, Response, request, abort
from services.r2_service import s3, R2_BUCKET
import mimetypes

bp = Blueprint("videos", __name__)


@bp.route("/videos/<path:filename>")
def serve_video(filename):
    try:
        # 파일 전체 메타 정보 얻기
        head = s3.head_object(Bucket=R2_BUCKET, Key=filename)
        file_size = head["ContentLength"]

        # MIME 타입 결정
        mime, _ = mimetypes.guess_type(filename)
        mime = mime or "video/mp4"

        range_header = request.headers.get("Range")
        
        if range_header:
            # "bytes=1000-2000" 형태
            bytes_range = range_header.replace("bytes=", "").split("-")
            start = int(bytes_range[0])
            end = int(bytes_range[1]) if bytes_range[1] else file_size - 1

            length = end - start + 1

            # R2에서 부분 범위만 가져오기
            obj = s3.get_object(
                Bucket=R2_BUCKET,
                Key=filename,
                Range=f"bytes={start}-{end}"
            )

            data = obj["Body"].read()

            # 206 Partial Content 응답
            rv = Response(
                data,
                status=206,
                mimetype=mime,
                direct_passthrough=True
            )
            rv.headers.add("Content-Range", f"bytes {start}-{end}/{file_size}")
            rv.headers.add("Accept-Ranges", "bytes")
            rv.headers.add("Content-Length", str(length))
            return rv

        else:
            # Range 요청 없음 → 전체 파일 제공
            obj = s3.get_object(Bucket=R2_BUCKET, Key=filename)
            data = obj["Body"].read()

            rv = Response(
                data,
                status=200,
                mimetype=mime,
                direct_passthrough=True
            )
            rv.headers.add("Content-Length", str(file_size))
            rv.headers.add("Accept-Ranges", "bytes")
            return rv

    except Exception as e:
        print("❌ Failed to load video from R2:", filename, e)
        abort(404)
