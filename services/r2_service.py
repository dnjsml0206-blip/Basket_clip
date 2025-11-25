# services/r2_service.py
import boto3
from botocore.config import Config
from pathlib import Path
import config

_session = None
_client = None


def get_s3_client():
    global _client, _session
    if _client is not None:
        return _client

    _session = boto3.session.Session()
    _client = _session.client(
        "s3",
        endpoint_url=config.R2_ENDPOINT,
        aws_access_key_id=config.R2_ACCESS_KEY_ID,
        aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(s3={"addressing_style": "virtual"})
    )
    return _client


# 🔼 R2에 업로드 (파일 객체 기반)
def upload_fileobj(fileobj, key: str):
    s3 = get_s3_client()
    s3.upload_fileobj(fileobj, config.R2_BUCKET, key)


# 🔽 R2에서 로컬 경로로 다운로드
def download_to_path(key: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    s3 = get_s3_client()
    s3.download_file(config.R2_BUCKET, key, str(dest))


# 📜 R2의 /videos/ 폴더 내 목록 가져오기
def list_videos_prefix(prefix: str = "videos/"):
    s3 = get_s3_client()
    resp = s3.list_objects_v2(Bucket=config.R2_BUCKET, Prefix=prefix)

    if "Contents" not in resp:
        return []

    result = []
    for obj in resp["Contents"]:
        key = obj["Key"]
        if not key.lower().endswith((".mp4", ".mov", ".avi", ".mkv")):
            continue
        # "videos/xxx.mp4" → "xxx.mp4"
        name = key.split("/")[-1]
        result.append(name)
    return sorted(result)


# 🎥 재생용 presigned URL 생성
def generate_presigned_video_url(filename: str, expires_in: int = 3600):
    key = f"videos/{filename}"
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": config.R2_BUCKET, "Key": key},
        ExpiresIn=expires_in,
    )
