# clip_utils.py
import torch
import clip
from torchvision import transforms
from PIL import Image
import requests
from io import BytesIO
from urllib.parse import urlparse, parse_qs, unquote
from sklearn.metrics.pairwise import cosine_similarity
from model.shirt_db_utils import data, all_data
import numpy as np



# Load CLIP model and preprocessing globally
device = "cuda" if torch.cuda.is_available() else "cpu"
clip_model, preprocess = clip.load("ViT-B/32", device=device)

# --- A. Embedding from PIL image ---
def get_image_embedding_pil(image):
    try:
        image_input = preprocess(image).unsqueeze(0).to(device)
        with torch.no_grad():
            image_features = clip_model.encode_image(image_input)
            image_features /= image_features.norm(dim=-1, keepdim=True)
        return image_features
    except Exception as e:
        print(f"[ERROR] Failed to embed image: {e}")
        return None

# --- B. Download image from a URL ---
def get_image_from_url(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content)).convert("RGB")
        return image
    except Exception as e:
        print(f"[ERROR] Could not fetch image from URL: {e}")
        return None

# --- C. Extract image URL from Temu link ---
def extract_image_url_from_temulink(full_url):
    try:
        query_params = parse_qs(urlparse(full_url).query)
        encoded_img_url = query_params.get("top_gallery_url", [None])[0]
        if encoded_img_url:
            return unquote(encoded_img_url)
    except Exception as e:
        print(f"[ERROR] Could not extract image URL: {e}")
    return None

def classify_image_with_clip(image: Image.Image, prompt_list: list, img_name = None) -> str:
    # Preprocess image
    image_input = preprocess(image).unsqueeze(0).to(device)

    if img_name:
        lst = []
        for type in prompt_list:
            lst.append(f"{type} {img_name}")
        prompt_list = lst

    # Get image features
    with torch.no_grad():
        image_features = clip_model.encode_image(image_input)

    # Tokenize and encode text prompts
    text_tokens = clip.tokenize(prompt_list).to(device)
    with torch.no_grad():
        text_features = clip_model.encode_text(text_tokens)

    # Normalize and calculate similarity
    image_features /= image_features.norm(dim=-1, keepdim=True)
    text_features /= text_features.norm(dim=-1, keepdim=True)
    similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)

    # Get best matching type
    best_match_idx = similarity.argmax().item()
    best_label = prompt_list[best_match_idx].strip()
    if img_name:
        uzunluq = len(img_name)
        return best_label[:-uzunluq].strip()
    else:
        return best_label

def generate_complement_prompt(item_type, color, material=None):
    prompt = f"A stylish item that complements a {color} {item_type}"
    if material:
        prompt += f" made of {material}"
    return prompt

def find_parent(clothing_dict, item_name):
    for category, items in clothing_dict.items():
        if item_name in items:
            return category
    return None

print(find_parent(all_data['types'], data['static\\uploads\\8c42b4cf-6793-4007-b6a8-9f125270f88a.jpg']['type']))

def suggest_complementary_items(input_item_path, top_k=3):
    # 1. Generate prompt
    input_item = data[input_item_path]
    tip = find_parent(all_data["types"], input_item['type'])
    print(tip)
    prompt = generate_complement_prompt(input_item['type'], input_item['color'])
    print(prompt)

    # 2. Encode prompt using CLIP
    with torch.no_grad():
        text_tokens = clip.tokenize([prompt]).to(device)
        text_embedding = clip_model.encode_text(text_tokens)
        text_embedding = text_embedding.cpu().numpy()[0]

    similarities = []
    for item in data:
        # Skip the same item
        if item == input_item_path:
            continue

        # Optional: filter out same type
        if find_parent(all_data["types"], data[item]['type']) == tip:
            print(data[item]['type'])
            continue

        item_embedding = np.array(data[item]['embedding'])
        sim = cosine_similarity([text_embedding], [item_embedding])[0][0]
        similarities.append((sim, item))

    # 4. Sort and return
    similarities.sort(reverse=True)
    return [item for _, item in similarities[:top_k]]
