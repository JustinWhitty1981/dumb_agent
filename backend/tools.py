"""
Tools for the LangChain agent.
Includes: current_time, web_search, web_scrape, and memory tools.
"""

from datetime import datetime
from langchain_core.tools import tool
from bs4 import BeautifulSoup
import httpx
import os

from memory import save_memory as mem_save, get_memory as mem_get, list_memories as mem_list


from datetime import datetime, timezone


@tool
def current_time() -> str:
    """
    Get the current date and time in both UTC (for ISO database queries) and local timezone.
    
    Returns:
        Current UTC date/time (ISO 8601) and local timezone date/time.
    """
    now_utc = datetime.now(timezone.utc)
    now_local = datetime.now()
    tz_name = os.getenv("TZ", "America/Chicago")
    return (
        f"Current UTC time (for UTC ISO parameters): {now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        f"Current Local time ({tz_name}): {now_local.strftime('%Y-%m-%d %H:%M:%S')}"
    )


@tool
def search_web(query: str) -> str:
    """
    Search the web using Tavily API.
    
    Args:
        query: The search query string.
        
    Returns:
        Search results with titles, snippets, and URLs.
    """
    try:
        from tavily import TavilyClient
        
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "Tavily API key not configured. Please set TAVILY_API_KEY environment variable."
        
        client = TavilyClient(api_key=api_key)
        
        # Search with Tavily
        response = client.search(query, search_depth="basic", max_results=5)
        
        if not response.get("results"):
            return "No search results found."
        
        formatted = []
        for i, result in enumerate(response["results"], 1):
            title = result.get("title", "No title")
            snippet = result.get("content", "No description")
            url = result.get("url", "No URL")
            formatted.append(f"{i}. **{title}**\n   {snippet}\n   URL: {url}")
        
        return "\n\n".join(formatted)
    except Exception as e:
        return f"Search failed: {str(e)}"


import ipaddress
import socket
from urllib.parse import urlparse


def validate_scrape_url(url_str: str) -> None:
    """Validates URL to prevent SSRF against loopback, link-local, or private IP ranges."""
    allow_internal = os.getenv("ALLOW_INTERNAL_SCRAPE", "").lower() in ("true", "1", "yes")
    if allow_internal:
        return

    parsed = urlparse(url_str)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(f"Forbidden URL scheme '{parsed.scheme}' (only http and https allowed).")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid host in URL.")

    try:
        ip_list = socket.getaddrinfo(hostname, None)
    except Exception as e:
        raise ValueError(f"Could not resolve host {hostname}: {e}")

    for addr in ip_list:
        ip_str = addr[4][0]
        ip_obj = ipaddress.ip_address(ip_str)
        if ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_private or ip_obj.is_multicast or ip_obj.is_unspecified:
            raise ValueError(f"Access to restricted or internal IP {ip_str} ({hostname}) is forbidden.")


@tool
def scrape_url(url: str) -> str:
    """
    Scrape content from a web page URL.
    
    Args:
        url: The URL to scrape.
        
    Returns:
        The text content extracted from the page.
    """
    try:
        validate_scrape_url(url)
    except Exception as e:
        return f"Scraping blocked by security policy: {str(e)}"

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        max_bytes = 2097152  # Default 2MB limit
        env_max = os.getenv("MAX_SCRAPE_BYTES", "").strip()
        if env_max.isdigit() and int(env_max) > 0:
            max_bytes = int(env_max)

        response_content = bytearray()
        with httpx.stream("GET", url, headers=headers, timeout=30.0, follow_redirects=True) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                response_content.extend(chunk)
                if len(response_content) >= max_bytes:
                    break

        soup = BeautifulSoup(response_content.decode("utf-8", errors="ignore"), "html.parser")
        
        # Remove script and style elements
        for script in soup(["script", "style", "noscript"]):
            script.decompose()
        
        # Extract text
        text = soup.get_text(separator="\n", strip=True)
        
        # Clean up whitespace
        lines = text.split("\n")
        cleaned_lines = [line.strip() for line in lines if line.strip()]
        cleaned_text = "\n".join(cleaned_lines)
        
        # Limit to reasonable length
        if len(cleaned_text) > 5000:
            cleaned_text = cleaned_text[:5000] + "\n\n... (content truncated)"
        
        return f"Content from {url}:\n\n{cleaned_text}"
    except httpx.RequestError as e:
        return f"Failed to fetch URL: {str(e)}"
    except Exception as e:
        return f"Scraping failed: {str(e)}"


@tool
def save_memory_tool(key: str, content: str) -> str:
    """
    Save information to memory storage.
    
    Args:
        key: A unique identifier for this memory.
        content: The content to store.
        
    Returns:
        Confirmation message with the memory key.
    """
    result = mem_save(key, content)
    return f"Memory saved as: {key}"


@tool
def get_memory_tool(key: str) -> str:
    """
    Retrieve stored information by key.
    
    Args:
        key: The memory key to look up.
        
    Returns:
        The stored content or a not found message.
    """
    return mem_get(key)


@tool
def list_memories_tool() -> str:
    """
    List all saved memory keys.
    
    Returns:
        A list of memory keys.
    """
    return mem_list()