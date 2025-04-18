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
    Analyze sitemap URLs to identify topical clusters using OpenAI, supporting batching and model selection for large sitemaps.
    Args:
        urls (list): List of URL dictionaries
        sitemap_stats (dict): Statistics about the sitemap structure
    Returns:
        dict: Aggregated topical clusters across all URLs
    """
    import difflib
    import re
    logger.info("Using OpenAI API for topical cluster analysis with batching support")
    global client
    if client:
        try:
            client.timeout = 180.0
            logger.info("Set OpenAI client timeout to 180 seconds for large sitemap processing")
        except Exception as e:
            logger.warning(f"Could not set timeout on existing client: {str(e)}")

    # Try to use gpt-4o-mini as preferred model
    models_to_try = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"]
    # Use the first model in the list (assuming all are available)
    model = models_to_try[0]
    logger.info(f"Using {model} for analysis")

    # Larger batches for faster processing
    batch_size = 100  # Use 100 URLs per batch for all models
    url_list = [url.get('loc', '') for url in urls if 'loc' in url]
    total_urls = len(url_list)
    if not url_list:
        raise ValueError("No valid URLs found in sitemap")
    logger.info(f"Processing {total_urls} URLs in batches of {batch_size} using model {model}")

    # Dynamic number of clusters based on total_urls
    n_clusters = min(15, max(5, round(total_urls / 30)))
    logger.info(f"Targeting {n_clusters} topical clusters based on total URL count")

    # Helper: merge clusters by fuzzy title match
    def merge_clusters(agg, new_clusters):
        for new in new_clusters:
            matched = None
            for agg_cl in agg:
                ratio = difflib.SequenceMatcher(None, agg_cl['title'].lower(), new['title'].lower()).ratio()
                if ratio > 0.8:
                    matched = agg_cl
                    break
            if matched:
                matched['count'] += new.get('count', 0)
                matched['examples'] = list(set(matched['examples'] + new.get('examples', [])))[:5]
                matched['article_ideas'] = (matched.get('article_ideas', []) + new.get('article_ideas', []))[:10]
            else:
                agg.append(new)
        return agg

    # Batch processing
    all_clusters = []
    for i in range(0, total_urls, batch_size):
        batch_urls = url_list[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size+1}: URLs {i+1}-{i+len(batch_urls)}")
        prompt = f"""
        Analyze the following sitemap URLs and identify up to {n_clusters} of the most significant SEO topical clusters.\n\nSitemap details:\n- Total URLs: {total_urls}\n- Main domain: {sitemap_stats['main_domain']}\n- Average path depth: {sitemap_stats['avg_depth']:.2f}\n\nURLs:\n{json.dumps(batch_urls, indent=2)}\n\nInstructions:\n1. Identify up to {n_clusters} of the most significant topical clusters in this batch.\n2. For each cluster, include exactly these JSON fields: "title" (string), "description" (string), "count" (integer), "examples" (array of 3 example sitemap URLs as strings), "seo_significance" (string), and "article_ideas" (array of 5 objects each with "headline" and "description").\n3. Respond ONLY with valid JSON matching schema: {{"clusters": [/* array of cluster objects */]}}.\n4. Do NOT include any additional keys, explanations, or commentary.\n5. If you cannot fit all clusters, prioritize the most significant and include only up to {n_clusters} clusters.\n"""
        # Retry logic


        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are an SEO expert analyzing website sitemaps to identify topical clusters. Respond ONLY with valid JSON, no explanations or commentary."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.5,
                    max_tokens=2000
                )
                content = response.choices[0].message.content
                clusters_data = json.loads(content)
                clusters = clusters_data.get('clusters', [])
                # Standardize/clean up clusters
                for cluster in clusters:
                    # Title
                    if 'title' not in cluster:
                        cluster['title'] = 'Unnamed Cluster'
                    # Count
                    if 'count' not in cluster:
                        cluster['count'] = 0
                    if isinstance(cluster['count'], str):
                        number_match = re.search(r'\d+', cluster['count'])
                        if number_match:
                            cluster['count'] = int(number_match.group())
                        else:
                            cluster['count'] = 0
                    # Extract example URLs or fallback to sitemap URLs
                    raw_examples = []
                    for key, val in cluster.items():
                        if key.lower().startswith('example') and isinstance(val, list):
                            for item in val:
                                if isinstance(item, str):
                                    raw_examples.append(item)
                                elif isinstance(item, dict):
                                    url = item.get('url') or item.get('loc')
                                    if isinstance(url, str):
                                        raw_examples.append(url)
                            break
                    # Use API examples if available, otherwise first 3 sitemap URLs
                    choices = raw_examples if raw_examples else url_list[:3]
                    # Deduplicate and limit to 3
                    cluster['examples'] = list(dict.fromkeys(choices))[:3]
                    # Description/SEO significance
                    if 'description' not in cluster:
                        cluster['description'] = 'No description provided'
                    if 'seo_significance' not in cluster:
                        cluster['seo_significance'] = 'No SEO significance provided'
                    # Article ideas
                    if 'article_ideas' not in cluster or not isinstance(cluster['article_ideas'], list):
                        cluster['article_ideas'] = [
                            {"headline": f"Article idea for {cluster['title']}", "description": "Suggested content based on this topical cluster"}
                        ] * 5
                all_clusters = merge_clusters(all_clusters, clusters)
                logger.info(f"Batch {i//batch_size+1}: Processed {len(clusters)} clusters, total aggregated: {len(all_clusters)}")
                break  # Success, no retry needed
            except json.JSONDecodeError as json_error:
                logger.error(f"JSON parsing error in batch {i//batch_size+1}: {str(json_error)}")
                # Retry with a smaller batch if possible
                if len(batch_urls) > 5:
                    new_batch_size = max(5, len(batch_urls) // 2)
                    logger.info(f"Retrying batch {i//batch_size+1} with smaller batch size: {new_batch_size}")
                    batch_urls = batch_urls[:new_batch_size]
                    continue
                if attempt < max_retries - 1:
                    logger.info(f"Retrying batch {i//batch_size+1} in 5 seconds...")
                    time.sleep(5)
                else:
                    logger.error("Maximum retries reached for JSON parsing error in batch")
                    raise Exception(f"Failed to parse OpenAI response as JSON: {str(json_error)}")
            except Exception as api_error:
                logger.error(f"OpenAI API error in batch {i//batch_size+1}: {str(api_error)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying batch {i//batch_size+1} in 5 seconds...")
                    time.sleep(5)
                else:
                    logger.error("Maximum retries reached for API error in batch")
                    raise Exception(f"OpenAI API error after {max_retries} attempts: {str(api_error)}")
    # Sort clusters by count and return the top n_clusters
    all_clusters.sort(key=lambda c: c.get('count', 0), reverse=True)
    logger.info(f"Returning {min(n_clusters, len(all_clusters))} clusters (topical aggregation complete)")
    return {"clusters": all_clusters[:n_clusters]}
