import requests
import xml.etree.ElementTree as ET
import logging
import re
from urllib.parse import urlparse
from datetime import datetime

logger = logging.getLogger(__name__)

def fetch_sitemap(url):
    """
    Fetch the sitemap XML content from the given URL.
    
    Args:
        url (str): The URL of the sitemap
        
    Returns:
        str: The XML content of the sitemap
        
    Raises:
        Exception: If the sitemap cannot be fetched
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        # Check if the content is gzipped
        if url.endswith('.gz'):
            import gzip
            import io
            return gzip.GzipFile(fileobj=io.BytesIO(response.content)).read().decode('utf-8')
        
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching sitemap: {str(e)}")
        raise Exception(f"Failed to fetch sitemap: {str(e)}")

def parse_sitemap(xml_content):
    """
    Parse the XML content of a sitemap to extract URLs.
    
    Args:
        xml_content (str): The XML content of the sitemap
        
    Returns:
        list: A list of URL dictionaries with 'loc', 'lastmod', etc.
        
    Raises:
        Exception: If the sitemap cannot be parsed
    """
    try:
        # Handle XML namespaces
        namespaces = {
            'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
            'xhtml': 'http://www.w3.org/1999/xhtml'
        }
        
        root = ET.fromstring(xml_content)
        
        urls = []
        
        # Check if this is a sitemap index
        is_sitemap_index = root.tag.endswith('sitemapindex')
        
        if is_sitemap_index:
            # Handle sitemap index (collection of sitemaps)
            sitemap_elements = root.findall(".//sm:sitemap", namespaces)
            for sitemap_element in sitemap_elements[:3]:  # Limit to 3 sitemaps for demo
                loc_element = sitemap_element.find("sm:loc", namespaces)
                if loc_element is not None and loc_element.text:
                    sitemap_url = loc_element.text.strip()
                    logger.debug(f"Found sitemap: {sitemap_url}")
                    
                    # Recursively fetch and parse this sitemap
                    try:
                        sub_xml_content = fetch_sitemap(sitemap_url)
                        sub_urls = parse_sitemap(sub_xml_content)
                        urls.extend(sub_urls)
                    except Exception as e:
                        logger.warning(f"Couldn't process sub-sitemap {sitemap_url}: {str(e)}")
            
        else:
            # Handle regular sitemap
            url_elements = root.findall(".//sm:url", namespaces)
            if not url_elements:
                # Try without namespace
                url_elements = root.findall(".//url")
            
            for url_element in url_elements:
                url_data = {}
                
                # Find loc element (with or without namespace)
                loc_element = url_element.find("sm:loc", namespaces) or url_element.find("loc")
                if loc_element is not None and loc_element.text:
                    url_data['loc'] = loc_element.text.strip()
                    
                    # Find lastmod element (with or without namespace)
                    lastmod_element = url_element.find("sm:lastmod", namespaces) or url_element.find("lastmod") 
                    if lastmod_element is not None and lastmod_element.text:
                        url_data['lastmod'] = lastmod_element.text.strip()
                    
                    # Find changefreq element (with or without namespace)
                    changefreq_element = url_element.find("sm:changefreq", namespaces) or url_element.find("changefreq")
                    if changefreq_element is not None and changefreq_element.text:
                        url_data['changefreq'] = changefreq_element.text.strip()
                    
                    # Find priority element (with or without namespace)
                    priority_element = url_element.find("sm:priority", namespaces) or url_element.find("priority")
                    if priority_element is not None and priority_element.text:
                        url_data['priority'] = priority_element.text.strip()
                    
                    urls.append(url_data)
            
        return urls
        
    except ET.ParseError as e:
        logger.error(f"XML parsing error: {str(e)}")
        raise Exception(f"Invalid sitemap format: {str(e)}")
    except Exception as e:
        logger.error(f"Error parsing sitemap: {str(e)}")
        raise Exception(f"Failed to parse sitemap: {str(e)}")

def extract_path_components(url):
    """Extract path components from a URL."""
    parsed_url = urlparse(url)
    path = parsed_url.path
    
    # Remove file extensions like .html, .php
    path = re.sub(r'\.\w+$', '', path)
    
    # Split by slashes and filter out empty components
    components = [component for component in path.split('/') if component]
    
    return components

def analyze_sitemap_structure(urls):
    """
    Analyze the structure of the sitemap URLs.
    
    Args:
        urls (list): A list of URL dictionaries
        
    Returns:
        dict: Statistics about the sitemap structure
    """
    total_urls = len(urls)
    domains = {}
    path_depths = {}
    last_modified_dates = []
    
    for url_data in urls:
        url = url_data.get('loc', '')
        
        # Extract domain
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        domains[domain] = domains.get(domain, 0) + 1
        
        # Extract path components and analyze depth
        path_components = extract_path_components(url)
        depth = len(path_components)
        path_depths[depth] = path_depths.get(depth, 0) + 1
        
        # Analyze last modified dates if available
        if 'lastmod' in url_data and url_data['lastmod']:
            try:
                date_str = url_data['lastmod']
                # Handle different date formats
                for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S']:
                    try:
                        date = datetime.strptime(date_str, fmt)
                        last_modified_dates.append(date)
                        break
                    except ValueError:
                        continue
            except Exception as e:
                logger.warning(f"Could not parse date {url_data['lastmod']}: {str(e)}")
    
    # Calculate statistics
    stats = {
        'total_urls': total_urls,
        'domains': domains,
        'main_domain': max(domains.items(), key=lambda x: x[1])[0] if domains else None,
        'avg_depth': sum(depth * count for depth, count in path_depths.items()) / total_urls if total_urls > 0 else 0,
        'depth_distribution': path_depths,
        'has_lastmod': len(last_modified_dates) > 0,
    }
    
    # Add date range if last modified dates are available
    if last_modified_dates:
        stats['newest_page'] = max(last_modified_dates).strftime('%Y-%m-%d')
        stats['oldest_page'] = min(last_modified_dates).strftime('%Y-%m-%d')
    
    return stats
