from flask import Blueprint, request, render_template, jsonify
from services.coord_service import BasketCoordService
from services.r2_service import r2_download_temp_frame
from pathlib import Path
import cv2
import uuid
import os

bp = Blueprint("basket", __name__)
coords = BasketCoordService(Path("basket_coords.json"))


@bp.route("/select_basket")
def select_basket():
    video = request.args.get("video")
    next_queue = request.args.get("next", "[]")
    return render_template("select_basket.html", video=video, next=next_queue)


@bp.route("/basket_frame")
def basket_frame():
    video = request.args.get("video")
    tmp_video = r2_download_temp_frame(video)
    if not tmp_video:
        return "cannot download", 500

    cap = cv2.VideoCapture(str(tmp_video))
    ret, frame = cap.read()
    cap.release()

    if not ret:
        return "frame error", 500

    filename = f"basket_{uuid.uuid4().hex}.jpg"
    path = os.path.join("static/frames", filename)
    os.makedirs("static/frames", exist_ok=True)
    cv2.imwrite(path, frame)

    return jsonify({"url": f"/static/frames/{filename}"})


@bp.route("/basket_coords", methods=["POST"])
def post_coords():
    body = request.json
    coords.save(body["video"], body)
    return jsonify({"status": "ok"})


@bp.route("/basket_coords", methods=["GET"])
def get_coords():
    video = request.args.get("video")
    return jsonify(coords.load(video))
