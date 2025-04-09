import os
import json
import logging
import time
import requests
from openai import OpenAI
# Define error classes in case package doesn't have them
try:
    from openai import APITimeoutError, APIConnectionError, RateLimitError
except ImportError:
    # Define fallback error classes if not available
    class APITimeoutError(Exception): pass
    class APIConnectionError(Exception): pass
    class RateLimitError(Exception): pass

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user

logger = logging.getLogger(__name__)

# Initialize OpenAI client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY environment variable is not set")

# Configure with extended timeouts for deployed environments
openai = OpenAI(
    api_key=OPENAI_API_KEY,
    timeout=60.0,  # Longer timeout for API requests
    max_retries=3  # Automatic retries built into OpenAI client
)

def identify_topical_clusters(urls, sitemap_stats):
    """
    Use OpenAI to identify topical clusters in the sitemap URLs.
    
    Args:
        urls (list): List of URL dictionaries
        sitemap_stats (dict): Statistics about the sitemap structure
        
    Returns:
        dict: Top 5 topical clusters with counts and examples
    """
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
        
        # Call the OpenAI API
        response = openai.chat.completions.create(
            model="gpt-4o",
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
        raise Exception(f"Failed to parse OpenAI response: {str(e)}")
    
    except (APITimeoutError, APIConnectionError) as e:
        logger.error(f"OpenAI API connection error: {str(e)}")
        # Try fallback using a simpler prompt with fewer tokens
        try:
            logger.info("Attempting fallback with simpler prompt...")
            
            # Simplify prompt to reduce token count
            simplified_prompt = f"""
            Analyze this sitemap for {sitemap_stats['main_domain']} with {sitemap_stats['total_urls']} URLs.
            Group URLs into 5 topical clusters and provide a title, count, and 3 examples for each cluster.
            Format as JSON with clusters array containing title, count, examples[], and description fields.
            """
            
            # Retry with simplified prompt
            fallback_response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an SEO expert analyzing website sitemaps."},
                    {"role": "user", "content": simplified_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.5,
                max_tokens=1000
            )
            
            # Extract and parse the JSON response
            content = fallback_response.choices[0].message.content
            clusters_data = json.loads(content)
            
            # Basic validation and standardization of response
            if 'clusters' not in clusters_data:
                clusters_data = {'clusters': []}
                
            logger.info(f"Successfully processed fallback response with {len(clusters_data.get('clusters', []))} clusters")
            return clusters_data
            
        except Exception as fallback_error:
            logger.error(f"Fallback attempt also failed: {str(fallback_error)}")
            raise Exception(f"Could not connect to OpenAI API. Please check your internet connection and API key.")
    
    except RateLimitError as e:
        logger.error(f"OpenAI API rate limit exceeded: {str(e)}")
        raise Exception("OpenAI API rate limit exceeded. Please try again in a few minutes.")
    
    except Exception as e:
        logger.error(f"Error in OpenAI analysis: {str(e)}")
        raise Exception(f"Failed to analyze sitemap with OpenAI: {str(e)}")
