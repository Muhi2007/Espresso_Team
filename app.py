# app.py
from flask import Flask, request, render_template
import os

from model.shirt_db_utils import (
    update_shirt_types,
    update_shirt_color,
    update_shirt,
    data, all_data, types_lst
)

from model.clip_utils import (
    get_image_embedding_pil,
    get_image_from_url,
    extract_image_url_from_temulink,
    classify_image_with_clip,
    suggest_complementary_items
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
        
        clothing_type = classify_image_with_clip(image, types_lst)
        if clothing_type is None:
            return "❌ Could not classify clothing type.", 500
        
        clothing_color = classify_image_with_clip(image, all_data["colors"], clothing_type)
        if clothing_color is None:
            return "❌ Could not classify clothing color.", 500
        
        clothing_mat = classify_image_with_clip(image, all_data["materials"], clothing_type)
        if clothing_mat is None:
            return "❌ Could not classify clothing material.", 500
        
        image_embedding = get_image_embedding_pil(image)
        if image_embedding is None:
            return "❌ Could not generate image embedding.", 500
        image_embedding = image_embedding.squeeze().tolist()
        
        update_shirt(img_path, clothing_type, clothing_color, clothing_mat, url, image_embedding)
        print(f"Image saved and updated: {img_path}")
        suggested_items = suggest_complementary_items(img_path)
        print(f"Suggested items: {suggested_items}")
        
        return render_template("result.html", img_url=extracted, clothing_type=clothing_type, clothing_color=clothing_color, outfits=suggested_items)
    else:
        #Else, just get from the database:

        data_shirt = data.get(img_path, {})
        clothing_type = data_shirt.get("type", "Unknown")
        clothing_color = data_shirt.get("color", "Unknown")
        clothing_mat = data_shirt.get("material", "Unknown")
        
        suggested_items = suggest_complementary_items(img_path)
        print(f"Suggested items: {suggested_items}")
        return render_template("result.html", img_url=extracted, clothing_type=clothing_type, clothing_color=clothing_color, outfits=suggested_items)
