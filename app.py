from flask import Flask, send_from_directory, send_file, Response, request, abort
from pathlib import Path
import config
import mimetypes
import re
import os

from routes.index import bp as index_bp
from routes.basket import bp as basket_bp
from routes.yolo import bp as yolo_bp
from routes.export import bp as export_bp
from routes.result_page import bp as result_bp
from routes.full import full_bp
from routes.upload import bp as upload_bp
from routes.videos import bp as videos_bp


app = Flask(__name__)

app.secret_key = "super-secret-key-123"

app.register_blueprint(index_bp)
app.register_blueprint(basket_bp)
app.register_blueprint(yolo_bp)
app.register_blueprint(export_bp)
app.register_blueprint(result_bp)
app.register_blueprint(full_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(videos_bp)




@app.route("/videos/<path:filename>")
def serve_video(filename):
    file_path = str(config.LOCAL_VIDEOS / filename)

    if not os.path.exists(file_path):
        return abort(404)

    file_size = os.path.getsize(file_path)
    mime = mimetypes.guess_type(file_path)[0] or "video/mp4"

    range_header = request.headers.get("Range", None)
    if range_header:
        # 예: "bytes=12345-"
        byte1, byte2 = 0, None

        m = range_header.replace("bytes=", "").split("-")
        if m[0]:
            byte1 = int(m[0])
        if len(m) > 1 and m[1]:
            byte2 = int(m[1])

        byte2 = byte2 if byte2 is not None else file_size - 1
        length = byte2 - byte1 + 1

        def stream():
            with open(file_path, "rb") as f:
                f.seek(byte1)
                remaining = length
                chunk_size = 1024 * 1024  # 1MB씩 스트리밍

                while remaining > 0:
                    chunk = f.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    yield chunk
                    remaining -= len(chunk)

        rv = Response(stream(), status=206, mimetype=mime)
        rv.headers.add("Content-Range", f"bytes {byte1}-{byte2}/{file_size}")
        rv.headers.add("Accept-Ranges", "bytes")
        rv.headers.add("Content-Length", str(length))
        return rv

    # Range 없는 경우 전체 스트리밍
    def full_stream():
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)  # 1MB씩
                if not chunk:
                    break
                yield chunk

    rv = Response(full_stream(), mimetype=mime)
    rv.headers.add("Content-Length", str(file_size))
    return rv


@app.route("/results/<path:filename>")
def serve_result(filename):
    return send_from_directory(config.RESULT_DIR, filename)

if __name__ == "__main__":
    print("서버 실행: http://127.0.0.1:8000")
    app.run(host="0.0.0.0", port=8000, debug=True)
