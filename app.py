# app.py
from flask import Flask, render_template, request, session, redirect, url_for, flash
import os
import random as rd
import json
import re 
from werkzeug.security import generate_password_hash, check_password_hash
from filelock import FileLock
from PIL import Image
from io import BytesIO 

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
    session.pop('new_item_to_detail', None) 
    # Also clear 'image_embedding_temp' if it was stored
    session.pop('image_embedding_temp', None) 
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
    count = int(request.form.get("count", 3))
    
    data = load_shirts()
    
    # Store parameters for redirection after details are added
    session['redirect_params_after_details'] = {
        "category": category,
        "style": style,
        "count": count
    }

    if input_type == "link":
        url = request.form.get("image_url")
        if not url:
            flash("Please provide a Temu link.", "error")
            return redirect(url_for('dashboard'))

        extracted = extract_image_url_from_temulink(url)
        if not extracted: 
            flash("Could not extract image URL from link.", "error")
            return redirect(url_for('dashboard'))
        
        image = get_image_from_url(extracted)
        if not image: 
            flash("Failed to download image.", "error")
            return redirect(url_for('dashboard'))

        if not os.path.exists(app.config["UPLOAD_FOLDER"]): 
            os.makedirs(app.config["UPLOAD_FOLDER"])

        img_name = extracted.split('/')[-1].split('?')[0]
        base_name, ext = os.path.splitext(img_name)
        counter = 1
        final_img_name = img_name
        while os.path.exists(os.path.join(app.config["UPLOAD_FOLDER"], final_img_name)):
            final_img_name = f"{base_name}_{counter}{ext}"
            counter += 1

        img_path_on_disk = os.path.join(app.config["UPLOAD_FOLDER"], final_img_name)
        
        is_existing_item = False
        existing_item_path = None
        for path, details in data.items():
            if details.get('link') == url: # Check by link if it's a Temu link already in DB
                is_existing_item = True
                existing_item_path = path
                break
        
        # If it's not an existing item based on link, check if a file with this name already exists
        # This prevents re-analyzing and re-saving if the *exact same* file was uploaded previously by path
        if not is_existing_item and img_path_on_disk in data:
            is_existing_item = True
            existing_item_path = img_path_on_disk


        if not is_existing_item:
            # Save the image to disk immediately
            image.save(img_path_on_disk)

            clothing_type = classify_image_with_clip(image, types_lst)
            clothing_color = classify_image_with_clip(image, all_data["colors"], clothing_type)
            clothing_mat = classify_image_with_clip(image, all_data["materials"], clothing_type)
            # Generate embedding here and store it temporarily in session if needed for `add_shirt_details`
            # OR re-calculate it in add_shirt_details based on the saved image.
            # Given the error, we will RE-CALCULATE it in add_shirt_details.
            
            if any(v is None for v in [clothing_type, clothing_color, clothing_mat]): # Embedding not classified here
                # If classification fails, delete the saved image to avoid clutter
                if os.path.exists(img_path_on_disk):
                    os.remove(img_path_on_disk)
                flash("AI classification failed.", "error")
                return redirect(url_for('dashboard'))
            
            # Store only lightweight metadata in session
            session['new_item_to_detail'] = {
                "name": img_path_on_disk, 
                "type": clothing_type,
                "color": clothing_color,
                "material": clothing_mat,
                "link": url
            }
            return redirect(url_for('ask_for_details')) 

        else: # Item already exists
            session['cloth_path'] = existing_item_path
            suggested_items_paths = suggest_complementary_items(existing_item_path, count, category, style)
            session['suggested_paths'] = suggested_items_paths 

    elif input_type == "image":
        file = request.files.get('image_file')
        if not file or not file.filename:
            flash("Please upload an image file.", "error")
            return redirect(url_for('dashboard'))
            
        image_stream_for_pil = BytesIO(file.read())
        image = Image.open(image_stream_for_pil).convert("RGB")
        
        # Even for existing image check, we avoid storing embedding in session
        image_embedding_for_search = get_image_embedding_pil(image) # Temporarily get embedding for search
        matched_item_path = None
        if image_embedding_for_search is not None:
            matched_item_path = find_most_similar_image(image_embedding_for_search, data)
        
        if not matched_item_path: # New image, not found in DB
            clothing_type = classify_image_with_clip(image, types_lst)
            clothing_color = classify_image_with_clip(image, all_data["colors"], clothing_type)
            clothing_mat = classify_image_with_clip(image, all_data["materials"], clothing_type)
            
            if any(v is None for v in [clothing_type, clothing_color, clothing_mat]):
                flash("AI classification failed.", "error")
                return redirect(url_for('dashboard'))

            # Generate a unique name for the new image and save it immediately
            original_filename = file.filename
            base_name, ext = os.path.splitext(original_filename)
            unique_filename = f"uploaded_{rd.randint(10000, 99999)}_{base_name}{ext}"
            img_path_on_disk = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
            image.save(img_path_on_disk) # Save the image to disk
            
            # Store only lightweight metadata in session
            session['new_item_to_detail'] = {
                "name": img_path_on_disk,
                "type": clothing_type,
                "color": clothing_color,
                "material": clothing_mat,
                "link": "" 
            }
            return redirect(url_for('ask_for_details')) 

        else: # Image already exists in DB
            session['cloth_path'] = matched_item_path
            suggested_items_paths = suggest_complementary_items(matched_item_path, count, category, style)
            session['suggested_paths'] = suggested_items_paths 

    elif input_type == "prompt":
        prompt_text = request.form.get("prompt_text")
        if not prompt_text:
            flash("Please enter a text prompt.", "error")
            return redirect(url_for('dashboard'))
        
        suggested_items_paths = suggest_items_from_prompt(prompt_text, count, category, data)
        session['prompt_text'] = prompt_text 
        session['suggested_paths'] = suggested_items_paths 
        session['cloth_path'] = None 

    return render_template_results()


