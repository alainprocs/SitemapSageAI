import os
import re
import logging
from collections import defaultdict, Counter
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, flash, session
from sitemap_analyzer import fetch_sitemap, parse_sitemap, analyze_sitemap_structure, extract_path_components
from openai_client import identify_topical_clusters, generate_blog_recommendations

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
    sitemap_url = request.form.get('sitemap_url', '').strip()
    
    if not sitemap_url:
        flash('Please enter a sitemap URL', 'danger')
        return redirect(url_for('index'))
    
    logger.info(f"Analyzing sitemap URL: {sitemap_url}")
    
    # Check if URL starts with http:// or https://
    if not sitemap_url.startswith(('http://', 'https://')):
        sitemap_url = 'https://' + sitemap_url
        logger.info(f"Added https:// prefix, URL is now: {sitemap_url}")
    
    # If URL doesn't end with .xml or doesn't contain sitemap, it might be just the domain
    # Try to append common WordPress sitemap paths
    from urllib.parse import urlparse
    parsed_url = urlparse(sitemap_url)
    is_domain_only = not parsed_url.path or parsed_url.path == '/'
    is_not_sitemap = not (parsed_url.path.endswith('.xml') or 'sitemap' in parsed_url.path.lower())
    
    if is_domain_only or is_not_sitemap:
        # Save original URL in case we need to fall back
        original_url = sitemap_url
        
        # WordPress sitemap formats to try in order of preference
        wp_sitemap_formats = [
            "/sitemap_index.xml",      # Standard WordPress sitemap index
            "/wp-sitemap.xml",         # WordPress core sitemap
            "/sitemap.xml",            # Common default name
            "/post-sitemap.xml",       # Yoast SEO format
            "/page-sitemap.xml"        # Yoast SEO format for pages
        ]
        
        # Try to get a base domain without path
        base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        for sitemap_format in wp_sitemap_formats:
            test_url = base_domain + sitemap_format
            logger.info(f"Trying WordPress sitemap format: {test_url}")
            try:
                # Just attempt to fetch, don't need to parse yet
                test_content = fetch_sitemap(test_url)
                # Check for either XML sitemap patterns or HTML containing links to sitemaps
                if (test_content and ('<urlset' in test_content or '<sitemapindex' in test_content)) or \
                   (test_content and '<!DOCTYPE html>' in test_content and ('wp-sitemap' in test_content or 'sitemap_index' in test_content)):
                    sitemap_url = test_url
                    logger.info(f"Found valid WordPress sitemap at: {sitemap_url}")
                    break
            except Exception as e:
                logger.debug(f"No valid sitemap found at {test_url}: {str(e)}")
                continue
    
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
            flash('No URLs found in the sitemap or invalid sitemap format', 'warning')
            return redirect(url_for('index'))
        
        # Get basic stats about the sitemap
        logger.info("Analyzing sitemap structure")
        sitemap_stats = analyze_sitemap_structure(urls)
        logger.info(f"Found {sitemap_stats['total_urls']} URLs in total across {len(sitemap_stats['domains'])} domains")
        
        # Create basic clusters from the URL structure without using OpenAI
        basic_clusters = create_basic_clusters_from_urls(urls)
        
        # Check if OpenAI API key is available, but continue with basic analysis if not
        if not os.environ.get("OPENAI_API_KEY"):
            logger.warning("OPENAI_API_KEY environment variable is not set, using basic analysis")
            flash('Working in limited mode without AI analysis. For AI-powered analysis, please configure an OpenAI API key.', 'warning')
            # Continue with basic clusters
            clusters = basic_clusters
        else:
            # Only attempt to use OpenAI if we have an API key
            logger.info("Identifying topical clusters with OpenAI")
            try:
                clusters = identify_topical_clusters(urls, sitemap_stats)
                logger.info(f"Identified {len(clusters['clusters'])} topical clusters")
                
                # Generate blog post recommendations for each cluster
                logger.info("Generating blog post recommendations for each cluster")
                try:
                    clusters_with_recommendations = generate_blog_recommendations(clusters)
                    clusters = clusters_with_recommendations
                except Exception as rec_error:
                    logger.error(f"Error generating blog recommendations: {str(rec_error)}")
                    # If recommendations fail, we can still continue with clusters only
                    flash('Blog recommendations could not be generated, but clusters analysis is available.', 'warning')
                    # Add empty recommendations to each cluster
                    for cluster in clusters['clusters']:
                        cluster['blog_recommendations'] = []
                        
            except Exception as ai_error:
                logger.error(f"Error in AI processing: {str(ai_error)}")
                flash(f'Error identifying topical clusters: {str(ai_error)}. Check API key and try again.', 'danger')
                # Fall back to basic clusters instead of showing an error
                logger.info("Falling back to basic clusters after OpenAI error")
                clusters = basic_clusters
        
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

