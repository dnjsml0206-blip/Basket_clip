# routes/full.py
import os
import uuid, threading
from pathlib import Path

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, send_file, flash, jsonify
)
from werkzeug.utils import secure_filename

import config
from services.full_service import (
    create_full_highlight,
    prepare_full_session,
    export_full_from_segments,   # 🔵 새로 추가
)
from services.store_service import load_store     # 🔵 /full_segments 에 필요
from utils.progress import ProgressManager
from utils.full_edit_store import save_full_edit, load_full_edit


full_bp = Blueprint("full", __name__)
progress = ProgressManager(Path("full_progress.json"))

UPLOAD_DIR = "results"

user_sync_history = {}   # { (left, right): offset }


# -------------------------------------------------
# 1단계: 좌/우 사용할 영상 선택 페이지
# -------------------------------------------------
from services.full_sync_store import load_sync

@full_bp.route("/full_select", methods=["GET"])
def full_select():
    videos = [p.name for p in Path(config.LOCAL_VIDEOS).glob("*.mp4")]
    sync_db = load_sync()

    return render_template(
        "full_select.html",
        videos=videos,
        sync_db=sync_db   # ← 반드시 추가
    )

# 좌/우 원본 영상 직접 재생용 (사용 여부에 따라 유지)
@full_bp.route("/full_video", methods=["GET"])
def full_video():
    video = request.args.get("video")
    if not video:
        return "video parameter required", 400

    path = Path(config.LOCAL_VIDEOS) / video
    if not path.exists():
        return "video not found", 404

    return send_file(path, mimetype="video/mp4")


# 분석 결과에서 segments 주는 엔드포인트 (optional)
@full_bp.route("/full_segments", methods=["GET"])
def full_segments():
    """
    분석 결과 기반 추천 구간 반환
    load_store()에 저장된 clips 사용
    반환 형식: { "segments": [ { "start": float, "end": float }, ... ] }
    """
    video = request.args.get("video")
    if not video:
        return jsonify({"segments": []})

    data = load_store()
    item = next((d for d in data if d.get("video") == video), None)
    if not item:
        return jsonify({"segments": []})

    segments = item.get("clips", [])
    return jsonify({"segments": segments})


# -------------------------------------------------
# 2단계: 교차 편집 UI (full.html)
# -------------------------------------------------
@full_bp.route("/full", methods=["GET"])
def full_form():
    left = request.args.get("left")
    right = request.args.get("right")

    if not left or not right:
        return redirect(url_for("full.full_select"))

    session_id = request.args.get("session") or str(uuid.uuid4())
    use_saved = request.args.get("use_saved_sync") == "1"

    left_path = Path(config.LOCAL_VIDEOS) / left
    right_path = Path(config.LOCAL_VIDEOS) / right

    if not left_path.exists() or not right_path.exists():
        return "원본 영상 파일을 찾을 수 없습니다.", 404

    # 🔵 NEW: full_sync_confirm 가 넘긴 싱크된 파일 경로
    user_left_synced  = request.args.get("left_synced")
    user_right_synced = request.args.get("right_synced")

    offset_to_use = None

    # 🔵 싱크 저장된 것이 있고, 사용자 요청(use_saved_sync=1)이면 → 자동 반영
    if use_saved:
        saved = get_sync(left, right)
        if saved is not None:
            offset_to_use = float(saved)
            print(f"[FULL] Using saved sync offset: {offset_to_use}")

            from services.full_service import apply_sync_cut
            user_left_synced, user_right_synced = apply_sync_cut(
                str(left_path), str(right_path), offset_to_use
            )

    session_data = prepare_full_session(
        left_video_path=str(left_path),
        right_video_path=str(right_path),
        left_video_name=left,
        right_video_name=right,
        session_id=session_id,
        user_synced_left=user_left_synced,
        user_synced_right=user_right_synced,
    )

    # 🔵 offset 추가 (없으면 0)
    session_data["offset"] = offset_to_use or 0

    return render_template(
        "full.html",
        session_id=session_data["session_id"],
        left_video=session_data["left_video"],
        right_video=session_data["right_video"],
        left_src=session_data["left_src"],
        right_src=session_data["right_src"],
        duration=session_data["duration"],
        left_clips=session_data["left_clips"],
        right_clips=session_data["right_clips"],
        offset=session_data["offset"]
    )



