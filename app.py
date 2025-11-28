from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, abort, jsonify
from routes.index import bp as index_bp
from routes.basket import bp as basket_bp
from routes.yolo import bp as yolo_bp
from routes.export import bp as export_bp
from routes.result_page import bp as result_bp
from routes.upload import bp as upload_bp
from routes.videos import bp as videos_bp
from services.r2_service import r2_stream_video, r2_list_videos
from routes.analysis_end import bp as analysis_end_bp
from routes.test_r2_permission import bp as test_r2_permission_bp
from routes.delete_video import bp as delete_video_bp

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')
app.secret_key = "super-secret-key-123"

app.register_blueprint(index_bp)
app.register_blueprint(basket_bp)
app.register_blueprint(yolo_bp)
app.register_blueprint(export_bp)
app.register_blueprint(result_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(videos_bp)
app.register_blueprint(analysis_end_bp)
app.register_blueprint(test_r2_permission_bp)
app.register_blueprint(delete_video_bp)


# 🔥 디버깅: R2 파일 목록 확인
@app.route("/debug/r2_files")
def debug_r2_files():
    files = r2_list_videos()
    return jsonify(files)

# 🔥 R2 영상 스트리밍
@app.route("/videos/<path:filename>")
def stream_video(filename):
    print(f"🔍 Streaming request: {filename}")
    
    # R2에 파일이 있는지 확인
    all_files = r2_list_videos()
    if filename not in all_files:
        print(f"❌ File not found in R2: {filename}")
        print(f"📁 Available files: {all_files}")
        return abort(404)
    
    resp = r2_stream_video(filename, request)
    if resp is None:
        print(f"❌ Stream failed: {filename}")
        return abort(500)
    
    print(f"✅ Streaming success: {filename}")
    return resp

if __name__ == "__main__":
    print("http://127.0.0.1:8000")
    app.run(host="0.0.0.0", port=8000, debug=True)
