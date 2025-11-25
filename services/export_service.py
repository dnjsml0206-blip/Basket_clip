import subprocess
import threading
import uuid
import shutil
from pathlib import Path
import config
from services.r2_service import download_to_path

def escape(p: Path):
    return str(p).replace("\\", "/")


class ExportManager:
    def __init__(self):
        self.jobs = {}
        self.lock = threading.Lock()
        self.process = {}

        # ffmpeg용 임시 디렉터리
        self.temp_dir = config.TMP_DIR / "export"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def create_job(self, video_name, clips):
        job_id = str(uuid.uuid4())
        with self.lock:
            self.jobs[job_id] = {
                "video": video_name,
                "clips": clips,
                "progress": 0,
                "status": "pending",
                "url": None,
                "stop": False
            }
        return job_id

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

    def worker(self, job_id, video_name: str, final_output: Path):
        """
        video_name: 원본 파일 이름 (R2: videos/{video_name})
        final_output: TMP_DIR 안 임시 mp4 경로
        """
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

        # 1) R2 → 로컬 temp 로 다운로드
        local_video = self.temp_dir / f"export_src_{job_id}_{video_name}"
        key = f"videos/{video_name}"
        try:
            download_to_path(key, local_video)
        except Exception as e:
            print("R2 다운로드 실패 (export):", e)
            with self.lock:
                job["status"] = "error"
            return

        # 2) ffmpeg concat용 임시 파일들
        temp_txt = self.temp_dir / f"{job_id}.txt"
        temp_out = self.temp_dir / f"{job_id}.mp4"

        with open(temp_txt, "w", encoding="utf-8") as f:
            for c in clips:
                f.write(f"file '{escape(local_video)}'\n")
                f.write(f"inpoint {c['start']}\n")
                f.write(f"outpoint {c['end']}\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-safe", "0",
            "-f", "concat",
            "-i", escape(temp_txt),
            "-c:v", "copy",
            "-c:a", "copy",
            str(temp_out)
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
        except FileNotFoundError:
            with self.lock:
                job["status"] = "error"
            return

        self.process[job_id] = proc

        try:
            for line in proc.stderr:
                if job["stop"]:
                    proc.kill()
                    break

                if "out_time_us=" in line:
                    try:
                        us = int(line.split("out_time_us=")[1].split()[0])
                        sec = us / 1_000_000
                        prog = min(100, int(sec / total_duration * 100))

                        with self.lock:
                            job["progress"] = prog
                    except:
                        pass

            proc.wait()

            if job["stop"]:
                with self.lock:
                    job["status"] = "stopped"
                return

            if proc.returncode == 0 and temp_out.exists():
                # temp_out → final_output 으로 이동
                shutil.move(str(temp_out), str(final_output))

                with self.lock:
                    job["progress"] = 100
                    job["status"] = "done"
                    # 프론트는 /results/.. 로 GET 하도록 유지
                    job["url"] = f"/results/{final_output.name}"
            else:
                with self.lock:
                    job["status"] = "error"

        except Exception:
            with self.lock:
                job["status"] = "error"

        finally:
            if job_id in self.process:
                del self.process[job_id]

            # 임시 파일 정리
            if temp_txt.exists():
                temp_txt.unlink(missing_ok=True)
            try:
                local_video.unlink(missing_ok=True)
            except Exception:
                pass
