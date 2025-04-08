document.addEventListener('DOMContentLoaded', function() {
    // Handle form submission with loading indicator
    const form = document.getElementById('sitemap-form');
    const submitButton = document.getElementById('submit-button');
    const loadingIndicator = document.getElementById('loading-indicator');
    
    if (form) {
        form.addEventListener('submit', function(e) {
            // Show loading state
            if (submitButton) submitButton.disabled = true;
            if (loadingIndicator) loadingIndicator.classList.remove('d-none');
        });
    }
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize cluster charts if we're on the results page
    const chartContainer = document.getElementById('clusters-chart');
    if (chartContainer) {
        initializeClusterChart();
    }
    
    // Copy to clipboard functionality
    const copyButtons = document.querySelectorAll('.copy-btn');
    copyButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const textToCopy = this.getAttribute('data-copy');
            navigator.clipboard.writeText(textToCopy).then(() => {
                // Change button text temporarily
                const originalText = this.textContent;
                this.textContent = 'Copied!';
                setTimeout(() => {
                    this.textContent = originalText;
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy text: ', err);
            });
        });
    });
});

function initializeClusterChart() {
    // Get cluster data from the page
    const chartData = JSON.parse(document.getElementById('chart-data').textContent);
    const ctx = document.getElementById('clusters-chart').getContext('2d');
    
    // Extract titles and counts for the chart
    const titles = chartData.clusters.map(cluster => cluster.title);
    const counts = chartData.clusters.map(cluster => parseInt(cluster.count));
    
    // Create a pie chart
    new Chart(ctx, {
        type: 'pie',
        data: {
            labels: titles,
            datasets: [{
                data: counts,
                backgroundColor: [
                    'rgba(75, 192, 192, 0.8)',
                    'rgba(54, 162, 235, 0.8)',
                    'rgba(153, 102, 255, 0.8)',
                    'rgba(255, 206, 86, 0.8)',
                    'rgba(255, 99, 132, 0.8)'
                ],
                borderColor: [
                    'rgba(75, 192, 192, 1)',
                    'rgba(54, 162, 235, 1)',
                    'rgba(153, 102, 255, 1)',
                    'rgba(255, 206, 86, 1)',
                    'rgba(255, 99, 132, 1)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
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
    
    // Create a bar chart for depth distribution
    const depthData = JSON.parse(document.getElementById('depth-data').textContent);
    const depthCtx = document.getElementById('depth-chart').getContext('2d');
    
    const depths = Object.keys(depthData).sort((a, b) => parseInt(a) - parseInt(b));
    const depthCounts = depths.map(depth => depthData[depth]);
    
    new Chart(depthCtx, {
        type: 'bar',
        data: {
            labels: depths.map(d => `Depth ${d}`),
            datasets: [{
                label: 'URLs',
                data: depthCounts,
                backgroundColor: 'rgba(54, 162, 235, 0.8)',
                borderColor: 'rgba(54, 162, 235, 1)',
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
                        text: 'Number of URLs'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'URL Path Depth'
                    }
                }
            }
        }
    });
}
