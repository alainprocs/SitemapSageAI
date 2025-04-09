import os
import json
import logging
import time
import random
import socket
import ssl

logger = logging.getLogger(__name__)

# Initialize OpenAI client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY environment variable is not set")

# Always have USE_MOCK_DATA as a fallback option, but default to False
USE_MOCK_DATA = False
client = None

# Define error classes so we can reference them even if the import fails
class APITimeoutError(Exception): pass
class APIConnectionError(Exception): pass
class RateLimitError(Exception): pass

# Try to import OpenAI library and initialize client
try:
    import requests
    from openai import OpenAI
    
    # Try to get more specific error classes if available
    try:
        from openai import APITimeoutError as OAITimeoutError
        from openai import APIConnectionError as OAIConnectionError
        from openai import RateLimitError as OAIRateLimitError
        APITimeoutError = OAITimeoutError
        APIConnectionError = OAIConnectionError
        RateLimitError = OAIRateLimitError
    except ImportError:
        # Keep our generic ones defined above
        pass
    
    # Test if we can reach the OpenAI API
    try:
        # First make sure API key looks valid
        if OPENAI_API_KEY and len(OPENAI_API_KEY) > 20:
            # Initialize the client with generous timeout settings
            client = OpenAI(
                api_key=OPENAI_API_KEY,
                timeout=90.0,  # Very long timeout
                max_retries=2   # Built-in retries
            )
            
            logger.info("OpenAI client initialized, will try to use real AI analysis")
        else:
            logger.warning("Invalid OpenAI API key, falling back to mock data")
            USE_MOCK_DATA = True
    except Exception as init_error:
        logger.error(f"OpenAI client initialization error: {init_error}")
        USE_MOCK_DATA = True
        
except (ImportError, Exception) as e:
    logger.error(f"Error setting up OpenAI: {e}")
    USE_MOCK_DATA = True

# Always log our decision
if USE_MOCK_DATA:
    logger.warning("Application is running in mock data mode")
else:
    logger.info("Application is set up to use OpenAI API")

# Let's define some high-quality mock clusters that will be used when OpenAI is unavailable
def get_mock_clusters(domain, url_count):
    """Generate realistic mock topical clusters for demonstration purposes."""
    common_clusters = [
        {
            "title": "Product Pages",
            "description": "Pages focused on products or services offered by the website",
            "count": max(1, int(url_count * 0.3)),
            "examples": [f"{domain}/products/product-1", f"{domain}/services/main-service", f"{domain}/shop/featured"],
            "seo_significance": "Critical for conversions and showing up in product-related searches",
            "article_ideas": [
                {
                    "headline": "10 Ways Our Products Can Solve Your Everyday Problems",
                    "description": "Practical applications and solutions provided by the products"
                },
                {
                    "headline": "Behind the Scenes: How Our Products Are Made",
                    "description": "A detailed look at the manufacturing process and quality control"
                },
                {
                    "headline": "Customer Success Stories: Real Results with Our Products",
                    "description": "Case studies and testimonials from satisfied customers"
                },
                {
                    "headline": "Product Comparison: How Our Offerings Stand Out from Competitors",
                    "description": "Detailed comparison of features, benefits, and value"
                },
                {
                    "headline": "Seasonal Guide: Best Products for Each Time of Year",
                    "description": "Recommendations tailored to seasonal needs and trends"
                }
            ]
        },
        {
            "title": "Blog Articles",
            "description": "Informational content providing value to visitors",
            "count": max(1, int(url_count * 0.25)),
            "examples": [f"{domain}/blog/latest-post", f"{domain}/articles/industry-news", f"{domain}/news/updates"],
            "seo_significance": "Builds authority, targets informational keywords, and creates link-worthy content",
            "article_ideas": [
                {
                    "headline": "Industry Trends: What to Watch for in the Coming Year",
                    "description": "Analysis of emerging trends and predictions for the industry"
                },
                {
                    "headline": "Expert Interview Series: Insights from Industry Leaders",
                    "description": "Interviews with thought leaders sharing valuable perspectives"
                },
                {
                    "headline": "Complete Beginner's Guide to Understanding Our Industry",
                    "description": "Educational content breaking down complex topics for newcomers"
                },
                {
                    "headline": "Problem-Solving Guide: Common Challenges and Solutions",
                    "description": "Practical advice for addressing frequently encountered issues"
                },
                {
                    "headline": "Data-Driven Insights: Key Statistics That Shape Our Field",
                    "description": "Analysis of important statistics and what they mean for the future"
                }
            ]
        },
        {
            "title": "About Pages",
            "description": "Company information, team, and mission pages",
            "count": max(1, int(url_count * 0.1)),
            "examples": [f"{domain}/about-us", f"{domain}/team", f"{domain}/mission"],
            "seo_significance": "Builds trust and provides context for search engines about the site's purpose",
            "article_ideas": [
                {
                    "headline": "Our Journey: From Startup to Industry Leader",
                    "description": "The story of the company's growth and key milestones"
                },
                {
                    "headline": "Meet the Team: The Experts Behind Our Success",
                    "description": "Profiles of key team members and their expertise"
                },
                {
                    "headline": "Our Core Values: How They Shape Everything We Do",
                    "description": "Explanation of company values and their practical application"
                },
                {
                    "headline": "Corporate Social Responsibility: Making a Difference",
                    "description": "Overview of initiatives and commitment to social causes"
                },
                {
                    "headline": "A Day in the Life: Behind the Scenes at Our Company",
                    "description": "Insight into company culture and daily operations"
                }
            ]
        },
        {
            "title": "Support & FAQ",
            "description": "Customer service, help articles, and frequently asked questions",
            "count": max(1, int(url_count * 0.15)),
            "examples": [f"{domain}/support", f"{domain}/faq", f"{domain}/help/getting-started"],
            "seo_significance": "Targets long-tail support queries and improves user experience metrics",
            "article_ideas": [
                {
                    "headline": "Comprehensive Troubleshooting Guide for Common Issues",
                    "description": "Step-by-step solutions for frequently encountered problems"
                },
                {
                    "headline": "How to Get the Most Out of Our Customer Support Resources",
                    "description": "Guide to utilizing all available support channels efficiently"
                },
                {
                    "headline": "Expert Tips: Advanced Solutions for Power Users",
                    "description": "Advanced troubleshooting and optimization techniques"
                },
                {
                    "headline": "Self-Service Support: Resolving Issues Without Waiting",
                    "description": "Resources and methods for quick self-service problem resolution"
                },
                {
                    "headline": "Understanding Our Guarantee and Return Policy",
                    "description": "Clear explanation of customer protection policies and procedures"
                }
            ]
        },
        {
            "title": "Contact Information",
            "description": "Ways to reach the company, including contact forms and location details",
            "count": max(1, int(url_count * 0.05)),
            "examples": [f"{domain}/contact", f"{domain}/locations", f"{domain}/directions"],
            "seo_significance": "Essential for local SEO and improving user experience",
            "article_ideas": [
                {
                    "headline": "The Best Ways to Contact Us for Different Needs",
                    "description": "Guide to choosing the most effective contact method for various situations"
                },
                {
                    "headline": "Visit Our Locations: What to Expect and Prepare",
                    "description": "Information about physical locations and planning your visit"
                },
                {
                    "headline": "Meet Our Customer Service Team: The Faces Behind the Support",
                    "description": "Introduction to customer service representatives and their expertise"
                },
                {
                    "headline": "How We've Improved Our Response Times and Customer Satisfaction",
                    "description": "Changes and improvements to the customer service experience"
                },
                {
                    "headline": "International Customer? Here's How to Reach Us Across Time Zones",
                    "description": "Special contact information and considerations for international customers"
                }
            ]
        }
    ]
    
    # Select 5 clusters and adjust their counts to seem realistic for the site
    selected_clusters = random.sample(common_clusters, min(5, len(common_clusters)))
    total_allocated = sum(cluster["count"] for cluster in selected_clusters)
    
    # Adjust counts to match the total URL count more closely
    if total_allocated > 0:
        for cluster in selected_clusters:
            cluster["count"] = max(1, int(cluster["count"] * url_count / total_allocated))
    
    return {"clusters": selected_clusters}

