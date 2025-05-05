import datetime
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    api_key = db.Column(db.String(256))
    api_secret = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    grid_configs = db.relationship('GridConfig', backref='user', lazy=True)
    trade_history = db.relationship('TradeHistory', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class GridConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)
    upper_bound = db.Column(db.Float, nullable=False)
    lower_bound = db.Column(db.Float, nullable=False)
    grid_size = db.Column(db.Integer, nullable=False)
    quantity_per_grid = db.Column(db.Float, nullable=False)
    leverage = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=False)
    # Trading direction: 'both', 'long', or 'short'
    bot_type = db.Column(db.String(10), default='both')
    # Wallet allocation percentage (1-100)
    wallet_allocation = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    long_positions = db.relationship('GridPosition', backref='grid_config', 
                                  primaryjoin="and_(GridPosition.grid_config_id==GridConfig.id, GridPosition.position_type=='long')",
                                  lazy=True)
    short_positions = db.relationship('GridPosition', backref='grid_config_short',
                                   primaryjoin="and_(GridPosition.grid_config_id==GridConfig.id, GridPosition.position_type=='short')",
                                   lazy=True)
    
    def __repr__(self):
        return f'<GridConfig {self.symbol} {self.lower_bound}-{self.upper_bound}>'

class GridPosition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    grid_config_id = db.Column(db.Integer, db.ForeignKey('grid_config.id'), nullable=False)
    position_type = db.Column(db.String(10), nullable=False)  # 'long' or 'short'
    price_level = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    order_id = db.Column(db.String(50))
    is_filled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f'<GridPosition {self.position_type} at {self.price_level}>'

class TradeHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    grid_config_id = db.Column(db.Integer, db.ForeignKey('grid_config.id'), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)
    order_id = db.Column(db.String(50))
    side = db.Column(db.String(10))  # 'BUY' or 'SELL'
    position_side = db.Column(db.String(10))  # 'LONG' or 'SHORT'
    price = db.Column(db.Float)
    quantity = db.Column(db.Float)
    realized_profit = db.Column(db.Float)
    commission = db.Column(db.Float)
    executed_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f'<TradeHistory {self.side} {self.symbol} at {self.price}>'