# 싱크된 mp4 파일 서빙
@full_bp.route("/full_file", methods=["GET"])
def full_file():
    rel_path = request.args.get("p")
    if not rel_path:
        return "path required", 400

    norm = os.path.normpath(rel_path)
    if not norm.startswith("results"):
        return "forbidden", 403

    return send_file(norm)


# 진행률 폴링 (full_start / full_wait 용)
@full_bp.route("/full_progress")
def full_progress():
    return jsonify(progress.load())


# 완성본 다운로드
@full_bp.route("/download_full")
def download_full():
    file = request.args.get("file")
    return send_file(Path("results") / file, as_attachment=True)


# -------------------------------------------------
# 로컬 영상 2개 선택 → 곧바로 자동 교차편집 (UI 없이)
# -------------------------------------------------
@full_bp.route("/full_process", methods=["GET"])
def full_process_local():
    left = request.args.get("left")
    right = request.args.get("right")

    if not left or not right:
        return "좌/우 영상이 필요합니다.", 400

    session_id = str(uuid.uuid4())
    left_path = Path(config.LOCAL_VIDEOS) / left
    right_path = Path(config.LOCAL_VIDEOS) / right

    output_path = Path("results") / f"full_{session_id}.mp4"

    progress.set(0, "starting", session_id)

    result_path = create_full_highlight(
        left_video_path=str(left_path),
        right_video_path=str(right_path),
        output_path=str(output_path),
        session_id=session_id,
    )

    progress.set(100, "done", session_id)

    return send_file(result_path)  # 바로 재생용, as_attachment 제거


# 업로드된 영상 두 개로 자동 교차편집 (선택적)
@full_bp.route("/full", methods=["POST"])
def full_process_upload():
    left_video = request.files.get("left_video")
    right_video = request.files.get("right_video")

    if not left_video or not right_video:
        flash("좌/우 골대 영상을 모두 업로드해주세요.")
        return redirect(url_for("full.full_form"))

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    session_id = str(uuid.uuid4())
    left_name = secure_filename(f"left_{session_id}.mp4")
    right_name = secure_filename(f"right_{session_id}.mp4")

    left_path = os.path.join(UPLOAD_DIR, left_name)
    right_path = os.path.join(UPLOAD_DIR, right_name)

    left_video.save(left_path)
    right_video.save(right_path)

    output_path = os.path.join(UPLOAD_DIR, f"full_{session_id}.mp4")

    try:
        result_path = create_full_highlight(
            left_video_path=left_path,
            right_video_path=right_path,
            output_path=output_path,
            session_id=session_id,
        )
    except Exception as e:
        print("full error:", e)
        flash("교차 편집 중 오류가 발생했습니다.")
        return redirect(url_for("full.full_form"))

    return send_file(result_path, as_attachment=True)


# -------------------------------------------------
# full_start → 백그라운드 자동 교차편집 + full_wait
# -------------------------------------------------
@full_bp.route("/full_start")
def full_start():
    left = request.args.get("left")
    right = request.args.get("right")

    if not left or not right:
        return "좌/우 영상이 필요합니다.", 400

    session_id = str(uuid.uuid4())
    left_path = Path(config.LOCAL_VIDEOS) / left
    right_path = Path(config.LOCAL_VIDEOS) / right

    # 진행률 초기화
    progress.set(0, "starting", left)

    def run_task():
        try:
            progress.set(5, "syncing", left)

            output_path = Path("results") / f"full_{session_id}.mp4"

            result = create_full_highlight(
                left_video_path=str(left_path),
                right_video_path=str(right_path),
                output_path=str(output_path),
                session_id=session_id
            )

            progress.set(
                100, "done", left,
                clips={"file": f"full_{session_id}.mp4"}
            )

        except Exception as e:
            print("full error:", e)
            progress.set(0, "error", left)

    threading.Thread(target=run_task, daemon=True).start()

    return render_template("full_wait.html")


