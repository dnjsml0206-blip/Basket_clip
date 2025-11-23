import json, os

STORE_PATH = "utils/analysis_store.json"

def load_store():
    if not os.path.exists(STORE_PATH):
        return []
    with open(STORE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_store(data):
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_item(item):
    data = load_store()
    data.append(item)
    save_store(data)

def delete_item(item_id):
    data = load_store()
    data = [d for d in data if d["id"] != item_id]
    save_store(data)