def create_basic_clusters_from_urls(urls):
    """
    Create basic topic clusters from URL patterns without using AI.
    This is used as a fallback when OpenAI API is not available.
    
    Args:
        urls (list): List of URL dictionaries from the sitemap
        
    Returns:
        dict: Dictionary with basic clusters based on URL patterns
    """
    logger.info("Creating basic clusters from URL patterns (no AI)")
    
    # Extract path components for analysis
    path_components = []
    for url_data in urls:
        url = url_data.get('loc', '')
        if url:
            components = extract_path_components(url)
            if components:
                path_components.append(components)
    
    # Count the most common first-level path components
    first_level_paths = [comp[0] for comp in path_components if comp]
    common_paths = Counter(first_level_paths).most_common(7)  # Get top 7 most common paths
    
    # Filter out common non-content paths
    filtered_paths = [
        (path, count) for path, count in common_paths 
        if path not in ['tag', 'wp-content', 'wp-includes', 'wp-admin', 'category', 'feed', 'author']
    ]
    
    # Additional potential topic identifiers in URLs
    content_patterns = [
        ('recipe', 'Recipes'),
        ('food', 'Food Content'),
        ('health', 'Health & Wellness'),
        ('review', 'Reviews'),
        ('guide', 'Guides & Tutorials'),
        ('how-to', 'How-To Content'),
        ('news', 'News Articles'),
        ('blog', 'Blog Posts'),
        ('product', 'Product Pages'),
        ('service', 'Services'),
        ('category', 'Categories')
    ]
    
    # Collect URLs by path or pattern
    url_clusters = defaultdict(list)
    
    # First, group by common first-level paths
    for url_data in urls:
        url = url_data.get('loc', '')
        if not url:
            continue
            
        components = extract_path_components(url)
        if not components:
            continue
            
        # Try to match with a first-level path
        if components[0] in [p[0] for p in filtered_paths]:
            url_clusters[components[0]].append(url)
            continue
        
        # Try to find content pattern matches
        matched = False
        for pattern, _ in content_patterns:
            if any(pattern in comp.lower() for comp in components):
                url_clusters[pattern].append(url)
                matched = True
                break
                
        # If no matches found, check for date patterns (YYYY/MM) which often indicate blog posts
        if not matched and len(components) >= 2:
            if re.match(r'\d{4}', components[0]) and (len(components) == 1 or re.match(r'\d{2}', components[1])):
                url_clusters['blog'].append(url)
                continue
                
        # As a fallback, put in a general content category
        if not matched:
            url_clusters['general'].append(url)
    
    # Create cluster objects
    clusters = {'clusters': []}
    
    # For each cluster, create a proper cluster object
    for cluster_key, urls_in_cluster in url_clusters.items():
        if len(urls_in_cluster) < 3:  # Skip tiny clusters
            continue
            
        # Determine a user-friendly title
        title = None
        for pattern, friendly_name in content_patterns:
            if pattern == cluster_key:
                title = friendly_name
                break
                
        if not title:
            # Capitalize and clean up the key
            title = cluster_key.replace('-', ' ').replace('_', ' ').title() + " Content"
        
        # Create cluster object
        cluster = {
            'title': title,
            'description': f"Content related to {title.lower()}",
            'count': len(urls_in_cluster),
            'examples': urls_in_cluster[:3],  # First 3 examples
            'seo_significance': f"This content group represents {len(urls_in_cluster)} pages on your site and may be significant for SEO.",
            'blog_recommendations': []  # Empty recommendations as this is AI-powered
        }
        
        clusters['clusters'].append(cluster)
    
    # Sort clusters by count (most URLs first)
    clusters['clusters'].sort(key=lambda x: x['count'], reverse=True)
    
    # Limit to top 5 clusters
    clusters['clusters'] = clusters['clusters'][:5]
    
    logger.info(f"Created {len(clusters['clusters'])} basic clusters without using AI")
    return clusters


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
