# app.py
from flask import Flask, request, render_template
import os

from model.shirt_db_utils import (
    update_shirt_types,
    update_shirt_color,
    update_shirt,
    data
)

from model.clip_utils import (
    get_image_embedding_pil,
    get_image_from_url,
    extract_image_url_from_temulink,
    classify_image_with_clip
)

app = Flask(__name__)
Upload_folder = "static\\uploads"
app.config["UPLOAD_FOLDER"] = Upload_folder




@app.route("/", methods=["GET"])
def home():
    return render_template("form.html")

@app.route("/from-url", methods=["POST"])
def from_url():
    url = request.form.get("image_url")
    if not url:
        return "❌ No URL provided", 400

    extracted = extract_image_url_from_temulink(url)
    if not extracted:
        return "❌ Could not extract image URL from link.", 400

    image = get_image_from_url(extracted)
    if not image:
        return "❌ Failed to download image.", 400

    img_name = extracted.replace("https://img.kwcdn.com/product/fancy/", "")
    img_path = os.path.join(app.config["UPLOAD_FOLDER"], img_name)

    # Check if the image already exists
    if not os.path.exists(img_path):
        #If not, then use AI for color and type:

        image.save(img_path)
        
        clothing_type = classify_image_with_clip(image, data["types"])
        if clothing_type is None:
            return "❌ Could not classify clothing type.", 500
        
        clothing_color = classify_image_with_clip(image, data["colors"])
        if clothing_color is None:
            return "❌ Could not classify clothing color.", 500
        
        update_shirt(img_name.replace(".jpg", ""), clothing_type, clothing_color)
        
        return render_template("result.html", img_url=extracted, clothing_type=clothing_type, clothing_color=clothing_color)
    else:
        #Else, just get from the database:

        data_shirt = data["shirts"].get(img_name.replace(".jpg", ""), {})
        clothing_type = data_shirt.get("type", "Unknown")
        clothing_color = data_shirt.get("color", "Unknown")

        return render_template("result.html", img_url = extracted, clothing_type = clothing_type, clothing_color = clothing_color)
