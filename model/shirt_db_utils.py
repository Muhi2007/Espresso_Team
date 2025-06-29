import json
from filelock import FileLock
import os

DB_PATH = "fashion_data\\shirt_db.json"
LOCK_PATH = "fashion_data\\shirt_db.json.lock"

with FileLock(LOCK_PATH):
    with open(DB_PATH, "r") as f:
        data = json.load(f)

with FileLock("fashion_data\\types_db.json.lock"):
    with open("fashion_data\\types_db.json", "r") as f:
        all_data = json.load(f)

def load_shirts():
    with FileLock(LOCK_PATH):
        with open(DB_PATH, "r") as f:
            return json.load(f)
        
def load():
    types_lst = []
    for type in all_data["types"]:
        for i in all_data["types"][type]:
            types_lst.append(i)
    return types_lst

types_lst = load()

# --- User Management ---
USERS_DB_PATH = "user_data\\users.json"
USERS_DB_LOCK_PATH = "user_data\\users.json.lock"


def load_users():
    """Loads users from the JSON database file, handling empty files."""
    if not os.path.exists(USERS_DB_PATH):
        return {}
    with FileLock(USERS_DB_LOCK_PATH):
        if os.path.getsize(USERS_DB_PATH) == 0:
            return {}
        with open(USERS_DB_PATH, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}

def save_users(users):
    """Saves the users dictionary to the JSON database file."""
    with FileLock(USERS_DB_LOCK_PATH):
        with open(USERS_DB_PATH, "w") as f:
            json.dump(users, f, indent=4)


def make_html_url(standart_url):
    val = "/" + standart_url.replace("\\", "/")
    print(val)
    return val

def update_shirt(name, new_type, new_color, new_material, new_link, new_embedding, image):
        if name not in data:
            data[name] = {"type": new_type, "color": new_color, "material":new_material, "link": new_link, "embedding": new_embedding}
            image.save(name)
        else:
            data[name]["type"] = new_type
            data[name]["color"] = new_color
            data[name]["link"] = new_link
            data[name]["embedding"] = new_embedding
        
        with FileLock(LOCK_PATH):
            with open(DB_PATH, "w") as f:
                json.dump(data, f, indent=2)