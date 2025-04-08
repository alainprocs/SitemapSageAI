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
        logger.debug(f"Fetching sitemap from URL: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xml,application/xhtml+xml,text/xml;q=0.9,*/*;q=0.8',
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        # Check content type to handle different formats
        content_type = response.headers.get('Content-Type', '').lower()
        
        # Check if the content is gzipped either by URL or content type
        if url.endswith('.gz') or 'gzip' in content_type or 'application/x-gzip' in content_type:
            import gzip
            import io
            logger.debug("Detected gzipped content, decompressing")
            return gzip.GzipFile(fileobj=io.BytesIO(response.content)).read().decode('utf-8')
        
        # Handle JSON sitemaps (some modern sites use these)
        if 'application/json' in content_type:
            logger.debug("Detected JSON sitemap, converting to XML format")
            import json
            try:
                json_data = response.json()
                
                # Simple conversion of JSON to XML-like structure for processing
                if isinstance(json_data, list):
                    xml_content = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                    for item in json_data:
                        if isinstance(item, dict) and 'url' in item:
                            xml_content += f'<url><loc>{item["url"]}</loc>'
                            if 'lastmod' in item:
                                xml_content += f'<lastmod>{item["lastmod"]}</lastmod>'
                            xml_content += '</url>'
                    xml_content += '</urlset>'
                    return xml_content
            except Exception as e:
                logger.warning(f"Failed to convert JSON sitemap: {e}")
        
        # Some WordPress sites serve sitemaps with text/html content type
        # but the actual content is XML with an XSLT stylesheet
        if 'text/html' in content_type and '<?xml' in response.text:
            logger.debug("Detected XML content with HTML content type")
            
        # Check if we got actual content
        if not response.text or response.text.isspace():
            raise Exception("Empty response from server")
            
        logger.debug(f"Successfully fetched sitemap, size: {len(response.text)} bytes")
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
        # Handle XML namespaces - WordPress and other CMS sitemaps use different namespaces
        namespaces = {
            'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
            'xhtml': 'http://www.w3.org/1999/xhtml',
            'image': 'http://www.google.com/schemas/sitemap-image/1.1'
        }
        
        # Clean up potentially problematic XML declarations
        if '<?xml' in xml_content and '?>' in xml_content:
            # Keep only the first XML declaration to avoid parsing errors
            first_decl_end = xml_content.find('?>') + 2
            next_decl_start = xml_content.find('<?xml', first_decl_end)
            if next_decl_start > 0:
                xml_content = xml_content[:first_decl_end] + xml_content[next_decl_start + xml_content[next_decl_start:].find('?>') + 2:]
        
        # Parse the XML content
        root = ET.fromstring(xml_content)
        
        urls = []
        root_tag = root.tag
        
        # Extract namespace from root tag if present
        if '}' in root_tag:
            ns = root_tag.split('}')[0] + '}'
            plain_tag = root_tag.split('}')[1]
        else:
            ns = ''
            plain_tag = root_tag
        
        # Check if this is a sitemap index
        is_sitemap_index = 'sitemapindex' in plain_tag
        
        if is_sitemap_index:
            # Handle sitemap index (collection of sitemaps)
            logger.debug("Processing sitemap index")
            
            # Try different methods to find sitemap elements
            sitemap_elements = []
            for path in [
                ".//sm:sitemap", 
                ".//sitemap", 
                "./sitemap", 
                f".//{ns}sitemap",
                "./*"  # Fallback to all children if specific tags not found
            ]:
                try:
                    if path.startswith(".//sm:"):
                        elements = root.findall(path, namespaces)
                    else:
                        elements = root.findall(path)
                    if elements:
                        sitemap_elements = elements
                        logger.debug(f"Found {len(elements)} sitemap entries with path {path}")
                        break
                except Exception as e:
                    logger.warning(f"Error finding sitemap elements with path {path}: {e}")
            
            # Process found sitemap elements (limit to 3 for demo purposes)
            for sitemap_element in sitemap_elements[:3]:
                # Try different methods to find loc element
                loc_text = None
                for loc_path in ["sm:loc", "loc", f"{ns}loc"]:
                    try:
                        if loc_path.startswith("sm:"):
                            loc_element = sitemap_element.find(loc_path, namespaces)
                        else:
                            loc_element = sitemap_element.find(loc_path)
                        
                        if loc_element is not None and loc_element.text:
                            loc_text = loc_element.text.strip()
                            break
                    except Exception:
                        continue
                
                if loc_text:
                    sitemap_url = loc_text
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
            logger.debug("Processing regular sitemap")
            
            # Try different methods to find URL elements
            url_elements = []
            for path in [
                ".//sm:url", 
                ".//url", 
                "./url", 
                f".//{ns}url",
                "./*"  # Fallback to all children if specific tags not found
            ]:
                try:
                    if path.startswith(".//sm:"):
                        elements = root.findall(path, namespaces)
                    else:
                        elements = root.findall(path)
                    if elements:
                        url_elements = elements
                        logger.debug(f"Found {len(elements)} URL entries with path {path}")
                        break
                except Exception as e:
                    logger.warning(f"Error finding URL elements with path {path}: {e}")
            
            for url_element in url_elements:
                url_data = {}
                
                # Try different methods to find loc element
                loc_text = None
                for loc_path in ["sm:loc", "loc", f"{ns}loc"]:
                    try:
                        if loc_path.startswith("sm:"):
                            loc_element = url_element.find(loc_path, namespaces)
                        else:
                            loc_element = url_element.find(loc_path)
                        
                        if loc_element is not None and loc_element.text:
                            loc_text = loc_element.text.strip()
                            break
                    except Exception:
                        continue
                
                if loc_text:
                    url_data['loc'] = loc_text
                    
                    # Find lastmod element (try multiple paths)
                    for lastmod_path in ["sm:lastmod", "lastmod", f"{ns}lastmod"]:
                        try:
                            if lastmod_path.startswith("sm:"):
                                lastmod_element = url_element.find(lastmod_path, namespaces)
                            else:
                                lastmod_element = url_element.find(lastmod_path)
                            
                            if lastmod_element is not None and lastmod_element.text:
                                url_data['lastmod'] = lastmod_element.text.strip()
                                break
                        except Exception:
                            continue
                    
                    # Find changefreq element (try multiple paths)
                    for changefreq_path in ["sm:changefreq", "changefreq", f"{ns}changefreq"]:
                        try:
                            if changefreq_path.startswith("sm:"):
                                changefreq_element = url_element.find(changefreq_path, namespaces)
                            else:
                                changefreq_element = url_element.find(changefreq_path)
                            
                            if changefreq_element is not None and changefreq_element.text:
                                url_data['changefreq'] = changefreq_element.text.strip()
                                break
                        except Exception:
                            continue
                    
                    # Find priority element (try multiple paths)
                    for priority_path in ["sm:priority", "priority", f"{ns}priority"]:
                        try:
                            if priority_path.startswith("sm:"):
                                priority_element = url_element.find(priority_path, namespaces)
                            else:
                                priority_element = url_element.find(priority_path)
                            
                            if priority_element is not None and priority_element.text:
                                url_data['priority'] = priority_element.text.strip()
                                break
                        except Exception:
                            continue
                    
                    urls.append(url_data)
            
        logger.debug(f"Extracted {len(urls)} URLs from sitemap")
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
