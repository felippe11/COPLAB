from app import app, db
import models  # Import models to register them with SQLAlchemy

# Create a context for the app
with app.app_context():
    # Create all tables
    db.create_all()
    
    print("Database tables created successfully!")