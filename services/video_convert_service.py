import subprocess
import os
import uuid

def convert_to_h264(input_path):
    """
    input_path: 원본 파일 (mp4)
    return: 변환된 파일 경로(output)
    """
    output_path = input_path.replace(".mp4", f"_h264_{uuid.uuid4().hex}.mp4")

    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-vcodec", "libx264",
        "-preset", "fast",
        "-acodec", "aac",
        "-movflags", "+faststart",
        "-y",  # 덮어쓰기
        output_path
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output_path
    except subprocess.CalledProcessError as e:
        print("❌ H.264 변환 실패:", e)
        return None
