# services/full_service.py
import os
import uuid
import subprocess
import wave
import contextlib
from typing import List, Dict, Optional

import numpy as np
import cv2

from services.store_service import load_store
# 맨 위 import 부분 어딘가에 추가
from services.full_sync_store import get_sync


TMP_DIR = os.path.join("results", "tmp_cross_edit")


# -------------------------------------------------------------
# TMP 폴더생성
# -------------------------------------------------------------
def _ensure_tmp():
    os.makedirs(TMP_DIR, exist_ok=True)


# -------------------------------------------------------------
# duration 계산
# -------------------------------------------------------------
def _get_duration(video_path: str) -> float:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 0.0
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    if not fps or fps <= 0:
        return 0.0
    return float(total) / float(fps)


# =================================================================
# 🔥 오디오 기반 싱크 (최대 30초)
# =================================================================

def _extract_wav_30s(input_video: str, output_wav: str, sample_rate: int = 16000):
    """앞쪽 최대 30초 오디오 추출"""
    _ensure_tmp()
    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        "-vn",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-t", "30",           # 🔥 30초까지 사용
        output_wav
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _load_wav_numpy(path: str):
    with contextlib.closing(wave.open(path, "rb")) as w:
        frames = w.readframes(w.getnframes())
        sr = w.getframerate()
    data = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
    return data, sr


def _compute_audio_offset_seconds_30s(video_a: str, video_b: str) -> float:
    """
    두 영상의 앞 30초 오디오를 기반으로 offset 계산
    (양수 = B 영상이 늦게 시작)
    """

    wav_a = os.path.join(TMP_DIR, f"{uuid.uuid4()}_a.wav")
    wav_b = os.path.join(TMP_DIR, f"{uuid.uuid4()}_b.wav")

    _extract_wav_30s(video_a, wav_a)
    _extract_wav_30s(video_b, wav_b)

    sig_a, sr = _load_wav_numpy(wav_a)
    sig_b, _ = _load_wav_numpy(wav_b)

    n = min(len(sig_a), len(sig_b))
    sig_a = sig_a[:n]
    sig_b = sig_b[:n]

    # 최대 ±30초
    max_shift = sr * 30

    corr = np.correlate(sig_a, sig_b, mode="full")
    mid = len(corr) // 2
    limited_corr = corr[mid - max_shift : mid + max_shift + 1]

    best_index = np.argmax(limited_corr)
    lag = best_index - max_shift
    offset_seconds = lag / float(sr)

    print(f"🎵 Audio Sync Offset (±30s): {offset_seconds:.3f}s")

    # 정리
    try:
        os.remove(wav_a)
        os.remove(wav_b)
    except:
        pass

    return offset_seconds


def _sync_videos_audio30s(left_video: str, right_video: str):
    """
    오디오 기반 싱크:
    offset > 0  → right 늦게 시작 → right 앞부분 offset 컷
    offset < 0  → left 늦게 시작  → left 앞부분 |offset| 컷
    """

    offset = _compute_audio_offset_seconds_30s(left_video, right_video)
    _ensure_tmp()

    out_left  = os.path.join(TMP_DIR, f"{uuid.uuid4()}_left.mp4")
    out_right = os.path.join(TMP_DIR, f"{uuid.uuid4()}_right.mp4")

    if offset > 0:
        # right 영상이 늦게 시작 → right에서 offset 잘라냄
        subprocess.run([
            "ffmpeg", "-y",
            "-i", left_video,
            "-c", "copy", out_left
        ])
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", str(offset), "-i", right_video,
            "-c", "copy", out_right
        ])
    else:
        # left 영상이 늦게 시작
        off = abs(offset)
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", str(off), "-i", left_video,
            "-c", "copy", out_left
        ])
        subprocess.run([
            "ffmpeg", "-y",
            "-i", right_video,
            "-c", "copy", out_right
        ])

    print("🎬 Audio sync complete.")
    return out_left, out_right


# =================================================================
# 🔥 변화량 기반 카메라 선택 (빈 시간 없이 전체 커버)
# =================================================================

