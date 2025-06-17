# clip_utils.py
import torch
import clip
from torchvision import transforms
from PIL import Image
import requests
from io import BytesIO
from urllib.parse import urlparse, parse_qs, unquote


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

def classify_image_with_clip(image: Image.Image, prompt_list: list) -> str:
    # Preprocess image
    image_input = preprocess(image).unsqueeze(0).to(device)

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

    return best_label