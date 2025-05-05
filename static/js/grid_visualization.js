/**
 * Grid visualization using Chart.js
 */

// Store chart instances
const gridCharts = {};

// Initialize a grid chart
function initGridChart(gridId) {
    const ctx = document.getElementById(`gridChart${gridId}`);
    if (!ctx) return;
    
    // Create chart instance
    const chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [], // Will be filled with price levels
            datasets: [
                {
                    label: 'Grid Levels',
                    data: [], // Will be filled with y-values for horizontal lines
                    borderColor: 'rgba(75, 192, 192, 0.5)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: false,
                    tension: 0
                },
                {
                    label: 'Long Positions',
                    data: [], // Will be filled with long position data
                    backgroundColor: 'rgba(46, 204, 113, 0.8)',
                    borderColor: 'rgba(46, 204, 113, 1)',
                    pointRadius: 5,
                    pointHoverRadius: 7,
                    showLine: false
                },
                {
                    label: 'Short Positions',
                    data: [], // Will be filled with short position data
                    backgroundColor: 'rgba(231, 76, 60, 0.8)',
                    borderColor: 'rgba(231, 76, 60, 1)',
                    pointRadius: 5,
                    pointHoverRadius: 7,
                    showLine: false
                },
                {
                    label: 'Current Price',
                    data: [], // Will be filled with current price data
                    backgroundColor: 'rgba(241, 196, 15, 0.8)',
                    borderColor: 'rgba(241, 196, 15, 1)',
                    pointRadius: 6,
                    pointHoverRadius: 8,
                    showLine: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    display: false,
                    beginAtZero: true
                },
                y: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)',
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            
                            if (context.datasetIndex === 0) {
                                label += context.parsed.y;
                            } else if (context.datasetIndex === 1) {
                                label += `Price: ${context.parsed.y} (Long)`;
                                if (context.raw.filled) {
                                    label += ' - Filled';
                                }
                            } else if (context.datasetIndex === 2) {
                                label += `Price: ${context.parsed.y} (Short)`;
                                if (context.raw.filled) {
                                    label += ' - Filled';
                                }
                            } else if (context.datasetIndex === 3) {
                                label += `Current: ${context.parsed.y}`;
                            }
                            
                            return label;
                        }
                    }
                }
            }
        }
    });
    
    // Store chart instance
    gridCharts[gridId] = chart;
    
    // Load initial data
    updateGridChart(gridId);
}

