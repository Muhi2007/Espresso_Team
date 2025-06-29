# app.py
from flask import Flask, render_template, request, session, redirect, url_for, flash
import os
import random as rd
import json
import re 
from werkzeug.security import generate_password_hash, check_password_hash
from filelock import FileLock
from PIL import Image

# Import your custom modules
from model.shirt_db_utils import (
    load_shirts,
    update_shirt,
    all_data, types_lst,
    make_html_url,
    load_users,
    save_users
)
from model.clip_utils import (
    get_image_embedding_pil,
    get_image_from_url,
    extract_image_url_from_temulink,
    classify_image_with_clip,
    suggest_complementary_items,
    find_most_similar_image,
    suggest_items_from_prompt
)

app = Flask(__name__)
Upload_folder = "static\\uploads"
app.config["UPLOAD_FOLDER"] = Upload_folder
app.secret_key = '6673a00bb4e05d3fb2f622c44fdfa54d81e658610b92f80cb17f24c5fa45eeed'

EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'


# --- Routes ---

@app.route("/", methods=["GET"])
def index():
    """Renders the login/signup page."""
    if 'email' in session:
        return redirect(url_for('dashboard'))
    return render_template("login.html")

@app.route('/register', methods=['POST'])
def register():
    """Handles user registration."""
    users = load_users()
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')

    if not name or not email or not password:
        flash('All fields are required.', 'error')
        return redirect(url_for('index'))
    if not re.match(EMAIL_REGEX, email):
        flash('Invalid email address format.', 'error')
        return redirect(url_for('index'))
    if email in users:
        flash('Email address already registered.', 'error')
        return redirect(url_for('index'))

    hashed_password = generate_password_hash(password)
    users[email] = {'name': name, 'password': hashed_password}
    save_users(users)
    flash('Account created successfully! Please sign in.', 'success')
    return redirect(url_for('index'))

