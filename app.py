import os
import logging
import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import uuid
import threading
from sitemap_analyzer import fetch_sitemap, parse_sitemap, analyze_sitemap_structure
from openai_client import identify_topical_clusters, test_openai_connection
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# File handler for error logs (ensure directory exists)
import os
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug.log')
file_handler = logging.FileHandler(log_file, mode='a')
file_handler.setLevel(logging.DEBUG)  # Log all levels
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)
logger.info(f"Logging to {log_file}")

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default-secret-key-for-development")

# Rate limiting variables
MAX_REQUESTS_PER_HOUR = 10
request_counter = {}

# In-memory job store: {job_id: {status: 'pending'|'done'|'error', result:..., error:...}}
jobs = {}

@app.route('/')
def index():
    """Render the main page with the sitemap URL input form."""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    # Generate a unique job_id
    job_id = str(uuid.uuid4())
    jobs[job_id] = {'status': 'pending', 'result': None, 'error': None}
    sitemap_url = request.form.get('sitemap_url', '').strip()
    def run_analysis():
        try:
            # Normalize URL - add https:// if missing
            normalized_url = sitemap_url
            if not normalized_url.startswith(('http://', 'https://')):
                normalized_url = 'https://' + normalized_url
                logger.info(f"Added https:// prefix, URL is now: {normalized_url}")
            
            logger.info(f"Starting analysis for job {job_id} with URL {normalized_url}")
            try:
                xml_content = fetch_sitemap(normalized_url)
                logger.info(f"Fetched sitemap: {len(xml_content)} bytes")
            except Exception as e:
                logger.error(f"Error fetching sitemap: {str(e)}", exc_info=True)
                jobs[job_id]['error'] = f"Error fetching sitemap: {str(e)}"
                jobs[job_id]['status'] = 'error'
                return

            try:
                urls = parse_sitemap(xml_content)
                logger.info(f"Parsed sitemap: {len(urls)} URLs found")
            except Exception as e:
                logger.error(f"Error parsing sitemap: {str(e)}", exc_info=True)
                jobs[job_id]['error'] = f"Error parsing sitemap: {str(e)}"
                jobs[job_id]['status'] = 'error'
                return

            try:
                sitemap_stats = analyze_sitemap_structure(urls)
                logger.info(f"Analyzed sitemap structure: {sitemap_stats['total_urls']} URLs")
            except Exception as e:
                logger.error(f"Error analyzing sitemap structure: {str(e)}", exc_info=True)
                jobs[job_id]['error'] = f"Error analyzing sitemap structure: {str(e)}"
                jobs[job_id]['status'] = 'error'
                return

            try:
                clusters = identify_topical_clusters(urls, sitemap_stats)
                logger.info(f"Identified clusters: {len(clusters.get('clusters', []))} clusters found")
            except Exception as e:
                logger.error(f"Error identifying clusters: {str(e)}", exc_info=True)
                jobs[job_id]['error'] = f"Error identifying clusters: {str(e)}"
                jobs[job_id]['status'] = 'error'
                return

            # Store the results
            jobs[job_id]['result'] = {'clusters': clusters, 'sitemap_url': sitemap_url, 'sitemap_stats': sitemap_stats}
            jobs[job_id]['status'] = 'done'
            logger.info(f"Job {job_id} completed successfully")
        except Exception as e:
            logger.error(f"Unexpected error in background job {job_id}: {str(e)}", exc_info=True)
            jobs[job_id]['error'] = f"Unexpected error: {str(e)}"
            jobs[job_id]['status'] = 'error'
    threading.Thread(target=run_analysis).start()
    return redirect(url_for('loading', job_id=job_id))

@app.route('/loading')
def loading():
    job_id = request.args.get('job_id')
    return render_template('loading.html', job_id=job_id)

@app.route('/analyze_status')
def analyze_status():
    job_id = request.args.get('job_id')
    job = jobs.get(job_id)
    if not job:
        return jsonify({'status': 'not_found'})
    return jsonify({'status': job['status']})

