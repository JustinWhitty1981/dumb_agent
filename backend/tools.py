"""
Tools for the LangChain agent.
Includes: current_time, web_search, web_scrape, and memory tools.
"""

from datetime import datetime
from langchain_core.tools import tool
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup
import httpx
import time
import random

from memory import save_memory as mem_save, get_memory as mem_get, list_memories as mem_list


@tool
def current_time() -> str:
    """
    Get the current date and time.
    
    Returns:
        Current date and time in a human-readable format.
    """
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


@tool
def search_web(query: str) -> str:
    """
    Search the web using DuckDuckGo.
    
    Args:
        query: The search query string.
        
    Returns:
        Search results with titles, snippets, and URLs.
    """
    max_retries = 7
    base_delay = 8  # Increased base delay to 8 seconds
    
    for attempt in range(max_retries):
        try:
            # Add random jitter to delay (between 0.8x and 1.5x of base delay)
            jitter = random.uniform(0.8, 1.5)
            delay = base_delay * (1.5 ** attempt) * jitter
            
            if attempt > 0:
                time.sleep(delay)
            
            # Use DDGS with safer settings to avoid rate limiting
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5, region="wt-wt"))
            
            if not results:
                return "No search results found."
            
            formatted = []
            for i, result in enumerate(results, 1):
                title = result.get("title", "No title")
                snippet = result.get("body", "No description")
                url = result.get("href", "No URL")
                formatted.append(f"{i}. **{title}**\n   {snippet}\n   URL: {url}")
            
            return "\n\n".join(formatted)
        except Exception as e:
            error_msg = str(e)
            # Check if it's a rate limit error
            if "ratelimit" in error_msg.lower() or "202" in error_msg or "429" in error_msg:
                if attempt < max_retries - 1:
                    continue
                else:
                    return f"Search failed after {max_retries} attempts due to rate limiting. Please try again in a few minutes."
            else:
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