# -------------------------------------------------
# full.html 에서 편집 끝낸 후 → segments 기반 최종 영상 생성
# -------------------------------------------------
@full_bp.route("/full_export", methods=["POST"])
def full_export():
    """
    full.html 에서 편집이 끝난 segments 를 받아 실제 결과 영상 생성
    """
    data = request.get_json() or {}

    left_src = data.get("left_src")     # 예: "results/tmp_cross_edit/...._left.mp4"
    right_src = data.get("right_src")
    segments = data.get("segments") or []

    if not left_src or not right_src:
        return jsonify({"ok": False, "error": "missing synced sources"}), 400

    if not segments:
        return jsonify({"ok": False, "error": "no segments"}), 400

    os.makedirs("results", exist_ok=True)
    out_name = f"full_{uuid.uuid4()}.mp4"
    output_path = os.path.join("results", out_name)

    try:
        result_path = export_full_from_segments(
            left_synced_path=left_src,
            right_synced_path=right_src,
            output_path=output_path,
            segments=segments,
        )
    except Exception as e:
        print("full_export error:", e)
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True, "file": os.path.basename(result_path)})


@full_bp.route("/full_result")
def full_result_page():
    file = request.args.get("file")
    if not file:
        return "file required", 400
    return render_template("full_result.html", file=file)


# -------------------------------------------------
# 작업 저장 / 불러오기
# -------------------------------------------------
@full_bp.route("/full_save_edit", methods=["POST"])
def full_save_edit():
    data = request.get_json(force=True)
    left = data.get("left_video")
    right = data.get("right_video")
    segments = data.get("segments", [])

    if not left or not right:
        return jsonify({"ok": False, "error": "left/right video required"}), 400

    try:
        save_full_edit(left, right, segments)
        return jsonify({"ok": True})
    except Exception as e:
        print("full_save_edit error:", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@full_bp.route("/full_load_edit")
def full_load_edit():
    left = request.args.get("left")
    right = request.args.get("right")
    if not left or not right:
        return jsonify({"ok": False, "error": "left/right video required"}), 400

    segs = load_full_edit(left, right)
    return jsonify({"ok": True, "segments": segs})



from services.full_sync_store import get_sync
from services.full_service import compute_auto_sync_offset

@full_bp.route("/full_sync")
def full_sync():
    left = request.args.get("left")
    right = request.args.get("right")

    if not left or not right:
        return redirect(url_for("full.full_select"))

    # 🔵 저장된 싱크 존재하는지 체크
    saved = get_sync(left, right)

    if saved:
        # 기존 싱크 존재 → 사용자에게 선택 제공
        return render_template(
            "full_sync_confirm_choice.html",
            left=left,
            right=right,
            saved_offset=saved["offset"]
        )

    # 🔵 기존 싱크 없음 → 자동 분석 화면으로 이동
    offset = compute_auto_sync_offset(
        str(Path(config.LOCAL_VIDEOS) / left),
        str(Path(config.LOCAL_VIDEOS) / right)
    )

    return render_template(
        "full_sync_adjust.html",
        left_video=left,
        right_video=right,
        auto_offset=offset
    )


# --- NEW: 사용자 선택 싱크 확정 ---

user_sync_offsets = {}  # { (left,right): offset }

@full_bp.route("/full_sync_confirm", methods=["POST"])
def full_sync_confirm():
    data = request.get_json()
    left   = data.get("left")
    right  = data.get("right")
    offset = data.get("offset")

    if not left or not right:
        return {"ok": False, "error": "Missing parameters"}

    try:
        offset = float(offset)
    except:
        return {"ok": False, "error": "Invalid offset"}

    # 🔵 저장 (파일에 저장!!)
    from services.full_sync_store import set_sync
    set_sync(left, right, offset)

    return {"ok": True}


@full_bp.route("/apply_user_sync", methods=["POST"])
def apply_user_sync():
    data = request.get_json()
    left   = data.get("left")
    right  = data.get("right")
    offset = float(data.get("offset"))

    from services.full_service import apply_sync_cut

    left_path  = Path(config.LOCAL_VIDEOS) / left
    right_path = Path(config.LOCAL_VIDEOS) / right

    # 실제 잘라낸 synced 비디오 생성
    left_out, right_out = apply_sync_cut(str(left_path), str(right_path), offset)

    return {
        "ok": True,
        "left": left_out.replace("\\", "/"),
        "right": right_out.replace("\\", "/")
    }

from services.full_sync_store import set_sync

@full_bp.route("/full_sync_save_offset", methods=["POST"])
def full_sync_save_offset():
    data = request.json
    left  = data["left"]
    right = data["right"]
    offset = data["offset"]

    set_sync(left, right, offset)
    return {"ok": True}

@full_bp.route("/api_sync_list")
def api_sync_list():
    from services.full_sync_store import load_sync
    return load_sync()
