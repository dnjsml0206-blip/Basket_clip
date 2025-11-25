from flask import Blueprint, request, render_template
import json

bp = Blueprint("result_page", __name__)

@bp.route("/result_page")
def result_page():
    video = request.args.get("video")

    # URL 로부터 clips (JSON 형태 문자열) 받기
    clips_raw = request.args.get("clips", "[]")

    try:
        clips = json.loads(clips_raw)
    except Exception as e:
        print("\n❌ CLIPS PARSE ERROR:")
        print("RAW:", clips_raw)
        print("ERR:", e, "\n")
        clips = []

    # 렌더링
    return render_template(
        "result_page.html",
        video=video,
        clips=clips
    )
