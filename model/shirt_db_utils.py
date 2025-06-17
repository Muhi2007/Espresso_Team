import json
from filelock import FileLock

DB_PATH = "fashion_data\\shirt_db.json"
LOCK_PATH = "fashion_data\\shirt_db.json.lock"


with FileLock(LOCK_PATH):
    with open(DB_PATH, "r") as f:
        data = json.load(f)


def update_shirt_types(new_type):
    if new_type not in data["types"]:
        data["types"].append(new_type)

    with open(DB_PATH, "w") as f:
        json.dump(data, f, indent=2)

def update_shirt_color(new_color):
    if new_color not in data["colors"]:
        data["colors"].append(new_color)

    with open(DB_PATH, "w") as f:
        json.dump(data, f, indent=2)

def update_shirt(name, new_type, new_color):
        if name not in data["shirts"]:
            data["shirts"][name] = {"type": new_type, "color": new_color}
        else:
            data["shirts"][name]["type"] = new_type
            data["shirts"][name]["color"] = new_color

        with open(DB_PATH, "w") as f:
            json.dump(data, f, indent=2)