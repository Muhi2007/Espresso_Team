import json
from filelock import FileLock

DB_PATH = "fashion_data\\shirt_db.json"
LOCK_PATH = "fashion_data\\shirt_db.json.lock"

def load_shirt_data():
    with FileLock(LOCK_PATH):
        with open(DB_PATH, "r") as f:
            data = json.load(f)
    return data

def update_shirt_types(new_type):
    with FileLock(LOCK_PATH):
        with open(DB_PATH, "r") as f:
            data = json.load(f)

        if new_type not in data["types"]:
            data["types"].append(new_type)

        with open(DB_PATH, "w") as f:
            json.dump(data, f, indent=2)

def update_shirt_color(new_color):
    with FileLock(LOCK_PATH):
        with open(DB_PATH, "r") as f:
            data = json.load(f)

        if new_color not in data["colors"]:
            data["colors"].append(new_color)

        with open(DB_PATH, "w") as f:
            json.dump(data, f, indent=2)
