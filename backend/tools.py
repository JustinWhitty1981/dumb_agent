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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        client = httpx.Client(headers=headers, timeout=30.0)
        response = client.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
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