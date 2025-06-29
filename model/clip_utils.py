# clip_utils.py
import torch
import clip
from torchvision import transforms
from PIL import Image
import requests
from io import BytesIO
from urllib.parse import urlparse, parse_qs, unquote
from sklearn.metrics.pairwise import cosine_similarity
from model.shirt_db_utils import all_data, load_shirts
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
    image_input = preprocess(image).unsqueeze(0).to(device)

    if img_name:
        lst = []
        for type in prompt_list:
            lst.append(f"{type} {img_name}")
        prompt_list = lst

    with torch.no_grad():
        image_features = clip_model.encode_image(image_input)

    text_tokens = clip.tokenize(prompt_list).to(device)
    with torch.no_grad():
        text_features = clip_model.encode_text(text_tokens)

    image_features /= image_features.norm(dim=-1, keepdim=True)
    text_features /= text_features.norm(dim=-1, keepdim=True)
    similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)

    best_match_idx = similarity.argmax().item()
    best_label = prompt_list[best_match_idx].strip()
    if img_name:
        uzunluq = len(img_name)
        return best_label[:-uzunluq].strip()
    else:
        return best_label

def generate_complement_prompt(item_type, color, material=None, style=None):
    prompt = f"A stylish item that complements a {color} {item_type}"
    if material:
        prompt += f" made of {material}"
    if style:
        prompt = prompt.replace("stylish", f"{style} style")
    print(prompt)
    return prompt

def find_parent(item_name):
    for category, items in all_data["types"].items():
        if item_name in items:
            return category
    return None

def suggest_complementary_items(input_item_path, top_k, category, style):
    data = load_shirts()
    
    if input_item_path not in data:
        print(f"[ERROR] Input item path not found in database: {input_item_path}")
        return []

    input_item = data[input_item_path]
    prompt = generate_complement_prompt(input_item['type'], input_item['color'], input_item['material'], style)

    with torch.no_grad():
        text_tokens = clip.tokenize([prompt]).to(device)
        text_embedding = clip_model.encode_text(text_tokens)
        text_embedding = text_embedding.cpu().numpy()[0]

    similarities = []
    for item_path, item_details in data.items():
        if item_path == input_item_path:
            continue

        if find_parent(item_details["type"]) != category:
           continue

        item_embedding = np.array(item_details['embedding'])
        sim = cosine_similarity([text_embedding], [item_embedding])[0][0]
        similarities.append((sim, item_path))

    similarities.sort(reverse=True)
    return [item for _, item in similarities[:top_k]]

def find_most_similar_image(uploaded_image_embedding, data):
    """Finds the most similar image in the database to the uploaded one."""
    if uploaded_image_embedding is None:
        return None
        
    uploaded_embedding_np = uploaded_image_embedding.cpu().numpy()
    
    max_similarity = -1
    best_match_path = None

    for item_path, item_details in data.items():
        db_embedding = np.array(item_details['embedding'])
        sim = cosine_similarity(uploaded_embedding_np, [db_embedding])[0][0]
        
        if sim > max_similarity:
            max_similarity = sim
            best_match_path = item_path
            
    return best_match_path

def suggest_items_from_prompt(prompt, top_k, category, data):
    """Suggests items from the database based on a text prompt."""
    with torch.no_grad():
        text_tokens = clip.tokenize([prompt]).to(device)
        text_embedding = clip_model.encode_text(text_tokens)
        text_embedding /= text_embedding.norm(dim=-1, keepdim=True)
        text_embedding_np = text_embedding.cpu().numpy()

    similarities = []
    for item_path, item_details in data.items():
        if find_parent(item_details.get("type")) != category:
            continue
            
        image_embedding = np.array(item_details['embedding']).reshape(1, -1)
        # Assuming embeddings are already normalized. If not, normalize them here.
        
        sim = cosine_similarity(text_embedding_np, image_embedding)[0][0]
        similarities.append((sim, item_path))
        
    similarities.sort(reverse=True, key=lambda x: x[0])
    
    return [item for _, item in similarities[:top_k]]
