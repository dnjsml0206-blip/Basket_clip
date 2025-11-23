from pathlib import Path

# 프로젝트 기본 경로
BASE_DIR = Path(__file__).resolve().parent

# 🔥 싱크 후 잘린 영상 저장 디렉터리 (사용자 지정)
WORK_DIR = Path(r"d:\Users\JWL\Desktop\YOLO\clips\sync_videos")
WORK_DIR.mkdir(parents=True, exist_ok=True)

# 원본 영상 디렉터리
LOCAL_VIDEOS = Path(r"d:\Users\JWL\Desktop\YOLO\clips")
LOCAL_VIDEOS.mkdir(parents=True, exist_ok=True)

# 결과 저장 디렉터리
RESULT_DIR = Path(r"d:\Users\JWL\Desktop\YOLO\clips\results")
RESULT_DIR.mkdir(parents=True, exist_ok=True)

# tmp 폴더
TMP_DIR = Path(r"d:\Users\JWL\Desktop\YOLO\clips\temp")
TMP_DIR.mkdir(parents=True, exist_ok=True)
