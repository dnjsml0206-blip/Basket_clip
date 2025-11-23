import subprocess
import threading
import uuid
import shutil
from pathlib import Path
import config


def escape(p: Path):
    return str(p).replace("\\", "/")


class ExportManager:
    def __init__(self):
        self.jobs = {}
        self.lock = threading.Lock()
        self.process = {}

    # ---------------------------------------------------------
    # Job 생성
    # ---------------------------------------------------------
    def create_job(self, video, clips):
        job_id = str(uuid.uuid4())
        with self.lock:
            self.jobs[job_id] = {
                "video": video,
                "clips": clips,
                "progress": 0,
                "status": "pending",
                "url": None,
                "stop": False
            }
        return job_id

    # ---------------------------------------------------------
    # STOP 요청
    # ---------------------------------------------------------
    def stop(self, job_id):
        with self.lock:
            if job_id in self.process:
                try:
                    self.process[job_id].kill()
                except:
                    pass
            if job_id in self.jobs:
                self.jobs[job_id]["stop"] = True
                self.jobs[job_id]["status"] = "stopped"

    # ---------------------------------------------------------
    # ffmpeg 기반 export worker
    # ---------------------------------------------------------
    def worker(self, job_id, video_path: Path, final_output: Path):

        job = self.jobs[job_id]
        clips = job["clips"]

        with self.lock:
            job["status"] = "running"
            job["progress"] = 0

        total_duration = sum(c["end"] - c["start"] for c in clips)
        if total_duration <= 0:
            with self.lock:
                job["status"] = "error"
            return

        # ---------------------------------------------------------
        # 🔥 로그 파일 생성
        # ---------------------------------------------------------
        error_log = final_output.with_suffix(".log")
        with open(error_log, "w", encoding="utf-8") as f:
            f.write("==== EXPORT START ====\n")
            f.write(f"VIDEO: {video_path}\n")
            f.write(f"CLIPS: {clips}\n")

        # ---------------------------------------------------------
        # 🔥 개별 클립을 results/tmp_clips/ 에 저장
        # ---------------------------------------------------------
        temp_dir = config.RESULT_DIR / "tmp_clips"
        temp_dir.mkdir(parents=True, exist_ok=True)

        temp_clips = []

        for idx, c in enumerate(clips):
            out_clip = temp_dir / f"{job_id}_{idx}.mp4"
            temp_clips.append(out_clip)

            cmd = [
                "ffmpeg",
                "-y",
                "-ss", str(c["start"]),
                "-to", str(c["end"]),
                "-i", f"\"{escape(video_path)}\"",
                "-c:v", "copy",
                "-c:a", "copy",
                f"\"{escape(out_clip)}\""
            ]

            full_cmd = " ".join(cmd)

            try:
                proc = subprocess.Popen(
                    full_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=True
                )
                self.process[job_id] = proc

                stderr_text = proc.stderr.read()

                with open(error_log, "a", encoding="utf-8") as f:
                    f.write(f"\n--- CLIP #{idx} LOG ---\n")
                    f.write(stderr_text)

                proc.wait()

                if job["stop"]:
                    raise Exception("STOP")

                if proc.returncode != 0 or not out_clip.exists():
                    raise Exception(f"Clip {idx} failed")

            except Exception as e:
                with open(error_log, "a", encoding="utf-8") as f:
                    f.write(f"\nERROR: {str(e)}\n")

                with self.lock:
                    job["status"] = "error"
                return

        # ---------------------------------------------------------
        # 🔥 concat 리스트 생성
        # ---------------------------------------------------------
        list_file = temp_dir / f"{job_id}.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for clip in temp_clips:
                f.write(f"file '{escape(clip)}'\n")

        # ---------------------------------------------------------
        # 🔥 concat 실행
        # ---------------------------------------------------------
        cmd2 = [
            "ffmpeg",
            "-y",
            "-safe", "0",
            "-f", "concat",
            "-i", f"\"{escape(list_file)}\"",
            "-c:v", "copy",
            "-c:a", "copy",
            f"\"{escape(final_output)}\""
        ]

        full_cmd2 = " ".join(cmd2)

        try:
            proc2 = subprocess.Popen(
                full_cmd2,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True
            )
            self.process[job_id] = proc2

            stderr_text2 = proc2.stderr.read()

            with open(error_log, "a", encoding="utf-8") as f:
                f.write("\n--- CONCAT LOG ---\n")
                f.write(stderr_text2)

            proc2.wait()

            if job["stop"]:
                with self.lock:
                    job["status"] = "stopped"
                return

            if proc2.returncode != 0 or not final_output.exists():
                raise Exception("Concat failed")

        except Exception as e:
            with open(error_log, "a", encoding="utf-8") as f:
                f.write(f"\nERROR: {str(e)}\n")

            with self.lock:
                job["status"] = "error"
            return

        # ---------------------------------------------------------
        # 완료
        # ---------------------------------------------------------
        with self.lock:
            job["progress"] = 100
            job["status"] = "done"
            job["url"] = f"/results/{final_output.name}"

        # ---------------------------------------------------------
        # 임시 파일 삭제
        # ---------------------------------------------------------
        try:
            list_file.unlink(missing_ok=True)
            for clip in temp_clips:
                clip.unlink(missing_ok=True)
        except:
            pass

        with open(error_log, "a", encoding="utf-8") as f:
            f.write("\n==== EXPORT DONE ====\n")

        if job_id in self.process:
            del self.process[job_id]