@app.route("/ask_for_details", methods=["GET"])
def ask_for_details():
    """Renders a popup to ask for comment and rating for a new item."""
    if 'email' not in session:
        return redirect(url_for('index'))
    if 'new_item_to_detail' not in session:
        flash("No new item to add details for.", "error")
        return redirect(url_for('dashboard'))

    new_item_info = session['new_item_to_detail']
    return render_template("add_details_popup.html", item_path=make_html_url(new_item_info['name']))

@app.route("/add_shirt_details", methods=["POST"])
def add_shirt_details():
    """Receives rating and comment, then saves the new shirt and redirects to results."""
    if 'email' not in session:
        return redirect(url_for('index'))
    if 'new_item_to_detail' not in session:
        flash("No new item details found for saving.", "error")
        return redirect(url_for('dashboard'))

    rating = request.form.get("rating")
    comment = request.form.get("comment")

    if not rating or not comment:
        flash("Rating and comment are required.", "error")
        return redirect(url_for('ask_for_details'))
    try:
        rating = float(rating)
        if not (0.0 <= rating <= 5.0):
            flash("Rating must be between 0.0 and 5.0.", "error")
            return redirect(url_for('ask_for_details'))
    except ValueError:
        flash("Invalid rating format. Please enter a number.", "error")
        return redirect(url_for('ask_for_details'))

    new_item_details = session.pop('new_item_to_detail') 
    redirect_params = session.pop('redirect_params_after_details') 

    img_path_on_disk = new_item_details['name']

    # --- RE-OPEN IMAGE AND GENERATE EMBEDDING HERE ---
    try:
        # Open the image from the disk where it was just saved
        image_from_disk = Image.open(img_path_on_disk).convert("RGB")
        image_embedding = get_image_embedding_pil(image_from_disk)
        if image_embedding is None:
            # If embedding generation fails, remove the item and flash error
            if os.path.exists(img_path_on_disk):
                os.remove(img_path_on_disk)
            flash("Failed to generate image embedding for the item.", "error")
            return redirect(url_for('dashboard'))
    except Exception as e:
        # Handle cases where image file might be corrupted or unreadable
        if os.path.exists(img_path_on_disk):
            os.remove(img_path_on_disk)
        flash(f"Error processing image from disk: {e}", "error")
        return redirect(url_for('dashboard'))
    # --------------------------------------------------

    update_shirt(
        name=img_path_on_disk,
        new_type=new_item_details['type'],
        new_color=new_item_details['color'],
        new_material=new_item_details['material'],
        new_link=new_item_details['link'],
        new_embedding=image_embedding.squeeze().tolist(), # Pass the newly generated embedding
        image=None, 
        rating=rating,
        comment=comment
    )

    data = load_shirts()
    suggested_items_paths = suggest_complementary_items(
        img_path_on_disk, 
        redirect_params['count'], 
        redirect_params['category'], 
        redirect_params['style']
    )
    
    session['suggested_paths'] = suggested_items_paths
    session['cloth_path'] = img_path_on_disk 

    return render_template_results()


