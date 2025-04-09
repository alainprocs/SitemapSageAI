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
        initializeTextAnimations();
    }
    
    // Copy to clipboard functionality
    const copyButtons = document.querySelectorAll('.copy-btn');
    copyButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const textToCopy = this.getAttribute('data-copy');
            navigator.clipboard.writeText(textToCopy).then(() => {
                // Change button text temporarily
                const originalIcon = this.innerHTML;
                this.innerHTML = '<i class="fas fa-check"></i>';
                // Add a success class
                this.classList.add('btn-success');
                this.classList.remove('btn-outline-secondary');
                
                setTimeout(() => {
                    this.innerHTML = originalIcon;
                    // Restore original class
                    this.classList.remove('btn-success');
                    this.classList.add('btn-outline-secondary');
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy text: ', err);
                // Show error state
                this.innerHTML = '<i class="fas fa-times"></i>';
                this.classList.add('btn-danger');
                this.classList.remove('btn-outline-secondary');
                
                setTimeout(() => {
                    this.innerHTML = '<i class="fas fa-copy"></i>';
                    this.classList.remove('btn-danger');
                    this.classList.add('btn-outline-secondary');
                }, 2000);
            });
        });
    });
});

// Text animation functionality inspired by the JSX Preview component
function initializeTextAnimations() {
    // Store all elements to animate for coordinated timing
    const animationElements = {
        titles: document.querySelectorAll('.cluster-title'),
        descriptions: document.querySelectorAll('.cluster-card p'),
        badges: document.querySelectorAll('.badge'),
        headings: document.querySelectorAll('.cluster-card h5'),
        urls: document.querySelectorAll('.example-url'),
        recommendationItems: document.querySelectorAll('.recommendation-list li'),
        blogRecommendations: document.querySelectorAll('.recommendation-item')
    };
    
    // Initial setup for animations
    setupElementsForAnimation(animationElements);
    
    // Calculate total animation time based on content amount
    const estimatedBaseDelay = 800; // Base delay before starting animations
    
    // Start sequential animations
    startTitleAnimations(animationElements.titles, estimatedBaseDelay);
    startDescriptionAnimations(animationElements.descriptions, estimatedBaseDelay + 1000);
    startFadeInAnimations(animationElements.badges, estimatedBaseDelay + 1500);
    startFadeInAnimations(animationElements.headings, estimatedBaseDelay + 2000);
    startURLAnimations(animationElements.urls, estimatedBaseDelay + 2500);
    startSequentialFadeIn(animationElements.recommendationItems, estimatedBaseDelay + 3000);
    startSequentialFadeIn(animationElements.blogRecommendations, estimatedBaseDelay + 3500);
}

// Set up elements for animation
function setupElementsForAnimation(elements) {
    // Prepare titles and paragraphs for typing animation
    [...elements.titles, ...elements.descriptions].forEach(element => {
        // Only animate if content isn't too long
        if (element.textContent.length <= 150) {
            element.dataset.originalText = element.textContent;
            element.textContent = '';
            element.classList.add('animate-text');
        }
    });
    
    // Prepare badges, headings and URLs for fade-in animation
    [...elements.badges, ...elements.headings, ...elements.urls, ...elements.recommendationItems, ...elements.blogRecommendations].forEach(element => {
        element.style.opacity = 0;
        element.style.transform = 'translateY(15px)';
        element.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    });
}

// Animate titles with typing effect
function startTitleAnimations(elements, baseDelay) {
    elements.forEach((element, index) => {
        if (!element.dataset.originalText) return;
        
        const delay = baseDelay + (index * 400);
        const originalText = element.dataset.originalText;
        
        setTimeout(() => {
            let currentIndex = 0;
            const textInterval = setInterval(() => {
                if (currentIndex < originalText.length) {
                    element.textContent += originalText[currentIndex];
                    currentIndex++;
                } else {
                    clearInterval(textInterval);
                    element.classList.remove('animate-text');
                    element.classList.add('animate-complete');
                }
            }, 25); // Faster typing for titles
        }, delay);
    });
}

// Animate descriptions with typing effect
function startDescriptionAnimations(elements, baseDelay) {
    elements.forEach((element, index) => {
        if (!element.dataset.originalText) return;
        
        const delay = baseDelay + (index * 300);
        const originalText = element.dataset.originalText;
        
        setTimeout(() => {
            let currentIndex = 0;
            const textInterval = setInterval(() => {
                if (currentIndex < originalText.length) {
                    element.textContent += originalText[currentIndex];
                    currentIndex++;
                } else {
                    clearInterval(textInterval);
                    element.classList.remove('animate-text');
                    element.classList.add('animate-complete');
                }
            }, 10); // Ultra-fast typing for longer descriptions
        }, delay);
    });
}

// Fade in elements like badges and headings
function startFadeInAnimations(elements, baseDelay) {
    elements.forEach((element, index) => {
        setTimeout(() => {
            element.style.opacity = 1;
            element.style.transform = 'translateY(0)';
        }, baseDelay + (index * 150));
    });
}

// Special animation for URL examples
function startURLAnimations(elements, baseDelay) {
    elements.forEach((url, index) => {
        setTimeout(() => {
            // Quick flash effect before fade in (monochrome theme)
            url.style.backgroundColor = 'rgba(255, 255, 255, 0.15)';
            
            // Then fade in
            setTimeout(() => {
                url.style.opacity = 1;
                url.style.transform = 'translateY(0)';
                
                // Return to normal background
                setTimeout(() => {
                    url.style.backgroundColor = 'rgba(0, 0, 0, 0.2)';
                }, 300);
                
            }, 100);
        }, baseDelay + (index * 200));
    });
}

// Create a sequential fade-in effect for recommendations
function startSequentialFadeIn(elements, baseDelay) {
    elements.forEach((element, index) => {
        setTimeout(() => {
            element.style.opacity = 1;
            element.style.transform = 'translateY(0)';
            
            // Add a subtle highlight effect for monochrome theme
            element.style.backgroundColor = 'rgba(255, 255, 255, 0.1)';
            setTimeout(() => {
                element.style.backgroundColor = 'transparent';
            }, 500);
            
        }, baseDelay + (index * 150));
    });
}

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
        
        // Monochrome theme colors (shades of gray)
        const backgroundColors = [
            'rgba(220, 220, 220, 0.8)',
            'rgba(190, 190, 190, 0.8)',
            'rgba(160, 160, 160, 0.8)',
            'rgba(130, 130, 130, 0.8)',
            'rgba(100, 100, 100, 0.8)',
            'rgba(70, 70, 70, 0.8)',
            'rgba(50, 50, 50, 0.8)',
            'rgba(30, 30, 30, 0.8)'
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
                    backgroundColor: 'rgba(180, 180, 180, 0.8)',
                    borderColor: 'rgba(180, 180, 180, 1)',
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
