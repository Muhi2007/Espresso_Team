# app.py
from flask import Flask, render_template, request, session
import os
import random as rd

from model.shirt_db_utils import (
    load_shirts,
    update_shirt,
    all_data, types_lst,
    make_html_url
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
app.secret_key = '6673a00bb4e05d3fb2f622c44fdfa54d81e658610b92f80cb17f24c5fa45eeed' # Change this to a secure key in production


@app.route("/", methods=["GET"])
def home():
    return render_template("form.html")

@app.route("/analyze", methods=["POST"])
def from_url():
    results = []
    cloth = {}
    url = request.form.get("image_url")
    category = request.form.get("category")
    count = int(request.form.get("count"), 11)
    #if category:
        #update_shirt_types(category)

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
        
        update_shirt(img_path, clothing_type, clothing_color, clothing_mat, url, image_embedding, image)

        print(f"Image saved and updated: {img_path}")

        suggested_items = suggest_complementary_items(img_path, count, category)
        data = load_shirts()
        for item in suggested_items:
            results.append({
                "name": data[item]["color"] +" "+  data[item]["material"] +" "+ data[item]["type"],
                "image": make_html_url(item),
                "link": data[item]["link"],
                "price": rd.randint(10, 100),  # Random price for demonstration
                "rating": rd.uniform(1.0, 5.0),  # Random rating for demonstration
                "comment": rd.choice(all_data["comments"]) # Random comment from predefined list
            })
        
        print(f"Results: {results}")

        cloth["image"] = make_html_url(os.path.join(app.config["UPLOAD_FOLDER"], img_name))
        cloth["name"] = clothing_color +" "+ clothing_mat +" "+ clothing_type
        cloth["link"] = url
        cloth["price"] = rd.randint(10, 100)
        cloth["rating"] = rd.uniform(2,5)

    else:
        #Else, just get from the database:
        data = load_shirts()

        clothing_type = data[img_path]["type"]
        clothing_color = data[img_path]["color"]
        clothing_mat = data[img_path]["material"] 

        suggested_items = suggest_complementary_items(img_path, count, category)
        
        for item in suggested_items:
            results.append({
                "name": data[item]["color"] +" "+  data[item]["material"] +" "+ data[item]["type"],
                "image": make_html_url(item),
                "link": data[item]["link"],
                "price": rd.randint(10, 100),  # Random price for demonstration
                "rating": rd.uniform(1.0, 5.0),  # Random rating for demonstration
                "comment": rd.choice(all_data["comments"]) # Random comment from predefined list
            })

        cloth["image"] = make_html_url(os.path.join(app.config["UPLOAD_FOLDER"], img_name))
        cloth["name"] = clothing_color +" "+ clothing_mat +" "+ clothing_type
        cloth["link"] = url
        cloth["price"] = rd.randint(10, 100)
        cloth["rating"] = rd.uniform(2,5)

    session["results"] = results
    session["cloth"] = cloth

    return render_template("result.html", item = cloth, results = results)

@app.route("/filter")
def filter_results():
    max_price = float(request.args.get("max_price") or 9999)
    min_rating = float(request.args.get("min_rating") or 0)

    results = session.get("results", [])
    cloth = session.get("cloth", {})

    filtered = []
    for item in results:
        if float(item.get("price", 0)) > max_price:
            continue
        if float(item.get("rating", 0)) < min_rating:
            continue
        filtered.append(item)
    print(f"Filtered results: {filtered}")

    return render_template("result.html", item = cloth, results=filtered)