@app.route('/login', methods=['POST'])
def login():
    """Handles user login."""
    users = load_users()
    email = request.form.get('email')
    password = request.form.get('password')

    if not re.match(EMAIL_REGEX, email):
        flash('Invalid email address format.', 'error')
        return redirect(url_for('index'))
    
    user = users.get(email)
    if user and check_password_hash(user['password'], password):
        session['email'] = email
        return redirect(url_for('dashboard'))
    else:
        flash('Invalid email or password.', 'error')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    """Handles user logout."""
    session.pop('email', None)
    session.pop('suggested_paths', None)
    session.pop('cloth_path', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

@app.route("/dashboard")
def dashboard():
    """Renders the main application page (the form) if the user is logged in."""
    if 'email' not in session:
        flash('Please sign in to access this page.', 'error')
        return redirect(url_for('index'))
    return render_template("form.html")

@app.route("/get_suggestions", methods=["POST"])
def get_suggestions():
    """Handles all suggestion requests from the tabbed form."""
    if 'email' not in session:
        return redirect(url_for('index'))
        
    input_type = request.form.get("input_type")
    category = request.form.get("category")
    style = request.form.get("style")
    print(style)
    count = int(request.form.get("count", 3))
    
    suggested_items_paths = []
    cloth_path = None
    data = load_shirts()

    if input_type == "link":
        url = request.form.get("image_url")
        if not url:
            flash("Please provide a Temu link.", "error")
            return redirect(url_for('dashboard'))

        extracted = extract_image_url_from_temulink(url)
        if not extracted: return "❌ Could not extract image URL from link.", 400
        
        image = get_image_from_url(extracted)
        if not image: return "❌ Failed to download image.", 400

        if not os.path.exists(app.config["UPLOAD_FOLDER"]): 
            os.makedirs(app.config["UPLOAD_FOLDER"])

        img_name = extracted.split('/')[-1].split('?')[0]
        img_path = os.path.join(app.config["UPLOAD_FOLDER"], img_name)
        print(img_path)

        if not os.path.exists(img_path):
            clothing_type = classify_image_with_clip(image, types_lst)
            clothing_color = classify_image_with_clip(image, all_data["colors"], clothing_type)
            clothing_mat = classify_image_with_clip(image, all_data["materials"], clothing_type)
            image_embedding = get_image_embedding_pil(image)
            if any(v is None for v in [clothing_type, clothing_color, clothing_mat, image_embedding]):
                return "❌ AI classification failed.", 500
            
            update_shirt(img_path, clothing_type, clothing_color, clothing_mat, url, image_embedding.squeeze().tolist(), image)
            data = load_shirts()
        
        cloth_path = img_path
        suggested_items_paths = suggest_complementary_items(cloth_path, count, category, style)

    elif input_type == "image":
        file = request.files.get('image_file')
        if not file or not file.filename:
            flash("Please upload an image file.", "error")
            return redirect(url_for('dashboard'))
            
        image = Image.open(file.stream).convert("RGB")
        image_embedding = get_image_embedding_pil(image)
        matched_item_path = find_most_similar_image(image_embedding, data)
        
        if not matched_item_path:
            return "❌ Could not find a similar item in the database.", 404

        cloth_path = matched_item_path
        suggested_items_paths = suggest_complementary_items(cloth_path, count, category, style)

    elif input_type == "prompt":
        prompt_text = request.form.get("prompt_text")
        if not prompt_text:
            flash("Please enter a text prompt.", "error")
            return redirect(url_for('dashboard'))
        
        suggested_items_paths = suggest_items_from_prompt(prompt_text, count, category, data)
        session['prompt_text'] = prompt_text # Store prompt text for display

    # Store only identifiers in the session
    session['suggested_paths'] = suggested_items_paths
    session['cloth_path'] = cloth_path
    
    # Now, build the results and cloth objects for rendering
    results = []
    for item_path in suggested_items_paths:
        item_details = data.get(item_path, {})
        if item_details:
            results.append({
                "name": f"{item_details.get('color')} {item_details.get('material')} {item_details.get('type')}",
                "image": make_html_url(item_path),
                "link": item_details.get("link"),
                "price": rd.randint(10, 100),
                "rating": round(rd.uniform(1.0, 5.0), 1),
                "comment": rd.choice(all_data["comments"])
            })

    cloth = None
    if cloth_path:
        print(cloth_path)
        cloth_details = data[cloth_path]
        cloth = {**cloth_details, "image": make_html_url(cloth_path), "price": rd.randint(10, 100), "rating": round(rd.uniform(2,5), 1), "name": f"{cloth_details['color']} {cloth_details['material']} {cloth_details['type']}"}
    elif 'prompt_text' in session:
        cloth = {"name": f"Suggestions for: '{session.get('prompt_text')}'", "image": None, "link": "#"}


    return render_template("result.html", item=cloth, results=results)


@app.route("/filter")
def filter_results():
    """Filters results on the results page."""
    if 'email' not in session: return redirect(url_for('index'))
    
    max_price = float(request.args.get("max_price") or 9999)
    min_rating = float(request.args.get("min_rating") or 0)
    
    suggested_paths = session.get("suggested_paths", [])
    cloth_path = session.get("cloth_path")
    data = load_shirts()

    # Re-build the full results list from the database
    full_results = []
    for item_path in suggested_paths:
        item_details = data.get(item_path, {})
        if item_details:
             full_results.append({
                "name": f"{item_details.get('color')} {item_details.get('material')} {item_details.get('type')}",
                "image": make_html_url(item_path),
                "link": item_details.get("link"),
                "price": rd.randint(10, 100), # Note: Price and rating will be random again on filter
                "rating": round(rd.uniform(1.0, 5.0), 1),
                "comment": rd.choice(all_data["comments"])
            })

    # Apply filters
    filtered_results = [item for item in full_results if float(item.get("price", 0)) <= max_price and float(item.get("rating", 0)) >= min_rating]
    
    # Re-build the cloth object for rendering
    cloth = None
    if cloth_path:
        cloth_details = data[cloth_path]
        cloth = {**cloth_details, "image": make_html_url(cloth_path), "price": rd.randint(10, 100), "rating": round(rd.uniform(2,5), 1), "name": f"{cloth_details['color']} {cloth_details['material']} {cloth_details['type']}"}
    elif 'prompt_text' in session:
         cloth = {"name": f"Suggestions for: '{session.get('prompt_text')}'", "image": None, "link": "#"}

    return render_template("result.html", item=cloth, results=filtered_results)

if __name__ == '__main__':
    app.run(debug=True)
