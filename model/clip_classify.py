import clip
import torch
from PIL import Image

# ✅ Load CLIP and device once
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)

# ✅ Function to classify an image using CLIP
def classify_image_with_clip(image: Image.Image, prompt_list: list) -> str:
    # Preprocess image
    image_input = preprocess(image).unsqueeze(0).to(device)

    # Get image features
    with torch.no_grad():
        image_features = model.encode_image(image_input)

    # Tokenize and encode text prompts
    text_tokens = clip.tokenize(prompt_list).to(device)
    with torch.no_grad():
        text_features = model.encode_text(text_tokens)

    # Normalize and calculate similarity
    image_features /= image_features.norm(dim=-1, keepdim=True)
    text_features /= text_features.norm(dim=-1, keepdim=True)
    similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)

    # Get best matching type
    best_match_idx = similarity.argmax().item()
    best_label = prompt_list[best_match_idx].strip()

    return best_label
