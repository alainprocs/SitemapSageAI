import os
import json
import logging
import time
import socket
import ssl
import sys
import re
import requests  # For HTTP requests

logger = logging.getLogger(__name__)

# Initialize OpenAI client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.critical("OPENAI_API_KEY environment variable is not set - cannot continue")
    
# Define error classes for OpenAI (used if import fails)
class APITimeoutError(Exception): pass
class APIConnectionError(Exception): pass
class RateLimitError(Exception): pass

# Import OpenAI and set up the client
client = None
try:
    # Import the OpenAI library
    from openai import OpenAI
    from openai.types.chat import ChatCompletion
    
    # Try to get specific error classes if available
    try:
        from openai import APITimeoutError as OAITimeoutError
        from openai import APIConnectionError as OAIConnectionError
        from openai import RateLimitError as OAIRateLimitError
        APITimeoutError = OAITimeoutError
        APIConnectionError = OAIConnectionError
        RateLimitError = OAIRateLimitError
    except ImportError:
        # Keep our generic ones defined above
        logger.warning("Could not import specific OpenAI error classes, using generic ones")
    
    # Initialize the OpenAI client with optimized settings
    if OPENAI_API_KEY and len(OPENAI_API_KEY) > 20:
        logger.info("Initializing OpenAI client with optimal settings")
        client = OpenAI(
            api_key=OPENAI_API_KEY,
            timeout=30.0,  # 30 second timeout to avoid hanging
            max_retries=2   # Built-in retries
        )
        
        logger.info("OpenAI client successfully initialized")
    else:
        logger.critical("Invalid OpenAI API key - application will not function correctly")
        # We still create a client but it won't work - the application will show a clear error
        client = None
        
except ImportError as e:
    logger.critical(f"Could not import the OpenAI library: {e}")
    client = None
except Exception as e:
    logger.critical(f"Fatal error setting up OpenAI: {e}")
    client = None

# No mock data functions - we exclusively use OpenAI for real analysis

