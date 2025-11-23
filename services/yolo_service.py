import cv2
import time
from ultralytics import YOLO
from pathlib import Path
from services.store_service import add_item
import uuid


# ---------------------------------------------------------
# 클립 병합 함수
# ---------------------------------------------------------
def merge_clips(clips):
    if not clips:
        return []

    clips = sorted(clips, key=lambda x: x["start"])
    merged = [clips[0]]

    for cur in clips[1:]:
        prev = merged[-1]

        # 겹치면 병합
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
    def run(self, video_path: Path):
        print("YOLO run 시작:", video_path)

        video_name = video_path.name

        # 골대 좌표 불러오기
        coords = self.coord_service.load(video_name)
        if not coords:
            print("⚠ 골대 좌표 없음 → 득점/시도 감지 비활성화하고 분석만 진행합니다.")
            bx1 = by1 = bx2 = by2 = None  # 좌표 없음 처리용
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
            fps = 30.0  # 기본값(필요시 프로젝트에 맞게 조정)

        frame_idx = 0

        clips = []
        ball_status = None        # "Attempt" or None
        ball_status_frame = 0
        prev_cy = None
        frames_info = []      # 👈 모든 프레임 분석 저장
        person_count = 0      # 👈 매 프레임 person 수


        # ---------------------------------------------------------
        # 프레임 반복
        # ---------------------------------------------------------
        while True:

            try:
                p = self.progress.load()
                if p and p.get("status") == "stopped":
                    print("🔴 사용자 중지 요청 감지: 분석 중단")
                    break
            except Exception as e:
                print(f"progress 상태 확인 오류: {e}")
                # progress 파일 문제가 있으면 그냥 계속 진행하게 함
                pass

            ret, frame = cap.read()
            if not ret:
                break

            frame_idx += 1
            now_sec = frame_idx / fps

            # 진행률 갱신
            progress_val = int((frame_idx / total) * 100)
            self.progress.set(progress_val, "running", video_name)

            # YOLO 추론
            result = self.model(frame, verbose=False)[0]

            # -----------------------------
            # 공(ball) 탐지
            # -----------------------------
            ball_found = False
            ball_cx, ball_cy = None, None
            person_count = 0     # 매 프레임 사람 수 카운트


            for box in result.boxes:
                cls = int(box.cls)
                label = self.model.names[cls]

                # ❗ 사람 탐지
                if label == "person":
                    conf = float(box.conf)
                    if conf >= 0.25:
                        person_count += 1
                    continue

                # 공 탐지
                if label != "ball":
                    continue

                conf = float(box.conf)
                if conf < 0.25:
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0])
                ball_cx = (x1 + x2) / 2
                ball_cy = (y1 + y2) / 2
                ball_found = True
                

            # 모든 프레임 기록 (ball 없어도 기록)
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


            # =========================================================
            # Attempt 감지 (골대 위쪽 박스)
            # =========================================================
            if bx1 is None:
                upper_zone = lower_zone = False
            else:
            
                upper_zone = (
                    (bx1 - 2 * basket_width <= ball_cx <= bx2 + 2 * basket_width) and
                    (ball_cy <= by1)
                )

            if upper_zone:
                ball_status = "Attempt"
                ball_status_frame = frame_idx

            # Attempt 상태 유지 시간 너무 길면 초기화 (1초)
            if ball_status == "Attempt":
                if (frame_idx - ball_status_frame) > fps * 1.0:
                    ball_status = None

            # =========================================================
            # Goal 감지 (Attempt → 아래로 통과)
            # =========================================================
            if prev_cy is not None and ball_status == "Attempt":

                is_downward = ball_cy > prev_cy

                lower_zone = (
                    (bx1 - 0.3 * basket_width <= ball_cx <= bx2 + 0.3 * basket_width) and
                    (by1 <= ball_cy <= by2 + basket_height * 1.2)
                )

                if lower_zone and is_downward:
                    start_t = max(0, now_sec - self.START_PAD)
                    end_t = now_sec + self.END_PAD

                    clips.append({
                        "start": round(start_t, 2),
                        "end": round(end_t, 2)
                    })

                    ball_status = None  # 득점 후 초기화

            prev_cy = ball_cy

        cap.release()

        # ---------------------------------------------------------
        # 최종 클립 병합
        # ---------------------------------------------------------
        merged = merge_clips(clips)

        self.progress.set(100, "done", video_name, clips=merged)
        print("YOLO 분석 완료:", video_name, merged)

        # 분석 결과 저장
        item = {
            "id": str(uuid.uuid4()),
            "video": video_name,
            "fps": fps,
            "frames": frames_info,   # 모든 프레임 정보
            "clips": merged,         # 하이라이트 구간
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        add_item(item)

