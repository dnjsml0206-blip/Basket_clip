import boto3
import os
import uuid
from flask import Response
from pathlib import Path
import tempfile
import mimetypes

# R2 API 환경변수
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")

# Cloudflare R2 S3 Endpoint
R2_ENDPOINT = "https://bf1e90f22c8c93d804483db67dd5b40a.r2.cloudflarestorage.com"

# 버킷명
R2_BUCKET = "basket"

# boto3 클라이언트
s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
)

# -----------------------------------------
# 🔥 1) R2 → temp 파일 다운로드
# -----------------------------------------
def download_to_path(key: str, dest_path: Path):
    """
    Cloudflare R2 파일을 dest_path 로 다운로드
    """
    try:
        s3.download_file(R2_BUCKET, key, str(dest_path))
        return True
    except Exception as e:
        print("❌ download_to_path ERROR:", e)
        return False


# -----------------------------------------
# 🔥 2) R2 → 임시 파일 다운로드 (basket.py에서 사용)
# -----------------------------------------
def r2_download_temp_frame(video_name: str):
    try:
        ext = os.path.splitext(video_name)[1]
        tmp_path = Path(tempfile.gettempdir()) / f"{uuid.uuid4().hex}{ext}"

        s3.download_file(R2_BUCKET, video_name, str(tmp_path))
        return tmp_path
    except Exception as e:
        print("❌ r2_download_temp_frame ERROR:", e)
        return None


# -----------------------------------------
# 🔥 3) R2 영상 스트리밍 (Range 지원)
# -----------------------------------------
def r2_stream_video(filename, request):
    try:
        obj = s3.head_object(Bucket=R2_BUCKET, Key=filename)
        file_size = obj["ContentLength"]

        mime = mimetypes.guess_type(filename)[0] or "video/mp4"
        range_header = request.headers.get("Range")

        # ---- Range 요청 ----
        if range_header:
            byte1, byte2 = 0, None
            parts = range_header.replace("bytes=", "").split("-")
            if parts[0]:
                byte1 = int(parts[0])
            if len(parts) > 1 and parts[1]:
                byte2 = int(parts[1])

            byte2 = byte2 or (file_size - 1)
            length = byte2 - byte1 + 1

            resp = s3.get_object(
                Bucket=R2_BUCKET,
                Key=filename,
                Range=f"bytes={byte1}-{byte2}",
            )

            def stream():
                yield from resp["Body"].iter_chunks()

            r = Response(stream(), status=206, mimetype=mime)
            r.headers.add("Content-Range", f"bytes {byte1}-{byte2}/{file_size}")
            r.headers.add("Accept-Ranges", "bytes")
            r.headers.add("Content-Length", str(length))
            return r

        # ---- 전체 다운로드 ----
        resp = s3.get_object(Bucket=R2_BUCKET, Key=filename)

        def full_stream():
            yield from resp["Body"].iter_chunks()

        r = Response(full_stream(), mimetype=mime)
        r.headers.add("Content-Length", str(file_size))
        return r

    except Exception as e:
        print("❌ r2_stream_video ERROR:", e)
        return None

# -----------------------------------------
# 🔥 3) 업로드용 R2 파일 업로드
# -----------------------------------------

def r2_upload_file(local_path: Path, r2_filename: str):
    """
    로컬 파일 local_path → R2 bucket/basket/r2_filename 로 업로드
    """
    try:
        s3.upload_file(
            Filename=str(local_path),
            Bucket=R2_BUCKET,
            Key=r2_filename
        )
        return True
    except Exception as e:
        print("❌ r2_upload_file ERROR:", e)
        return False


# -----------------------------------------
# 🔥 4) 메모리 파일 업로드 (Flask FileStorage 직접 업로드)
# -----------------------------------------

def r2_upload_bytes(file_storage, r2_filename: str):
    """
    Flask 파일 업로드 객체(file_storage) → R2에 직접 업로드
    """
    try:
        s3.put_object(
            Bucket=R2_BUCKET,
            Key=r2_filename,
            Body=file_storage.read()
        )
        return True
    except Exception as e:
        print("❌ r2_upload_bytes ERROR:", e)
        return False


# -----------------------------------------
# 🔥 5) R2 파일 리스트 조회
# -----------------------------------------

def r2_list_videos():
    try:
        resp = s3.list_objects_v2(Bucket=R2_BUCKET)
        items = resp.get("Contents", [])
        return [obj["Key"] for obj in items if obj["Key"].lower().endswith((".mp4", ".mov", ".avi", ".mkv"))]
    except Exception as e:
        print("❌ r2_list_videos ERROR:", e)
        return []

