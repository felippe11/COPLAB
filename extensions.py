from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

# Create extensions but don't initialize them yet
db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()  # Add this line

# These will be initialized in app.py