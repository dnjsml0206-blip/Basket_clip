from flask import Blueprint, render_template, request, jsonify
from pathlib import Path
from services.coord_service import BasketCoordService
import cv2
import time
import config

LOCAL_VIDEOS = config.LOCAL_VIDEOS

bp = Blueprint("basket", __name__)

FRAME_DIR = Path("static/frames")
FRAME_DIR.mkdir(exist_ok=True)

coord_service = BasketCoordService(Path("basket_coords.json"))


def extract_middle_frame(video_path: Path, out_path: Path):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError("비디오를 열 수 없습니다.")

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    mid = frame_count // 2

    cap.set(cv2.CAP_PROP_POS_FRAMES, mid)
    ret, frame = cap.read()
    if not ret:
        raise RuntimeError("중간 프레임을 읽을 수 없습니다.")

    cv2.imwrite(str(out_path), frame)
    h, w = frame.shape[:2]
    cap.release()
    return w, h


@bp.route("/select_basket")
def select_basket():
    video = request.args.get("video")
    if not video:
        return "영상 이름이 필요합니다.", 400

    video_path = LOCAL_VIDEOS / video
    if not video_path.exists():
        return f"{video} 파일 없음", 404

    # 저장될 프레임 파일 이름
    ts = int(time.time())
    frame_file = f"basket_{ts}.jpg"
    frame_path = FRAME_DIR / frame_file

    # 프레임 추출 (원본 해상도 반환)
    orig_w, orig_h = extract_middle_frame(video_path, frame_path)

    return render_template(
        "select_basket.html",
        video=video,
        frame_file=frame_file,
        orig_w=orig_w,
        orig_h=orig_h
    )

@bp.route("/basket_coords")
def basket_coords():
    video = request.args.get("video")
    data = coord_service.load(video)
    return jsonify(data if data else {})

@bp.route("/save_basket", methods=["POST"])
def save_basket():
    data = request.get_json()
    video = data.get("video")
    next_list = data.get("next", [])

    if not video:
        return jsonify({"error": "video 없음"}), 400

    coord_service.save(video, data)

    # 다음 좌표 설정할 영상이 있다면 바로 다음 영상으로 이동
    if next_list:
        return jsonify({
            "ok": True,
            "next": next_list[0],
            "remain": next_list[1:]
        })

    return jsonify({"ok": True})

