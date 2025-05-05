import logging
import numpy as np
from models import GridConfig, GridPosition, TradeHistory
from app import db

# Configure logging
logger = logging.getLogger(__name__)

def create_grid_levels(lower_bound, upper_bound, grid_size):
    """Create price levels for a grid strategy"""
    return np.linspace(lower_bound, upper_bound, grid_size)

def calculate_grid_profit(grid_config):
    """Calculate potential profit for a grid strategy"""
    # Calculate grid step size
    grid_step = (grid_config.upper_bound - grid_config.lower_bound) / (grid_config.grid_size - 1)
    
    # Calculate profit per grid (assuming full grid traversal)
    profit_per_grid = grid_step * grid_config.quantity_per_grid
    
    # Total potential profit if all grids are traversed
    total_potential_profit = profit_per_grid * (grid_config.grid_size - 1)
    
    # Calculate as percentage
    mid_price = (grid_config.upper_bound + grid_config.lower_bound) / 2
    profit_percentage = (total_potential_profit / (mid_price * grid_config.quantity_per_grid * grid_config.grid_size)) * 100
    
    return {
        'grid_step': grid_step,
        'profit_per_grid': profit_per_grid,
        'total_potential_profit': total_potential_profit,
        'profit_percentage': profit_percentage
    }

def calculate_grid_performance(grid_config):
    """Calculate actual performance of a grid strategy"""
    # Get all completed trades for this grid
    trades = TradeHistory.query.filter_by(grid_config_id=grid_config.id).all()
    
    total_profit = sum(trade.realized_profit or 0 for trade in trades)
    total_commission = sum(trade.commission or 0 for trade in trades)
    net_profit = total_profit - total_commission
    
    # Calculate ROI
    initial_investment = grid_config.lower_bound * grid_config.quantity_per_grid * grid_config.grid_size
    roi = (net_profit / initial_investment) * 100 if initial_investment > 0 else 0
    
    # Calculate win/loss ratio
    winning_trades = sum(1 for trade in trades if trade.realized_profit and trade.realized_profit > 0)
    losing_trades = sum(1 for trade in trades if trade.realized_profit and trade.realized_profit < 0)
    win_rate = (winning_trades / len(trades)) * 100 if trades else 0
    
    return {
        'total_trades': len(trades),
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'total_profit': total_profit,
        'total_commission': total_commission,
        'net_profit': net_profit,
        'roi': roi
    }

def validate_grid_parameters(symbol, lower_bound, upper_bound, grid_size, quantity_per_grid, leverage, bot_type='both', wallet_allocation=10):
    """Validate grid parameters"""
    errors = []
    
    if not symbol:
        errors.append("Symbol is required")
        
    try:
        lower_bound = float(lower_bound)
        if lower_bound <= 0:
            errors.append("Lower bound must be greater than 0")
    except (ValueError, TypeError):
        errors.append("Lower bound must be a number")
        
    try:
        upper_bound = float(upper_bound)
        if upper_bound <= 0:
            errors.append("Upper bound must be greater than 0")
    except (ValueError, TypeError):
        errors.append("Upper bound must be a number")
        
    if lower_bound and upper_bound and lower_bound >= upper_bound:
        errors.append("Upper bound must be greater than lower bound")
        
    try:
        grid_size = int(grid_size)
        if grid_size < 2:
            errors.append("Grid size must be at least 2")
        if grid_size > 100:
            errors.append("Grid size cannot exceed 100")
    except (ValueError, TypeError):
        errors.append("Grid size must be an integer")
        
    try:
        quantity_per_grid = float(quantity_per_grid)
        if quantity_per_grid <= 0:
            errors.append("Quantity per grid must be greater than 0")
    except (ValueError, TypeError):
        errors.append("Quantity per grid must be a number")
        
    try:
        leverage = int(leverage)
        if leverage < 1:
            errors.append("Leverage must be at least 1")
        if leverage > 125:
            errors.append("Leverage cannot exceed 125")
    except (ValueError, TypeError):
        errors.append("Leverage must be an integer")
        
    # Validate bot type
    if bot_type not in ['both', 'long', 'short']:
        errors.append("Bot type must be 'both', 'long', or 'short'")
    
    # Validate wallet allocation
    try:
        wallet_allocation = int(wallet_allocation)
        if wallet_allocation < 1:
            errors.append("Wallet allocation must be at least 1%")
        if wallet_allocation > 100:
            errors.append("Wallet allocation cannot exceed 100%")
    except (ValueError, TypeError):
        errors.append("Wallet allocation must be an integer")
        
    return errors

def create_grid_config(user_id, symbol, lower_bound, upper_bound, grid_size, quantity_per_grid, leverage, bot_type='both', wallet_allocation=10):
    """Create a new grid configuration"""
    try:
        # Create grid config
        grid_config = GridConfig(
            user_id=user_id,
            symbol=symbol,
            lower_bound=float(lower_bound),
            upper_bound=float(upper_bound),
            grid_size=int(grid_size),
            quantity_per_grid=float(quantity_per_grid),
            leverage=int(leverage),
            bot_type=bot_type,
            wallet_allocation=int(wallet_allocation),
            is_active=False
        )
        
        db.session.add(grid_config)
        db.session.commit()
        
        return grid_config
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating grid config: {e}")
        raise

def update_grid_config(grid_id, lower_bound=None, upper_bound=None, grid_size=None, quantity_per_grid=None, leverage=None, is_active=None):
    """Update an existing grid configuration"""
    try:
        grid_config = GridConfig.query.get(grid_id)
        
        if not grid_config:
            raise ValueError(f"Grid configuration with ID {grid_id} not found")
            
        if lower_bound is not None:
            grid_config.lower_bound = float(lower_bound)
            
        if upper_bound is not None:
            grid_config.upper_bound = float(upper_bound)
            
        if grid_size is not None:
            grid_config.grid_size = int(grid_size)
            
        if quantity_per_grid is not None:
            grid_config.quantity_per_grid = float(quantity_per_grid)
            
        if leverage is not None:
            grid_config.leverage = int(leverage)
            
        if is_active is not None:
            grid_config.is_active = bool(is_active)
            
        db.session.commit()
        
        return grid_config
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating grid config: {e}")
        raise

def delete_grid_config(grid_id):
    """Delete a grid configuration"""
    try:
        grid_config = GridConfig.query.get(grid_id)
        
        if not grid_config:
            raise ValueError(f"Grid configuration with ID {grid_id} not found")
            
        # Delete related positions
        GridPosition.query.filter_by(grid_config_id=grid_id).delete()
        
        # Delete the grid config
        db.session.delete(grid_config)
        db.session.commit()
        
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting grid config: {e}")
        raise
