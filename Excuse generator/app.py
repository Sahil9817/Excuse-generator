from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import openai
import os
from dotenv import load_dotenv
import json
import random
from datetime import datetime, timedelta
import faker
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import requests
from gtts import gTTS
import pyttsx3
import threading
import time

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///excuse_generator.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Fake data generator
fake = faker.Faker()

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    excuses = db.relationship('Excuse', backref='user', lazy=True)
    favorites = db.relationship('FavoriteExcuse', backref='user', lazy=True)

class Excuse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    scenario = db.Column(db.String(100), nullable=False)
    urgency = db.Column(db.String(20), nullable=False)
    language = db.Column(db.String(10), default='en')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    effectiveness_score = db.Column(db.Float, default=0.0)
    proof_generated = db.Column(db.Boolean, default=False)

class FavoriteExcuse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    excuse_id = db.Column(db.Integer, db.ForeignKey('excuse.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class EmergencyContact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    relationship = db.Column(db.String(50), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# AI Excuse Generation
class ExcuseGenerator:
    def __init__(self):
        self.scenarios = {
            'work': ['meeting', 'deadline', 'sick', 'family_emergency', 'transportation', 'technical_issues'],
            'school': ['homework', 'exam', 'sick', 'family_emergency', 'transportation', 'technical_issues'],
            'social': ['previous_commitment', 'sick', 'family_emergency', 'transportation', 'weather'],
            'family': ['work_commitment', 'sick', 'previous_engagement', 'transportation', 'weather']
        }
        
        self.languages = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ja', 'ko', 'zh']
        
    def generate_excuse(self, scenario, urgency, language='en', custom_context=''):
        try:
            prompt = f"""
            Generate a believable and realistic excuse for a {scenario} scenario with {urgency} urgency.
            The excuse should be natural, convincing, and appropriate for the situation.
            
            Context: {custom_context}
            
            Requirements:
            - Sound natural and conversational
            - Include specific details that make it believable
            - Match the urgency level appropriately
            - Be culturally appropriate for {language} speakers
            
            Generate the excuse in {language} language.
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert at creating believable excuses that sound natural and convincing."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.8
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            return self.fallback_excuse(scenario, urgency, language)
    
    def fallback_excuse(self, scenario, urgency, language):
        excuses = {
            'work': {
                'high': 'I have a family emergency that requires my immediate attention.',
                'medium': 'I\'m experiencing some technical difficulties that are preventing me from working.',
                'low': 'I have a previous commitment that I need to attend to.'
            },
            'school': {
                'high': 'I\'m feeling very ill and need to rest.',
                'medium': 'I have a family matter that needs my attention.',
                'low': 'I have a conflicting appointment that I can\'t reschedule.'
            }
        }
        
        return excuses.get(scenario, {}).get(urgency, 'I have an unexpected situation that requires my attention.')
    
    def generate_proof(self, excuse_type, scenario):
        """Generate fake proof documents for excuses"""
        if excuse_type == 'medical':
            return self.generate_medical_certificate()
        elif excuse_type == 'transportation':
            return self.generate_transport_proof()
        elif excuse_type == 'technical':
            return self.generate_technical_issue_proof()
        else:
            return self.generate_generic_proof(scenario)
    
    def generate_medical_certificate(self):
        """Generate a fake medical certificate"""
        # Create a simple medical certificate image
        img = Image.new('RGB', (800, 600), color='white')
        draw = ImageDraw.Draw(img)
        
        # Add medical certificate content
        draw.text((50, 50), "MEDICAL CERTIFICATE", fill='black')
        draw.text((50, 100), f"Date: {datetime.now().strftime('%Y-%m-%d')}", fill='black')
        draw.text((50, 150), "Patient is unable to attend due to medical reasons.", fill='black')
        draw.text((50, 200), "Valid for 24 hours from issue date.", fill='black')
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    
    def generate_transport_proof(self):
        """Generate fake transportation proof"""
        img = Image.new('RGB', (800, 600), color='lightblue')
        draw = ImageDraw.Draw(img)
        
        draw.text((50, 50), "TRANSPORTATION ISSUE", fill='black')
        draw.text((50, 100), f"Date: {datetime.now().strftime('%Y-%m-%d')}", fill='black')
        draw.text((50, 150), "Service disruption affecting travel.", fill='black')
        draw.text((50, 200), "Expected delay: 2-3 hours", fill='black')
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    
    def generate_technical_issue_proof(self):
        """Generate fake technical issue proof"""
        img = Image.new('RGB', (800, 600), color='lightgray')
        draw = ImageDraw.Draw(img)
        
        draw.text((50, 50), "TECHNICAL ISSUE REPORT", fill='black')
        draw.text((50, 100), f"Date: {datetime.now().strftime('%Y-%m-%d')}", fill='black')
        draw.text((50, 150), "System maintenance in progress.", fill='black')
        draw.text((50, 200), "Estimated resolution time: 4-6 hours", fill='black')
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    
    def generate_generic_proof(self, scenario):
        """Generate generic proof document"""
        img = Image.new('RGB', (800, 600), color='lightgreen')
        draw = ImageDraw.Draw(img)
        
        draw.text((50, 50), f"{scenario.upper()} VERIFICATION", fill='black')
        draw.text((50, 100), f"Date: {datetime.now().strftime('%Y-%m-%d')}", fill='black')
        draw.text((50, 150), "This document verifies the stated excuse.", fill='black')
        draw.text((50, 200), "Valid for current date only.", fill='black')
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"

# Emergency System
class EmergencySystem:
    def __init__(self):
        self.emergency_templates = {
            'call': [
                "I'm in an emergency situation and need to leave immediately.",
                "There's a family emergency that requires my urgent attention.",
                "I have a medical emergency and need to go to the hospital."
            ],
            'text': [
                "Emergency - need to leave now. Will explain later.",
                "Family emergency. Can't make it. Sorry.",
                "Urgent situation. Will contact you when possible."
            ]
        }
    
    def trigger_emergency_call(self, contact_name, contact_phone):
        """Simulate emergency call"""
        message = random.choice(self.emergency_templates['call'])
        return {
            'type': 'call',
            'contact': contact_name,
            'phone': contact_phone,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
    
    def trigger_emergency_text(self, contact_name, contact_phone):
        """Simulate emergency text"""
        message = random.choice(self.emergency_templates['text'])
        return {
            'type': 'text',
            'contact': contact_name,
            'phone': contact_phone,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }

# Apology Generator
class ApologyGenerator:
    def __init__(self):
        self.apology_styles = ['professional', 'emotional', 'casual', 'formal']
    
    def generate_apology(self, style, context, language='en'):
        try:
            prompt = f"""
            Generate a {style} apology in {language} language for the following context:
            {context}
            
            The apology should be:
            - Sincere and heartfelt
            - Appropriate for the {style} style
            - Include acknowledgment of the inconvenience
            - Offer a solution or compensation if appropriate
            
            Make it sound natural and genuine.
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert at crafting sincere and appropriate apologies."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            return self.fallback_apology(style, context)
    
    def fallback_apology(self, style, context):
        apologies = {
            'professional': 'I sincerely apologize for any inconvenience this may have caused. I understand the impact this has had and I am committed to making it right.',
            'emotional': 'I'm really sorry about this. I feel terrible for letting you down and I want you to know how much I value our relationship.',
            'casual': 'Hey, I'm really sorry about that. I know it's not cool and I'll make sure it doesn't happen again.',
            'formal': 'Please accept my sincere apologies for the inconvenience. I take full responsibility and will ensure this situation is resolved appropriately.'
        }
        return apologies.get(style, 'I apologize for the inconvenience.')

# Initialize generators
excuse_generator = ExcuseGenerator()
emergency_system = EmergencySystem()
apology_generator = ApologyGenerator()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_excuses = Excuse.query.filter_by(user_id=current_user.id).order_by(Excuse.created_at.desc()).limit(5).all()
    favorite_excuses = FavoriteExcuse.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', excuses=user_excuses, favorites=favorite_excuses)

@app.route('/generate_excuse', methods=['POST'])
@login_required
def generate_excuse():
    data = request.get_json()
    scenario = data.get('scenario', 'work')
    urgency = data.get('urgency', 'medium')
    language = data.get('language', 'en')
    custom_context = data.get('custom_context', '')
    
    excuse = excuse_generator.generate_excuse(scenario, urgency, language, custom_context)
    
    # Save excuse to database
    new_excuse = Excuse(
        content=excuse,
        scenario=scenario,
        urgency=urgency,
        language=language,
        user_id=current_user.id
    )
    db.session.add(new_excuse)
    db.session.commit()
    
    return jsonify({
        'excuse': excuse,
        'id': new_excuse.id,
        'scenario': scenario,
        'urgency': urgency,
        'language': language
    })

@app.route('/generate_proof', methods=['POST'])
@login_required
def generate_proof():
    data = request.get_json()
    excuse_type = data.get('excuse_type', 'generic')
    scenario = data.get('scenario', 'work')
    
    proof_image = excuse_generator.generate_proof(excuse_type, scenario)
    
    return jsonify({
        'proof_image': proof_image,
        'type': excuse_type
    })

@app.route('/trigger_emergency', methods=['POST'])
@login_required
def trigger_emergency():
    data = request.get_json()
    emergency_type = data.get('type', 'call')
    contact_name = data.get('contact_name', 'Emergency Contact')
    contact_phone = data.get('contact_phone', '555-0123')
    
    if emergency_type == 'call':
        result = emergency_system.trigger_emergency_call(contact_name, contact_phone)
    else:
        result = emergency_system.trigger_emergency_text(contact_name, contact_phone)
    
    return jsonify(result)

@app.route('/generate_apology', methods=['POST'])
@login_required
def generate_apology():
    data = request.get_json()
    style = data.get('style', 'professional')
    context = data.get('context', 'General inconvenience')
    language = data.get('language', 'en')
    
    apology = apology_generator.generate_apology(style, context, language)
    
    return jsonify({
        'apology': apology,
        'style': style,
        'language': language
    })

@app.route('/add_to_favorites', methods=['POST'])
@login_required
def add_to_favorites():
    data = request.get_json()
    excuse_id = data.get('excuse_id')
    
    # Check if already in favorites
    existing = FavoriteExcuse.query.filter_by(
        user_id=current_user.id, 
        excuse_id=excuse_id
    ).first()
    
    if not existing:
        favorite = FavoriteExcuse(user_id=current_user.id, excuse_id=excuse_id)
        db.session.add(favorite)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Added to favorites'})
    
    return jsonify({'success': False, 'message': 'Already in favorites'})

@app.route('/get_excuse_history')
@login_required
def get_excuse_history():
    excuses = Excuse.query.filter_by(user_id=current_user.id).order_by(Excuse.created_at.desc()).all()
    history = []
    
    for excuse in excuses:
        history.append({
            'id': excuse.id,
            'content': excuse.content,
            'scenario': excuse.scenario,
            'urgency': excuse.urgency,
            'language': excuse.language,
            'created_at': excuse.created_at.strftime('%Y-%m-%d %H:%M'),
            'effectiveness_score': excuse.effectiveness_score
        })
    
    return jsonify(history)

@app.route('/rate_excuse', methods=['POST'])
@login_required
def rate_excuse():
    data = request.get_json()
    excuse_id = data.get('excuse_id')
    rating = data.get('rating', 0)
    
    excuse = Excuse.query.get(excuse_id)
    if excuse and excuse.user_id == current_user.id:
        excuse.effectiveness_score = rating
        db.session.commit()
        return jsonify({'success': True, 'message': 'Rating updated'})
    
    return jsonify({'success': False, 'message': 'Unable to update rating'})

@app.route('/text_to_speech', methods=['POST'])
@login_required
def text_to_speech():
    data = request.get_json()
    text = data.get('text', '')
    language = data.get('language', 'en')
    
    try:
        tts = gTTS(text=text, lang=language)
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)
        
        audio_data = base64.b64encode(buffer.getvalue()).decode()
        return jsonify({
            'success': True,
            'audio': f"data:audio/mp3;base64,{audio_data}"
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/speech_to_text', methods=['POST'])
@login_required
def speech_to_text():
    # This would integrate with a speech recognition service
    # For now, return a placeholder
    return jsonify({
        'success': True,
        'text': 'Speech to text functionality would be implemented here with a service like Google Speech-to-Text or Azure Speech Services.'
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
