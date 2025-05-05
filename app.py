import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pandas as pd
import joblib
import numpy as np
from datetime import datetime
import re
from flask import abort
import math

model_pipeline = joblib.load('model/model.pkl')

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('property.db')
    conn.row_factory = sqlite3.Row
    return conn

app.secret_key = 'your_secret_key'

# Configure upload folder
app.config['UPLOAD_FOLDER'] = 'static/images/'  # Adjust this path based on your project structure
app.config['ALLOWED_EXTENSIONS'] = {'jpg', 'jpeg', 'png', 'gif'}

# Initialize LoginManager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Sample users database (can be replaced with a database)
users = {
    "admin": generate_password_hash("admin1234"),
}

# User class
class User(UserMixin):
    def __init__(self, id):
        self.id = id

    @staticmethod
    def get(user_id):
        return User(user_id) if user_id in users else None

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username in users and check_password_hash(users[username], password):
            user = User(username)
            login_user(user)
            return redirect(url_for('admin'))

    return render_template('login.html')

# Admin panel route (only accessible for logged-in users)


@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    conn = sqlite3.connect('property.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Pagination and optional search
    per_page = 10
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '', type=str).strip().lower()

    # Count total matching rows
    if search_query:
        count_sql = "SELECT COUNT(*) FROM properties WHERE LOWER(area_name) LIKE ?"
        cursor.execute(count_sql, (f"%{search_query}%",))
    else:
        cursor.execute("SELECT COUNT(*) FROM properties")
    total = cursor.fetchone()[0]
    total_pages = math.ceil(total / per_page)

    # Fetch only the rows for the current page
    offset = (page - 1) * per_page
    if search_query:
        data_sql = """
          SELECT * FROM properties
          WHERE LOWER(area_name) LIKE ?
          ORDER BY id DESC
          LIMIT ? OFFSET ?
        """
        cursor.execute(data_sql, (f"%{search_query}%", per_page, offset))
    else:
        data_sql = "SELECT * FROM properties ORDER BY id DESC LIMIT ? OFFSET ?"
        cursor.execute(data_sql, (per_page, offset))

    properties = cursor.fetchall()
    conn.close()

    return render_template(
        'admin.html',
        properties=properties,
        current_page=page,
        total_pages=total_pages,
        search_query=search_query
    )


