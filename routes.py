import os
import json
import logging
import requests
from flask import render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from binance.exceptions import BinanceAPIException
from app import db, app
from models import User, GridConfig, GridPosition, TradeHistory
from binance_client import BinanceClient
from grid_strategy import (create_grid_levels, calculate_grid_profit, calculate_grid_performance,
                          validate_grid_parameters, create_grid_config, update_grid_config, delete_grid_config)

# Configure logging
logger = logging.getLogger(__name__)

# Initialize LoginManager
login_manager = LoginManager()

def register_routes(app):
    """Register all routes with the app"""
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Home route
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return render_template('index.html')
    
    # Authentication routes
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            user = User.query.filter_by(username=username).first()
            
            if user and user.check_password(password):
                login_user(user)
                flash('Logged in successfully', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'danger')
                
        return render_template('index.html')
        
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            
            # Validate input
            if not username or not email or not password:
                flash('All fields are required', 'danger')
                return redirect(url_for('index'))
                
            if password != confirm_password:
                flash('Passwords do not match', 'danger')
                return redirect(url_for('index'))
                
            # Check if user exists
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('Username already exists', 'danger')
                return redirect(url_for('index'))
                
            existing_email = User.query.filter_by(email=email).first()
            if existing_email:
                flash('Email already registered', 'danger')
                return redirect(url_for('index'))
                
            # Create new user
            new_user = User(username=username, email=email)
            new_user.set_password(password)
            
            try:
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
                flash('Account created successfully', 'success')
                return redirect(url_for('dashboard'))
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error creating user: {e}")
                flash('An error occurred. Please try again.', 'danger')
                
        return render_template('index.html')
        
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Logged out successfully', 'success')
        return redirect(url_for('index'))
        
    # Dashboard route
    @app.route('/dashboard')
    @login_required
    def dashboard():
        # Get user's grid configs
        grid_configs = GridConfig.query.filter_by(user_id=current_user.id).all()
        
        # Calculate performance for each grid
        for grid in grid_configs:
            grid.performance = calculate_grid_performance(grid)
            grid.potential = calculate_grid_profit(grid)
            
        return render_template('dashboard.html', grid_configs=grid_configs)
        
    # Helper function to get server IP
    def get_server_ip():
        try:
            # Use an external service to get our public IP
            response = requests.get('https://api.ipify.org?format=json', timeout=5)
            if response.status_code == 200:
                return response.json().get('ip')
        except Exception as e:
            logger.error(f"Error getting server IP: {e}")
        
        # Fallback - try another service
        try:
            response = requests.get('https://ifconfig.me/ip', timeout=5)
            if response.status_code == 200:
                return response.text.strip()
        except Exception as e:
            logger.error(f"Error getting server IP (fallback): {e}")
        
        return None

    # API key settings route
    @app.route('/settings', methods=['GET', 'POST'])
    @login_required
    def settings():
        # Get server IP for API whitelisting
        server_ip = get_server_ip()
        
        if request.method == 'POST':
            api_key = request.form.get('api_key')
            api_secret = request.form.get('api_secret')
            skip_verification = request.form.get('skip_verification') == 'on'
            
            if api_key and api_secret:
                if skip_verification:
                    # Skip verification and save keys directly
                    current_user.api_key = api_key
                    current_user.api_secret = api_secret
                    db.session.commit()
                    flash('API keys saved without verification', 'success')
                else:
                    # Test API connection
                    try:
                        client = BinanceClient(api_key, api_secret)
                        if client.check_connection():
                            # Save API keys
                            current_user.api_key = api_key
                            current_user.api_secret = api_secret
                            db.session.commit()
                            flash('API keys saved and verified successfully', 'success')
                        else:
                            flash('Invalid API keys or connection failed', 'danger')
                    except Exception as e:
                        logger.error(f"API verification error: {e}")
                        flash(f'API verification failed: {str(e)}. You can try saving with "Skip Verification" option.', 'danger')
            else:
                flash('Both API key and secret are required', 'danger')
                
        return render_template('settings.html', server_ip=server_ip)
        
    # Grid configuration routes
    @app.route('/grid/create', methods=['GET', 'POST'])
    @login_required
    def create_grid():
        if request.method == 'POST':
            symbol = request.form.get('symbol')
            lower_bound = request.form.get('lower_bound')
            upper_bound = request.form.get('upper_bound')
            grid_size = request.form.get('grid_size')
            quantity_per_grid = request.form.get('quantity_per_grid')
            leverage = request.form.get('leverage')
            bot_type = request.form.get('bot_type', 'both')  # Default to both if not specified
            wallet_allocation = request.form.get('wallet_allocation', 10)  # Default to 10% if not specified
            
            # Validate inputs
            errors = validate_grid_parameters(
                symbol, lower_bound, upper_bound, grid_size, 
                quantity_per_grid, leverage, bot_type, wallet_allocation
            )
            
            if errors:
                for error in errors:
                    flash(error, 'danger')
                return redirect(url_for('dashboard'))
                
            try:
                # Create grid config
                grid_config = create_grid_config(
                    current_user.id,
                    symbol,
                    lower_bound,
                    upper_bound,
                    grid_size,
                    quantity_per_grid,
                    leverage,
                    bot_type,
                    wallet_allocation
                )
                
                flash('Grid configuration created successfully', 'success')
                return redirect(url_for('dashboard'))
            except BinanceAPIException as e:
                logger.error(f"Binance API error creating grid: {e}")
                if "restricted location" in str(e).lower() or e.status_code == 451:
                    flash(
                        'Binance API access is restricted in your location. '
                        'Please check the geographic restrictions section in Settings for possible solutions.', 
                        'danger'
                    )
                else:
                    flash(f'Binance API error: {str(e)}', 'danger')
                return redirect(url_for('dashboard'))
            except Exception as e:
                logger.error(f"Error creating grid: {e}")
                flash(f'An error occurred: {str(e)}', 'danger')
                
        return redirect(url_for('dashboard'))
        
    @app.route('/grid/<int:grid_id>/toggle', methods=['POST'])
    @login_required
    def toggle_grid(grid_id):
        try:
            grid_config = GridConfig.query.get(grid_id)
            
            if not grid_config or grid_config.user_id != current_user.id:
                flash('Grid not found', 'danger')
                return redirect(url_for('dashboard'))
                
            # Check if user has API keys
            if not current_user.api_key or not current_user.api_secret:
                flash('Please set up your API keys first', 'danger')
                return redirect(url_for('settings'))
                
            # Toggle grid active status
            is_active = not grid_config.is_active
            
            # If activating, set up grid trading
            if is_active:
                try:
                    client = BinanceClient(current_user.api_key, current_user.api_secret)
                    if client.setup_grid_trading(grid_config):
                        update_grid_config(grid_id, is_active=is_active)
                        flash('Grid bot started successfully', 'success')
                    else:
                        flash('Failed to start grid bot', 'danger')
                except BinanceAPIException as e:
                    logger.error(f"Binance API error setting up grid trading: {e}")
                    if "restricted location" in str(e).lower() or e.status_code == 451:
                        flash(
                            'Binance API access is restricted in your location. '
                            'Please check the geographic restrictions section in Settings for possible solutions.',
                            'danger'
                        )
                    else:
                        flash(f'Binance API error: {str(e)}', 'danger')
                except Exception as e:
                    logger.error(f"Error setting up grid trading: {e}")
                    flash(f'Failed to start grid bot: {str(e)}', 'danger')
            else:
                # Deactivate grid
                update_grid_config(grid_id, is_active=is_active)
                flash('Grid bot stopped successfully', 'success')
                
            return redirect(url_for('dashboard'))
        except Exception as e:
            logger.error(f"Error toggling grid: {e}")
            flash('An error occurred. Please try again.', 'danger')
            return redirect(url_for('dashboard'))
            
    @app.route('/grid/<int:grid_id>/delete', methods=['POST'])
    @login_required
    def delete_grid(grid_id):
        try:
            grid_config = GridConfig.query.get(grid_id)
            
            if not grid_config or grid_config.user_id != current_user.id:
                flash('Grid not found', 'danger')
                return redirect(url_for('dashboard'))
                
            # Can't delete an active grid
            if grid_config.is_active:
                flash('Please stop the grid bot before deleting', 'danger')
                return redirect(url_for('dashboard'))
                
            # Delete grid
            delete_grid_config(grid_id)
            flash('Grid configuration deleted successfully', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            logger.error(f"Error deleting grid: {e}")
            flash('An error occurred. Please try again.', 'danger')
            return redirect(url_for('dashboard'))
            
    # API routes for AJAX requests
    @app.route('/api/grid/<int:grid_id>/positions')
    @login_required
    def get_grid_positions(grid_id):
        try:
            grid_config = GridConfig.query.get(grid_id)
            
            if not grid_config or grid_config.user_id != current_user.id:
                return jsonify({'error': 'Grid not found'}), 404
                
            # Get grid positions
            long_positions = [
                {
                    'id': pos.id,
                    'price_level': pos.price_level,
                    'quantity': pos.quantity,
                    'is_filled': pos.is_filled
                }
                for pos in grid_config.long_positions
            ]
            
            short_positions = [
                {
                    'id': pos.id,
                    'price_level': pos.price_level,
                    'quantity': pos.quantity,
                    'is_filled': pos.is_filled
                }
                for pos in grid_config.short_positions
            ]
            
            # Get grid levels
            grid_levels = create_grid_levels(grid_config.lower_bound, grid_config.upper_bound, grid_config.grid_size)
            
            # Get current price if API keys are set
            current_price = None
            if current_user.api_key and current_user.api_secret:
                try:
                    client = BinanceClient(current_user.api_key, current_user.api_secret)
                    current_price = client.get_symbol_price(grid_config.symbol)
                except BinanceAPIException as e:
                    logger.error(f"Error getting current price: {e}")
                    if "restricted location" in str(e).lower() or getattr(e, 'status_code', 0) == 451:
                        # We'll still return other data, but indicate restriction
                        current_price = None
                except Exception as e:
                    logger.error(f"Error getting current price: {e}")
            
            return jsonify({
                'grid_levels': grid_levels.tolist(),
                'long_positions': long_positions,
                'short_positions': short_positions,
                'current_price': current_price,
                'bot_type': grid_config.bot_type,
                'wallet_allocation': grid_config.wallet_allocation
            })
        except Exception as e:
            logger.error(f"Error getting grid positions: {e}")
            return jsonify({'error': str(e)}), 500
            
    @app.route('/api/grid/<int:grid_id>/trades')
    @login_required
    def get_grid_trades(grid_id):
        try:
            grid_config = GridConfig.query.get(grid_id)
            
            if not grid_config or grid_config.user_id != current_user.id:
                return jsonify({'error': 'Grid not found'}), 404
                
            # Get trades for this grid
            trades = TradeHistory.query.filter_by(grid_config_id=grid_id).order_by(TradeHistory.executed_at.desc()).limit(50).all()
            
            trade_data = [
                {
                    'id': trade.id,
                    'side': trade.side,
                    'position_side': trade.position_side,
                    'price': trade.price,
                    'quantity': trade.quantity,
                    'realized_profit': trade.realized_profit,
                    'executed_at': trade.executed_at.strftime('%Y-%m-%d %H:%M:%S')
                }
                for trade in trades
            ]
            
            return jsonify({'trades': trade_data})
        except Exception as e:
            logger.error(f"Error getting grid trades: {e}")
            return jsonify({'error': str(e)}), 500
            
    @app.route('/api/symbols')
    @login_required
    def get_symbols():
        try:
            if not current_user.api_key or not current_user.api_secret:
                return jsonify({'error': 'API keys not set'}), 400
            
            # Common trading pairs if we can't get them from Binance
            default_symbols = [
                'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'DOGEUSDT',
                'XRPUSDT', 'DOTUSDT', 'UNIUSDT', 'SOLUSDT', 'LTCUSDT'
            ]
                
            try:
                client = BinanceClient(current_user.api_key, current_user.api_secret)
                exchange_info = client.get_exchange_info()
                
                # Filter for USDT futures symbols
                symbols = [s['symbol'] for s in exchange_info['symbols'] if s['symbol'].endswith('USDT') and s['status'] == 'TRADING']
                return jsonify({'symbols': symbols})
            except BinanceAPIException as e:
                logger.warning(f"Binance API error fetching symbols: {e}")
                if "restricted location" in str(e).lower() or getattr(e, 'status_code', 0) == 451:
                    return jsonify({
                        'error': 'Geographic restriction error',
                        'message': 'Binance API access is restricted in your location. Please check the geographic restrictions section in Settings for possible solutions.',
                        'symbols': default_symbols,
                        'restricted': True
                    }), 451
                else:
                    return jsonify({
                        'error': 'Binance API error',
                        'message': str(e),
                        'symbols': default_symbols,
                        'restricted': True
                    }), 400
            except Exception as e:
                logger.warning(f"Could not fetch symbols from Binance API: {e}")
                logger.info("Using default symbol list")
                return jsonify({
                    'error': 'Connection error',
                    'message': 'Could not connect to Binance API. Please check your API keys and try again.',
                    'symbols': default_symbols,
                    'restricted': True
                }), 500
        except Exception as e:
            logger.error(f"Error getting symbols: {e}")
            return jsonify({'error': str(e)}), 500
            
    @app.route('/api/symbol/<symbol>/price')
    @login_required
    def get_symbol_price(symbol):
        """Get the current price for a symbol"""
        try:
            # Default prices if we can't connect to Binance
            default_prices = {
                'BTCUSDT': 65000.0, 'ETHUSDT': 3500.0, 'BNBUSDT': 500.0,
                'ADAUSDT': 0.5, 'DOGEUSDT': 0.15, 'XRPUSDT': 0.6,
                'DOTUSDT': 12.0, 'UNIUSDT': 10.0, 'SOLUSDT': 150.0, 'LTCUSDT': 80.0
            }
            
            if not current_user.api_key or not current_user.api_secret:
                return jsonify({'error': 'API keys not set'}), 400
                
            try:
                client = BinanceClient(current_user.api_key, current_user.api_secret)
                price = client.get_symbol_price(symbol)
                return jsonify({'price': price})
            except BinanceAPIException as e:
                logger.warning(f"Binance API error fetching price: {e}")
                if "restricted location" in str(e).lower() or getattr(e, 'status_code', 0) == 451:
                    return jsonify({
                        'error': 'Geographic restriction error',
                        'message': 'Binance API access is restricted in your location. Please check the geographic restrictions section in Settings for possible solutions.'
                    }), 451
                else:
                    return jsonify({
                        'error': 'Binance API error',
                        'message': str(e)
                    }), 400
            except Exception as e:
                logger.warning(f"Could not fetch price from Binance API: {e}")
                return jsonify({
                    'error': 'Connection error',
                    'message': 'Could not connect to Binance API. Please check your API keys and try again.'
                }), 500
        except Exception as e:
            logger.error(f"Error getting symbol price: {e}")
            return jsonify({'error': str(e)}), 500
            
    @app.route('/api/account/balance')
    @login_required
    def get_account_balance():
        """Get the user's account balance"""
        try:
            if not current_user.api_key or not current_user.api_secret:
                return jsonify({'error': 'API keys not set'}), 400
                
            try:
                client = BinanceClient(current_user.api_key, current_user.api_secret)
                account_info = client.get_account_info()
                
                # Get USDT balance
                usdt_balance = 0
                for asset in account_info.get('assets', []):
                    if asset.get('asset') == 'USDT':
                        usdt_balance = float(asset.get('walletBalance', 0))
                        break
                        
                return jsonify({
                    'usdt_balance': usdt_balance,
                    'account_info': account_info
                })
            except BinanceAPIException as e:
                logger.warning(f"Binance API error fetching account balance: {e}")
                if "restricted location" in str(e).lower() or getattr(e, 'status_code', 0) == 451:
                    return jsonify({
                        'error': 'Geographic restriction error',
                        'message': 'Binance API access is restricted in your location. Please check the geographic restrictions section in Settings for possible solutions.'
                    }), 451
                else:
                    return jsonify({
                        'error': 'Binance API error',
                        'message': str(e)
                    }), 400
            except Exception as e:
                logger.warning(f"Could not fetch account balance from Binance API: {e}")
                return jsonify({
                    'error': 'Connection error',
                    'message': 'Could not connect to Binance API. Please check your API keys and try again.'
                }), 500
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return jsonify({'error': str(e)}), 500
