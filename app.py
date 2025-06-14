# app.py
from flask import Flask, request, render_template

from model.clip_classify import classify_image_with_clip

from model.shirt_db_utils import (
    update_shirt_types,
    load_shirt_data,
    update_shirt_color
)

from model.clip_utils import (
    get_image_embedding_pil,
    get_image_from_url,
    extract_image_url_from_temulink
)

app = Flask(__name__)


@app.route("/", methods=["GET"])
def home():
    return render_template("form.html")

@app.route("/from-url", methods=["POST"])
def from_url():
    data = load_shirt_data()
    url = request.form.get("image_url")
    extracted = extract_image_url_from_temulink(url)

    if not extracted:
        return "❌ Could not extract image URL from link.", 400

    image = get_image_from_url(extracted)
    if not image:
        return "❌ Failed to download image.", 400

    embedding = get_image_embedding_pil(image)
    if embedding is None:
        return "❌ Failed to process image.", 500
    
    if not url:
        return "No URL provided", 400
    
    clothing_type = classify_image_with_clip(image, data["types"])
    if clothing_type is None:
        return "❌ Could not classify clothing type.", 500
    clothing_color = classify_image_with_clip(image, data["colors"])
    if clothing_color is None:
        return "❌ Could not classify clothing color.", 500
    
    update_shirt_color(clothing_color)
    update_shirt_types(clothing_type)
    return render_template("result.html", img_url=extracted, clothing_type=clothing_type, clothing_color=clothing_color)