# Route to delete a property
@app.route('/delete_property/<int:id>', methods=['GET'])
def delete_property(id):
    conn = sqlite3.connect('property.db')
    conn.row_factory = sqlite3.Row  # Ensure rows are returned as dictionaries
    cursor = conn.cursor()
    cursor.execute('DELETE FROM properties WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

# Allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Load the model and columns
model = joblib.load('model/model.pkl')
columns = joblib.load('model/columns.pkl')

@app.route('/predict', methods=['GET','POST'])
def predict():
    prediction = None
    if request.method == 'POST':
        # Gather form inputs into a dict
        data = {
            'Area':            [int(request.form['area'])],
            'Area_Name':       [request.form['area_name']],
            'BHK':             [int(request.form['bhk'])],
            'Bathroom':        [int(request.form['bathroom'])],
            'Furnishing':      [request.form['furnishing']],
            'Parking':         [int(request.form['parking'])],
            'Status':          [request.form['status']],
            'Transaction':     [request.form['transaction']],
            'Type':            [request.form['type']],
            'Per_Sqft':        [ None ]  # if Per_Sqft was feature; else drop
        }
        # Build a DataFrame
        input_df = pd.DataFrame(data)

        # Make prediction
        prediction = model_pipeline.predict(input_df)[0]

    return render_template('predict.html', prediction=prediction)


@app.route('/')
def home():
    conn = sqlite3.connect('property.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM properties LIMIT 4')
    featured_properties = cursor.fetchall()

    region_clusters = {
        'north-delhi': ['rohini', 'patel nagar', 'karol bagh', 'najafgarh', 'narela', 'kirti nagar', 'moti nagar'],
        'south-delhi': ['greater kailash', 'okhla', 'janakpuri', 'kailash colony', 'new friends colony', 'maharani bagh', 'sarita vihar', 'vasant vihar', 'vasant kunj', 'mehrauli', 'geetanjali enclave', 'malviya nagar', 'saket', 'kalkaji', 'hauz khas', 'govindpuri'],
        'east-delhi': ['naveen shahdara', 'shahdara', 'yamuna vihar', 'laxmi nagar', 'shastri park', 'dilshad garden', 'vasundhara enclave'],
        'west-delhi': ['uttam nagar', 'paschim vihar', 'punjabi bagh', 'chittaranjan park'],
        'central-delhi': ['chandni chowk', 'new delhi', 'green park'],
    }

    region_properties = {}
    for region, areas in region_clusters.items():
        placeholders = ','.join(['?'] * len(areas))
        cursor.execute(f"SELECT * FROM properties WHERE LOWER(area_name) IN ({placeholders}) ORDER BY RANDOM() LIMIT 4", areas)
        region_properties[region] = cursor.fetchall()

    conn.close()

    return render_template('index.html', featured_properties=featured_properties, region_properties=region_properties, current_year=datetime.now().year)

@app.route('/property/<slug>')
def property_details(slug):
    # Convert slug back to original searchable form
    try:
        parts = slug.split('-in-')
        pre_in = parts[0].replace('-', ' ')  # e.g. "2 bhk semi furnished builder floor"
        area_name = parts[1].replace('-', ' ')  # e.g. "punjabi bagh"
    except (IndexError, AttributeError):
        abort(404)

    # Reconstruct type from title
    conn = get_db_connection()
    properties = conn.execute("SELECT * FROM properties WHERE lower(area_name) = ?", (area_name.lower(),)).fetchall()
    conn.close()

    matched_property = None
    for prop in properties:
        expected_type = prop['type'].replace('_', ' ')
        generated_slug = f"{prop['bhk']}-bhk-{prop['furnishing'].lower()}-{expected_type.lower().replace(' ', '-')}-in-{prop['area_name'].lower().replace(' ', '-')}"
        if generated_slug == slug:
            matched_property = dict(prop)
            break

    if not matched_property:
        abort(404)

    # Split images
    image_list = matched_property['image_filenames'].split(',') if matched_property['image_filenames'] else []
    return render_template('property_details.html', property=matched_property, image_list=image_list)

def render_region_page(area_list, region_slug):
    conn = sqlite3.connect('your_database_name.db')
    cursor = conn.cursor()

    placeholders = ', '.join('?' for _ in area_list)  # Generate the right number of ? for SQL query
    query = f"SELECT * FROM properties WHERE LOWER(area_name) IN ({placeholders})"
    cursor.execute(query, [area.lower() for area in area_list])

    properties = cursor.fetchall()
    conn.close()

    return render_template(f"{region_slug}.html", properties=properties)
@app.route('/north-delhi')
def north_delhi_properties():
    return render_region_page(
        ['rohini', 'patel nagar', 'karol bagh', 'najafgarh', 'narela', 'kirti nagar', 'moti nagar'],
        'north-delhi'
    )

@app.route('/south-delhi')
def south_delhi_properties():
    return render_region_page(
        ['greater kailash', 'okhla', 'janakpuri', 'kailash colony', 'new friends colony',
         'maharani bagh', 'sarita vihar', 'vasant vihar', 'vasant kunj', 'mehrauli',
         'geetanjali enclave', 'malviya nagar', 'saket', 'kalkaji', 'hauz khas', 'govindpuri'],
        'south-delhi'
    )

@app.route('/east-delhi')
def east_delhi_properties():
    return render_region_page(
        ['naveen shahdara', 'shahdara', 'yamuna vihar', 'laxmi nagar', 'shastri park',
         'dilshad garden', 'vasundhara enclave'],
        'east-delhi'
    )

@app.route('/west-delhi')
def west_delhi_properties():
    return render_region_page(
        ['uttam nagar', 'paschim vihar', 'punjabi bagh', 'chittaranjan park'],
        'west-delhi'
    )

@app.route('/central-delhi')
def central_delhi_properties():
    return render_region_page(
        ['chandni chowk', 'new delhi', 'green park'],
        'central-delhi'
    )

@app.route('/property', methods=['GET'])
def property_search():
    area_name = request.args.get('area_name', '').strip()
    bhk = request.args.get('bhk', '')
    prop_type = request.args.get('type', '').capitalize()

    # Map BHK values
    bhk_mapping = {
        "1 BHK": 1,
        "2 BHK": 2,
        "3 BHK": 3,
        "4 BHK": 4,
        "5+ BHK": 5
    }
    bhk_value = bhk_mapping.get(bhk)

    # Validate property type
    valid_types = ["Apartment", "Builder_Floor"]
    if prop_type not in valid_types:
        prop_type = None

    # Build SQL query
    query = "SELECT * FROM properties WHERE 1=1"
    params = []

    if area_name:
        query += " AND LOWER(Area_Name) LIKE ?"
        params.append(f"%{area_name.lower()}%")

    if bhk_value is not None:
        if bhk_value < 5:
            query += " AND BHK = ?"
            params.append(bhk_value)
        else:
            query += " AND BHK >= ?"
            params.append(5)

    if prop_type:
        query += " AND Type = ?"
        params.append(prop_type)

    # Execute query
    conn = sqlite3.connect('property.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    results = [dict(row) for row in rows]

    # Generate slug
    def generate_slug(prop):
        bhk = prop.get('BHK', '')
        furnishing = prop.get('Furnishing', '')
        prop_type = prop.get('Type', '').replace('_', ' ')
        area = prop.get('Area_Name', '')
        title = f"{bhk} BHK {furnishing} {prop_type} in {area}"
        return title.lower().replace(' ', '-').replace('_', '-')

    # Add slug to each property
    for prop in results:
        prop['slug'] = generate_slug(prop)

    conn.close()
    return render_template("search-results.html", properties=results)



@app.route('/about-us')
def about():
    return render_template('about-us.html')
@app.route('/contact-us') 
def contact_us():
    return render_template('contact-us.html')


region_mapping = {
    'north-delhi': ['rohini', 'patel nagar', 'karol bagh', 'najafgarh', 'narela', 'kirti nagar', 'moti nagar'],
    'south-delhi': ['greater kailash', 'okhla', 'janakpuri', 'kailash colony', 'new friends colony', 'maharani bagh', 'sarita vihar', 'vasant vihar', 'vasant kunj', 'mehrauli', 'geetanjali enclave', 'malviya nagar', 'saket', 'kalkaji', 'hauz khas', 'govindpuri'],
    'east-delhi': ['naveen shahdara', 'shahdara', 'yamuna vihar', 'laxmi nagar', 'shastri park', 'dilshad garden', 'vasundhara enclave'],
    'west-delhi': ['uttam nagar', 'paschim vihar', 'punjabi bagh', 'chittaranjan park'],
    'central-delhi': ['chandni chowk', 'new delhi', 'green park']
}
@app.route('/location/<region>', methods=['GET', 'POST'])
def region_page(region):
    region_areas = {
        'north-delhi': ['rohini', 'patel nagar', 'karol bagh', 'najafgarh', 'narela', 'kirti nagar', 'moti nagar'],
        'south-delhi': ['greater kailash', 'okhla', 'janakpuri', 'kailash colony', 'new friends colony', 'maharani bagh', 'sarita vihar', 'vasant vihar', 'vasant kunj', 'mehrauli', 'geetanjali enclave', 'malviya nagar', 'saket', 'kalkaji', 'hauz khas', 'govindpuri'],
        'east-delhi': ['naveen shahdara', 'shahdara', 'yamuna vihar', 'laxmi nagar', 'shastri park', 'dilshad garden', 'vasundhara enclave'],
        'west-delhi': ['uttam nagar', 'paschim vihar', 'punjabi bagh', 'chittaranjan park'],
        'central-delhi': ['chandni chowk', 'new delhi', 'green park']
    }

    if region not in region_areas:
        return "Region not found", 404

    areas = region_areas[region]

    # ✅ Capture filter parameters from the request
    min_price = request.args.get('min_price', type=int)
    max_price = request.args.get('max_price', type=int)
    min_area = request.args.get('min_area', type=int)
    max_area = request.args.get('max_area', type=int)
    bhk = request.args.get('bhk', type=int)
    furnishing = request.args.get('furnishing', type=str)
    status = request.args.get('status', type=str)
    property_type = request.args.get('type', type=str)

    # ✅ Establish database connection here
    conn = sqlite3.connect('property.db')
    cursor = conn.cursor()

    query = "SELECT * FROM properties WHERE LOWER(area_name) IN ({})".format(
        ",".join(["?"] * len(areas))
    )
    params = [area.lower() for area in areas]

    # ✅ Apply additional filters based on user input
    if min_price:
        query += " AND price >= ?"
        params.append(min_price)
    if max_price:
        query += " AND price <= ?"
        params.append(max_price)
    if min_area:
        query += " AND area >= ?"
        params.append(min_area)
    if max_area:
        query += " AND area <= ?"
        params.append(max_area)
    if bhk:
        query += " AND bhk = ?"
        params.append(bhk)
    if furnishing:
        query += " AND furnishing = ?"
        params.append(furnishing)
    if status:
        query += " AND status = ?"
        params.append(status)
    if property_type:
        query += " AND type = ?"
        params.append(property_type)

    cursor.execute(query, params)
    properties = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    conn.close()

    return render_template('region_listings.html', properties=properties, region=region)

@app.template_filter('format_price')
def format_price(value):
    try:
        value = int(value)
        return f"₹ {value:,.0f}"  # Formatting the price with commas and a ₹ symbol
    except (ValueError, TypeError):
        return value

if __name__ == '__main__':
    app.run(debug=True)
