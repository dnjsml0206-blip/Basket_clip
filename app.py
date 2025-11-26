from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, abort
from routes.index import bp as index_bp
from routes.basket import bp as basket_bp
from routes.yolo import bp as yolo_bp
from routes.export import bp as export_bp
from routes.result_page import bp as result_bp
from routes.upload import bp as upload_bp
from routes.videos import bp as videos_bp
from services.r2_service import r2_stream_video

app = Flask(__name__)
app.secret_key = "super-secret-key-123"

app.register_blueprint(index_bp)
app.register_blueprint(basket_bp)
app.register_blueprint(yolo_bp)
app.register_blueprint(export_bp)
app.register_blueprint(result_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(videos_bp)

# 🔥 R2 영상 스트리밍
@app.route("/videos/<path:filename>")
def stream_video(filename):
    resp = r2_stream_video(filename, request)
    if resp is None:
        return abort(404)
    return resp

if __name__ == "__main__":
    print("http://127.0.0.1:8000")
    app.run(host="0.0.0.0", port=8000, debug=True)
