import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'meca-tech-atia-v3-secret-2026')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///meca_tech.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Root & Upload configurations
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'svg', 'ico'}