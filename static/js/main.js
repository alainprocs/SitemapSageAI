document.addEventListener('DOMContentLoaded', function() {
    // Handle form submission with loading indicator
    const form = document.getElementById('sitemap-form');
    const submitButton = document.getElementById('submit-button');
    const loadingIndicator = document.getElementById('loading-indicator');
    
    if (form) {
        form.addEventListener('submit', function(e) {
            // Show loading state
            if (submitButton) submitButton.disabled = true;
            if (loadingIndicator) loadingIndicator.classList.remove('hidden');
        });
    }
    
    // Initialize cluster charts if we're on the results page
    const chartContainer = document.getElementById('clusters-chart');
    if (chartContainer) {
        initializeClusterChart();
    }
});

function initializeClusterChart() {
    try {
        // Get cluster data from the page
        const chartDataElement = document.getElementById('chart-data');
        if (!chartDataElement) {
            console.error('Chart data element not found');
            return;
        }
        
        const chartData = JSON.parse(chartDataElement.textContent);
        console.log('Chart data:', chartData);
        
        const ctx = document.getElementById('clusters-chart').getContext('2d');
        
        // Check if chartData has the expected structure
        if (!chartData || !chartData.clusters || !Array.isArray(chartData.clusters)) {
            console.error('Invalid chart data structure', chartData);
            displayChartError('clusters-chart', 'Invalid data structure for cluster chart');
            return;
        }
        
        // Extract titles and counts for the chart
        const titles = chartData.clusters.map(cluster => cluster.title || 'Unnamed Cluster');
        
        // Handle different count formats: numeric string or actual number
        const counts = chartData.clusters.map(cluster => {
            console.log('Processing cluster:', cluster.title, 'with count:', cluster.count);
            
            if (typeof cluster.count === 'number') {
                return cluster.count;
            } else if (typeof cluster.count === 'string') {
                // Try to parse the count from formats like "~120" or "approximately 50"
                const numMatch = cluster.count.match(/\d+/);
                const extractedCount = numMatch ? parseInt(numMatch[0]) : 0;
                console.log(`Extracted count ${extractedCount} from string "${cluster.count}"`);
                return extractedCount;
            }
            console.warn('No valid count found for cluster:', cluster.title);
            return 1; // Default to 1 instead of 0 to ensure at least some visibility
        });
        
        // Check if we have valid data
        if (titles.length === 0 || counts.some(isNaN)) {
            console.error('Invalid titles or counts found in chart data', { titles, counts });
            displayChartError('clusters-chart', 'Invalid cluster data found');
            return;
        }
        
        console.log('Prepared chart data:', { titles, counts });
        
        // Ensure we have enough colors (modern monochrome with subtle accent)
        const backgroundColors = [
            'rgba(255, 255, 255, 0.9)',
            'rgba(230, 230, 230, 0.8)',
            'rgba(200, 200, 200, 0.8)',
            'rgba(170, 170, 170, 0.8)',
            'rgba(140, 140, 140, 0.8)',
            'rgba(110, 110, 110, 0.8)',
            'rgba(80, 80, 80, 0.8)',
            'rgba(50, 50, 50, 0.8)'
        ];
        
        const borderColors = backgroundColors.map(color => color.replace('0.8', '1'));
        
        // Create a pie chart
        new Chart(ctx, {
            type: 'pie',
            data: {
                labels: titles,
                datasets: [{
                    data: counts,
                    backgroundColor: backgroundColors.slice(0, titles.length),
                    borderColor: borderColors.slice(0, titles.length),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#fff'
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.label}: ${context.raw} URLs`;
                            }
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error initializing cluster chart:', error);
        displayChartError('clusters-chart', 'Error rendering cluster chart');
    }
    
    try {
        // Create a bar chart for depth distribution
        const depthDataElement = document.getElementById('depth-data');
        if (!depthDataElement) {
            console.error('Depth data element not found');
            return;
        }
        
        const depthData = JSON.parse(depthDataElement.textContent);
        console.log('Depth data:', depthData);
        
        const depthCtx = document.getElementById('depth-chart').getContext('2d');
        
        // Check if depthData is valid
        if (!depthData || typeof depthData !== 'object' || Object.keys(depthData).length === 0) {
            console.error('Invalid depth data structure', depthData);
            displayChartError('depth-chart', 'Invalid data structure for depth chart');
            return;
        }
        
        const depths = Object.keys(depthData).sort((a, b) => parseInt(a) - parseInt(b));
        const depthCounts = depths.map(depth => depthData[depth]);
        
        // Check if we have valid data
        if (depths.length === 0 || depthCounts.some(isNaN)) {
            console.error('Invalid depth data found', { depths, depthCounts });
            displayChartError('depth-chart', 'Invalid depth data found');
            return;
        }
        
        console.log('Prepared depth data:', { depths, depthCounts });
        
        new Chart(depthCtx, {
            type: 'bar',
            data: {
                labels: depths.map(d => `Depth ${d}`),
                datasets: [{
                    label: 'URLs',
                    data: depthCounts,
                    backgroundColor: 'rgba(255, 255, 255, 0.8)',
                    borderColor: 'rgba(255, 255, 255, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Number of URLs',
                            color: '#fff'
                        },
                        ticks: {
                            color: '#fff'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'URL Path Depth',
                            color: '#fff'
                        },
                        ticks: {
                            color: '#fff'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: {
                            color: '#fff'
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error initializing depth chart:', error);
        displayChartError('depth-chart', 'Error rendering depth chart');
    }
}

// Helper function to display error message in chart containers
function displayChartError(chartId, message) {
    const chartContainer = document.getElementById(chartId);
    if (!chartContainer) return;
    
    // Create and append error message
    const errorDiv = document.createElement('div');
    errorDiv.className = 'chart-error-message';
    errorDiv.textContent = message;
    errorDiv.style.color = '#dc3545';
    errorDiv.style.padding = '20px';
    errorDiv.style.textAlign = 'center';
    
    // Add refresh suggestion
    const refreshText = document.createElement('div');
    refreshText.textContent = 'Try refreshing the page or using a different sitemap URL.';
    refreshText.style.fontSize = '0.9em';
    refreshText.style.marginTop = '10px';
    errorDiv.appendChild(refreshText);
    
    // Replace canvas with error message
    const parent = chartContainer.parentNode;
    parent.removeChild(chartContainer);
    parent.appendChild(errorDiv);
}
