from flask import Blueprint, render_template, jsonify, request
from services.store_service import load_store, add_item, delete_item
from services.r2_service import r2_list_videos
from uuid import uuid4

bp = Blueprint("index", __name__)

@bp.route("/")
def index():
    videos = r2_list_videos()
    return render_template("index.html", videos=videos)

@bp.route("/saved", methods=["GET"])
def saved_get():
    return jsonify(load_store())

@bp.route("/saved", methods=["POST"])
def saved_post():
    body = request.json
    item = {
        "id": str(uuid4()),
        "video": body["video"],
        "created": body.get("created"),
        "clips": body.get("clips", [])
    }
    add_item(item)
    return jsonify({"status": "ok"})

@bp.route("/saved/<item_id>", methods=["DELETE"])
def saved_delete(item_id):
    delete_item(item_id)
    return jsonify({"status": "deleted"})
