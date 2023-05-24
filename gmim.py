# Import necessary libraries
import secrets
import qrcode
import os
import base64
from io import BytesIO
from flask import Flask, render_template, make_response, request, redirect, url_for, session, send_file
from flask_session import Session
from uuid import uuid4
from PIL import Image, ImageDraw, ImageFont

# Create the Flask web server application
app = Flask(__name__, static_url_path='/static')

# Configure the Flask web server application with secret key and session type
app.config['SECRET_KEY'] = secrets.token_hex(16)  # Generates a random 16 byte hex string to use as the secret key
app.config['SESSION_TYPE'] = 'filesystem'  # Specifies that sessions should be stored in the file system
Session(app)  # Initialize the Flask session

users = {} # Dictionary of users and their balances

# Initialize the GMIMcoin pool
gmimcoin_pool = {}
gmimcoin_pool_qrcodes = {
    token: generate_qrcode_base64(url_for('attribute', token=token, _external=True), amount)
    for token, amount in gmimcoin_pool.items()
}

# Define a function to generate a QR code for a user and return it as a base64-encoded string
def generate_user_qrcode_base64(qr_data, username):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,  # Increase the box_size for a larger QR code
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="gold", back_color="black").convert('RGBA')

    logo_path = os.path.join(os.path.dirname(__file__), 'static/images/logo.jpeg')
    logo = Image.open(logo_path).convert("RGBA")

    qr_box = img.size[0]
    logo_size = int(qr_box * 0.3)
    logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
    logo_pos = ((qr_box - logo_size) // 2, (qr_box - logo_size) // 2)
    img.paste(logo, logo_pos, logo)

    # Create a new image with the same width as the QR code image and a height for the text
    draw = ImageDraw.Draw(img)
    font_path = os.path.join(os.path.dirname(__file__), 'static/fonts/impact.ttf')
    font_size = int(qr_box * 0.05)  # Adjust the font size
    font = ImageFont.truetype(font_path, font_size)
    
    text = username
    text_width, text_height = draw.textsize(text, font=font)
    text_pos = ((qr_box - text_width) // 2, qr_box - text_height - 5)  # Position the text at the bottom of the QR code

    draw.text(text_pos, text, font=font, fill=(255, 0, 0, 255))  # Draw the text

    # Save the QR code image as a base64-encoded string
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    img_base64 = base64.b64encode(img_io.getvalue()).decode('ascii')

    return img_base64


# Define a function to generate a QR code for a GMIMcoin amount and return it as a base64-encoded string
def generate_qrcode_base64(qr_data, amount):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=3,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="gold", back_color="black").convert('RGBA')

    logo_path = os.path.join(os.path.dirname(__file__), 'static/images/logo.jpeg')
    logo = Image.open(logo_path).convert("RGBA")


    qr_box = img.size[0]
    logo_size = int(qr_box * 0.3)
    logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
    logo_pos = ((qr_box - logo_size) // 2, (qr_box - logo_size) // 2)
    img.paste(logo, logo_pos, logo)

    # Create a new image with the same width as the QR code image and a height for the text
    draw = ImageDraw.Draw(img)
    font_path = os.path.join(os.path.dirname(__file__), 'static/fonts/impact.ttf')
    font_size = int(qr_box * 0.2)
    font = ImageFont.truetype(font_path, font_size)
    text = f"{amount} GMIMCOIN"
    text_size = draw.textbbox((0, 0), text, font=font)
    text_img = Image.new('RGBA', (qr_box, font_size * 2), color=(0, 0, 0, 255))

    # Add amount text to the new image
    draw = ImageDraw.Draw(text_img)
    font_size = int(qr_box * 0.1)  # Adjust the font size
    font = ImageFont.truetype(font_path, font_size)

    text1 = f"{amount}"
    text2 = "GMIMCOIN"

    text_size1 = draw.textsize(text1, font=font)
    text_size2 = draw.textsize(text2, font=font)

    text_pos1 = ((qr_box - text_size1[0]) // 2, 0)
    text_pos2 = ((qr_box - text_size2[0]) // 2, font_size)

    draw.text(text_pos1, text1, font=font, fill=(255, 0, 0, 255))
    draw.text(text_pos2, text2, font=font, fill=(255, 0, 0, 255))

    # Create a new image with the same width as the QR code image and a height equal to the sum of the QR code and text image heights
    combined_img = Image.new('RGBA', (qr_box, qr_box + font_size * 3), color=(0, 0, 0, 255))

    # Paste the QR code image and text image
    combined_img.paste(img, (0, 0), img)
    combined_img.paste(text_img, (0, qr_box), text_img)

    # Save the combined image as a base64-encoded string
    img_io = BytesIO()
    combined_img.save(img_io, 'PNG')
    img_io.seek(0)
    img_base64 = base64.b64encode(img_io.getvalue()).decode('ascii')

    return img_base64

# Define the route for registering new users
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']

        if username not in users:
            users[username] = {'balance': 0, 'role': 'Loyal Supporter'}
            session['username'] = username
            return redirect('/')
        else:
            return "Username already exists. Please choose another.", 400

    return render_template('register_template.html')

# Define the route for assigning roles to users
@app.route('/assign-role', methods=['POST'])
def assign_role():
    if 'username' not in session or users[session['username']]['role'] != 'CEO':
        return "You are not authorized to assign roles.", 403

    target_username = request.form['username']
    new_role = request.form['role']

    # Prevent users from modifying their own roles, including the CEO
    if target_username == session['username']:
        return "You cannot change your own role.", 400

    if target_username in users:
        users[target_username]['role'] = new_role
        return redirect('/')
    else:
        return "Username not found. Please register first.", 400


    return render_template('assign_role_template.html')

# Define the route for logging in
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']

        if username in users:
            session['username'] = username
            qr_data = username
            users[username]['qr_code'] = generate_user_qrcode_base64(qr_data, username) 
            return redirect('/')
        else:
            return "Username not found. Please register first.", 400

    sorted_users = sorted(users.items(), key=lambda x: x[1]['balance'], reverse=True)
    return render_template('login_template.html', sorted_users=sorted_users, gmimcoin_pool=gmimcoin_pool, gmimcoin_pool_qrcodes=gmimcoin_pool_qrcodes)

# Define the route for the homepage
@app.route('/', methods=['GET'])
def index():
    if 'username' not in session:
        return redirect(url_for('login'))

    user_role = users[session['username']]['role']
    can_generate = user_role in ['Representative','CEO']
    sorted_users = sorted(users.items(), key=lambda x: x[1]['balance'], reverse=True)

    return render_template('index_template.html', gmimcoin_pool=gmimcoin_pool, users=users, sorted_users=sorted_users, can_generate=can_generate, gmimcoin_pool_qrcodes=gmimcoin_pool_qrcodes)

# Define the route for attributing GMIMcoins to a user
@app.route('/attribute/<token>', methods=['GET', 'POST'])
def attribute(token):
    if token not in gmimcoin_pool:
        return "Invalid or expired GMIMcoin URL.", 400

    amount = gmimcoin_pool[token]

    if request.method == 'POST':
        username = request.form['username']

        if 'username' in session:
            users[username]['balance'] += amount
            del gmimcoin_pool[token]
            return redirect('/')
        else:
            if username in users:
                session['username'] = username
                return redirect(url_for('attribute', token=token))
            else:
                return "Username not found. Please register first.", 400

    logged_in = 'username' in session
    username = session['username'] if logged_in else None

    return render_template('attribute_template.html', amount=amount, token=token, logged_in=logged_in, username=username)

# Define the route for generating GMIMcoins
@app.route('/generate', methods=['POST'])
def generate():
    if 'username' not in session:
        return redirect(url_for('login'))

    amount = int(request.form['amount'])
    token = str(uuid4())
    gmimcoin_pool[token] = amount
    gmimcoin_pool_qrcodes[token] = generate_qrcode_base64(url_for('attribute', token=token, _external=True), amount)

    return redirect('/')

# Define the route for logging out
@app.route('/logout', methods=['GET'])
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

# Define the route for updating balances
@app.route('/update_balances', methods=['GET'])
def update_balances():
    sorted_users = sorted(users.items(), key=lambda x: x[1]['balance'], reverse=True)
    return render_template('balances_template.html', sorted_users=sorted_users)


# Define the route for adding users
@app.route('/add-user', methods=['POST'])
def add_user():
    if 'username' not in session or users[session['username']]['role'] != 'CEO':
        return "You are not authorized to add users.", 403

    username = request.form['username']

    if username not in users:
        users[username] = {'balance': 0, 'role': 'Loyal Supporter'}
        return redirect('/')
    else:
        return "Username already exists. Please choose another.", 400

# Define the route for removing users
@app.route('/remove-user', methods=['POST'])
def remove_user():
    if 'username' not in session or users[session['username']]['role'] != 'CEO':
        return "You are not authorized to remove users.", 403

    username = request.form['username']

    if username in users:
        if username == session['username']:
            return "You cannot remove yourself.", 400
        del users[username]
        return redirect('/')
    else:
        return "Username not found.", 400

# Define the route for editing a user's balance
@app.route('/edit-balance', methods=['POST'])
def edit_balance():
    if 'username' not in session or users[session['username']]['role'] != 'CEO':
        return "You are not authorized to edit balances.", 403

    target_username = request.form['username']
    new_balance = int(request.form['new_balance'])
    operation_type = request.form.get('operation_type', 'edit')

    if target_username in users:
        if operation_type == 'add':
            # Add new balance to current balance
            current_balance = users[target_username].get('balance', 0)
            users[target_username]['balance'] = current_balance + new_balance
        elif operation_type == 'edit':
            # Set balance to new balance
            users[target_username]['balance'] = new_balance
        return redirect('/')
    else:
        return "Username not found.", 400

# Define the route for viewing all users
@app.route('/progress', methods=['GET'])
def users_page():
    sorted_users = sorted(users.items(), key=lambda x: x[1]['balance'], reverse=True)

    return render_template('progress_template.html', gmimcoin_pool=gmimcoin_pool, users=users, sorted_users=sorted_users,  gmimcoin_pool_qrcodes=gmimcoin_pool_qrcodes)


# Define a function to create the CEO user
def create_ceo_user():
    users['CEO'] = {'balance': 10000000, 'role': 'CEO'}
    
# Run the Flask web server application
if __name__ == '__main__':
    create_ceo_user()
    app.run(debug=True)

# This line is added for compatibility with PythonAnywhere
create_ceo_user()
