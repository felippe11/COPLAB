import os
import uuid
from werkzeug.utils import secure_filename

# Function to check allowed file extensions
def allowed_file(filename):
    from app import app  # Local import to avoid circular imports
    allowed_extensions = app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

# Helper function to generate unique filename
def gerar_nome_arquivo(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    novo_nome = f"{uuid.uuid4().hex}.{ext}"
    return novo_nome