def generate_full_coverage_segments(
    video_left: str,
    video_right: str,
    offset: float = 0.0,   # 🟩 추가
    duration_hint: Optional[float] = None,
    sustain_sec: float = 2.0,
    fps_fallback: float = 30.0,
) -> List[Dict]:

    store = load_store()
    left_data = next((d for d in store if d.get("video") == video_left), None)
    right_data = next((d for d in store if d.get("video") == video_right), None)

    if not left_data or not right_data:
        dur = duration_hint or 0
        return [{"start": 0, "end": dur, "target": "left"}]

    left_frames = left_data["frames"]
    right_frames = right_data["frames"]

    fps = min(left_data.get("fps", fps_fallback), right_data.get("fps", fps_fallback))

    n = min(len(left_frames), len(right_frames))
    if n == 0:
        dur = duration_hint or 0
        return [{"start": 0, "end": dur, "target": "left"}]

    step = int(round(fps))
    if step <= 0:
        step = 30

    samples = []
    for i in range(step, n, step):
        lf, rf = left_frames[i], right_frames[i]
        lf_prev, rf_prev = left_frames[i-step], right_frames[i-step]

        # 🟩 싱크 적용된 시간 반영
        t_left  = lf["t"]
        t_right = rf["t"] + offset    # offsets 적용!

        t = min(t_left, t_right)      # 두 영상 중 동일 순간을 대표하는 시간

        pl, pr = lf["persons"], rf["persons"]
        pl_prev, pr_prev = lf_prev["persons"], rf_prev["persons"]

        pl_diff = pl - pl_prev
        pr_diff = pr - pr_prev
        samples.append((t, pl_diff, pr_diff))

    if not samples:
        dur = duration_hint or 0
        return [{"start": 0, "end": dur, "target": "left"}]

    if duration_hint:
        duration = duration_hint
    else:
        duration = samples[-1][0]

    cur_side = "left"
    seg_start = 0.0

    pending_side = None
    pending_start = None
    pending_threshold = None

    def compute_threshold(abs_cv):
        if abs_cv >= 8:
            return 0
        if abs_cv <= 2:
            return sustain_sec
        return sustain_sec * (1 - ((abs_cv - 2) / 6))

    prev_abs_cv = 0
    segments = []

    for t, pl_diff, pr_diff in samples:
        change = pr_diff - pl_diff
        abs_cv = abs(change)
        desired = "right" if change > 0 else "left"

        # 반대방향 강한 변화 → 후보 취소
        if pending_side and desired != pending_side:
            if abs_cv >= 2:
                pending_side = None
                pending_start = None
                pending_threshold = None

        # 즉시 전환
        if abs_cv >= 8 and desired != cur_side:
            segments.append({"start": seg_start, "end": t, "target": cur_side})
            cur_side = desired
            seg_start = t
            pending_side = None
            pending_start = None
            pending_threshold = None
            prev_abs_cv = abs_cv
            continue

        # 후보 진행 중 threshold 감소
        if pending_side and desired == pending_side:
            if abs_cv > prev_abs_cv:
                new_th = compute_threshold(abs_cv)
                if pending_threshold is None or new_th < pending_threshold:
                    pending_threshold = new_th

        # 후보 시작
        if desired != cur_side:
            if pending_side is None:
                pending_side = desired
                pending_start = t
                pending_threshold = compute_threshold(abs_cv)

        # 후보 확정
        if pending_side:
            if (t - pending_start) >= pending_threshold:
                segments.append({"start": seg_start, "end": pending_start, "target": cur_side})
                cur_side = pending_side
                seg_start = pending_start

                pending_side = None
                pending_start = None
                pending_threshold = None

        prev_abs_cv = abs_cv

    segments.append({"start": seg_start, "end": duration, "target": cur_side})
    return segments


# =================================================================
# FFmpeg concat
# =================================================================

def _build_ffmpeg_cross_edit(left_synced, right_synced, segments, output_path):
    _ensure_tmp()
    concat_list = os.path.join(TMP_DIR, f"{uuid.uuid4()}_concat.txt")
    temp_list = []

    for i, seg in enumerate(segments):
        start = seg["start"]
        end = seg["end"]
        if end <= start:
            continue

        dur = end - start
        src = left_synced if seg["target"] == "left" else right_synced
        out = os.path.join(TMP_DIR, f"{uuid.uuid4()}_p{i}.mp4")
        temp_list.append(out)

        subprocess.run([
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", src,
            "-t", str(dur),
            "-c", "copy",
            out
        ])

    with open(concat_list, "w") as f:
        for p in temp_list:
            f.write(f"file '{os.path.abspath(p)}'\n")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c", "copy",
        output_path
    ])

    return output_path


