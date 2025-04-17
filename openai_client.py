import os
import json
import logging
import time
import requests
import random
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# Initialize OpenAI client
# Force reload environment variables to ensure we get the latest values
load_dotenv(override=True)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY environment variable is not set")
    OPENAI_API_KEY = None  # Ensure it's explicitly None if not found
else:
    # Log the first few characters of the key for debugging
    key_start = OPENAI_API_KEY[:8] + "..." if OPENAI_API_KEY else "None"
    logger.info(f"Found API key starting with: {key_start}")

# Define error classes for exception handling
try:
    # Try to import the OpenAI error classes directly
    from openai.error import APITimeoutError, APIConnectionError, RateLimitError
except ImportError:
    # Fallback definitions if imports fail
    class APITimeoutError(Exception): pass
    class APIConnectionError(Exception): pass
    class RateLimitError(Exception): pass

# Initialize the OpenAI client
try:
    from openai import OpenAI
    
    if not OPENAI_API_KEY:
        logger.error("No OpenAI API key available. Cannot initialize client.")
        client = None
    else:
        # Print the API key type for debugging
        logger.info(f"API key type: {type(OPENAI_API_KEY)}, Length: {len(OPENAI_API_KEY)}")
        
        # Create the client with minimal options first
        client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {str(e)}")
    client = None

def test_openai_connection():
    """
    Test the OpenAI API connection with a simple request.
    
    Returns:
        bool: True if connection successful, raises an exception otherwise
    """
    if not OPENAI_API_KEY:
        raise Exception("OpenAI API key not set in environment")
        
    if not client:
        raise Exception("OpenAI client not initialized")
    
    # Allow any key starting with 'sk-' including 'sk-proj-'
    if not OPENAI_API_KEY.startswith('sk-'):
        raise Exception(f"Invalid OpenAI API key format. Key should start with 'sk-'")
    
    try:
        logger.info("Testing OpenAI API connection")
        # Make a simple request to test the connection
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Using a more widely available model for testing
            messages=[{"role": "user", "content": "Hello, this is a test"}],
            max_tokens=5
        )
        logger.info("OpenAI API connection test successful")
        return True
    except Exception as e:
        logger.error(f"OpenAI API connection test failed: {str(e)}")
        raise Exception(f"Could not connect to OpenAI API: {str(e)}")

def identify_topical_clusters(urls, sitemap_stats):
    """
    Analyze sitemap URLs to identify topical clusters using OpenAI.
    
    Args:
        urls (list): List of URL dictionaries
        sitemap_stats (dict): Statistics about the sitemap structure
        
    Returns:
        dict: Top 5 topical clusters with counts and examples
    """
    logger.info("Using OpenAI API for topical cluster analysis")
    
    # Set a longer timeout for the OpenAI client
    global client
    # Reinitialize the client with a longer timeout for this specific operation
    if client:
        try:
            client.timeout = 180.0  # 3 minutes timeout
            logger.info(f"Set OpenAI client timeout to 180 seconds for large sitemap processing")
        except Exception as e:
            logger.warning(f"Could not set timeout on existing client: {str(e)}")
    
    try:
        # Prepare the URL list for analysis
        # Limit to 100 URLs to avoid token limits
        url_list = [url.get('loc', '') for url in urls[:100] if 'loc' in url]
        
        if not url_list:
            raise ValueError("No valid URLs found in sitemap")
        
        # Create a more focused prompt that instructs GPT to analyze the URLs and identify topical clusters
        prompt = f"""
        I need a quick analysis of this website sitemap to identify the top 5 SEO topical clusters.
        
        Here are some details about the sitemap:
        - Total URLs: {sitemap_stats['total_urls']}
        - Main domain: {sitemap_stats['main_domain']}
        - Average path depth: {sitemap_stats['avg_depth']:.2f}
        
        Here's a sample of URLs from the sitemap (up to 40):
        {json.dumps(url_list[:40], indent=2)}
        
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
                # Call the OpenAI API with a longer timeout
                logger.info(f"Calling OpenAI API for analysis (attempt {attempt+1}/{max_retries})")
                
                # Use a simpler model for faster processing
                model = "gpt-3.5-turbo"
                logger.info(f"Using model: {model} for faster processing")
                
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are an SEO expert analyzing website sitemaps to identify topical clusters."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.5,
                    max_tokens=2000
                )
                
                # Extract and parse the JSON response
                content = response.choices[0].message.content
                clusters_data = json.loads(content)
                
                # Log success
                logger.info("Successfully received and parsed OpenAI response")
                
                # Ensure we have the correct structure
                if 'clusters' not in clusters_data or not isinstance(clusters_data['clusters'], list):
                    logger.warning("Invalid response structure from OpenAI. Missing 'clusters' list.")
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
                
                # Return the processed clusters data
                return clusters_data
                
            except json.JSONDecodeError as json_error:
                logger.error(f"JSON parsing error: {str(json_error)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error("Maximum retries reached for JSON parsing error")
                    raise Exception(f"Failed to parse OpenAI response as JSON: {str(json_error)}")
                    
            except Exception as api_error:
                logger.error(f"OpenAI API error: {str(api_error)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error("Maximum retries reached for API error")
                    raise Exception(f"OpenAI API error after {max_retries} attempts: {str(api_error)}")
    
    except Exception as e:
        logger.error(f"Error in identify_topical_clusters: {str(e)}")
        raise Exception(f"Failed to identify topical clusters: {str(e)}")
