# gmim.py

# Import necessary libraries
import secrets
import qrcode
import os
import base64
from io import BytesIO
from flask import (
    Flask, render_template, request, redirect, url_for, session, flash
)
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from uuid import uuid4
from PIL import Image, ImageDraw, ImageFont

# Initialize the Flask application
app = Flask(__name__, static_url_path='/static')

# Configuration
app.config['SECRET_KEY'] = secrets.token_hex(16)  # Secure secret key
app.config['SESSION_TYPE'] = 'filesystem'        # Session storage type
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gmim.db'  # Database URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False        # Disable track modifications
app.config['SESSION_COOKIE_SECURE'] = True                   # Ensure cookies are sent over HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True                 # Prevent JavaScript access to cookies
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'                # Protect against CSRF

# Initialize extensions
Session(app)
db = SQLAlchemy(app)

# Define the User model
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    balance = db.Column(db.Integer, default=0, nullable=False)
    role = db.Column(db.String(50), default='Loyal Member', nullable=False)
    qr_code = db.Column(db.Text, nullable=True)  # Store base64-encoded QR code

    def __repr__(self):
        return f"<User(username={self.username}, balance={self.balance}, role={self.role})>"

# Define the GMIMCoinToken model
class GMIMCoinToken(db.Model):
    __tablename__ = 'gmimcoin_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(36), unique=True, nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    qr_code = db.Column(db.Text, nullable=False)  # Store base64-encoded QR code

    def __repr__(self):
        return f"<GMIMCoinToken(token={self.token}, amount={self.amount})>"

# Create the database tables
with app.app_context():
    db.create_all()

