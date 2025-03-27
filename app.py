import os
from flask import Flask

# Import extensions to initialize them
from extensions import db, migrate, csrf 

def create_app():
    # Create the Flask app
    app = Flask(__name__)
    
    # App configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'chave-secreta-temporaria'
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'postgresql://coplab:123456@localhost/coplab_database'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit
    app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    
    # Create uploads folder
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize extensions with the app
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    
    # Import and register blueprints/routes
    from routes import register_routes
    register_routes(app)
    
    return app

# Create the app
app = create_app()

# Run the app
if __name__ == '__main__':
    # Cria as tabelas se elas não existirem
    with app.app_context():
        db.create_all()
    app.run(debug=True)