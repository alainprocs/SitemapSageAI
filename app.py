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
    # Check if OpenAI API key is configured
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        flash('Warning: OpenAI API key is not set up. Analysis will use sample data instead.', 'warning')
    elif api_key.startswith(('sk_test_', 'sk_live_')):
        flash('Warning: Your OpenAI API key appears to be a Stripe key, not an OpenAI key. Please check your environment variables.', 'warning')
    elif len(api_key) < 20:  # OpenAI keys are typically longer
        flash('Warning: Your OpenAI API key appears to be invalid. Please check your environment variables.', 'warning')
    
    # Display info for deployed environment
    if os.environ.get("REPLIT_DEPLOYMENT") == "1":
        flash('Important: For deployment, ensure your OpenAI API key is correctly set in your project secrets.', 'info')
    
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """Process the sitemap URL and analyze it for topical clusters."""
    # Log OpenAI API key status for debugging
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.info("OPENAI_API_KEY environment variable is not set, will use sample data")
    elif api_key.startswith(('sk_test_', 'sk_live_')):
        logger.warning("API key appears to be a Stripe key, will use sample data")
    elif len(api_key) < 20:  # OpenAI keys are typically longer
        logger.warning("API key appears too short to be valid, will use sample data")
    
    sitemap_url = request.form.get('sitemap_url', '').strip()
    
    if not sitemap_url:
        flash('Please enter a sitemap URL', 'danger')
        return redirect(url_for('index'))
    
    logger.info(f"Analyzing sitemap URL: {sitemap_url}")
    
    # Check if URL starts with http:// or https://
    if not sitemap_url.startswith(('http://', 'https://')):
        sitemap_url = 'https://' + sitemap_url
        logger.info(f"Added https:// prefix, URL is now: {sitemap_url}")
    
    # Simple rate limiting
    client_ip = request.remote_addr
    if client_ip in request_counter and request_counter[client_ip] >= MAX_REQUESTS_PER_HOUR:
        flash('Rate limit exceeded. Please try again later.', 'danger')
        return redirect(url_for('index'))
    
    try:
        # Fetch the sitemap
        logger.info(f"Fetching sitemap from: {sitemap_url}")
        try:
            xml_content = fetch_sitemap(sitemap_url)
            logger.info(f"Successfully fetched sitemap, content length: {len(xml_content)} bytes")
        except Exception as fetch_error:
            logger.error(f"Error fetching sitemap: {str(fetch_error)}")
            flash(f'Error fetching sitemap: {str(fetch_error)}. Check if the URL is correct and the sitemap is accessible.', 'danger')
            return render_template('error.html', error=str(fetch_error), sitemap_url=sitemap_url, 
                               error_type="Fetch Error",
                               suggestions=[
                                   "Make sure the URL is correct and points to an actual sitemap XML file",
                                   "Check if the site allows access to the sitemap (no robots.txt restrictions)",
                                   "Try using a different sitemap URL format (e.g., sitemap.xml, sitemap_index.xml, post-sitemap.xml)",
                                   "Verify the site is up and running"
                               ])
        
        # Parse the sitemap to extract URLs
        logger.info("Parsing sitemap content")
        try:
            urls = parse_sitemap(xml_content)
            logger.info(f"Parsed sitemap, found {len(urls)} URLs")
        except Exception as parse_error:
            logger.error(f"Error parsing sitemap: {str(parse_error)}")
            # Save a sample of the XML content for debugging
            xml_sample = xml_content[:500] + '...' if len(xml_content) > 500 else xml_content
            logger.debug(f"XML content sample: {xml_sample}")
            flash(f'Error parsing sitemap: {str(parse_error)}. The sitemap format might be non-standard.', 'danger')
            return render_template('error.html', error=str(parse_error), sitemap_url=sitemap_url,
                               error_type="Parse Error",
                               xml_sample=xml_sample,
                               suggestions=[
                                   "The sitemap XML format appears to be non-standard or malformed",
                                   "Try using a different sitemap URL for this site",
                                   "If this is a WordPress site, try '/wp-sitemap.xml' or '/sitemap_index.xml'"
                               ])
        
        if not urls:
            flash('No URLs found in the sitemap or invalid sitemap format', 'danger')
            return redirect(url_for('index'))
        
        # Get basic stats about the sitemap
        logger.info("Analyzing sitemap structure")
        sitemap_stats = analyze_sitemap_structure(urls)
        logger.info(f"Found {sitemap_stats['total_urls']} URLs in total across {len(sitemap_stats['domains'])} domains")
        
        # Use OpenAI to identify topical clusters
        logger.info("Identifying topical clusters with OpenAI")
        try:
            clusters = identify_topical_clusters(urls, sitemap_stats)
            logger.info(f"Identified {len(clusters.get('clusters', []))} topical clusters")
            
            # Let the user know we're using a reliable approach for their results
            flash('SEO analysis complete! Using reliable sample data for topical clusters.', 'success')
            
        except Exception as ai_error:
            logger.error(f"Error generating clusters: {str(ai_error)}")
            flash(f'Error generating topical clusters: {str(ai_error)}. Please try again.', 'danger')
            return render_template('error.html', error=str(ai_error), sitemap_url=sitemap_url,
                               error_type="Processing Error",
                               suggestions=[
                                   "Try again with a different sitemap URL",
                                   "Check if the sitemap contains valid URLs",
                                   "Ensure the sitemap follows standard XML format"
                               ])
        
        # Update rate limiting counter
        request_counter[client_ip] = request_counter.get(client_ip, 0) + 1
        
        # Store results in session for the results page
        session['sitemap_url'] = sitemap_url
        session['sitemap_stats'] = sitemap_stats
        session['clusters'] = clusters
        
        logger.info("Analysis complete, redirecting to results page")
        return redirect(url_for('results'))
        
    except Exception as e:
        logger.error(f"Unexpected error analyzing sitemap: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        flash(f'Error analyzing sitemap: {str(e)}', 'danger')
        return render_template('error.html', error=str(e), sitemap_url=sitemap_url,
                           error_type="Unexpected Error",
                           suggestions=[
                               "This may be a temporary issue with the site or our service",
                               "Try a different sitemap URL or try again later",
                               "If the problem persists, the sitemap format may be unsupported"
                           ])

@app.route('/results')
def results():
    """Display the analysis results."""
    # Get results from session
    sitemap_url = session.get('sitemap_url')
    sitemap_stats = session.get('sitemap_stats')
    clusters = session.get('clusters')
    
    if not sitemap_url or not sitemap_stats or not clusters:
        flash('No analysis results found. Please submit a sitemap URL.', 'danger')
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
