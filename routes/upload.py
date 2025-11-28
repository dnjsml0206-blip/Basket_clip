from services.r2_service import r2_upload_bytes, r2_list_videos
from flask import Blueprint, request, jsonify
import os
from werkzeug.utils import secure_filename
from services.video_convert_service import convert_to_h264

bp = Blueprint("upload", __name__)

UPLOAD_TMP = "tmp_upload"
os.makedirs(UPLOAD_TMP, exist_ok=True)

@bp.route("/upload_video", methods=["POST"])
def upload_video():
    files = request.files.getlist("files")
    results = []

    for f in files:
        original_name = secure_filename(f.filename)

        # 1) 임시 저장
        tmp_path = os.path.join(UPLOAD_TMP, original_name)
        f.save(tmp_path)

        # 2) H.264로 변환
        converted_path = convert_to_h264(tmp_path)
        if not converted_path:
            return jsonify({"error": f"H.264 변환 실패: {original_name}"}), 500

        # 3) 변환된 파일을 바이너리로 읽기
        with open(converted_path, "rb") as fp:
            file_bytes = fp.read()

        # 4) R2 업로드
        r2_upload_bytes(original_name, file_bytes)

        # 5) 임시 파일 삭제
        try: os.remove(tmp_path)
        except: pass
        try: os.remove(converted_path)
        except: pass

        results.append(original_name)

    return jsonify({"uploaded": results})


@bp.route("/videos_list")
def videos_list():
    return jsonify(r2_list_videos())