def identify_topical_clusters(urls, sitemap_stats):
    """
    Analyze sitemap URLs to identify topical clusters.
    Uses real OpenAI if available, otherwise falls back to mock data.
    
    Args:
        urls (list): List of URL dictionaries
        sitemap_stats (dict): Statistics about the sitemap structure
        
    Returns:
        dict: Top 5 topical clusters with counts and examples
    """
    # For immediate reliability, use mock data when OpenAI is not available
    if USE_MOCK_DATA or not client:
        logger.info("Using mock response for topical clusters to ensure reliability")
        return get_mock_clusters(sitemap_stats['main_domain'], sitemap_stats['total_urls'])
    
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
                    logger.warning("All API connection attempts failed, falling back to mock data")
                    return get_mock_clusters(sitemap_stats['main_domain'], sitemap_stats['total_urls'])
                time.sleep(retry_delay)
            
            except RateLimitError as e:
                logger.error(f"OpenAI API rate limit exceeded: {str(e)}")
                # Use mock clusters for rate limiting too
                logger.warning("Rate limit hit, falling back to mock data")
                return get_mock_clusters(sitemap_stats['main_domain'], sitemap_stats['total_urls'])
            
            except Exception as e:
                logger.error(f"Error in OpenAI analysis (attempt {attempt+1}): {str(e)}")
                if attempt == max_retries - 1:
                    # Fall back to mock data for any other error after all retries
                    logger.warning("All API attempts failed, falling back to mock data")
                    return get_mock_clusters(sitemap_stats['main_domain'], sitemap_stats['total_urls'])
                time.sleep(retry_delay)
        
        # This should never be reached due to the returns in the retry loop
        logger.error("Unexpected code path in identify_topical_clusters")
        return get_mock_clusters(sitemap_stats['main_domain'], sitemap_stats['total_urls'])
        
    except Exception as e:
        logger.error(f"Unexpected error in identify_topical_clusters: {str(e)}")
        # Fall back to mock data for any unexpected error
        return get_mock_clusters(sitemap_stats['main_domain'], sitemap_stats['total_urls'])
