import os
import logging
import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode
import numpy as np
from decimal import Decimal, ROUND_DOWN
from flask import current_app
from binance.client import Client
from binance.exceptions import BinanceAPIException
from app import db
from models import User, GridConfig, GridPosition, TradeHistory

# Configure logging
logger = logging.getLogger(__name__)

class BinanceClient:
    def __init__(self, api_key=None, api_secret=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://fapi.binance.com"
        
        # If API keys are provided, create client
        if api_key and api_secret:
            self.client = Client(api_key, api_secret)
        else:
            self.client = None

    def _generate_signature(self, params):
        """Generate HMAC SHA256 signature for API authentication"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _make_request(self, method, endpoint, params=None, signed=False):
        """Make API request to Binance with proper authentication"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            'X-MBX-APIKEY': self.api_key
        }
        
        if params is None:
            params = {}
            
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, headers=headers, params=params)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, params=params)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            # Check for geographic restriction error (HTTP 451)
            if response.status_code == 451:
                error_data = response.json()
                logger.error(f"Geographic restriction error: {error_data}")
                raise BinanceAPIException(
                    status_code=response.status_code,
                    response=response,
                    code=error_data.get('code', 0),
                    msg="Service unavailable from your location due to geographic restrictions. Please try using a VPN from a supported region or deploy this bot on a server in a supported region."
                )
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 451:
                # Already handled above
                raise
            logger.error(f"Error making request to Binance: {e}")
            raise

    def check_connection(self):
        """Check if API connection is working"""
        try:
            self._make_request('GET', '/fapi/v1/ping')
            return True
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            return False

    def get_account_info(self):
        """Get account information"""
        return self._make_request('GET', '/fapi/v2/account', signed=True)

    def get_exchange_info(self):
        """Get exchange information"""
        return self._make_request('GET', '/fapi/v1/exchangeInfo')

    def get_symbol_price(self, symbol):
        """Get current price for a symbol"""
        params = {'symbol': symbol}
        return float(self._make_request('GET', '/fapi/v1/ticker/price', params)['price'])

    def change_margin_type(self, symbol, margin_type="ISOLATED"):
        """Change margin type for a symbol"""
        params = {
            'symbol': symbol,
            'marginType': margin_type
        }
        try:
            return self._make_request('POST', '/fapi/v1/marginType', params, signed=True)
        except Exception as e:
            # If already in this margin type, ignore error
            if "Already" in str(e):
                return {"msg": "Already in this margin type"}
            raise

    def change_leverage(self, symbol, leverage):
        """Change leverage for a symbol"""
        params = {
            'symbol': symbol,
            'leverage': leverage
        }
        return self._make_request('POST', '/fapi/v1/leverage', params, signed=True)

    def enable_hedge_mode(self):
        """Enable hedge mode for futures trading"""
        params = {
            'dualSidePosition': 'true'
        }
        try:
            return self._make_request('POST', '/fapi/v1/positionSide/dual', params, signed=True)
        except Exception as e:
            # If already enabled, ignore error
            if "already" in str(e).lower():
                return {"msg": "Hedge mode already enabled"}
            raise

    def get_open_positions(self, symbol=None):
        """Get all open positions or for a specific symbol"""
        account_info = self.get_account_info()
        positions = account_info['positions']
        
        if symbol:
            positions = [p for p in positions if p['symbol'] == symbol]
            
        return positions

    def get_precision(self, symbol):
        """Get price and quantity precision for a symbol"""
        exchange_info = self.get_exchange_info()
        symbol_info = next((s for s in exchange_info['symbols'] if s['symbol'] == symbol), None)
        
        if not symbol_info:
            raise ValueError(f"Symbol {symbol} not found")
        
        price_precision = 0
        qty_precision = 0
        
        for f in symbol_info['filters']:
            if f['filterType'] == 'PRICE_FILTER':
                tick_size = float(f['tickSize'])
                price_precision = len(str(tick_size).rstrip('0').split('.')[-1])
            elif f['filterType'] == 'LOT_SIZE':
                step_size = float(f['stepSize'])
                qty_precision = len(str(step_size).rstrip('0').split('.')[-1])
                
        return {
            'price_precision': price_precision,
            'qty_precision': qty_precision,
            'min_qty': float(symbol_info['filters'][1]['minQty']),
            'min_notional': float(symbol_info['filters'][5]['notional'])
        }

    def round_step_size(self, quantity, step_size):
        """Round quantity to valid step size"""
        precision = len(str(step_size).rstrip('0').split('.')[-1])
        return float(Decimal(str(quantity)).quantize(Decimal(str(step_size)), rounding=ROUND_DOWN))

    def place_order(self, symbol, side, position_side, type="LIMIT", quantity=None, price=None):
        """
        Place an order on Binance Futures
        
        Args:
            symbol (str): Trading pair
            side (str): BUY or SELL
            position_side (str): LONG or SHORT
            type (str): Order type (LIMIT, MARKET)
            quantity (float): Order quantity
            price (float): Order price (for LIMIT orders)
        """
        params = {
            'symbol': symbol,
            'side': side,
            'positionSide': position_side,
            'type': type,
            'quantity': quantity,
            'newOrderRespType': 'RESULT'
        }
        
        if type == 'LIMIT':
            params['price'] = price
            params['timeInForce'] = 'GTC'
        
        return self._make_request('POST', '/fapi/v1/order', params, signed=True)

    def cancel_order(self, symbol, order_id):
        """Cancel an open order"""
        params = {
            'symbol': symbol,
            'orderId': order_id
        }
        return self._make_request('DELETE', '/fapi/v1/order', params, signed=True)

    def get_order(self, symbol, order_id):
        """Get order status"""
        params = {
            'symbol': symbol,
            'orderId': order_id
        }
        return self._make_request('GET', '/fapi/v1/order', params, signed=True)

    def setup_grid_trading(self, grid_config):
        """Set up initial configuration for grid trading"""
        try:
            symbol = grid_config.symbol
            
            # Enable hedge mode
            self.enable_hedge_mode()
            
            # Change margin type to isolated
            self.change_margin_type(symbol)
            
            # Set leverage
            self.change_leverage(symbol, grid_config.leverage)
            
            return True
        except Exception as e:
            logger.error(f"Error setting up grid trading: {e}")
            return False
            
    def execute_grid_strategy(self, grid_config):
        """Execute grid trading strategy for a configuration"""
        logger.debug(f"Executing grid strategy for config {grid_config.id}")
        try:
            # Get current price
            current_price = self.get_symbol_price(grid_config.symbol)
            logger.debug(f"Current price for {grid_config.symbol}: {current_price}")
            
            # Calculate grid levels
            grid_levels = np.linspace(grid_config.lower_bound, grid_config.upper_bound, grid_config.grid_size)
            
            # Get precision for the symbol
            precision_info = self.get_precision(grid_config.symbol)
            price_precision = precision_info['price_precision']
            qty_precision = precision_info['qty_precision']
            
            # Format quantity based on precision
            quantity = round(grid_config.quantity_per_grid, qty_precision)
            
            # Check existing positions and place new orders if needed
            for i, price_level in enumerate(grid_levels):
                # Format price to match required precision
                price_level = round(price_level, price_precision)
                
                # Check for long position
                long_position = next((p for p in grid_config.long_positions if abs(p.price_level - price_level) < 0.0001), None)
                
                # Check for short position
                short_position = next((p for p in grid_config.short_positions if abs(p.price_level - price_level) < 0.0001), None)
                
                # Place long order if price is below current and no long position exists at this level
                if price_level < current_price and not long_position:
                    try:
                        order = self.place_order(
                            symbol=grid_config.symbol,
                            side="BUY",
                            position_side="LONG",
                            type="LIMIT",
                            quantity=quantity,
                            price=price_level
                        )
                        
                        # Create new grid position
                        new_position = GridPosition(
                            grid_config_id=grid_config.id,
                            position_type="long",
                            price_level=price_level,
                            quantity=quantity,
                            order_id=order['orderId'],
                            is_filled=False
                        )
                        db.session.add(new_position)
                        logger.debug(f"Placed long order at {price_level}")
                    except Exception as e:
                        logger.error(f"Error placing long order at {price_level}: {e}")
                
                # Place short order if price is above current and no short position exists at this level
                if price_level > current_price and not short_position:
                    try:
                        order = self.place_order(
                            symbol=grid_config.symbol,
                            side="SELL",
                            position_side="SHORT",
                            type="LIMIT",
                            quantity=quantity,
                            price=price_level
                        )
                        
                        # Create new grid position
                        new_position = GridPosition(
                            grid_config_id=grid_config.id,
                            position_type="short",
                            price_level=price_level,
                            quantity=quantity,
                            order_id=order['orderId'],
                            is_filled=False
                        )
                        db.session.add(new_position)
                        logger.debug(f"Placed short order at {price_level}")
                    except Exception as e:
                        logger.error(f"Error placing short order at {price_level}: {e}")
            
            # Check and update orders status
            self.update_order_status(grid_config)
            
            # Commit session
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error executing grid strategy: {e}")
            return False

    def update_order_status(self, grid_config):
        """Update status of all orders for a grid configuration"""
        # Get all positions with order_id
        all_positions = []
        all_positions.extend(grid_config.long_positions)
        all_positions.extend(grid_config.short_positions)
        
        for position in all_positions:
            if position.order_id and not position.is_filled:
                try:
                    order_status = self.get_order(grid_config.symbol, position.order_id)
                    
                    # Check if order is filled
                    if order_status['status'] == 'FILLED':
                        position.is_filled = True
                        
                        # Record trade in history
                        trade = TradeHistory(
                            user_id=grid_config.user_id,
                            grid_config_id=grid_config.id,
                            symbol=grid_config.symbol,
                            order_id=position.order_id,
                            side=order_status['side'],
                            position_side=order_status['positionSide'],
                            price=float(order_status['price']),
                            quantity=float(order_status['executedQty']),
                            realized_profit=0,  # To be calculated later
                            commission=float(order_status.get('commission', 0)),
                            executed_at=datetime.datetime.fromtimestamp(order_status['updateTime']/1000)
                        )
                        db.session.add(trade)
                        
                        # Place opposite order for profit taking
                        try:
                            opposite_side = "SELL" if order_status['side'] == "BUY" else "BUY"
                            opposite_position_side = "LONG" if order_status['positionSide'] == "LONG" else "SHORT"
                            
                            # Calculate profit taking price based on grid step
                            grid_step = (grid_config.upper_bound - grid_config.lower_bound) / (grid_config.grid_size - 1)
                            current_price = float(order_status['price'])
                            
                            # For long positions, sell one level up
                            # For short positions, buy one level down
                            if order_status['positionSide'] == "LONG":
                                profit_price = current_price + grid_step
                            else:
                                profit_price = current_price - grid_step
                                
                            # Get precision for formatting
                            precision_info = self.get_precision(grid_config.symbol)
                            price_precision = precision_info['price_precision']
                            
                            # Format profit price
                            profit_price = round(profit_price, price_precision)
                            
                            # Place opposite order
                            self.place_order(
                                symbol=grid_config.symbol,
                                side=opposite_side,
                                position_side=opposite_position_side,
                                type="LIMIT",
                                quantity=float(order_status['executedQty']),
                                price=profit_price
                            )
                            
                        except Exception as e:
                            logger.error(f"Error placing profit taking order: {e}")
                    
                    # Check if order is cancelled or expired
                    elif order_status['status'] in ['CANCELED', 'EXPIRED', 'REJECTED']:
                        # Remove position from database
                        db.session.delete(position)
                        
                except BinanceAPIException as e:
                    # If order not found, remove from database
                    if e.code == -2013:  # Order does not exist
                        db.session.delete(position)
                    else:
                        logger.error(f"Error checking order status: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error checking order status: {e}")

def update_active_grids():
    """Update all active grid configurations"""
    from app import app
    with app.app_context():
        try:
            # Get all active grid configurations
            active_grids = GridConfig.query.filter_by(is_active=True).all()
            
            for grid in active_grids:
                # Get the user
                user = User.query.get(grid.user_id)
                
                if user and user.api_key and user.api_secret:
                    # Create binance client
                    client = BinanceClient(user.api_key, user.api_secret)
                    
                    # Execute grid strategy
                    client.execute_grid_strategy(grid)
                    
            logger.debug(f"Updated {len(active_grids)} active grid configurations")
        except Exception as e:
            logger.error(f"Error updating active grids: {e}")
