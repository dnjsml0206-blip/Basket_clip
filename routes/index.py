from flask import Blueprint, render_template, jsonify, request
import config
from services.store_service import load_store, add_item, delete_item
from uuid import uuid4

bp = Blueprint("index", __name__)

@bp.route("/")
def index():
    videos = [f.name for f in config.LOCAL_VIDEOS.glob("*.mp4")]
    return render_template("index.html", videos=videos)



@bp.route("/saved", methods=["GET"])
def get_saved():
    return jsonify(load_store())

@bp.route("/saved", methods=["POST"])
def save_item():
    body = request.json
    item = {
        "id": str(uuid4()),
        "video": body["video"],
        "created": body["created"],
        "clips": body.get("clips", [])
    }
    add_item(item)
    return jsonify({"status": "ok"})

@bp.route("/saved/<item_id>", methods=["DELETE"])
def remove_item(item_id):
    delete_item(item_id)
    return jsonify({"status": "deleted"})
