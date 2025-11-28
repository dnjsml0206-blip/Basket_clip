from flask import Blueprint, jsonify
import os, json, shutil
from services.r2_service import s3, R2_BUCKET

bp = Blueprint("analysis_end", __name__)

UPLOAD_DIR = "upload"
RESULT_DIR = "results"
FRAMES_DIR = "static/frames"
TMP_DIR = "tmp"
STORE_FILE = "utils/analysis_store.json"
PROGRESS_FILE = "progress.json"
FULL_PROGRESS_FILE = "full_progress.json"


def delete_r2_file(filename):
    """Cloudflare R2에서 파일 삭제"""
    try:
        s3.delete_object(Bucket=R2_BUCKET, Key=filename)
        print(f"🗑 R2 삭제 완료: {filename}")
    except Exception as e:
        print(f"⚠ R2 삭제 실패: {filename}", e)


@bp.route("/end_analysis", methods=["POST"])
def end_analysis():
    print("🔚 분석 종료: 모든 데이터 초기화 시작")

    # progress.json에서 영상 이름 가져오기 (있으면)
    uploaded_video = None
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, "r") as f:
                p = json.load(f)
                uploaded_video = p.get("video")
    except:
        pass

    # 1) 업로드된 원본 영상 삭제 (로컬)
    if uploaded_video and os.path.exists(UPLOAD_DIR):
        local_path = os.path.join(UPLOAD_DIR, uploaded_video)
        if os.path.exists(local_path):
            try:
                os.remove(local_path)
                print("🗑 로컬 업로드 영상 삭제:", local_path)
            except:
                pass

        # R2에서도 원본 삭제
        delete_r2_file(uploaded_video)

    # 2) 결과 영상/하이라이트 파일 삭제 (로컬+R2)
    if os.path.exists(RESULT_DIR):
        for f in os.listdir(RESULT_DIR):
            if f.endswith(".mp4") or f.endswith(".txt") or f.startswith("tmp"):
                file_path = os.path.join(RESULT_DIR, f)
                try:
                    os.remove(file_path)
                    print("🗑 로컬 결과 파일 삭제:", f)
                except:
                    pass

                # R2에서도 삭제 시도
                delete_r2_file(f)

    # 3) frames 폴더 비우기
    shutil.rmtree(FRAMES_DIR, ignore_errors=True)
    os.makedirs(FRAMES_DIR, exist_ok=True)

    # 4) tmp 폴더 비우기
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    os.makedirs(TMP_DIR, exist_ok=True)

    # 5) analysis_store.json 초기화
    with open(STORE_FILE, "w") as f:
        json.dump([], f)

    # 6) progress.json 초기화
    with open(PROGRESS_FILE, "w") as f:
        json.dump({}, f)

    # 7) full_progress.json 초기화
    with open(FULL_PROGRESS_FILE, "w") as f:
        json.dump({}, f)

    print("✅ 분석 종료: 모든 자료 초기화 완료")
    return jsonify({"status": "ok"})
