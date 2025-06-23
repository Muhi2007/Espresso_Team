import json
from filelock import FileLock

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

def update_shirt_types(new_type):
    if new_type not in all_data["types"]:
        all_data["types"].append(new_type)

    with open(DB_PATH, "w") as f:
        json.dump(all_data, f, indent=2)

def update_shirt_color(new_color):
    if new_color not in all_data["colors"]:
        all_data["colors"].append(new_color)

    with open(DB_PATH, "w") as f:
        json.dump(all_data, f, indent=2)

def make_html_url(standart_url):
    val = "/" + standart_url.replace("\\", "/")
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