@app.route('/results')
def results():
    job_id = request.args.get('job_id')
    if not job_id:
        logger.error("No job_id provided to /results")
        return render_template('error.html', error_msg='No job ID provided.', 
                            error_details="Please return to the home page and try again.")
    
    job = jobs.get(job_id)
    if not job:
        logger.error(f"Job not found: {job_id}")
        return render_template('error.html', error_msg='Job not found.', 
                            error_details=f"The job ID {job_id} was not found in our system. It may have expired or been removed.")
    
    if job['status'] == 'error':
        error = job['error']
        logger.error(f"Job error: {job_id} - {error}")
        return render_template('error.html', error_msg='Analysis Error', 
                            error_details=error)
    
    if job['status'] != 'done':
        logger.info(f"Job not ready, redirecting to loading: {job_id} - {job['status']}")
        return redirect(url_for('loading', job_id=job_id))
    
    try:
        clusters = job['result']['clusters']
        sitemap_url = job['result']['sitemap_url']
        sitemap_stats = job['result']['sitemap_stats']
        logger.info(f"Rendering results for job {job_id}: {len(clusters.get('clusters', []))} clusters")
        return render_template('results.html', clusters=clusters, sitemap_url=sitemap_url, sitemap_stats=sitemap_stats)
    except Exception as e:
        logger.error(f"Error rendering results for job {job_id}: {str(e)}", exc_info=True)
        return render_template('error.html', error_msg='Error Rendering Results', 
                            error_details=f"An error occurred while rendering the results: {str(e)}")
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable is not set")
        flash('Error: OpenAI API key not found. Please set OPENAI_API_KEY in your .env file.', 'error')
        return render_template('index.html')
    
    # Verify the API key format (simplify to just check for 'sk-' prefix)
    if not api_key.startswith('sk-'):
        logger.error("Invalid OpenAI API key format")
        flash('Error: Invalid OpenAI API key format. Key should start with sk-', 'error')
        return render_template('index.html')
    
    logger.info("API key validation passed")

    # Show loading screen while processing
    if request.method == 'POST':
        sitemap_url = request.form.get('sitemap_url')
        if not sitemap_url:
            flash('Please enter a sitemap URL.', 'error')
            return render_template('index.html')
        # Render the loading screen and continue processing in the background
        # (for demo: process synchronously, but show loading page)
        # In production, use background jobs/celery for async
        from flask import copy_current_request_context
        import threading
        
        @copy_current_request_context
        def process_and_redirect():
            try:
                xml_content = fetch_sitemap(sitemap_url)
                urls = parse_sitemap(xml_content)
                sitemap_stats = analyze_sitemap_structure(urls)
                clusters = identify_topical_clusters(urls, sitemap_stats)
                # Store results in session or cache
                session['clusters'] = clusters
                session['sitemap_url'] = sitemap_url
                session['sitemap_stats'] = sitemap_stats
            except Exception as e:
                logger.error(f"Error during analysis: {e}")
                session['error'] = str(e)

        t = threading.Thread(target=process_and_redirect)
        t.start()
        return render_template('loading.html')
    
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
        
        # Test OpenAI API connection first before starting analysis
        logger.info("Testing OpenAI API connection")
        try:
            test_openai_connection()
            logger.info("OpenAI API connection test successful")
        except Exception as api_test_error:
            logger.error(f"OpenAI API connection test failed: {str(api_test_error)}")
            flash(f"OpenAI API connection error: {str(api_test_error)}. Please verify your API key and connection.", 'danger')
            return render_template('index.html')
        
        # Get topical clusters using OpenAI API exclusively
        logger.info("Identifying topical clusters with OpenAI API (NO mock data)")
        try:
            # Use the OpenAI API directly - simpler and more reliable approach
            logger.info("Making OpenAI API call to analyze sitemap content")
            clusters = identify_topical_clusters(urls, sitemap_stats)
            logger.info(f"Identified {len(clusters.get('clusters', []))} topical clusters")
            
            # Tell user their results are ready
            flash('SEO analysis complete! Your topical cluster results are ready.', 'success')
            
        except Exception as ai_error:
            logger.error(f"Error generating clusters: {str(ai_error)}")
            logger.error("OpenAI API error - no fallback available")
            
            # No fallback to mock data - just show the error and return to the index page
            flash(f"OpenAI API error: {str(ai_error)}. Please verify your API key and try again.", 'danger')
            return render_template('index.html')
        
        # Update rate limiting counter
        request_counter[client_ip] = request_counter.get(client_ip, 0) + 1
        
        # Generate a unique key for this analysis based on IP and sitemap URL
        import hashlib
        cache_key = hashlib.md5(f"{client_ip}:{sitemap_url}".encode()).hexdigest()
        
        # Store results in server-side cache instead of session cookie
        results_cache[cache_key] = {
            'clusters': clusters,
            'sitemap_url': sitemap_url,
            'sitemap_stats': sitemap_stats,
            'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'timestamp': time.time()
        }
        
        # Store only the cache key in session
        session['results_cache_key'] = cache_key
        
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


    # Extract data from cache
    clusters = cached_data.get('clusters', {})
    sitemap_url = cached_data.get('sitemap_url', '')
    sitemap_stats = cached_data.get('sitemap_stats', {})
    analysis_time = cached_data.get('analysis_time', '')
    
    return render_template('results.html', 
                           clusters=clusters, 
                           sitemap_url=sitemap_url,
                           sitemap_stats=sitemap_stats,
                           analysis_time=analysis_time)

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template('error.html', error='Page not found'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    error_message = str(e)
    if "openai" in error_message.lower() or "api" in error_message.lower():
        error_message = "OpenAI API connection error. The API key may be invalid or there may be network connectivity issues."
        suggestions = [
            "Check that your OpenAI API key is valid and has sufficient credits",
            "Verify internet connectivity to the OpenAI API servers",
            "Try again later as OpenAI API may be experiencing temporary issues",
            "Check if there are any rate limits or quota issues with your OpenAI account"
        ]
    else:
        error_message = "Internal server error occurred."
        suggestions = [
            "Try refreshing the page or submitting your request again",
            "Check your sitemap URL and make sure it's valid",
            "Try a different sitemap URL",
            "If the problem persists, please try again later"
        ]
    
    return render_template('error.html', error=error_message, 
                          error_type="Server Error", 
                          suggestions=suggestions), 500

if __name__ == '__main__':
    # Delete any existing log file to start fresh
    try:
        os.remove(log_file)
        logger.info(f"Removed existing log file: {log_file}")
    except OSError:
        pass
    port = int(os.environ.get('PORT', 5001))
    logger.info(f"Starting Flask application on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
