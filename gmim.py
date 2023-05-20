import secrets
import qrcode
import os
import base64
from io import BytesIO
from flask import Flask, render_template, make_response, request, redirect, url_for, session, send_file
from flask_session import Session
from uuid import uuid4
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__, static_url_path='/static')

app.config['SECRET_KEY'] = secrets.token_hex(16)  # Set a secret key for the app
app.config['SESSION_TYPE'] = 'filesystem'  # Set the session type to filesystem
Session(app)  # Initialize the session

users = {}
gmimcoin_pool = {}
gmimcoin_pool_qrcodes = {
    token: generate_qrcode_base64(url_for('attribute', token=token, _external=True), amount)
    for token, amount in gmimcoin_pool.items()
}

def generate_qrcode_base64(qr_data, amount):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']

        if username in users:
            session['username'] = username
            return redirect('/')
        else:
            return "Username not found. Please register first.", 400

    sorted_users = sorted(users.items(), key=lambda x: x[1]['balance'], reverse=True)
    return render_template('login_template.html', sorted_users=sorted_users, gmimcoin_pool=gmimcoin_pool, gmimcoin_pool_qrcodes=gmimcoin_pool_qrcodes)

@app.route('/', methods=['GET'])
def index():
    if 'username' not in session:
        return redirect(url_for('login'))

    user_role = users[session['username']]['role']
    can_generate = user_role in ['Representative','CEO']
    sorted_users = sorted(users.items(), key=lambda x: x[1]['balance'], reverse=True)

    return render_template('index_template.html', gmimcoin_pool=gmimcoin_pool, users=users, sorted_users=sorted_users, can_generate=can_generate, gmimcoin_pool_qrcodes=gmimcoin_pool_qrcodes)

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

@app.route('/generate', methods=['POST'])
def generate():
    if 'username' not in session:
        return redirect(url_for('login'))

    amount = int(request.form['amount'])
    token = str(uuid4())
    gmimcoin_pool[token] = amount
    gmimcoin_pool_qrcodes[token] = generate_qrcode_base64(url_for('attribute', token=token, _external=True), amount)

    return redirect('/')

@app.route('/logout', methods=['GET'])
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

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

@app.route('/edit-balance', methods=['POST'])
def edit_balance():
    if 'username' not in session or users[session['username']]['role'] != 'CEO':
        return "You are not authorized to edit balances.", 403

    target_username = request.form['username']
    new_balance = int(request.form['new_balance'])

    if target_username in users:
        users[target_username]['balance'] = new_balance
        return redirect('/')
    else:
        return "Username not found.", 400

def create_ceo_user():
    users['CEO'] = {'balance': 10000000, 'role': 'CEO'}


if __name__ == '__main__':
    create_ceo_user()
    app.run(debug=True)

# This line is added for compatibility with PythonAnywhere
create_ceo_user()
