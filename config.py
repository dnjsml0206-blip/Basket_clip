from pathlib import Path
import os

# 프로젝트 기본 경로
BASE_DIR = Path(__file__).resolve().parent

# ===============================
# 🔥 Cloudflare R2 (S3 호환) 설정
# ===============================
R2_ENDPOINT = "https://bf1e90f22c8c93d804483db67dd5b40a.r2.cloudflarestorage.com"
R2_BUCKET = "basket"

# ⚠ 실제 키는 환경변수로 넣어두는 걸 추천
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")

# ===============================
# 🔥 로컬 임시 작업 디렉터리 (YOLO/ffmpeg용)
#   - R2에서 다운받은 영상 / 렌더링 결과 임시 저장
#   - 다운로드 후 사용자 전송이 끝나면 삭제
# ===============================
TMP_DIR = BASE_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

# (기존 WORK_DIR 등이 다른 곳에서 아직 사용 중이면 그대로 둬도 됨.
#  여기서는 LOCAL_VIDEOS, RESULT_DIR은 더 이상 쓰지 않도록 정리)