# =================================================================
# FULL Export (편집 결과 전달)
# =================================================================

def export_full_from_segments(left_synced_path, right_synced_path, output_path, segments):
    norm = []
    for seg in segments:
        start = seg["start"]
        end = seg["end"]
        if end <= start:
            continue
        side = seg.get("side") or seg.get("target") or "left"
        target = "right" if side == "right" else "left"
        norm.append({"start": start, "end": end, "target": target})

    return _build_ffmpeg_cross_edit(left_synced_path, right_synced_path, norm, output_path)


# =================================================================
# 자동 교차 편집
# =================================================================

def create_full_highlight(left_video_path, right_video_path, output_path, session_id):
    left_synced, right_synced = _sync_videos_audio30s(left_video_path, right_video_path)
    duration = min(_get_duration(left_synced), _get_duration(right_synced))

    segs = generate_full_coverage_segments(
        video_left=os.path.basename(left_video_path),
        video_right=os.path.basename(right_video_path),
        offset=offset,                 # 🟩 추가
        duration_hint=duration,
        sustain_sec=2.0,
    )

    return _build_ffmpeg_cross_edit(left_synced, right_synced, segs, output_path)


# =================================================================
# 편집 페이지 초기 세션 준비
# =================================================================

def prepare_full_session(
    left_video_path: str,
    right_video_path: str,
    left_video_name: str,
    right_video_name: str,
    session_id: str,
    user_synced_left: Optional[str] = None,
    user_synced_right: Optional[str] = None,
) -> dict:
    """
    - user_synced_left/right 가 넘어오면: 그 경로를 그대로 사용 (유저가 싱크 조정 후 자른 영상)
    - 아니면: 기존처럼 오디오 30초 기준 자동 싱크
    """
    # 🔵 1) 싱크된 영상 경로 결정
    if user_synced_left and user_synced_right:
        # full_sync_confirm → apply_sync_cut 에서 만든 '잘린' 싱크 영상
        left_synced = user_synced_left
        right_synced = user_synced_right
    else:
        # 예전 방식: 오디오 30초 자동 싱크 (백업 플로우)
        left_synced, right_synced = _sync_videos_audio30s(left_video_path, right_video_path)

    # 🔵 1-1) 싱크 offset 조회 (full_sync_store 에 저장된 값, float)
    sync_info = get_sync(left_video_name, right_video_name)
    # get_sync 가 float (또는 None) 을 반환하므로 그대로 캐스팅
    offset = float(sync_info) if sync_info is not None else 0.0

    # 🔵 2) duration 계산
    duration = min(_get_duration(left_synced), _get_duration(right_synced))

    # 🔵 3) 사람 수 변화량 기반 full coverage 세그먼트
    segs = generate_full_coverage_segments(
        video_left=left_video_name,
        video_right=right_video_name,
        duration_hint=duration,
        sustain_sec=2.0
    )

    left_clips: List[Dict] = []
    right_clips: List[Dict] = []
    for s in segs:
        item = {"start": s["start"], "end": s["end"]}
        if s["target"] == "left":
            left_clips.append(item)
        else:
            right_clips.append(item)

    return {
        "session_id": session_id,
        "left_src": os.path.relpath(left_synced).replace("\\", "/"),
        "right_src": os.path.relpath(right_synced).replace("\\", "/"),
        "left_video": left_video_name,
        "right_video": right_video_name,
        "duration": float(duration),
        "left_clips": left_clips,
        "right_clips": right_clips,
        "offset": offset,   # ★ 여기서 템플릿으로 넘겨줌
    }




def compute_auto_sync_offset(left_video, right_video):
    """유저에게 추천할 오디오 기반 싱크값 계산 (±30s)"""
    return _compute_audio_offset_seconds_30s(left_video, right_video)

