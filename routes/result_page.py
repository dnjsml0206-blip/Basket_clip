from flask import Blueprint, render_template, request, session
import json

bp = Blueprint("result_page", __name__)

@bp.route("/result_page")
def result_page():
    video = request.args.get("video")

    clips_param = request.args.get("clips", "[]")
    try:
        clips = json.loads(clips_param)
    except:
        clips = []


    return render_template("result_page.html", video=video, clips=clips)
