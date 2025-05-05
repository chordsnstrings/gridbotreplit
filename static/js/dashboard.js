/**
 * Dashboard functions for the Binance Futures Grid Bot
 */

// Format number with appropriate decimal places
function formatNumber(number, decimals = 2) {
    if (number === null || number === undefined) return '-';
    return parseFloat(number).toFixed(decimals);
}

// Toggle grid bot status
function toggleGridBot(gridId) {
    // Submit the form programmatically
    document.querySelector(`#toggleForm${gridId}`).submit();
}

// Update grid statistics
function updateGridStats(gridId) {
    fetch(`/api/grid/${gridId}/stats`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // Update displayed statistics
            const statsContainer = document.querySelector(`#gridStats${gridId}`);
            if (statsContainer && data) {
                // Update profit stats
                if (data.performance) {
                    document.querySelector(`#totalProfit${gridId}`).textContent = 
                        formatNumber(data.performance.net_profit, 4);
                    document.querySelector(`#winRate${gridId}`).textContent = 
                        formatNumber(data.performance.win_rate) + '%';
                    document.querySelector(`#totalTrades${gridId}`).textContent = 
                        data.performance.total_trades;
                }
            }
        })
        .catch(error => {
            console.error('Error updating grid stats:', error);
        });
}

// Initialize the create grid form
function initCreateGridForm() {
    // Form elements
    const symbolSelect = document.getElementById('symbol');
    const lowerBoundInput = document.getElementById('lower_bound');
    const upperBoundInput = document.getElementById('upper_bound');
    const gridSizeInput = document.getElementById('grid_size');
    const quantityPerGridInput = document.getElementById('quantity_per_grid');
    const leverageInput = document.getElementById('leverage');
    const walletAllocationInput = document.getElementById('wallet_allocation');
    const walletAllocationSlider = document.getElementById('wallet_allocation_slider');
    const rangePercentageSlider = document.getElementById('range_percentage');
    const rangePercentText = document.getElementById('rangePercent');
    const rangePercentDisplay = rangePercentageSlider.nextElementSibling;
    const botTypeRadios = document.querySelectorAll('input[name="bot_type"]');
    
    // Display elements
    const marketPriceInfo = document.getElementById('marketPriceInfo');
    const currentPriceDisplay = document.getElementById('currentPrice');
    const walletBalanceDisplay = document.getElementById('walletBalance');
    const allocationAmountDisplay = document.getElementById('allocationAmount');
    const walletInfoDisplay = document.getElementById('walletInfo');
    const gridStepPreview = document.getElementById('gridStepPreview');
    
    // State variables
    let currentPrice = 0;
    let walletBalance = 0;
    let selectedSymbol = '';
    
    // Load wallet balance
    function loadWalletBalance() {
        fetch('/api/account/balance')
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errorData => {
                        // Handle HTTP errors with error message from server
                        throw new Error(errorData.message || `Error ${response.status}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.usdt_balance) {
                    walletBalance = parseFloat(data.usdt_balance);
                    walletBalanceDisplay.textContent = formatNumber(walletBalance, 2);
                    walletInfoDisplay.classList.remove('d-none');
                    walletErrorMessage.classList.add('d-none');
                    updateAllocationAmount();
                }
            })
            .catch(error => {
                console.error('Error loading wallet balance:', error);
                walletInfoDisplay.classList.add('d-none');
                
                // Show error message
                walletErrorMessage.textContent = error.message || 'Could not connect to Binance API. Please check your API keys.';
                walletErrorMessage.classList.remove('d-none');
                
                // If it's a geographic restriction error
                if (error.message && error.message.includes('Geographic restriction')) {
                    walletErrorMessage.innerHTML = `
                        <div class="alert alert-warning">
                            <strong>Geographic Restriction:</strong> ${error.message}
                            <a href="/settings" class="alert-link">Check Settings</a> for possible solutions.
                        </div>
                    `;
                }
            });
    }
    
    // Update quantity calculations based on allocation
    function updateAllocationAmount() {
        const allocation = parseFloat(walletAllocationInput.value) / 100;
        const allocationAmount = walletBalance * allocation;
        allocationAmountDisplay.textContent = formatNumber(allocationAmount, 2);
        
        // Calculate quantity per grid
        calculateQuantityPerGrid(allocationAmount);
    }
    
    // Calculate quantity per grid based on allocation and grid settings
    function calculateQuantityPerGrid(allocationAmount) {
        if (!currentPrice || currentPrice <= 0 || !allocationAmount) return;
        
        const gridSize = parseInt(gridSizeInput.value);
        const botType = document.querySelector('input[name="bot_type"]:checked').value;
        const leverage = parseInt(leverageInput.value);
        
        // Determine number of grid positions based on bot type
        let gridPositions = gridSize;
        if (botType === 'both') {
            gridPositions = gridSize * 2; // Both long and short
        }
        
        // Calculate quantity per grid with leverage
        const effectiveAllocation = allocationAmount * leverage;
        const quantityPerGrid = effectiveAllocation / (gridPositions * currentPrice);
        
        // Update the quantity per grid input
        quantityPerGridInput.value = formatNumber(quantityPerGrid, 8);
    }
    
    // Update grid bounds based on current price and range percentage
    function updateGridBounds() {
        if (!currentPrice || currentPrice <= 0) return;
        
        const rangePercent = parseInt(rangePercentageSlider.value) / 100;
        const lower = currentPrice * (1 - rangePercent);
        const upper = currentPrice * (1 + rangePercent);
        
        // Update inputs
        lowerBoundInput.value = formatNumber(lower, 8);
        upperBoundInput.value = formatNumber(upper, 8);
        
        // Update grid preview
        updateGridPreview();
    }
    
    // Update grid step preview
    function updateGridPreview() {
        const lowerBound = parseFloat(lowerBoundInput.value);
        const upperBound = parseFloat(upperBoundInput.value);
        const gridSize = parseInt(gridSizeInput.value);
        
        if (!isNaN(lowerBound) && !isNaN(upperBound) && !isNaN(gridSize) && gridSize >= 2) {
            const gridStep = (upperBound - lowerBound) / (gridSize - 1);
            
            if (gridStepPreview) {
                gridStepPreview.innerHTML = `<div class="alert alert-secondary">
                    <i class="fas fa-calculator me-2"></i>
                    <strong>Grid Step:</strong> ${formatNumber(gridStep, 6)} (${formatNumber(gridStep/currentPrice*100, 2)}% of price)
                </div>`;
                gridStepPreview.classList.remove('d-none');
            }
        }
    }
    
    // Load current price for a symbol
    function loadSymbolPrice(symbol) {
        selectedSymbol = symbol;
        
        fetch(`/api/symbol/${symbol}/price`)
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errorData => {
                        // Handle HTTP errors with error message from server
                        throw new Error(errorData.message || `Error ${response.status}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.price) {
                    currentPrice = parseFloat(data.price);
                    currentPriceDisplay.textContent = formatNumber(currentPrice, 8);
                    marketPriceInfo.classList.remove('d-none');
                    marketErrorMessage.classList.add('d-none');
                    
                    // Update UI based on current price
                    updateGridBounds();
                    updateAllocationAmount();
                }
            })
            .catch(error => {
                console.error('Error fetching price:', error);
                marketPriceInfo.classList.add('d-none');
                
                // Show error message
                marketErrorMessage.textContent = error.message || 'Could not connect to Binance API. Please check your API keys.';
                marketErrorMessage.classList.remove('d-none');
                
                // If it's a geographic restriction error
                if (error.message && error.message.includes('Geographic restriction')) {
                    marketErrorMessage.innerHTML = `
                        <div class="alert alert-warning">
                            <strong>Geographic Restriction:</strong> ${error.message}
                            <a href="/settings" class="alert-link">Check Settings</a> for possible solutions.
                        </div>
                    `;
                }
            });
    }
    
    // Add event listeners
    if (symbolSelect) {
        symbolSelect.addEventListener('change', function() {
            if (this.value) {
                loadSymbolPrice(this.value);
                loadWalletBalance();
            } else {
                marketPriceInfo.classList.add('d-none');
                walletInfoDisplay.classList.add('d-none');
            }
        });
    }
    
    // Range percentage slider
    if (rangePercentageSlider) {
        rangePercentageSlider.addEventListener('input', function() {
            const value = this.value;
            rangePercentText.textContent = value;
            rangePercentDisplay.textContent = `${value}%`;
            updateGridBounds();
        });
    }
    
    // Wallet allocation slider
    if (walletAllocationSlider && walletAllocationInput) {
        // Sync slider with input
        walletAllocationSlider.addEventListener('input', function() {
            walletAllocationInput.value = this.value;
            updateAllocationAmount();
        });
        
        walletAllocationInput.addEventListener('input', function() {
            walletAllocationSlider.value = this.value;
            updateAllocationAmount();
        });
    }
    
    // Grid size input
    if (gridSizeInput) {
        gridSizeInput.addEventListener('input', function() {
            updateGridPreview();
            updateAllocationAmount();
        });
    }
    
    // Bounds inputs
    if (lowerBoundInput && upperBoundInput) {
        lowerBoundInput.addEventListener('input', updateGridPreview);
        upperBoundInput.addEventListener('input', updateGridPreview);
    }
    
    // Bot type radios
    botTypeRadios.forEach(radio => {
        radio.addEventListener('change', updateAllocationAmount);
    });
    
    // Leverage input
    if (leverageInput) {
        leverageInput.addEventListener('input', updateAllocationAmount);
    }
}

// Initialize grid bot dashboard
function initDashboard() {
    // Initialize grid form
    initCreateGridForm();
    
    // Initialize auto-updating for active grids
    const activeGrids = document.querySelectorAll('.grid-card[data-active="true"]');
    if (activeGrids.length > 0) {
        // Update stats for active grids every 30 seconds
        setInterval(() => {
            activeGrids.forEach(grid => {
                const gridId = grid.dataset.gridId;
                updateGridStats(gridId);
                // Also update grid visualization
                updateGridChart(gridId);
            });
        }, 30000);
    }
}

// When DOM is loaded, initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    initDashboard();
});