# Helper function to avoid code duplication for rendering results
def render_template_results():
    data = load_shirts()
    suggested_items_paths = session.get('suggested_paths', [])
    cloth_path = session.get('cloth_path')
    prompt_text = session.get('prompt_text')

    results = []
    for item_path in suggested_items_paths:
        item_details = data.get(item_path, {})
        if item_details:
            results.append({
                "name": f"{item_details.get('color')} {item_details.get('material')} {item_details.get('type')}",
                "image": make_html_url(item_path),
                "link": item_details.get("link"),
                "rating": item_details.get("rating", round(rd.uniform(1.0, 5.0), 1)),
                "comment": item_details.get("comment", rd.choice(all_data["comments"]))
            })

    cloth = None
    if cloth_path:
        cloth_details = data.get(cloth_path, {})
        cloth = {
            **cloth_details, 
            "image": make_html_url(cloth_path), 
            "rating": cloth_details.get("rating", round(rd.uniform(2,5), 1)), 
            "name": f"{cloth_details.get('color', '')} {cloth_details.get('material', '')} {cloth_details.get('type', '')}"
        }
    elif prompt_text:
        cloth = {"name": f"Suggestions for: '{prompt_text}'", "image": None, "link": "#"}
    
    return render_template("result.html", item=cloth, results=results)


@app.route("/filter")
def filter_results():
    """Filters results on the results page."""
    if 'email' not in session: return redirect(url_for('index'))
    
    max_price = float(request.args.get("max_price") or 9999)
    min_rating = float(request.args.get("min_rating") or 0)
    
    suggested_paths = session.get("suggested_paths", [])
    cloth_path = session.get("cloth_path")
    prompt_text = session.get("prompt_text") 
    data = load_shirts()

    full_results = []
    for item_path in suggested_paths:
        item_details = data.get(item_path, {})
        if item_details:
             full_results.append({
                "name": f"{item_details.get('color')} {item_details.get('material')} {item_details.get('type')}",
                "image": make_html_url(item_path),
                "link": item_details.get("link"),
                "rating": item_details.get("rating", round(rd.uniform(1.0, 5.0), 1)),
                "comment": item_details.get("comment", rd.choice(all_data["comments"]))
            })

    filtered_results = [item for item in full_results if float(item.get("rating", 0)) >= min_rating]
    
    cloth = None
    if cloth_path:
        cloth_details = data.get(cloth_path, {})
        cloth = {
            **cloth_details, 
            "image": make_html_url(cloth_path), 
            "rating": cloth_details.get("rating", round(rd.uniform(2,5), 1)), 
            "name": f"{cloth_details.get('color', '')} {cloth_details.get('material', '')} {cloth_details.get('type', '')}"
        }
    elif prompt_text: 
         cloth = {"name": f"Suggestions for: '{prompt_text}'", "image": None, "link": "#"}

    return render_template("result.html", item=cloth, results=filtered_results)

if __name__ == '__main__':
    app.run(debug=True)