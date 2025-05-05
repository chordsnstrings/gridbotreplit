import os
import logging

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from apscheduler.schedulers.background import BackgroundScheduler

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # needed for url_for to generate with https

# Configure the PostgreSQL database
database_url = os.environ.get("DATABASE_URL")
# Handle potential "postgres://" to "postgresql://" conversion needed for SQLAlchemy
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///grid_bot.db"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the database
db.init_app(app)

# Create scheduler for background tasks
scheduler = BackgroundScheduler(daemon=True)

# Import routes after app is created to avoid circular imports
with app.app_context():
    # Create database tables based on models
    from models import User, GridConfig, TradeHistory
    db.create_all()
    
    # Import and register routes
    from routes import register_routes
    register_routes(app)
    
    # Import and set up scheduled tasks
    from binance_client import update_active_grids
    
    # Run active grid bots every 10 seconds
    if not scheduler.running:
        scheduler.add_job(update_active_grids, 'interval', seconds=10)
        scheduler.start()
        logger.info("Scheduler started for grid bot updates")