def identify_topical_clusters(urls, sitemap_stats):
    """
    Analyze sitemap URLs to identify topical clusters using OpenAI.
    
    Args:
        urls (list): List of URL dictionaries
        sitemap_stats (dict): Statistics about the sitemap structure
        
    Returns:
        dict: Top 5 topical clusters with counts and examples
        
    Raises:
        RuntimeError: If the OpenAI client is not available or API calls fail
        ValueError: If the sitemap data is invalid
    """
    # Check if OpenAI client is available
    if not client:
        error_msg = "OpenAI client is not initialized - cannot perform analysis"
        logger.critical(error_msg)
        raise RuntimeError(f"OpenAI API is not available. Please check your API key and try again. Error: {error_msg}")
        
    if not OPENAI_API_KEY or len(OPENAI_API_KEY) < 20:
        error_msg = "Invalid OpenAI API key - cannot perform analysis"
        logger.critical(error_msg)
        raise RuntimeError(f"OpenAI API key is invalid or missing. Please provide a valid API key. Error: {error_msg}")
    
    # OpenAI analysis logic below
    logger.info(f"Starting OpenAI analysis of {len(urls[:100])} URLs from the sitemap")
    
    try:
        # Prepare the URL list for analysis
        # Limit to 100 URLs to avoid token limits
        url_list = [url.get('loc', '') for url in urls[:100] if 'loc' in url]
        
        if not url_list:
            raise ValueError("No valid URLs found in sitemap")
        
        # Create a prompt that instructs GPT to analyze the URLs and identify topical clusters
        prompt = f"""
        I need to analyze a website sitemap to identify the top 5 SEO topical clusters.
        
        Here are some details about the sitemap:
        - Total URLs: {sitemap_stats['total_urls']}
        - Main domain: {sitemap_stats['main_domain']}
        - Average path depth: {sitemap_stats['avg_depth']:.2f}
        
        Here's a sample of URLs from the sitemap (up to 100):
        {json.dumps(url_list, indent=2)}
        
        Based on SEO best practices and content organization:
        1. Identify the top 5 topical clusters present in this sitemap
        2. Count the approximate number of URLs that belong to each cluster
        3. List 3 example URLs for each cluster
        4. Provide a brief description of each cluster and its SEO significance
        5. Suggest a descriptive title for each cluster
        6. Suggest 5 engaging blog article ideas for each cluster that would be ideal for expanding the content in that topic area. Each suggestion should include a compelling headline and a brief description of what the article would cover.
        
        Respond with JSON in the following format:
        {{
            "clusters": [
                {{
                    "title": "Cluster title",
                    "description": "Brief description of this topical cluster",
                    "count": "Approximate number of URLs in this cluster",
                    "examples": ["example-url-1", "example-url-2", "example-url-3"],
                    "seo_significance": "Why this cluster is significant for SEO",
                    "article_ideas": [
                        {{
                            "headline": "Compelling article headline",
                            "description": "Brief description of the article content"
                        }},
                        // 4 more article ideas
                    ]
                }},
                // more clusters
            ]
        }}
        
        Only include the 5 most significant clusters ordered by importance. Ensure the article ideas are specific, relevant to the cluster topic, and designed to address potential content gaps or trending topics that would enhance SEO performance.
        """
        
        # Call the OpenAI API with retry logic
        max_retries = 3
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                # Log that we're using the real OpenAI API
                logger.info(f"Calling OpenAI API for analysis (attempt {attempt+1}/{max_retries})")
                
                # Call the OpenAI API
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",  # Use a more reliable model for this task
                    messages=[
                        {"role": "system", "content": "You are an SEO expert analyzing website sitemaps to identify topical clusters."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3,  # Lower temperature for more consistent results
                    max_tokens=1500,  # Slightly smaller response size
                    timeout=30  # 30 second timeout for faster response
                )
                
                # Extract and parse the JSON response
                content = response.choices[0].message.content
                clusters_data = json.loads(content)
                
                # Log success
                logger.info("Successfully received and parsed OpenAI response")
                
                # Ensure we have the correct structure and standardize number format
                if 'clusters' not in clusters_data or not isinstance(clusters_data['clusters'], list):
                    logger.warning(f"Invalid response structure from OpenAI. Missing 'clusters' list.")
                    clusters_data = {'clusters': []}
                
                # Process each cluster to standardize the format
                for cluster in clusters_data['clusters']:
                    # Ensure each cluster has all required fields
                    if 'title' not in cluster:
                        cluster['title'] = 'Unnamed Cluster'
                    
                    if 'count' not in cluster:
                        cluster['count'] = 0
                    
                    # Convert count to a number if it's a string
                    if isinstance(cluster['count'], str):
                        try:
                            # Extract numbers from strings like "~120" or "approximately 50"
                            import re
                            number_match = re.search(r'\d+', cluster['count'])
                            if number_match:
                                cluster['count'] = int(number_match.group())
                            else:
                                cluster['count'] = 0
                        except:
                            cluster['count'] = 0
                    
                    # Ensure examples is a list
                    if 'examples' not in cluster or not isinstance(cluster['examples'], list):
                        cluster['examples'] = []
                    
                    # Ensure description and seo_significance exist
                    if 'description' not in cluster:
                        cluster['description'] = 'No description provided'
                    
                    if 'seo_significance' not in cluster:
                        cluster['seo_significance'] = 'No SEO significance provided'
                        
                    # Ensure article_ideas exists and is properly formatted
                    if 'article_ideas' not in cluster or not isinstance(cluster['article_ideas'], list):
                        cluster['article_ideas'] = [
                            {
                                "headline": f"Article idea for {cluster['title']}",
                                "description": "Suggested content based on this topical cluster"
                            }
                        ] * 5  # Create 5 placeholder article ideas
                
                logger.info(f"Successfully processed {len(clusters_data['clusters'])} topical clusters")
                
                return clusters_data
                
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON response: {str(e)}")
                if attempt == max_retries - 1:
                    raise Exception(f"Failed to parse OpenAI response: {str(e)}")
            
            except (APITimeoutError, APIConnectionError, requests.exceptions.Timeout) as e:
                logger.error(f"OpenAI API connection error (attempt {attempt+1}): {str(e)}")
                if attempt == max_retries - 1:
                    # No fallback - propagate the error
                    logger.critical("All OpenAI API connection attempts failed")
                    raise RuntimeError(f"Failed to connect to OpenAI API after {max_retries} attempts: {str(e)}")
                time.sleep(retry_delay)
            
            except RateLimitError as e:
                logger.error(f"OpenAI API rate limit exceeded: {str(e)}")
                # No fallback - propagate the error
                raise RuntimeError(f"OpenAI API rate limit exceeded: {str(e)}")
            
            except Exception as e:
                logger.error(f"Error in OpenAI analysis (attempt {attempt+1}): {str(e)}")
                if attempt == max_retries - 1:
                    # No fallback - propagate the error
                    logger.critical("All OpenAI API requests failed")
                    raise RuntimeError(f"OpenAI API analysis failed: {str(e)}")
                time.sleep(retry_delay)
        
        # This should never be reached due to the returns in the retry loop
        logger.error("Unexpected code path in identify_topical_clusters")
        raise RuntimeError("Unexpected error in OpenAI processing")
        
    except Exception as e:
        logger.error(f"Unexpected error in identify_topical_clusters: {str(e)}")
        # No fallback - propagate the error
        raise RuntimeError(f"Error analyzing sitemap with OpenAI: {str(e)}")