// Update grid chart with current data
function updateGridChart(gridId) {
    if (!gridCharts[gridId]) return;
    
    fetch(`/api/grid/${gridId}/positions`)
        .then(response => response.json())
        .then(data => {
            const chart = gridCharts[gridId];
            
            // Set grid levels
            if (data.grid_levels && data.grid_levels.length > 0) {
                const gridLevels = data.grid_levels;
                
                // Create labels for each grid level
                const labels = Array(gridLevels.length).fill('').map((_, i) => i.toString());
                
                // Get bot type from data or default to 'both'
                const botType = data.bot_type || 'both';
                
                // Update chart title based on bot type
                const gridInfoElement = document.querySelector(`#gridInfo${gridId} .bot-type`);
                if (gridInfoElement) {
                    let botTypeText = '';
                    let botTypeClass = '';
                    
                    switch(botType) {
                        case 'long':
                            botTypeText = 'Long Only';
                            botTypeClass = 'text-success';
                            break;
                        case 'short':
                            botTypeText = 'Short Only';
                            botTypeClass = 'text-danger';
                            break;
                        default:
                            botTypeText = 'Long & Short';
                            botTypeClass = 'text-primary';
                    }
                    
                    gridInfoElement.textContent = botTypeText;
                    gridInfoElement.className = `bot-type ${botTypeClass}`;
                }
                
                // Prepare grid level dataset
                const gridDataset = {
                    label: 'Grid Levels',
                    data: gridLevels.map((level, i) => ({ x: i, y: level })),
                    borderColor: 'rgba(75, 192, 192, 0.5)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: false,
                    tension: 0
                };
                
                // Prepare long positions dataset
                const longPositions = botType === 'short' ? [] : data.long_positions.map(pos => ({
                    x: gridLevels.findIndex(level => Math.abs(level - pos.price_level) < 0.0001),
                    y: pos.price_level,
                    filled: pos.is_filled
                }));
                
                // Prepare short positions dataset
                const shortPositions = botType === 'long' ? [] : data.short_positions.map(pos => ({
                    x: gridLevels.findIndex(level => Math.abs(level - pos.price_level) < 0.0001),
                    y: pos.price_level,
                    filled: pos.is_filled
                }));
                
                // Prepare current price dataset
                const currentPriceData = [];
                if (data.current_price) {
                    // Find closest index for display purposes
                    const closestIndex = findClosestGridLevelIndex(gridLevels, data.current_price);
                    currentPriceData.push({
                        x: closestIndex,
                        y: data.current_price
                    });
                    
                    // Update current price display if element exists
                    const currentPriceElement = document.querySelector(`#gridInfo${gridId} .current-price`);
                    if (currentPriceElement) {
                        currentPriceElement.textContent = formatNumber(data.current_price, 6);
                    }
                }
                
                // Update chart data
                chart.data.labels = labels;
                chart.data.datasets[0].data = gridDataset.data;
                chart.data.datasets[1].data = longPositions;
                chart.data.datasets[2].data = shortPositions;
                chart.data.datasets[3].data = currentPriceData;
                
                // Show/hide datasets based on bot type
                chart.data.datasets[1].hidden = botType === 'short';
                chart.data.datasets[2].hidden = botType === 'long';
                
                // Update chart scales to properly display all data
                const minPrice = Math.min(...gridLevels);
                const maxPrice = Math.max(...gridLevels);
                const padding = (maxPrice - minPrice) * 0.05; // 5% padding
                
                chart.options.scales.y.min = minPrice - padding;
                chart.options.scales.y.max = maxPrice + padding;
                
                // Update chart
                chart.update();
                
                // Update grid stats display
                updateGridStatsDisplay(gridId, data);
            }
        })
        .catch(error => {
            console.error('Error updating grid chart:', error);
        });
}

// Update grid statistics display
function updateGridStatsDisplay(gridId, data) {
    // Update grid information elements if they exist
    const statsContainer = document.querySelector(`#gridStats${gridId}`);
    if (!statsContainer) return;
    
    const gridLevels = data.grid_levels || [];
    if (gridLevels.length > 0) {
        // Calculate grid stats
        const minPrice = Math.min(...gridLevels);
        const maxPrice = Math.max(...gridLevels);
        const gridStep = (maxPrice - minPrice) / (gridLevels.length - 1);
        const currentPrice = data.current_price || 0;
        
        // Update stats
        const lowerBoundElement = statsContainer.querySelector('.lower-bound');
        const upperBoundElement = statsContainer.querySelector('.upper-bound');
        const gridStepElement = statsContainer.querySelector('.grid-step');
        const rangePercentElement = statsContainer.querySelector('.range-percent');
        
        if (lowerBoundElement) lowerBoundElement.textContent = formatNumber(minPrice, 6);
        if (upperBoundElement) upperBoundElement.textContent = formatNumber(maxPrice, 6);
        if (gridStepElement) gridStepElement.textContent = formatNumber(gridStep, 6);
        
        if (rangePercentElement && currentPrice > 0) {
            const rangePercent = ((maxPrice - minPrice) / currentPrice) * 100;
            rangePercentElement.textContent = formatNumber(rangePercent, 2) + '%';
        }
    }
}

// Helper function to find the closest grid level index for a price
function findClosestGridLevelIndex(gridLevels, price) {
    if (!gridLevels || gridLevels.length === 0) return 0;
    
    let closestIndex = 0;
    let closestDiff = Math.abs(gridLevels[0] - price);
    
    for (let i = 1; i < gridLevels.length; i++) {
        const diff = Math.abs(gridLevels[i] - price);
        if (diff < closestDiff) {
            closestDiff = diff;
            closestIndex = i;
        }
    }
    
    return closestIndex;
}
