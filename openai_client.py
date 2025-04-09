import os
import json
import logging
from openai import OpenAI

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user

logger = logging.getLogger(__name__)

# Initialize OpenAI client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Validate API key format
if OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-") and len(OPENAI_API_KEY) > 20:
    openai = OpenAI(api_key=OPENAI_API_KEY)
else:
    logger.error(f"Invalid OpenAI API key format: {OPENAI_API_KEY[:5]}... (showing only prefix)")
    openai = None

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
        # Make sure we have a valid API key
        if not OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY environment variable is not set")
            raise ValueError("OpenAI API key not provided. Please set the OPENAI_API_KEY environment variable.")
            
        # Check if the client is initialized properly
        if openai is None:
            logger.error("OpenAI client is not properly initialized")
            raise ValueError("OpenAI client initialization failed. Please check your API key format.")
        
        # Prepare the URL list for analysis
        # Limit to 100 URLs to avoid token limits
        url_list = [url.get('loc', '') for url in urls[:200] if 'loc' in url]
        
        if not url_list:
            raise ValueError("No valid URLs found in sitemap")
        
        # Create a prompt that instructs GPT to analyze the URLs and identify topical clusters
        prompt = f"""
        I need to analyze a website sitemap to identify the top 5 SEO topical clusters.
        
        Here are some details about the sitemap:
        - Total URLs: {sitemap_stats['total_urls']}
        - Main domain: {sitemap_stats['main_domain']}
        - Average path depth: {sitemap_stats['avg_depth']:.2f}
        
        Here's a sample of URLs from the sitemap (up to 200):
        {json.dumps(url_list, indent=2)}
        
        Based on SEO best practices and content organization:
        1. Identify the top 5 topical clusters present in this sitemap
        2. Count the approximate number of URLs that belong to each cluster
        3. List 3 example URLs for each cluster
        4. Provide a brief description of each cluster and its SEO significance
        5. Suggest a descriptive title for each cluster
        
        Respond with JSON in the following format:
        {{
            "clusters": [
                {{
                    "title": "Cluster title",
                    "description": "Brief description of this topical cluster",
                    "count": "Approximate number of URLs in this cluster",
                    "examples": ["example-url-1", "example-url-2", "example-url-3"],
                    "seo_significance": "Why this cluster is significant for SEO"
                }},
                ...
            ]
        }}
        
        Only include the 5 most significant clusters ordered by importance.
        """
        
        # Call the OpenAI API to generate the analysis
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
        
        logger.info(f"Successfully processed {len(clusters_data['clusters'])} topical clusters")
        logger.debug(f"Processed clusters data: {json.dumps(clusters_data)}")
        
        return clusters_data
        
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON response: {str(e)}")
        logger.debug(f"Raw response: {content}")
        raise Exception("Invalid response format from OpenAI")
    
    except Exception as e:
        logger.error(f"Error in OpenAI analysis: {str(e)}")
        raise Exception(f"Failed to analyze sitemap with OpenAI: {str(e)}")

def generate_blog_recommendations(clusters):
    """
    Generate 3 blog post recommendations for each topical cluster based on SEO gaps.
    
    Args:
        clusters (dict): Dictionary containing clusters data
        
    Returns:
        dict: Updated clusters data with blog recommendations for each cluster
    """
    try:
        # Make sure we have a valid API key
        if not OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY environment variable is not set")
            raise ValueError("OpenAI API key not provided. Please set the OPENAI_API_KEY environment variable.")
            
        # Check if the client is initialized properly
        if openai is None:
            logger.error("OpenAI client is not properly initialized")
            raise ValueError("OpenAI client initialization failed. Please check your API key format.")
        
        updated_clusters = clusters.copy()
        
        # Process each cluster to add blog recommendations
        for cluster in updated_clusters['clusters']:
            cluster_title = cluster['title']
            cluster_description = cluster['description']
            example_urls = cluster['examples']
            
            # Create a prompt for blog recommendations
            prompt = f"""
            I need to generate 3 strategic blog post ideas for a topical cluster on a website.

            Cluster title: {cluster_title}
            Cluster description: {cluster_description}
            Current URLs in this cluster:
            {json.dumps(example_urls, indent=2)}
            
            Please suggest 3 blog post ideas that:
            1. Fill gaps in the current content
            2. Target valuable SEO keywords related to this topic
            3. Complement the existing content without duplicating it
            4. Are specific, actionable, and have clear value for the audience
            5. Follow best SEO practices for content creation
            
            For each blog post idea, provide:
            1. An SEO-optimized title (65 characters max)
            2. A brief description of what the post should cover
            3. The main SEO benefit of publishing this content
            
            Respond with JSON in the following format:
            {{
                "recommendations": [
                    {{
                        "title": "Blog post title",
                        "description": "What this post should cover",
                        "seo_benefit": "The main SEO benefit"
                    }},
                    ...
                ]
            }}
            
            Ensure the recommendations are highly relevant to the specific cluster.
            """
            
            # Call the OpenAI API to generate recommendations
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an SEO content strategist helping website owners identify gaps in their content."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=1000
            )
            
            # Extract and parse the JSON response
            content = response.choices[0].message.content
            recommendations_data = json.loads(content)
            
            # Add recommendations to the cluster
            if 'recommendations' in recommendations_data and isinstance(recommendations_data['recommendations'], list):
                cluster['blog_recommendations'] = recommendations_data['recommendations']
            else:
                cluster['blog_recommendations'] = []
            
        logger.info(f"Successfully generated blog recommendations for {len(updated_clusters['clusters'])} clusters")
        return updated_clusters
        
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON response for blog recommendations: {str(e)}")
        logger.debug(f"Raw response: {content}")
        raise Exception("Invalid response format from OpenAI")
    
    except Exception as e:
        logger.error(f"Error generating blog recommendations: {str(e)}")
        raise Exception(f"Failed to generate blog recommendations: {str(e)}")
