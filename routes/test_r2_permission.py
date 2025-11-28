from flask import Blueprint, jsonify
from services.r2_service import s3, R2_BUCKET
import uuid

bp = Blueprint("test_r2_permission", __name__)

@bp.route("/test_r2_permission")
def test_r2_permission():
    """ .env 파일의 R2 키가 삭제 권한을 가지고 있는지 테스트 """
    test_key = f"_permission_test_{uuid.uuid4().hex}.txt"

    # 1) 업로드 권한 테스트
    try:
        s3.put_object(Bucket=R2_BUCKET, Key=test_key, Body=b"test")
        upload_ok = True
    except Exception as e:
        return jsonify({
            "upload_permission": False,
            "delete_permission": False,
            "error": f"Upload failed: {str(e)}"
        })

    # 2) 삭제 권한 테스트
    try:
        s3.delete_object(Bucket=R2_BUCKET, Key=test_key)
        delete_ok = True
    except Exception as e:
        delete_ok = False
        error_msg = str(e)

    if delete_ok:
        return jsonify({
            "upload_permission": True,
            "delete_permission": True,
            "details": "✔ 현재 .env의 R2 키는 삭제 권한이 있습니다."
        })
    else:
        return jsonify({
            "upload_permission": True,
            "delete_permission": False,
            "details": "⚠ 업로드는 가능하지만 삭제 권한은 없습니다.",
            "error": error_msg
        })
