import cv2
import time
from ultralytics import YOLO
from pathlib import Path
from services.store_service import add_item
import uuid


def merge_clips(clips):
    if not clips:
        return []

    clips = sorted(clips, key=lambda x: x["start"])
    merged = [clips[0]]

    for cur in clips[1:]:
        prev = merged[-1]
        if cur["start"] <= prev["end"]:
            prev["end"] = max(prev["end"], cur["end"])
        else:
            merged.append(cur)

    return merged


class YoloHighlighter:
    def __init__(self, model_path, progress, coord_service):
        model_path = Path(model_path)
        if not model_path.is_absolute():
            model_path = Path(__file__).resolve().parent.parent / model_path

        print("YOLO 모델 로딩:", model_path)
        self.model = YOLO(str(model_path))

        self.progress = progress
        self.coord_service = coord_service

        self.START_PAD = 5   # -5초
        self.END_PAD = 3     # +3초

    # ---------------------------------------------------------
    # 메인 실행 함수
    # ---------------------------------------------------------
    def run(self, video_path: Path, video_name: str):
        """
        video_path : 로컬 temp mp4 경로
        video_name : R2에 올라간 실제 파일명 (coords / 저장용 키)
        """
        print("YOLO run 시작:", video_path, " (logical name:", video_name, ")")

        # 골대 좌표 불러오기 (video_name 기준)
        coords = self.coord_service.load(video_name)
        if not coords:
            print("⚠ 골대 좌표 없음 → 득점/시도 감지 비활성화하고 분석만 진행합니다.")
            bx1 = by1 = bx2 = by2 = None
        else:
            bx1, by1, bx2, by2 = coords["x1"], coords["y1"], coords["x2"], coords["y2"]
            basket_width = bx2 - bx1
            basket_height = by2 - by1

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            self.progress.set(0, "error_video_open", video_name)
            return

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 0:
            fps = 30.0

        frame_idx = 0

        clips = []
        ball_status = None
        ball_status_frame = 0
        prev_cy = None
        frames_info = []
        person_count = 0

        while True:
            try:
                p = self.progress.load()
                if p and p.get("status") == "stopped":
                    print("🔴 사용자 중지 요청 감지: 분석 중단")
                    break
            except Exception as e:
                print(f"progress 상태 확인 오류: {e}")
                pass

            ret, frame = cap.read()
            if not ret:
                break

            frame_idx += 1
            now_sec = frame_idx / fps

            progress_val = int((frame_idx / total) * 100)
            self.progress.set(progress_val, "running", video_name)

            result = self.model(frame, verbose=False)[0]

            ball_found = False
            ball_cx, ball_cy = None, None
            person_count = 0

            for box in result.boxes:
                cls = int(box.cls)
                label = self.model.names[cls]

                if label == "person":
                    conf = float(box.conf)
                    if conf >= 0.25:
                        person_count += 1
                    continue

                if label != "ball":
                    continue

                conf = float(box.conf)
                if conf < 0.25:
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0])
                ball_cx = (x1 + x2) / 2
                ball_cy = (y1 + y2) / 2
                ball_found = True

            frames_info.append({
                "t": round(now_sec, 4),
                "ball": {
                    "found": bool(ball_found),
                    "cx": ball_cx,
                    "cy": ball_cy
                },
                "persons": person_count,
            })

            if not ball_found:
                prev_cy = None
                continue

            if bx1 is None:
                upper_zone = lower_zone = False
            else:
                upper_zone = (
                    (bx1 - 2 * basket_width <= ball_cx <= bx2 + 2 * basket_width)
                    and (ball_cy <= by1)
                )

            if upper_zone:
                ball_status = "Attempt"
                ball_status_frame = frame_idx

            if ball_status == "Attempt":
                if (frame_idx - ball_status_frame) > fps * 1.0:
                    ball_status = None

            if prev_cy is not None and ball_status == "Attempt":

                is_downward = ball_cy > prev_cy

                lower_zone = (
                    (bx1 - 0.3 * basket_width <= ball_cx <= bx2 + 0.3 * basket_width)
                    and (by1 <= ball_cy <= by2 + basket_height * 1.2)
                )

                if lower_zone and is_downward:
                    start_t = max(0, now_sec - self.START_PAD)
                    end_t = now_sec + self.END_PAD

                    clips.append({
                        "start": round(start_t, 2),
                        "end": round(end_t, 2)
                    })

                    ball_status = None

            prev_cy = ball_cy

        cap.release()

        merged = merge_clips(clips)

        self.progress.set(100, "done", video_name, clips=merged)
        print("YOLO 분석 완료:", video_name, merged)

        item = {
            "id": str(uuid.uuid4()),
            "video": video_name,
            "fps": fps,
            "frames": frames_info,
            "clips": merged,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        add_item(item)
