import uuid
import subprocess
import tempfile
from pathlib import Path
from threading import Lock
from services.r2_service import download_to_path
import os

class ExportManager:
    def __init__(self):
        self.jobs = {}
        self.locker = Lock()

    # ---------------------------------------
    # 🔥 1) 작업 생성
    # ---------------------------------------
    def create_job(self, video, clips):
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = {
            "status": "pending",
            "progress": 0,
            "video": video,
            "clips": clips,
            "error": None
        }
        return job_id

    # ---------------------------------------
    # 🔥 2) 중지 요청
    # ---------------------------------------
    def stop(self, job_id):
        job = self.jobs.get(job_id)
        if job:
            job["status"] = "stopped"

    # ---------------------------------------
    # 🔥 3) ffmpeg 실행기
    # ---------------------------------------
    def worker(self, job_id, video_name, output_path):
        job = self.jobs.get(job_id)
        if not job:
            return

        try:
            # ---------------------------------------
            # ① R2 → temp 영상 다운로드
            # ---------------------------------------
            tmp_video_path = Path(tempfile.gettempdir()) / f"exp_{uuid.uuid4().hex}.mp4"
            download_to_path(video_name, tmp_video_path)

            if not tmp_video_path.exists():
                job["status"] = "error"
                job["error"] = "Cannot download video from R2"
                return

            clips = job["clips"]
            if not clips:
                job["status"] = "error"
                job["error"] = "No clips provided"
                return

            # ---------------------------------------
            # ② 개별 클립 추출 → temp 파일 생성
            # ---------------------------------------
            temp_dir = Path(tempfile.gettempdir()) / f"exp_{job_id}"
            temp_dir.mkdir(exist_ok=True)

            clip_files = []
            total = len(clips)

            for idx, c in enumerate(clips):
                if job["status"] == "stopped":
                    return

                start = c["start"]
                end = c["end"]
                duration = max(0.01, end - start)

                clip_path = temp_dir / f"clip_{idx}.mp4"
                clip_files.append(clip_path)

                # ffmpeg extract
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start),
                    "-i", str(tmp_video_path),
                    "-t", str(duration),
                    "-c", "copy",
                    str(clip_path)
                ]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                job["progress"] = int(((idx + 1) / total) * 50)

            # ---------------------------------------
            # ③ 병합 리스트 파일 생성
            # ---------------------------------------
            list_path = temp_dir / "list.txt"
            with open(list_path, "w", encoding="utf-8") as f:
                for clip in clip_files:
                    f.write(f"file '{clip.as_posix()}'\n")

            # ---------------------------------------
            # ④ concat 병합
            # ---------------------------------------
            job["progress"] = 80

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_path),
                "-c", "copy",
                str(output_path)
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # ---------------------------------------
            # 완료
            # ---------------------------------------
            if not output_path.exists():
                job["status"] = "error"
                job["error"] = "Failed to create result file"
                return

            job["progress"] = 100
            job["status"] = "done"

        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)

        finally:
            # ❗ temp 파일 정리
            try:
                if tmp_video_path.exists():
                    os.remove(tmp_video_path)
            except:
                pass

            try:
                for f in list(temp_dir.glob("*")):
                    try:
                        f.unlink()
                    except:
                        pass
                temp_dir.rmdir()
            except:
                pass
