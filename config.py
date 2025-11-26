from pathlib import Path

# 프로젝트 기본 경로
BASE_DIR = Path(__file__).resolve().parent

# 임시 파일 저장 디렉터리 (YOLO / ffmpeg 작업용)
TMP_DIR = BASE_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

# 하이라이트 결과 mp4 임시 저장 디렉터리 (사용자 다운로드용)
RESULT_DIR = BASE_DIR / "results"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

# 진행 상태 저장 파일
PROGRESS_PATH = BASE_DIR / "progress.json"

# 골대 좌표 저장 파일
COORDS_PATH = BASE_DIR / "basket_coords.json"

# 분석 결과(클립, 프레임 정보 등) 저장 파일
ANALYSIS_STORE_PATH = BASE_DIR / "utils" / "analysis_store.json"
ANALYSIS_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
if not ANALYSIS_STORE_PATH.exists():
    ANALYSIS_STORE_PATH.write_text("[]", encoding="utf-8")
