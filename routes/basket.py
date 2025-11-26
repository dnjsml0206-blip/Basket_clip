from flask import Blueprint, request, render_template, jsonify
from services.coord_service import BasketCoordService
from services.r2_service import r2_download_temp_frame
from pathlib import Path
from config import BASE_DIR
import cv2
import uuid
import os

bp = Blueprint("basket", __name__)
coords = BasketCoordService(Path("basket_coords.json"))


@bp.route("/select_basket")
def select_basket():
    video = request.args.get("video")
    next_queue = request.args.get("next", "[]")
    
    # 🔥 프레임 추출
    tmp_video = r2_download_temp_frame(video)
    if not tmp_video:
        return "cannot download video", 500

    cap = cv2.VideoCapture(str(tmp_video))
    ret, frame = cap.read()
    orig_h, orig_w = frame.shape[:2] if ret else (0, 0)
    cap.release()

    if not ret:
        return "frame error", 500

    # 프레임 저장
    frames_dir = BASE_DIR / "static" / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"basket_{uuid.uuid4().hex}.jpg"
    frame_path = frames_dir / filename
    cv2.imwrite(str(frame_path), frame)
    
    # 임시 파일 삭제
    tmp_video.unlink(missing_ok=True)

    return render_template(
        "select_basket.html",
        video=video,
        next=next_queue,
        frame_file=filename,
        orig_w=orig_w,
        orig_h=orig_h
    )


# 🔥 좌표 저장 (POST)
@bp.route("/save_basket", methods=["POST"])
def save_basket():
    body = request.json
    video = body["video"]
    next_list = body.get("next", [])
    
    coords.save(video, {
        "x1": body["x1"],
        "y1": body["y1"],
        "x2": body["x2"],
        "y2": body["y2"]
    })
    
    if next_list and len(next_list) > 0:
        return jsonify({
            "ok": True,
            "next": next_list[0],
            "remain": next_list[1:]
        })
    
    return jsonify({"ok": True})


@bp.route("/basket_coords", methods=["GET"])
def get_coords():
    video = request.args.get("video")
    return jsonify(coords.load(video))