# Helper function to generate a QR code and return it as a base64-encoded string
def generate_qrcode_base64(qr_data, text=None, is_user=False, username=None):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10 if is_user else 3,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="gold", back_color="black").convert('RGBA')

    # Add logo to the QR code
    logo_path = os.path.join(app.root_path, 'static', 'images', 'logo.jpeg')
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        qr_box = img.size[0]
        logo_size = int(qr_box * 0.2)
        logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
        logo_pos = ((qr_box - logo_size) // 2, (qr_box - logo_size) // 2)
        img.paste(logo, logo_pos, logo)
    
    # Add text below the QR code if provided
    if text:
        draw = ImageDraw.Draw(img)
        font_path = os.path.join(app.root_path, 'static', 'fonts', 'impact.ttf')
        if not os.path.exists(font_path):
            # Fallback to a default font if the specified font is not found
            font = ImageFont.load_default()
        else:
            font_size = int(img.size[0] * 0.05) if is_user else int(img.size[0] * 0.2)
            font = ImageFont.truetype(font_path, font_size)
        
        if is_user and username:
            # Add username at the bottom for user QR codes
            text_content = username
            text_width, text_height = draw.textsize(text_content, font=font)
            text_pos = ((img.size[0] - text_width) // 2, img.size[1] - text_height - 5)
            draw.text(text_pos, text_content, font=font, fill=(255, 0, 0, 255))
        else:
            # Add amount and "GMIMCOIN" for GMIMCoin tokens
            amount_text = f"{text} GMIMCOIN"
            text_size = draw.textbbox((0, 0), amount_text, font=font)
            text_img = Image.new('RGBA', (img.size[0], font.size * 2), color=(0, 0, 0, 255))
            draw_text = ImageDraw.Draw(text_img)
            text_size1 = draw_text.textsize(str(text), font=font)
            text_size2 = draw_text.textsize("GMIMCOIN", font=font)
            text_pos1 = ((img.size[0] - text_size1[0]) // 2, 0)
            text_pos2 = ((img.size[0] - text_size2[0]) // 2, font.size)
            draw_text.text(text_pos1, str(text), font=font, fill=(255, 0, 0, 255))
            draw_text.text(text_pos2, "GMIMCOIN", font=font, fill=(255, 0, 0, 255))
            combined_img = Image.new('RGBA', (img.size[0], img.size[1] + font.size * 2), color=(0, 0, 0, 255))
            combined_img.paste(img, (0, 0), img)
            combined_img.paste(text_img, (0, img.size[1]), text_img)
            img = combined_img

    # Save the QR code image as a base64-encoded string
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    img_base64 = base64.b64encode(img_io.getvalue()).decode('ascii')

    return img_base64

# Initialize the CEO user if not exists
def create_ceo_user():
    ceo = User.query.filter_by(username='CEO').first()
    if not ceo:
        ceo = User(
            username='CEO',
            balance=10000000,
            role='CEO',
            qr_code=''  # Will be generated upon login
        )
        db.session.add(ceo)
        db.session.commit()

# Call the function to ensure the CEO exists
with app.app_context():
    create_ceo_user()

# Define the route for registering new users
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        
        if not username:
            flash("Username cannot be empty.", "error")
            return redirect(url_for('register'))
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists. Please choose another.", "error")
            return redirect(url_for('register'))
        
        new_user = User(
            username=username,
            balance=0,
            role='Loyal Member'
        )
        db.session.add(new_user)
        db.session.commit()
        
        session['username'] = username
        flash("Registration successful! You are now logged in.", "success")
        return redirect(url_for('index'))
    
    return render_template('register_template.html')

# Define the route for logging in
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        
        if not username:
            flash("Username cannot be empty.", "error")
            return redirect(url_for('login'))
        
        user = User.query.filter_by(username=username).first()
        if user:
            session['username'] = user.username
            # Generate QR code upon login
            user.qr_code = generate_qrcode_base64(user.username, username=user.username, is_user=True)
            db.session.commit()
            flash("Login successful!", "success")
            return redirect(url_for('index'))
        else:
            flash("Username not found. Please register first.", "error")
            return redirect(url_for('login'))
    
    sorted_users = User.query.order_by(User.balance.desc()).all()
    gmimcoin_tokens = GMIMCoinToken.query.all()
    gmimcoin_pool_qrcodes = {token.token: token.qr_code for token in gmimcoin_tokens}
    return render_template(
        'login_template.html', 
        sorted_users=sorted_users, 
        gmimcoin_pool=gmimcoin_tokens, 
        gmimcoin_pool_qrcodes=gmimcoin_pool_qrcodes
    )

# Define the route for logging out
@app.route('/logout', methods=['GET'])
def logout():
    session.pop('username', None)
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

# Define the route for verifying the word
@app.route('/verify_word', methods=['GET', 'POST'])
def verify_word():
    if request.method == 'POST':
        entered_word = request.form['word'].strip()
        if entered_word.lower() == 'praisebob':
            session['entered_word'] = entered_word
            flash("Word verified successfully!", "success")
            return redirect(url_for('index'))
        else:
            flash("Incorrect word. Please try again.", "error")
            return redirect(url_for('verify_word'))
    
    return render_template('verify_word_template.html')

# Define the route for the homepage/dashboard
@app.route('/dmtx', methods=['GET'])
def index():
    if 'username' not in session:
        flash("Please log in to access the dashboard.", "error")
        return redirect(url_for('login'))
    
    if 'entered_word' not in session:
        flash("Please verify the required word to access the dashboard.", "error")
        return redirect(url_for('verify_word'))
    
    entered_word = session.get('entered_word', '').lower()
    if entered_word != 'praisebob':
        flash("Incorrect verification word. Please try again.", "error")
        return redirect(url_for('verify_word'))
    
    # Fetch the current user from the database
    user = User.query.filter_by(username=session['username']).first()
    if not user:
        flash("User not found. Please log in again.", "error")
        return redirect(url_for('login'))
    
    can_generate = user.role in ['Representative', 'CEO']
    sorted_users = User.query.order_by(User.balance.desc()).all()
    gmimcoin_tokens = GMIMCoinToken.query.all()
    gmimcoin_pool_qrcodes = {token.token: token.qr_code for token in gmimcoin_tokens}
    
    return render_template(
        'index_template.html',
        gmimcoin_pool=gmimcoin_tokens,
        users=sorted_users,
        sorted_users=sorted_users,
        can_generate=can_generate,
        gmimcoin_pool_qrcodes=gmimcoin_pool_qrcodes,
        user=user  # Pass the current user to the template
    )

# Define the route for attributing GMIMcoins to a user
@app.route('/attribute/<token>', methods=['GET', 'POST'])
def attribute(token):
    gmimcoin_token = GMIMCoinToken.query.filter_by(token=token).first()
    if not gmimcoin_token:
        flash("Invalid or expired GMIMcoin URL.", "error")
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'username' in session:
            user = User.query.filter_by(username=session['username']).first()
            if user:
                user.balance += gmimcoin_token.amount
                db.session.delete(gmimcoin_token)
                db.session.commit()
                flash(f"{gmimcoin_token.amount} GMIMCoin attributed to you successfully!", "success")
                return redirect(url_for('index'))
            else:
                flash("User not found. Please register first.", "error")
                return redirect(url_for('register'))
        else:
            username = request.form['username'].strip()
            user = User.query.filter_by(username=username).first()
            if user:
                session['username'] = user.username
                # Generate QR code upon login
                user.qr_code = generate_qrcode_base64(user.username, username=user.username, is_user=True)
                db.session.commit()
                return redirect(url_for('attribute', token=token))
            else:
                flash("Username not found. Please register first.", "error")
                return redirect(url_for('register'))
    
    logged_in = 'username' in session
    username = session['username'] if logged_in else None
    
    return render_template(
        'attribute_template.html',
        amount=gmimcoin_token.amount,
        token=gmimcoin_token.token,
        logged_in=logged_in,
        username=username
    )

# Define the route for generating GMIMcoins
@app.route('/generate', methods=['POST'])
def generate():
    if 'username' not in session:
        flash("You must be logged in to generate GMIMCoin.", "error")
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['username']).first()
    if not user or user.role not in ['Representative', 'CEO']:
        flash("You are not authorized to generate GMIMCoin.", "error")
        return redirect(url_for('index'))
    
    try:
        amount = int(request.form['amount'])
        if amount < 1:
            raise ValueError
    except (ValueError, KeyError):
        flash("Invalid amount. Please enter a positive integer.", "error")
        return redirect(url_for('index'))
    
    token_str = str(uuid4())
    qr_url = url_for('attribute', token=token_str, _external=True)
    qr_code = generate_qrcode_base64(qr_url, text=amount, is_user=False)
    
    new_token = GMIMCoinToken(
        token=token_str,
        amount=amount,
        qr_code=qr_code
    )
    db.session.add(new_token)
    db.session.commit()
    
    flash(f"{amount} GMIMCoin generated successfully!", "success")
    return redirect(url_for('index'))

# Define the route for assigning roles to users
@app.route('/assign-role', methods=['POST'])
def assign_role():
    if 'username' not in session:
        flash("You must be logged in to assign roles.", "error")
        return redirect(url_for('login'))
    
    current_user = User.query.filter_by(username=session['username']).first()
    if not current_user or current_user.role != 'CEO':
        flash("You are not authorized to assign roles.", "error")
        return redirect(url_for('index'))
    
    target_username = request.form['username'].strip()
    new_role = request.form['role'].strip()
    
    if not target_username or not new_role:
        flash("Username and role are required.", "error")
        return redirect(url_for('index'))
    
    if target_username == current_user.username:
        flash("You cannot change your own role.", "error")
        return redirect(url_for('index'))
    
    target_user = User.query.filter_by(username=target_username).first()
    if not target_user:
        flash("Username not found. Please register first.", "error")
        return redirect(url_for('index'))
    
    if new_role not in ['Representative', 'Loyal Member']:
        flash("Invalid role selected.", "error")
        return redirect(url_for('index'))
    
    target_user.role = new_role
    db.session.commit()
    
    flash(f"Role of {target_username} has been updated to {new_role}.", "success")
    return redirect(url_for('index'))

# Define the route for adding users (alternative to /register)
@app.route('/add-user', methods=['POST'])
def add_user():
    if 'username' not in session:
        flash("You must be logged in to add users.", "error")
        return redirect(url_for('login'))
    
    current_user = User.query.filter_by(username=session['username']).first()
    if not current_user or current_user.role != 'CEO':
        flash("You are not authorized to add users.", "error")
        return redirect(url_for('index'))
    
    username = request.form['username'].strip()
    
    if not username:
        flash("Username cannot be empty.", "error")
        return redirect(url_for('index'))
    
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash("Username already exists. Please choose another.", "error")
        return redirect(url_for('index'))
    
    new_user = User(
        username=username,
        balance=0,
        role='Loyal Member'
    )
    db.session.add(new_user)
    db.session.commit()
    
    flash(f"User {username} added successfully.", "success")
    return redirect(url_for('index'))

# Define the route for removing users
@app.route('/remove-user', methods=['POST'])
def remove_user():
    if 'username' not in session:
        flash("You must be logged in to remove users.", "error")
        return redirect(url_for('login'))
    
    current_user = User.query.filter_by(username=session['username']).first()
    if not current_user or current_user.role != 'CEO':
        flash("You are not authorized to remove users.", "error")
        return redirect(url_for('index'))
    
    username = request.form['username'].strip()
    
    if not username:
        flash("Username cannot be empty.", "error")
        return redirect(url_for('index'))
    
    if username == current_user.username:
        flash("You cannot remove yourself.", "error")
        return redirect(url_for('index'))
    
    user_to_remove = User.query.filter_by(username=username).first()
    if not user_to_remove:
        flash("Username not found.", "error")
        return redirect(url_for('index'))
    
    db.session.delete(user_to_remove)
    db.session.commit()
    
    flash(f"User {username} has been removed successfully.", "success")
    return redirect(url_for('index'))

# Define the route for editing a user's balance
@app.route('/edit-balance', methods=['POST'])
def edit_balance():
    if 'username' not in session:
        flash("You must be logged in to edit balances.", "error")
        return redirect(url_for('login'))
    
    current_user = User.query.filter_by(username=session['username']).first()
    if not current_user or current_user.role != 'CEO':
        flash("You are not authorized to edit balances.", "error")
        return redirect(url_for('index'))
    
    target_username = request.form['username'].strip()
    operation_type = request.form.get('operation_type', 'edit').strip()
    
    try:
        new_balance = int(request.form['new_balance'])
        if new_balance < 0:
            raise ValueError
    except (ValueError, KeyError):
        flash("Invalid balance. Please enter a non-negative integer.", "error")
        return redirect(url_for('index'))
    
    target_user = User.query.filter_by(username=target_username).first()
    if not target_user:
        flash("Username not found.", "error")
        return redirect(url_for('index'))
    
    if operation_type == 'add':
        target_user.balance += new_balance
        flash(f"Added {new_balance} GMIMCoin to {target_username}'s balance.", "success")
    elif operation_type == 'edit':
        target_user.balance = new_balance
        flash(f"Set {target_username}'s balance to {new_balance} GMIMCoin.", "success")
    else:
        flash("Invalid operation type.", "error")
        return redirect(url_for('index'))
    
    db.session.commit()
    return redirect(url_for('index'))

# Define the route for viewing all users (progress board)
@app.route('/', methods=['GET'])
def users_page():
    sorted_users = User.query.order_by(User.balance.desc()).all()
    gmimcoin_tokens = GMIMCoinToken.query.all()
    gmimcoin_pool_qrcodes = {token.token: token.qr_code for token in gmimcoin_tokens}
    
    return render_template(
        'progress_template.html',
        gmimcoin_pool=gmimcoin_tokens,
        users=sorted_users,
        sorted_users=sorted_users,
        gmimcoin_pool_qrcodes=gmimcoin_pool_qrcodes
    )

# Define the route for updating balances via HTMX
@app.route('/update_balances', methods=['GET'])
def update_balances():
    sorted_users = User.query.order_by(User.balance.desc()).all()
    return render_template('balances_template.html', sorted_users=sorted_users)

# Run the Flask application
if __name__ == '__main__':
    app.run(debug=True)