def apply_sync_cut(left_video, right_video, offset):
    """사용자가 선택한 offset(초)을 기준으로 실제 싱크 영상 생성"""

    _ensure_tmp()

    left_out  = os.path.join(TMP_DIR, f"{uuid.uuid4()}_user_left.mp4")
    right_out = os.path.join(TMP_DIR, f"{uuid.uuid4()}_user_right.mp4")

    if offset > 0:
        # right 늦음 → right 컷
        subprocess.run([
            "ffmpeg", "-y",
            "-i", left_video,
            "-c", "copy", left_out
        ])
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", str(offset),
            "-i", right_video,
            "-c", "copy", right_out
        ])
    else:
        # left 늦음 → left 컷
        off = abs(offset)
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", str(off),
            "-i", left_video,
            "-c", "copy", left_out
        ])
        subprocess.run([
            "ffmpeg", "-y",
            "-i", right_video,
            "-c", "copy", right_out
        ])

    return left_out, right_out



import base64
import tempfile

def extract_wav_30s_base64(video_path: str) -> str:
    """앞 30초 wav 생성하고 base64 로 반환"""
    _ensure_tmp()

    temp_wav = os.path.join(TMP_DIR, f"{uuid.uuid4()}_preview.wav")

    subprocess.run([
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-t", "30",
        temp_wav
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    with open(temp_wav, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    return "data:audio/wav;base64," + encoded


# =================================================================
# 사용자 싱크 페이지에서 사용하는 "자동 추천 sync offset"
# =================================================================

def compute_auto_sync_offset(left_video: str, right_video: str) -> float:
    """
    full_sync_adjust.html 에 표시할 자동 오디오 싱크 추천값.
    오디오 30초 기준 자동 싱크 offset 계산.
    """
    return _compute_audio_offset_seconds_30s(left_video, right_video)

def extract_waveform_png(video_path: str, width=900, height=80) -> str:
    """
    앞 30초 오디오를 추출 후 파형 PNG Base64로 반환
    """
    _ensure_tmp()

    wav = os.path.join(TMP_DIR, f"{uuid.uuid4()}_wave.wav")
    png = os.path.join(TMP_DIR, f"{uuid.uuid4()}_wave.png")

    # 오디오 30초 추출
    subprocess.run([
        "ffmpeg","-y",
        "-i", video_path,
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-t", "30",
        wav
    ])

    # numpy 로 로드
    data, _ = _load_wav_numpy(wav)
    n = len(data)

    # 파형 그리기
    img = np.zeros((height, width), dtype=np.uint8)

    for x in range(width):
        idx = int((x / width) * n)
        val = abs(data[idx]) / 32768.0
        h = int(val * (height/2))
        mid = height//2
        img[mid-h:mid+h, x] = 255

    cv2.imwrite(png, img)

    with open(png, "rb") as f:
        enc = base64.b64encode(f.read()).decode()

    try:
        os.remove(wav)
        os.remove(png)
    except:
        pass

    return enc

def generate_wave_png(wav_path: str, width=2000, height=300):
    import matplotlib.pyplot as plt
    import numpy as np
    import io
    import base64
    import wave
    import contextlib

    with contextlib.closing(wave.open(wav_path, "rb")) as w:
        frames = w.readframes(w.getnframes())
        sr = w.getframerate()

    sig = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
    sig = sig / np.max(np.abs(sig))

    fig = plt.figure(figsize=(width/100, height/100), dpi=100)
    plt.plot(sig)
    plt.fill_between(range(len(sig)), sig, color="white", alpha=0.7)
    plt.axis("off")

    buf = io.BytesIO()
    plt.savefig(buf, format="png", transparent=True)
    plt.close(fig)
    buf.seek(0)

    b64 = base64.b64encode(buf.read()).decode("utf-8")
    return "data:image/png;base64," + b64


def load_yolo_data(video_path: str, offset: float = 0.0):
    """
    YOLO 분석 데이터를 불러오고 sync offset 만큼 time 보정 적용.
    """
    import json
    from pathlib import Path
    import config

    name = Path(video_path).name
    yolo_file = Path(config.WORK_DIR) / f"{name}_yolo.json"

    if not yolo_file.exists():
        return []

    data = json.loads(yolo_file.read_text(encoding="utf-8"))

    corrected = []
    for row in data:
        t = row["time"] + offset   # ← offset 보정

        if t < 0:
            continue  # 잘린 앞부분 제거

        corrected.append({
            **row,
            "time": t
        })

    return corrected
