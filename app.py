import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session
from sitemap_analyzer import fetch_sitemap, parse_sitemap, analyze_sitemap_structure
from openai_client import identify_topical_clusters

# Set up logging for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default-secret-key-for-development")

# Rate limiting variables
MAX_REQUESTS_PER_HOUR = 10
request_counter = {}

@app.route('/')
def index():
    """Render the main page with the sitemap URL input form."""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """Process the sitemap URL and analyze it for topical clusters."""
    sitemap_url = request.form.get('sitemap_url')
    
    if not sitemap_url:
        flash('Please enter a sitemap URL', 'danger')
        return redirect(url_for('index'))
    
    # Check if URL starts with http:// or https://
    if not sitemap_url.startswith(('http://', 'https://')):
        sitemap_url = 'https://' + sitemap_url
    
    # Simple rate limiting
    client_ip = request.remote_addr
    if client_ip in request_counter and request_counter[client_ip] >= MAX_REQUESTS_PER_HOUR:
        flash('Rate limit exceeded. Please try again later.', 'danger')
        return redirect(url_for('index'))
    
    try:
        # Fetch the sitemap
        xml_content = fetch_sitemap(sitemap_url)
        
        # Parse the sitemap to extract URLs
        urls = parse_sitemap(xml_content)
        
        if not urls:
            flash('No URLs found in the sitemap or invalid sitemap format', 'warning')
            return redirect(url_for('index'))
        
        # Get basic stats about the sitemap
        sitemap_stats = analyze_sitemap_structure(urls)
        
        # Use OpenAI to identify topical clusters
        clusters = identify_topical_clusters(urls, sitemap_stats)
        
        # Update rate limiting counter
        request_counter[client_ip] = request_counter.get(client_ip, 0) + 1
        
        # Store results in session for the results page
        session['sitemap_url'] = sitemap_url
        session['sitemap_stats'] = sitemap_stats
        session['clusters'] = clusters
        
        return redirect(url_for('results'))
        
    except Exception as e:
        logger.error(f"Error analyzing sitemap: {str(e)}")
        flash(f'Error analyzing sitemap: {str(e)}', 'danger')
        return render_template('error.html', error=str(e))

@app.route('/results')
def results():
    """Display the analysis results."""
    # Get results from session
    sitemap_url = session.get('sitemap_url')
    sitemap_stats = session.get('sitemap_stats')
    clusters = session.get('clusters')
    
    if not sitemap_url or not sitemap_stats or not clusters:
        flash('No analysis results found. Please submit a sitemap URL.', 'warning')
        return redirect(url_for('index'))
    
    return render_template(
        'results.html',
        sitemap_url=sitemap_url,
        sitemap_stats=sitemap_stats,
        clusters=clusters
    )

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template('error.html', error='Page not found'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    return render_template('error.html', error='Internal server error'), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
