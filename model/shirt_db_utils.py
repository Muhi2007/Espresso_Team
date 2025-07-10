# model/shirt_db_utils.py

import json
from filelock import FileLock
import os

DB_PATH = "fashion_data\\shirt_db.json"
LOCK_PATH = "fashion_data\\shirt_db.json.lock"

# Initial loading of data (consider moving this into a function if it causes issues with imports)
with FileLock(LOCK_PATH):
    try:
        with open(DB_PATH, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {} # Initialize if file doesn't exist or is empty

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

# Modified update_shirt function
def update_shirt(name, new_type, new_color, new_material, new_link, new_embedding, image=None, rating=None, comment=None): # Made image=None default
    global data # Ensure we are modifying the global 'data'
    if name not in data:
        data[name] = {
            "type": new_type,
            "color": new_color,
            "material": new_material,
            "link": new_link,
            "embedding": new_embedding,
            "rating": rating,
            "comment": comment
        }
        # Only save image if an image object is provided
        if image:
            img_dir = os.path.dirname(name)
            if not os.path.exists(img_dir):
                os.makedirs(img_dir)
            image.save(name) # 'name' here should be the full path (e.g., static/uploads/img.png)
    else:
        # Update existing item's details
        data[name]["type"] = new_type
        data[name]["color"] = new_color
        data[name]["material"] = new_material # Ensure material is also updated
        data[name]["link"] = new_link
        data[name]["embedding"] = new_embedding
        if rating is not None:
            data[name]["rating"] = rating
        if comment is not None:
            data[name]["comment"] = comment
        # We don't save the image again if it already exists, as it's already on disk

    with FileLock(LOCK_PATH):
        with open(DB_PATH, "w") as f:
            json.dump(data, f, indent=2)